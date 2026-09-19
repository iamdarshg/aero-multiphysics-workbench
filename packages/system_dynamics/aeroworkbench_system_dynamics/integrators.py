"""Deterministic fixed-step time integration with an explicit method receipt.

Only declared, deterministic single-step methods are offered (explicit Euler,
Heun/RK2, classic RK4). Inputs are held constant across a macro step (zero-order
hold), which is recorded as an assumption. No random or wall-clock behaviour
enters a result.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from math import ceil

from .errors import TransientValidationError
from .results import IntegratorReceipt
from .validity import finite

DerivativeFn = Callable[[float, Mapping[str, float], Mapping[str, float]], Mapping[str, float]]
InputProvider = Callable[[float], Mapping[str, float]]


class IntegrationMethod(StrEnum):
    """Declared deterministic single-step integration methods."""

    EXPLICIT_EULER = "explicit-euler"
    HEUN = "heun-rk2"
    RUNGE_KUTTA_4 = "runge-kutta-4"


@dataclass(frozen=True, slots=True)
class IntegratorSpec:
    """A declared integrator method and fixed macro step."""

    method: IntegrationMethod
    step_size_s: float

    def __post_init__(self) -> None:
        finite(self.step_size_s, "integrator.step_size_s", positive=True)

    def canonical(self) -> dict[str, str | float]:
        return {"method": self.method.value, "stepSizeS": self.step_size_s}


@dataclass(frozen=True, slots=True)
class IntegrationHistory:
    """Deterministic sampled state history plus its integrator receipt."""

    times_s: tuple[float, ...]
    states: tuple[dict[str, float], ...]
    receipt: IntegratorReceipt


def _checked(
    derivative: DerivativeFn,
    time_s: float,
    state: Mapping[str, float],
    inputs: Mapping[str, float],
) -> dict[str, float]:
    raw = derivative(time_s, state, inputs)
    result: dict[str, float] = {}
    for name in state:
        if name not in raw:
            raise TransientValidationError(f"DERIVATIVE_MISSING_STATE:{name}")
        result[name] = finite(raw[name], f"derivative.{name}")
    return result


def advance(
    derivative: DerivativeFn,
    method: IntegrationMethod,
    time_s: float,
    state: Mapping[str, float],
    dt_s: float,
    inputs: Mapping[str, float],
) -> dict[str, float]:
    """Take one deterministic step of the declared method."""

    if method is IntegrationMethod.EXPLICIT_EULER:
        k1 = _checked(derivative, time_s, state, inputs)
        return {name: state[name] + dt_s * k1[name] for name in state}
    if method is IntegrationMethod.HEUN:
        k1 = _checked(derivative, time_s, state, inputs)
        predictor = {name: state[name] + dt_s * k1[name] for name in state}
        k2 = _checked(derivative, time_s + dt_s, predictor, inputs)
        return {
            name: state[name] + 0.5 * dt_s * (k1[name] + k2[name]) for name in state
        }
    k1 = _checked(derivative, time_s, state, inputs)
    x2 = {name: state[name] + 0.5 * dt_s * k1[name] for name in state}
    k2 = _checked(derivative, time_s + 0.5 * dt_s, x2, inputs)
    x3 = {name: state[name] + 0.5 * dt_s * k2[name] for name in state}
    k3 = _checked(derivative, time_s + 0.5 * dt_s, x3, inputs)
    x4 = {name: state[name] + dt_s * k3[name] for name in state}
    k4 = _checked(derivative, time_s + dt_s, x4, inputs)
    return {
        name: state[name]
        + dt_s / 6.0 * (k1[name] + 2.0 * k2[name] + 2.0 * k3[name] + k4[name])
        for name in state
    }


def integrate_fixed_step(
    derivative: DerivativeFn,
    initial: Mapping[str, float],
    *,
    spec: IntegratorSpec,
    duration_s: float,
    input_provider: InputProvider | None = None,
) -> IntegrationHistory:
    """Integrate a pure ODE from a typed initial state to ``duration_s``."""

    finite(duration_s, "duration_s", positive=True)
    state = {name: finite(value, f"initial.{name}") for name, value in initial.items()}
    if not state:
        raise TransientValidationError("initial state must not be empty")
    steps = max(1, int(ceil(duration_s / spec.step_size_s)))
    times: list[float] = [0.0]
    states: list[dict[str, float]] = [dict(state)]
    time = 0.0
    for _ in range(steps):
        dt = min(spec.step_size_s, duration_s - time)
        inputs = dict(input_provider(time) if input_provider is not None else {})
        state = advance(derivative, spec.method, time, state, dt, inputs)
        time += dt
        times.append(time)
        states.append(dict(state))
    receipt = IntegratorReceipt(
        method=spec.method.value,
        step_size_s=spec.step_size_s,
        steps=steps,
        duration_s=duration_s,
        recorded_points=len(times),
    )
    return IntegrationHistory(tuple(times), tuple(states), receipt)


__all__ = [
    "DerivativeFn",
    "InputProvider",
    "IntegrationHistory",
    "IntegrationMethod",
    "IntegratorSpec",
    "advance",
    "integrate_fixed_step",
]
