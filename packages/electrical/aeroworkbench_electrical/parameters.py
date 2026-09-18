"""Immutable electrical-machine and power-electronics parameter revisions.

Every constant/map used by the generic machine and drive participants is a
named, content-addressed revision carrying its source, units, and validity
bounds. Revisions never mutate: a new operating model is a new revision label.
Material electrical/magnetic properties (winding temperature coefficient,
magnet remanence, core-loss shape) are read from the shared material database
instead of being re-declared here.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from aeroworkbench_materials import MaterialDatabase

UNITS: dict[str, str] = {
    "bus_voltage_v": "V",
    "dc_bus_voltage_v": "V",
    "motor_voltage_v": "V",
    "commanded_speed_rpm": "rpm",
    "speed_rpm": "rpm",
    "load_torque_n_m": "N.m",
    "torque_n_m": "N.m",
    "current_a": "A",
    "output_current_a": "A",
    "dc_current_a": "A",
    "electrical_power_w": "W",
    "mechanical_power_w": "W",
    "output_power_w": "W",
    "dc_power_w": "W",
    "copper_loss_w": "W",
    "core_loss_w": "W",
    "friction_loss_w": "W",
    "conduction_loss_w": "W",
    "switching_loss_w": "W",
    "total_loss_w": "W",
    "heat_load_w": "W",
    "heat_load_winding_w": "W",
    "heat_load_core_w": "W",
    "heat_load_magnet_w": "W",
    "winding_temp_k": "K",
    "magnet_temp_k": "K",
    "case_temp_k": "K",
    "junction_temp_k": "K",
    "switching_frequency_hz": "Hz",
    "modulation_index": "dimensionless",
    "efficiency": "dimensionless",
}

_REFERENCE_TEMPERATURE_K = 293.15


def _digest(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _check_bounds(low: float, high: float, label: str) -> None:
    if not low < high:
        raise ValueError(f"INVALID_VALIDITY_BOUNDS:{label}")


@dataclass(frozen=True, slots=True)
class MachineParameters:
    """One immutable revision of a generic lumped electrical machine model."""

    revision: str
    source: str
    torque_constant_n_m_per_a: float
    winding_resistance_ohm: float
    back_emf_constant_v_s_per_rad: float | None = None
    reference_temperature_k: float = _REFERENCE_TEMPERATURE_K
    pole_pairs: int = 1
    core_mass_kg: float = 0.0
    friction_torque_n_m: float = 0.0
    magnet_derate_per_k: float = -0.0011
    winding_material_id: str = "copper-etp"
    magnet_material_id: str = "ndfeb-n42"
    core_material_id: str = "ndfeb-n42"
    max_current_a: float = 200.0
    max_speed_rpm: float = 60000.0
    min_speed_rpm: float = 0.0
    min_winding_temp_k: float = 253.15
    max_winding_temp_k: float = 453.15
    min_magnet_temp_k: float = 253.15
    max_magnet_temp_k: float = 453.15
    note: str = ""

    def __post_init__(self) -> None:
        if not self.revision.strip() or not self.source.strip():
            raise ValueError("MACHINE_REVISION_AND_SOURCE_REQUIRED")
        if self.torque_constant_n_m_per_a <= 0:
            raise ValueError("MACHINE_TORQUE_CONSTANT_MUST_BE_POSITIVE")
        if self.winding_resistance_ohm <= 0:
            raise ValueError("MACHINE_RESISTANCE_MUST_BE_POSITIVE")
        if self.pole_pairs < 1:
            raise ValueError("MACHINE_POLE_PAIRS_MUST_BE_AT_LEAST_ONE")
        if self.core_mass_kg < 0 or self.friction_torque_n_m < 0:
            raise ValueError("MACHINE_LOSS_TERMS_MUST_BE_NONNEGATIVE")
        _check_bounds(self.min_speed_rpm, self.max_speed_rpm, "machine_speed")
        _check_bounds(self.min_winding_temp_k, self.max_winding_temp_k, "winding_temp")
        _check_bounds(self.min_magnet_temp_k, self.max_magnet_temp_k, "magnet_temp")

    @property
    def back_emf_constant(self) -> float:
        if self.back_emf_constant_v_s_per_rad is None:
            return self.torque_constant_n_m_per_a
        return self.back_emf_constant_v_s_per_rad

    def winding_resistance_at(
        self, temperature_k: float, database: MaterialDatabase | None = None
    ) -> float:
        """Temperature-corrected winding resistance from the material database."""

        alpha = material_temperature_coefficient(
            self.winding_material_id, database
        )
        return self.winding_resistance_ohm * (
            1.0 + alpha * (temperature_k - self.reference_temperature_k)
        )

    def torque_constant_at(self, magnet_temp_k: float) -> float:
        """Temperature-derated torque constant (reversible magnet derating)."""

        factor = 1.0 + self.magnet_derate_per_k * (
            magnet_temp_k - self.reference_temperature_k
        )
        if factor <= 0.0:
            raise ValueError("MACHINE_MAGNET_DERATE_INVALID")
        return self.torque_constant_n_m_per_a * factor

    def back_emf_at(self, magnet_temp_k: float) -> float:
        factor = 1.0 + self.magnet_derate_per_k * (
            magnet_temp_k - self.reference_temperature_k
        )
        if factor <= 0.0:
            raise ValueError("MACHINE_MAGNET_DERATE_INVALID")
        return self.back_emf_constant * factor

    def core_loss_w_at(
        self, speed_rpm: float, database: MaterialDatabase | None = None
    ) -> float:
        """Core loss from the core material's frequency loss table (W)."""

        if self.core_mass_kg <= 0.0:
            return 0.0
        frequency_hz = self.pole_pairs * speed_rpm / 60.0
        return core_loss_w(
            self.core_material_id, frequency_hz=frequency_hz, mass_kg=self.core_mass_kg,
            database=database,
        )

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "kind": "machine-parameters",
            "revision": self.revision,
            "source": self.source,
            "torqueConstantNmPerA": self.torque_constant_n_m_per_a,
            "windingResistanceOhm": self.winding_resistance_ohm,
            "backEmfConstantVSPerRad": self.back_emf_constant,
            "referenceTemperatureK": self.reference_temperature_k,
            "polePairs": self.pole_pairs,
            "coreMassKg": self.core_mass_kg,
            "frictionTorqueNm": self.friction_torque_n_m,
            "magnetDeratePerK": self.magnet_derate_per_k,
            "windingMaterialId": self.winding_material_id,
            "magnetMaterialId": self.magnet_material_id,
            "coreMaterialId": self.core_material_id,
            "maxCurrentA": self.max_current_a,
            "maxSpeedRpm": self.max_speed_rpm,
            "minSpeedRpm": self.min_speed_rpm,
            "minWindingTempK": self.min_winding_temp_k,
            "maxWindingTempK": self.max_winding_temp_k,
            "minMagnetTempK": self.min_magnet_temp_k,
            "maxMagnetTempK": self.max_magnet_temp_k,
            "note": self.note,
        }

    def digest(self) -> str:
        return _digest(self.canonical_payload())


@dataclass(frozen=True, slots=True)
class DriveParameters:
    """One immutable revision of a generic inverter/ESC loss model."""

    revision: str
    source: str
    conduction_resistance_ohm: float
    switching_energy_j_per_a: float
    thermal_resistance_k_per_w: float
    si_temperature_coefficient_per_k: float = 0.004
    reference_temperature_k: float = 298.15
    min_dc_bus_v: float = 6.0
    max_dc_bus_v: float = 60.0
    max_output_power_w: float = 50000.0
    max_modulation_index: float = 0.98
    min_case_temp_k: float = 233.15
    max_case_temp_k: float = 358.15
    max_junction_temp_k: float = 423.15
    note: str = ""

    def __post_init__(self) -> None:
        if not self.revision.strip() or not self.source.strip():
            raise ValueError("DRIVE_REVISION_AND_SOURCE_REQUIRED")
        if self.conduction_resistance_ohm < 0:
            raise ValueError("DRIVE_CONDUCTION_RESISTANCE_MUST_BE_NONNEGATIVE")
        if self.switching_energy_j_per_a < 0:
            raise ValueError("DRIVE_SWITCHING_ENERGY_MUST_BE_NONNEGATIVE")
        if self.thermal_resistance_k_per_w <= 0:
            raise ValueError("DRIVE_THERMAL_RESISTANCE_MUST_BE_POSITIVE")
        _check_bounds(self.min_dc_bus_v, self.max_dc_bus_v, "drive_dc_bus")
        _check_bounds(self.min_case_temp_k, self.max_case_temp_k, "drive_case_temp")
        if not 0.0 < self.max_modulation_index <= 1.0:
            raise ValueError("DRIVE_MODULATION_LIMIT_INVALID")

    def conduction_resistance_at(self, junction_temp_k: float) -> float:
        return self.conduction_resistance_ohm * (
            1.0 + self.si_temperature_coefficient_per_k
            * (junction_temp_k - self.reference_temperature_k)
        )

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "kind": "drive-parameters",
            "revision": self.revision,
            "source": self.source,
            "conductionResistanceOhm": self.conduction_resistance_ohm,
            "switchingEnergyJPerA": self.switching_energy_j_per_a,
            "thermalResistanceKPerW": self.thermal_resistance_k_per_w,
            "siTemperatureCoefficientPerK": self.si_temperature_coefficient_per_k,
            "referenceTemperatureK": self.reference_temperature_k,
            "minDcBusV": self.min_dc_bus_v,
            "maxDcBusV": self.max_dc_bus_v,
            "maxOutputPowerW": self.max_output_power_w,
            "maxModulationIndex": self.max_modulation_index,
            "minCaseTempK": self.min_case_temp_k,
            "maxCaseTempK": self.max_case_temp_k,
            "maxJunctionTempK": self.max_junction_temp_k,
            "note": self.note,
        }

    def digest(self) -> str:
        return _digest(self.canonical_payload())


def _database(database: MaterialDatabase | None) -> MaterialDatabase:
    return database if database is not None else MaterialDatabase.seeded()


def material_temperature_coefficient(
    material_id: str, database: MaterialDatabase | None = None
) -> float:
    """Winding resistivity temperature coefficient from the material database."""

    material = _database(database).get_material(material_id)
    try:
        return float(material.evaluate("temperature_coefficient"))
    except KeyError as exc:  # pragma: no cover - guarded by seeded database
        raise ValueError(f"MATERIAL_LACKS_TEMPERATURE_COEFFICIENT:{material_id}") from exc


def core_loss_w(
    material_id: str,
    *,
    frequency_hz: float,
    mass_kg: float,
    database: MaterialDatabase | None = None,
) -> float:
    """Core loss (W) from a core material's frequency loss table (W/kg)."""

    material = _database(database).get_material(material_id)
    try:
        specific_loss = material.evaluate("core_loss", frequency_hz=frequency_hz)
    except KeyError as exc:
        raise ValueError(f"MATERIAL_LACKS_CORE_LOSS:{material_id}") from exc
    return specific_loss * mass_kg


def magnet_remanence(material_id: str, database: MaterialDatabase | None = None) -> float:
    """Magnet remanence (T) from the material database."""

    material = _database(database).get_material(material_id)
    try:
        return float(material.evaluate("remanence"))
    except KeyError as exc:
        raise ValueError(f"MATERIAL_LACKS_REMANENCE:{material_id}") from exc


def screening_machine_revision() -> MachineParameters:
    """Default generic machine revision used when none is supplied."""

    return MachineParameters(
        revision="screening-r1",
        source="generic PM machine screening constants; verify before certification",
        torque_constant_n_m_per_a=0.0085,
        winding_resistance_ohm=0.05,
        pole_pairs=2,
        core_mass_kg=0.05,
        friction_torque_n_m=0.002,
        magnet_derate_per_k=-0.0011,
        note="Kv ~ 1126 rpm/V; NdFeB reversible magnet derating",
    )


def screening_drive_revision() -> DriveParameters:
    """Default generic inverter/ESC revision used when none is supplied."""

    return DriveParameters(
        revision="screening-r1",
        source="generic MOSFET inverter screening losses; verify before certification",
        conduction_resistance_ohm=0.006,
        switching_energy_j_per_a=1.5e-5,
        thermal_resistance_k_per_w=0.8,
        note="3-phase effective conduction resistance and per-amp switching energy",
    )


MACHINE_REVISIONS: dict[str, MachineParameters] = {
    screening_machine_revision().revision: screening_machine_revision()
}
DRIVE_REVISIONS: dict[str, DriveParameters] = {
    screening_drive_revision().revision: screening_drive_revision()
}


def get_machine_parameters(revision: str) -> MachineParameters:
    try:
        return MACHINE_REVISIONS[revision]
    except KeyError:
        raise ValueError(f"UNKNOWN_MACHINE_REVISION:{revision}") from None


def get_drive_parameters(revision: str) -> DriveParameters:
    try:
        return DRIVE_REVISIONS[revision]
    except KeyError:
        raise ValueError(f"UNKNOWN_DRIVE_REVISION:{revision}") from None


__all__ = [
    "DRIVE_REVISIONS",
    "DriveParameters",
    "MACHINE_REVISIONS",
    "MachineParameters",
    "UNITS",
    "core_loss_w",
    "get_drive_parameters",
    "get_machine_parameters",
    "magnet_remanence",
    "material_temperature_coefficient",
    "screening_drive_revision",
    "screening_machine_revision",
]
