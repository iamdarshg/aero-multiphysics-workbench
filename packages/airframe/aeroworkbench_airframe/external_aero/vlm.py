"""Vortex-lattice (horseshoe) solver for multiple lifting surfaces.

This is a real linear vortex-lattice method, not a correlation: it builds one
horseshoe vortex per spanwise strip (bound filament at the quarter chord,
collocation at the three-quarter chord), solves the no-penetration system for
the circulation, and integrates Kutta-Joukowski force and moment including the
induced downwash, so lift *and* induced drag are resolved consistently.

The aerodynamic frame is ``x`` streamwise, ``y`` spanwise, ``z`` up. A mirrored
half-wing is built as the physical image of the source half (spanwise direction
preserved) so a symmetric full wing resolves a symmetric circulation.

Stability and control derivatives come from central differences of the same
solver; twist, camber zero-lift angle and control deflection enter each strip's
effective incidence. The result is deterministic and hashable. Nothing here is
labelled native: a VSPAERO result comes only from the governed native path.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from math import acos, cos, isfinite, pi, sin, sqrt

from aeroworkbench_core.types import FidelityLevel, Provenance, ResultSource

from ..canonical import content_digest
from .case import (
    ExternalAeroCase,
    control_alpha_increment_deg,
    cosine_fractions,
    interpolate_stations,
)
from .contracts import (
    D_CD_D_ALPHA,
    D_CL_D_ALPHA,
    D_CL_D_BETA,
    D_CL_D_ROLL_RATE,
    D_CM_D_ALPHA,
    D_CM_D_BETA,
    D_CM_D_PITCH_RATE,
    D_CN_D_YAW_RATE,
    D_CY_D_ALPHA,
    D_CY_D_BETA,
    VLM_VALIDITY_LIMITS,
    AeroCoefficients,
    AeroDerivatives,
    AeroReference,
    ExternalAeroFidelity,
    ExternalAeroResult,
    SpanLoad,
    evaluate_aero_validity,
)
from .errors import ExternalAeroValidationError

Vec = tuple[float, float, float]
_ZERO: Vec = (0.0, 0.0, 0.0)

VLM_MODEL = "airframe.external_aero.vortex-lattice"
_SINGULAR_TOLERANCE = 1e-12
_MM_TO_M = 1e-3


@dataclass(frozen=True, slots=True)
class VlmOptions:
    """Deterministic discretization and differentiation controls."""

    panels_per_surface: int = 16
    mirror: bool | None = None
    include_derivatives: bool = True
    derivative_step_deg: float = 0.5
    rate_step: float = 0.01
    require_valid: bool = False

    def __post_init__(self) -> None:
        if self.panels_per_surface < 2:
            raise ExternalAeroValidationError("VLM_REQUIRES_AT_LEAST_TWO_PANELS_PER_SURFACE")
        if not isfinite(self.derivative_step_deg) or self.derivative_step_deg <= 0.0:
            raise ExternalAeroValidationError("VLM_DERIVATIVE_STEP_INVALID")
        if not isfinite(self.rate_step) or self.rate_step <= 0.0:
            raise ExternalAeroValidationError("VLM_RATE_STEP_INVALID")


@dataclass(frozen=True, slots=True)
class _Section:
    surface_id: str
    span_fraction: float
    x_le_m: float
    y_m: float
    z_le_m: float
    chord_m: float
    twist_deg: float
    alpha0_deg: float
    cm_ac: float
    profile_drag: float


@dataclass(frozen=True, slots=True)
class _Panel:
    surface_id: str
    span_fraction: float
    arc_m: float
    chord_m: float
    bound_a: Vec
    bound_b: Vec
    bound_mid: Vec
    collocation: Vec
    theta_base_deg: float
    cm_ac: float
    profile_drag: float


def _add(left: Vec, right: Vec) -> Vec:
    return (left[0] + right[0], left[1] + right[1], left[2] + right[2])


def _sub(left: Vec, right: Vec) -> Vec:
    return (left[0] - right[0], left[1] - right[1], left[2] - right[2])


def _scale(vector: Vec, factor: float) -> Vec:
    return (vector[0] * factor, vector[1] * factor, vector[2] * factor)


def _dot(left: Vec, right: Vec) -> float:
    return left[0] * right[0] + left[1] * right[1] + left[2] * right[2]


def _cross(left: Vec, right: Vec) -> Vec:
    return (
        left[1] * right[2] - left[2] * right[1],
        left[2] * right[0] - left[0] * right[2],
        left[0] * right[1] - left[1] * right[0],
    )


def _norm(vector: Vec) -> float:
    return sqrt(_dot(vector, vector))


def _unit(vector: Vec) -> Vec:
    length = _norm(vector)
    if length <= _SINGULAR_TOLERANCE:
        raise ExternalAeroValidationError("VLM_DEGENERATE_GEOMETRY")
    return _scale(vector, 1.0 / length)


def _segment_velocity(point: Vec, start: Vec, end: Vec) -> Vec:
    """Unit-circulation velocity induced by a finite straight vortex segment."""

    r1 = _sub(point, start)
    r2 = _sub(point, end)
    cross = _cross(r1, r2)
    denom = _dot(cross, cross)
    if denom <= _SINGULAR_TOLERANCE:
        return _ZERO
    r1_len = _norm(r1)
    r2_len = _norm(r2)
    if r1_len <= _SINGULAR_TOLERANCE or r2_len <= _SINGULAR_TOLERANCE:
        return _ZERO
    direction = _sub(end, start)
    coef = _dot(direction, _sub(_scale(r1, 1.0 / r1_len), _scale(r2, 1.0 / r2_len)))
    return _scale(cross, coef / (4.0 * pi * denom))


def _semi_infinite_velocity(point: Vec, start: Vec, direction: Vec) -> Vec:
    """Unit-circulation velocity induced by a semi-infinite vortex from ``start``."""

    r1 = _sub(point, start)
    cross = _cross(direction, r1)
    denom = _dot(cross, cross)
    if denom <= _SINGULAR_TOLERANCE:
        return _ZERO
    r1_len = _norm(r1)
    if r1_len <= _SINGULAR_TOLERANCE:
        return _ZERO
    coef = 1.0 + _dot(r1, direction) / r1_len
    return _scale(cross, coef / (4.0 * pi * denom))


def _horseshoe_velocity(point: Vec, start: Vec, end: Vec, wake: Vec) -> Vec:
    velocity = _segment_velocity(point, start, end)
    velocity = _add(velocity, _semi_infinite_velocity(point, end, wake))
    velocity = _add(velocity, _scale(_semi_infinite_velocity(point, start, wake), -1.0))
    return velocity


def _solve(matrix: list[list[float]], rhs: list[float]) -> list[float]:
    size = len(rhs)
    augmented = [row[:] + [rhs[index]] for index, row in enumerate(matrix)]
    for column in range(size):
        pivot = max(range(column, size), key=lambda row: abs(augmented[row][column]))
        if abs(augmented[pivot][column]) <= _SINGULAR_TOLERANCE:
            raise ExternalAeroValidationError("VLM_SINGULAR_INFLUENCE_MATRIX")
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        pivot_value = augmented[column][column]
        for row in range(size):
            if row == column:
                continue
            factor = augmented[row][column] / pivot_value
            if factor == 0.0:
                continue
            for index in range(column, size + 1):
                augmented[row][index] -= factor * augmented[column][index]
    return [augmented[index][size] / augmented[index][index] for index in range(size)]


def _freestream(alpha_deg: float, beta_deg: float) -> Vec:
    alpha = alpha_deg * pi / 180.0
    beta = beta_deg * pi / 180.0
    return (cos(alpha) * cos(beta), sin(beta), sin(alpha) * cos(beta))


def _lift_direction(freestream: Vec) -> Vec:
    return _unit((-freestream[2], 0.0, freestream[0]))


def _normal_at(theta_base_deg: float) -> Vec:
    theta = theta_base_deg * pi / 180.0
    return (-sin(theta), 0.0, cos(theta))


def _fourier_induced_drag(
    panels: Sequence[_Panel],
    gamma: Sequence[float],
    reference: AeroReference,
) -> tuple[float, tuple[float, ...]]:
    """Classical lifting-line induced drag from the VLM circulation span load.

    The VLM solves the circulation; the induced drag is then evaluated with the
    standard Prandtl Fourier span-load integral, which is finite at the tips and
    avoids the concentrated-edge singularity of a discrete near-field wake sum.
    """

    count = len(panels)
    span = reference.span_m
    velocity = reference.velocity_m_s
    aspect_ratio = span * span / reference.area_m2
    if count < 2 or velocity <= 0.0 or span <= 0.0:
        return 0.0, tuple(0.0 for _ in panels)
    harmonic_count = max(1, count // 2)
    thetas = tuple(
        acos(min(max(-2.0 * panel.arc_m / span, -1.0), 1.0)) for panel in panels
    )
    ordered = sorted(range(count), key=lambda index: thetas[index])
    sorted_thetas = tuple(thetas[index] for index in ordered)
    edges = (
        (0.0,)
        + tuple(
            0.5 * (lower + upper)
            for lower, upper in zip(sorted_thetas, sorted_thetas[1:], strict=False)
        )
        + (pi,)
    )
    widths = tuple(edges[rank + 1] - edges[rank] for rank in range(count))
    coefficients = [0.0] * (harmonic_count + 1)
    scale = 1.0 / (pi * span * velocity)
    for harmonic in range(1, harmonic_count + 1):
        total = sum(
            gamma[ordered[rank]] * sin(harmonic * sorted_thetas[rank]) * widths[rank]
            for rank in range(count)
        )
        coefficients[harmonic] = total * scale
    harmonics = range(1, harmonic_count + 1)
    induced_cdi = (
        pi * aspect_ratio * sum(harmonic * coefficients[harmonic] ** 2 for harmonic in harmonics)
    )
    angles: list[float] = []
    for theta in thetas:
        sine = sin(theta)
        numerator = sum(
            harmonic * coefficients[harmonic] * sin(harmonic * theta)
            for harmonic in range(1, harmonic_count + 1)
        )
        if sine > 1e-8:
            angles.append(numerator / sine)
        else:
            angles.append(
                sum(
                    harmonic * harmonic * coefficients[harmonic]
                    for harmonic in range(1, harmonic_count + 1)
                )
            )
    return induced_cdi, tuple(angles)



def _rate_velocity(point: Vec, rates: tuple[float, float, float], reference: AeroReference) -> Vec:
    roll, pitch, yaw = rates
    speed = reference.velocity_m_s
    omega: Vec = (
        roll * 2.0 * speed / reference.span_m,
        pitch * 2.0 * speed / reference.mean_chord_m,
        yaw * 2.0 * speed / reference.span_m,
    )
    return _cross(omega, _sub(point, reference.moment_reference_m))


def _build_sections(
    case: ExternalAeroCase,
    surface_id: str,
    panels: int,
    mirrored: bool,
) -> list[_Section]:
    surface = case.surface(surface_id)
    model = case.section_model(surface_id)
    alpha0 = model.zero_lift_angle_deg
    cm_ac = model.quarter_chord_moment_coefficient()
    profile_drag = model.profile_drag_coefficient(0.0)
    fractions = cosine_fractions(panels)
    ordered: Sequence[float] = tuple(reversed(fractions)) if mirrored else fractions
    sections: list[_Section] = []
    for fraction in ordered:
        le, chord_mm, twist, _dihedral, _station = interpolate_stations(surface, fraction)
        y = -le[2] * _MM_TO_M if mirrored else le[2] * _MM_TO_M
        sections.append(
            _Section(
                surface_id=surface_id,
                span_fraction=fraction,
                x_le_m=le[0] * _MM_TO_M,
                y_m=y,
                z_le_m=le[1] * _MM_TO_M,
                chord_m=chord_mm * _MM_TO_M,
                twist_deg=twist,
                alpha0_deg=alpha0,
                cm_ac=cm_ac,
                profile_drag=profile_drag,
            )
        )
    return sections


def _build_panels(sections: Sequence[_Section]) -> list[_Panel]:
    panels: list[_Panel] = []
    for left, right in zip(sections, sections[1:], strict=False):
        chord_mid = 0.5 * (left.chord_m + right.chord_m)
        x_le_mid = 0.5 * (left.x_le_m + right.x_le_m)
        z_le_mid = 0.5 * (left.z_le_m + right.z_le_m)
        fraction_mid = 0.5 * (left.span_fraction + right.span_fraction)
        twist_mid = 0.5 * (left.twist_deg + right.twist_deg)
        bound_a = (left.x_le_m + 0.25 * left.chord_m, left.y_m, left.z_le_m)
        bound_b = (right.x_le_m + 0.25 * right.chord_m, right.y_m, right.z_le_m)
        panels.append(
            _Panel(
                surface_id=left.surface_id,
                span_fraction=fraction_mid,
                arc_m=0.5 * (left.y_m + right.y_m),
                chord_m=chord_mid,
                bound_a=bound_a,
                bound_b=bound_b,
                bound_mid=_scale(_add(bound_a, bound_b), 0.5),
                collocation=(
                    x_le_mid + 0.75 * chord_mid,
                    0.5 * (left.y_m + right.y_m),
                    z_le_mid,
                ),
                theta_base_deg=twist_mid - left.alpha0_deg,
                cm_ac=left.cm_ac,
                profile_drag=0.5 * (left.profile_drag + right.profile_drag),
            )
        )
    return panels


@dataclass(frozen=True, slots=True)
class _State:
    coefficients: AeroCoefficients
    loads: tuple[SpanLoad, ...]


@dataclass(frozen=True, slots=True)
class _Solver:
    case: ExternalAeroCase
    reference: AeroReference
    panels: tuple[_Panel, ...]
    wake: Vec
    influence: tuple[tuple[float, ...], ...]

    @classmethod
    def build(
        cls, case: ExternalAeroCase, reference: AeroReference, options: VlmOptions
    ) -> _Solver:
        mirror = case.symmetry == "mirror" if options.mirror is None else options.mirror
        panels: list[_Panel] = []
        for surface in case.surfaces:
            panels.extend(
                _build_panels(
                    _build_sections(case, surface.surface_id, options.panels_per_surface, False)
                )
            )
            if mirror:
                panels.extend(
                    _build_panels(
                        _build_sections(case, surface.surface_id, options.panels_per_surface, True)
                    )
                )
        wake = (1.0, 0.0, 0.0)
        influence = tuple(
            tuple(
                _dot(
                    _horseshoe_velocity(
                        panel.collocation, other.bound_a, other.bound_b, wake
                    ),
                    _normal_at(panel.theta_base_deg),
                )
                for other in panels
            )
            for panel in panels
        )
        return cls(case, reference, tuple(panels), wake, influence)

    def _rhs(
        self,
        alpha_deg: float,
        beta_deg: float,
        rates: tuple[float, float, float],
        deflections: tuple[tuple[str, float], ...] | None,
    ) -> list[float]:
        freestream = _scale(_freestream(alpha_deg, beta_deg), self.reference.velocity_m_s)
        components: list[float] = []
        for panel in self.panels:
            control = control_alpha_increment_deg(
                self.case, panel.surface_id, panel.span_fraction, deflections
            )
            normal = _normal_at(panel.theta_base_deg + control)
            inflow = _add(freestream, _rate_velocity(panel.collocation, rates, self.reference))
            components.append(-_dot(inflow, normal))
        return components

    def solve_state(
        self,
        alpha_deg: float,
        beta_deg: float,
        rates: tuple[float, float, float] = (0.0, 0.0, 0.0),
        deflections: tuple[tuple[str, float], ...] | None = None,
    ) -> _State:
        rhs = self._rhs(alpha_deg, beta_deg, rates, deflections)
        gamma = _solve([list(row) for row in self.influence], rhs)
        freestream = _freestream(alpha_deg, beta_deg)
        lift_unit = _lift_direction(freestream)
        velocity = self.reference.velocity_m_s
        density = self.reference.density_kg_m3
        dynamic = self.reference.dynamic_pressure_pa
        area = self.reference.area_m2
        chord = self.reference.mean_chord_m

        force: Vec = _ZERO
        moment: Vec = _ZERO
        planform_area = 0.0
        profile_area = 0.0
        spans: list[float] = []
        for index, panel in enumerate(self.panels):
            dl = _sub(panel.bound_b, panel.bound_a)
            span = _norm(dl)
            spans.append(span)
            panel_force = _scale(_cross(freestream, dl), density * velocity * gamma[index])
            force = _add(force, panel_force)
            moment = _add(
                moment,
                _cross(_sub(panel.bound_mid, self.reference.moment_reference_m), panel_force),
            )
            moment = _add(
                moment,
                (0.0, dynamic * panel.chord_m**2 * panel.cm_ac * span, 0.0),
            )
            planform_area += panel.chord_m * span
            profile_area += panel.profile_drag * panel.chord_m * span

        induced_cdi, induced_angles = _fourier_induced_drag(self.panels, gamma, self.reference)
        profile_drag = profile_area / planform_area if planform_area > 0.0 else 0.0
        loads: list[SpanLoad] = []
        for index, panel in enumerate(self.panels):
            dl = _sub(panel.bound_b, panel.bound_a)
            span = spans[index]
            panel_force = _scale(_cross(freestream, dl), density * velocity * gamma[index])
            lift_per_span = _dot(panel_force, lift_unit) / span if span > 0.0 else 0.0
            section_cl = (
                lift_per_span / (dynamic * panel.chord_m)
                if panel.chord_m > 0.0 and dynamic > 0.0
                else 0.0
            )
            loads.append(
                SpanLoad(
                    surface_id=panel.surface_id,
                    span_fraction=panel.span_fraction,
                    arc_m=panel.arc_m,
                    chord_m=panel.chord_m,
                    section_lift_coefficient=section_cl,
                    circulation_m2_s=gamma[index],
                    lift_per_span_n_m=lift_per_span,
                    induced_alpha_deg=induced_angles[index] * 180.0 / pi,
                )
            )

        coefficients = AeroCoefficients(
            lift=_dot(force, lift_unit) / (dynamic * area),
            drag=induced_cdi + profile_drag,
            side=force[1] / (dynamic * area),
            roll=moment[0] / (dynamic * area * self.reference.span_m),
            pitch=moment[1] / (dynamic * area * chord),
            yaw=moment[2] / (dynamic * area * self.reference.span_m),
        )
        return _State(coefficients=coefficients, loads=tuple(loads))


def _derivatives(solver: _Solver, options: VlmOptions) -> AeroDerivatives:
    step = options.derivative_step_deg
    alpha = solver.reference.alpha_deg
    beta = solver.reference.beta_deg

    plus = solver.solve_state(alpha + step, beta).coefficients
    minus = solver.solve_state(alpha - step, beta).coefficients
    values: list[tuple[str, float]] = [
        (D_CL_D_ALPHA, (plus.lift - minus.lift) / (2.0 * step)),
        (D_CD_D_ALPHA, (plus.drag - minus.drag) / (2.0 * step)),
        (D_CY_D_ALPHA, (plus.side - minus.side) / (2.0 * step)),
        (D_CM_D_ALPHA, (plus.pitch - minus.pitch) / (2.0 * step)),
    ]
    beta_plus = solver.solve_state(alpha, beta + step).coefficients
    beta_minus = solver.solve_state(alpha, beta - step).coefficients
    values.extend(
        [
            (D_CL_D_BETA, (beta_plus.lift - beta_minus.lift) / (2.0 * step)),
            (D_CY_D_BETA, (beta_plus.side - beta_minus.side) / (2.0 * step)),
            (D_CM_D_BETA, (beta_plus.pitch - beta_minus.pitch) / (2.0 * step)),
        ]
    )

    rate_step = options.rate_step
    roll_plus = solver.solve_state(alpha, beta, (rate_step, 0.0, 0.0)).coefficients
    roll_minus = solver.solve_state(alpha, beta, (-rate_step, 0.0, 0.0)).coefficients
    pitch_plus = solver.solve_state(alpha, beta, (0.0, rate_step, 0.0)).coefficients
    pitch_minus = solver.solve_state(alpha, beta, (0.0, -rate_step, 0.0)).coefficients
    yaw_plus = solver.solve_state(alpha, beta, (0.0, 0.0, rate_step)).coefficients
    yaw_minus = solver.solve_state(alpha, beta, (0.0, 0.0, -rate_step)).coefficients
    values.extend(
        [
            (D_CL_D_ROLL_RATE, (roll_plus.roll - roll_minus.roll) / (2.0 * rate_step)),
            (D_CM_D_PITCH_RATE, (pitch_plus.pitch - pitch_minus.pitch) / (2.0 * rate_step)),
            (D_CN_D_YAW_RATE, (yaw_plus.yaw - yaw_minus.yaw) / (2.0 * rate_step)),
        ]
    )

    for control in solver.case.controls:
        control_id = control.control_id
        plus_state = solver.solve_state(
            alpha, beta, deflections=((control_id, step),)
        ).coefficients
        minus_state = solver.solve_state(
            alpha, beta, deflections=((control_id, -step),)
        ).coefficients
        values.extend(
            [
                (f"dCL/ddelta:{control_id}", (plus_state.lift - minus_state.lift) / (2.0 * step)),
                (f"dCm/ddelta:{control_id}", (plus_state.pitch - minus_state.pitch) / (2.0 * step)),
                (f"dCD/ddelta:{control_id}", (plus_state.drag - minus_state.drag) / (2.0 * step)),
            ]
        )
    return AeroDerivatives(values=tuple(values), method="vlm-central-difference", step_deg=step)


def solve_vlm(
    case: ExternalAeroCase,
    reference: AeroReference,
    options: VlmOptions | None = None,
    *,
    deflections: tuple[tuple[str, float], ...] | None = None,
) -> ExternalAeroResult:
    """Solve the vortex-lattice case and return the canonical result contract."""

    resolved = options or VlmOptions()
    if reference.velocity_m_s <= 0.0:
        raise ExternalAeroValidationError("VLM_REQUIRES_POSITIVE_VELOCITY")
    validity = evaluate_aero_validity(reference, VLM_VALIDITY_LIMITS)
    if resolved.require_valid and not validity.passed:
        raise ExternalAeroValidationError(f"VLM_REFERENCE_INVALID:{validity.detail}")
    solver = _Solver.build(case, reference, resolved)
    state = solver.solve_state(
        reference.alpha_deg, reference.beta_deg, reference.angular_rates, deflections
    )
    derivatives = _derivatives(solver, resolved) if resolved.include_derivatives else None
    mirror = case.symmetry == "mirror" if resolved.mirror is None else resolved.mirror
    provenance = Provenance.from_inputs(
        source=ResultSource.ANALYTICAL,
        model=VLM_MODEL,
        model_version="1.0.0",
        fidelity=FidelityLevel.ANALYTICAL,
        inputs={
            "case": case.digest,
            "reference": reference.canonical(),
            "discretization": vlm_panel_digest(case, resolved.panels_per_surface, mirror),
        },
        assumptions=(
            "linear vortex-lattice theory; thin attached lifting surfaces; small angles",
            "fixed streamwise wake; no viscosity or compressibility correction",
        ),
    )
    return ExternalAeroResult(
        result_id=f"{case.case_id}-vlm",
        fidelity=ExternalAeroFidelity.VLM,
        source=ResultSource.ANALYTICAL,
        reference=reference,
        coefficients=state.coefficients,
        derivatives=derivatives,
        validity=validity,
        distributed_loads=state.loads,
        provenance=provenance,
    )


def vlm_panel_digest(case: ExternalAeroCase, panels_per_surface: int, mirror: bool) -> str:
    """Deterministic identity of the discretization used by a VLM solve."""

    return content_digest(
        {
            "case": case.digest,
            "panelsPerSurface": panels_per_surface,
            "mirror": mirror,
        }
    )


__all__ = [
    "VLM_MODEL",
    "VlmOptions",
    "solve_vlm",
    "vlm_panel_digest",
]
