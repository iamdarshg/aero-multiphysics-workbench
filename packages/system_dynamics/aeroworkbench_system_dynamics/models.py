"""Generic lumped transient plant models.

These are product-neutral 0-D physical contracts: a rotational-inertia spool, a
lumped thermal capacitance, an isothermal storage volume, a battery state of
charge, a vehicle speed, a first-order lag, and a composite that integrates
several such blocks under one state contract. Each model is deterministic,
declares its typed state, and computes derivatives only from its declared state
and typed inputs.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from .errors import TransientValidationError
from .state import DynamicStateSpec, StateKind, StateVariable
from .validity import finite


class PlantModel(Protocol):
    """A transient plant: typed state plus a deterministic derivative."""

    def state_spec(self) -> DynamicStateSpec: ...

    def derivative(
        self, time_s: float, state: Mapping[str, float], inputs: Mapping[str, float]
    ) -> dict[str, float]: ...

    def outputs(
        self, time_s: float, state: Mapping[str, float], inputs: Mapping[str, float]
    ) -> dict[str, float]: ...


@dataclass(frozen=True, slots=True)
class SpoolModel:
    """Rotational inertia: J domega/dt = torque - load - damping*omega."""

    inertia_kg_m2: float
    damping_n_m_s: float = 0.0
    initial_speed_rad_s: float = 0.0
    variable_inertia: bool = False

    def __post_init__(self) -> None:
        finite(self.inertia_kg_m2, "spool.inertia_kg_m2", positive=True)
        finite(self.damping_n_m_s, "spool.damping_n_m_s", minimum=0.0)
        finite(self.initial_speed_rad_s, "spool.initial_speed_rad_s")

    def state_spec(self) -> DynamicStateSpec:
        variables = [
            StateVariable(
                "shaft_speed_rad_s", "rad/s", StateKind.SHAFT_SPEED, self.initial_speed_rad_s
            )
        ]
        if self.variable_inertia:
            variables.append(
                StateVariable(
                    "inertia_kg_m2",
                    "kg*m2",
                    StateKind.ROTATIONAL_INERTIA,
                    self.inertia_kg_m2,
                )
            )
        return DynamicStateSpec("shaft-spool", tuple(variables))

    def derivative(
        self, time_s: float, state: Mapping[str, float], inputs: Mapping[str, float]
    ) -> dict[str, float]:
        del time_s
        inertia = state.get("inertia_kg_m2", self.inertia_kg_m2)
        if inertia <= 0.0:
            raise TransientValidationError("spool: inertia must stay positive")
        torque = float(inputs.get("shaft_torque_n_m", 0.0))
        load = float(inputs.get("load_torque_n_m", 0.0))
        speed = state["shaft_speed_rad_s"]
        acceleration = (torque - load - self.damping_n_m_s * speed) / inertia
        result = {"shaft_speed_rad_s": acceleration}
        if "inertia_kg_m2" in state:
            result["inertia_kg_m2"] = float(inputs.get("inertia_rate_kg_m2_s", 0.0))
        return result

    def outputs(
        self, time_s: float, state: Mapping[str, float], inputs: Mapping[str, float]
    ) -> dict[str, float]:
        del time_s
        torque = float(inputs.get("shaft_torque_n_m", 0.0))
        load = float(inputs.get("load_torque_n_m", 0.0))
        speed = state["shaft_speed_rad_s"]
        return {
            "shaft_speed_rad_s": speed,
            "shaft_acceleration_rad_s2": (
                torque - load - self.damping_n_m_s * speed
            )
            / state.get("inertia_kg_m2", self.inertia_kg_m2),
        }


@dataclass(frozen=True, slots=True)
class ThermalCapacitanceModel:
    """Lumped capacitance: C dT/dt = heat_in - heat_out - (T - ambient)/R."""

    heat_capacity_j_k: float
    ambient_temperature_k: float
    resistance_k_w: float
    initial_temperature_k: float

    def __post_init__(self) -> None:
        finite(self.heat_capacity_j_k, "thermal.heat_capacity_j_k", positive=True)
        finite(self.ambient_temperature_k, "thermal.ambient_temperature_k")
        finite(self.resistance_k_w, "thermal.resistance_k_w", positive=True)
        finite(self.initial_temperature_k, "thermal.initial_temperature_k")

    def state_spec(self) -> DynamicStateSpec:
        return DynamicStateSpec(
            "thermal-capacitance",
            (
                StateVariable(
                    "temperature_k",
                    "K",
                    StateKind.THERMAL_CAPACITANCE,
                    self.initial_temperature_k,
                ),
            ),
        )

    def derivative(
        self, time_s: float, state: Mapping[str, float], inputs: Mapping[str, float]
    ) -> dict[str, float]:
        del time_s
        heat_in = float(inputs.get("heat_in_w", 0.0))
        heat_out = float(inputs.get("heat_out_w", 0.0))
        temperature = state["temperature_k"]
        rejection = (temperature - self.ambient_temperature_k) / self.resistance_k_w
        return {
            "temperature_k": (heat_in - heat_out - rejection) / self.heat_capacity_j_k
        }

    def outputs(
        self, time_s: float, state: Mapping[str, float], inputs: Mapping[str, float]
    ) -> dict[str, float]:
        del time_s, inputs
        temperature = state["temperature_k"]
        return {
            "temperature_k": temperature,
            "heat_rejection_w": (
                temperature - self.ambient_temperature_k
            )
            / self.resistance_k_w,
        }


@dataclass(frozen=True, slots=True)
class StorageVolumeModel:
    """Isothermal storage volume: dP/dt = gamma*R*T/V * (mdot_in - mdot_out)."""

    volume_m3: float
    gas_constant_j_kg_k: float
    temperature_k: float
    specific_heat_ratio: float
    initial_pressure_pa: float

    def __post_init__(self) -> None:
        finite(self.volume_m3, "storage.volume_m3", positive=True)
        finite(self.gas_constant_j_kg_k, "storage.gas_constant_j_kg_k", positive=True)
        finite(self.temperature_k, "storage.temperature_k", positive=True)
        finite(self.specific_heat_ratio, "storage.specific_heat_ratio", minimum=1.0)
        finite(self.initial_pressure_pa, "storage.initial_pressure_pa", positive=True)

    def state_spec(self) -> DynamicStateSpec:
        return DynamicStateSpec(
            "storage-volume",
            (
                StateVariable(
                    "pressure_pa",
                    "Pa",
                    StateKind.PRESSURE_STORAGE,
                    self.initial_pressure_pa,
                ),
            ),
        )

    def derivative(
        self, time_s: float, state: Mapping[str, float], inputs: Mapping[str, float]
    ) -> dict[str, float]:
        del time_s, state
        coefficient = (
            self.specific_heat_ratio
            * self.gas_constant_j_kg_k
            * self.temperature_k
            / self.volume_m3
        )
        mass_rate = float(inputs.get("mass_flow_in_kg_s", 0.0)) - float(
            inputs.get("mass_flow_out_kg_s", 0.0)
        )
        return {"pressure_pa": coefficient * mass_rate}

    def outputs(
        self, time_s: float, state: Mapping[str, float], inputs: Mapping[str, float]
    ) -> dict[str, float]:
        del time_s
        mass_rate = float(inputs.get("mass_flow_in_kg_s", 0.0)) - float(
            inputs.get("mass_flow_out_kg_s", 0.0)
        )
        return {"pressure_pa": state["pressure_pa"], "net_mass_flow_kg_s": mass_rate}


@dataclass(frozen=True, slots=True)
class BatteryStateOfChargeModel:
    """Coulomb counting: dSOC/dt = -current / capacity."""

    capacity_a_s: float
    initial_state_of_charge: float
    open_circuit_voltage_v: float = 3.8
    internal_resistance_ohm: float = 0.01

    def __post_init__(self) -> None:
        finite(self.capacity_a_s, "battery.capacity_a_s", positive=True)
        finite(self.initial_state_of_charge, "battery.initial_state_of_charge")
        if not 0.0 <= self.initial_state_of_charge <= 1.0:
            raise TransientValidationError(
                "battery.initial_state_of_charge must be within [0, 1]"
            )
        finite(self.open_circuit_voltage_v, "battery.open_circuit_voltage_v", positive=True)
        finite(self.internal_resistance_ohm, "battery.internal_resistance_ohm", minimum=0.0)

    def state_spec(self) -> DynamicStateSpec:
        return DynamicStateSpec(
            "electrical-storage",
            (
                StateVariable(
                    "state_of_charge",
                    "1",
                    StateKind.ELECTRICAL,
                    self.initial_state_of_charge,
                ),
            ),
        )

    def derivative(
        self, time_s: float, state: Mapping[str, float], inputs: Mapping[str, float]
    ) -> dict[str, float]:
        del time_s, state
        current = float(inputs.get("current_a", 0.0))
        return {"state_of_charge": -current / self.capacity_a_s}

    def outputs(
        self, time_s: float, state: Mapping[str, float], inputs: Mapping[str, float]
    ) -> dict[str, float]:
        del time_s
        current = float(inputs.get("current_a", 0.0))
        return {
            "state_of_charge": state["state_of_charge"],
            "pack_voltage_v": self.open_circuit_voltage_v
            - self.internal_resistance_ohm * current,
        }


@dataclass(frozen=True, slots=True)
class VehicleSpeedModel:
    """Point-mass vehicle speed: m dv/dt = thrust - drag."""

    mass_kg: float
    initial_speed_m_s: float = 0.0

    def __post_init__(self) -> None:
        finite(self.mass_kg, "vehicle.mass_kg", positive=True)
        finite(self.initial_speed_m_s, "vehicle.initial_speed_m_s")

    def state_spec(self) -> DynamicStateSpec:
        return DynamicStateSpec(
            "vehicle-speed",
            (StateVariable("speed_m_s", "m/s", StateKind.VEHICLE, self.initial_speed_m_s),),
        )

    def derivative(
        self, time_s: float, state: Mapping[str, float], inputs: Mapping[str, float]
    ) -> dict[str, float]:
        del time_s, state
        thrust = float(inputs.get("thrust_n", 0.0))
        drag = float(inputs.get("drag_n", 0.0))
        return {"speed_m_s": (thrust - drag) / self.mass_kg}

    def outputs(
        self, time_s: float, state: Mapping[str, float], inputs: Mapping[str, float]
    ) -> dict[str, float]:
        del time_s, inputs
        return {"speed_m_s": state["speed_m_s"]}


@dataclass(frozen=True, slots=True)
class FirstOrderLagModel:
    """Generic first-order lag: tau dX/dt = target - X."""

    variable_name: str
    unit: str
    kind: StateKind
    time_constant_s: float
    initial_value: float
    target_input: str

    def __post_init__(self) -> None:
        if not self.variable_name.strip() or not self.target_input.strip():
            raise TransientValidationError("lag variable and target input are required")
        finite(self.time_constant_s, "lag.time_constant_s", positive=True)
        finite(self.initial_value, "lag.initial_value")

    def state_spec(self) -> DynamicStateSpec:
        return DynamicStateSpec(
            "first-order-lag",
            (
                StateVariable(
                    self.variable_name, self.unit, self.kind, self.initial_value
                ),
            ),
        )

    def derivative(
        self, time_s: float, state: Mapping[str, float], inputs: Mapping[str, float]
    ) -> dict[str, float]:
        del time_s
        target = float(inputs.get(self.target_input, 0.0))
        return {
            self.variable_name: (target - state[self.variable_name]) / self.time_constant_s
        }

    def outputs(
        self, time_s: float, state: Mapping[str, float], inputs: Mapping[str, float]
    ) -> dict[str, float]:
        del time_s, inputs
        return {self.variable_name: state[self.variable_name]}


@dataclass(frozen=True, slots=True)
class CompositePlant:
    """Integrate several typed plant blocks under one state contract."""

    plant_id: str
    blocks: tuple[PlantModel, ...]

    def __post_init__(self) -> None:
        if not self.plant_id.strip():
            raise TransientValidationError("composite.plant_id is required")
        if not self.blocks:
            raise TransientValidationError("composite.blocks must not be empty")
        self.state_spec()

    def state_spec(self) -> DynamicStateSpec:
        variables: list[StateVariable] = []
        seen: set[str] = set()
        for block in self.blocks:
            for variable in block.state_spec().variables:
                if variable.name in seen:
                    raise TransientValidationError(
                        f"COMPOSITE_DUPLICATE_STATE:{variable.name}"
                    )
                seen.add(variable.name)
                variables.append(variable)
        return DynamicStateSpec(self.plant_id, tuple(variables))

    def derivative(
        self, time_s: float, state: Mapping[str, float], inputs: Mapping[str, float]
    ) -> dict[str, float]:
        merged: dict[str, float] = {}
        for block in self.blocks:
            for name, value in block.derivative(time_s, state, inputs).items():
                if name in merged:
                    raise TransientValidationError(f"COMPOSITE_DUPLICATE_DERIVATIVE:{name}")
                merged[name] = value
        return merged

    def outputs(
        self, time_s: float, state: Mapping[str, float], inputs: Mapping[str, float]
    ) -> dict[str, float]:
        merged: dict[str, float] = {}
        for block in self.blocks:
            for name, value in block.outputs(time_s, state, inputs).items():
                merged[name] = value
        return merged


__all__ = [
    "BatteryStateOfChargeModel",
    "CompositePlant",
    "FirstOrderLagModel",
    "PlantModel",
    "SpoolModel",
    "StorageVolumeModel",
    "ThermalCapacitanceModel",
    "VehicleSpeedModel",
]
