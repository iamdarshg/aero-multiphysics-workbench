"""Fracture mechanics: stress intensity, criticality, and Paris crack growth.

Stress-intensity factors and critical crack lengths are computed from a sourced
fracture-toughness value; fatigue crack growth integrates a Paris curve between
an initial flaw and the critical length. Missing toughness or out-of-validity
stress-intensity ranges fail closed rather than fabricating a life.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import pi, sqrt
from typing import Any

from aeroworkbench_core.types import Provenance

from .curves import CrackGrowthCurve
from .provenance import analytical_provenance
from .validity import DataUnavailable, Validity, finite

__all__ = [
    "CrackGrowthResult",
    "CrackType",
    "StressIntensityResult",
    "critical_crack_length_m",
    "evaluate_crack_criticality",
    "paris_life",
    "stress_intensity_factor_pa_m05",
]


class CrackType(StrEnum):
    """Generic crack geometry family with a standard geometry factor."""

    THROUGH = "through"
    SURFACE = "surface"
    EDGE = "edge"


_GEOMETRY_FACTORS: dict[CrackType, float] = {
    CrackType.THROUGH: 1.0,
    CrackType.SURFACE: 1.12,
    CrackType.EDGE: 1.12,
}


def geometry_factor_for(crack_type: CrackType) -> float:
    return _GEOMETRY_FACTORS[crack_type]


def stress_intensity_factor_pa_m05(
    stress_pa: float,
    crack_length_m: float,
    *,
    crack_type: CrackType = CrackType.THROUGH,
    geometry_factor: float | None = None,
) -> float:
    """Mode-I stress intensity ``K = F * sigma * sqrt(pi a)`` in Pa*m^0.5."""

    stress = finite(stress_pa, "stress_pa", positive=True)
    crack = finite(crack_length_m, "crack_length_m", positive=True)
    factor = (
        finite(geometry_factor, "geometry_factor", positive=True)
        if geometry_factor is not None
        else geometry_factor_for(crack_type)
    )
    return float(factor * stress * sqrt(pi * crack))


def critical_crack_length_m(
    fracture_toughness_pa_m05: float,
    stress_pa: float,
    *,
    crack_type: CrackType = CrackType.THROUGH,
    geometry_factor: float | None = None,
) -> float:
    """Critical crack length from fracture toughness and applied stress."""

    toughness = finite(fracture_toughness_pa_m05, "fracture_toughness_pa_m05", positive=True)
    stress = finite(stress_pa, "stress_pa", positive=True)
    factor = (
        finite(geometry_factor, "geometry_factor", positive=True)
        if geometry_factor is not None
        else geometry_factor_for(crack_type)
    )
    return float((toughness / (factor * stress)) ** 2 / pi)


@dataclass(frozen=True, slots=True)
class StressIntensityResult:
    """Provenance-backed crack criticality check."""

    crack_type: CrackType
    geometry_factor: float
    stress_pa: float
    crack_length_m: float
    stress_intensity_pa_m05: float
    fracture_toughness_pa_m05: float | None
    critical_crack_length_m: float | None
    validity: Validity
    provenance: Provenance

    @property
    def passed(self) -> bool:
        return self.validity.passed

    def reserve_factor(self) -> float | None:
        if self.fracture_toughness_pa_m05 is None:
            return None
        return self.fracture_toughness_pa_m05 / self.stress_intensity_pa_m05

    def units(self) -> dict[str, str]:
        return {
            "stress_pa": "Pa",
            "crack_length_m": "m",
            "stress_intensity_pa_m05": "Pa*m^0.5",
            "fracture_toughness_pa_m05": "Pa*m^0.5",
            "critical_crack_length_m": "m",
        }

    def as_dict(self) -> dict[str, Any]:
        return {
            "crackType": self.crack_type.value,
            "geometryFactor": self.geometry_factor,
            "stressPa": self.stress_pa,
            "crackLengthM": self.crack_length_m,
            "stressIntensityPaM05": self.stress_intensity_pa_m05,
            "fractureToughnessPaM05": self.fracture_toughness_pa_m05,
            "criticalCrackLengthM": self.critical_crack_length_m,
            "validity": self.validity.as_dict(),
            "inputsHash": self.provenance.inputs_hash,
            "source": self.provenance.source.value,
        }


def evaluate_crack_criticality(
    curve: CrackGrowthCurve,
    *,
    stress_pa: float,
    crack_length_m: float,
    crack_type: CrackType = CrackType.THROUGH,
    geometry_factor: float | None = None,
) -> StressIntensityResult:
    """Check a crack against the declared fracture toughness; fails closed if absent."""

    if curve.fracture_toughness_pa_m05 is None:
        raise DataUnavailable(f"{curve.identity}_FRACTURE_TOUGHNESS_UNDECLARED")
    factor = (
        finite(geometry_factor, "geometry_factor", positive=True)
        if geometry_factor is not None
        else geometry_factor_for(crack_type)
    )
    intensity = stress_intensity_factor_pa_m05(
        stress_pa, crack_length_m, crack_type=crack_type, geometry_factor=factor
    )
    critical = critical_crack_length_m(
        curve.fracture_toughness_pa_m05,
        stress_pa,
        crack_type=crack_type,
        geometry_factor=factor,
    )
    passed = intensity < curve.fracture_toughness_pa_m05 and crack_length_m < critical
    provenance = analytical_provenance(
        "crack-criticality",
        {
            "curve": curve.identity,
            "curveSource": curve.source,
            "stressPa": stress_pa,
            "crackLengthM": crack_length_m,
            "crackType": crack_type.value,
            "geometryFactor": factor,
        },
        assumptions=(
            "LEFM Mode-I stress intensity with a constant geometry factor",
            "plane-strain fracture toughness assumed independent of temperature",
        ),
    )
    return StressIntensityResult(
        crack_type=crack_type,
        geometry_factor=factor,
        stress_pa=stress_pa,
        crack_length_m=crack_length_m,
        stress_intensity_pa_m05=intensity,
        fracture_toughness_pa_m05=curve.fracture_toughness_pa_m05,
        critical_crack_length_m=critical,
        validity=Validity(
            passed=passed,
            checks={
                "intensity_below_toughness": intensity < curve.fracture_toughness_pa_m05,
                "crack_below_critical": crack_length_m < critical,
            },
            detail=f"criticality:{curve.identity}",
        ),
        provenance=provenance,
    )


@dataclass(frozen=True, slots=True)
class CrackGrowthResult:
    """Provenance-backed Paris crack-growth life to a critical length."""

    initial_crack_m: float
    critical_crack_m: float
    stress_range_pa: float
    geometry_factor: float
    initial_growth_rate_m_per_cycle: float
    cycles_to_critical: float
    allowable_cycles: float
    safety_factor: float
    validity: Validity
    provenance: Provenance

    def passed(self) -> bool:
        return self.validity.passed

    def units(self) -> dict[str, str]:
        return {
            "initial_crack_m": "m",
            "critical_crack_m": "m",
            "stress_range_pa": "Pa",
            "initial_growth_rate_m_per_cycle": "m/cycle",
            "cycles_to_critical": "cycle",
            "allowable_cycles": "cycle",
        }

    def as_dict(self) -> dict[str, Any]:
        return {
            "initialCrackM": self.initial_crack_m,
            "criticalCrackM": self.critical_crack_m,
            "stressRangePa": self.stress_range_pa,
            "geometryFactor": self.geometry_factor,
            "initialGrowthRateMPerCycle": self.initial_growth_rate_m_per_cycle,
            "cyclesToCritical": self.cycles_to_critical,
            "allowableCycles": self.allowable_cycles,
            "safetyFactor": self.safety_factor,
            "validity": self.validity.as_dict(),
            "inputsHash": self.provenance.inputs_hash,
            "source": self.provenance.source.value,
        }


def paris_life(
    curve: CrackGrowthCurve,
    *,
    initial_crack_m: float,
    stress_range_pa: float,
    maximum_stress_pa: float | None = None,
    crack_type: CrackType = CrackType.THROUGH,
    geometry_factor: float | None = None,
    safety_factor: float = 1.0,
) -> CrackGrowthResult:
    """Cycles for a crack to grow from an initial flaw to fracture toughness."""

    if curve.fracture_toughness_pa_m05 is None:
        raise DataUnavailable(f"{curve.identity}_FRACTURE_TOUGHNESS_UNDECLARED")
    start = finite(initial_crack_m, "initial_crack_m", positive=True)
    stress_range = finite(stress_range_pa, "stress_range_pa", positive=True)
    factor = finite(safety_factor, "safety_factor", positive=True)
    geometry = (
        finite(geometry_factor, "geometry_factor", positive=True)
        if geometry_factor is not None
        else geometry_factor_for(crack_type)
    )
    maximum = (
        finite(maximum_stress_pa, "maximum_stress_pa", positive=True)
        if maximum_stress_pa is not None
        else stress_range
    )
    critical = critical_crack_length_m(
        curve.fracture_toughness_pa_m05,
        maximum,
        crack_type=crack_type,
        geometry_factor=geometry,
    )
    if start >= critical:
        raise DataUnavailable(f"{curve.identity}_INITIAL_CRACK_ALREADY_CRITICAL")
    initial_delta_k = geometry * stress_range * sqrt(pi * start)
    growth_rate = curve.growth_rate_m_per_cycle(initial_delta_k)
    cycles = curve.cycles_to_grow(
        start, critical, stress_range, geometry_factor=geometry
    )
    allowable = cycles / factor
    provenance = analytical_provenance(
        "paris-crack-growth",
        {
            "curve": curve.identity,
            "curveSource": curve.source,
            "initialCrackM": start,
            "criticalCrackM": critical,
            "stressRangePa": stress_range,
            "maximumStressPa": maximum,
            "crackType": crack_type.value,
            "geometryFactor": geometry,
            "safetyFactor": factor,
        },
        assumptions=(
            "Paris law integration with a constant geometry factor",
            "no retardation/overload interaction or threshold excursion modelled",
        ),
    )
    return CrackGrowthResult(
        initial_crack_m=start,
        critical_crack_m=critical,
        stress_range_pa=stress_range,
        geometry_factor=geometry,
        initial_growth_rate_m_per_cycle=growth_rate,
        cycles_to_critical=cycles,
        allowable_cycles=allowable,
        safety_factor=factor,
        validity=Validity(
            passed=True,
            checks={
                "initial_intensity_above_threshold": initial_delta_k
                >= curve.threshold_delta_k_pa_m05,
                "initial_crack_below_critical": start < critical,
            },
            detail=f"paris:{curve.identity}",
        ),
        provenance=provenance,
    )
