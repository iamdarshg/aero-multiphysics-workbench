"""Typed dynamic-state declarations for transient system dynamics.

A ``DynamicStateSpec`` is a product-neutral declaration of the continuous
states a participant integrates: shaft/spool speed, rotational inertia,
pressure/flow/temperature storage, electrical/battery state, actuator
position/rate, control state, thermal capacitance, and coupled vehicle or
airflow state. The integrator never invents states; it integrates exactly the
declared typed contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import TransientValidationError
from .units import require_unit
from .validity import finite


class StateKind(StrEnum):
    """The generic physical category of one integrated state variable."""

    SHAFT_SPEED = "shaft-speed"
    ROTATIONAL_INERTIA = "rotational-inertia"
    PRESSURE_STORAGE = "pressure-storage"
    TEMPERATURE_STORAGE = "temperature-storage"
    FLOW_STORAGE = "flow-storage"
    ELECTRICAL = "electrical"
    ACTUATOR_POSITION = "actuator-position"
    ACTUATOR_RATE = "actuator-rate"
    CONTROL = "control"
    THERMAL_CAPACITANCE = "thermal-capacitance"
    VEHICLE = "vehicle"
    AIRFLOW = "airflow"


@dataclass(frozen=True, slots=True)
class StateVariable:
    """One typed, unit-bearing continuous state variable."""

    name: str
    unit: str
    kind: StateKind
    initial: float

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise TransientValidationError("state.variable.name is required")
        require_unit(self.unit)
        finite(self.initial, f"state.{self.name}.initial")

    def canonical(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "unit": self.unit,
            "kind": self.kind.value,
            "initial": self.initial,
        }


@dataclass(frozen=True, slots=True)
class DynamicStateSpec:
    """A deterministic declaration of the integrated continuous state."""

    state_id: str
    variables: tuple[StateVariable, ...]

    def __post_init__(self) -> None:
        if not self.state_id.strip():
            raise TransientValidationError("state.state_id is required")
        if not self.variables:
            raise TransientValidationError("state.variables must not be empty")
        names = [variable.name for variable in self.variables]
        if len(set(names)) != len(names):
            raise TransientValidationError("state.variables must be unique")

    def names(self) -> tuple[str, ...]:
        return tuple(variable.name for variable in self.variables)

    def unit_of(self, name: str) -> str:
        return self.variable(name).unit

    def variable(self, name: str) -> StateVariable:
        for variable in self.variables:
            if variable.name == name:
                return variable
        raise TransientValidationError(f"UNKNOWN_STATE:{name}")

    def by_kind(self, kind: StateKind) -> tuple[StateVariable, ...]:
        return tuple(variable for variable in self.variables if variable.kind is kind)

    def initial(self) -> dict[str, float]:
        return {variable.name: variable.initial for variable in self.variables}

    def canonical(self) -> dict[str, Any]:
        return {
            "stateId": self.state_id,
            "variables": [variable.canonical() for variable in self.variables],
        }


__all__ = ["DynamicStateSpec", "StateKind", "StateVariable"]
