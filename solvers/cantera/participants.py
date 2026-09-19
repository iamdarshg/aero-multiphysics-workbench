"""Governed participant manifest for the Cantera combustion capability.

Registered centrally in ``participants/manifest.py``; defined here so the
contract can be validated and tested without editing the central registry.
"""

from __future__ import annotations

from participants.manifest import (
    MANIFEST_VERSION,
    CheckpointMode,
    ExecutableCapability,
    ParticipantManifest,
    PortSpec,
)

from .case import CANTERA_PARTICIPANT_ID

COMBUSTION_FIDELITY_LEVELS: tuple[str, ...] = (
    "equilibrium",
    "psr",
    "reactor-network",
)


def _scalar(name: str, unit: str, direction: str, data_type: str = "float") -> PortSpec:
    return PortSpec(name, "scalar", data_type, unit, direction)


COMBUSTION_INPUTS: tuple[PortSpec, ...] = (
    _scalar("mechanism", "dimensionless", "in", "string"),
    _scalar("reactor_mode", "dimensionless", "in", "string"),
    _scalar("inlet_temperature_k", "K", "in"),
    _scalar("inlet_pressure_pa", "Pa", "in"),
    _scalar("equivalence_ratio", "dimensionless", "in"),
    _scalar("air_mass_flow_kg_s", "kg/s", "in"),
    _scalar("fuel_mass_flow_kg_s", "kg/s", "in"),
    _scalar("fuel_lower_heating_value_j_kg", "J/kg", "in"),
    _scalar("combustion_efficiency", "dimensionless", "in"),
    _scalar("pressure_loss_fraction", "dimensionless", "in"),
    _scalar("pattern_factor", "dimensionless", "in"),
)

COMBUSTION_OUTPUTS: tuple[PortSpec, ...] = (
    _scalar("exit_total_temperature_k", "K", "out"),
    _scalar("exit_total_pressure_pa", "Pa", "out"),
    _scalar("adiabatic_flame_temperature_k", "K", "out"),
    _scalar("fuel_mass_flow_kg_s", "kg/s", "out"),
    _scalar("heat_release_w", "W", "out"),
    _scalar("combustion_efficiency", "dimensionless", "out"),
    _scalar("pressure_loss_fraction", "dimensionless", "out"),
    _scalar("pattern_factor", "dimensionless", "out"),
    _scalar("residence_time_s", "s", "out"),
    _scalar("stability_indicator", "dimensionless", "out"),
)


def combustion_participant() -> ParticipantManifest:
    """The single governed Cantera combustion participant."""

    return ParticipantManifest(
        participant_id=CANTERA_PARTICIPANT_ID,
        physics_domain="combustion",
        manifest_version=MANIFEST_VERSION,
        description=(
            "Governed Cantera 0D equilibrium / perfectly-stirred / "
            "reactor-network combustion with finite-rate chemistry selection."
        ),
        inputs=COMBUSTION_INPUTS,
        outputs=COMBUSTION_OUTPUTS,
        geometry_roles=(),
        mesh_roles=(),
        semantic_requirements=("combustion_chamber",),
        coupling_direction="one-way",
        convergence_measures=("energy", "species_balance"),
        fidelity_levels=COMBUSTION_FIDELITY_LEVELS,
        executable=ExecutableCapability(
            solver_id="cantera",
            executables=("cantera",),
            execution_mode="in-process",
            run_script=None,
        ),
        prepare_ref="participants.combustion_case:prepare_combustion_case",
        execute_ref="participants.combustion_case:execute_combustion_case",
        parser_ref="participants.combustion_parser:parse_combustion_result",
        validity_ref="participants.combustion_parser:validate_combustion_result",
        artifacts=("case.json", "result.json"),
        checkpoint=False,
        benchmark_ref="turbo08:cantera-ch4-air-hp-equilibrium",
        checkpoint_policy=CheckpointMode.UNSUPPORTED,
    )


def combustion_participants() -> tuple[ParticipantManifest, ...]:
    return (combustion_participant(),)
