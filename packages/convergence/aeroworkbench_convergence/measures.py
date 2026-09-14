"""Named physical convergence measures and global acceptance.

Every closure quantity carries its own absolute tolerance, relative
tolerance, and normalization scale, so 1 watt and 1 metre are never compared
with the same raw tolerance. Global acceptance requires all four gates:
individual participant convergence, interface convergence, physical closure,
and quality gates. An energy-closure failure blocks acceptance even when
every residual is small.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from math import isfinite

# Legacy declared names from milestone-2 participant manifests mapped to the
# canonical quantity set. Screening aliases only; the canonical assessment
# always uses explicit ClosureMeasure specs below.
LEGACY_MEASURE_ALIASES: dict[str, str] = {
    "residual": "force",
    "continuity": "mass",
    "energy": "energy",
    "torque": "torque",
    "solver_residual": "energy",
    "eigen_residual": "modes",
    "quality": "displacement",
    "topology": "displacement",
    "interface_residual": "force",
    "conservation": "energy",
}


@dataclass(frozen=True, slots=True)
class ClosureMeasure:
    """One normalized closure quantity with its own tolerances and scale."""

    name: str
    absolute_tolerance: float
    reference_scale: float
    relative_tolerance: float = 1e-6

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("MEASURE_NAME_REQUIRED")
        for label, value in (
            ("absolute_tolerance", self.absolute_tolerance),
            ("reference_scale", self.reference_scale),
            ("relative_tolerance", self.relative_tolerance),
        ):
            if not isfinite(value) or value <= 0:
                raise ValueError(f"INVALID_MEASURE_SPEC:{self.name}:{label}")


def _default_measures() -> dict[str, ClosureMeasure]:
    specs = {
        "mass": (1e-6, 1.0),
        "energy": (1e-3, 100.0),
        "force": (1e-3, 10.0),
        "torque": (1e-4, 1.0),
        "momentum": (1e-6, 1.0),
        "displacement": (1e-6, 0.01),
        "clearance": (1e-6, 0.001),
        "temperature": (1e-2, 300.0),
        "heat-flow": (1e-3, 100.0),
        "resistance": (1e-6, 1.0),
        "voltage": (1e-4, 10.0),
        "current": (1e-4, 10.0),
        "shaft-power": (0.5, 1000.0),
        "modes": (1e-2, 50.0),
        "critical-speeds": (1.0, 3000.0),
        "forcing-spectra": (1e-2, 50.0),
        "resonance-separation": (0.5, 10.0),
    }
    return {
        name: ClosureMeasure(name, absolute, scale)
        for name, (absolute, scale) in specs.items()
    }


DEFAULT_MEASURES: dict[str, ClosureMeasure] = _default_measures()


@dataclass(frozen=True, slots=True)
class MeasureAssessment:
    name: str
    simulated: float
    reference: float
    residual: float
    passed: bool
    detail: str


def assess_measure(
    spec: ClosureMeasure, simulated: float, reference: float
) -> MeasureAssessment:
    """Assess one closure quantity against its own normalized tolerances."""
    for label, value in (("simulated", simulated), ("reference", reference)):
        if not isfinite(value):
            raise ValueError(f"NONFINITE_MEASURE_VALUE:{spec.name}:{label}")
    deviation = abs(simulated - reference)
    allowed = spec.absolute_tolerance + spec.relative_tolerance * max(
        abs(reference), spec.reference_scale
    )
    residual = deviation / spec.reference_scale
    passed = deviation <= allowed
    return MeasureAssessment(
        spec.name, simulated, reference, residual, passed,
        f"|sim-ref|={deviation:.3g} allowed={allowed:.3g} (scale={spec.reference_scale:.3g})",
    )


def declared_measures(names: tuple[str, ...]) -> tuple[str, ...]:
    """Validate participant-declared convergence quantities to canonical names."""
    resolved: list[str] = []
    for name in names:
        canonical = LEGACY_MEASURE_ALIASES.get(name, name)
        if canonical not in DEFAULT_MEASURES:
            raise ValueError(f"UNKNOWN_CONVERGENCE_MEASURE:{name}")
        resolved.append(canonical)
    return tuple(resolved)


@dataclass(frozen=True, slots=True)
class GlobalConvergenceReport:
    participants_converged: bool
    interfaces_converged: bool
    closure_passed: bool
    quality_passed: bool
    accepted: bool
    detail: str


def assess_global(
    *,
    participants: Mapping[str, bool],
    interfaces: Mapping[str, tuple[float, float]],
    closures: Mapping[str, MeasureAssessment],
    quality: Mapping[str, bool],
) -> GlobalConvergenceReport:
    """Accept only when participants, interfaces, closure, and quality pass."""

    if not participants:
        raise ValueError("GLOBAL_ASSESSMENT_NEEDS_PARTICIPANTS")
    participants_ok = all(participants.values())
    interfaces_ok = bool(interfaces) and all(
        isfinite(residual) and residual >= 0 and residual <= tolerance
        for residual, tolerance in interfaces.values()
    )
    closure_ok = bool(closures) and all(
        assessment.passed for assessment in closures.values()
    )
    quality_ok = bool(quality) and all(quality.values())
    accepted = participants_ok and interfaces_ok and closure_ok and quality_ok
    failures = [
        gate
        for gate, passed in (
            ("participants", participants_ok),
            ("interfaces", interfaces_ok),
            ("closure", closure_ok),
            ("quality", quality_ok),
        )
        if not passed
    ]
    return GlobalConvergenceReport(
        participants_ok, interfaces_ok, closure_ok, quality_ok, accepted,
        "all gates passed" if accepted else f"blocked by: {', '.join(failures)}",
    )
