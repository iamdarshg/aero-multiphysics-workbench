"""Typed structural load cases and seams from aero/trim/mass contracts.

A :class:`StructuralLoadCase` is a unit-bearing, hashable description of the
spanwise and discrete loads a structure must carry: a linear distributed normal
load, point loads, and a declared load factor. Load cases are built from typed
seams (:class:`AeroLoadSeam`, :class:`TrimLoadSeam`, :class:`MassLoadSeam`) so an
external-aerodynamics result, a trim solve, or a mass item can be consumed
without importing those workstreams. A :class:`LoadEnvelope` folds several cases
into the root bending moment, shear, and axial demand a sizing pass uses.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from math import isfinite
from typing import Any

from .contracts import content_digest
from .errors import LoadCaseError

__all__ = [
    "AeroLoadSeam",
    "DistributedLoad",
    "LoadEnvelope",
    "LoadSource",
    "MassLoadSeam",
    "PointLoad",
    "StructuralLoadCase",
    "StructuralLoadSet",
    "TrimLoadSeam",
    "load_case_from_aero",
    "load_case_from_mass",
    "load_case_from_trim",
    "load_case_from_landing_gear",
    "load_case_from_propulsor",
    "ground_load_set_for_segment",
]

STANDARD_GRAVITY_M_S2 = 9.80665


class LoadSource(StrEnum):
    """Where a structural load case originated."""

    EXTERNAL_AERO = "external_aero"
    TRIM = "trim"
    MASS = "mass"
    LANDING = "landing"
    PROPULSION = "propulsion"


@dataclass(frozen=True, slots=True)
class DistributedLoad:
    """A linear distributed load from root intensity to tip intensity (N/m)."""

    root_intensity_n_per_m: float
    tip_intensity_n_per_m: float
    start_fraction: float = 0.0
    end_fraction: float = 1.0

    def __post_init__(self) -> None:
        for label, value in (
            ("ROOT_INTENSITY", self.root_intensity_n_per_m),
            ("TIP_INTENSITY", self.tip_intensity_n_per_m),
        ):
            if not isfinite(value):
                raise LoadCaseError(f"DISTRIBUTED_LOAD_{label}_NOT_FINITE")
        if not 0.0 <= self.start_fraction < self.end_fraction <= 1.0:
            raise LoadCaseError("DISTRIBUTED_LOAD_FRACTION_RANGE_INVALID")

    def normal_force_n(self, span_m: float) -> float:
        length = span_m * (self.end_fraction - self.start_fraction)
        return 0.5 * (self.root_intensity_n_per_m + self.tip_intensity_n_per_m) * length

    def root_bending_moment_n_m(self, span_m: float) -> float:
        length = span_m * (self.end_fraction - self.start_fraction)
        w0 = self.root_intensity_n_per_m
        w1 = self.tip_intensity_n_per_m
        return length * length * (w0 + 2.0 * w1) / 6.0

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "rootIntensityNPerM": self.root_intensity_n_per_m,
            "tipIntensityNPerM": self.tip_intensity_n_per_m,
            "startFraction": self.start_fraction,
            "endFraction": self.end_fraction,
        }


@dataclass(frozen=True, slots=True)
class PointLoad:
    """A discrete six-component-ish load at a span fraction."""

    fraction: float
    normal_n: float
    axial_n: float = 0.0
    shear_n: float = 0.0

    def __post_init__(self) -> None:
        if not 0.0 <= self.fraction <= 1.0:
            raise LoadCaseError("POINT_LOAD_FRACTION_OUT_OF_RANGE")
        for label, value in (
            ("NORMAL", self.normal_n),
            ("AXIAL", self.axial_n),
            ("SHEAR", self.shear_n),
        ):
            if not isfinite(value):
                raise LoadCaseError(f"POINT_LOAD_{label}_NOT_FINITE")

    def as_dict(self) -> dict[str, float]:
        return {
            "fraction": self.fraction,
            "normalN": self.normal_n,
            "axialN": self.axial_n,
            "shearN": self.shear_n,
        }


@dataclass(frozen=True, slots=True)
class StructuralLoadCase:
    """One typed, hashable structural load case."""

    case_id: str
    source: LoadSource
    component_id: str
    span_m: float
    load_factor: float = 1.0
    distributed: tuple[DistributedLoad, ...] = ()
    point: tuple[PointLoad, ...] = ()
    reference: str = ""
    applied_moments_n_m: tuple[float, float, float] = (0.0, 0.0, 0.0)

    def __post_init__(self) -> None:
        if not self.case_id.strip() or not self.component_id.strip():
            raise LoadCaseError("LOAD_CASE_ID_AND_COMPONENT_REQUIRED")
        if not isfinite(self.span_m) or self.span_m <= 0.0:
            raise LoadCaseError("LOAD_CASE_SPAN_MUST_BE_POSITIVE")
        if not isfinite(self.load_factor) or self.load_factor <= 0.0:
            raise LoadCaseError("LOAD_CASE_FACTOR_MUST_BE_POSITIVE")
        if len(self.applied_moments_n_m) != 3 or any(not isfinite(value) for value in self.applied_moments_n_m):  # noqa: E501
            raise LoadCaseError("LOAD_CASE_APPLIED_MOMENTS_INVALID")

    def normal_force_n(self) -> float:
        total = sum(load.normal_force_n(self.span_m) for load in self.distributed)
        total += sum(load.normal_n for load in self.point)
        return total * self.load_factor

    def root_bending_moment_n_m(self) -> float:
        total = sum(
            load.root_bending_moment_n_m(self.span_m) for load in self.distributed
        )
        total += sum(load.normal_n * load.fraction * self.span_m for load in self.point)
        return total * self.load_factor

    def total_shear_n(self) -> float:
        total = sum(load.shear_n for load in self.point)
        return total * self.load_factor

    def total_axial_n(self) -> float:
        total = sum(load.axial_n for load in self.point)
        return total * self.load_factor

    def with_load_factor(self, load_factor: float) -> StructuralLoadCase:
        if not isfinite(load_factor) or load_factor <= 0.0:
            raise LoadCaseError("LOAD_CASE_FACTOR_MUST_BE_POSITIVE")
        return replace(self, load_factor=load_factor)

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "caseId": self.case_id,
            "source": self.source.value,
            "componentId": self.component_id,
            "spanM": self.span_m,
            "loadFactor": self.load_factor,
            "distributed": [load.canonical_payload() for load in self.distributed],
            "point": [load.as_dict() for load in self.point],
            "reference": self.reference,
            "appliedMomentsNm": list(self.applied_moments_n_m),
        }

    @property
    def digest(self) -> str:
        return content_digest(self.canonical_payload())


@dataclass(frozen=True, slots=True)
class LoadEnvelope:
    """Folded governing demand from one or more load cases."""

    component_id: str
    span_m: float
    root_bending_n_m: float
    total_shear_n: float
    total_axial_n: float
    normal_force_n: float
    case_ids: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "componentId": self.component_id,
            "spanM": self.span_m,
            "rootBendingNm": self.root_bending_n_m,
            "totalShearN": self.total_shear_n,
            "totalAxialN": self.total_axial_n,
            "normalForceN": self.normal_force_n,
            "caseIds": list(self.case_ids),
        }


@dataclass(frozen=True, slots=True)
class StructuralLoadSet:
    """A component's load cases with deterministic envelope folding."""

    component_id: str
    load_cases: tuple[StructuralLoadCase, ...]

    def __post_init__(self) -> None:
        if not self.component_id.strip():
            raise LoadCaseError("LOAD_SET_COMPONENT_REQUIRED")
        if not self.load_cases:
            raise LoadCaseError("LOAD_SET_REQUIRES_CASES")
        identifiers = [case.case_id for case in self.load_cases]
        if len(identifiers) != len(set(identifiers)):
            raise LoadCaseError("LOAD_SET_DUPLICATE_CASE_ID")
        for case in self.load_cases:
            if case.component_id != self.component_id:
                raise LoadCaseError(
                    f"LOAD_CASE_COMPONENT_MISMATCH:{case.case_id}"
                )

    def envelope(self, span_m: float) -> LoadEnvelope:
        root = max(case.root_bending_moment_n_m() for case in self.load_cases)
        shear = max(abs(case.total_shear_n()) for case in self.load_cases)
        axial = max(abs(case.total_axial_n()) for case in self.load_cases)
        normal = max(abs(case.normal_force_n()) for case in self.load_cases)
        return LoadEnvelope(
            component_id=self.component_id,
            span_m=span_m,
            root_bending_n_m=root,
            total_shear_n=shear,
            total_axial_n=axial,
            normal_force_n=normal,
            case_ids=tuple(sorted(case.case_id for case in self.load_cases)),
        )

    def scaled(self, factor: float) -> StructuralLoadSet:
        return StructuralLoadSet(
            component_id=self.component_id,
            load_cases=tuple(
                case.with_load_factor(case.load_factor * factor)
                for case in self.load_cases
            ),
        )

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "componentId": self.component_id,
            "loadCases": [
                case.canonical_payload()
                for case in sorted(self.load_cases, key=lambda item: item.case_id)
            ],
        }

    @property
    def digest(self) -> str:
        return content_digest(self.canonical_payload())


def _linear_distributed(
    normal_force_n: float, span_m: float, tip_to_root_ratio: float
) -> DistributedLoad:
    if not isfinite(tip_to_root_ratio) or tip_to_root_ratio < 0.0:
        raise LoadCaseError("TIP_TO_ROOT_RATIO_INVALID")
    if not isfinite(normal_force_n):
        raise LoadCaseError("NORMAL_FORCE_NOT_FINITE")
    denominator = span_m * (1.0 + tip_to_root_ratio)
    if denominator <= 0.0:
        raise LoadCaseError("DISTRIBUTED_LOAD_DENOMINATOR_INVALID")
    root_intensity = 2.0 * normal_force_n / denominator
    return DistributedLoad(
        root_intensity_n_per_m=root_intensity,
        tip_intensity_n_per_m=root_intensity * tip_to_root_ratio,
    )


@dataclass(frozen=True, slots=True)
class AeroLoadSeam:
    """External-aerodynamics output: a spanwise normal force and axial force."""

    component_id: str
    normal_force_n: float
    span_m: float
    tip_to_root_ratio: float = 0.6
    axial_force_n: float = 0.0
    load_factor: float = 1.0
    reference: str = "external-aero"

    def __post_init__(self) -> None:
        if not self.component_id.strip():
            raise LoadCaseError("AERO_SEAM_COMPONENT_REQUIRED")
        if not isfinite(self.span_m) or self.span_m <= 0.0:
            raise LoadCaseError("AERO_SEAM_SPAN_MUST_BE_POSITIVE")


@dataclass(frozen=True, slots=True)
class TrimLoadSeam:
    """Trim/loads output: a trimmed normal force at a declared load factor."""

    component_id: str
    normal_force_n: float
    span_m: float
    load_factor: float
    tip_to_root_ratio: float = 0.6
    axial_force_n: float = 0.0
    reference: str = "trim"

    def __post_init__(self) -> None:
        if not self.component_id.strip():
            raise LoadCaseError("TRIM_SEAM_COMPONENT_REQUIRED")
        if not isfinite(self.span_m) or self.span_m <= 0.0:
            raise LoadCaseError("TRIM_SEAM_SPAN_MUST_BE_POSITIVE")
        if not isfinite(self.load_factor) or self.load_factor <= 0.0:
            raise LoadCaseError("TRIM_SEAM_LOAD_FACTOR_MUST_BE_POSITIVE")


@dataclass(frozen=True, slots=True)
class MassLoadSeam:
    """Mass-contract output: an inertial load from a component mass and CG."""

    component_id: str
    mass_kg: float
    span_m: float
    load_factor: float
    cg_fraction: float = 0.4
    tip_to_root_ratio: float = 0.5
    gravity_m_s2: float = STANDARD_GRAVITY_M_S2
    reference: str = "mass"

    def __post_init__(self) -> None:
        if not self.component_id.strip():
            raise LoadCaseError("MASS_SEAM_COMPONENT_REQUIRED")
        if not isfinite(self.mass_kg) or self.mass_kg <= 0.0:
            raise LoadCaseError("MASS_SEAM_MASS_MUST_BE_POSITIVE")
        if not isfinite(self.span_m) or self.span_m <= 0.0:
            raise LoadCaseError("MASS_SEAM_SPAN_MUST_BE_POSITIVE")
        if not isfinite(self.load_factor) or self.load_factor <= 0.0:
            raise LoadCaseError("MASS_SEAM_LOAD_FACTOR_MUST_BE_POSITIVE")
        if not 0.0 <= self.cg_fraction <= 1.0:
            raise LoadCaseError("MASS_SEAM_CG_FRACTION_OUT_OF_RANGE")


def load_case_from_aero(seam: AeroLoadSeam, *, case_id: str) -> StructuralLoadCase:
    """Convert an external-aero seam into a structural load case."""

    distributed = _linear_distributed(
        seam.normal_force_n, seam.span_m, seam.tip_to_root_ratio
    )
    return StructuralLoadCase(
        case_id=case_id,
        source=LoadSource.EXTERNAL_AERO,
        component_id=seam.component_id,
        span_m=seam.span_m,
        load_factor=seam.load_factor,
        distributed=(distributed,),
        point=(
            PointLoad(fraction=0.5, normal_n=0.0, axial_n=seam.axial_force_n),
        ),
        reference=seam.reference,
    )


def load_case_from_trim(seam: TrimLoadSeam, *, case_id: str) -> StructuralLoadCase:
    """Convert a trim seam into a structural load case."""

    distributed = _linear_distributed(
        seam.normal_force_n, seam.span_m, seam.tip_to_root_ratio
    )
    return StructuralLoadCase(
        case_id=case_id,
        source=LoadSource.TRIM,
        component_id=seam.component_id,
        span_m=seam.span_m,
        load_factor=seam.load_factor,
        distributed=(distributed,),
        point=(
            PointLoad(fraction=0.5, normal_n=0.0, axial_n=seam.axial_force_n),
        ),
        reference=seam.reference,
    )


def load_case_from_mass(seam: MassLoadSeam, *, case_id: str) -> StructuralLoadCase:
    """Convert a mass-contract seam into an inertial structural load case."""

    inertial_force = seam.mass_kg * seam.gravity_m_s2 * seam.load_factor
    distributed = _linear_distributed(
        inertial_force, seam.span_m, seam.tip_to_root_ratio
    )
    return StructuralLoadCase(
        case_id=case_id,
        source=LoadSource.MASS,
        component_id=seam.component_id,
        span_m=seam.span_m,
        load_factor=1.0,
        distributed=(distributed,),
        reference=seam.reference,
    )


def load_case_from_landing_gear(gear_case: Any, *, component_id: str, span_m: float, station_fraction: float, load_factor: float = 1.0) -> StructuralLoadCase:  # noqa: E501
    from aeroworkbench_vehicle_systems.landing_gear import GearLoadCase
    if not isinstance(gear_case, GearLoadCase):
        raise LoadCaseError("LANDING_GEAR_CASE_REQUIRED")
    return StructuralLoadCase(
        case_id=f"landing:{gear_case.case_id}", source=LoadSource.LANDING,
        component_id=component_id, span_m=span_m, load_factor=load_factor,
        point=(PointLoad(station_fraction, gear_case.vertical_force_n, gear_case.drag_force_n, gear_case.side_force_n),),  # noqa: E501
        reference=f"{gear_case.gear_id}:{gear_case.kind.value}",
    )


def load_case_from_propulsor(loads: Any, *, component_id: str, span_m: float, station_fraction: float, case_id: str, load_factor: float = 1.0) -> StructuralLoadCase:  # noqa: E501
    return StructuralLoadCase(
        case_id=case_id, source=LoadSource.PROPULSION, component_id=component_id,
        span_m=span_m, load_factor=load_factor,
        point=(PointLoad(station_fraction, loads.normal_force_n, loads.thrust_n, 0.0),),
        applied_moments_n_m=tuple(
            value * load_factor
            for value in (loads.torque_n_m, loads.pitching_moment_n_m, loads.yawing_moment_n_m)
        ),
        reference=loads.provenance.model,
    )


def ground_load_set_for_segment(segment: Any, export: Any, *, component_id: str, span_m: float, station_fraction: float) -> StructuralLoadSet:  # noqa: E501
    from aeroworkbench_vehicle_systems.mission import SegmentKind
    if segment.kind not in {SegmentKind.TAXI, SegmentKind.TAKEOFF, SegmentKind.LANDING}:
        raise ValueError("GROUND_SEGMENT_REQUIRED")
    return StructuralLoadSet(component_id, tuple(
        load_case_from_landing_gear(case, component_id=component_id, span_m=span_m, station_fraction=station_fraction)  # noqa: E501
        for case in export.cases
    ))
