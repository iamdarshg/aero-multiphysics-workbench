"""GEN 03: deterministic candidate generation over the declared design space.

Fixtures are small canonical design spaces (the same JSON shape validated by
GEN 02); no solver runs, so every assertion is a pure contract check.
"""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError

import pytest
from aeroworkbench_optimization import (
    CandidateGenerator,
    GenerationBudgetError,
    GenerationError,
    GenerationRequest,
    candidate_hash,
    flatten_design_state,
)

UNCONDITIONAL_SPACE = r"""
{
  "id": "gen03-unconditional",
  "variables": [
    { "id": "x", "kind": "integer",
      "bindings": [{ "target": "parameter", "path": "p.x" }], "baseValue": 1,
      "domain": { "kind": "integer", "lower": 0, "upper": 2, "step": 1 } },
    { "id": "y", "kind": "discrete",
      "bindings": [{ "target": "parameter", "path": "p.y" }], "baseValue": 1.0,
      "domain": { "kind": "discrete", "values": [1.0, 2.0] } },
    { "id": "mat", "kind": "categorical",
      "bindings": [{ "target": "material", "path": "m.mat" }], "baseValue": "a",
      "domain": { "kind": "categorical", "values": ["a", "b"] } }
  ],
  "branches": [],
  "constraints": []
}
"""

CONDITIONAL_SPACE = r"""
{
  "id": "gen03-conditional",
  "variables": [
    { "id": "material", "kind": "categorical",
      "bindings": [{ "target": "material", "path": "region" }], "baseValue": "alloy",
      "domain": { "kind": "categorical", "values": ["alloy", "steel"] } },
    { "id": "ribbed", "kind": "boolean",
      "bindings": [{ "target": "parameter", "path": "shell.ribbed" }], "baseValue": false,
      "domain": { "kind": "boolean" } },
    { "id": "slotWidth", "kind": "continuous", "unit": "mm",
      "bindings": [{ "target": "solver", "path": "mesh.slot" }], "baseValue": 1.0,
      "activeWhen": { "op": "equals", "variable": "material", "value": "alloy" },
      "domain": { "kind": "continuous", "lower": 0.0, "upper": 3.0 } },
    { "id": "thickness", "kind": "continuous", "unit": "mm",
      "bindings": [{ "target": "parameter", "path": "shell.thickness" }], "baseValue": 2.0,
      "domain": { "kind": "continuous", "lower": 0.5, "upper": 10.0 } }
  ],
  "branches": [
    { "id": "material-branch", "selector": "material",
      "options": { "alloy": ["slotWidth"], "steel": [] } }
  ],
  "constraints": [
    { "id": "steel-requires-ribbed", "kind": "requires",
      "when": { "op": "equals", "variable": "material", "value": "steel" },
      "require": { "op": "equals", "variable": "ribbed", "value": true } }
  ]
}
"""

BIG_SPACE = r"""
{
  "id": "gen03-big",
  "variables": [
    { "id": "x0", "kind": "continuous", "bindings": [{ "target": "parameter", "path": "p0" }],
      "baseValue": 0.5, "domain": { "kind": "continuous", "lower": 0.0, "upper": 1.0 } },
    { "id": "x1", "kind": "continuous", "bindings": [{ "target": "parameter", "path": "p1" }],
      "baseValue": 0.5, "domain": { "kind": "continuous", "lower": 0.0, "upper": 1.0 } },
    { "id": "x2", "kind": "continuous", "bindings": [{ "target": "parameter", "path": "p2" }],
      "baseValue": 0.5, "domain": { "kind": "continuous", "lower": 0.0, "upper": 1.0 } },
    { "id": "x3", "kind": "continuous", "bindings": [{ "target": "parameter", "path": "p3" }],
      "baseValue": 0.5, "domain": { "kind": "continuous", "lower": 0.0, "upper": 1.0 } },
    { "id": "x4", "kind": "continuous", "bindings": [{ "target": "parameter", "path": "p4" }],
      "baseValue": 0.5, "domain": { "kind": "continuous", "lower": 0.0, "upper": 1.0 } },
    { "id": "x5", "kind": "continuous", "bindings": [{ "target": "parameter", "path": "p5" }],
      "baseValue": 0.5, "domain": { "kind": "continuous", "lower": 0.0, "upper": 1.0 } }
  ],
  "branches": [],
  "constraints": []
}
"""

ALIAS_SPACE = r"""
{
  "id": "gen03-alias",
  "variables": [
    { "id": "mode", "kind": "categorical",
      "bindings": [{ "target": "parameter", "path": "p.mode" }], "baseValue": "off",
      "domain": { "kind": "categorical", "values": ["on", "off"] } },
    { "id": "extra", "kind": "discrete",
      "bindings": [{ "target": "parameter", "path": "p.extra" }], "baseValue": 1.0,
      "activeWhen": { "op": "equals", "variable": "mode", "value": "on" },
      "domain": { "kind": "discrete", "values": [1.0, 2.0, 3.0] } }
  ],
  "branches": [
    { "id": "mode-branch", "selector": "mode",
      "options": { "on": ["extra"], "off": [] } }
  ],
  "constraints": []
}
"""


def space(raw: str) -> dict:
    return json.loads(raw)


def test_gen03_factorial_matches_expected_finite_count() -> None:
    generator = CandidateGenerator(
        space(UNCONDITIONAL_SPACE),
        GenerationRequest("factorial", levels=3, budget=100),
    )
    cardinality = generator.plan.cardinality
    assert cardinality.exact is True
    assert cardinality.count == 3 * 2 * 2 == 12
    candidates = list(generator)
    assert len(candidates) == 12
    assert len({candidate.candidate_hash for candidate in candidates}) == 12
    assert all(candidate.valid for candidate in candidates)


def test_gen03_grid_and_permutation_counts() -> None:
    grid = CandidateGenerator(
        space(UNCONDITIONAL_SPACE),
        GenerationRequest("grid", levels=3, budget=100),
    )
    assert len(list(grid)) == 12
    permutation = CandidateGenerator(
        space(UNCONDITIONAL_SPACE),
        GenerationRequest("permutation", budget=100),
    )
    assert permutation.plan.cardinality.count == 4
    assert len(list(permutation)) == 4


def test_gen03_enumeration_requires_explicit_budget() -> None:
    with pytest.raises(GenerationBudgetError, match="EXPLICIT_BUDGET_REQUIRED"):
        CandidateGenerator(space(UNCONDITIONAL_SPACE), GenerationRequest("factorial"))


def test_gen03_budget_truncates_safely() -> None:
    generator = CandidateGenerator(
        space(BIG_SPACE), GenerationRequest("factorial", levels=20, budget=10)
    )
    assert generator.plan.cardinality.count == 20**6
    assert generator.plan.exceeds_budget is True
    assert generator.plan.stop_reason == "budget"
    candidates = list(generator)
    assert len(candidates) == 10
    assert generator.stats.emitted == 10
    assert generator.stats.stop_reason == "budget"


def test_gen03_lazy_enumeration_does_not_materialize_cross_product() -> None:
    generator = CandidateGenerator(
        space(BIG_SPACE), GenerationRequest("factorial", levels=20, budget=10_000_000)
    )
    assert generator.plan.cardinality.count == 20**6
    first_three = generator.take(3)
    assert len(first_three) == 3
    assert generator.stats.emitted == 3
    assert generator.stats.generated == 3


def test_gen03_seeded_random_is_deterministic_and_seed_sensitive() -> None:
    request = GenerationRequest("random", count=10, seed=7)
    first = [candidate.candidate_hash for candidate in CandidateGenerator(
        space(UNCONDITIONAL_SPACE), request
    )]
    second = [candidate.candidate_hash for candidate in CandidateGenerator(
        space(UNCONDITIONAL_SPACE), request
    )]
    other = [candidate.candidate_hash for candidate in CandidateGenerator(
        space(UNCONDITIONAL_SPACE), GenerationRequest("random", count=10, seed=8)
    )]
    assert first == second
    assert first != other


def test_gen03_lhs_and_halton_are_deterministic() -> None:
    for strategy in ("lhs", "halton"):
        request = GenerationRequest(strategy, count=8, seed=3)
        first_generator = CandidateGenerator(space(UNCONDITIONAL_SPACE), request)
        first = [candidate.normalized for candidate in first_generator]
        second = [candidate.normalized for candidate in CandidateGenerator(
            space(UNCONDITIONAL_SPACE), request
        )]
        assert first == second
        assert first_generator.stats.generated == 8
        assert len(first) == first_generator.stats.emitted <= 8


def test_gen03_sobol_low_discrepancy_is_deterministic() -> None:
    request = GenerationRequest("sobol", count=8, seed=1)
    first = [candidate.normalized for candidate in CandidateGenerator(
        space(UNCONDITIONAL_SPACE), request
    )]
    second = [candidate.normalized for candidate in CandidateGenerator(
        space(UNCONDITIONAL_SPACE), request
    )]
    assert first == second
    assert len(first) > 0


def test_gen03_conditional_branches_never_produce_impossible_assignments() -> None:
    generator = CandidateGenerator(
        space(CONDITIONAL_SPACE),
        GenerationRequest("factorial", levels=2, budget=200),
    )
    assert generator.plan.cardinality.exact is False
    for candidate in generator:
        values = {
            item.variable_id: item.value
            for item in candidate.assignment
            if item.point_id is None
        }
        if values["material"] == "steel":
            assert "slotWidth" not in candidate.state
            assert "slotWidth" not in values
        else:
            assert "slotWidth" in candidate.state
    steel_candidates = [
        candidate
        for candidate in generator
        if candidate.state.get("material", {}).get("value") == "steel"
    ]
    assert steel_candidates
    assert all("slotWidth" not in candidate.state for candidate in steel_candidates)


def test_gen03_mixed_domains_are_respected() -> None:
    generator = CandidateGenerator(
        space(UNCONDITIONAL_SPACE),
        GenerationRequest("factorial", levels=3, budget=100),
    )
    for candidate in generator:
        values = {item.variable_id: item.value for item in candidate.assignment}
        assert float(values["x"]).is_integer()
        assert 0.0 <= float(values["x"]) <= 2.0
        assert values["y"] in (1.0, 2.0)
        assert values["mat"] in ("a", "b")


def test_gen03_identical_resolved_designs_dedupe() -> None:
    generator = CandidateGenerator(
        space(ALIAS_SPACE), GenerationRequest("random", count=12, seed=0)
    )
    candidates = list(generator)
    assert generator.stats.generated == 12
    assert generator.stats.duplicates > 0
    assert len(candidates) == generator.stats.emitted < generator.stats.generated
    assert len({candidate.candidate_hash for candidate in candidates}) == len(candidates)
    off_states = [
        candidate for candidate in candidates
        if candidate.state.get("mode", {}).get("value") == "off"
    ]
    assert len(off_states) == 1
    assert generator.stats.emitted <= 4


def test_gen03_candidates_are_immutable_and_content_addressed() -> None:
    generator = CandidateGenerator(
        space(UNCONDITIONAL_SPACE),
        GenerationRequest("factorial", levels=3, budget=100),
    )
    candidate = generator.take(1)[0]
    assert candidate.candidate_hash == candidate_hash(
        flatten_design_state(space(UNCONDITIONAL_SPACE), candidate.state)
    )
    with pytest.raises(FrozenInstanceError):
        candidate.candidate_hash = "tampered"  # type: ignore[misc]


def test_gen03_provenance_reconstructs_candidate() -> None:
    request = GenerationRequest("random", count=6, seed=11)
    first = CandidateGenerator(space(UNCONDITIONAL_SPACE), request).take(4)
    second = CandidateGenerator(space(UNCONDITIONAL_SPACE), request).take(4)
    for left, right in zip(first, second, strict=True):
        assert left.candidate_hash == right.candidate_hash
        assert left.provenance.as_dict() == right.provenance.as_dict()
        assert left.mutations and all(item.source == "base" for item in left.mutations)


def test_gen03_stochastic_requires_count() -> None:
    with pytest.raises(GenerationError, match="REQUIRES_COUNT"):
        CandidateGenerator(space(UNCONDITIONAL_SPACE), GenerationRequest("random"))
