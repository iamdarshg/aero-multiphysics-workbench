"""Generic controller contracts: schedules, PID, lookup, state machine, filter.

Controllers map measured signals to commands and declare saturation, rate/slew
limits, an anti-windup seam, and sensor filtering/delay. Every controller is
deterministic and resettable so a transient replay is bit-for-bit reproducible.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from math import exp

from .errors import TransientValidationError
from .units import require_unit
from .validity import finite


class Controller(ABC):
    """The generic controller contract: reset plus a measured-to-command update."""

    controller_id: str
    output_name: str
    unit: str

    @abstractmethod
    def reset(self) -> None: ...

    @abstractmethod
    def update(
        self, time_s: float, measured: Mapping[str, float], dt_s: float
    ) -> dict[str, float]: ...


class PIDController(Controller):
    """PID control with saturation, slew limiting, and a back-calculation seam."""

    def __init__(
        self,
        controller_id: str,
        output_name: str,
        *,
        measured_variable: str,
        setpoint: float,
        kp: float,
        ki: float = 0.0,
        kd: float = 0.0,
        unit: str = "1",
        output_min: float | None = None,
        output_max: float | None = None,
        max_rate: float | None = None,
        anti_windup: bool = True,
    ) -> None:
        if not controller_id.strip() or not output_name.strip():
            raise TransientValidationError("pid controller identity is required")
        if not measured_variable.strip():
            raise TransientValidationError("pid measured_variable is required")
        require_unit(unit)
        self.controller_id = controller_id
        self.output_name = output_name
        self.unit = unit
        self.measured_variable = measured_variable
        self.setpoint = finite(setpoint, "pid.setpoint")
        self.kp = finite(kp, "pid.kp")
        self.ki = finite(ki, "pid.ki")
        self.kd = finite(kd, "pid.kd")
        self.output_min = None if output_min is None else finite(output_min, "pid.output_min")
        self.output_max = None if output_max is None else finite(output_max, "pid.output_max")
        if (
            self.output_min is not None
            and self.output_max is not None
            and self.output_min >= self.output_max
        ):
            raise TransientValidationError("pid output limits must be ordered")
        self.max_rate = (
            None if max_rate is None else finite(max_rate, "pid.max_rate", positive=True)
        )
        self.anti_windup = anti_windup
        self.integral = 0.0
        self.saturated = False
        self.anti_windup_active = False
        self.last_output = 0.0
        self._previous_error: float | None = None

    def reset(self) -> None:
        self.integral = 0.0
        self.saturated = False
        self.anti_windup_active = False
        self.last_output = 0.0
        self._previous_error = None

    def update(
        self, time_s: float, measured: Mapping[str, float], dt_s: float
    ) -> dict[str, float]:
        del time_s
        dt = finite(dt_s, "pid.dt_s", positive=True)
        error = self.setpoint - float(measured.get(self.measured_variable, 0.0))
        self.integral += error * dt
        derivative = (
            0.0 if self._previous_error is None else (error - self._previous_error) / dt
        )
        self._previous_error = error
        raw = self.kp * error + self.ki * self.integral + self.kd * derivative
        clamped = raw
        if self.output_min is not None:
            clamped = max(clamped, self.output_min)
        if self.output_max is not None:
            clamped = min(clamped, self.output_max)
        self.saturated = clamped != raw
        self.anti_windup_active = False
        if self.anti_windup and self.saturated and self.ki != 0.0:
            self.integral = (
                clamped - self.kp * error - self.kd * derivative
            ) / self.ki
            self.anti_windup_active = True
        if self.max_rate is not None:
            max_delta = self.max_rate * dt
            delta = clamped - self.last_output
            if delta > max_delta:
                clamped = self.last_output + max_delta
            elif delta < -max_delta:
                clamped = self.last_output - max_delta
        self.last_output = clamped
        return {self.output_name: clamped}


class ScheduleController(Controller):
    """Open-loop time schedule (piecewise linear or step)."""

    def __init__(
        self,
        controller_id: str,
        output_name: str,
        *,
        unit: str,
        points: tuple[tuple[float, float], ...],
        mode: str = "linear",
    ) -> None:
        if not controller_id.strip() or not output_name.strip():
            raise TransientValidationError("schedule controller identity is required")
        if mode not in {"linear", "step"}:
            raise TransientValidationError(f"UNKNOWN_SCHEDULE_MODE:{mode}")
        if not points:
            raise TransientValidationError("schedule.points must not be empty")
        ordered = tuple(sorted(points))
        if len({time for time, _ in ordered}) != len(ordered):
            raise TransientValidationError("schedule.points times must be unique")
        for time, value in ordered:
            finite(time, "schedule.time", minimum=0.0)
            finite(value, "schedule.value")
        require_unit(unit)
        self.controller_id = controller_id
        self.output_name = output_name
        self.unit = unit
        self.mode = mode
        self.points = ordered

    def reset(self) -> None:
        return None

    def update(
        self, time_s: float, measured: Mapping[str, float], dt_s: float
    ) -> dict[str, float]:
        del measured, dt_s
        value = self.evaluate(time_s)
        return {self.output_name: value}

    def evaluate(self, time_s: float) -> float:
        points = self.points
        if time_s <= points[0][0]:
            return points[0][1]
        if time_s >= points[-1][0]:
            return points[-1][1]
        for (earlier_t, earlier_v), (later_t, later_v) in zip(points, points[1:], strict=False):
            if earlier_t <= time_s <= later_t:
                if self.mode == "step":
                    return earlier_v
                span = later_t - earlier_t
                fraction = 0.0 if span == 0.0 else (time_s - earlier_t) / span
                return earlier_v + (later_v - earlier_v) * fraction
        return points[-1][1]


class LookupController(Controller):
    """Table lookup control with linear interpolation and fail-closed bounds."""

    def __init__(
        self,
        controller_id: str,
        output_name: str,
        *,
        input_variable: str,
        unit: str,
        table: tuple[tuple[float, float], ...],
        clamp: bool = True,
    ) -> None:
        if not controller_id.strip() or not output_name.strip():
            raise TransientValidationError("lookup controller identity is required")
        if not input_variable.strip():
            raise TransientValidationError("lookup.input_variable is required")
        if len(table) < 2:
            raise TransientValidationError("lookup.table needs at least two points")
        ordered = tuple(sorted(table))
        for x, y in ordered:
            finite(x, "lookup.x")
            finite(y, "lookup.y")
        if len({x for x, _ in ordered}) != len(ordered):
            raise TransientValidationError("lookup.table inputs must be unique")
        require_unit(unit)
        self.controller_id = controller_id
        self.output_name = output_name
        self.unit = unit
        self.input_variable = input_variable
        self.table = ordered
        self.clamp = clamp

    def reset(self) -> None:
        return None

    def update(
        self, time_s: float, measured: Mapping[str, float], dt_s: float
    ) -> dict[str, float]:
        del time_s, dt_s
        if self.input_variable not in measured:
            raise TransientValidationError(
                f"LOOKUP_INPUT_MISSING:{self.input_variable}"
            )
        x = float(measured[self.input_variable])
        low, high = self.table[0][0], self.table[-1][0]
        if x < low or x > high:
            if not self.clamp:
                raise TransientValidationError(f"LOOKUP_OUT_OF_RANGE:{x}")
            x = min(max(x, low), high)
        return {self.output_name: self._interpolate(x)}

    def _interpolate(self, x: float) -> float:
        points = self.table
        for (x0, y0), (x1, y1) in zip(points, points[1:], strict=False):
            if x0 <= x <= x1:
                if x1 == x0:
                    return y0
                return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
        return points[-1][1]


@dataclass(frozen=True, slots=True)
class StateTransition:
    """One guarded discrete transition between control states."""

    variable: str
    comparator: str
    threshold: float
    target: str

    def __post_init__(self) -> None:
        if self.comparator not in {"gt", "ge", "lt", "le"}:
            raise TransientValidationError(f"UNKNOWN_COMPARATOR:{self.comparator}")
        finite(self.threshold, "transition.threshold")

    def matches(self, measured: Mapping[str, float]) -> bool:
        if self.variable not in measured:
            return False
        value = float(measured[self.variable])
        if self.comparator == "gt":
            return value > self.threshold
        if self.comparator == "ge":
            return value >= self.threshold
        if self.comparator == "lt":
            return value < self.threshold
        return value <= self.threshold


@dataclass(frozen=True, slots=True)
class ControllerState:
    """One discrete control state with its transition guards."""

    name: str
    output: float
    transitions: tuple[StateTransition, ...] = ()

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise TransientValidationError("control state name is required")
        finite(self.output, "control state output")


class StateMachineController(Controller):
    """Discrete state-machine control with guarded transitions."""

    def __init__(
        self,
        controller_id: str,
        output_name: str,
        *,
        unit: str,
        initial_state: str,
        states: tuple[ControllerState, ...],
    ) -> None:
        if not controller_id.strip() or not output_name.strip():
            raise TransientValidationError("state machine identity is required")
        if not states:
            raise TransientValidationError("state machine needs states")
        names = {state.name for state in states}
        if initial_state not in names:
            raise TransientValidationError(f"UNKNOWN_INITIAL_STATE:{initial_state}")
        for state in states:
            for transition in state.transitions:
                if transition.target not in names:
                    raise TransientValidationError(
                        f"UNKNOWN_TRANSITION_TARGET:{transition.target}"
                    )
        require_unit(unit)
        self.controller_id = controller_id
        self.output_name = output_name
        self.unit = unit
        self.initial_state = initial_state
        self.states = states
        self.current_state = initial_state

    def reset(self) -> None:
        self.current_state = self.initial_state

    def update(
        self, time_s: float, measured: Mapping[str, float], dt_s: float
    ) -> dict[str, float]:
        del time_s, dt_s
        state = self._state(self.current_state)
        for transition in state.transitions:
            if transition.matches(measured):
                self.current_state = transition.target
                state = self._state(self.current_state)
                break
        return {self.output_name: state.output}

    def _state(self, name: str) -> ControllerState:
        for state in self.states:
            if state.name == name:
                return state
        raise TransientValidationError(f"UNKNOWN_STATE:{name}")


class FirstOrderSensorFilter(Controller):
    """First-order sensor filtering/delay for a measured signal."""

    def __init__(
        self,
        controller_id: str,
        output_name: str,
        *,
        input_variable: str,
        unit: str,
        time_constant_s: float,
        initial_value: float,
    ) -> None:
        if not controller_id.strip() or not output_name.strip():
            raise TransientValidationError("sensor filter identity is required")
        if not input_variable.strip():
            raise TransientValidationError("sensor filter input_variable is required")
        require_unit(unit)
        self.controller_id = controller_id
        self.output_name = output_name
        self.unit = unit
        self.input_variable = input_variable
        self.time_constant_s = finite(
            time_constant_s, "filter.time_constant_s", positive=True
        )
        self.initial_value = finite(initial_value, "filter.initial_value")
        self.value = self.initial_value

    def reset(self) -> None:
        self.value = self.initial_value

    def update(
        self, time_s: float, measured: Mapping[str, float], dt_s: float
    ) -> dict[str, float]:
        del time_s
        if self.input_variable not in measured:
            raise TransientValidationError(
                f"FILTER_INPUT_MISSING:{self.input_variable}"
            )
        dt = finite(dt_s, "filter.dt_s", positive=True)
        target = float(measured[self.input_variable])
        alpha = 1.0 - exp(-dt / self.time_constant_s)
        self.value += (target - self.value) * alpha
        return {self.output_name: self.value}


__all__ = [
    "Controller",
    "ControllerState",
    "FirstOrderSensorFilter",
    "LookupController",
    "PIDController",
    "ScheduleController",
    "StateMachineController",
    "StateTransition",
]
