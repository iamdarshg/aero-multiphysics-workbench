"""OpenMDAO composition: machine + power-electronics + battery + thermal.

Ports are taken from the registered generic participant manifests; the scalar
coordinator closes bus voltage, current, power, losses, and temperatures as a
real nonlinear OpenMDAO problem. Battery and thermal are generic scalar
participants supplied here as honest analytical placeholders so the loop can be
exercised without any application model.
"""

from __future__ import annotations

from collections.abc import Mapping

from aeroworkbench_coupling.manifest_coordinator import (
    CoordinatorPolicy,
    CoordinatorResult,
    CouplingLink,
    ManifestCoordinator,
    ScalarFunction,
    ScalarParticipantSpec,
    VariableSpec,
)
from participants.manifest import ParticipantManifest, get_participant

from .machine import solve_machine
from .parameters import (
    DriveParameters,
    MachineParameters,
    screening_drive_revision,
    screening_machine_revision,
)
from .power_electronics import solve_inverter

MACHINE_PARTICIPANT_ID = "rotating-electrical-machine"
DRIVE_PARTICIPANT_ID = "power-electronics-drive"
BATTERY_PARTICIPANT_ID = "battery-scalar-pack"
THERMAL_PARTICIPANT_ID = "thermal-scalar-lumped"

_AMBIENT_K = 293.15
_WINDING_RISE_K_PER_W = 0.25
_MAGNET_RISE_K_PER_W = 0.18
_DRIVE_RISE_K_PER_W = 0.40
_BATTERY_CELLS_SERIES = 6
_BATTERY_CELL_OCV_V = 3.8
_BATTERY_PACK_RESISTANCE_OHM = 0.01


def scalar_spec_from_manifest(
    manifest: ParticipantManifest,
    function: ScalarFunction,
    *,
    input_initials: Mapping[str, float] | None = None,
    output_initials: Mapping[str, float] | None = None,
) -> ScalarParticipantSpec:
    """Build a scalar spec from a manifest, binding non-float ports into the function."""

    in_initial = dict(input_initials or {})
    out_initial = dict(output_initials or {})
    inputs: list[VariableSpec] = []
    for port in manifest.inputs:
        if port.kind != "scalar" or port.data_type != "float":
            continue
        inputs.append(VariableSpec(port.name, port.unit, in_initial.get(port.name, 0.0)))
    outputs: list[VariableSpec] = []
    for port in manifest.outputs:
        if port.kind != "scalar":
            continue
        if port.data_type != "float":
            raise ValueError(f"NONFLOAT_OUTPUT_PORT:{manifest.participant_id}:{port.name}")
        outputs.append(VariableSpec(port.name, port.unit, out_initial.get(port.name, 0.0)))
    if not outputs:
        raise ValueError(f"PARTICIPANT_HAS_NO_SCALAR_OUTPUT:{manifest.participant_id}")
    return ScalarParticipantSpec(
        participant_id=manifest.participant_id,
        physics_domain=manifest.physics_domain,
        fidelity=",".join(manifest.fidelity_levels),
        solver_identity=manifest.executable.solver_id,
        solver_version="declared-by-manifest",
        inputs=tuple(inputs),
        outputs=tuple(outputs),
        function=function,
    )


def machine_port_function(parameters: MachineParameters) -> ScalarFunction:
    """Wrap ``solve_machine`` (analytical level) as a manifest-port function."""

    def evaluate(state: Mapping[str, float]) -> Mapping[str, float]:
        result = solve_machine(
            parameters,
            bus_voltage_v=float(state["bus_voltage_v"]),
            speed_rpm=float(state["commanded_speed_rpm"]),
            winding_temp_k=float(state["winding_temp_k"]),
            magnet_temp_k=float(state["magnet_temp_k"]),
        )
        return result.as_scalars()

    return evaluate


def drive_port_function(parameters: DriveParameters) -> ScalarFunction:
    """Wrap ``solve_inverter`` as a manifest-port function."""

    def evaluate(state: Mapping[str, float]) -> Mapping[str, float]:
        result = solve_inverter(
            parameters,
            dc_bus_voltage_v=float(state["dc_bus_voltage_v"]),
            output_power_w=float(state["output_power_w"]),
            switching_frequency_hz=float(state["switching_frequency_hz"]),
            modulation_index=float(state["modulation_index"]),
            case_temp_k=float(state["case_temp_k"]),
        )
        return result.as_scalars()

    return evaluate


def _battery_spec() -> ScalarParticipantSpec:
    def evaluate(state: Mapping[str, float]) -> Mapping[str, float]:
        current = float(state["current_a"])
        voltage = _BATTERY_CELLS_SERIES * _BATTERY_CELL_OCV_V - (
            current * _BATTERY_PACK_RESISTANCE_OHM
        )
        return {"pack_voltage_v": voltage}

    return ScalarParticipantSpec(
        participant_id=BATTERY_PARTICIPANT_ID,
        physics_domain="electrochemical",
        fidelity="analytic-pack",
        solver_identity="analytic",
        solver_version="screening-scalar-pack",
        inputs=(VariableSpec("current_a", "A"),),
        outputs=(VariableSpec("pack_voltage_v", "V", 22.8),),
        function=evaluate,
    )


def _thermal_spec() -> ScalarParticipantSpec:
    def evaluate(state: Mapping[str, float]) -> Mapping[str, float]:
        machine_loss = float(state["machine_loss_w"])
        drive_loss = float(state["drive_loss_w"])
        return {
            "winding_temp_k": _AMBIENT_K + _WINDING_RISE_K_PER_W * machine_loss,
            "magnet_temp_k": _AMBIENT_K + _MAGNET_RISE_K_PER_W * machine_loss,
            "drive_case_temp_k": _AMBIENT_K + _DRIVE_RISE_K_PER_W * drive_loss,
        }

    return ScalarParticipantSpec(
        participant_id=THERMAL_PARTICIPANT_ID,
        physics_domain="thermal",
        fidelity="analytic-lumped",
        solver_identity="analytic",
        solver_version="screening-lumped-network",
        inputs=(VariableSpec("machine_loss_w", "W"), VariableSpec("drive_loss_w", "W")),
        outputs=(
            VariableSpec("winding_temp_k", "K", 380.0),
            VariableSpec("magnet_temp_k", "K", 356.0),
            VariableSpec("drive_case_temp_k", "K", 326.0),
        ),
        function=evaluate,
    )


def build_electrical_thermal_coordinator(
    *,
    machine_parameters: MachineParameters | None = None,
    drive_parameters: DriveParameters | None = None,
    policy: CoordinatorPolicy | None = None,
) -> ManifestCoordinator:
    """Assemble machine + drive + battery + thermal from generic manifests."""

    machine = machine_parameters or screening_machine_revision()
    drive = drive_parameters or screening_drive_revision()
    machine_initials = {
        "speed_rpm": 20000.0,
        "torque_n_m": 0.7,
        "current_a": 84.0,
        "electrical_power_w": 1850.0,
        "mechanical_power_w": 1490.0,
        "copper_loss_w": 353.0,
        "core_loss_w": 0.6,
        "friction_loss_w": 4.2,
        "total_loss_w": 358.0,
        "efficiency": 0.81,
        "heat_load_winding_w": 353.0,
        "heat_load_core_w": 0.6,
        "heat_load_magnet_w": 0.0,
    }
    drive_initials = {
        "motor_voltage_v": 20.0,
        "output_current_a": 90.0,
        "dc_current_a": 85.0,
        "dc_power_w": 1930.0,
        "conduction_loss_w": 49.0,
        "switching_loss_w": 33.0,
        "total_loss_w": 82.0,
        "efficiency": 0.94,
        "junction_temp_k": 390.0,
        "heat_load_w": 82.0,
    }
    participants = (
        scalar_spec_from_manifest(
            get_participant(MACHINE_PARTICIPANT_ID),
            machine_port_function(machine),
            output_initials=machine_initials,
        ),
        scalar_spec_from_manifest(
            get_participant(DRIVE_PARTICIPANT_ID),
            drive_port_function(drive),
            output_initials=drive_initials,
        ),
        _battery_spec(),
        _thermal_spec(),
    )
    links = (
        CouplingLink(
            BATTERY_PARTICIPANT_ID, "pack_voltage_v", MACHINE_PARTICIPANT_ID, "bus_voltage_v"
        ),
        CouplingLink(
            BATTERY_PARTICIPANT_ID,
            "pack_voltage_v",
            DRIVE_PARTICIPANT_ID,
            "dc_bus_voltage_v",
        ),
        CouplingLink(
            MACHINE_PARTICIPANT_ID,
            "electrical_power_w",
            DRIVE_PARTICIPANT_ID,
            "output_power_w",
        ),
        CouplingLink(
            DRIVE_PARTICIPANT_ID, "dc_current_a", BATTERY_PARTICIPANT_ID, "current_a"
        ),
        CouplingLink(
            MACHINE_PARTICIPANT_ID,
            "total_loss_w",
            THERMAL_PARTICIPANT_ID,
            "machine_loss_w",
        ),
        CouplingLink(
            DRIVE_PARTICIPANT_ID, "total_loss_w", THERMAL_PARTICIPANT_ID, "drive_loss_w"
        ),
        CouplingLink(
            THERMAL_PARTICIPANT_ID,
            "winding_temp_k",
            MACHINE_PARTICIPANT_ID,
            "winding_temp_k",
        ),
        CouplingLink(
            THERMAL_PARTICIPANT_ID,
            "magnet_temp_k",
            MACHINE_PARTICIPANT_ID,
            "magnet_temp_k",
        ),
        CouplingLink(
            THERMAL_PARTICIPANT_ID,
            "drive_case_temp_k",
            DRIVE_PARTICIPANT_ID,
            "case_temp_k",
        ),
    )

    def closure(state: Mapping[str, float]) -> float:
        delivered = state[f"{BATTERY_PARTICIPANT_ID}.pack_voltage_v"] * state[
            f"{DRIVE_PARTICIPANT_ID}.dc_current_a"
        ]
        consumed = (
            state[f"{MACHINE_PARTICIPANT_ID}.mechanical_power_w"]
            + state[f"{MACHINE_PARTICIPANT_ID}.total_loss_w"]
            + state[f"{DRIVE_PARTICIPANT_ID}.total_loss_w"]
        )
        return float(delivered - consumed)

    return ManifestCoordinator(
        participants,
        links,
        policy
        or CoordinatorPolicy(
            nonlinear_solver="block-gs",
            linear_solver="none",
            tolerance=1e-6,
            max_iterations=200,
            relaxation=0.8,
        ),
        closure=closure,
    )


def default_initial_state(
    *, speed_rpm: float = 20000.0, load_torque_n_m: float = 0.0
) -> dict[str, float]:
    """Non-driven scalar inputs required by the assembled coordinator."""

    return {
        f"{MACHINE_PARTICIPANT_ID}.commanded_speed_rpm": speed_rpm,
        f"{MACHINE_PARTICIPANT_ID}.load_torque_n_m": load_torque_n_m,
        f"{DRIVE_PARTICIPANT_ID}.switching_frequency_hz": 24000.0,
        f"{DRIVE_PARTICIPANT_ID}.modulation_index": 0.92,
    }


def solve_electrical_thermal(
    *,
    speed_rpm: float = 20000.0,
    load_torque_n_m: float = 0.0,
    machine_parameters: MachineParameters | None = None,
    drive_parameters: DriveParameters | None = None,
    policy: CoordinatorPolicy | None = None,
) -> CoordinatorResult:
    """Run the coupled machine/drive/battery/thermal scalar loop on OpenMDAO."""

    coordinator = build_electrical_thermal_coordinator(
        machine_parameters=machine_parameters, drive_parameters=drive_parameters, policy=policy
    )
    return coordinator.solve(
        default_initial_state(speed_rpm=speed_rpm, load_torque_n_m=load_torque_n_m)
    )


__all__ = [
    "BATTERY_PARTICIPANT_ID",
    "DRIVE_PARTICIPANT_ID",
    "MACHINE_PARTICIPANT_ID",
    "THERMAL_PARTICIPANT_ID",
    "build_electrical_thermal_coordinator",
    "default_initial_state",
    "drive_port_function",
    "machine_port_function",
    "scalar_spec_from_manifest",
    "solve_electrical_thermal",
]
