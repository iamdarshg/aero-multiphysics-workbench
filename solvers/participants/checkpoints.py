"""Immutable checkpoint lineage, trusted-resume compatibility, and retry policy.

A checkpoint receipt is the only evidence that lets a governed job resume
instead of restarting from scratch. Resume is fail-closed: a changed upstream
physical input, an incompatible solver/image version, a corrupted artifact, or
an invalid lineage all reject the resume. Retries are classified and bounded so
solver divergence can never trigger a blind paid loop.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from participants.errors import (
    GovernanceErrorCode,
    NativeErrorCode,
    ParticipantError,
)
from participants.manifest import CheckpointMode

__all__ = [
    "CheckpointArtifact",
    "CheckpointMode",
    "CheckpointReceipt",
    "CheckpointCompatibility",
    "RetryClass",
    "RetryPolicy",
    "checkpoint_id_for",
    "classify_failure",
    "make_checkpoint_receipt",
    "verify_resume_compatibility",
]

_HEX = "0123456789abcdef"


def _is_hex64(value: str | None) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in _HEX for c in value)


def checkpoint_id_for(payload: Mapping[str, Any]) -> str:
    """Deterministic content address for a checkpoint payload."""

    try:
        encoded = json.dumps(dict(payload), sort_keys=True, separators=(",", ":")).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError(f"INVALID_CHECKPOINT_PAYLOAD:{exc}") from exc
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class CheckpointArtifact:
    """One checkpoint file with its immutable content hash."""

    name: str
    sha256: str
    bytes: int

    def __post_init__(self) -> None:
        if not self.name.strip() or "/" in self.name or "\\" in self.name:
            raise ValueError(f"INVALID_CHECKPOINT_ARTIFACT:{self.name}")
        if not _is_hex64(self.sha256):
            raise ValueError(f"INVALID_CHECKPOINT_ARTIFACT_HASH:{self.name}")
        if self.bytes < 0:
            raise ValueError(f"INVALID_CHECKPOINT_ARTIFACT_SIZE:{self.name}")


@dataclass(frozen=True, slots=True)
class CheckpointReceipt:
    """Immutable proof that a trusted restart point exists for one attempt."""

    checkpoint_id: str
    job_id: str
    run_id: str
    participant_id: str
    solver_id: str
    solver_version: str
    input_hash: str
    sequence: int
    created_at: str
    artifacts: tuple[CheckpointArtifact, ...]
    geometry_hash: str | None = None
    mesh_hash: str | None = None
    upstream_hashes: tuple[tuple[str, str], ...] = ()
    image_digest: str | None = None
    resume_of: str | None = None
    compatibility: tuple[tuple[str, str], ...] = ()
    detail: str = ""

    def __post_init__(self) -> None:
        if not _is_hex64(self.checkpoint_id):
            raise ValueError("CHECKPOINT_RECEIPT_NEEDS_ID")
        if not _is_hex64(self.input_hash):
            raise ValueError("CHECKPOINT_RECEIPT_NEEDS_INPUT_HASH")
        if not self.job_id.strip() or not self.run_id.strip():
            raise ValueError("CHECKPOINT_RECEIPT_NEEDS_LINEAGE")
        if not self.participant_id.strip() or not self.solver_id.strip():
            raise ValueError("CHECKPOINT_RECEIPT_NEEDS_IDENTITY")
        if self.sequence < 0:
            raise ValueError("CHECKPOINT_SEQUENCE_INVALID")
        if not self.artifacts:
            raise ValueError("CHECKPOINT_RECEIPT_NEEDS_ARTIFACTS")
        for name, value in self.upstream_hashes:
            if not name.strip() or not _is_hex64(value):
                raise ValueError(f"INVALID_UPSTREAM_HASH:{name}")

    def to_payload(self) -> dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "job_id": self.job_id,
            "run_id": self.run_id,
            "participant_id": self.participant_id,
            "solver_id": self.solver_id,
            "solver_version": self.solver_version,
            "input_hash": self.input_hash,
            "geometry_hash": self.geometry_hash,
            "mesh_hash": self.mesh_hash,
            "upstream_hashes": [list(item) for item in self.upstream_hashes],
            "sequence": self.sequence,
            "created_at": self.created_at,
            "image_digest": self.image_digest,
            "resume_of": self.resume_of,
            "compatibility": [list(item) for item in self.compatibility],
            "detail": self.detail,
            "artifacts": [
                {"name": a.name, "sha256": a.sha256, "bytes": a.bytes}
                for a in self.artifacts
            ],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_payload(), sort_keys=True, separators=(",", ":"))


def make_checkpoint_receipt(
    *,
    job_id: str,
    run_id: str,
    participant_id: str,
    solver_id: str,
    solver_version: str,
    input_hash: str,
    sequence: int,
    created_at: str,
    artifacts: tuple[CheckpointArtifact, ...],
    geometry_hash: str | None = None,
    mesh_hash: str | None = None,
    upstream_hashes: tuple[tuple[str, str], ...] = (),
    image_digest: str | None = None,
    resume_of: str | None = None,
    compatibility: tuple[tuple[str, str], ...] = (),
    detail: str = "",
) -> CheckpointReceipt:
    payload = {
        "job_id": job_id,
        "run_id": run_id,
        "participant_id": participant_id,
        "solver_id": solver_id,
        "solver_version": solver_version,
        "input_hash": input_hash,
        "geometry_hash": geometry_hash,
        "mesh_hash": mesh_hash,
        "upstream_hashes": [list(item) for item in upstream_hashes],
        "sequence": sequence,
        "created_at": created_at,
        "image_digest": image_digest,
        "resume_of": resume_of,
        "artifacts": [
            {"name": a.name, "sha256": a.sha256, "bytes": a.bytes} for a in artifacts
        ],
    }
    return CheckpointReceipt(
        checkpoint_id=checkpoint_id_for(payload),
        job_id=job_id,
        run_id=run_id,
        participant_id=participant_id,
        solver_id=solver_id,
        solver_version=solver_version,
        input_hash=input_hash,
        sequence=sequence,
        created_at=created_at,
        artifacts=artifacts,
        geometry_hash=geometry_hash,
        mesh_hash=mesh_hash,
        upstream_hashes=upstream_hashes,
        image_digest=image_digest,
        resume_of=resume_of,
        compatibility=compatibility,
        detail=detail,
    )


@dataclass(frozen=True, slots=True)
class CheckpointCompatibility:
    """Result of proving (or refusing) a trusted resume."""

    ok: bool
    reason: str
    checks: Mapping[str, bool]

    def __post_init__(self) -> None:
        object.__setattr__(self, "checks", dict(self.checks))

    def require_ok(self) -> None:
        if not self.ok:
            code: NativeErrorCode | GovernanceErrorCode = {
                "CORRUPTED_ARTIFACT": GovernanceErrorCode.CHECKPOINT_CORRUPT,
            }.get(self.reason, GovernanceErrorCode.CHECKPOINT_INCOMPATIBLE)
            raise ParticipantError(code, f"resume refused:{self.reason}")


_CHECK_ORDER: tuple[str, ...] = (
    "input_hash",
    "geometry_hash",
    "mesh_hash",
    "solver_id",
    "solver_version",
    "image_digest",
    "artifacts",
    "lineage",
)


def verify_resume_compatibility(
    receipt: CheckpointReceipt,
    *,
    expected_input_hash: str,
    expected_solver_id: str,
    expected_solver_version: str | None = None,
    expected_image_digest: str | None = None,
    expected_geometry_hash: str | None = None,
    expected_mesh_hash: str | None = None,
    live_artifact_hashes: Mapping[str, str | None] | None = None,
    lineage_ok: bool = True,
) -> CheckpointCompatibility:
    """Prove a checkpoint is a trusted restart point for the current request."""

    checks: dict[str, bool] = {
        "input_hash": receipt.input_hash == expected_input_hash,
        "geometry_hash": (
            True
            if expected_geometry_hash is None
            else receipt.geometry_hash == expected_geometry_hash
        ),
        "mesh_hash": (
            True
            if expected_mesh_hash is None
            else receipt.mesh_hash == expected_mesh_hash
        ),
        "solver_id": receipt.solver_id == expected_solver_id,
        "solver_version": (
            True
            if expected_solver_version is None
            else receipt.solver_version == expected_solver_version
        ),
        "image_digest": (
            True
            if expected_image_digest is None
            else receipt.image_digest == expected_image_digest
        ),
        "lineage": bool(lineage_ok),
    }
    artifacts_ok = True
    if live_artifact_hashes is not None:
        for artifact in receipt.artifacts:
            live = live_artifact_hashes.get(artifact.name)
            if live is None or live != artifact.sha256:
                artifacts_ok = False
                break
    checks["artifacts"] = artifacts_ok

    reasons = {
        "input_hash": "CHANGED_INPUT",
        "geometry_hash": "CHANGED_GEOMETRY",
        "mesh_hash": "CHANGED_MESH",
        "solver_id": "INCOMPATIBLE_SOLVER",
        "solver_version": "INCOMPATIBLE_SOLVER_VERSION",
        "image_digest": "INCOMPATIBLE_IMAGE",
        "artifacts": "CORRUPTED_ARTIFACT",
        "lineage": "INVALID_LINEAGE",
    }
    for key in _CHECK_ORDER:
        if not checks[key]:
            return CheckpointCompatibility(False, reasons[key], checks)
    return CheckpointCompatibility(True, "", checks)


class RetryClass(StrEnum):
    """Closed classification of a failed attempt's retry eligibility."""

    INFRASTRUCTURE_TRANSIENT = "infrastructure-transient"
    SOLVER_DIVERGENCE = "solver-divergence"
    INVALID_INPUT = "invalid-input"
    USER_CANCELLATION = "user-cancellation"
    BUDGET_EXHAUSTION = "budget-exhaustion"


_RETRY_BY_CODE: dict[str, RetryClass] = {
    GovernanceErrorCode.PREEMPTED.value: RetryClass.INFRASTRUCTURE_TRANSIENT,
    NativeErrorCode.INTERRUPTED.value: RetryClass.INFRASTRUCTURE_TRANSIENT,
    NativeErrorCode.PROCESS_START_FAILED.value: RetryClass.INFRASTRUCTURE_TRANSIENT,
    NativeErrorCode.PROCESS_TIMEOUT.value: RetryClass.INFRASTRUCTURE_TRANSIENT,
    NativeErrorCode.CAPABILITY_UNAVAILABLE.value: RetryClass.INFRASTRUCTURE_TRANSIENT,
    NativeErrorCode.PROCESS_EXIT_NONZERO.value: RetryClass.SOLVER_DIVERGENCE,
    NativeErrorCode.PROCESS_RSS_LIMIT_EXCEEDED.value: RetryClass.SOLVER_DIVERGENCE,
    NativeErrorCode.PARSER_FAILED.value: RetryClass.SOLVER_DIVERGENCE,
    NativeErrorCode.QUALITY_GATE_FAILED.value: RetryClass.SOLVER_DIVERGENCE,
    NativeErrorCode.RESULT_INVALID.value: RetryClass.SOLVER_DIVERGENCE,
    NativeErrorCode.PREPARATION_FAILED.value: RetryClass.INVALID_INPUT,
    NativeErrorCode.MESH_INVALID.value: RetryClass.INVALID_INPUT,
    NativeErrorCode.ADMISSION_REJECTED.value: RetryClass.INVALID_INPUT,
    NativeErrorCode.CANCELLED.value: RetryClass.USER_CANCELLATION,
    GovernanceErrorCode.COST_LIMIT_EXCEEDED.value: RetryClass.BUDGET_EXHAUSTION,
    GovernanceErrorCode.REMOTE_COMPUTE_NOT_AUTHORIZED.value: RetryClass.USER_CANCELLATION,
    GovernanceErrorCode.CHECKPOINT_UNSUPPORTED.value: RetryClass.INVALID_INPUT,
    GovernanceErrorCode.CHECKPOINT_INCOMPATIBLE.value: RetryClass.INVALID_INPUT,
    GovernanceErrorCode.CHECKPOINT_CORRUPT.value: RetryClass.INVALID_INPUT,
    GovernanceErrorCode.RESUME_REJECTED.value: RetryClass.INVALID_INPUT,
}


def classify_failure(
    error_code: NativeErrorCode | GovernanceErrorCode | str | None,
    *,
    reason: str | None = None,
) -> RetryClass:
    """Classify a failure so only transient infrastructure failures retry."""

    code = (
        error_code.value
        if isinstance(error_code, (NativeErrorCode, GovernanceErrorCode))
        else error_code
    )
    if code is not None and code in _RETRY_BY_CODE:
        return _RETRY_BY_CODE[code]
    if reason and "PREEMPT" in reason.upper():
        return RetryClass.INFRASTRUCTURE_TRANSIENT
    return RetryClass.SOLVER_DIVERGENCE


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Bounded retry budget; empty ``auto_resume_classes`` means no auto-resume."""

    max_attempts: int = 1
    auto_resume_classes: frozenset[RetryClass] = frozenset()

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("INVALID_RETRY_POLICY")

    def may_retry(self, retry_class: RetryClass, attempt: int) -> bool:
        if attempt >= self.max_attempts:
            return False
        return retry_class in self.auto_resume_classes
