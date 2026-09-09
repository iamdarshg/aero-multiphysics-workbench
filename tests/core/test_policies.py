from __future__ import annotations

import pytest
from aeroworkbench_core.convergence import (
    ConvergenceCriteria,
    ConvergenceSnapshot,
    GlobalConvergenceManager,
)
from aeroworkbench_core.coupling import CouplingPolicy
from aeroworkbench_core.resonance import (
    Excitation,
    Mode,
    ResonanceDetector,
    ResonanceRegime,
)
from aeroworkbench_core.types import FidelityLevel
from pydantic import ValidationError


def test_coupling_strength_maps_monotonically_to_stronger_settings() -> None:
    screening = CouplingPolicy.from_strength(0.0)
    serious = CouplingPolicy.from_strength(0.90)

    assert serious.interface_tolerance < screening.interface_tolerance
    assert serious.max_coupling_iterations > screening.max_coupling_iterations
    assert serious.field_exchange_frequency > screening.field_exchange_frequency
    assert serious.geometry_feedback_interval <= screening.geometry_feedback_interval
    assert serious.dynamic_solver_enabled is True
    assert screening.dynamic_solver_enabled is False


def test_coupling_expert_overrides_are_visible_and_validated() -> None:
    policy = CouplingPolicy.from_strength(
        0.9,
        expert_overrides={"max_coupling_iterations": 160, "interface_tolerance": 5e-7},
    )

    assert policy.expert_overrides == {
        "max_coupling_iterations": 160,
        "interface_tolerance": 5e-7,
    }
    assert policy.max_coupling_iterations == 160
    assert policy.interface_tolerance == 5e-7

    with pytest.raises(ValueError, match="Unknown expert override"):
        CouplingPolicy.from_strength(0.9, expert_overrides={"magic": 1})


def test_coupling_strength_rejects_values_outside_meta_control_range() -> None:
    with pytest.raises(ValidationError):
        CouplingPolicy.from_strength(1.1)


def test_global_convergence_requires_every_relevant_physical_balance() -> None:
    manager = GlobalConvergenceManager(ConvergenceCriteria())
    snapshot = ConvergenceSnapshot(
        numerical_residuals={"cfd": 2e-6, "thermal": 5e-7},
        mass_in_kg_s=1.0,
        mass_out_kg_s=0.9995,
        energy_in_w=1000.0,
        energy_out_w=999.0,
        force_applied_n=100.0,
        force_reaction_n=99.9,
        geometry_change_m=5e-7,
        thermal_change_k=0.02,
        electrical_change_fraction=0.001,
        dynamic_frequency_change_fraction=0.001,
    )

    report = manager.evaluate(snapshot)

    assert report.converged is True
    assert set(report.categories) == {
        "numerical",
        "mass",
        "energy",
        "force",
        "geometry",
        "thermal",
        "electrical",
        "dynamic",
    }
    assert all(category.passed for category in report.categories.values())


def test_global_convergence_reports_energy_failure_despite_small_residuals() -> None:
    snapshot = ConvergenceSnapshot(
        numerical_residuals={"cfd": 1e-8},
        energy_in_w=1000.0,
        energy_out_w=900.0,
    )

    report = GlobalConvergenceManager(ConvergenceCriteria()).evaluate(snapshot)

    assert report.converged is False
    assert report.categories["numerical"].passed is True
    assert report.categories["energy"].passed is False
    assert "energy closure" in report.categories["energy"].message.lower()


def test_resonance_detector_escalates_fidelity_near_blade_passing_mode() -> None:
    report = ResonanceDetector().evaluate(
        excitations=[Excitation(name="blade passing", frequency_hz=800.0)],
        modes=[Mode(name="blade bending 1", frequency_hz=804.0, damping_ratio=0.012)],
        current_fidelity=FidelityLevel.MRF,
    )

    assert report.regime is ResonanceRegime.CRITICAL
    assert report.minimum_separation_fraction == pytest.approx(4 / 804)
    assert report.required_fidelity is FidelityLevel.HARMONIC_RESPONSE
    assert report.escalation_required is True
    assert "within" in report.explanation
    assert "0.50%" in report.explanation


def test_resonance_detector_keeps_fidelity_when_modes_are_well_separated() -> None:
    report = ResonanceDetector().evaluate(
        excitations=[Excitation(name="shaft", frequency_hz=500.0)],
        modes=[Mode(name="shaft bending", frequency_hz=900.0, damping_ratio=0.02)],
        current_fidelity=FidelityLevel.MRF,
    )

    assert report.regime is ResonanceRegime.CLEAR
    assert report.required_fidelity is FidelityLevel.MRF
    assert report.escalation_required is False
