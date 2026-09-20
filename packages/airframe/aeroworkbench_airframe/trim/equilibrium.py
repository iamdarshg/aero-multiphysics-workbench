"""Generic trim solver over selected state and control variables.

The residual system is the three steady-flight equilibrium conditions: lift
balance normal to the flight path, thrust/drag balance along it, and zero
pitching moment. Any three of ``alpha``, ``elevator``, ``throttle``, ``thrust``,
``velocity`` and ``gamma`` may be selected as unknowns; the rest are fixed by
the flight condition. A converged trim is never allowed to hide a control
authority or static stability violation.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from math import cos, sin
from typing import Any

from ..state import Controls
from ..units import Quantity
from .authority import ControlAuthorityReport, evaluate_control_authority
from .contract import (
    AerodynamicCoefficientProvider,
    AeroReference,
    AeroState,
    FlightCondition,
    ResultMeta,
    TrimFidelity,
    finite,
    result_meta,
)
from .errors import AeroCoefficientError, TrimSolverError
from .linalg import solve_linear
from .stability import StaticStabilityReport, evaluate_static_stability

MODEL = "airframe-trim-equilibrium"

_ASSUMPTIONS = (
    "Steady point-mass/longitudinal equilibrium about the moment reference.",
    "Linear control effectiveness and static derivatives at the trim state.",
    "Screening trim only; native nonlinear verification is a capability-gated seam.",
)

TRIMMED = "trimmed"
INFEASIBLE = "infeasible"
NOT_CONVERGED = "not-converged"
PREFLIGHT_INVALID = "preflight-invalid"

_cos = cos
_sin = sin

ResidualVector = tuple[float, float, float]
ResidualEvaluator = Callable[[Sequence[float]], tuple[ResidualVector, ResidualVector]]

_VARIABLE_UNITS: dict[str, str] = {
    "alpha": "rad",
    "elevator": "rad",
    "throttle": "dimensionless",
    "thrust": "N",
    "velocity": "m/s",
    "gamma": "rad",
}


class TrimVariable(StrEnum):
    """Selectable trim unknowns."""

    ALPHA = "alpha"
    ELEVATOR = "elevator"
    THROTTLE = "throttle"
    THRUST = "thrust"
    VELOCITY = "velocity"
    GAMMA = "gamma"

    @staticmethod
    def surface(name: str) -> TrimControl:
        return TrimControl("surface", name)

    @staticmethod
    def rpm() -> TrimControl:
        return TrimControl("rpm", "rpm")

    @staticmethod
    def collective() -> TrimControl:
        return TrimControl("collective", "collective")

    @staticmethod
    def cyclic(name: str) -> TrimControl:
        return TrimControl("cyclic", name)


@dataclass(frozen=True, slots=True)
class TrimControl:
    """A generic AIRFRAME 01 control that may be selected as a trim unknown."""

    kind: str
    name: str

    def __post_init__(self) -> None:
        if self.kind not in {"surface", "rpm", "collective", "cyclic"}:
            raise ValueError(f"UNKNOWN_TRIM_CONTROL_KIND:{self.kind}")
        if not self.name.strip():
            raise ValueError("TRIM_CONTROL_NAME_REQUIRED")
        if self.kind in {"rpm", "collective"} and self.name != self.kind:
            raise ValueError(f"TRIM_CONTROL_NAME_MISMATCH:{self.kind}")

    @classmethod
    def surface(cls, name: str) -> TrimControl:
        return cls("surface", name)

    @classmethod
    def rpm(cls) -> TrimControl:
        return cls("rpm", "rpm")

    @classmethod
    def collective(cls) -> TrimControl:
        return cls("collective", "collective")

    @classmethod
    def cyclic(cls, name: str) -> TrimControl:
        return cls("cyclic", name)


TrimUnknown = TrimVariable | TrimControl


@dataclass(frozen=True, slots=True)
class NewtonSettings:
    max_iterations: int = 60
    tolerance: float = 1e-10
    finite_difference_step: float = 1e-7

    def __post_init__(self) -> None:
        if self.max_iterations < 1:
            raise ValueError("NONPOSITIVE_MAX_ITERATIONS")
        finite(self.tolerance, "newton.tolerance")
        if self.tolerance <= 0.0:
            raise ValueError("NONPOSITIVE_NEWTON_TOLERANCE")
        finite(self.finite_difference_step, "newton.finiteDifferenceStep")
        if self.finite_difference_step <= 0.0:
            raise ValueError("NONPOSITIVE_FD_STEP")


@dataclass(frozen=True, slots=True)
class TrimSpec:
    """A trim problem: condition, selected variables, and control limits."""

    condition: FlightCondition
    variables: tuple[TrimUnknown, ...]
    initial: tuple[tuple[TrimUnknown, float], ...] = ()
    controls: Controls = Controls()
    elevator_limit: Quantity | None = None
    aileron_limit: Quantity | None = None
    rudder_limit: Quantity | None = None
    require_stability: bool = True
    settings: NewtonSettings = NewtonSettings()

    def __post_init__(self) -> None:
        if len(self.variables) != 3:
            raise ValueError("TRIM_REQUIRES_THREE_VARIABLES")
        if len(set(self.variables)) != len(self.variables):
            raise ValueError("DUPLICATE_TRIM_VARIABLE")
        names = [name for name, _ in self.initial]
        if len(names) != len(set(names)):
            raise ValueError("DUPLICATE_TRIM_INITIAL")
        for _, value in self.initial:
            finite(value, "trim.initial")
        for label, limit in (
            ("elevator", self.elevator_limit),
            ("aileron", self.aileron_limit),
            ("rudder", self.rudder_limit),
        ):
            if limit is not None and limit.dimension != "angle":
                raise ValueError(f"TRIM_LIMIT_NOT_ANGLE:{label}")
        for variable in self.variables:
            if not isinstance(variable, (TrimVariable, TrimControl)):
                raise ValueError(f"UNKNOWN_TRIM_VARIABLE:{variable!r}")
            if isinstance(variable, TrimControl) and not _control_is_bound(
                variable, self.controls
            ):
                raise ValueError(
                    f"TRIM_CONTROL_UNBOUND:{variable.kind}:{variable.name}"
                )


class _ThrustMode(StrEnum):
    THROTTLE = "throttle"
    THRUST = "thrust"
    FIXED = "fixed"


@dataclass(frozen=True, slots=True)
class TrimResiduals:
    lift: float
    thrust: float
    pitch: float
    scaled_norm: float

    def as_dict(self) -> dict[str, float]:
        return {
            "liftN": self.lift,
            "thrustN": self.thrust,
            "pitchNm": self.pitch,
            "scaledNorm": self.scaled_norm,
        }


@dataclass(frozen=True, slots=True)
class TrimSolution:
    alpha: Quantity
    elevator: Quantity
    throttle: float | None
    thrust: Quantity
    velocity: Quantity
    gamma: Quantity
    lift: Quantity
    drag: Quantity
    pitch_moment: Quantity
    controls: Controls = Controls()

    def as_dict(self) -> dict[str, Any]:
        return {
            "alpha": self.alpha.canonical(),
            "elevator": self.elevator.canonical(),
            "throttle": self.throttle,
            "thrust": self.thrust.canonical(),
            "velocity": self.velocity.canonical(),
            "gamma": self.gamma.canonical(),
            "lift": self.lift.canonical(),
            "drag": self.drag.canonical(),
            "pitchMoment": self.pitch_moment.canonical(),
            "controls": self.controls.canonical(),
        }


@dataclass(frozen=True, slots=True)
class TrimResult:
    status: str
    converged: bool
    feasible: bool
    solution: TrimSolution | None
    residuals: TrimResiduals | None
    iterations: int
    control_authority: ControlAuthorityReport | None
    static_stability: StaticStabilityReport | None
    fidelity: TrimFidelity
    notes: tuple[str, ...]
    meta: ResultMeta

    @property
    def trimmed(self) -> bool:
        return self.status == TRIMMED

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "converged": self.converged,
            "feasible": self.feasible,
            "fidelity": self.fidelity.value,
            "solution": None if self.solution is None else self.solution.as_dict(),
            "residuals": None if self.residuals is None else self.residuals.as_dict(),
            "iterations": self.iterations,
            "controlAuthority": (
                None
                if self.control_authority is None
                else self.control_authority.as_dict()
            ),
            "staticStability": (
                None
                if self.static_stability is None
                else self.static_stability.as_dict()
            ),
            "notes": list(self.notes),
            "meta": self.meta.as_dict(),
        }

    @property
    def content_hash(self) -> str:
        from ..canonical import content_digest

        return content_digest(self.as_dict())


def _control_is_bound(control: TrimControl, controls: Controls) -> bool:
    if control.kind == "surface":
        return control.name in {name for name, _ in controls.surface_deflections}
    if control.kind == "cyclic":
        return control.name in {name for name, _ in controls.cyclic}
    return getattr(controls, control.kind) is not None


def _control_value(control: TrimControl, controls: Controls) -> float:
    if control.kind == "surface":
        return dict(controls.surface_deflections)[control.name].value_si
    if control.kind == "cyclic":
        return dict(controls.cyclic)[control.name].value_si
    if control.kind == "rpm":
        quantity = controls.rpm
    elif control.kind == "collective":
        quantity = controls.collective
    else:
        raise ValueError(f"UNKNOWN_TRIM_CONTROL_KIND:{control.kind}")
    assert quantity is not None
    return quantity.value_si


def _controls_for_values(
    baseline: Controls, values: Mapping[TrimUnknown, float]
) -> Controls:
    surfaces = dict(baseline.surface_deflections)
    cyclic = dict(baseline.cyclic)
    throttle = baseline.throttle
    rpm = baseline.rpm
    collective = baseline.collective
    if TrimVariable.ELEVATOR in values:
        surfaces.setdefault("elevator", Quantity(values[TrimVariable.ELEVATOR], "rad"))
        surfaces["elevator"] = Quantity(values[TrimVariable.ELEVATOR], "rad")
    if TrimVariable.THROTTLE in values:
        raw = values[TrimVariable.THROTTLE]
        # Preserve the historical solver's ability to report throttle > 1 as
        # infeasible; canonical Controls validation is applied to valid/fixed
        # controls and to the final result below.
        throttle = Quantity(raw, "dimensionless") if 0.0 <= raw <= 1.0 else None
    for variable, value in values.items():
        if not isinstance(variable, TrimControl):
            continue
        quantity = Quantity(value, "rad")
        if variable.kind == "surface":
            surfaces[variable.name] = quantity
        elif variable.kind == "cyclic":
            cyclic[variable.name] = quantity
        elif variable.kind == "rpm":
            rpm = Quantity(value, "rev/s")
        elif variable.kind == "collective":
            collective = quantity
    return Controls(
        surface_deflections=tuple(surfaces.items()),
        throttle=throttle,
        rpm=rpm,
        collective=collective,
        cyclic=tuple(cyclic.items()),
        tilt=baseline.tilt,
    )


def _initial_values(spec: TrimSpec) -> dict[TrimUnknown, float]:
    condition = spec.condition
    values: dict[TrimUnknown, float] = {
        TrimVariable.ALPHA: 0.0,
        TrimVariable.ELEVATOR: 0.0,
        TrimVariable.THROTTLE: 0.0,
        TrimVariable.THRUST: (
            condition.thrust.value_si if condition.thrust is not None else 0.0
        ),
        TrimVariable.VELOCITY: condition.velocity.value_si,
        TrimVariable.GAMMA: condition.gamma.value_si,
    }
    for variable in spec.variables:
        if isinstance(variable, TrimControl):
            values[variable] = _control_value(variable, spec.controls)
    for variable, value in spec.initial:
        values[variable] = value
    return values


def _thrust_mode(
    spec: TrimSpec, variables: tuple[TrimUnknown, ...]
) -> _ThrustMode | None:
    condition = spec.condition
    if TrimVariable.THROTTLE in variables:
        return _ThrustMode.THROTTLE if condition.thrust_max is not None else None
    if TrimVariable.THRUST in variables:
        return _ThrustMode.THRUST
    return _ThrustMode.FIXED if condition.thrust is not None else None


def _make_evaluator(
    provider: AerodynamicCoefficientProvider,
    spec: TrimSpec,
    reference: AeroReference,
    mode: _ThrustMode,
) -> ResidualEvaluator:
    condition = spec.condition
    rho = condition.density.value_si
    weight = condition.weight().value_si
    load_factor = condition.resolved_load_factor()
    area = reference.area.value_si
    chord = reference.chord.value_si
    thrust_max = (
        condition.thrust_max.value_si if condition.thrust_max is not None else 0.0
    )
    fixed_thrust = condition.thrust.value_si if condition.thrust is not None else 0.0
    order = spec.variables

    def evaluate(x: Sequence[float]) -> tuple[ResidualVector, ResidualVector]:
        fixed = _initial_values(spec)
        for variable, val in zip(order, x, strict=True):
            fixed[variable] = val
        alpha = fixed[TrimVariable.ALPHA]
        velocity = fixed[TrimVariable.VELOCITY]
        gamma = fixed[TrimVariable.GAMMA]
        if velocity <= 1e-6:
            raise TrimSolverError("NONPOSITIVE_TRIM_VELOCITY")
        q_dyn = 0.5 * rho * velocity * velocity
        controls = _controls_for_values(spec.controls, fixed)
        state = AeroState(
            alpha=Quantity(alpha, "rad"),
            velocity=Quantity(velocity, "m/s"),
            deflections=tuple(controls.surface_deflections),
            controls=controls,
        )
        coeff = provider.coefficients(state)
        lift = q_dyn * area * coeff.c_lift
        drag = q_dyn * area * coeff.c_drag
        pitch = q_dyn * area * chord * coeff.c_pitch
        if mode is _ThrustMode.THROTTLE:
            thrust = thrust_max * fixed[TrimVariable.THROTTLE]
        elif mode is _ThrustMode.THRUST:
            thrust = fixed[TrimVariable.THRUST]
        else:
            thrust = fixed_thrust
        raw = (
            lift - load_factor * weight * _cos(gamma),
            thrust - drag - weight * _sin(gamma),
            pitch,
        )
        scale = (weight, weight, q_dyn * area * chord)
        scaled: ResidualVector = (
            raw[0] / scale[0],
            raw[1] / scale[1],
            raw[2] / scale[2],
        )
        return raw, scaled

    return evaluate


def _newton(
    evaluate: ResidualEvaluator,
    initial: Sequence[float],
    settings: NewtonSettings,
) -> tuple[list[float], int, bool]:
    size = len(initial)
    x = list(initial)

    def scaled_norm(vector: Sequence[float]) -> float:
        return float(sum(component * component for component in vector) ** 0.5)

    for iteration in range(settings.max_iterations):
        _, scaled = evaluate(x)
        if scaled_norm(scaled) <= settings.tolerance:
            return x, iteration, True
        raw, _ = evaluate(x)
        jacobian: list[list[float]] = [[0.0] * size for _ in range(size)]
        for column in range(size):
            step = settings.finite_difference_step * max(1.0, abs(x[column]))
            plus = list(x)
            minus = list(x)
            plus[column] += step
            minus[column] -= step
            raw_plus, _ = evaluate(plus)
            raw_minus, _ = evaluate(minus)
            for row in range(size):
                jacobian[row][column] = (raw_plus[row] - raw_minus[row]) / (2.0 * step)
        delta = solve_linear(jacobian, [-component for component in raw])
        baseline = scaled_norm(scaled)
        step_scale = 1.0
        accepted = False
        for _ in range(40):
            trial = [x[index] + step_scale * delta[index] for index in range(size)]
            try:
                _, trial_scaled = evaluate(trial)
            except TrimSolverError:
                trial_scaled = None
            if trial_scaled is not None and scaled_norm(trial_scaled) < baseline:
                x = trial
                accepted = True
                break
            step_scale *= 0.5
        if not accepted:
            return x, iteration, False
    raw, scaled = evaluate(x)
    del raw
    return x, settings.max_iterations, scaled_norm(scaled) <= settings.tolerance


def _solution_from(
    provider: AerodynamicCoefficientProvider,
    spec: TrimSpec,
    reference: AeroReference,
    mode: _ThrustMode,
    values: Mapping[TrimUnknown, float],
) -> tuple[TrimSolution, TrimResiduals, AeroState]:
    condition = spec.condition
    alpha = values[TrimVariable.ALPHA]
    elevator = values[TrimVariable.ELEVATOR]
    velocity = values[TrimVariable.VELOCITY]
    gamma = values[TrimVariable.GAMMA]
    q_dyn = 0.5 * condition.density.value_si * velocity * velocity
    controls = _controls_for_values(spec.controls, values)
    state = AeroState(
        alpha=Quantity(alpha, "rad"),
        velocity=Quantity(velocity, "m/s"),
        deflections=tuple(controls.surface_deflections),
        controls=controls,
    )
    coeff = provider.coefficients(state)
    area = reference.area.value_si
    chord = reference.chord.value_si
    weight = condition.weight().value_si
    load_factor = condition.resolved_load_factor()
    lift = q_dyn * area * coeff.c_lift
    drag = q_dyn * area * coeff.c_drag
    pitch = q_dyn * area * chord * coeff.c_pitch
    thrust_max = (
        condition.thrust_max.value_si if condition.thrust_max is not None else 0.0
    )
    if mode is _ThrustMode.THROTTLE:
        thrust = thrust_max * values[TrimVariable.THROTTLE]
        throttle: float | None = values[TrimVariable.THROTTLE]
    elif mode is _ThrustMode.THRUST:
        thrust = values[TrimVariable.THRUST]
        throttle = None
    else:
        thrust = condition.thrust.value_si if condition.thrust is not None else 0.0
        throttle = None
    residual_lift = lift - load_factor * weight * _cos(gamma)
    residual_thrust = thrust - drag - weight * _sin(gamma)
    scale = (weight, weight, q_dyn * area * chord)
    scaled = (
        residual_lift / scale[0],
        residual_thrust / scale[1],
        pitch / scale[2],
    )
    residuals = TrimResiduals(
        lift=residual_lift,
        thrust=residual_thrust,
        pitch=pitch,
        scaled_norm=sum(component * component for component in scaled) ** 0.5,
    )
    solution = TrimSolution(
        alpha=Quantity(alpha, "rad"),
        elevator=Quantity(elevator, "rad"),
        throttle=throttle,
        thrust=Quantity(thrust, "N"),
        velocity=Quantity(velocity, "m/s"),
        gamma=Quantity(gamma, "rad"),
        lift=Quantity(lift, "N"),
        drag=Quantity(drag, "N"),
        pitch_moment=Quantity(pitch, "N.m"),
        controls=controls,
    )
    return solution, residuals, state


def _result(
    *,
    spec: TrimSpec,
    provider: AerodynamicCoefficientProvider,
    reference: AeroReference,
    status: str,
    converged: bool,
    feasible: bool,
    solution: TrimSolution | None,
    residuals: TrimResiduals | None,
    iterations: int,
    authority: ControlAuthorityReport | None,
    stability: StaticStabilityReport | None,
    notes: tuple[str, ...],
) -> TrimResult:
    inputs = {
        "provider": provider.provider_id,
        "condition": spec.condition.as_dict(),
        "variables": [
            variable.value
            if isinstance(variable, TrimVariable)
            else f"{variable.kind}:{variable.name}"
            for variable in spec.variables
        ],
        "reference": reference.as_dict(),
        "elevatorLimit": None
        if spec.elevator_limit is None
        else spec.elevator_limit.canonical(),
        "controls": spec.controls.canonical(),
        "solution": None if solution is None else solution.as_dict(),
    }
    meta = result_meta(
        model=MODEL,
        inputs=inputs,
        valid=status == TRIMMED,
        notes=notes,
        assumptions=_ASSUMPTIONS,
    )
    return TrimResult(
        status=status,
        converged=converged,
        feasible=feasible,
        solution=solution,
        residuals=residuals,
        iterations=iterations,
        control_authority=authority,
        static_stability=stability,
        fidelity=TrimFidelity.SCREENING,
        notes=notes,
        meta=meta,
    )


def solve_trim(
    provider: AerodynamicCoefficientProvider,
    spec: TrimSpec,
) -> TrimResult:
    """Solve the selected-variable trim problem and evaluate its constraints."""

    reference = provider.reference()
    mode = _thrust_mode(spec, spec.variables)
    if mode is None:
        return _result(
            spec=spec,
            provider=provider,
            reference=reference,
            status=PREFLIGHT_INVALID,
            converged=False,
            feasible=False,
            solution=None,
            residuals=None,
            iterations=0,
            authority=None,
            stability=None,
            notes=("THRUST_SOURCE_UNAVAILABLE",),
        )
    values = _initial_values(spec)
    evaluate = _make_evaluator(provider, spec, reference, mode)
    x0 = [values[variable] for variable in spec.variables]
    try:
        x, iterations, converged = _newton(evaluate, x0, spec.settings)
    except (AeroCoefficientError, TrimSolverError) as error:
        return _result(
            spec=spec,
            provider=provider,
            reference=reference,
            status=PREFLIGHT_INVALID,
            converged=False,
            feasible=False,
            solution=None,
            residuals=None,
            iterations=0,
            authority=None,
            stability=None,
            notes=(str(error),),
        )
    for variable, value in zip(spec.variables, x, strict=True):
        values[variable] = value
    try:
        solution, residuals, state = _solution_from(
            provider, spec, reference, mode, values
        )
    except (AeroCoefficientError, TrimSolverError) as error:
        return _result(
            spec=spec,
            provider=provider,
            reference=reference,
            status=PREFLIGHT_INVALID,
            converged=converged,
            feasible=False,
            solution=None,
            residuals=None,
            iterations=iterations,
            authority=None,
            stability=None,
            notes=(str(error),),
        )
    if not converged:
        return _result(
            spec=spec,
            provider=provider,
            reference=reference,
            status=NOT_CONVERGED,
            converged=False,
            feasible=False,
            solution=solution,
            residuals=residuals,
            iterations=iterations,
            authority=None,
            stability=None,
            notes=("TRIM_DID_NOT_CONVERGE",),
        )
    notes: list[str] = []
    dynamic_pressure = (
        0.5 * spec.condition.density.value_si * solution.velocity.value_si**2
    )
    if solution.throttle is not None and not 0.0 <= solution.throttle <= 1.0:
        notes.append("THROTTLE_OUT_OF_RANGE")
    stability: StaticStabilityReport | None = None
    bundle = provider.derivatives(state)
    if not bundle.valid:
        notes.extend(bundle.notes or ("DERIVATIVE_OPERATING_POINT_INVALID",))
    if reference.cg_mac_fraction is None:
        if spec.require_stability:
            notes.append("CG_UNAVAILABLE_FOR_STATIC_MARGIN")
    else:
        stability = evaluate_static_stability(
            bundle.longitudinal,
            bundle.lateral_directional,
            cg_mac_fraction=reference.cg_mac_fraction,
            high_speed_valid=bundle.valid,
            high_speed_notes=bundle.notes,
        )
        if not stability.valid:
            notes.append("STATIC_STABILITY_COVERAGE_INSUFFICIENT")
    authority: ControlAuthorityReport | None = None
    if (
        spec.elevator_limit is not None
        or spec.aileron_limit is not None
        or spec.rudder_limit is not None
    ):
        state_zero = AeroState(
            alpha=solution.alpha,
            velocity=solution.velocity,
            deflections=(("elevator", Quantity(0.0, "rad")),),
        )
        coeff_zero = provider.coefficients(state_zero)
        required_pitch = (
            -dynamic_pressure
            * reference.area.value_si
            * reference.chord.value_si
            * coeff_zero.c_pitch
        )
        try:
            authority = evaluate_control_authority(
                provider,
                state_zero,
                reference=reference,
                dynamic_pressure=dynamic_pressure,
                required_pitch_moment=required_pitch,
                elevator_limit=spec.elevator_limit,
                aileron_limit=spec.aileron_limit,
                rudder_limit=spec.rudder_limit,
            )
        except AeroCoefficientError as error:
            notes.append(str(error))
    infeasible = False
    invalid = False
    if not bundle.valid:
        invalid = True
    if "THROTTLE_OUT_OF_RANGE" in notes:
        infeasible = True
    if authority is not None and not authority.within_authority:
        infeasible = True
        notes.extend(authority.reasons)
    if stability is not None:
        if not stability.valid:
            invalid = True
        elif stability.longitudinal_stable is False:
            infeasible = True
            notes.append("STATIC_INSTABILITY_CONSTRAINT_VIOLATION")
    if spec.require_stability and reference.cg_mac_fraction is None:
        invalid = True
    if invalid:
        status = PREFLIGHT_INVALID
    elif infeasible:
        status = INFEASIBLE
    else:
        status = TRIMMED
    return _result(
        spec=spec,
        provider=provider,
        reference=reference,
        status=status,
        converged=True,
        feasible=status == TRIMMED,
        solution=solution,
        residuals=residuals,
        iterations=iterations,
        authority=authority,
        stability=stability,
        notes=tuple(notes),
    )


def trim_level_flight(
    provider: AerodynamicCoefficientProvider,
    condition: FlightCondition,
    *,
    elevator_limit: Quantity | None = None,
    initial_alpha: float = 0.0,
    initial_elevator: float = 0.0,
    require_stability: bool = True,
) -> TrimResult:
    """Convenience level-flight trim in ``alpha``, ``elevator``, ``throttle``."""

    spec = TrimSpec(
        condition=condition,
        variables=(TrimVariable.ALPHA, TrimVariable.ELEVATOR, TrimVariable.THROTTLE),
        initial=(
            (TrimVariable.ALPHA, initial_alpha),
            (TrimVariable.ELEVATOR, initial_elevator),
        ),
        elevator_limit=elevator_limit,
        require_stability=require_stability,
    )
    return solve_trim(provider, spec)


__all__ = [
    "INFEASIBLE",
    "NOT_CONVERGED",
    "PREFLIGHT_INVALID",
    "TRIMMED",
    "NewtonSettings",
    "TrimResiduals",
    "TrimResult",
    "TrimSolution",
    "TrimSpec",
    "TrimControl",
    "TrimUnknown",
    "TrimVariable",
    "solve_trim",
    "trim_level_flight",
]
