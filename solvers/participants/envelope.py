"""Canonical ResultEnvelope with evidence-gated native publication.

A native result is publishable only when the full evidence chain exists:
accepted capability probe, immutable input hash, actual run id, successful
process receipt, stdout/stderr artifact references, parser receipt, expected
output files, artifact hashes, solver identity/version, geometry and mesh
hashes where relevant, participant manifest version, and a validity result.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from .errors import NativeErrorCode, ParticipantError
from .receipts import ParseReceipt, ValidityReport

_HEX64 = r"^[0-9a-f]{64}$"


class ArtifactFile(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1)
    sha256: str = Field(pattern=_HEX64)
    bytes: int = Field(ge=0)


class EvidenceBundle(BaseModel):
    """Complete evidence chain required to publish one native result."""

    model_config = ConfigDict(frozen=True)

    capability_state: str = Field(pattern=r"^(ready)$")
    capability_detail: str = Field(min_length=1)
    solver_name: str = Field(min_length=1)
    solver_version: str = Field(min_length=1)
    input_hash: str = Field(pattern=_HEX64)
    run_id: str = Field(min_length=1)
    process_state: str = Field(pattern=r"^(completed)$")
    exit_code: int = Field(ge=0, le=0)
    peak_rss_mib: float | None = Field(default=None, ge=0)
    execution_mode: str = Field(default="subprocess", pattern=r"^(subprocess|in-process)$")
    stdout_sha256: str | None = Field(default=None, pattern=_HEX64)
    stderr_sha256: str | None = Field(default=None, pattern=_HEX64)
    parser_name: str = Field(min_length=1)
    parser_detail: str = Field(default="")
    output_files: tuple[ArtifactFile, ...] = Field(min_length=1)
    geometry_hash: str | None = Field(default=None, pattern=_HEX64)
    mesh_hash: str | None = Field(default=None, pattern=_HEX64)
    participant_id: str = Field(min_length=1)
    manifest_version: str = Field(min_length=1)
    validity_passed: bool
    validity_detail: str = Field(default="")


class ResultEnvelope(BaseModel):
    """Canonical durable result: units, validity, identity, provenance."""

    model_config = ConfigDict(frozen=True)

    source: str = Field(pattern=r"^(native_solver)$")
    fidelity: str = Field(min_length=1)
    units: dict[str, str] = Field(min_length=1)
    validity: ValidityReport
    input_hash: str = Field(pattern=_HEX64)
    solver_identity: str = Field(min_length=1)
    solver_version: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    provenance_id: str = Field(min_length=1)
    warnings: tuple[str, ...] = ()
    scalars: dict[str, float] = Field(default_factory=dict)
    artifacts: tuple[ArtifactFile, ...] = ()


def publish_result(
    evidence: EvidenceBundle,
    *,
    parse: ParseReceipt,
    validity: ValidityReport,
    fidelity: str,
    provenance_id: str,
    warnings: tuple[str, ...] = (),
    expected_artifacts: tuple[str, ...] = (),
) -> ResultEnvelope:
    """Publish a native ResultEnvelope only from a complete evidence chain."""

    if evidence.participant_id != parse.participant_id:
        raise ParticipantError(
            NativeErrorCode.RESULT_INVALID, "evidence/parse participant mismatch"
        )
    if evidence.participant_id != validity.participant_id:
        raise ParticipantError(
            NativeErrorCode.RESULT_INVALID, "evidence/validity participant mismatch"
        )
    if not validity.passed or not evidence.validity_passed:
        raise ParticipantError(NativeErrorCode.RESULT_INVALID, "validity did not pass")
    if evidence.execution_mode == "subprocess" and (
        evidence.stdout_sha256 is None or evidence.stderr_sha256 is None
    ):
        raise ParticipantError(
            NativeErrorCode.RESULT_INVALID, "subprocess evidence needs stdout/stderr hashes"
        )
    if expected_artifacts:
        produced = {artifact.name for artifact in evidence.output_files}
        missing = [name for name in expected_artifacts if name not in produced]
        if missing:
            raise ParticipantError(
                NativeErrorCode.RESULT_INVALID, f"missing expected artifacts:{','.join(missing)}"
            )
    if not fidelity.strip():
        raise ParticipantError(NativeErrorCode.RESULT_INVALID, "fidelity is required")
    if not provenance_id.strip():
        raise ParticipantError(NativeErrorCode.RESULT_INVALID, "provenance id is required")
    for name, value in parse.scalars.items():
        if value != value or value in (float("inf"), float("-inf")):
            raise ParticipantError(
                NativeErrorCode.RESULT_INVALID, f"non-finite scalar:{name}"
            )
    return ResultEnvelope(
        source="native_solver",
        fidelity=fidelity,
        units=dict(parse.units) or {"dimensionless": "dimensionless"},
        validity=validity,
        input_hash=evidence.input_hash,
        solver_identity=evidence.solver_name,
        solver_version=evidence.solver_version,
        run_id=evidence.run_id,
        provenance_id=provenance_id,
        warnings=tuple(warnings),
        scalars=dict(parse.scalars),
        artifacts=tuple(evidence.output_files),
    )
