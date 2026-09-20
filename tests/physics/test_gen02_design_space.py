"""GEN 02: canonical mixed, conditional, hierarchical design-space contract.

The fixture JSON below is the *same* document embedded in
``tests/unit/design-space.test.ts``. Both layers must parse it and agree on the
candidate hash, which is the cross-language contract this issue requires.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from aeroworkbench_optimization import (
    DesignSpaceError,
    active_variable_ids,
    candidate_hash,
    flatten_design_state,
    numeric_vector,
    preflight_design_state,
    unflatten_design_state,
    validate_design_space,
)

CROSS_LANGUAGE_FIXTURE = r"""
{
  "id": "gen02-crosslang",
  "variables": [
    { "id": "thickness", "name": "Wall thickness", "kind": "continuous", "unit": "mm",
      "bindings": [{ "target": "parameter", "path": "shell.thickness", "unit": "mm" }],
      "baseValue": 2.0, "mutationScale": 0.25,
      "domain": { "kind": "continuous", "lower": 0.5, "upper": 10.0 } },
    { "id": "segments", "kind": "integer",
      "bindings": [{ "target": "parameter", "path": "ring.segments" }],
      "baseValue": 3,
      "domain": { "kind": "integer", "lower": 1, "upper": 6, "step": 1 } },
    { "id": "taper", "kind": "discrete",
      "bindings": [{ "target": "parameter", "path": "blade.taper" }],
      "baseValue": 1.0,
      "domain": { "kind": "discrete", "values": [0.5, 1.0, 1.5] } },
    { "id": "material", "kind": "categorical",
      "bindings": [{ "target": "material", "path": "region.hot" }],
      "baseValue": "alloy",
      "domain": { "kind": "categorical", "values": ["alloy", "steel"] } },
    { "id": "hollow", "kind": "boolean",
      "bindings": [{ "target": "parameter", "path": "shell.hollow" }],
      "baseValue": false, "domain": { "kind": "boolean" } },
    { "id": "ribbed", "kind": "boolean",
      "bindings": [{ "target": "parameter", "path": "shell.ribbed" }],
      "baseValue": false, "domain": { "kind": "boolean" } },
    { "id": "profile", "kind": "vector-profile", "unit": "mm",
      "bindings": [{ "target": "parameter", "path": "airfoil.camber" }],
      "domain": { "kind": "vector-profile", "lengthVariable": "segments",
        "controlPoints": [
          { "id": "p0", "lower": 0, "upper": 5, "baseValue": 1 },
          { "id": "p1", "lower": 0, "upper": 5, "baseValue": 2 },
          { "id": "p2", "lower": 0, "upper": 5, "baseValue": 3 },
          { "id": "p3", "lower": 0, "upper": 5, "baseValue": 4 },
          { "id": "p4", "lower": 0, "upper": 5, "baseValue": 3 },
          { "id": "p5", "lower": 0, "upper": 5, "baseValue": 2 }
        ] } },
    { "id": "wallOuter", "kind": "linked", "unit": "mm",
      "bindings": [{ "target": "parameter", "path": "shell.outer" }],
      "domain": { "kind": "linked", "targetVariable": "thickness", "scale": 2.0 } },
    { "id": "area", "kind": "derived", "unit": "mm",
      "bindings": [{ "target": "parameter", "path": "shell.area" }],
      "domain": { "kind": "derived", "expression": { "op": "multiply",
        "left": { "op": "variable", "variable": "thickness" },
        "right": { "op": "constant", "value": 4 } } } },
    { "id": "slotWidth", "kind": "continuous", "unit": "mm",
      "bindings": [{ "target": "solver", "path": "mesh.slot", "unit": "mm" }],
      "baseValue": 1.0,
      "activeWhen": { "op": "equals", "variable": "material", "value": "alloy" },
      "domain": { "kind": "continuous", "lower": 0.0, "upper": 3.0 } }
  ],
  "branches": [
    { "id": "material-branch", "selector": "material",
      "options": { "alloy": ["slotWidth"], "steel": [] } }
  ],
  "constraints": [
    { "id": "shell-mutex", "kind": "mutually-exclusive", "variables": ["hollow", "ribbed"] },
    { "id": "steel-requires-ribbed", "kind": "requires",
      "when": { "op": "equals", "variable": "material", "value": "steel" },
      "require": { "op": "equals", "variable": "ribbed", "value": true } },
    { "id": "length-check", "kind": "count",
      "countVariable": "segments", "memberVariable": "profile" },
    { "id": "thin-limit", "kind": "relation",
      "expression": { "op": "variable", "variable": "thickness" },
      "relation": "lessOrEqual", "limit": 0.008 }
  ]
}
"""

CROSS_LANGUAGE_STATE = r"""
{
  "thickness": { "kind": "number", "value": 2.0, "unit": "mm" },
  "segments": { "kind": "dimensionless", "value": 3 },
  "taper": { "kind": "dimensionless", "value": 1.0 },
  "material": { "kind": "categorical", "value": "alloy" },
  "hollow": { "kind": "boolean", "value": true },
  "ribbed": { "kind": "boolean", "value": false },
  "profile": { "kind": "vector-profile", "points": [
    { "id": "p0", "value": 1.0, "unit": "mm" },
    { "id": "p1", "value": 2.0, "unit": "mm" },
    { "id": "p2", "value": 3.0, "unit": "mm" }
  ] }
}
"""

CROSS_LANGUAGE_HASH = "38cf9ebbe8335edf812c7424f4ca1dfd7075c316e07495912750ff3d1259aa77"


def fixture() -> dict:
    return json.loads(CROSS_LANGUAGE_FIXTURE)


def base_state() -> dict:
    return json.loads(CROSS_LANGUAGE_STATE)


def with_state(**overrides: object) -> dict:
    return {**base_state(), **overrides}


def test_gen02_design_space_fixture_validates() -> None:
    validate_design_space(fixture())


def test_gen02_candidate_hash_matches_typescript_contract() -> None:
    flat = flatten_design_state(fixture(), base_state())
    assert candidate_hash(flat) == CROSS_LANGUAGE_HASH


def test_gen02_every_variable_kind_round_trips_losslessly() -> None:
    space = fixture()
    flat = flatten_design_state(space, base_state())
    rebuilt = unflatten_design_state(space, flat)
    assert flatten_design_state(space, rebuilt) == flat
    kinds = {entry["kind"] for entry in flat["entries"]}
    assert {
        "continuous",
        "integer",
        "discrete",
        "categorical",
        "boolean",
        "vector-profile",
        "linked",
        "derived",
    } <= kinds


def test_gen02_unit_bearing_bounds_normalize() -> None:
    space = fixture()
    millimetres = flatten_design_state(
        space, with_state(thickness={"kind": "number", "value": 2.0, "unit": "mm"})
    )
    metres = flatten_design_state(
        space, with_state(thickness={"kind": "number", "value": 0.002, "unit": "m"})
    )
    thickness_mm = next(entry for entry in millimetres["entries"] if entry["id"] == "thickness")
    thickness_m = next(entry for entry in metres["entries"] if entry["id"] == "thickness")
    assert thickness_mm["valueSI"] == pytest.approx(0.002)
    assert thickness_m["valueSI"] == pytest.approx(0.002)
    assert candidate_hash(millimetres) == candidate_hash(metres)

    with pytest.raises(DesignSpaceError, match="PREFLIGHT_FAILED"):
        flatten_design_state(
            space, with_state(thickness={"kind": "number", "value": 20, "unit": "mm"})
        )


@pytest.mark.parametrize(
    ("declared_unit", "declared_value", "alternate_unit", "alternate_value"),
    [
        ("m", 2.0, "ft", 2.0 / 0.3048),
        ("rad", 0.5, "deg", 0.5 * 180.0 / 3.141592653589793),
        ("m/s", 40.0, "kt", 40.0 / (1852.0 / 3600.0)),
        ("kg", 10.0, "lbm", 10.0 / 0.45359237),
        ("kg/m3", 1.2, "g/cm3", 1.2 / 1000.0),
        ("m2", 3.0, "ft2", 3.0 / 0.09290304),
        ("rpm", 1200.0, "rev/s", 20.0),
    ],
)
def test_gen02_shared_units_preserve_equivalent_candidate_hashes(
    declared_unit: str,
    declared_value: float,
    alternate_unit: str,
    alternate_value: float,
) -> None:
    space: dict[str, Any] = {
        "id": "shared-units",
        "variables": [
            {
                "id": "value",
                "kind": "continuous",
                "unit": declared_unit,
                "bindings": [{"target": "parameter", "path": "value"}],
                "domain": {
                    "kind": "continuous",
                    "lower": declared_value * 0.5,
                    "upper": declared_value * 1.5,
                },
                "baseValue": declared_value,
            }
        ],
    }
    declared = flatten_design_state(
        space, {"value": {"kind": "number", "value": declared_value, "unit": declared_unit}}
    )
    alternate = flatten_design_state(
        space, {"value": {"kind": "number", "value": alternate_value, "unit": alternate_unit}}
    )
    assert candidate_hash(declared) == candidate_hash(alternate)


def test_gen02_shared_units_reject_unknown_and_mixed_units() -> None:
    space: dict[str, Any] = {
        "id": "shared-unit-fail-closed",
        "variables": [
            {
                "id": "length",
                "kind": "continuous",
                "unit": "m",
                "bindings": [{"target": "parameter", "path": "length"}],
                "domain": {"kind": "continuous", "lower": 0.1, "upper": 10.0},
                "baseValue": 1.0,
            }
        ],
    }
    unknown = {**space, "variables": [{**space["variables"][0], "unit": "furlong"}]}
    with pytest.raises(DesignSpaceError, match="UNSUPPORTED_UNIT:length:furlong"):
        validate_design_space(unknown)

    with pytest.raises(DesignSpaceError, match="UNIT_DIMENSION_MISMATCH"):
        flatten_design_state(
            space, {"length": {"kind": "number", "value": 1.0, "unit": "deg"}}
        )


def test_gen02_conditional_activation_is_deterministic() -> None:
    space = fixture()
    alloy = flatten_design_state(space, base_state())
    steel_state = with_state(
        material={"kind": "categorical", "value": "steel"},
        ribbed={"kind": "boolean", "value": True},
        hollow={"kind": "boolean", "value": False},
    )
    steel = flatten_design_state(space, steel_state)
    assert "slotWidth" in alloy["order"]
    assert "slotWidth" in active_variable_ids(space, base_state())
    assert "slotWidth" in steel["inactive"]
    assert "slotWidth" not in steel["order"]
    assert "slotWidth" not in active_variable_ids(space, steel_state)


def test_gen02_profile_length_and_rebuild() -> None:
    space = fixture()
    shortened = flatten_design_state(
        space,
        with_state(
            segments={"kind": "dimensionless", "value": 2},
            profile={
                "kind": "vector-profile",
                "points": [
                    {"id": "p0", "value": 1.0, "unit": "mm"},
                    {"id": "p1", "value": 2.0, "unit": "mm"},
                ],
            },
        ),
    )
    profile = next(entry for entry in shortened["entries"] if entry["id"] == "profile")
    assert [point["id"] for point in profile["points"]] == ["p0", "p1"]
    assert unflatten_design_state(space, shortened)["profile"] == {
        "kind": "vector-profile",
        "points": [
            {"id": "p0", "value": 1.0, "unit": "mm"},
            {"id": "p1", "value": 2.0, "unit": "mm"},
        ],
    }


def test_gen02_invalid_combinations_fail_preflight() -> None:
    space = fixture()
    with pytest.raises(DesignSpaceError, match="PREFLIGHT_FAILED"):
        flatten_design_state(
            space, with_state(material={"kind": "categorical", "value": "titanium"})
        )
    with pytest.raises(DesignSpaceError, match="PREFLIGHT_FAILED"):
        flatten_design_state(space, with_state(material={"kind": "categorical", "value": "steel"}))
    with pytest.raises(DesignSpaceError, match="MUTUALLY_EXCLUSIVE_VIOLATION"):
        flatten_design_state(
            space,
            with_state(
                hollow={"kind": "boolean", "value": True},
                ribbed={"kind": "boolean", "value": True},
            ),
        )
    with pytest.raises(DesignSpaceError, match="thin-limit:RELATION_VIOLATION"):
        flatten_design_state(
            space, with_state(thickness={"kind": "number", "value": 9, "unit": "mm"})
        )
    with pytest.raises(DesignSpaceError, match="length-check:COUNT_MISMATCH"):
        flatten_design_state(space, with_state(segments={"kind": "dimensionless", "value": 2}))


def test_gen02_invalid_space_definitions_fail_closed() -> None:
    duplicate = fixture()
    duplicate["variables"].append(dict(duplicate["variables"][0]))
    with pytest.raises(DesignSpaceError, match="DUPLICATE_VARIABLE"):
        validate_design_space(duplicate)

    cyclic = fixture()
    for variable in cyclic["variables"]:
        if variable["id"] == "wallOuter":
            variable["kind"] = "derived"
            variable["domain"] = {
                "kind": "derived",
                "expression": {"op": "variable", "variable": "area"},
            }
        if variable["id"] == "area":
            variable["kind"] = "derived"
            variable["domain"] = {
                "kind": "derived",
                "expression": {"op": "variable", "variable": "wallOuter"},
            }
    with pytest.raises(DesignSpaceError, match="DESIGN_SPACE_CYCLE"):
        validate_design_space(cyclic)


def test_gen02_candidate_hash_is_key_order_independent() -> None:
    space = fixture()
    reordered = {
        "ribbed": {"kind": "boolean", "value": False},
        "material": {"kind": "categorical", "value": "alloy"},
        "thickness": {"kind": "number", "unit": "mm", "value": 2.0},
        "segments": {"kind": "dimensionless", "value": 3},
        "taper": {"kind": "dimensionless", "value": 1.0},
        "hollow": {"kind": "boolean", "value": True},
        "profile": {
            "points": [
                {"value": 1.0, "id": "p0", "unit": "mm"},
                {"value": 2.0, "id": "p1", "unit": "mm"},
                {"value": 3.0, "id": "p2", "unit": "mm"},
            ],
            "kind": "vector-profile",
        },
    }
    assert candidate_hash(flatten_design_state(space, base_state())) == candidate_hash(
        flatten_design_state(space, reordered)
    )


def test_gen02_preflight_reports_without_physics() -> None:
    space = fixture()
    assert preflight_design_state(space, base_state()) == ()
    violations = preflight_design_state(
        space, with_state(material={"kind": "categorical", "value": "titanium"})
    )
    assert any("NOT_A_CATEGORICAL_VALUE" in item for item in violations)


def test_gen02_numeric_vector_is_stable_for_search_drivers() -> None:
    space = fixture()
    flat = flatten_design_state(space, base_state())
    vector = numeric_vector(flat)
    assert [name for name, _ in vector] == [
        "thickness",
        "segments",
        "taper",
        "wallOuter",
        "area",
        "slotWidth",
    ]
    assert dict(vector)["thickness"] == pytest.approx(0.002)
