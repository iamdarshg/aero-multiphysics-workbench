"""Explicit, provenance-backed surface roughness for aerodynamic regions.

Every roughness input names its model, carries an SI equivalent sand-grain
value, cites a source, and records a canonical input hash. There are no hidden
roughness constants: a caller cannot create a roughness state without a source.
Degraded, iced, eroded, or fouled roughness produced by ADV-PHYS 08 is imported
through :func:`roughness_from_degradation`, which adds the declared increments to
a base state instead of inventing a value.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite
from typing import TYPE_CHECKING, Any

from aeroworkbench_core.types import Provenance
from aeroworkbench_fluid_properties import SoftwareIdentity

from .contracts import (
    SOFTWARE_IDENTITY,
    analytical_provenance,
)
from .errors import TurbulenceValidationError

if TYPE_CHECKING:
    from aeroworkbench_environmental import DegradationState


class RoughnessModel(StrEnum):
    """The declared roughness model behind an equivalent sand-grain value."""

    HYDRAULICALLY_SMOOTH = "hydraulically_smooth"
    EQUIVALENT_SAND_GRAIN = "equivalent_sand_grain"
    MANUFACTURED_FINISH = "manufactured_finish"
    ICED = "iced"
    ERODED = "eroded"
    FOULED = "fouled"


@dataclass(frozen=True, slots=True)
class RoughnessSpec:
    """One named surface's declared roughness with full provenance."""

    surface: str
    model: RoughnessModel
    equivalent_sand_grain_m: float
    source: str
    provenance: Provenance
    finish_state: str | None = None
    degraded_from: str | None = None
    revision: str = "1"
    software: SoftwareIdentity = SOFTWARE_IDENTITY

    def __post_init__(self) -> None:
        if not self.surface.strip():
            raise TurbulenceValidationError("ROUGHNESS_SURFACE_REQUIRED")
        if not self.source.strip():
            raise TurbulenceValidationError("ROUGHNESS_SOURCE_REQUIRED")
        if not self.revision.strip():
            raise TurbulenceValidationError("ROUGHNESS_REVISION_REQUIRED")
        if not isfinite(self.equivalent_sand_grain_m) or self.equivalent_sand_grain_m < 0.0:
            raise TurbulenceValidationError("INVALID_EQUIVALENT_SAND_GRAIN")
        if self.finish_state is not None and not self.finish_state.strip():
            raise TurbulenceValidationError("ROUGHNESS_FINISH_STATE_EMPTY")
        if self.degraded_from is not None and not self.degraded_from.strip():
            raise TurbulenceValidationError("ROUGHNESS_DEGRADED_FROM_EMPTY")

    @property
    def hydraulically_smooth(self) -> bool:
        return self.equivalent_sand_grain_m == 0.0

    def sand_grain_ratio(self, length_m: float) -> float:
        """Return ``ks / L``; the roughness length must be positive."""
        if not isfinite(length_m) or length_m <= 0.0:
            raise TurbulenceValidationError("ROUGHNESS_REFERENCE_LENGTH_INVALID")
        return self.equivalent_sand_grain_m / length_m

    def canonical(self) -> dict[str, Any]:
        return {
            "surface": self.surface,
            "model": self.model.value,
            "equivalentSandGrainM": self.equivalent_sand_grain_m,
            "finishState": self.finish_state,
            "degradedFrom": self.degraded_from,
            "revision": self.revision,
            "source": self.source,
            "units": {"equivalentSandGrainM": "m"},
            "inputsHash": self.provenance.inputs_hash,
            "software": self.software.canonical(),
        }


def make_roughness(
    *,
    surface: str,
    model: RoughnessModel,
    equivalent_sand_grain_m: float,
    source: str,
    finish_state: str | None = None,
    degraded_from: str | None = None,
    revision: str = "1",
) -> RoughnessSpec:
    """Build a roughness state, refusing any anonymous value."""
    provenance = analytical_provenance(
        f"turbulence.roughness.{model.value}",
        {
            "surface": surface,
            "model": model.value,
            "equivalentSandGrainM": equivalent_sand_grain_m,
            "finishState": finish_state,
            "degradedFrom": degraded_from,
            "revision": revision,
            "source": source,
        },
        f"declared roughness source: {source}",
    )
    return RoughnessSpec(
        surface=surface,
        model=model,
        equivalent_sand_grain_m=equivalent_sand_grain_m,
        source=source,
        provenance=provenance,
        finish_state=finish_state,
        degraded_from=degraded_from,
        revision=revision,
    )


SMOOTH_ROUGHNESS = make_roughness(
    surface="default",
    model=RoughnessModel.HYDRAULICALLY_SMOOTH,
    equivalent_sand_grain_m=0.0,
    source="hydraulically-smooth declared assumption",
)


def apply_roughness_increment(
    base: RoughnessSpec,
    *,
    increment_m: float,
    model: RoughnessModel,
    source: str,
    detail: str = "",
) -> RoughnessSpec:
    """Add a declared roughness increment to a base state (never negative)."""
    if not isfinite(increment_m) or increment_m < 0.0:
        raise TurbulenceValidationError("ROUGHNESS_INCREMENT_INVALID")
    if not source.strip():
        raise TurbulenceValidationError("ROUGHNESS_SOURCE_REQUIRED")
    total = base.equivalent_sand_grain_m + increment_m
    provenance = analytical_provenance(
        f"turbulence.roughness.increment.{model.value}",
        {
            "baseHash": base.provenance.inputs_hash,
            "baseEquivalentSandGrainM": base.equivalent_sand_grain_m,
            "incrementM": increment_m,
            "model": model.value,
            "source": source,
            "detail": detail,
        },
        f"base roughness {base.model.value} + declared increment",
        f"increment source: {source}",
    )
    return RoughnessSpec(
        surface=base.surface,
        model=model,
        equivalent_sand_grain_m=total,
        source=source,
        provenance=provenance,
        finish_state=base.finish_state,
        degraded_from=base.model.value,
        revision=base.revision,
    )


_DEGRADED_ROUGHNESS_QUANTITIES = (
    "leading_edge_roughness_increment",
    "surface_roughness_increment",
)


def roughness_from_degradation(
    degradation: DegradationState,
    *,
    base: RoughnessSpec = SMOOTH_ROUGHNESS,
    surface: str | None = None,
) -> RoughnessSpec:
    """Convert an ADV-PHYS 08 degradation state into a roughness state.

    Only the explicitly declared roughness increments are summed. The result
    model is chosen from the degradation kinds so an iced, eroded, or fouled
    surface is never mislabelled. The degradation digest is recorded in the
    roughness provenance.
    """
    from aeroworkbench_environmental import DegradationKind

    increment = 0.0
    kinds: list[DegradationKind] = []
    for modifier in degradation.modifiers:
        if modifier.quantity_name not in _DEGRADED_ROUGHNESS_QUANTITIES:
            continue
        increment += float(modifier.delta.value_si)
        kinds.append(modifier.kind)
    if DegradationKind.LEADING_EDGE_ROUGHNESS in kinds:
        model = RoughnessModel.ICED
    elif DegradationKind.EROSION_MATERIAL_LOSS in kinds:
        model = RoughnessModel.ERODED
    elif DegradationKind.DEPOSIT_FOULING in kinds:
        model = RoughnessModel.FOULED
    else:
        model = RoughnessModel.MANUFACTURED_FINISH
    provenance = analytical_provenance(
        "turbulence.roughness.degradation",
        {
            "degradationHash": degradation.provenance.inputs_hash,
            "degradationModel": degradation.model_id,
            "baseHash": base.provenance.inputs_hash,
            "incrementM": increment,
            "model": model.value,
            "surface": surface or base.surface,
        },
        "roughness derived from declared environmental degradation",
        f"degradation model: {degradation.model_id}",
    )
    return RoughnessSpec(
        surface=surface or base.surface,
        model=model,
        equivalent_sand_grain_m=base.equivalent_sand_grain_m + increment,
        source=f"aeroworkbench-environmental:{degradation.model_id}",
        provenance=provenance,
        finish_state=base.finish_state,
        degraded_from=base.model.value,
        revision=base.revision,
    )


__all__ = [
    "SMOOTH_ROUGHNESS",
    "RoughnessModel",
    "RoughnessSpec",
    "apply_roughness_increment",
    "make_roughness",
    "roughness_from_degradation",
]
