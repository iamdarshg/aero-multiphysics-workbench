"""Generic, revisioned manufacturing-process and hardware-limit envelopes.

An envelope is *data*: it is serializable, content-addressed, and versioned, and
it reuses the canonical design-space hashing primitives so it binds into the
existing design-revision system instead of inventing a parallel one. Envelopes
never encode application-specific logic; they carry declarative scalar limits
plus conditional activation predicates.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from enum import StrEnum
from math import isfinite
from typing import Any

from aeroworkbench_optimization.design_space import canonical_json, content_digest

from .units import to_si, unit_dimension

__all__ = [
    "BOUND_LIMIT_KINDS",
    "LIMIT_SCHEMA_VERSION",
    "STAGE_ORDER",
    "ConstraintClass",
    "EnvelopeBinding",
    "EnvelopeError",
    "EnvelopeSet",
    "EvaluationStage",
    "HardwareLimitEnvelope",
    "LimitProvenance",
    "LimitRelation",
    "LimitSourceKind",
    "ManufacturingProcessEnvelope",
    "ScalarLimit",
    "bind_envelopes",
]

LIMIT_SCHEMA_VERSION = "turbo05-v1"


class EnvelopeError(ValueError):
    """Raised when an envelope document is structurally invalid."""


class LimitRelation(StrEnum):
    LESS_OR_EQUAL = "lessOrEqual"
    GREATER_OR_EQUAL = "greaterOrEqual"
    EQUAL = "equal"


class EvaluationStage(StrEnum):
    PRE_CAD_ALGEBRAIC = "pre-cad-algebraic"
    POST_CAD_GEOMETRY = "post-cad-geometry"
    PRE_SOLVER_PHYSICS = "pre-solver-physics"
    NATIVE_SOLVER_VALIDATED = "native-solver-validated"


#: Cheapest-to-most-expensive evaluation order; hard limits at a stage are
#: cleared before the next stage may run.
STAGE_ORDER: tuple[EvaluationStage, ...] = (
    EvaluationStage.PRE_CAD_ALGEBRAIC,
    EvaluationStage.POST_CAD_GEOMETRY,
    EvaluationStage.PRE_SOLVER_PHYSICS,
    EvaluationStage.NATIVE_SOLVER_VALIDATED,
)


class ConstraintClass(StrEnum):
    HARD = "hard"
    SOFT = "soft"


class LimitSourceKind(StrEnum):
    MATERIAL = "material"
    BEARING = "bearing"
    MOTOR = "motor"
    MANUFACTURING_METHOD = "manufacturing-method"
    USER_REQUIREMENT = "user-requirement"
    CERTIFIED_COMPONENT = "certified-component"
    REGULATION = "regulation"


@dataclass(frozen=True, slots=True)
class LimitProvenance:
    """Where a limit came from; required for every limit."""

    source_kind: LimitSourceKind
    reference: str
    revision: str = "1"
    digest: str = ""
    software: str | None = None

    def __post_init__(self) -> None:
        if not self.reference.strip():
            raise EnvelopeError("LIMIT_PROVENANCE_REFERENCE_REQUIRED")
        if not self.revision.strip():
            raise EnvelopeError("LIMIT_PROVENANCE_REVISION_REQUIRED")

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "sourceKind": self.source_kind.value,
            "reference": self.reference,
            "revision": self.revision,
            "digest": self.digest,
        }
        if self.software is not None:
            payload["software"] = self.software
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> LimitProvenance:
        return cls(
            source_kind=LimitSourceKind(str(payload["sourceKind"])),
            reference=str(payload["reference"]),
            revision=str(payload.get("revision", "1")),
            digest=str(payload.get("digest", "")),
            software=None if payload.get("software") is None else str(payload["software"]),
        )


@dataclass(frozen=True, slots=True)
class ScalarLimit:
    """One declarative scalar constraint with provenance and a stage."""

    id: str
    value_name: str
    relation: LimitRelation
    limit: float
    unit: str
    stage: EvaluationStage
    constraint_class: ConstraintClass = ConstraintClass.HARD
    provenance: LimitProvenance = field(
        default_factory=lambda: LimitProvenance(
            LimitSourceKind.USER_REQUIREMENT, "unspecified"
        )
    )
    applies_when: Mapping[str, Any] | None = None
    recommended_variables: tuple[str, ...] = ()
    detail: str = ""

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise EnvelopeError("LIMIT_ID_REQUIRED")
        if not self.value_name.strip():
            raise EnvelopeError(f"LIMIT_VALUE_NAME_REQUIRED:{self.id}")
        if not isfinite(self.limit):
            raise EnvelopeError(f"NONFINITE_LIMIT:{self.id}")
        unit_dimension(self.unit)

    @property
    def limit_si(self) -> float:
        return to_si(self.limit, self.unit)

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.id,
            "valueName": self.value_name,
            "relation": self.relation.value,
            "limit": self.limit,
            "unit": self.unit,
            "stage": self.stage.value,
            "constraintClass": self.constraint_class.value,
            "provenance": self.provenance.as_dict(),
            "recommendedVariables": list(self.recommended_variables),
            "detail": self.detail,
        }
        if self.applies_when is not None:
            payload["appliesWhen"] = dict(self.applies_when)
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> ScalarLimit:
        applies_when = payload.get("appliesWhen")
        return cls(
            id=str(payload["id"]),
            value_name=str(payload.get("valueName", payload.get("value_name", ""))),
            relation=LimitRelation(str(payload["relation"])),
            limit=float(payload["limit"]),
            unit=str(payload["unit"]),
            stage=EvaluationStage(str(payload["stage"])),
            constraint_class=ConstraintClass(
                str(payload.get("constraintClass", ConstraintClass.HARD.value))
            ),
            provenance=LimitProvenance.from_dict(payload["provenance"]),
            applies_when=None if applies_when is None else dict(applies_when),
            recommended_variables=tuple(
                str(item) for item in payload.get("recommendedVariables", ())
            ),
            detail=str(payload.get("detail", "")),
        )


@dataclass(frozen=True, slots=True)
class ManufacturingProcessEnvelope:
    """A named manufacturing process with its capability and process limits."""

    id: str
    process: str
    revision: int = 1
    limits: tuple[ScalarLimit, ...] = ()
    capability: Mapping[str, Any] = field(default_factory=dict)
    applies_when: Mapping[str, Any] | None = None
    provenance: LimitProvenance | None = None
    schema_version: str = LIMIT_SCHEMA_VERSION
    parent_hash: str | None = None

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.process.strip():
            raise EnvelopeError("PROCESS_ENVELOPE_NEEDS_ID_AND_PROCESS")
        if self.revision < 1:
            raise EnvelopeError(f"INVALID_ENVELOPE_REVISION:{self.id}")
        _require_unique_limits(self.limits, self.id)

    def content_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "kind": "manufacturing-process",
            "id": self.id,
            "process": self.process,
            "revision": self.revision,
            "limits": [limit.as_dict() for limit in self.limits],
            "capability": dict(self.capability),
            "schemaVersion": self.schema_version,
            "parentHash": self.parent_hash,
        }
        if self.applies_when is not None:
            payload["appliesWhen"] = dict(self.applies_when)
        if self.provenance is not None:
            payload["provenance"] = self.provenance.as_dict()
        return payload

    def as_dict(self) -> dict[str, Any]:
        payload = self.content_payload()
        payload["contentHash"] = self.content_hash
        return payload

    @property
    def content_hash(self) -> str:
        return content_digest(self.content_payload())

    def revise(self, **changes: Any) -> ManufacturingProcessEnvelope:
        """Revision bump that records the previous content hash as parent."""

        if "revision" in changes:
            raise EnvelopeError("REVISE_MUST_NOT_SET_REVISION")
        return replace(self, **changes, revision=self.revision + 1, parent_hash=self.content_hash)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> ManufacturingProcessEnvelope:
        applies_when = payload.get("appliesWhen")
        provenance = payload.get("provenance")
        return cls(
            id=str(payload["id"]),
            process=str(payload["process"]),
            revision=int(payload.get("revision", 1)),
            limits=tuple(ScalarLimit.from_dict(item) for item in payload.get("limits", ())),
            capability=dict(payload.get("capability", {})),
            applies_when=None if applies_when is None else dict(applies_when),
            provenance=None if provenance is None else LimitProvenance.from_dict(provenance),
            schema_version=str(payload.get("schemaVersion", LIMIT_SCHEMA_VERSION)),
            parent_hash=None if payload.get("parentHash") is None else str(payload["parentHash"]),
        )


@dataclass(frozen=True, slots=True)
class HardwareLimitEnvelope:
    """A named component/assembly with its mechanical operating limits."""

    id: str
    component: str
    revision: int = 1
    limits: tuple[ScalarLimit, ...] = ()
    applies_when: Mapping[str, Any] | None = None
    provenance: LimitProvenance | None = None
    schema_version: str = LIMIT_SCHEMA_VERSION
    parent_hash: str | None = None

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.component.strip():
            raise EnvelopeError("HARDWARE_ENVELOPE_NEEDS_ID_AND_COMPONENT")
        if self.revision < 1:
            raise EnvelopeError(f"INVALID_ENVELOPE_REVISION:{self.id}")
        _require_unique_limits(self.limits, self.id)

    def content_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "kind": "hardware-limit",
            "id": self.id,
            "component": self.component,
            "revision": self.revision,
            "limits": [limit.as_dict() for limit in self.limits],
            "schemaVersion": self.schema_version,
            "parentHash": self.parent_hash,
        }
        if self.applies_when is not None:
            payload["appliesWhen"] = dict(self.applies_when)
        if self.provenance is not None:
            payload["provenance"] = self.provenance.as_dict()
        return payload

    def as_dict(self) -> dict[str, Any]:
        payload = self.content_payload()
        payload["contentHash"] = self.content_hash
        return payload

    @property
    def content_hash(self) -> str:
        return content_digest(self.content_payload())

    def revise(self, **changes: Any) -> HardwareLimitEnvelope:
        if "revision" in changes:
            raise EnvelopeError("REVISE_MUST_NOT_SET_REVISION")
        return replace(self, **changes, revision=self.revision + 1, parent_hash=self.content_hash)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> HardwareLimitEnvelope:
        applies_when = payload.get("appliesWhen")
        provenance = payload.get("provenance")
        return cls(
            id=str(payload["id"]),
            component=str(payload["component"]),
            revision=int(payload.get("revision", 1)),
            limits=tuple(ScalarLimit.from_dict(item) for item in payload.get("limits", ())),
            applies_when=None if applies_when is None else dict(applies_when),
            provenance=None if provenance is None else LimitProvenance.from_dict(provenance),
            schema_version=str(payload.get("schemaVersion", LIMIT_SCHEMA_VERSION)),
            parent_hash=None if payload.get("parentHash") is None else str(payload["parentHash"]),
        )


BOUND_LIMIT_KINDS = ("manufacturing", "hardware")


def _require_unique_limits(limits: Sequence[ScalarLimit], envelope_id: str) -> None:
    seen: set[str] = set()
    for limit in limits:
        if limit.id in seen:
            raise EnvelopeError(f"DUPLICATE_LIMIT:{envelope_id}:{limit.id}")
        seen.add(limit.id)


@dataclass(frozen=True, slots=True)
class EnvelopeSet:
    """The complete set of process and hardware envelopes bound to a revision."""

    manufacturing: tuple[ManufacturingProcessEnvelope, ...] = ()
    hardware: tuple[HardwareLimitEnvelope, ...] = ()
    schema_version: str = LIMIT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        ids = [envelope.id for envelope in self.manufacturing]
        ids.extend(envelope.id for envelope in self.hardware)
        if len(ids) != len(set(ids)):
            raise EnvelopeError("DUPLICATE_ENVELOPE_ID")

    def as_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": self.schema_version,
            "manufacturing": [envelope.as_dict() for envelope in self.manufacturing],
            "hardware": [envelope.as_dict() for envelope in self.hardware],
        }

    @property
    def content_hash(self) -> str:
        return content_digest(self.as_dict())

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> EnvelopeSet:
        return cls(
            manufacturing=tuple(
                ManufacturingProcessEnvelope.from_dict(item)
                for item in payload.get("manufacturing", ())
            ),
            hardware=tuple(
                HardwareLimitEnvelope.from_dict(item) for item in payload.get("hardware", ())
            ),
            schema_version=str(payload.get("schemaVersion", LIMIT_SCHEMA_VERSION)),
        )


@dataclass(frozen=True, slots=True)
class EnvelopeBinding:
    """The revision binding placed into a design revision document."""

    envelope_set_hash: str
    design_revision_hash: str | None = None
    schema_version: str = LIMIT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not self.envelope_set_hash.strip():
            raise EnvelopeError("ENVELOPE_BINDING_HASH_REQUIRED")

    def as_dict(self) -> dict[str, Any]:
        return {
            "envelopeSetHash": self.envelope_set_hash,
            "designRevisionHash": self.design_revision_hash,
            "schemaVersion": self.schema_version,
        }


def bind_envelopes(
    design_revision: Mapping[str, Any],
    envelopes: EnvelopeSet,
) -> dict[str, Any]:
    """Return the envelope section bound to ``design_revision``.

    The design revision document is not mutated; the returned mapping is the
    section a caller embeds (e.g. under ``computePolicy.manufacturingEnvelopes``)
    so the revision hash and the envelope-set hash stay verifiable together.
    """

    revision_hash = design_revision.get("contentHash")
    binding = EnvelopeBinding(
        envelope_set_hash=envelopes.content_hash,
        design_revision_hash=None if revision_hash is None else str(revision_hash),
        schema_version=envelopes.schema_version,
    )
    return {
        "section": "manufacturing-envelopes",
        "binding": binding.as_dict(),
        "envelopes": envelopes.as_dict(),
    }


def verify_binding(section: Mapping[str, Any], envelopes: EnvelopeSet) -> None:
    """Fail closed when a bound envelope section does not match the data."""

    binding = section.get("binding")
    if not isinstance(binding, Mapping):
        raise EnvelopeError("ENVELOPE_BINDING_MISSING")
    if str(binding.get("envelopeSetHash")) != envelopes.content_hash:
        raise EnvelopeError("ENVELOPE_BINDING_HASH_MISMATCH")
    if str(section.get("section")) != "manufacturing-envelopes":
        raise EnvelopeError("ENVELOPE_BINDING_SECTION_MISMATCH")


def canonical_envelope_json(envelopes: EnvelopeSet) -> str:
    return canonical_json(envelopes.as_dict())
