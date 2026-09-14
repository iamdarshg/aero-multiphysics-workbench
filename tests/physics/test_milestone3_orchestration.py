"""Milestone 3: general multiphysics orchestration, field coupling, convergence,
fidelity, and optimization.

Uses simple toy participants plus native benchmark participants (ROSS modal,
PyBaMM SPM). Every number carries source/fidelity/units/validity; missing
native capability fails closed via skip, never via invented values.
"""

from __future__ import annotations

import math
from typing import Any

import pytest
from aeroworkbench_convergence.measures import (
    DEFAULT_MEASURES,
    ClosureMeasure,
    assess_global,
    assess_measure,
    declared_measures,
)
from aeroworkbench_coupling.dag import (
    CHANGE_IMPACT,
    ComputationDAG,
    ContentCache,
    NodeSpec,
)
from aeroworkbench_coupling.field import (
    FieldCoupler,
    SideSpec,
    register_mesh,
    transfer_field,
)
from aeroworkbench_coupling.manifest_coordinator import (
    CoordinatorPolicy,
    CouplingLink,
    ManifestCoordinator,
    ScalarParticipantSpec,
    VariableSpec,
    participant_from_manifest,
)
from aeroworkbench_coupling.policy import expand_coupling_strength
from aeroworkbench_coupling.resonance import (
    ForcingSpectrum,
    ModalSpectrum,
    ResonancePolicy,
    check_resonance,
)
from aeroworkbench_coupling.units import (
    convert_value,
    dimension_of,
    units_compatible,
)
from aeroworkbench_optimization.drivers import (
    DesignVariable,
    OperatingPointEval,
    StudyConstraint,
    StudyObjective,
    pareto_front,
    rank_valid,
    run_doe,
    run_optimize,
    run_sweep,
    study_from_design_state,
)
from aeroworkbench_optimization.planner import (
    FidelityImplementation,
    FidelitySignals,
    plan_fidelity,
)
from aeroworkbench_optimization.quality import (
    PhysicsFlags,
    QualityPolicy,
    assess_sample,
)


def _toy_participants() -> tuple[ScalarParticipantSpec, ScalarParticipantSpec]:
    """Two contractive scalar participants sharing one coupling variable."""

    heater = ScalarParticipantSpec(
        participant_id="heater",
        physics_domain="thermal",
        fidelity="analytical",
        solver_identity="toy",
        solver_version="0.0.0",
        inputs=(VariableSpec("power_w", "W", 100.0),),
        outputs=(VariableSpec("temperature_k", "K", 300.0),),
        function=lambda state: {"temperature_k": 300.0 + 0.05 * state["power_w"]},
    )
    controller = ScalarParticipantSpec(
        participant_id="controller",
        physics_domain="control",
        fidelity="analytical",
        solver_identity="toy",
        solver_version="0.0.0",
        inputs=(VariableSpec("temperature_k", "K", 300.0),),
        outputs=(VariableSpec("power_w", "W", 100.0),),
        function=lambda state: {"power_w": 200.0 - 0.5 * (state["temperature_k"] - 300.0)},
    )
    return heater, controller


def _links() -> tuple[CouplingLink, ...]:
    return (
        CouplingLink("heater", "temperature_k", "controller", "temperature_k"),
        CouplingLink("controller", "power_w", "heater", "power_w"),
    )


# -- A. actual OpenMDAO execution ---------------------------------------------


def test_openmdao_executes_arbitrary_cyclic_graph() -> None:
    heater, controller = _toy_participants()
    coordinator = ManifestCoordinator((heater, controller), _links())
    result = coordinator.solve({})
    assert result.engine == "openmdao"
    assert result.openmdao_version
    assert result.converged
    assert result.iterations >= 1
    assert len(result.history) >= 2
    assert result.history[0].iteration == 0
    values = dict(result.values)
    # Fixed point: T = 300 + 0.05 * P, P = 200 - 0.5 * (T - 300).
    assert values["heater.temperature_k"] == pytest.approx(309.75609, rel=1e-4)
    assert values["controller.power_w"] == pytest.approx(195.12195, rel=1e-4)
    assert values["heater.temperature_k"] == pytest.approx(
        values["controller.temperature_k"], rel=1e-9
    )
    assert result.checkpoint
    assert "NonlinearBlockGS" in result.solver_name or "Newton" in result.solver_name


def test_openmdao_three_participant_cycle_converges() -> None:
    maker = ScalarParticipantSpec(
        participant_id="maker",
        physics_domain="generic",
        fidelity="analytical",
        solver_identity="toy",
        solver_version="0.0.0",
        inputs=(VariableSpec("c", "dimensionless", 0.0),),
        outputs=(VariableSpec("a", "dimensionless", 0.0),),
        function=lambda state: {"a": 0.5 * state["c"] + 1.0},
    )
    middle = ScalarParticipantSpec(
        participant_id="middle",
        physics_domain="generic",
        fidelity="analytical",
        solver_identity="toy",
        solver_version="0.0.0",
        inputs=(VariableSpec("a", "dimensionless", 0.0),),
        outputs=(VariableSpec("b", "dimensionless", 0.0),),
        function=lambda state: {"b": 0.5 * state["a"] + 1.0},
    )
    sink = ScalarParticipantSpec(
        participant_id="sink",
        physics_domain="generic",
        fidelity="analytical",
        solver_identity="toy",
        solver_version="0.0.0",
        inputs=(VariableSpec("b", "dimensionless", 0.0),),
        outputs=(VariableSpec("c", "dimensionless", 0.0),),
        function=lambda state: {"c": 0.5 * state["b"] + 1.0},
    )
    links = (
        CouplingLink("maker", "a", "middle", "a"),
        CouplingLink("middle", "b", "sink", "b"),
        CouplingLink("sink", "c", "maker", "c"),
    )
    result = ManifestCoordinator((maker, middle, sink), links).solve({})
    assert result.converged
    values = dict(result.values)
    # a = b = c = 2 is the unique fixed point.
    assert values["maker.a"] == pytest.approx(2.0, rel=1e-5)
    assert values["middle.b"] == pytest.approx(2.0, rel=1e-5)
    assert values["sink.c"] == pytest.approx(2.0, rel=1e-5)


def test_openmdao_newton_solver_path_executes() -> None:
    heater, controller = _toy_participants()
    policy = CoordinatorPolicy(nonlinear_solver="newton", tolerance=1e-8)
    result = ManifestCoordinator((heater, controller), _links(), policy).solve({})
    assert result.engine == "openmdao"
    assert "Newton" in result.solver_name
    assert result.converged
    assert dict(result.values)["heater.temperature_k"] == pytest.approx(309.75609, rel=1e-4)


def test_coordinator_builds_from_participant_manifest_declarations() -> None:
    from participants.manifest import get_participant

    flow = participant_from_manifest(
        get_participant("incompressible-steady-flow"),
        lambda state: {
            "pressure_drop_pa": 10.0 * state["inlet_velocity_m_s"],
            "continuity_error": 0.0,
        },
    )
    assert flow.participant_id == "incompressible-steady-flow"
    assert flow.solver_identity == "openfoam"
    assert {var.name for var in flow.inputs} == {
        "inlet_velocity_m_s", "outlet_pressure_pa", "density_kg_m3", "viscosity_pa_s",
    }
    with pytest.raises(ValueError, match="NONFLOAT_PORT_NOT_SUPPORTED"):
        participant_from_manifest(
            get_participant("rotor-campbell"), lambda state: {}
        )


def test_shared_design_input_is_promoted_to_both_participants() -> None:
    first = ScalarParticipantSpec(
        participant_id="first",
        physics_domain="generic",
        fidelity="analytical",
        solver_identity="toy",
        solver_version="0.0.0",
        inputs=(VariableSpec("ambient_k", "K", 300.0),),
        outputs=(VariableSpec("a", "dimensionless", 0.0),),
        function=lambda state: {"a": state["ambient_k"] / 100.0},
    )
    second = ScalarParticipantSpec(
        participant_id="second",
        physics_domain="generic",
        fidelity="analytical",
        solver_identity="toy",
        solver_version="0.0.0",
        inputs=(VariableSpec("ambient_k", "K", 300.0),),
        outputs=(VariableSpec("b", "dimensionless", 0.0),),
        function=lambda state: {"b": state["ambient_k"] / 50.0},
    )
    coordinator = ManifestCoordinator((first, second), (), shared=("ambient_k",))
    result = coordinator.solve({"ambient_k": 320.0})
    assert result.converged
    values = dict(result.values)
    assert values["first.a"] == pytest.approx(3.2, rel=1e-9)
    assert values["second.b"] == pytest.approx(6.4, rel=1e-9)


# -- units ---------------------------------------------------------------------


def test_unit_mismatch_is_rejected_before_execution() -> None:
    assert dimension_of("Pa") != dimension_of("m")
    assert units_compatible("mm", "m")
    assert not units_compatible("Pa", "m")
    assert convert_value(1000.0, "mm", "m") == pytest.approx(1.0)
    heater, _ = _toy_participants()
    mismatched = ScalarParticipantSpec(
        participant_id="mismatched",
        physics_domain="generic",
        fidelity="analytical",
        solver_identity="toy",
        solver_version="0.0.0",
        inputs=(VariableSpec("temperature_k", "Pa", 300.0),),
        outputs=(VariableSpec("power_w", "W", 100.0),),
        function=lambda state: {"power_w": 1.0},
    )
    with pytest.raises(ValueError, match="UNIT_MISMATCH"):
        ManifestCoordinator(
            (heater, mismatched),
            (CouplingLink("heater", "temperature_k", "mismatched", "temperature_k"),),
        )


def test_link_with_compatible_units_converts_values() -> None:
    source = ScalarParticipantSpec(
        participant_id="source",
        physics_domain="generic",
        fidelity="analytical",
        solver_identity="toy",
        solver_version="0.0.0",
        inputs=(),
        outputs=(VariableSpec("gap", "mm", 10.0),),
        function=lambda _state: {"gap": 20.0},
    )
    sink = ScalarParticipantSpec(
        participant_id="sink",
        physics_domain="generic",
        fidelity="analytical",
        solver_identity="toy",
        solver_version="0.0.0",
        inputs=(VariableSpec("gap", "m", 0.0),),
        outputs=(VariableSpec("echo", "dimensionless", 0.0),),
        function=lambda state: {"echo": state["gap"] * 1000.0},
    )
    result = ManifestCoordinator(
        (source, sink), (CouplingLink("source", "gap", "sink", "gap"),)
    ).solve({})
    assert result.converged
    assert dict(result.values)["sink.echo"] == pytest.approx(20.0, rel=1e-9)


# -- warm start / checkpoint ----------------------------------------------------


def test_warm_start_is_deterministic() -> None:
    heater, controller = _toy_participants()
    coordinator = ManifestCoordinator((heater, controller), _links())
    first = coordinator.solve({})
    assert first.converged
    checkpoint = coordinator.checkpoint_of(first)
    restarted = coordinator.solve({}, warm_start=checkpoint)
    assert restarted.converged
    # Same fixed point within solver tolerance ...
    assert dict(restarted.values) == pytest.approx(dict(first.values), rel=1e-6)
    # ... and bit-identical replay from the same warm start (deterministic).
    replayed = coordinator.solve({}, warm_start=checkpoint)
    assert dict(replayed.values) == dict(restarted.values)
    assert replayed.history[0].values == restarted.history[0].values
    # Iteration zero of the restart is the checkpoint itself.
    assert dict(restarted.history[0].values) == dict(checkpoint.values)


# -- C. global physical convergence ----------------------------------------------


def test_global_convergence_requires_all_four_gates() -> None:
    temperature = assess_measure(DEFAULT_MEASURES["temperature"], 350.0, 350.0 + 1e-9)
    assert temperature.passed
    blocked = assess_global(
        participants={"heater": True, "controller": True},
        interfaces={"heater<->controller": (1e-9, 1e-6)},
        closures={"temperature": temperature},
        quality={"mesh-sensitivity": True},
    )
    assert blocked.accepted
    energy_failed = assess_measure(DEFAULT_MEASURES["energy"], 100.0, 120.0)
    assert not energy_failed.passed
    denied = assess_global(
        participants={"heater": True, "controller": True},
        interfaces={"heater<->controller": (1e-9, 1e-6)},
        closures={"energy": energy_failed},
        quality={"mesh-sensitivity": True},
    )
    assert not denied.accepted
    assert denied.detail
    partial = assess_global(
        participants={"heater": True, "controller": False},
        interfaces={"heater<->controller": (1e-9, 1e-6)},
        closures={"temperature": temperature},
        quality={"mesh-sensitivity": True},
    )
    assert not partial.accepted


def test_closure_measures_normalize_independently() -> None:
    power = ClosureMeasure("shaft-power", absolute_tolerance=0.5, reference_scale=1000.0)
    length = ClosureMeasure("displacement", absolute_tolerance=1e-4, reference_scale=0.01)
    assert assess_measure(power, 1000.4, 1000.0).passed
    assert not assess_measure(power, 1002.0, 1000.0).passed
    assert assess_measure(length, 0.01005, 0.01).passed
    assert not assess_measure(length, 0.011, 0.01).passed
    assert set(DEFAULT_MEASURES) >= {
        "mass", "energy", "force", "torque", "momentum", "displacement",
        "clearance", "temperature", "heat-flow", "resistance", "voltage",
        "current", "shaft-power", "modes", "critical-speeds",
        "forcing-spectra", "resonance-separation",
    }


def test_energy_closure_failure_blocks_coordinator_acceptance() -> None:
    heater, controller = _toy_participants()
    coordinator = ManifestCoordinator(
        (heater, controller),
        _links(),
        closure=lambda _state: 0.5,
    )
    result = coordinator.solve({})
    assert result.converged is False
    assert "closure" in result.detail


def test_participant_declared_measures_are_validated() -> None:
    assert "torque" in declared_measures(("residual", "continuity", "torque"))
    with pytest.raises(ValueError, match="UNKNOWN_CONVERGENCE_MEASURE"):
        declared_measures(("blade-magic",))


# -- E. coupling-strength policy --------------------------------------------------


def test_coupling_strength_expands_to_persisted_expert_parameters() -> None:
    loose = expand_coupling_strength(0.0)
    tight = expand_coupling_strength(1.0)
    assert loose.nonlinear_tolerance > tight.nonlinear_tolerance
    assert loose.max_iterations <= tight.max_iterations
    assert loose.field_exchange_frequency <= tight.field_exchange_frequency
    assert loose.time_resolution_s >= tight.time_resolution_s
    assert len(loose.digest) == 64
    assert loose.as_dict()["strength"] == 0.0
    with pytest.raises(ValueError, match="INVALID_COUPLING_STRENGTH"):
        expand_coupling_strength(1.5)
    overridden = expand_coupling_strength(0.5, overrides={"max_iterations": 7})
    assert overridden.max_iterations == 7
    assert ("max_iterations", 7) in overridden.overrides_applied


# -- B. computation DAG ------------------------------------------------------------


def _dag_functions() -> dict[str, Any]:
    def geometry(_deps: dict[str, Any]) -> tuple[float, str]:
        return 1.5, "m"

    def mesh(deps: dict[str, Any]) -> tuple[float, str]:
        return deps["geometry"].value * 1000.0, "mm"

    def structural(deps: dict[str, Any]) -> tuple[float, str]:
        return deps["mesh"].value * 2.0, "mm"

    return {"geometry": geometry, "mesh": mesh, "structural": structural}


def _dag_nodes() -> tuple[NodeSpec, ...]:
    return (
        NodeSpec("geometry", "geometry", "geometry", (), ("occ", "2.8.0"), {},
                 ("geometry", "semantic")),
        NodeSpec("mesh", "mesh", "mesh", ("geometry",), ("gmsh", "4.15.2"), {"size": 1.0},
                 ("geometry", "semantic")),
        NodeSpec(
            "structural", "native-analysis", "structural",
            ("mesh",), ("code-aster", "16"), {"load": 1.0},
            ("geometry", "semantic", "material"),
        ),
    )


def test_dag_reuses_cache_and_invalidates_descendants_only() -> None:
    dag = ComputationDAG(_dag_functions())
    for node in _dag_nodes():
        dag.add(node)
    base = {"geometry": "a" * 64, "semantic": "b" * 64, "material": "c" * 64}
    first = dag.execute(base)
    assert all(not receipt.cached for receipt in first.values())
    second = dag.execute(base)
    assert all(receipt.cached for receipt in second.values())
    assert {key: receipt.value for key, receipt in second.items()} == {
        key: receipt.value for key, receipt in first.items()
    }
    # A materials change re-runs mesh + structural descendants (per CHANGE_IMPACT)
    # but reuses the unaffected geometry node.
    third = dag.execute({**base, "material": "d" * 64}, changed_sections=("materials",))
    assert third["geometry"].cached
    assert not third["mesh"].cached
    assert not third["structural"].cached
    # Unknown sections fail closed by invalidating everything.
    fourth = dag.execute(base, changed_sections=("mystery-section",))
    assert all(not receipt.cached for receipt in fourth.values())


def test_dag_change_impact_matches_design_contract() -> None:
    import re
    from pathlib import Path

    design_ts = (
        Path(__file__).parents[2] / "packages" / "schema" / "src" / "design.ts"
    )
    text = design_ts.read_text(encoding="utf-8")
    block = text.split("CHANGE_IMPACT")[1].split("invalidatedNodes")[0]
    ts_sections = set(re.findall(r"^\s*(\w+):", block, flags=re.M))
    assert set(CHANGE_IMPACT) == ts_sections


def test_content_cache_is_immutable() -> None:
    cache: ContentCache[float] = ContentCache()
    cache.put("a" * 64, 1.0)
    assert cache.get("a" * 64) == 1.0
    with pytest.raises(ValueError, match="immutable"):
        cache.put("a" * 64, 2.0)


# -- D. field coupling ---------------------------------------------------------------


def test_field_transfer_conserves_at_two_resolutions() -> None:
    for node_count in (5, 17):
        source = register_mesh(
            f"fluid-{node_count}",
            tuple(i / (node_count - 1) for i in range(node_count)),
        )
        target = register_mesh(
            f"solid-{node_count + 3}",
            tuple(i / (node_count + 2) for i in range(node_count + 3)),
        )
        flux = tuple(100.0 + 50.0 * x for x in source.coordinates)
        receipt = transfer_field(source, flux, target, "heat-flux")
        assert receipt.accepted
        assert receipt.relative_conservation_error <= 1e-9
        temperature = tuple(300.0 + 20.0 * x for x in source.coordinates)
        consistent = transfer_field(source, temperature, target, "temperature")
        assert consistent.accepted


def test_field_checkpoint_rollback_and_native_gate() -> None:
    fluid_mesh = register_mesh("fluid", (0.0, 0.5, 1.0))
    solid_mesh = register_mesh("solid", (0.0, 0.25, 0.5, 0.75, 1.0))
    coupler = FieldCoupler(
        SideSpec("fluid", lambda displacement: {
            "pressure": tuple(1000.0 + 1e4 * d for d in displacement),
        }),
        SideSpec("solid", lambda pressure: {
            "displacement": tuple(1e-4 * p / 1000.0 for p in pressure),
        }),
        fluid_mesh,
        solid_mesh,
        "pressure",
        "displacement",
        tolerance=1e-6,
        max_iterations=30,
    )
    window = coupler.solve(
        tuple(0.0 for _ in fluid_mesh.coordinates),
        tuple(1000.0 for _ in solid_mesh.coordinates),
    )
    assert window.accepted
    assert window.iterations >= 1
    assert window.checkpoints >= 1
    assert window.residual_trace[0] >= window.residual_trace[-1]
    assert window.engine == "analytic-transfer"
    native = FieldCoupler(
        SideSpec("fluid", lambda pressure: {"displacement": pressure}),
        SideSpec("solid", lambda displacement: {"pressure": displacement}),
        fluid_mesh,
        solid_mesh,
        "pressure",
        "displacement",
        engine="precice-native",
    )
    with pytest.raises(Exception, match="CAPABILITY_UNAVAILABLE"):
        native.solve((1.0, 1.0, 1.0), (0.0, 0.0, 0.0, 0.0, 0.0))


def test_native_precice_engine_reports_honest_state() -> None:
    from participants.capabilities import probe_solver

    probe = probe_solver("precice")
    assert probe.state in {"ready", "unavailable"}
    if probe.state != "ready":
        assert "precice" in probe.detail.lower() or "not installed" in probe.detail.lower()


# -- F. fidelity planner --------------------------------------------------------------


def _implementations() -> tuple[FidelityImplementation, ...]:
    return (
        FidelityImplementation("analytical", 0, 1.0, ("screening",)),
        FidelityImplementation("steady-native", 1, 10.0, ("steady",)),
        FidelityImplementation("transient-coupled", 2, 100.0, ("transient", "field-coupled")),
    )


def _signals_with(**overrides: object) -> FidelitySignals:
    base: dict[str, object] = {
        "question": "screening",
        "maturity": 0.2,
        "constraint_margin": 0.5,
        "disagreement": 0.0,
        "sensitivity": 0.0,
        "convergence_difficulty": 0.0,
        "mesh_dependence": 0.0,
        "timestep_dependence": 0.0,
        "resonance_proximity": 1.0,
        "validity_ok": {"analytical": True, "steady-native": True,
                        "transient-coupled": True},
        "cost_budget": 1000.0,
    }
    base.update(overrides)
    return FidelitySignals(**base)  # type: ignore[arg-type]


def _quiet_signals() -> FidelitySignals:
    return _signals_with()


def test_fidelity_escalates_for_explicit_reason_and_not_unnecessarily() -> None:
    implementations = _implementations()
    steady = plan_fidelity("analytical", implementations, _quiet_signals())
    assert steady.level == "analytical"
    assert steady.escalate is False
    assert steady.input_hash
    strained = plan_fidelity(
        "analytical",
        implementations,
        _signals_with(disagreement=0.4),
    )
    assert strained.escalate is True
    assert strained.level == "steady-native"
    assert strained.reasons
    invalid = plan_fidelity(
        "analytical",
        implementations,
        _signals_with(
            validity_ok={"analytical": False, "steady-native": True,
                         "transient-coupled": True}
        ),
    )
    assert invalid.level == "steady-native"
    assert any("validity" in reason for reason in invalid.reasons)


def test_fidelity_never_jumps_to_max_without_cause() -> None:
    decision = plan_fidelity("analytical", _implementations(), _quiet_signals())
    assert decision.level != "transient-coupled"


# -- G/H. DOE and optimization ----------------------------------------------------------


def _paraboloid(
    point: dict[str, float], operating_point: str
) -> tuple[dict[str, float], PhysicsFlags]:
    del operating_point
    x, y = point["x"], point["y"]
    return {"f": (x - 1.0) ** 2 + (y + 2.0) ** 2, "g": x + y}, PhysicsFlags(True, True, True)


def _study_dict() -> dict[str, Any]:
    return {
        "variables": (
            DesignVariable("x", "dimensionless", "continuous", -5.0, 5.0),
            DesignVariable("y", "dimensionless", "continuous", -5.0, 5.0),
        ),
        "objectives": (StudyObjective("f", "minimize", 1.0, "dimensionless"),),
        "constraints": (StudyConstraint("g", "upper", 1.0, "dimensionless"),),
        "operating_points": (OperatingPointEval("nominal", 1.0),),
    }


def test_doe_sweep_operates_with_cache_reuse() -> None:
    study = _study_dict()
    swept = run_sweep(study, _paraboloid, {"x": 3, "y": 3})
    assert len(swept.samples) == 9
    assert swept.engine == "openmdao-compatible"
    assert swept.best is not None
    repeated = run_sweep(study, _paraboloid, {"x": 3, "y": 3})
    assert repeated.cache_hits == 9
    doe = run_doe(study, _paraboloid, method="lhs", n=6, seed=3)
    assert len(doe.samples) == 6
    first_point = dict(doe.samples[0].point)["x"]
    again = run_doe(study, _paraboloid, method="lhs", n=6, seed=3)
    assert dict(again.samples[0].point)["x"] == pytest.approx(first_point)


def test_constrained_optimization_uses_real_driver() -> None:
    study = _study_dict()
    result = run_optimize(study, _paraboloid, driver="slsqp", max_iter=50)
    assert "SLSQP" in result.engine or "slsqp" in result.engine.lower()
    assert result.best is not None
    best = dict(result.best.point)
    assert best["x"] + best["y"] <= 1.0 + 1e-6
    assert result.best.outputs["f"] == pytest.approx(0.0, abs=0.05)
    free = run_optimize(study, _paraboloid, driver="cobyla", max_iter=50)
    assert free.best is not None
    assert free.best.outputs["f"] == pytest.approx(0.0, abs=0.1)


def test_failed_physics_points_are_excluded_from_ranking() -> None:
    def fragile(
        point: dict[str, float], operating_point: str
    ) -> tuple[dict[str, float], PhysicsFlags]:
        del operating_point
        ok = point["x"] >= 0.0
        return {"f": -100.0 if not ok else point["x"]}, PhysicsFlags(
            ok, ok, ok
        )

    study = {
        "variables": (DesignVariable("x", "dimensionless", "continuous", -2.0, 2.0),),
        "objectives": (StudyObjective("f", "minimize", 1.0, "dimensionless"),),
        "constraints": (),
        "operating_points": (OperatingPointEval("nominal", 1.0),),
    }
    result = run_sweep(study, fragile, {"x": 5})
    invalid = [sample for sample in result.samples if sample.state == "invalid-sample"]
    assert invalid
    assert result.best is not None
    assert dict(result.best.point)["x"] >= 0.0
    assert result.best.outputs["f"] == pytest.approx(0.0, abs=1e-9)


def test_study_variables_come_from_design_state_not_solver_code() -> None:
    design_state = {
        "parameters": {"x": {"valueSI": 0.0}, "y": {"valueSI": 0.0}},
        "operatingPoints": [{"name": "nominal", "values": {}}],
        "objectives": [{"name": "f", "target": "minimize", "weight": 1.0,
                        "unit": "dimensionless"}],
        "constraints": [{"name": "g", "bound": "upper", "limitSI": 1.0,
                         "unit": "dimensionless"}],
    }
    study = study_from_design_state(
        design_state,
        (DesignVariable("x", "dimensionless", "continuous", -5.0, 5.0),
         DesignVariable("y", "dimensionless", "continuous", -5.0, 5.0)),
    )
    assert study["objectives"][0].name == "f"
    assert study["constraints"][0].limit == 1.0
    result = run_doe(study, _paraboloid, method="factorial", n=2)
    assert len(result.samples) == 4


def test_pareto_front_keeps_only_nondominated_valid_samples() -> None:
    def two_objective(
        point: dict[str, float], operating_point: str
    ) -> tuple[dict[str, float], PhysicsFlags]:
        del operating_point
        return {"fa": point["x"] ** 2, "fb": (point["x"] - 2.0) ** 2}, PhysicsFlags(
            True, True, True
        )

    study = {
        "variables": (DesignVariable("x", "dimensionless", "continuous", 0.0, 2.0),),
        "objectives": (
            StudyObjective("fa", "minimize", 1.0, "dimensionless"),
            StudyObjective("fb", "minimize", 1.0, "dimensionless"),
        ),
        "constraints": (),
        "operating_points": (OperatingPointEval("nominal", 1.0),),
    }
    result = run_sweep(study, two_objective, {"x": 9})
    front = pareto_front(result.samples, study["objectives"])
    assert len(front) >= 2
    ranked = rank_valid(result.samples, study["objectives"])
    assert ranked[0].outputs["fa"] + ranked[0].outputs["fb"] <= (
        ranked[-1].outputs["fa"] + ranked[-1].outputs["fb"]
    )


def test_quality_policy_marks_mesh_dependent_samples_invalid() -> None:
    policy = QualityPolicy(max_mesh_sensitivity=0.05)
    assert assess_sample(PhysicsFlags(True, True, True, 0.01, 0.0, None), policy).state == "valid"
    verdict = assess_sample(PhysicsFlags(True, True, True, 0.2, 0.0, None), policy)
    assert verdict.state == "invalid-sample"
    assert verdict.reasons


# -- I. resonance in the physics loop -----------------------------------------------------


def test_resonance_proximity_triggers_higher_fidelity() -> None:
    forcing = ForcingSpectrum("flow-participant", "unsteady-pressure", (48.0, 96.0), (1.0, 0.5))
    modal = ModalSpectrum("rotor-participant", "rotordynamic", (50.0, 120.0), (0.02, 0.02))
    policy = ResonancePolicy(
        warning_margin_hz=5.0,
        critical_margin_hz=2.5,
        watch_activate=("harmonic-response",),
        critical_activate=("harmonic-response", "transient-fsi"),
        available=("harmonic-response", "transient-fsi"),
    )
    trigger = check_resonance((forcing,), (modal,), policy)
    assert trigger.state == "triggered"
    assert trigger.min_separation_hz == pytest.approx(2.0)
    assert "harmonic-response" in trigger.activate
    assert trigger.required_capability in {"harmonic", "transient", "field-coupled"}
    clear = check_resonance(
        (ForcingSpectrum("flow-participant", "unsteady-pressure", (10.0,), (1.0,)),),
        (modal,),
        policy,
    )
    assert clear.state == "clear"
    assert clear.activate == ()


def test_resonance_feeds_fidelity_planner() -> None:
    implementations = (
        FidelityImplementation("steady-native", 0, 10.0, ("steady",)),
        FidelityImplementation("harmonic-response", 1, 40.0, ("harmonic",)),
        FidelityImplementation("transient-fsi", 2, 200.0, ("transient", "field-coupled")),
    )
    signals = _signals_with(
        resonance_proximity=0.02, required_capability="harmonic"
    )
    decision = plan_fidelity("steady-native", implementations, signals)
    assert decision.escalate is True
    assert decision.level == "harmonic-response"


# -- native benchmark participants inside orchestration -------------------------------------


def test_native_ross_modal_participates_in_coordinator(tmp_path: Any) -> None:  # noqa: ANN001
    pytest.importorskip("ross")
    from participants.lifecycle import JobState, NativeJobManager
    from ross.rotor import beam_first_critical_rpm

    manager = NativeJobManager(tmp_path / "jobs")
    inputs: dict[str, object] = {
        "analysis": "modal",
        "shaft_length_m": 1.5,
        "shaft_diameter_m": 0.05,
        "n_elements": 4,
        "bearing_stiffness_n_m": 1e8,
        "speed_rpm": 3000.0,
    }
    job_id = manager.submit("rotor-modal", inputs, deferred=True)
    assert manager.run(job_id) == JobState.COMPLETED.value
    envelope = manager.envelope(job_id)
    assert envelope["source"] == "native_solver"
    whirl_hz = envelope["scalars"]["first_whirl_hz"]
    assert math.isfinite(whirl_hz) and whirl_hz > 0
    estimate_rpm = beam_first_critical_rpm(shaft_length_m=1.5, shaft_diameter_m=0.05)
    assert whirl_hz * 60.0 == pytest.approx(estimate_rpm, rel=0.15)
    native_freq = ScalarParticipantSpec(
        participant_id="rotor-modal",
        physics_domain="rotordynamics",
        fidelity="beam-modal",
        solver_identity="ross",
        solver_version=str(envelope["solver_version"]),
        inputs=(),
        outputs=(VariableSpec("first_whirl_hz", "Hz", whirl_hz),),
        function=lambda _state: {"first_whirl_hz": whirl_hz},
    )
    margin = ScalarParticipantSpec(
        participant_id="margin",
        physics_domain="generic",
        fidelity="analytical",
        solver_identity="toy",
        solver_version="0.0.0",
        inputs=(VariableSpec("first_whirl_hz", "Hz", whirl_hz),),
        outputs=(VariableSpec("separation_hz", "Hz", 0.0),),
        function=lambda state: {"separation_hz": abs(state["first_whirl_hz"] - 50.0)},
    )
    result = ManifestCoordinator(
        (native_freq, margin),
        (CouplingLink("rotor-modal", "first_whirl_hz", "margin", "first_whirl_hz"),),
    ).solve({})
    assert result.engine == "openmdao"
    assert result.converged
    assert dict(result.values)["margin.separation_hz"] == pytest.approx(
        abs(whirl_hz - 50.0), rel=1e-9
    )


def test_native_pybamm_cht_conservation_at_two_resolutions(tmp_path: Any) -> None:  # noqa: ANN001
    pytest.importorskip("pybamm")
    from participants.lifecycle import JobState, NativeJobManager

    manager = NativeJobManager(tmp_path / "jobs")
    inputs: dict[str, object] = {
        "model": "spm",
        "parameter_set": "Chen2020",
        "discharge_current_a": 1.0,
        "duration_s": 10.0,
        "n_series": 1,
        "n_parallel": 1,
    }
    job_id = manager.submit("cell-spm-discharge", inputs, deferred=True)
    assert manager.run(job_id) == JobState.COMPLETED.value
    envelope = manager.envelope(job_id)
    assert envelope["source"] == "native_solver"
    delivered_ah = envelope["scalars"]["delivered_ah"]
    assert delivered_ah == pytest.approx(1.0 * 10.0 / 3600.0, rel=0.05)
    heat_w = delivered_ah * 3600.0 / 10.0 * 0.1  # 0.1 V overpotential proxy, labelled
    for node_count in (5, 13):
        hot = register_mesh(
            f"cell-{node_count}",
            tuple(i / (node_count - 1) for i in range(node_count)),
        )
        sink = register_mesh(
            f"plate-{node_count + 2}",
            tuple(i / (node_count + 1) for i in range(node_count + 2)),
        )
        flux = tuple(heat_w * (1.0 + 0.1 * x) for x in hot.coordinates)
        receipt = transfer_field(hot, flux, sink, "heat-flux")
        assert receipt.accepted
        assert receipt.relative_conservation_error <= 1e-9
