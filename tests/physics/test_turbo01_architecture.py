"""TURBO 01: canonical rotating-gas-machine architecture contract.

The six acceptance fixtures are schema-only portability documents. This module
proves the same contract can represent an electrically driven ducted fan, a
multi-row axial compressor, a radial compressor plus diffuser, a
compressor-combustor-turbine core, a multi-spool bypass gas path, and a
free-power-turbine arrangement, and that the deterministic hash matches the
TypeScript mirror (``tests/unit/turbo01_architecture.test.ts``).
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from aeroworkbench_coupling.dag import CHANGE_IMPACT, invalidated_families
from aeroworkbench_turbomachinery import (
    RotatingGasArchitecture,
    architecture_from_payload,
    architecture_hash,
    architecture_provenance,
    canonical_architecture,
    topology_change_sections,
    topology_digest,
)

_TESTS_ROOT = Path(__file__).resolve().parents[1]
_FIXTURE_DIR = _TESTS_ROOT / "turbo" / "fixtures"
_EXPECTED_HASHES: dict[str, str] = json.loads(
    (_TESTS_ROOT / "turbo" / "expected_hashes.json").read_text(encoding="utf-8")
)

_ACCEPTANCE_FIXTURES = (
    "single_ducted_fan.json",
    "multi_row_axial_compressor.json",
    "radial_compressor_diffuser.json",
    "core_compressor_combustor_turbine.json",
    "multi_spool_bypass.json",
    "free_power_turbine.json",
)


def load_fixture(name: str) -> dict[str, Any]:
    return json.loads((_FIXTURE_DIR / name).read_text(encoding="utf-8"))


def parse(name: str) -> RotatingGasArchitecture:
    return architecture_from_payload(load_fixture(name))


def node_kinds(architecture: RotatingGasArchitecture) -> set[str]:
    return {node.kind for node in architecture.nodes}


def row_roles(architecture: RotatingGasArchitecture) -> set[str]:
    return {row.role for row in architecture.rows}


def test_turbo01_every_acceptance_fixture_validates() -> None:
    for name in _ACCEPTANCE_FIXTURES:
        architecture = parse(name)
        assert architecture.architecture_id.startswith("turbo01-")


@pytest.mark.parametrize("name", _ACCEPTANCE_FIXTURES)
def test_turbo01_hashes_match_shared_cross_language_contract(name: str) -> None:
    architecture = parse(name)
    expected = _EXPECTED_HASHES[architecture.architecture_id]
    assert architecture_hash(architecture) == expected
    assert architecture.architecture_hash == expected


def test_turbo01_canonical_roundtrip_is_lossless() -> None:
    for name in _ACCEPTANCE_FIXTURES:
        architecture = parse(name)
        canonical = architecture.canonical_payload()
        rebuilt = architecture_from_payload(canonical)
        assert rebuilt.canonical_payload() == canonical
        assert architecture_hash(rebuilt) == architecture_hash(architecture)
        assert topology_digest(rebuilt) == topology_digest(architecture)


def test_turbo01_hash_is_order_independent() -> None:
    for name in _ACCEPTANCE_FIXTURES:
        payload = load_fixture(name)
        reordered = {
            "shafts": list(reversed(payload["shafts"])),
            "rows": list(reversed(payload["rows"])),
            "stations": list(reversed(payload["stations"])),
            "edges": list(reversed(payload["edges"])),
            "nodes": list(reversed(payload["nodes"])),
            "defaultFluid": payload.get("defaultFluid"),
            "architectureId": payload["architectureId"],
            "schemaVersion": payload["schemaVersion"],
        }
        assert architecture_hash(reordered) == architecture_hash(payload)


def test_turbo01_topology_digest_ignores_station_values() -> None:
    architecture = parse("single_ducted_fan.json")
    changed = deepcopy(load_fixture("single_ducted_fan.json"))
    changed["stations"][1]["state"]["totalPressure"] = {"value": 92000, "unit": "Pa"}
    assert topology_digest(changed) == topology_digest(architecture)
    assert architecture_hash(changed) != architecture_hash(architecture)


def test_turbo01_topology_change_sections_feed_existing_invalidation() -> None:
    architecture = parse("single_ducted_fan.json")
    value_change = deepcopy(load_fixture("single_ducted_fan.json"))
    value_change["stations"][1]["state"]["totalPressure"] = {"value": 92000, "unit": "Pa"}
    assert topology_change_sections(architecture, value_change) == ("operatingPoints",)

    structural = deepcopy(load_fixture("single_ducted_fan.json"))
    structural["nodes"].append({"id": "diffuser", "kind": "diffuser"})
    structural["edges"].append(
        {"from": "fan", "to": "diffuser", "kind": "flow", "station": "2"}
    )
    structural["edges"].append(
        {"from": "diffuser", "to": "nozzle", "kind": "flow", "station": "2"}
    )
    sections = topology_change_sections(architecture, structural)
    assert "topologyDigest" in sections
    for section in sections:
        assert section in CHANGE_IMPACT
    families = set(invalidated_families(sections))
    assert {"mesh", "analysis"} <= families


def test_turbo01_acceptance_examples_cover_required_constructs() -> None:
    fan = parse("single_ducted_fan.json")
    assert {"ambient", "inlet", "fan_stage", "nozzle", "exhaust"} <= node_kinds(fan)
    assert fan.rows[0].role == "work_adding"
    assert fan.rows[0].frame == "rotating"
    assert fan.rows[0].family == "axial"
    assert fan.shafts[0].couplings[0].kind == "electric_motor"

    axial = parse("multi_row_axial_compressor.json")
    rotors = [row for row in axial.rows if row.role == "work_adding"]
    stators = [row for row in axial.rows if row.role == "turning_only"]
    assert len(rotors) >= 3 and len(stators) >= 3
    assert all(row.shaft == "hp-spool" for row in rotors)
    assert all(row.shaft is None for row in stators)

    radial = parse("radial_compressor_diffuser.json")
    assert any(row.family == "radial" for row in radial.rows)
    assert any(row.role == "diffuser_guide" for row in radial.rows)
    assert "diffuser" in node_kinds(radial)

    core = parse("core_compressor_combustor_turbine.json")
    assert "combustor" in node_kinds(core)
    core_rows = {row.role for row in core.rows}
    assert {"work_adding", "work_extracting"} <= core_rows
    assert core.shafts[0].couplings[0].kind == "mechanical_load"

    bypass = parse("multi_spool_bypass.json")
    assert {"bypass_split", "core_split", "bypass_merge", "core_merge"} <= node_kinds(bypass)
    assert len(bypass.shafts) >= 2
    geared = [c for shaft in bypass.shafts for c in shaft.couplings if c.kind == "geared"]
    assert geared and geared[0].ratio == pytest.approx(3.0)

    free = parse("free_power_turbine.json")
    assert any(shaft.kind == "free_power" for shaft in free.shafts)
    generators = [
        c
        for shaft in free.shafts
        for c in shaft.couplings
        if c.kind == "electric_generator"
    ]
    assert generators and generators[0].efficiency == pytest.approx(0.97)


def test_turbo01_invalid_architectures_fail_closed() -> None:
    def mutated(mutator) -> dict[str, Any]:
        payload = deepcopy(load_fixture("single_ducted_fan.json"))
        mutator(payload)
        return payload

    def drop_shaft(payload: dict[str, Any]) -> None:
        payload["rows"][0]["shaft"] = None

    with pytest.raises(ValueError, match="ROTATING_ROW_NEEDS_SHAFT"):
        architecture_from_payload(mutated(drop_shaft))

    def wrong_role_frame(payload: dict[str, Any]) -> None:
        payload["rows"][0].update({"role": "work_adding", "frame": "stationary", "shaft": None})

    with pytest.raises(ValueError, match="WORK_ROW_MUST_ROTATE|STATIONARY_ROW_HAS_SHAFT"):
        architecture_from_payload(mutated(wrong_role_frame))

    def bad_endpoint(payload: dict[str, Any]) -> None:
        payload["edges"][0]["to"] = "missing-node"

    with pytest.raises(ValueError, match="EDGE_ENDPOINT_UNKNOWN"):
        architecture_from_payload(mutated(bad_endpoint))

    def duplicate_node(payload: dict[str, Any]) -> None:
        payload["nodes"].append(dict(payload["nodes"][0]))

    with pytest.raises(ValueError, match="DUPLICATE_NODE"):
        architecture_from_payload(mutated(duplicate_node))

    def cycle(payload: dict[str, Any]) -> None:
        payload["edges"].append(
            {"from": "exhaust", "to": "fan", "kind": "flow", "station": "2"}
        )

    with pytest.raises(ValueError, match="FLOW_CYCLE"):
        architecture_from_payload(mutated(cycle))

    def wrong_machine_kind(payload: dict[str, Any]) -> None:
        payload["shafts"][0]["couplings"][0]["targetNode"] = "fan"

    with pytest.raises(ValueError, match="COUPLING_TARGET_NODE_KIND"):
        architecture_from_payload(mutated(wrong_machine_kind))


def test_turbo01_units_are_dimension_checked() -> None:
    payload = deepcopy(load_fixture("single_ducted_fan.json"))
    payload["stations"][1]["state"]["massFlow"] = {"value": 1.0, "unit": "Pa"}
    with pytest.raises(ValueError, match="QUANTITY_DIMENSION_MISMATCH"):
        architecture_from_payload(payload)

    payload = deepcopy(load_fixture("single_ducted_fan.json"))
    payload["stations"][1]["state"]["totalPressure"] = {"value": 1.0, "unit": "furlongs"}
    with pytest.raises(ValueError, match="UNKNOWN_UNIT"):
        architecture_from_payload(payload)


def test_turbo01_provenance_records_schema_identity() -> None:
    architecture = parse("single_ducted_fan.json")
    provenance = architecture_provenance(architecture)
    assert provenance.source.value == "analytical"
    assert provenance.model == "rotating-gas-architecture"
    assert len(provenance.inputs_hash) == 64
    assert provenance.solver_name is None


def test_turbo01_canonical_architecture_rejects_unrelated_document() -> None:
    with pytest.raises(ValueError):
        canonical_architecture({"architectureId": "x"})
