"""Typed mass-item, installation, and provenance contracts (AIRFRAME 03).

Every component carries its own mass, local centre of gravity, local inertia
tensor, installation transform, category, and an explicit source/fidelity
record. There is deliberately no default mass: a missing value fails closed
rather than injecting a hidden estimate.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from aeroworkbench_core.types import FidelityLevel, Provenance, ResultSource

from ..canonical import content_digest
from ..frames import IDENTITY, Frame, Mat3, rotation_between
from ..state import InertiaTensor
from ..units import Quantity, Vec3, require_dimension
from .linalg import is_orthonormal

SOFTWARE_NAME = "aeroworkbench-airframe-mass"
SOFTWARE_VERSION = "1.0"

MASS_RESULT_UNITS: tuple[tuple[str, str], ...] = (
    ("mass", "kg"),
    ("length", "m"),
    ("moment_of_inertia", "kg.m2"),
)


class MassCategory(StrEnum):
    """Generic contributor categories; no platform-specific assumption."""

    PAYLOAD = "payload"
    BATTERY = "battery"
    PROPULSION = "propulsion"
    STRUCTURE = "structure"
    AVIONICS = "avionics"
    SYSTEMS = "systems"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class SoftwareIdentity:
    name: str
    version: str

    def __post_init__(self) -> None:
        if not self.name.strip() or not self.version.strip():
            raise ValueError("SOFTWARE_IDENTITY_REQUIRED")

    def as_dict(self) -> dict[str, Any]:
        return {"name": self.name, "version": self.version}


DEFAULT_SOFTWARE = SoftwareIdentity(SOFTWARE_NAME, SOFTWARE_VERSION)


@dataclass(frozen=True, slots=True)
class Validity:
    valid: bool
    notes: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {"valid": self.valid, "notes": list(self.notes)}


@dataclass(frozen=True, slots=True)
class MassItemSource:
    """Where one mass item came from; required for every item."""

    source: ResultSource
    fidelity: FidelityLevel
    method: str
    reference: str
    revision: str = "1"
    digest: str = ""
    software: SoftwareIdentity | None = None

    def __post_init__(self) -> None:
        if not self.method.strip():
            raise ValueError("MASS_SOURCE_METHOD_REQUIRED")
        if not self.reference.strip():
            raise ValueError("MASS_SOURCE_REFERENCE_REQUIRED")
        if not self.revision.strip():
            raise ValueError("MASS_SOURCE_REVISION_REQUIRED")
        if self.source is ResultSource.NATIVE_SOLVER and (
            not self.digest or self.software is None
        ):
            raise ValueError("NATIVE_MASS_SOURCE_REQUIRES_DIGEST_AND_SOFTWARE")

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "source": self.source.value,
            "fidelity": self.fidelity.value,
            "method": self.method,
            "reference": self.reference,
            "revision": self.revision,
            "digest": self.digest,
        }
        if self.software is not None:
            payload["software"] = self.software.as_dict()
        return payload


@dataclass(frozen=True, slots=True)
class MassResultMeta:
    """Uniform result metadata: source/fidelity/units/validity/hash/provenance."""

    source: ResultSource
    fidelity: FidelityLevel
    software: SoftwareIdentity
    units: tuple[tuple[str, str], ...]
    validity: Validity
    input_hash: str
    provenance: Provenance

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": self.source.value,
            "fidelity": self.fidelity.value,
            "software": self.software.as_dict(),
            "units": {dimension: unit for dimension, unit in self.units},
            "validity": self.validity.as_dict(),
            "inputHash": self.input_hash,
            "provenance": {
                "source": self.provenance.source.value,
                "model": self.provenance.model,
                "modelVersion": self.provenance.model_version,
                "fidelity": self.provenance.fidelity.value,
                "inputsHash": self.provenance.inputs_hash,
                "assumptions": list(self.provenance.assumptions),
            },
        }


def result_meta(
    *,
    model: str,
    inputs: Mapping[str, Any],
    valid: bool,
    notes: tuple[str, ...] = (),
    assumptions: tuple[str, ...] = (),
    software: SoftwareIdentity = DEFAULT_SOFTWARE,
    source: ResultSource = ResultSource.ANALYTICAL,
    fidelity: FidelityLevel = FidelityLevel.ANALYTICAL,
) -> MassResultMeta:
    """Build deterministic result metadata with an inputs hash and provenance."""
    provenance = Provenance.from_inputs(
        source=source,
        model=model,
        model_version=SOFTWARE_VERSION,
        fidelity=fidelity,
        inputs=dict(inputs),
        assumptions=assumptions,
    )
    return MassResultMeta(
        source=source,
        fidelity=fidelity,
        software=software,
        units=MASS_RESULT_UNITS,
        validity=Validity(valid=valid, notes=notes),
        input_hash=provenance.inputs_hash,
        provenance=provenance,
    )


@dataclass(frozen=True, slots=True)
class InstallationTransform:
    """Rigid placement of a local item frame into an aggregate frame.

    ``translation`` is the origin of ``from_frame`` measured in ``to_frame`` and
    ``rotation`` maps a vector expressed in ``from_frame`` into ``to_frame``.
    """

    from_frame: str
    to_frame: str
    translation: Vec3
    rotation: Mat3 = IDENTITY

    def __post_init__(self) -> None:
        if not self.from_frame.strip() or not self.to_frame.strip():
            raise ValueError("INSTALLATION_FRAMES_REQUIRED")
        require_dimension(self.translation, "length", "installation.translation")
        if self.translation.frame != self.to_frame:
            raise ValueError("INSTALLATION_TRANSLATION_FRAME_MISMATCH")
        if not is_orthonormal(self.rotation):
            raise ValueError("INSTALLATION_ROTATION_NOT_ORTHONORMAL")

    @classmethod
    def identity(cls, frame: str, *, translation: Vec3 | None = None) -> InstallationTransform:
        location = translation if translation is not None else Vec3(0.0, 0.0, 0.0, "m", frame)
        return cls(from_frame=frame, to_frame=frame, translation=location, rotation=IDENTITY)

    @classmethod
    def from_frames(
        cls,
        frames: tuple[Frame, ...],
        *,
        from_frame: str,
        to_frame: str,
        translation: Vec3,
    ) -> InstallationTransform:
        rotation = rotation_between(frames, from_frame, to_frame)
        return cls(
            from_frame=from_frame,
            to_frame=to_frame,
            translation=translation,
            rotation=rotation,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "fromFrame": self.from_frame,
            "toFrame": self.to_frame,
            "translation": self.translation.canonical(),
            "rotation": [[component for component in row] for row in self.rotation],
        }


@dataclass(frozen=True, slots=True)
class MassItem:
    """One component contributor with local mass properties and placement."""

    item_id: str
    category: MassCategory
    mass: Quantity
    cg: Vec3
    inertia: InertiaTensor
    installation: InstallationTransform
    source: MassItemSource

    def __post_init__(self) -> None:
        if not self.item_id.strip():
            raise ValueError("MASS_ITEM_ID_REQUIRED")
        require_dimension(self.mass, "mass", f"{self.item_id}.mass")
        if self.mass.value_si <= 0:
            raise ValueError(f"NONPOSITIVE_MASS_ITEM:{self.item_id}")
        require_dimension(self.cg, "length", f"{self.item_id}.cg")
        if self.cg.frame != self.installation.from_frame:
            raise ValueError(f"MASS_ITEM_CG_FRAME_MISMATCH:{self.item_id}")
        if self.inertia.frame != self.installation.from_frame:
            raise ValueError(f"MASS_ITEM_INERTIA_FRAME_MISMATCH:{self.item_id}")

    def canonical(self) -> dict[str, Any]:
        return {
            "id": self.item_id,
            "category": self.category.value,
            "mass": self.mass.canonical(),
            "cg": self.cg.canonical(),
            "inertia": self.inertia.canonical(),
            "installation": self.installation.as_dict(),
            "source": self.source.as_dict(),
        }

    def as_dict(self) -> dict[str, Any]:
        return self.canonical()


@dataclass(frozen=True, slots=True)
class MassBreakdown:
    """Deterministic, hashable set of component mass items for one vehicle."""

    vehicle_id: str
    frame: str
    items: tuple[MassItem, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.vehicle_id.strip() or not self.frame.strip():
            raise ValueError("MASS_BREAKDOWN_ID_AND_FRAME_REQUIRED")
        if not self.items:
            raise ValueError("EMPTY_MASS_BREAKDOWN")
        identifiers = [item.item_id for item in self.items]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("DUPLICATE_MASS_ITEM_ID")
        for item in self.items:
            if item.installation.to_frame != self.frame:
                raise ValueError(f"MASS_ITEM_INSTALLATION_FRAME_MISMATCH:{item.item_id}")

    def item(self, item_id: str) -> MassItem:
        for candidate in self.items:
            if candidate.item_id == item_id:
                return candidate
        raise KeyError(f"UNKNOWN_MASS_ITEM:{item_id}")

    def sorted_items(self) -> tuple[MassItem, ...]:
        return tuple(sorted(self.items, key=lambda item: item.item_id))

    def contributors(self, category: MassCategory) -> tuple[MassItem, ...]:
        return tuple(item for item in self.sorted_items() if item.category is category)

    def canonical(self) -> dict[str, Any]:
        return {
            "vehicleId": self.vehicle_id,
            "frame": self.frame,
            "items": [item.canonical() for item in self.sorted_items()],
        }

    def as_dict(self) -> dict[str, Any]:
        return self.canonical()

    @property
    def content_hash(self) -> str:
        return content_digest(self.canonical())

    def with_item(self, item: MassItem) -> MassBreakdown:
        """Return a new breakdown with ``item`` replacing or adding by id."""
        updated: list[MassItem] = [
            existing for existing in self.items if existing.item_id != item.item_id
        ]
        updated.append(item)
        return MassBreakdown(vehicle_id=self.vehicle_id, frame=self.frame, items=tuple(updated))
