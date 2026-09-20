from dataclasses import replace
from threading import Barrier

import pytest
from aeroworkbench_core import physical
from aeroworkbench_coupling.dag import ComputationDAG


def tree():
    motor = physical.PhysicalSystem("motor", "1")
    propulsion = physical.PhysicalAssembly("propulsion", "1", children=(motor,))
    wing = physical.PhysicalSystem("wing", "1")
    return physical.PhysicalAssembly("vehicle", "1", children=(wing, propulsion))


def test_merkle_identity_is_order_independent_and_reuses_sibling():
    root = tree()
    reordered = replace(root, children=tuple(reversed(root.children)))
    assert root.subtree_digest == reordered.subtree_digest
    changed = replace(root, children=(replace(root.children[0], revision="2"), root.children[1]))
    assert changed.subtree_digest != root.subtree_digest
    assert changed.children[1].subtree_digest == root.children[1].subtree_digest
    assert physical.PhysicalSystem.from_dict(root.to_dict()) == root
    with pytest.raises(ValueError, match="DUPLICATE"):
        replace(root, children=(root.children[0], root.children[0]))


def test_recursive_dag_parallel_leaves_replay_and_typed_failure():
    barrier = Barrier(2)
    calls = []

    def leaf(name):
        def run(_deps):
            calls.append(name)
            barrier.wait(timeout=3)
            return 2, "W"
        return run

    functions = {"motor": leaf("motor"), "wing": leaf("wing"),
                 "propulsion": lambda deps: (deps["motor"].value, "W"),
                 "vehicle": lambda deps: (sum(r.value for r in deps.values()), "W")}
    dag = ComputationDAG.from_system(tree(), functions)
    result = dag.execute({}, max_workers=2, capture_failures=True)
    assert result["vehicle"].value == 4
    assert result["vehicle"].status == "computed"
    assert all(r.cached for r in dag.execute({}, max_workers=2).values())
    assert sorted(calls) == ["motor", "wing"]

    def fail(_deps):
        raise ValueError("invalid boundary")

    functions["motor"] = fail
    broken = ComputationDAG.from_system(tree(), functions)
    # Wing must not wait at the successful-case barrier in this run.
    broken._functions["wing"] = lambda deps: (2, "W")
    failed = broken.execute({}, max_workers=2, capture_failures=True)
    assert failed["motor"].status == "failed"
    assert failed["propulsion"].status == "upstream_failed"
    assert failed["vehicle"].status == "upstream_failed"
    assert failed["wing"].status == "computed"


def test_ports_reject_unit_semantic_and_direction_mismatch():
    p = physical.PhysicalPort("heat", "thermal", "W", "out", "body")
    q = replace(p, port_id="sink", direction="in")
    contract = physical.InterfaceContract("a", p, "b", q)
    assert len(contract.digest) == 64
    for invalid in (replace(q, semantic="electrical"), replace(q, direction="out")):
        with pytest.raises(ValueError):
            physical.InterfaceContract("a", p, "b", invalid)
    with pytest.raises(ValueError):
        replace(p, unit="K")
