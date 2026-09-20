"""Typed mission state: time, distance, altitude, speed, mass, fuel, energy, thermal.

The integrated core is a flat, unit-bearing mapping so it can be advanced by the
shared deterministic integrator in ``aeroworkbench_system_dynamics``. The full
state adds wall-clock mission time and the cumulative jettisoned mass, both of
which are tracked outside the ODE. Nothing is fabricated: an unconfigured
thermal or battery state simply has a zero derivative.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from .errors import MissionContractError
from .segments import VehicleSpec

INTEGRATED_STATE: tuple[str, ...] = (
    "distance_m",
    "altitude_m",
    "speed_m_s",
    "mass_kg",
    "fuel_kg",
    "battery_soc",
    "thermal_k",
    "stored_energy_consumed_j",
    "propulsive_energy_j",
)


@dataclass(frozen=True, slots=True)
class MissionState:
    """One deterministic point on a mission trajectory."""

    time_s: float
    distance_m: float
    altitude_m: float
    speed_m_s: float
    mass_kg: float
    fuel_kg: float
    battery_soc: float
    thermal_k: float
    stored_energy_consumed_j: float = 0.0
    propulsive_energy_j: float = 0.0
    jettisoned_kg: float = 0.0

    @classmethod
    def initial(cls, vehicle: VehicleSpec) -> MissionState:
        return cls(
            time_s=0.0,
            distance_m=0.0,
            altitude_m=0.0,
            speed_m_s=vehicle.ground_speed_m_s,
            mass_kg=vehicle.initial_mass_kg,
            fuel_kg=vehicle.initial_fuel_kg,
            battery_soc=vehicle.initial_state_of_charge,
            thermal_k=vehicle.initial_thermal_k,
        )

    def core(self) -> dict[str, float]:
        """The integrated state mapping handed to the shared integrator."""

        return {
            "distance_m": self.distance_m,
            "altitude_m": self.altitude_m,
            "speed_m_s": self.speed_m_s,
            "mass_kg": self.mass_kg,
            "fuel_kg": self.fuel_kg,
            "battery_soc": self.battery_soc,
            "thermal_k": self.thermal_k,
            "stored_energy_consumed_j": self.stored_energy_consumed_j,
            "propulsive_energy_j": self.propulsive_energy_j,
        }

    @classmethod
    def from_core(
        cls,
        *,
        time_s: float,
        core: dict[str, float],
        jettisoned_kg: float,
    ) -> MissionState:
        return cls(
            time_s=time_s,
            distance_m=core["distance_m"],
            altitude_m=core["altitude_m"],
            speed_m_s=core["speed_m_s"],
            mass_kg=core["mass_kg"],
            fuel_kg=core["fuel_kg"],
            battery_soc=core["battery_soc"],
            thermal_k=core["thermal_k"],
            stored_energy_consumed_j=core["stored_energy_consumed_j"],
            propulsive_energy_j=core["propulsive_energy_j"],
            jettisoned_kg=jettisoned_kg,
        )

    def stored_energy_j(self, vehicle: VehicleSpec) -> float:
        return self.fuel_kg * vehicle.fuel_lhv_j_kg + self.battery_soc * vehicle.battery_capacity_j

    def specific_energy_j_kg(self, vehicle: VehicleSpec) -> float:
        if self.mass_kg <= 0.0:
            raise MissionContractError("MISSION_STATE_MASS_MUST_BE_POSITIVE")
        return self.stored_energy_j(vehicle) / self.mass_kg

    def jettison(self, amount_kg: float) -> MissionState:
        if amount_kg < 0.0:
            raise MissionContractError("JETTISON_AMOUNT_MUST_BE_NONNEGATIVE")
        if amount_kg > self.mass_kg - self.fuel_kg:
            raise MissionContractError("JETTISON_EXCEEDS_NON_FUEL_MASS")
        return replace(
            self,
            mass_kg=self.mass_kg - amount_kg,
            jettisoned_kg=self.jettisoned_kg + amount_kg,
        )

    def canonical(self) -> dict[str, Any]:
        return {
            "timeS": self.time_s,
            "distanceM": self.distance_m,
            "altitudeM": self.altitude_m,
            "speedMS": self.speed_m_s,
            "massKg": self.mass_kg,
            "fuelKg": self.fuel_kg,
            "batterySoc": self.battery_soc,
            "thermalK": self.thermal_k,
            "storedEnergyConsumedJ": self.stored_energy_consumed_j,
            "propulsiveEnergyJ": self.propulsive_energy_j,
            "jettisonedKg": self.jettisoned_kg,
        }


__all__ = ["INTEGRATED_STATE", "MissionState"]
