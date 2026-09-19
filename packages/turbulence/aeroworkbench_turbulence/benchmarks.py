"""Portable canonical benchmarks spanning external, internal, and rotating flows.

Four small deterministic cases exercise the same generic capability:
low-Reynolds external airfoil, flat-plate boundary layer, separated/diffuser
internal flow, and a rotating blade/propulsor section. Predictions come from the
declared analytical correlations and are compared against declared analytical
references; the result is labelled ``benchmark`` (never ``native``) and carries
units/validity/input-hash/software-identity/provenance.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite
from typing import Any

from aeroworkbench_core.types import Provenance, ResultSource
from aeroworkbench_fluid_properties import SoftwareIdentity

from .contracts import (
    SOFTWARE_IDENTITY,
    TurbulenceFidelity,
    Validity,
    analytical_provenance,
)
from .diagnostics import transition_location_fraction
from .errors import TurbulenceValidationError
from .models import select_turbulence_model
from .regimes import (
    EXTERNAL_FLOW_THRESHOLDS,
    INTERNAL_FLOW_THRESHOLDS,
    LOW_REYNOLDS_THRESHOLDS,
    FlowRegime,
    FlowState,
    ReferenceScales,
    RegimeThresholds,
    TransitionState,
    classify_regime,
)
from .wall import (
    WallTreatmentMode,
    skin_friction_coefficient_flat_plate,
    wall_requirement_for_mode,
)

REGIME_INDEX: dict[FlowRegime, float] = {
    FlowRegime.LAMINAR: 0.0,
    FlowRegime.TRANSITIONAL: 1.0,
    FlowRegime.TURBULENT: 2.0,
}


class BenchmarkKind(StrEnum):
    """The four canonical flow categories every capability must serve."""

    LOW_REYNOLDS_AIRFOIL = "low_reynolds_airfoil"
    FLAT_PLATE_BOUNDARY_LAYER = "flat_plate_boundary_layer"
    SEPARATED_INTERNAL_FLOW = "separated_internal_flow"
    ROTATING_BLADE_SECTION = "rotating_blade_section"


@dataclass(frozen=True, slots=True)
class BenchmarkCase:
    """One portable benchmark case with its declared analytical reference."""

    case_id: str
    kind: BenchmarkKind
    description: str
    flow: FlowState
    reference_source: str
    expected: tuple[tuple[str, float], ...]
    tolerance: float = 1.0e-3
    critical_reynolds: float | None = None
    wall_mode: WallTreatmentMode = WallTreatmentMode.WALL_RESOLVED
    layer_count: int = 20
    growth_ratio: float = 1.2

    def __post_init__(self) -> None:
        if not self.case_id.strip() or not self.description.strip():
            raise TurbulenceValidationError("BENCHMARK_IDENTITY_REQUIRED")
        if not self.reference_source.strip():
            raise TurbulenceValidationError("BENCHMARK_REFERENCE_SOURCE_REQUIRED")
        if not self.expected:
            raise TurbulenceValidationError("BENCHMARK_REFERENCE_REQUIRED")
        if not isfinite(self.tolerance) or self.tolerance <= 0.0:
            raise TurbulenceValidationError("BENCHMARK_TOLERANCE_INVALID")

    def canonical(self) -> dict[str, Any]:
        return {
            "caseId": self.case_id,
            "kind": self.kind.value,
            "description": self.description,
            "flow": self.flow.canonical(),
            "referenceSource": self.reference_source,
            "expected": [[name, value] for name, value in self.expected],
            "tolerance": self.tolerance,
            "criticalReynolds": self.critical_reynolds,
            "wallMode": self.wall_mode.value,
            "layerCount": self.layer_count,
            "growthRatio": self.growth_ratio,
        }


def _flow(
    label: str,
    *,
    reynolds: float,
    mach: float,
    intensity: float,
    length_m: float,
    velocity_m_s: float,
    source: str,
    thresholds: RegimeThresholds,
    transition_state: TransitionState | None = None,
    separation_fraction: float = 0.0,
) -> FlowState:
    return FlowState(
        label=label,
        reynolds_number=reynolds,
        mach_number=mach,
        turbulence_intensity=intensity,
        reference=ReferenceScales(
            label="reference",
            length_m=length_m,
            velocity_m_s=velocity_m_s,
            source=source,
        ),
        transition_state=transition_state or TransitionState.UNKNOWN,
        separation_fraction=separation_fraction,
        thresholds=thresholds,
        source=source,
    )


def portable_benchmarks() -> tuple[BenchmarkCase, ...]:
    """Return the four portable benchmark cases (deterministic, tiny)."""
    return (
        BenchmarkCase(
            case_id="flat-plate-boundary-layer",
            kind=BenchmarkKind.FLAT_PLATE_BOUNDARY_LAYER,
            description="Turbulent flat-plate boundary layer at Re_L = 1e6.",
            flow=_flow(
                "flat-plate",
                reynolds=1.0e6,
                mach=0.1,
                intensity=0.01,
                length_m=1.0,
                velocity_m_s=30.0,
                source="canonical flat-plate boundary layer",
                thresholds=EXTERNAL_FLOW_THRESHOLDS,
            ),
            reference_source="Schlichting turbulent flat plate Cf = 0.0576/Re_x^0.2",
            expected=(("skinFrictionCoefficient", 0.003634), ("regimeIndex", 2.0)),
        ),
        BenchmarkCase(
            case_id="low-reynolds-airfoil",
            kind=BenchmarkKind.LOW_REYNOLDS_AIRFOIL,
            description="Low-Reynolds external airfoil transition at Re_c = 5e4.",
            flow=_flow(
                "low-re-airfoil",
                reynolds=1.0e5,
                mach=0.05,
                intensity=0.005,
                length_m=0.15,
                velocity_m_s=10.0,
                source="canonical low-Reynolds airfoil",
                thresholds=LOW_REYNOLDS_THRESHOLDS,
            ),
            reference_source="critical-Reynolds transition Re_c = 5e4 (declared)",
            expected=(("transitionFraction", 0.5), ("regimeIndex", 1.0)),
            critical_reynolds=5.0e4,
        ),
        BenchmarkCase(
            case_id="separated-diffuser",
            kind=BenchmarkKind.SEPARATED_INTERNAL_FLOW,
            description="Separated internal diffuser passage with a recirculation zone.",
            flow=_flow(
                "separated-diffuser",
                reynolds=5.0e4,
                mach=0.2,
                intensity=0.05,
                length_m=0.5,
                velocity_m_s=20.0,
                source="canonical separated diffuser",
                thresholds=INTERNAL_FLOW_THRESHOLDS,
                separation_fraction=0.35,
            ),
            reference_source="declared separated diffuser screening reference",
            expected=(("separationFraction", 0.35), ("regimeIndex", 2.0)),
        ),
        BenchmarkCase(
            case_id="rotating-blade-section",
            kind=BenchmarkKind.ROTATING_BLADE_SECTION,
            description="Rotating blade/propulsor section with a wall-resolved target.",
            flow=_flow(
                "rotating-blade-section",
                reynolds=3.0e5,
                mach=0.3,
                intensity=0.03,
                length_m=0.2,
                velocity_m_s=60.0,
                source="canonical rotating blade section",
                thresholds=EXTERNAL_FLOW_THRESHOLDS,
                transition_state=TransitionState.NATURAL,
            ),
            reference_source="wall-resolved y+ target band 0.1..5 (declared)",
            expected=(("targetYPlus", 1.0), ("regimeIndex", 1.0)),
            wall_mode=WallTreatmentMode.WALL_RESOLVED,
        ),
    )


def _predict(case: BenchmarkCase) -> dict[str, float]:
    flow = case.flow
    classification = classify_regime(flow)
    base = {"regimeIndex": REGIME_INDEX[classification.regime]}
    if case.kind is BenchmarkKind.FLAT_PLATE_BOUNDARY_LAYER:
        coefficient, _ = skin_friction_coefficient_flat_plate(
            flow.reynolds_number, regime=classification.regime
        )
        base["skinFrictionCoefficient"] = coefficient
        return base
    if case.kind is BenchmarkKind.LOW_REYNOLDS_AIRFOIL:
        if case.critical_reynolds is None:
            raise TurbulenceValidationError("LOW_RE_AIRFOIL_REQUIRES_CRITICAL_REYNOLDS")
        fraction, _ = transition_location_fraction(
            flow,
            critical_reynolds=case.critical_reynolds,
            source=case.reference_source,
        )
        base["transitionFraction"] = fraction
        return base
    if case.kind is BenchmarkKind.SEPARATED_INTERNAL_FLOW:
        base["separationFraction"] = flow.separation_fraction
        return base
    requirement = wall_requirement_for_mode(
        surface=case.case_id,
        mode=case.wall_mode,
        flow=flow,
        layer_count=case.layer_count,
        growth_ratio=case.growth_ratio,
    )
    base["targetYPlus"] = requirement.target_y_plus
    base["firstCellHeightM"] = requirement.first_cell_height_target_m
    return base


@dataclass(frozen=True, slots=True)
class BenchmarkResult:
    """One benchmark outcome with declared reference comparison and provenance."""

    case_id: str
    kind: BenchmarkKind
    source: ResultSource
    fidelity: TurbulenceFidelity
    predictions: tuple[tuple[str, float], ...]
    references: tuple[tuple[str, float], ...]
    deviations: tuple[tuple[str, float], ...]
    passed: bool
    tolerance: float
    validity: Validity
    provenance: Provenance
    software: SoftwareIdentity = SOFTWARE_IDENTITY

    def canonical(self) -> dict[str, Any]:
        return {
            "caseId": self.case_id,
            "kind": self.kind.value,
            "source": self.source.value,
            "fidelity": self.fidelity.value,
            "predictions": [[name, value] for name, value in self.predictions],
            "references": [[name, value] for name, value in self.references],
            "deviations": [[name, value] for name, value in self.deviations],
            "passed": self.passed,
            "tolerance": self.tolerance,
            "validity": self.validity.canonical(),
            "units": {
                "skinFrictionCoefficient": "1",
                "regimeIndex": "1",
                "transitionFraction": "1",
                "separationFraction": "1",
                "targetYPlus": "1",
                "firstCellHeightM": "m",
            },
            "inputsHash": self.provenance.inputs_hash,
            "software": self.software.canonical(),
        }


def run_benchmark(case: BenchmarkCase) -> BenchmarkResult:
    """Evaluate one benchmark against its declared analytical reference."""
    classification = classify_regime(case.flow)
    selection = select_turbulence_model(case.flow, classification)
    predicted = _predict(case)
    deviations: list[tuple[str, float]] = []
    passed = True
    for name, reference in case.expected:
        value = predicted.get(name)
        if value is None:
            deviations.append((name, float("inf")))
            passed = False
            continue
        deviation = abs(value - reference) / max(abs(reference), 1e-12)
        deviations.append((name, deviation))
        if deviation > case.tolerance:
            passed = False
    provenance = analytical_provenance(
        "turbulence.benchmark",
        {
            "case": case.canonical(),
            "predictions": dict(sorted(predicted.items())),
            "deviations": dict(sorted(deviations)),
        },
        f"reference source: {case.reference_source}",
        "benchmark compares a declared analytical prediction to a declared reference",
    )
    validity = Validity(
        passed=passed,
        checks={name: deviation <= case.tolerance for name, deviation in deviations},
        detail=(
            f"{case.case_id}: {'within' if passed else 'outside'} tolerance "
            f"{case.tolerance:.3g}"
        ),
    )
    return BenchmarkResult(
        case_id=case.case_id,
        kind=case.kind,
        source=ResultSource.BENCHMARK,
        fidelity=selection.fidelity,
        predictions=tuple(sorted(predicted.items())),
        references=tuple(case.expected),
        deviations=tuple(deviations),
        passed=passed,
        tolerance=case.tolerance,
        validity=validity,
        provenance=provenance,
    )


__all__ = [
    "REGIME_INDEX",
    "BenchmarkCase",
    "BenchmarkKind",
    "BenchmarkResult",
    "portable_benchmarks",
    "run_benchmark",
]
