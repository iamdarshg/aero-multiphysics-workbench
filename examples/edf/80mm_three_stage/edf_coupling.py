"""Example-level multiphysics coupling through the generic M3 coordinator.

Scalar reconciliation (torque/RPM/power/current/voltage/losses/temperatures)
runs through a real OpenMDAO ``ManifestCoordinator`` over example-level
participant specs -- never a hand-built EDF loop. Field transfer uses the
generic ``transfer_field`` coupler; the preCICE-native path is probed and
recorded fail-closed when the engine is absent.
"""

from __future__ import annotations

import math
from collections.abc import Mapping

from aeroworkbench_coupling.field import (
    TransferReceipt,
    register_mesh,
    transfer_field,
)
from aeroworkbench_coupling.manifest_coordinator import (
    CoordinatorPolicy,
    CoordinatorResult,
    CouplingLink,
    ManifestCoordinator,
    ScalarFunction,
    ScalarParticipantSpec,
    VariableSpec,
)
from aeroworkbench_coupling.resonance import ForcingSpectrum, ModalSpectrum
from edf_config import EDF80Config
from edf_screening import screen_candidate


def _aero_function(config: EDF80Config) -> ScalarFunction:
    def evaluate(state: Mapping[str, float]) -> Mapping[str, float]:
        receipt = screen_candidate(
            config, rpm=state["rpm"], freestream_m_s=0.0
        )
        return {
            "torque_n_m": receipt.outputs["torque_n_m"],
            "shaft_power_w": receipt.outputs["shaft_power_w"],
        }

    return evaluate


def _motor_function(config: EDF80Config) -> ScalarFunction:
    def evaluate(state: Mapping[str, float]) -> Mapping[str, float]:
        omega = state["rpm"] * 2.0 * math.pi / 60.0
        shaft = state["torque_load_n_m"] * omega
        voltage = max(float(state["voltage_v"]), 1.0)
        demand = shaft * (1.0 / config.motor_efficiency + 0.01)
        discriminant = max(voltage**2 - 4.0 * config.esc_resistance_ohm * demand, 0.0)
        current = (voltage - math.sqrt(discriminant)) / (
            2.0 * config.esc_resistance_ohm
        )
        esc_loss = current**2 * config.esc_resistance_ohm + 0.01 * shaft
        electrical = shaft / config.motor_efficiency + esc_loss
        copper = current**2 * config.motor_resistance_ohm
        return {
            "current_a": current,
            "loss_w": copper + 0.02 * shaft,
            "electrical_power_w": electrical,
        }

    return evaluate


def _battery_function(config: EDF80Config) -> ScalarFunction:
    def evaluate(state: Mapping[str, float]) -> Mapping[str, float]:
        current = state["current_a"]
        pack_voltage = config.battery_n_series * 4.0 - current * 0.003 * config.battery_n_series
        soc = 0.8 - current * 60.0 / 3600.0 / 5.0
        return {"pack_voltage_v": pack_voltage, "soc": soc}

    return evaluate


def _thermal_function(config: EDF80Config) -> ScalarFunction:
    _ = config

    def evaluate(state: Mapping[str, float]) -> Mapping[str, float]:
        return {"winding_temp_k": 288.15 + state["loss_w"] * 0.8}

    return evaluate


def build_coordinator(config: EDF80Config) -> ManifestCoordinator:
    """Assemble the example scalar graph from generic coordinator pieces."""

    participants = (
        ScalarParticipantSpec(
            participant_id="aero",
            physics_domain="fluid",
            fidelity="screening-analytic",
            solver_identity="analytic",
            solver_version="example-screening",
            inputs=(VariableSpec("rpm", "rpm", 35000.0),),
            outputs=(
                VariableSpec("torque_n_m", "N.m"),
                VariableSpec("shaft_power_w", "W"),
            ),
            function=_aero_function(config),
        ),
        ScalarParticipantSpec(
            participant_id="motor",
            physics_domain="electromagnetic",
            fidelity="analytic-motor",
            solver_identity="analytic",
            solver_version="example-screening",
            inputs=(
                VariableSpec("torque_load_n_m", "N.m"),
                VariableSpec("rpm", "rpm", 35000.0),
                VariableSpec("voltage_v", "V"),
            ),
            outputs=(
                VariableSpec("current_a", "A"),
                VariableSpec("loss_w", "W"),
                VariableSpec("electrical_power_w", "W"),
            ),
            function=_motor_function(config),
        ),
        ScalarParticipantSpec(
            participant_id="battery",
            physics_domain="electrochemical",
            fidelity="analytic-pack",
            solver_identity="analytic",
            solver_version="example-screening",
            inputs=(VariableSpec("current_a", "A"),),
            outputs=(
                VariableSpec("pack_voltage_v", "V"),
                VariableSpec("soc", "dimensionless"),
            ),
            function=_battery_function(config),
        ),
        ScalarParticipantSpec(
            participant_id="thermal",
            physics_domain="thermal",
            fidelity="analytic-lumped",
            solver_identity="analytic",
            solver_version="example-screening",
            inputs=(VariableSpec("loss_w", "W"),),
            outputs=(VariableSpec("winding_temp_k", "K"),),
            function=_thermal_function(config),
        ),
    )
    links = (
        CouplingLink("aero", "torque_n_m", "motor", "torque_load_n_m"),
        CouplingLink("motor", "current_a", "battery", "current_a"),
        CouplingLink("battery", "pack_voltage_v", "motor", "voltage_v"),
        CouplingLink("motor", "loss_w", "thermal", "loss_w"),
    )

    def closure(state: Mapping[str, float]) -> float:
        # Electrical power balance at the motor terminals (W).
        return float(
            state["motor.current_a"] * state["motor.voltage_v"]
            - state["motor.electrical_power_w"]
        )

    return ManifestCoordinator(
        participants,
        links,
        CoordinatorPolicy(
            nonlinear_solver="block-gs",
            linear_solver="none",
            tolerance=1e-6,
            max_iterations=50,
        ),
        shared=("rpm",),
        closure=closure,
    )


def solve_coupled_system(config: EDF80Config, *, rpm: float) -> CoordinatorResult:
    """Reconcile the coupled EDF state through real OpenMDAO (engine=openmdao)."""

    return build_coordinator(config).solve({"rpm": rpm})


def forcing_spectra(
    *,
    rpm: float,
    blade_counts: tuple[int, ...],
    stator_counts: tuple[int, ...],
) -> tuple[ForcingSpectrum, ...]:
    """Blade-pass forcing lines from arbitrary rotor/stator counts (generic shape)."""

    rev_s = rpm / 60.0
    rotor_lines = tuple(float(count) * rev_s for count in blade_counts)
    interaction = tuple(
        float(blades + stators) * rev_s
        for blades, stators in zip(
            blade_counts, (*stator_counts, stator_counts[-1]), strict=True
        )
    )
    return (
        ForcingSpectrum(
            source="edf-aero",
            label="blade-pass",
            frequencies_hz=rotor_lines,
            amplitudes=tuple(1.0 for _ in rotor_lines),
        ),
        ForcingSpectrum(
            source="edf-aero",
            label="rotor-stator-interaction",
            frequencies_hz=interaction,
            amplitudes=tuple(0.5 for _ in interaction),
        ),
    )


def modal_spectrum(first_whirl_hz: float) -> ModalSpectrum:
    """Modal spectrum from a dynamic participant's first whirl (generic shape)."""

    return ModalSpectrum(
        source="edf-rotor",
        kind="whirl",
        natural_frequencies_hz=(first_whirl_hz, first_whirl_hz * 2.4),
        damping_ratios=(0.02, 0.02),
    )


def aero_structural_transfer() -> TransferReceipt:
    """Analytic-transfer pressure exchange over the generic field coupler."""

    source = register_mesh(
        "aero-outlet-ring",
        (0.014, 0.020, 0.026, 0.032, 0.0395),
    )
    target = register_mesh(
        "blade-ring",
        (0.014, 0.023, 0.032, 0.0395),
    )
    pressures = (1200.0, 1500.0, 1600.0, 1500.0, 1100.0)
    return transfer_field(source, pressures, target, "pressure", tolerance=1e-6)


__all__ = [
    "aero_structural_transfer",
    "build_coordinator",
    "forcing_spectra",
    "modal_spectrum",
    "solve_coupled_system",
]
