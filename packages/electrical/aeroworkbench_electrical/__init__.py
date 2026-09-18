"""Generic electrical-machine and power-electronics participants.

Provides a real fidelity ladder (analytical -> reduced map -> native seam),
immutable parameter/map revisions, material-database-backed properties, an
inverter/ESC loss model whose losses participate in energy closure, and an
OpenMDAO composition that closes machine + drive + battery + thermal loops.
"""

from .composition import (
    BATTERY_PARTICIPANT_ID,
    DRIVE_PARTICIPANT_ID,
    MACHINE_PARTICIPANT_ID,
    THERMAL_PARTICIPANT_ID,
    build_electrical_thermal_coordinator,
    default_initial_state,
    drive_port_function,
    machine_port_function,
    scalar_spec_from_manifest,
    solve_electrical_thermal,
)
from .machine import (
    ElectricalCapabilityUnavailable,
    ElectricalModelError,
    MachineMap,
    MachineResult,
    MapPoint,
    NativeEmStatus,
    build_analytical_map,
    native_em_benchmark_inputs,
    native_em_status,
    solve_machine,
)
from .parameters import (
    DRIVE_REVISIONS,
    MACHINE_REVISIONS,
    UNITS,
    DriveParameters,
    MachineParameters,
    core_loss_w,
    get_drive_parameters,
    get_machine_parameters,
    magnet_remanence,
    material_temperature_coefficient,
    screening_drive_revision,
    screening_machine_revision,
)
from .power_electronics import InverterModelError, InverterResult, solve_inverter
from .validity import FidelityLevel, OutOfEnvelopePolicy, Validity

__all__ = [
    "BATTERY_PARTICIPANT_ID",
    "DRIVE_PARTICIPANT_ID",
    "DRIVE_REVISIONS",
    "DriveParameters",
    "ElectricalCapabilityUnavailable",
    "ElectricalModelError",
    "FidelityLevel",
    "InverterModelError",
    "InverterResult",
    "MACHINE_PARTICIPANT_ID",
    "MACHINE_REVISIONS",
    "MachineMap",
    "MachineParameters",
    "MachineResult",
    "MapPoint",
    "NativeEmStatus",
    "OutOfEnvelopePolicy",
    "THERMAL_PARTICIPANT_ID",
    "UNITS",
    "Validity",
    "build_analytical_map",
    "build_electrical_thermal_coordinator",
    "core_loss_w",
    "default_initial_state",
    "drive_port_function",
    "get_drive_parameters",
    "get_machine_parameters",
    "machine_port_function",
    "magnet_remanence",
    "material_temperature_coefficient",
    "native_em_benchmark_inputs",
    "native_em_status",
    "scalar_spec_from_manifest",
    "screening_drive_revision",
    "screening_machine_revision",
    "solve_electrical_thermal",
    "solve_inverter",
    "solve_machine",
]
