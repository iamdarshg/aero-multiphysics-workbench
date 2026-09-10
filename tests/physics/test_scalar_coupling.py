from __future__ import annotations

from aeroworkbench_convergence import ConvergenceManager
from aeroworkbench_coupling import CouplingParticipant, ScalarCouplingProblem
from aeroworkbench_optimization import select_fidelity


def test_cyclic_motor_thermal_loop_converges_with_visible_strength() -> None:
    problem = ScalarCouplingProblem(
        (
            CouplingParticipant(
                "motor", lambda state: {"temperature": 25 + 0.02 * state["power"]}, ("power",)
            ),
            CouplingParticipant(
                "thermal",
                lambda state: {"power": 120 - 0.5 * (state["temperature"] - 25)},
                ("temperature",),
            ),
        ),
        coupling_strength=0.90,
        energy_closure=lambda state: state["power"] - (120 - 0.5 * (state["temperature"] - 25)),
    )
    result = problem.solve({"temperature": 25.0, "power": 100.0})
    assert result.converged
    assert result.closure.energy_closed
    assert result.checkpoint
    assert result.iterations < 100


def test_residual_convergence_cannot_override_energy_closure() -> None:
    problem = ScalarCouplingProblem(
        (CouplingParticipant("steady", lambda _state: {"power": 10.0}, ("power",)),),
        energy_closure=lambda _state: 0.5,
    )
    result = problem.solve({"power": 10.0})
    assert result.converged is False
    assert result.closure.energy_closed is False
    assert ConvergenceManager().accept({"force": 0.0}, energy_closed=False) is False


def test_fidelity_escalates_after_nonconvergence_or_sensitivity() -> None:
    assert select_fidelity("reduced", converged=False).level == "native"
    decision = select_fidelity("analytical", quality_history=(1.0, 0.8))
    assert decision.escalate
    assert decision.level == "reduced"
