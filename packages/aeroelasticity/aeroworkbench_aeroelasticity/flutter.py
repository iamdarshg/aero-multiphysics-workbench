"""Flutter/stability: a fidelity ladder from reduced screening to native FSI.

A generic linear aeroelastic system couples a structural mass/stiffness/damping
triplet with dynamic-pressure-scaled aerodynamic stiffness and speed-scaled
aerodynamic damping. The reduced screening level evaluates the 2Nx2N state
matrix eigenvalues at caller-supplied speeds, reporting frequency/damping
versus speed and the critical speed where the growth rate first crosses zero.

Near-instability states escalate: the p-k/equivalent linear flutter level
(:class:`AeroelasticFidelity.HARMONIC`) and the transient CFD/FSI level
(:class:`AeroelasticFidelity.TRANSIENT_FSI`) are capability-gated seams that
fail closed when the engine is absent. Nothing here fabricates native output.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import pi
from typing import Any

from aeroworkbench_core.types import Provenance

from .capabilities import NativeRequirement, require_native
from .errors import AeroelasticError
from .linalg import FloatMatrix, complex_eigenvalues, solve
from .provenance import DEFAULT_SOFTWARE, SoftwareIdentity, analytical_provenance
from .validity import AeroelasticFidelity, Validity, finite, finite_tuple

_DIVERGENCE_TOL = 1e-9


@dataclass(frozen=True, slots=True)
class AeroelasticSystem:
    """A generic linear aeroelastic system scaled by density and speed.

    Structural equations move the aerodynamic force to the left-hand side::

        M q + (C + 0.5 rho U A_damp) q' + (K + 0.5 rho U^2 A_stiff) q = 0

    so ``A_stiff`` and ``A_damp`` are aerodynamic influence matrices and the
    apparent-mass (fluid inertia) term is deliberately absent from this
    screening level.
    """

    system_id: str
    mass_matrix: FloatMatrix
    stiffness_matrix: FloatMatrix
    damping_matrix: FloatMatrix
    aero_stiffness_matrix: FloatMatrix
    aero_damping_matrix: FloatMatrix
    density_kg_m3: float

    def __post_init__(self) -> None:
        if not self.system_id.strip():
            raise AeroelasticError("system_id is required")
        size = len(self.mass_matrix)
        if size == 0:
            raise AeroelasticError("mass matrix must be non-empty")
        for label, matrix in (
            ("mass_matrix", self.mass_matrix),
            ("stiffness_matrix", self.stiffness_matrix),
            ("damping_matrix", self.damping_matrix),
            ("aero_stiffness_matrix", self.aero_stiffness_matrix),
            ("aero_damping_matrix", self.aero_damping_matrix),
        ):
            self._check_square(label, matrix, size)
        finite(self.density_kg_m3, "density_kg_m3", positive=True)

    @staticmethod
    def _check_square(label: str, matrix: FloatMatrix, size: int) -> None:
        if len(matrix) != size or any(len(row) != size for row in matrix):
            raise AeroelasticError(f"{label} must be {size}x{size}")
        for row in matrix:
            for value in row:
                finite(value, f"{label} entry")

    @property
    def dof(self) -> int:
        return len(self.mass_matrix)

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "system_id": self.system_id,
            "mass_matrix": [list(row) for row in self.mass_matrix],
            "stiffness_matrix": [list(row) for row in self.stiffness_matrix],
            "damping_matrix": [list(row) for row in self.damping_matrix],
            "aero_stiffness_matrix": [list(row) for row in self.aero_stiffness_matrix],
            "aero_damping_matrix": [list(row) for row in self.aero_damping_matrix],
            "density_kg_m3": self.density_kg_m3,
        }


@dataclass(frozen=True, slots=True)
class TypicalSection:
    """A 2-DOF plunge/pitch typical section with quasi-steady lift.

    ``semi_chord_m`` is ``b``; ``elastic_axis_fraction`` is ``a`` (elastic axis
    at ``a b`` behind mid-chord); ``0.5 + a`` sets the lift moment arm. The
    factory emits a general :class:`AeroelasticSystem` so the same stability
    evaluator serves any reduced model.
    """

    section_id: str
    semi_chord_m: float
    elastic_axis_fraction: float
    mass_matrix: FloatMatrix
    stiffness_matrix: FloatMatrix
    damping_matrix: FloatMatrix
    lift_curve_slope_per_rad: float
    density_kg_m3: float

    def __post_init__(self) -> None:
        if not self.section_id.strip():
            raise AeroelasticError("section_id is required")
        finite(self.semi_chord_m, "semi_chord_m", positive=True)
        finite(
            self.elastic_axis_fraction,
            "elastic_axis_fraction",
            minimum=-1.0,
            maximum=1.0,
        )
        finite(self.lift_curve_slope_per_rad, "lift_curve_slope_per_rad", positive=True)
        finite(self.density_kg_m3, "density_kg_m3", positive=True)
        for label, matrix in (
            ("mass_matrix", self.mass_matrix),
            ("stiffness_matrix", self.stiffness_matrix),
            ("damping_matrix", self.damping_matrix),
        ):
            if len(matrix) != 2 or any(len(row) != 2 for row in matrix):
                raise AeroelasticError(f"{label} must be 2x2")
            for row in matrix:
                for value in row:
                    finite(value, f"{label} entry")

    def to_system(self) -> AeroelasticSystem:
        b = self.semi_chord_m
        a = self.elastic_axis_fraction
        a0 = self.lift_curve_slope_per_rad
        sl = b * a0
        sm = b * b * a0 * (0.5 + a)
        aero_stiff = ((0.0, sl), (0.0, -sm))
        aero_damp = (
            (sl, sl * b * (0.5 - a)),
            (-sm, -sm * b * (0.5 - a)),
        )
        return AeroelasticSystem(
            system_id=self.section_id,
            mass_matrix=self.mass_matrix,
            stiffness_matrix=self.stiffness_matrix,
            damping_matrix=self.damping_matrix,
            aero_stiffness_matrix=aero_stiff,
            aero_damping_matrix=aero_damp,
            density_kg_m3=self.density_kg_m3,
        )


@dataclass(frozen=True, slots=True)
class AeroelasticMode:
    """One eigenvalue branch of the coupled aeroelastic system."""

    frequency_hz: float
    damping_ratio: float
    growth_rate_1_s: float
    kind: str

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "frequency_hz": self.frequency_hz,
            "damping_ratio": self.damping_ratio,
            "growth_rate_1_s": self.growth_rate_1_s,
            "kind": self.kind,
        }


@dataclass(frozen=True, slots=True)
class StabilityPoint:
    """Aeroelastic eigenvalues and stability verdict at one speed."""

    speed_m_s: float
    dynamic_pressure_pa: float
    modes: tuple[AeroelasticMode, ...]
    max_growth_rate_1_s: float
    stable: bool
    flutter: bool
    provenance: Provenance

    def damping_ratios(self) -> tuple[float, ...]:
        return tuple(mode.damping_ratio for mode in self.modes)

    def frequencies_hz(self) -> tuple[float, ...]:
        return tuple(mode.frequency_hz for mode in self.modes)

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "speed_m_s": self.speed_m_s,
            "dynamic_pressure_pa": self.dynamic_pressure_pa,
            "max_growth_rate_1_s": self.max_growth_rate_1_s,
            "stable": self.stable,
            "flutter": self.flutter,
            "modes": [mode.canonical_payload() for mode in self.modes],
        }


@dataclass(frozen=True, slots=True)
class FlutterBoundary:
    """The critical speed/frequency where the growth rate crosses zero."""

    critical_speed_m_s: float | None
    critical_frequency_hz: float | None
    method: str
    crossing_index: int | None
    provenance: Provenance

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "critical_speed_m_s": self.critical_speed_m_s,
            "critical_frequency_hz": self.critical_frequency_hz,
            "method": self.method,
            "crossing_index": self.crossing_index,
        }


@dataclass(frozen=True, slots=True)
class StabilityCurve:
    """Frequency/damping versus speed for a caller-supplied speed set."""

    system_id: str
    points: tuple[StabilityPoint, ...]
    min_growth_rate_1_s: float
    boundary: FlutterBoundary
    fidelity: AeroelasticFidelity
    validity: Validity
    provenance: Provenance
    software: SoftwareIdentity = DEFAULT_SOFTWARE

    def units(self) -> dict[str, str]:
        return {
            "speed_m_s": "m/s",
            "dynamic_pressure_pa": "Pa",
            "frequency_hz": "Hz",
            "damping_ratio": "dimensionless",
            "growth_rate_1_s": "1/s",
        }

    @property
    def unstable(self) -> bool:
        return any(point.flutter for point in self.points)

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "system_id": self.system_id,
            "min_growth_rate_1_s": self.min_growth_rate_1_s,
            "unstable": self.unstable,
            "boundary": self.boundary.canonical_payload(),
            "points": [point.canonical_payload() for point in self.points],
            "source": self.provenance.source.value,
            "fidelity": self.fidelity.value,
            "inputs_hash": self.provenance.inputs_hash,
            "software": self.software.canonical(),
        }


def _state_matrix(mass: FloatMatrix, damping: FloatMatrix, stiffness: FloatMatrix) -> FloatMatrix:
    size = len(mass)
    m_inv_k = solve(mass, stiffness)
    m_inv_c = solve(mass, damping)
    rows: list[list[float]] = []
    for i in range(size):
        rows.append([0.0] * size + [1.0 if j == i else 0.0 for j in range(size)])
    for i in range(size):
        rows.append(
            [-m_inv_k[i][j] for j in range(size)]
            + [-m_inv_c[i][j] for j in range(size)]
        )
    return tuple(tuple(row) for row in rows)


def _mode_from_eigenvalue(value: complex) -> AeroelasticMode:
    real = value.real
    imag = value.imag
    if abs(imag) <= _DIVERGENCE_TOL * max(1.0, abs(real)):
        return AeroelasticMode(
            frequency_hz=0.0,
            damping_ratio=-1.0 if real > 0.0 else 1.0,
            growth_rate_1_s=real,
            kind="divergence",
        )
    magnitude = abs(value)
    damping = -real / magnitude if magnitude > 0.0 else 0.0
    return AeroelasticMode(
        frequency_hz=abs(imag) / (2.0 * pi),
        damping_ratio=damping,
        growth_rate_1_s=real,
        kind="vibration",
    )


def evaluate_stability(system: AeroelasticSystem, *, speed_m_s: float) -> StabilityPoint:
    """Evaluate the coupled aeroelastic eigenvalues at one speed (screening)."""

    speed = finite(speed_m_s, "speed_m_s", minimum=0.0)
    q_dyn = 0.5 * system.density_kg_m3 * speed * speed
    rho_u = 0.5 * system.density_kg_m3 * speed
    size = system.dof
    damping = tuple(
        tuple(
            system.damping_matrix[i][j] + rho_u * system.aero_damping_matrix[i][j]
            for j in range(size)
        )
        for i in range(size)
    )
    stiffness = tuple(
        tuple(
            system.stiffness_matrix[i][j] + q_dyn * system.aero_stiffness_matrix[i][j]
            for j in range(size)
        )
        for i in range(size)
    )
    values = complex_eigenvalues(_state_matrix(system.mass_matrix, damping, stiffness))
    modes = tuple(_mode_from_eigenvalue(value) for value in values)
    max_growth = max(mode.growth_rate_1_s for mode in modes)
    provenance = analytical_provenance(
        "aeroelasticity.flutter.quasi-steady-state-matrix",
        {"system": system.canonical_payload(), "speed_m_s": speed},
        assumptions=(
            "quasi-steady aerodynamics; apparent mass neglected; linear eigenvalues",
        ),
    )
    return StabilityPoint(
        speed_m_s=speed,
        dynamic_pressure_pa=q_dyn,
        modes=modes,
        max_growth_rate_1_s=max_growth,
        stable=max_growth < 0.0,
        flutter=max_growth >= 0.0,
        provenance=provenance,
    )


def build_stability_curve(
    system: AeroelasticSystem,
    *,
    speeds_m_s: tuple[float, ...],
) -> StabilityCurve:
    """Evaluate a deterministic stability curve at caller-supplied speeds.

    This does not sweep: the caller owns the speed set, mirroring the shared
    Campbell-diagram contract.
    """

    speeds = finite_tuple(speeds_m_s, "speeds_m_s")
    if any(speed < 0.0 for speed in speeds):
        raise AeroelasticError("speeds_m_s must be non-negative")
    points = tuple(evaluate_stability(system, speed_m_s=speed) for speed in speeds)
    boundary = _critical_speed(points)
    min_growth = min(point.max_growth_rate_1_s for point in points)
    weights = sum(speed for speed in speeds)
    checks = {
        "speeds_monotonic": all(
            first <= second for first, second in zip(speeds, speeds[1:], strict=False)
        ),
        "all_modes_finite": all(
            mode.frequency_hz == mode.frequency_hz for point in points for mode in point.modes
        ),
    }
    provenance = analytical_provenance(
        "aeroelasticity.flutter.reduced-screening-curve",
        {"system": system.canonical_payload(), "speeds_m_s": list(speeds), "speed_weight": weights},
        assumptions=("reduced linear aeroelastic screening",),
    )
    return StabilityCurve(
        system_id=system.system_id,
        points=points,
        min_growth_rate_1_s=min_growth,
        boundary=boundary,
        fidelity=AeroelasticFidelity.SCREENING,
        validity=Validity(
            passed=all(checks.values()),
            checks=checks,
            detail=f"evaluated {len(points)} caller-supplied speeds",
        ),
        provenance=provenance,
    )


def _critical_speed(points: tuple[StabilityPoint, ...]) -> FlutterBoundary:
    provenance = analytical_provenance(
        "aeroelasticity.flutter.damping-crossing",
        {"speeds_m_s": [point.speed_m_s for point in points]},
        assumptions=("linear interpolation between supplied speeds",),
    )
    for index in range(len(points) - 1):
        lower = points[index]
        upper = points[index + 1]
        if lower.max_growth_rate_1_s < 0.0 <= upper.max_growth_rate_1_s:
            span = upper.max_growth_rate_1_s - lower.max_growth_rate_1_s
            fraction = (
                (0.0 - lower.max_growth_rate_1_s) / span if span != 0.0 else 0.0
            )
            speed = lower.speed_m_s + fraction * (upper.speed_m_s - lower.speed_m_s)
            unstable = min(
                (mode for mode in upper.modes if mode.growth_rate_1_s >= 0.0),
                key=lambda mode: mode.growth_rate_1_s,
                default=None,
            )
            frequency = unstable.frequency_hz if unstable is not None else None
            return FlutterBoundary(
                critical_speed_m_s=speed,
                critical_frequency_hz=frequency,
                method="quasi-steady-damping-crossing",
                crossing_index=index,
                provenance=provenance,
            )
    return FlutterBoundary(
        critical_speed_m_s=None,
        critical_frequency_hz=None,
        method="stable-through-supplied-range",
        crossing_index=None,
        provenance=provenance,
    )


@dataclass(frozen=True, slots=True)
class AerodynamicDampingEstimate:
    """Aerodynamic damping coefficients from the speed-scaled aero matrix."""

    speed_m_s: float
    dynamic_pressure_pa: float
    per_dof_damping_n_s_m: tuple[float, ...]
    provenance: Provenance

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "speed_m_s": self.speed_m_s,
            "dynamic_pressure_pa": self.dynamic_pressure_pa,
            "per_dof_damping_n_s_m": list(self.per_dof_damping_n_s_m),
        }


def aerodynamic_damping_estimate(
    system: AeroelasticSystem, *, speed_m_s: float
) -> AerodynamicDampingEstimate:
    """Estimate per-DOF aerodynamic damping from the aero velocity matrix."""

    speed = finite(speed_m_s, "speed_m_s", minimum=0.0)
    rho_u = 0.5 * system.density_kg_m3 * speed
    per_dof = tuple(
        rho_u * system.aero_damping_matrix[i][i] for i in range(system.dof)
    )
    return AerodynamicDampingEstimate(
        speed_m_s=speed,
        dynamic_pressure_pa=0.5 * system.density_kg_m3 * speed * speed,
        per_dof_damping_n_s_m=per_dof,
        provenance=analytical_provenance(
            "aeroelasticity.flutter.aerodynamic-damping",
            {"system": system.canonical_payload(), "speed_m_s": speed},
            assumptions=("quasi-steady velocity-proportional aerodynamic damping",),
        ),
    )


@dataclass(frozen=True, slots=True)
class FlutterEscalationPolicy:
    """Thresholds that trigger the next fidelity level near instability."""

    warning_damping_margin: float = 0.02

    def __post_init__(self) -> None:
        finite(self.warning_damping_margin, "warning_damping_margin", positive=True)


@dataclass(frozen=True, slots=True)
class EscalationDecision:
    """The fidelity level and capability requested by an escalation trigger."""

    state: str
    required_fidelity: AeroelasticFidelity
    required_capability: str | None
    detail: str
    provenance: Provenance

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "required_fidelity": self.required_fidelity.value,
            "required_capability": self.required_capability,
            "detail": self.detail,
        }


def assess_flutter_escalation(
    curve: StabilityCurve,
    *,
    policy: FlutterEscalationPolicy | None = None,
    current_fidelity: AeroelasticFidelity = AeroelasticFidelity.SCREENING,
) -> EscalationDecision:
    """Escalate fidelity when the stability margin approaches instability."""

    active = policy or FlutterEscalationPolicy()
    provenance = analytical_provenance(
        "aeroelasticity.flutter.escalation",
        {
            "system_id": curve.system_id,
            "min_growth_rate_1_s": curve.min_growth_rate_1_s,
            "unstable": curve.unstable,
            "current_fidelity": current_fidelity.value,
        },
        assumptions=("proximity-to-instability fidelity escalation",),
    )
    if curve.unstable:
        return EscalationDecision(
            state="triggered",
            required_fidelity=AeroelasticFidelity.TRANSIENT_FSI,
            required_capability=NativeRequirement.PRECICE_FSI.value,
            detail="growth rate reaches zero within the supplied speed range",
            provenance=provenance,
        )
    if curve.min_growth_rate_1_s >= -active.warning_damping_margin:
        return EscalationDecision(
            state="watch",
            required_fidelity=AeroelasticFidelity.HARMONIC,
            required_capability=NativeRequirement.PK_FLUTTER.value,
            detail="growth rate approaches zero; p-k/equivalent level requested",
            provenance=provenance,
        )
    return EscalationDecision(
        state="clear",
        required_fidelity=current_fidelity,
        required_capability=None,
        detail="stable with margin across the supplied speed range",
        provenance=provenance,
    )


def solve_pk_flutter(
    system: AeroelasticSystem,
    *,
    speeds_m_s: tuple[float, ...],
) -> StabilityCurve:
    """Request the p-k/equivalent linear flutter level; fails closed until wired."""

    require_native(NativeRequirement.PK_FLUTTER)


def solve_transient_fsi(
    system: AeroelasticSystem,
    *,
    speed_m_s: float,
    fluid_participant: str = "fluid",
    structural_participant: str = "structure",
) -> StabilityCurve:
    """Request transient CFD/FSI via preCICE; fails closed until wired."""

    if not fluid_participant.strip() or not structural_participant.strip():
        raise AeroelasticError("transient FSI requires two participants")
    finite(speed_m_s, "speed_m_s", minimum=0.0)
    require_native(NativeRequirement.PRECICE_FSI)


__all__ = [
    "AerodynamicDampingEstimate",
    "AeroelasticMode",
    "AeroelasticSystem",
    "EscalationDecision",
    "FlutterBoundary",
    "FlutterEscalationPolicy",
    "StabilityCurve",
    "StabilityPoint",
    "TypicalSection",
    "aerodynamic_damping_estimate",
    "assess_flutter_escalation",
    "build_stability_curve",
    "evaluate_stability",
    "solve_pk_flutter",
    "solve_transient_fsi",
]
