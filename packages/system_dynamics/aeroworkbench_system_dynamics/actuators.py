"""Generic actuator dynamics: position/rate limits and first-order lag.

An actuator converts a commanded position into a physically achievable
position under declared lower/upper limits, a maximum slew rate, and an
optional first-order lag. Saturation and rate limiting are reported, and the
result carries full provenance so a control limit can never be silently hidden.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import exp
from typing import Any

from aeroworkbench_core.types import Provenance

from .errors import TransientValidationError
from .provenance import analytical_provenance
from .state import DynamicStateSpec, StateKind, StateVariable
from .units import require_unit
from .validity import Validity, finite

_ASSUMPTIONS = (
    "position limits applied before slew limiting",
    "first-order lag is applied on the position response",
)


@dataclass(frozen=True, slots=True)
class ActuatorResult:
    """One actuator step response with saturation and rate-limit flags."""

    actuator_id: str
    command: float
    position: float
    rate: float
    command_clamped: bool
    rate_limited: bool
    validity: Validity
    provenance: Provenance

    def canonical(self) -> dict[str, Any]:
        return {
            "actuatorId": self.actuator_id,
            "command": self.command,
            "position": self.position,
            "rate": self.rate,
            "commandClamped": self.command_clamped,
            "rateLimited": self.rate_limited,
            "validity": self.validity.as_dict(),
            "provenance": {
                "source": self.provenance.source.value,
                "model": self.provenance.model,
                "inputsHash": self.provenance.inputs_hash,
            },
        }


@dataclass(frozen=True, slots=True)
class ActuatorSpec:
    """A declared actuator with limits, slew rate, and lag."""

    actuator_id: str
    command_name: str
    output_name: str
    unit: str
    lower_limit: float
    upper_limit: float
    max_rate: float
    time_constant_s: float = 0.0
    initial_position: float = 0.0

    def __post_init__(self) -> None:
        if not self.actuator_id.strip() or not self.command_name.strip():
            raise TransientValidationError("actuator identity is required")
        if not self.output_name.strip():
            raise TransientValidationError("actuator.output_name is required")
        require_unit(self.unit)
        finite(self.lower_limit, "actuator.lower_limit")
        finite(self.upper_limit, "actuator.upper_limit")
        if self.lower_limit >= self.upper_limit:
            raise TransientValidationError("actuator limits must be ordered")
        finite(self.max_rate, "actuator.max_rate", positive=True)
        finite(self.time_constant_s, "actuator.time_constant_s", minimum=0.0)
        finite(self.initial_position, "actuator.initial_position")
        if not self.lower_limit <= self.initial_position <= self.upper_limit:
            raise TransientValidationError("actuator.initial_position outside limits")

    def state_variables(self) -> tuple[StateVariable, ...]:
        return (
            StateVariable(
                f"{self.actuator_id}.position",
                self.unit,
                StateKind.ACTUATOR_POSITION,
                self.initial_position,
            ),
            StateVariable(
                f"{self.actuator_id}.rate",
                f"{self.unit}/s",
                StateKind.ACTUATOR_RATE,
                0.0,
            ),
        )

    def state_spec(self) -> DynamicStateSpec:
        return DynamicStateSpec(f"actuator-{self.actuator_id}", self.state_variables())

    def step(self, command: float, *, position: float, dt_s: float) -> ActuatorResult:
        command_value = finite(command, "actuator.command")
        dt = finite(dt_s, "actuator.dt_s", positive=True)
        clamped = min(max(command_value, self.lower_limit), self.upper_limit)
        command_clamped = clamped != command_value
        if self.time_constant_s > 0.0:
            alpha = 1.0 - exp(-dt / self.time_constant_s)
            desired = position + (clamped - position) * alpha
        else:
            desired = clamped
        delta = desired - position
        max_delta = self.max_rate * dt
        rate_limited = abs(delta) > max_delta
        if rate_limited:
            delta = max_delta if delta > 0.0 else -max_delta
        new_position = position + delta
        new_position = min(max(new_position, self.lower_limit), self.upper_limit)
        rate = (new_position - position) / dt
        within = self.lower_limit <= new_position <= self.upper_limit
        validity = Validity(
            passed=within,
            checks={
                "within_limits": within,
                "command_saturated": not command_clamped,
                "rate_within_limit": not rate_limited,
            },
            detail="actuator step evaluated",
        )
        provenance = analytical_provenance(
            "actuator-rate-limit-lag",
            {
                "actuatorId": self.actuator_id,
                "command": command_value,
                "position": position,
                "dtS": dt,
                "lowerLimit": self.lower_limit,
                "upperLimit": self.upper_limit,
                "maxRate": self.max_rate,
                "timeConstantS": self.time_constant_s,
            },
            assumptions=_ASSUMPTIONS,
        )
        return ActuatorResult(
            actuator_id=self.actuator_id,
            command=command_value,
            position=new_position,
            rate=rate,
            command_clamped=command_clamped,
            rate_limited=rate_limited,
            validity=validity,
            provenance=provenance,
        )


__all__ = ["ActuatorResult", "ActuatorSpec"]
