"""TURBO 07: rotating-gas fidelity ladder and multidisciplinary promotion policy.

The ladder is physics-derived, the promotion step is measured and explainable,
the multi-physics dependency graph requests only relevant participants, ranking
uses the highest-fidelity trusted evidence (never a stale cheap result), warm
starts obey the existing topology/hash validity rules, and every native rung is
capability-gated and fails closed.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aeroworkbench_core.types import FidelityLevel, Provenance, ResultSource
from aeroworkbench_optimization import StudyObjective
from aeroworkbench_turbomachinery import architecture_from_payload
from aeroworkbench_turbomachinery.fidelity import (
    AnalysisKind,
    ArchitectureFeatures,
    CandidateFidelityLedger,
    CapabilityStatus,
    FidelityEvidence,
    LadderLevel,
    MultiphysicsDependencyGraph,
    NativeCapabilityGate,
    NativeCapabilityState,
    ParticipantGate,
    PromotionSignals,
    RotatingGasFidelityLadder,
    WarmStartAsset,
    WarmStartKey,
    architecture_features,
    default_multiphysics_graph,
    default_rotating_gas_ladder,
    ladder_from_payload,
    plan_promotion,
    plan_warm_start,
    rank_candidates,
    validate_final,
)

_FIXTURES = Path(__file__).resolve().parents[1] / "turbo" / "fidelity"


def _arch(name: str) -> Any:
    return architecture_from_payload(
        json.loads((_FIXTURES / name).read_text(encoding="utf-8"))
    )


def _features(name: str) -> ArchitectureFeatures:
    return architecture_features(_arch(name))


def _native_provenance(model: str) -> Provenance:
    return Provenance(
        source=ResultSource.NATIVE_SOLVER,
        model=model,
        fidelity=FidelityLevel.MRF,
        solver_name=model,
        solver_version="2412",
        run_id="run-0001",
        inputs_hash="a" * 64,
    )


def _ready(capability: str) -> NativeCapabilityGate:
    return NativeCapabilityGate(
        {capability: CapabilityStatus(capability, NativeCapabilityState.READY, "1.0")}
    )


def test_turbo07_ladder_is_complete_ordered_and_hashable() -> None:
    ladder = default_rotating_gas_ladder()
    assert isinstance(ladder, RotatingGasFidelityLadder)
    assert len(ladder.rungs) == 8
    assert [rung.rank for rung in ladder.rungs] == list(range(8))
    assert [rung.level for rung in ladder.rungs] == list(LadderLevel)
    costs = [rung.cost for rung in ladder.rungs]
    assert costs == sorted(costs)
    for rung in ladder.rungs:
        assert rung.analyses
        assert rung.validity_criteria
        if rung.requires_native:
            assert rung.source is ResultSource.NATIVE_SOLVER
            assert rung.native_capabilities
            assert rung.fidelity is not FidelityLevel.ANALYTICAL
        else:
            assert rung.source is ResultSource.ANALYTICAL
            assert not rung.native_capabilities
    assert ladder.digest == default_rotating_gas_ladder().digest
    rebuilt = ladder_from_payload(ladder.canonical())
    assert rebuilt == ladder
    assert rebuilt.digest == ladder.digest
    assert ladder.rung("meanline-screening").level is LadderLevel.MEANLINE_SCREENING
    assert ladder.next_rung("transient-unsteady-cfd").rung_id == "detailed-cht-fsi-reacting"


def test_turbo07_applicability_follows_physics_not_names() -> None:
    ladder = default_rotating_gas_ladder()
    fan = _features("electric_fan.json")
    fan_levels = {rung.level for rung in ladder.applicable(fan)}
    assert LadderLevel.ALGEBRAIC_PREFLIGHT in fan_levels
    assert LadderLevel.MEANLINE_SCREENING in fan_levels
    assert LadderLevel.MESH_INDEPENDENT_STEADY_CFD in fan_levels
    assert LadderLevel.MULTIPHYSICS_VERIFICATION in fan_levels
    assert LadderLevel.TRANSIENT_UNSTEADY_CFD not in fan_levels
    assert LadderLevel.DETAILED_COUPLED not in fan_levels

    unsteady = {
        rung.level
        for rung in ladder.applicable(fan, requested={AnalysisKind.UNSTEADY_CFD.value})
    }
    assert LadderLevel.TRANSIENT_UNSTEADY_CFD in unsteady

    combustion = _features("combustion_turbine.json")
    combustion_levels = {rung.level for rung in ladder.applicable(combustion)}
    assert LadderLevel.DETAILED_COUPLED in combustion_levels
    assert LadderLevel.MULTIPHYSICS_VERIFICATION in combustion_levels


def test_turbo07_dependency_graph_gates_only_relevant_participants() -> None:
    graph = default_multiphysics_graph()
    assert isinstance(graph, MultiphysicsDependencyGraph)
    fan = _features("electric_fan.json")
    required = graph.required_ids(fan)
    assert {"flow", "throughflow", "shaft-load-balance", "electrical", "thermal",
            "structure", "rotordynamics"} <= set(required)
    assert {"battery", "combustion", "acoustics", "field-coupling"}.isdisjoint(required)

    order = graph.topological_order()
    assert order.index("flow") < order.index("throughflow")
    assert order.index("shaft-load-balance") < order.index("electrical")
    assert order.index("electrical") < order.index("battery")
    assert order.index("thermal") < order.index("combustion")
    assert order.index("structure") < order.index("rotordynamics")

    assert "battery" in graph.required_ids(fan, requested={AnalysisKind.BATTERY.value})
    assert "acoustics" not in required
    assert "acoustics" in graph.required_ids(fan, requested={AnalysisKind.ACOUSTICS.value})
    assert "acoustics" in graph.required_ids(
        architecture_features(_arch("electric_fan.json"), acoustics_requested=True)
    )
    assert "field-coupling" not in required
    assert "field-coupling" in graph.required_ids(
        fan,
        requested={
            AnalysisKind.FIELD_COUPLING.value,
            AnalysisKind.THERMAL.value,
            AnalysisKind.STRUCTURAL.value,
        },
    )

    combustion = graph.required_ids(_features("combustion_turbine.json"))
    assert {"combustion", "thermal"} <= set(combustion)
    assert "battery" not in combustion
    assert graph.digest == default_multiphysics_graph().digest
    assert _features("electric_fan.json").digest == _features("electric_fan.json").digest


def test_turbo07_promotion_holds_when_healthy_and_escalates_when_uncertain() -> None:
    ladder = default_rotating_gas_ladder()
    fan = _features("electric_fan.json")
    held = plan_promotion(
        "meanline-screening",
        ladder,
        PromotionSignals(cost_budget=100.0),
        features=fan,
    )
    assert held.escalate is False
    assert held.blocked is False
    assert held.target_rung == "meanline-screening"

    escalated = plan_promotion(
        "meanline-screening",
        ladder,
        PromotionSignals(model_disagreement=0.5, cost_budget=100.0),
        features=fan,
    )
    assert escalated.escalate is True
    assert escalated.target_rung == "throughflow-row-matching"
    assert any("disagreement" in reason for reason in escalated.reasons)

    proximity = plan_promotion(
        "meanline-screening",
        ladder,
        PromotionSignals(choke_stall_surge_proximity=0.05, cost_budget=100.0),
        features=fan,
    )
    assert proximity.escalate is True
    assert any("surge" in reason for reason in proximity.reasons)


def test_turbo07_promotion_fails_closed_when_native_capability_absent() -> None:
    ladder = default_rotating_gas_ladder()
    fan = _features("electric_fan.json")
    signals = PromotionSignals(model_disagreement=0.5, cost_budget=100.0)
    blocked = plan_promotion(
        "throughflow-row-matching",
        ladder,
        signals,
        features=fan,
        capability_gate=NativeCapabilityGate(),
    )
    assert blocked.blocked is True
    assert blocked.escalate is False
    assert blocked.target_rung == "throughflow-row-matching"
    assert blocked.native_gate_ok is False
    assert blocked.blockers == ("NATIVE_CAPABILITY_UNAVAILABLE:openfoam-steady-ras",)

    advanced = plan_promotion(
        "throughflow-row-matching",
        ladder,
        signals,
        features=fan,
        capability_gate=_ready("openfoam-steady-ras"),
    )
    assert advanced.escalate is True
    assert advanced.blocked is False
    assert advanced.target_rung == "coarse-steady-rans-mrf"
    assert advanced.native_gate_ok is True


def test_turbo07_cost_budget_never_buys_an_unaffordable_rung() -> None:
    ladder = default_rotating_gas_ladder()
    fan = _features("electric_fan.json")
    held = plan_promotion(
        "throughflow-row-matching",
        ladder,
        PromotionSignals(model_disagreement=0.5, cost_budget=0.5),
        features=fan,
        capability_gate=_ready("openfoam-steady-ras"),
    )
    assert held.escalate is False
    assert held.target_rung == "throughflow-row-matching"

    blocked = plan_promotion(
        "throughflow-row-matching",
        ladder,
        PromotionSignals(
            model_disagreement=0.5,
            choke_stall_surge_proximity=0.05,
            cost_budget=0.5,
        ),
        features=fan,
        capability_gate=_ready("openfoam-steady-ras"),
    )
    assert blocked.blocked is True
    assert blocked.blockers == ("COST_BUDGET_EXCLUDED:coarse-steady-rans-mrf",)


def test_turbo07_high_fidelity_disagreement_demotes_a_cheap_winner() -> None:
    ledger = CandidateFidelityLedger()
    ledger.record(
        FidelityEvidence("A", "meanline-screening", 1, "analytical", "analytical",
                         (("efficiency", 0.95),))
    )
    ledger.record(
        FidelityEvidence("A", "mesh-independent-steady-cfd", 4, "native_solver", "mrf",
                         (("efficiency", 0.70),), provenance=_native_provenance("openfoam"))
    )
    ledger.record(
        FidelityEvidence("B", "meanline-screening", 1, "analytical", "analytical",
                         (("efficiency", 0.60),))
    )
    ledger.record(
        FidelityEvidence("B", "mesh-independent-steady-cfd", 4, "native_solver", "mrf",
                         (("efficiency", 0.90),), provenance=_native_provenance("openfoam"))
    )
    ledger.record(
        FidelityEvidence("C", "meanline-screening", 1, "analytical", "analytical",
                         (("efficiency", 0.99),), validity_ok=False)
    )
    report = rank_candidates(ledger, (StudyObjective("efficiency", "maximize"),))
    assert [item.candidate_hash for item in report.ranking] == ["B", "A"]
    assert report.demoted == ("A",)
    assert ("C", "no-trusted-valid-evidence") in report.excluded
    disagreement = dict(report.disagreement)
    assert disagreement["A"] > 0.0
    assert disagreement["B"] > 0.0
    assert report.as_dict()["demoted"] == ["A"]


def test_turbo07_warm_start_reuses_only_under_matching_topology_and_hashes() -> None:
    previous = WarmStartKey("topo-1", "geom-1", "mesh-1", "maps-1", "state-1")
    assets = (
        WarmStartAsset("geometry", "geo"),
        WarmStartAsset("mesh", "mesh"),
        WarmStartAsset("map", "map"),
        WarmStartAsset("converged-state", "state"),
    )
    same = WarmStartKey("topo-1", "geom-1", "mesh-1", "maps-1", "state-1")
    reuse = plan_warm_start(previous, same, assets)
    assert reuse.reuse is True
    assert set(reuse.reusable) == {"geometry", "mesh", "map", "converged-state"}

    topology_changed = WarmStartKey("topo-2", "geom-1", "mesh-1", "maps-1", "state-1")
    invalidated = plan_warm_start(previous, topology_changed, assets)
    assert invalidated.reuse is False
    assert all(reason == "field-changed:topology_digest" for _, reason in invalidated.blocked)

    geometry_changed = WarmStartKey("topo-1", "geom-2", "mesh-1", "maps-1", "state-1")
    partial = plan_warm_start(previous, geometry_changed, assets)
    assert partial.reuse is False
    assert partial.reusable == ("map",)
    assert ("mesh", "field-changed:geometry_hash") in partial.blocked
    assert ("converged-state", "field-changed:geometry_hash") in partial.blocked

    stale = plan_warm_start(previous, same, (WarmStartAsset("geometry", "geo", False),))
    assert stale.reuse is False
    assert stale.blocked == (("geometry", "asset-invalid"),)


def test_turbo07_evidence_carries_source_fidelity_validity_and_provenance() -> None:
    provenance = _native_provenance("openfoam")
    evidence = FidelityEvidence(
        "candidate-1",
        "coarse-steady-rans-mrf",
        3,
        "native_solver",
        "mrf",
        (("pressure_ratio", 2.1),),
        provenance=provenance,
    )
    payload = evidence.canonical()
    assert payload["source"] == "native_solver"
    assert payload["fidelity"] == "mrf"
    assert payload["validityOk"] is True
    assert payload["provenance"]["solver_name"] == "openfoam"
    assert payload["provenance"]["run_id"] == "run-0001"
    repeated = FidelityEvidence(
        "candidate-1",
        "coarse-steady-rans-mrf",
        3,
        "native_solver",
        "mrf",
        (("pressure_ratio", 2.1),),
        provenance=provenance,
    )
    assert evidence.digest == repeated.digest


def test_turbo07_final_validation_is_fail_closed_on_native_capability() -> None:
    participant = ParticipantGate("structure", native_capability="code-aster-structural")
    blocked = validate_final("candidate-1", (participant,), capability_gate=NativeCapabilityGate())
    assert blocked.validated_final is False
    assert blocked.status == "incomplete-diagnostic"
    assert any(
        blocker.startswith("required-participant-unavailable") for blocker in blocked.blockers
    )

    ready = validate_final(
        "candidate-1",
        (participant,),
        capability_gate=_ready("code-aster-structural"),
    )
    assert ready.validated_final is True
    assert ready.status == "validated-final"

    analytical = validate_final("candidate-2", (ParticipantGate("flow"),))
    assert analytical.validated_final is True

    independent = validate_final(
        "candidate-3",
        (ParticipantGate("flow"),),
        require_mesh_independence=True,
        require_timestep_independence=True,
    )
    assert independent.validated_final is False
    assert any("mesh-independence-failed" in item for item in independent.blockers)
    assert any("timestep-independence-failed" in item for item in independent.blockers)


def test_turbo07_promotion_is_deterministic_and_explainable() -> None:
    ladder = default_rotating_gas_ladder()
    fan = _features("electric_fan.json")
    signals = PromotionSignals(model_disagreement=0.5, cost_budget=100.0)
    first = plan_promotion(
        "throughflow-row-matching",
        ladder,
        signals,
        features=fan,
        capability_gate=_ready("openfoam-steady-ras"),
    )
    second = plan_promotion(
        "throughflow-row-matching",
        ladder,
        signals,
        features=fan,
        capability_gate=_ready("openfoam-steady-ras"),
    )
    assert first == second
    assert first.signal_digest == second.signal_digest
    assert first.as_dict()["targetRung"] == "coarse-steady-rans-mrf"


def test_turbo07_rung_adapts_to_shared_fidelity_implementation() -> None:
    rung = default_rotating_gas_ladder().rung("coarse-steady-rans-mrf")
    implementation = rung.implementation()
    assert implementation.name == rung.rung_id
    assert implementation.rank == rung.rank
    assert implementation.cost == rung.cost
    assert "steady-cfd" in implementation.capabilities
