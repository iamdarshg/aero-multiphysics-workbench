"""Evidence status: measurement and simulation are kept distinct forever.

An :class:`EvidenceRecord` is the single provenance-backed status object for a
piece of engineering evidence. It validates that a measurement is never
labelled native solver output, that the record's source matches its provenance,
and that the ``native`` flag is only set for an actually executed external
engine. Experimental agreement may be recorded as corroboration, but it can
never retroactively relabel an analytical result as native solver output.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aeroworkbench_core.types import Provenance, ResultSource
from aeroworkbench_optimization.design_space import content_digest

from .contracts import (
    DEFAULT_SOFTWARE,
    EvidenceFidelity,
    EvidenceKind,
    SoftwareIdentity,
    Validity,
)
from .errors import EvidenceError, finite
from .provenance import measurement_provenance

__all__ = [
    "CorroborationResult",
    "EvidenceRecord",
    "assert_no_relabel",
    "corroborate",
    "measurement_evidence",
    "promote_to_native",
    "simulation_evidence",
]

_DIGITAL_KINDS = (EvidenceKind.SIMULATION,)
_PHYSICAL_KINDS = (
    EvidenceKind.MEASUREMENT,
    EvidenceKind.REPLAY,
    EvidenceKind.HARDWARE_IN_LOOP,
)


@dataclass(frozen=True, slots=True)
class EvidenceRecord:
    """The provenance-backed status of one engineering result."""

    evidence_id: str
    kind: EvidenceKind
    fidelity: EvidenceFidelity
    source: ResultSource
    unit: str
    validity: Validity
    inputs_hash: str
    software: SoftwareIdentity
    provenance: Provenance
    native: bool

    def __post_init__(self) -> None:
        if not self.evidence_id.strip():
            raise EvidenceError("EVIDENCE_ID_REQUIRED")
        if not self.unit.strip():
            raise EvidenceError("EVIDENCE_UNIT_REQUIRED")
        if self.source is not self.provenance.source:
            raise EvidenceError("EVIDENCE_SOURCE_PROVENANCE_MISMATCH")
        if self.native != (self.source is ResultSource.NATIVE_SOLVER):
            raise EvidenceError("EVIDENCE_NATIVE_FLAG_MISMATCH")
        if self.kind in _PHYSICAL_KINDS and self.source is ResultSource.NATIVE_SOLVER:
            raise EvidenceError(f"MEASUREMENT_CANNOT_BE_NATIVE_SOLVER:{self.evidence_id}")
        if (
            self.kind in _DIGITAL_KINDS
            and self.native
            and (not self.provenance.solver_name or not self.provenance.run_id)
        ):
            raise EvidenceError(f"NATIVE_SIMULATION_NEEDS_SOLVER_IDENTITY:{self.evidence_id}")

    def canonical(self) -> dict[str, Any]:
        return {
            "evidenceId": self.evidence_id,
            "kind": self.kind.value,
            "fidelity": self.fidelity.value,
            "source": self.source.value,
            "unit": self.unit,
            "validity": self.validity.canonical(),
            "inputsHash": self.inputs_hash,
            "software": self.software.canonical(),
            "native": self.native,
            "provenance": self.provenance.model_dump(mode="json"),
        }

    def as_dict(self) -> dict[str, Any]:
        return self.canonical()

    def digest(self) -> str:
        return content_digest(self.canonical())


def measurement_evidence(
    *,
    evidence_id: str,
    unit: str,
    validity: Validity,
    inputs_hash: str,
    provenance: Provenance,
    fidelity: EvidenceFidelity = EvidenceFidelity.MEASURED,
    kind: EvidenceKind = EvidenceKind.MEASUREMENT,
    software: SoftwareIdentity = DEFAULT_SOFTWARE,
) -> EvidenceRecord:
    """Build measured-data evidence; a native source is rejected."""

    return EvidenceRecord(
        evidence_id=evidence_id,
        kind=kind,
        fidelity=fidelity,
        source=provenance.source,
        unit=unit,
        validity=validity,
        inputs_hash=inputs_hash,
        software=software,
        provenance=provenance,
        native=provenance.source is ResultSource.NATIVE_SOLVER,
    )


def simulation_evidence(
    *,
    evidence_id: str,
    unit: str,
    validity: Validity,
    inputs_hash: str,
    provenance: Provenance,
    fidelity: EvidenceFidelity = EvidenceFidelity.CALIBRATED,
    kind: EvidenceKind = EvidenceKind.SIMULATION,
    software: SoftwareIdentity = DEFAULT_SOFTWARE,
) -> EvidenceRecord:
    """Build simulation evidence, optionally native if provenance says so."""

    return EvidenceRecord(
        evidence_id=evidence_id,
        kind=kind,
        fidelity=fidelity,
        source=provenance.source,
        unit=unit,
        validity=validity,
        inputs_hash=inputs_hash,
        software=software,
        provenance=provenance,
        native=provenance.source is ResultSource.NATIVE_SOLVER,
    )


def assert_no_relabel(base: EvidenceRecord, requested_source: ResultSource) -> None:
    """Fail closed on any attempt to relabel non-native evidence as native."""

    non_native_base = base.source is not ResultSource.NATIVE_SOLVER
    if requested_source is ResultSource.NATIVE_SOLVER and non_native_base:
        raise EvidenceError(f"CANNOT_RELABEL_AS_NATIVE_SOLVER:{base.evidence_id}")


def promote_to_native(base: EvidenceRecord) -> EvidenceRecord:
    """Native evidence stays native; non-native evidence can never be promoted."""

    assert_no_relabel(base, ResultSource.NATIVE_SOLVER)
    return base


@dataclass(frozen=True, slots=True)
class CorroborationResult:
    """Experimental corroboration that leaves the base source untouched."""

    base: EvidenceRecord
    experimental: EvidenceRecord
    agreement: float
    tolerance: float
    experimentally_supported: bool
    validity: Validity
    inputs_hash: str
    software: SoftwareIdentity
    provenance: Provenance

    @property
    def relabelled_source(self) -> ResultSource:
        """The base result's source, which corroboration never changes."""

        return self.base.source

    def canonical(self) -> dict[str, Any]:
        return {
            "base": self.base.digest(),
            "experimental": self.experimental.digest(),
            "agreement": self.agreement,
            "tolerance": self.tolerance,
            "experimentallySupported": self.experimentally_supported,
            "relabelledSource": self.relabelled_source.value,
            "validity": self.validity.canonical(),
            "inputsHash": self.inputs_hash,
            "software": self.software.canonical(),
        }

    def digest(self) -> str:
        return content_digest(self.canonical())


def corroborate(
    base: EvidenceRecord,
    experimental: EvidenceRecord,
    *,
    agreement: float,
    tolerance: float,
) -> CorroborationResult:
    """Record experimental agreement without relabelling the base evidence."""

    if base.kind not in _DIGITAL_KINDS:
        raise EvidenceError(f"CORROBORATION_BASE_MUST_BE_SIMULATION:{base.evidence_id}")
    if experimental.kind not in _PHYSICAL_KINDS:
        raise EvidenceError(f"CORROBORATION_NEEDS_PHYSICAL_EVIDENCE:{experimental.evidence_id}")
    finite(agreement, "agreement", minimum=0.0)
    finite(tolerance, "tolerance", minimum=0.0)
    supported = agreement <= tolerance
    payload = {
        "base": base.digest(),
        "experimental": experimental.digest(),
        "agreement": agreement,
        "tolerance": tolerance,
    }
    return CorroborationResult(
        base=base,
        experimental=experimental,
        agreement=agreement,
        tolerance=tolerance,
        experimentally_supported=supported,
        validity=Validity(
            passed=supported,
            checks={"within-tolerance": supported},
            detail=""
            if supported
            else f"experimental agreement {agreement:.6g} exceeds {tolerance:.6g}",
        ),
        inputs_hash=content_digest(payload),
        software=DEFAULT_SOFTWARE,
        provenance=measurement_provenance(
            "experimental-corroboration",
            payload,
            assumptions=(
                "base evidence source is never changed by experimental agreement",
                "measurement and simulation remain separately labelled",
            ),
        ),
    )
