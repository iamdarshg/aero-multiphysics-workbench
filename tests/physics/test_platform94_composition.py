import json
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest
from aeroworkbench_core import assembly as asm
from aeroworkbench_core import composition as comp
from aeroworkbench_core import physical
from aeroworkbench_coupling import field, resonance
from aeroworkbench_coupling import hierarchy as hier

_FIXTURE_PATH = Path(__file__).resolve().parents[1] / "platform" / "composition" / "fixtures.py"
_spec = spec_from_file_location("platform94_fixtures", _FIXTURE_PATH)
assert _spec is not None and _spec.loader is not None
fixtures = module_from_spec(_spec)
_spec.loader.exec_module(fixtures)

HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _child(result: hier.HierarchicalResult, system_id: str) -> hier.HierarchicalResult:
    for node in result.children:
        if node.system_id == system_id:
            return node
    raise AssertionError(f"missing child {system_id}")


def test_platform94_mechanical_hierarchy_composes() -> None:
    record, models, boundary = fixtures.build_mechanical()
    assert record.depth == 2
    assert [leaf.system_id for leaf in record.leaves()] == ["compA", "compB"]
    assert record.mass is not None and record.mass.mass_kg == pytest.approx(5.0)
    assert record.mass.cg_m[0] == pytest.approx(0.6)
    assert record.mass.inertia_kgm2 == pytest.approx((0.3, 1.5, 1.5))
    result = hier.HierarchicalSimulator(record, models).evaluate(boundary)
    assert result.status == "converged"
    assert result.values["result_disp"] == pytest.approx(2.0)
    assert _child(result, "compA").values["force_out"] == pytest.approx(10.0)
    assert result.receipts
    assert any("compA.force_out->compB.force_in" in receipt for receipt in result.receipts)


def test_platform94_propulsion_power_chain_closes() -> None:
    record, models, boundary = fixtures.build_propulsion()
    result = hier.HierarchicalSimulator(record, models).evaluate(boundary)
    assert result.status == "converged"
    assert result.values["thrust"] == pytest.approx(360.0)
    motor = _child(result, "motor")
    assert motor.values["shaft_out"] == pytest.approx(900.0)
    assert motor.values["heat_out"] == pytest.approx(100.0)
    source_power = _child(result, "source").values["power_out"]
    assert field.power_closure(None, source_power, motor.values["shaft_out"],
                               loss_w=motor.values["heat_out"]).accepted
    assert result.validity_passed


def test_platform94_aircraft_two_way_coupling_and_retrim() -> None:
    record, models, boundary = fixtures.build_aircraft()
    assert record.depth == 3
    simulator = hier.HierarchicalSimulator(record, models)
    result = simulator.evaluate(boundary)
    assert result.status == "converged"
    airframe = _child(result, "airframe")
    controls = _child(result, "controls")
    propulsion = _child(result, "propulsion")
    assert airframe.values["lift_resid_out"] == pytest.approx(0.0, abs=1e-6)
    assert airframe.values["thrust_resid_out"] == pytest.approx(0.0, abs=1e-6)
    assert airframe.values["lift_out"] == pytest.approx(98.1, abs=1e-4)
    assert airframe.values["inlet_out"] < boundary["freestream_ms"]
    assert propulsion.values["wake_out"] == pytest.approx(0.28763, abs=1e-4)
    assert any("wake_out->airframe.wake_in" in receipt for receipt in result.receipts)
    assert 20.0 < airframe.values["moment_out"] < 45.0
    assert propulsion.values["thrust_out"] == pytest.approx(airframe.values["drag_out"],
                                                            abs=1e-6)
    assert len(result.receipts) >= 6
    first_attitude = controls.values["attitude_out"]
    retrims = simulator.evaluate({"freestream_ms": 32.0, "weight_N": 120.0})
    assert retrims.status == "converged"
    assert retrims.values["lift_out"] == pytest.approx(120.0, abs=1e-4)
    assert retrims.values["lift_out"] != pytest.approx(result.values["lift_out"])
    assert _child(retrims, "controls").values["attitude_out"] != pytest.approx(first_attitude)
    assert retrims.cache_reason == "warm_start"


def test_platform94_serialization_hashing_and_depth() -> None:
    record, models, boundary = fixtures.build_mechanical()
    clone = comp.SystemRecord.from_dict(json.loads(json.dumps(record.to_dict())))
    assert clone.subtree_digest == record.subtree_digest
    swapped = replace(record, children=(record.children[1], record.children[0]))
    assert swapped.subtree_digest == record.subtree_digest
    revised = replace(record.children[0], revision="a2")
    assert replace(record, children=(revised, record.children[1])).subtree_digest != (
        record.subtree_digest)
    chain, chain_models, chain_boundary = fixtures.build_chain(4)
    assert chain.depth == 4
    chain_result = hier.HierarchicalSimulator(chain, chain_models).evaluate(chain_boundary)
    assert chain_result.status == "converged"
    assert chain_result.values["x_out"] == pytest.approx(1.0)


def test_platform94_sibling_subtree_reuse_and_miss_reasons() -> None:
    bundle = fixtures.build_parallel()
    record, models, boundary = bundle[0], bundle[1], bundle[2]
    simulator = hier.HierarchicalSimulator(record, models)
    first = simulator.evaluate(boundary)
    assert first.status == "converged"
    assert first.values == {"out0": 1.0, "out1": 2.0, "out2": 3.0}
    second = simulator.evaluate(dict(boundary))
    assert second.cache_key == first.cache_key
    assert second.values == first.values
    third = simulator.evaluate({"unrelated": 1.0})
    assert third.cache_key != first.cache_key
    for leaf_result in third.children:
        assert leaf_result.cache_reason == "hit_exact"
    axes = {"solver": "a@1", "boundary": "b1", "input": "i1"}
    assert hier.classify_miss(axes, {**axes, "boundary": "b2"}) == "miss_boundary_changed"
    assert hier.classify_miss(axes, {**axes, "solver": "a@2"}) == "miss_solver_changed"
    assert hier.classify_miss(axes, dict(axes)) == "miss_input_changed"
    key = hier.hierarchy_cache_key(subtree_digest=record.subtree_digest,
                                   boundary_digest=first.cache_key,
                                   solver=("hier", "1"), fidelity="analytical")
    assert HEX64.fullmatch(key)
    altered = hier.hierarchy_cache_key(
        subtree_digest=record.subtree_digest, boundary_digest=first.cache_key,
        solver=("hier", "1"), fidelity="analytical", harmonic_digest="0" * 64)
    assert altered != key
    with pytest.raises(ValueError, match="DIGEST"):
        hier.hierarchy_cache_key(subtree_digest="nope", boundary_digest=first.cache_key,
                                 solver=("hier", "1"))


def test_platform94_mass_aggregates_through_levels() -> None:
    record, _, _ = fixtures.build_aircraft()
    assert record.mass is not None
    assert record.mass.mass_kg == pytest.approx(11.0)
    assert record.mass.cg_m[0] == pytest.approx(2.15 / 11.0)
    assert record.mass.cg_m[2] == pytest.approx(0.1 / 11.0)
    propulsion = record.find("propulsion")
    assert propulsion is not None and propulsion.mass is not None
    assert propulsion.mass.mass_kg == pytest.approx(2.5)
    assert propulsion.mass.cg_m[0] == pytest.approx(0.42)


def test_platform94_port_mismatch_fails_before_solver() -> None:
    fixtures.build_mechanical()
    out_port = comp.mechanical_port("force_out", "force", "N", "out", "frameA")
    bad_unit = comp.mechanical_port("force_in", "force", "Pa", "in", "frameB")
    with pytest.raises(ValueError, match="UNIT_MISMATCH"):
        comp.check_compatible(out_port, bad_unit)
    bad_frame = comp.mechanical_port("force_in", "force", "N", "in", "other")
    with pytest.raises(ValueError, match="TRANSFORM_REQUIRED"):
        comp.check_compatible(out_port, bad_frame)
    bad_signal = comp.mechanical_port("force_in", "torque", "N", "in", "frameA")
    with pytest.raises(ValueError, match="SIGNAL_MISMATCH"):
        comp.check_compatible(out_port, bad_signal)
    with pytest.raises(ValueError, match="UNIT_MISMATCH"):
        comp.SystemRecord(
            system_id="root", revision="1", system_type="bad",
            ports=(comp.mechanical_port("x", "displacement", "mm", "out", "bench"),),
            children=(
                comp.SystemRecord(system_id="a", revision="1", system_type="leaf",
                                  ports=(out_port,)),
                comp.SystemRecord(system_id="b", revision="1", system_type="leaf",
                                  ports=(bad_unit,)),
            ),
            links=(comp.AssemblyLink("a", "force_out", "b", "force_in"),),
            bindings=(comp.Binding("b", "force_in", "x"),),
        )


def test_platform94_independent_subtrees_run_concurrently() -> None:
    record, models, boundary, seen = fixtures.build_parallel()
    result = hier.HierarchicalSimulator(record, models).evaluate(boundary)
    assert result.status == "converged"
    assert len(set(seen.values())) >= 2


def test_platform94_child_failure_propagates_typed() -> None:
    record, models, boundary = fixtures.build_propulsion()

    def broken(inputs: dict[str, float]) -> dict[str, float]:
        raise RuntimeError("stator fault")

    models["motor"] = hier.LeafModel("motor", broken, {"shaft_out": "W", "heat_out": "W"})
    result = hier.HierarchicalSimulator(record, models).evaluate(boundary)
    assert result.status == "failed"
    assert "CHILD_FAILED:motor" in result.receipts[0]
    by_id = {node.system_id: node for node in result.children}
    assert by_id["motor"].status == "failed"
    assert by_id["source"].status == "converged"
    assert "MODEL_FAILED:motor" in by_id["motor"].receipts[0]


def test_platform94_mixed_fidelity_never_promotes_parent() -> None:
    record, models, _ = fixtures.build_propulsion()
    promoted = asm.promote_fidelity(record, "motor", "native")
    assert asm.limiting_fidelity(promoted) == "analytical"
    assert asm.fidelity_evidence(promoted)["motor"] == "native"
    native_models = dict(models)
    native_models["motor"] = hier.LeafModel(
        "motor", lambda inputs: {"shaft_out": inputs["motor_power"] * 0.9,
                                 "heat_out": inputs["motor_power"] * 0.1},
        {"shaft_out": "W", "heat_out": "W"}, native=True, solver=("prop-motor", "9.9"))
    simulator = hier.HierarchicalSimulator(promoted, native_models)
    with pytest.raises(hier.CapabilityUnavailable):
        simulator.evaluate({})
    try:
        simulator.evaluate({})
    except hier.CapabilityUnavailable as exc:
        assert exc.requirement == "motor"
    else:
        raise AssertionError("capability gate did not fail closed")
    outcome = simulator.evaluate({}, capabilities={"motor": True})
    assert outcome.status == "converged"
    assert outcome.fidelity == "analytical"
    assert outcome.source == "analytical"
    assert _child(outcome, "motor").source == "native_solver"


def test_platform94_requirements_and_margins_three_levels() -> None:
    record, _, _ = fixtures.build_aircraft()
    allocated = asm.allocate_requirements(record, {
        "propulsion": (comp.Requirement("PS2", "response", "thrust_out", "N", 10.0, ">=",
                                        margin=0.1),),
        "motor": (comp.Requirement("MO2", "thermal headroom", "heat_out", "W", 50.0, "<=",
                                   margin=0.05),),
    })
    assert allocated.find("motor") is not None
    assert any(req.req_id == "MO2" for req in allocated.find("motor").requirements)
    rolled = asm.margin_rollup(allocated)
    assert rolled["MO2"] == pytest.approx(0.05)
    assert asm.system_margin(allocated) == pytest.approx(0.05)
    with pytest.raises(ValueError, match="ALLOCATION_TARGET_UNKNOWN"):
        asm.allocate_requirements(record, {"ghost": ()})
    quantities = {"vehicle": {"lift_out": 98.1, "drag_out": 30.0}}
    verdicts = asm.evaluate_tree(allocated, quantities)
    assert verdicts["vehicle"].passed
    assert set(verdicts) >= {"vehicle", "airframe", "propulsion", "motor", "energy", "controls"}


def test_platform94_rom_replacement_is_provenance_distinct() -> None:
    record, models, boundary = fixtures.build_aircraft()
    live = hier.HierarchicalSimulator(record, models).evaluate(boundary)
    rom = fixtures.build_rom_replacement()
    replaced = asm.replace_subassembly(record, "propulsion", rom)
    assert replaced.find("propulsion") is not None
    assert replaced.find("propulsion").mode == "rom"
    assert replaced.subtree_digest != record.subtree_digest
    rom_models = {key: value for key, value in models.items()
                  if key not in ("motor", "propulsor")}
    rom_models.update(fixtures.rom_models())
    reused = hier.HierarchicalSimulator(replaced, rom_models).evaluate(boundary)
    assert reused.status == "converged"
    assert reused.values["thrust_out"] != pytest.approx(live.values["thrust_out"])
    assert reused.inputs_hash != live.inputs_hash
    assert reused.provenance_id != live.provenance_id
    broken = replace(rom, ports=tuple(port for port in rom.ports
                                     if port.port_id != "heat_out"))
    with pytest.raises(ValueError, match="SUBASSEMBLY"):
        asm.replace_subassembly(record, "propulsion", broken)


def test_platform94_native_paths_fail_closed() -> None:
    with pytest.raises(hier.CapabilityUnavailable, match="NATIVE_CAPABILITY_UNAVAILABLE"):
        hier.require_capability("openfoam", present=False)
    hier.require_capability("openfoam", present=True)
    record, models, _ = fixtures.build_mechanical()
    with pytest.raises(ValueError, match="MODEL_MISSING"):
        hier.HierarchicalSimulator(record, {})
    with pytest.raises(ValueError, match="MODEL_FOR_ASSEMBLY"):
        hier.HierarchicalSimulator(
            record, {**models, "assembly": models["compA"]})


def test_platform94_single_flight_and_cache_store() -> None:
    cache: hier.SingleFlightCache[dict[str, float]] = hier.SingleFlightCache()
    key = "ab" * 32

    def factory() -> dict[str, float]:
        time.sleep(0.05)
        return {"value": 1.0}

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: cache.compute_if_absent(key, factory), range(8)))
    assert cache.computations == 1
    assert all(item == {"value": 1.0} for item in results)
    assert threading.active_count() >= 1


def test_platform94_every_result_carries_full_envelope() -> None:
    record, models, boundary = fixtures.build_aircraft()
    result = hier.HierarchicalSimulator(record, models).evaluate(boundary)
    stack = [result]
    seen = 0
    while stack:
        node = stack.pop()
        seen += 1
        assert node.source in ("analytical", "surrogate", "benchmark", "native_solver")
        assert node.fidelity in ("analytical", "surrogate", "benchmark", "native")
        assert set(node.units) == set(node.values)
        assert isinstance(node.validity_passed, bool)
        assert HEX64.fullmatch(node.inputs_hash)
        assert HEX64.fullmatch(node.provenance_id)
        assert node.software == ("aeroworkbench-coupling-hierarchy", "1.0.0")
        stack.extend(node.children)
    assert seen == 7


def test_platform94_interference_and_wrench_receipts() -> None:
    contacts = asm.detect_interference({"a": ((0.0, 0.0, 0.0), 1.0),
                                        "b": ((1.5, 0.0, 0.0), 1.0)})
    assert contacts[0].contact
    assert contacts[0].gap_m == pytest.approx(-0.5)
    clear = asm.detect_interference({"a": ((0.0, 0.0, 0.0), 1.0),
                                     "b": ((3.0, 0.0, 0.0), 1.0)})
    assert not clear[0].contact
    with pytest.raises(ValueError, match="CLEARANCE"):
        asm.detect_interference({"a": ((0.0, 0.0, 0.0), 1.0)}, clearance_m=-1.0)
    source = physical.PhysicalPort("force", "wrench", "N", "out", "motor")
    target = physical.PhysicalPort("load", "wrench", "N", "in", "vehicle")
    contract = physical.InterfaceContract("motor", source, "vehicle", target)
    transform = physical.RigidTransform("motor", "vehicle",
                                        ((0.0, -1.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0)),
                                        (1.0, 0.0, 0.0))
    receipt = field.transfer_wrench(contract, (10.0, 0.0, 0.0), (0.0, 0.0, 2.0), transform)
    assert receipt.values == pytest.approx((0.0, 10.0, 0.0, 0.0, 0.0, 12.0))
    assert receipt.accepted
    assert len(receipt.operator_digest) == 64
    altered = field.transfer_wrench(
        contract, (10.0, 0.0, 0.0), (0.0, 0.0, 2.0),
        replace(transform, translation_m=(2.0, 0.0, 0.0)))
    assert altered.operator_digest != receipt.operator_digest


def test_platform94_harmonic_order_triggers_resonance_escalation() -> None:
    source = physical.PhysicalPort("force", "harmonic", "N", "out", "motor")
    target = physical.PhysicalPort("load", "harmonic", "N", "in", "vehicle")
    contract = physical.InterfaceContract("motor", source, "vehicle", target)
    basis = physical.HarmonicBasis("shaft-1", "motor", frequency_hz=100.0, order=4.0)
    moved = field.transfer_harmonic(contract, (3.0 + 0j,), basis)
    assert moved.basis.frame == "vehicle"
    assert moved.basis.order == pytest.approx(4.0)
    assert moved.receipt.accepted
    trigger = resonance.check_resonance(
        (resonance.ForcingSpectrum("propulsor", "blade-pass",
                                  (moved.basis.frequency_hz,), (3.0,)),),
        (resonance.ModalSpectrum("wing", "bending", (100.5,), (0.01,)),),
        resonance.ResonancePolicy(2.0, 1.0, ("harmonic-response",), ("harmonic-response",),
                                  ("harmonic-response",)),
    )
    assert trigger.state == "triggered"
    assert trigger.required_capability is not None
    clear = resonance.check_resonance(
        (resonance.ForcingSpectrum("propulsor", "blade-pass", (50.0,), (3.0,)),),
        (resonance.ModalSpectrum("wing", "bending", (100.5,), (0.01,)),),
        resonance.ResonancePolicy(2.0, 1.0, (), (), ()),
    )
    assert clear.state == "clear"
