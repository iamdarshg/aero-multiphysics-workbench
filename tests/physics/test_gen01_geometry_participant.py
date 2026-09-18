"""GEN 01: parametric geometry as a first-class design-variable participant.

Generic infrastructure only: a rectangular body, a positional face envelope,
and scalar parameters. No application-specific component names appear here.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from aeroworkbench_coupling.manifest_coordinator import (
    GeometryDesignVariable,
    make_geometry_regeneration_component,
)
from aeroworkbench_geometry import (
    GeometryRegenerationRequest,
    GeometryRegenerator,
    ParameterDef,
    ParameterSet,
    ParametricModel,
    SemanticBinding,
    export_artifacts,
    live_shapes,
    param,
    regenerate,
)
from aeroworkbench_semantics import SemanticAssignment

_PARAMETERS = (
    ParameterDef("span", 12.0),
    ParameterDef("depth", 6.0),
    ParameterDef("rise", 4.0),
    ParameterDef("halfRise", expression="rise/2"),
)


def _model() -> ParametricModel:
    model = ParametricModel("generic-block", ParameterSet(_PARAMETERS))
    model.add_box("body", param("span"), param("depth"), param("halfRise"))
    return model


def _request(model: ParametricModel | None = None, **kwargs: object) -> GeometryRegenerationRequest:
    return GeometryRegenerationRequest(model=model or _model(), **kwargs)  # type: ignore[arg-type]


def _total_volume(receipt: object) -> float:
    return sum(component.volume_mm3 for component in receipt.components)  # type: ignore[attr-defined]


def test_gen01_parameter_update_changes_geometry_and_hashes() -> None:
    regenerator = GeometryRegenerator(_request())
    small = regenerator.evaluate({"span": 12.0})
    large = regenerator.evaluate({"span": 24.0})

    assert small.valid and large.valid
    assert small.shape_hash != large.shape_hash
    assert small.parameter_hash != large.parameter_hash
    # A bound value change must not perturb the structural definition hash.
    assert small.definition_hash == large.definition_hash
    assert _total_volume(large) > _total_volume(small)


def test_gen01_unchanged_parameters_hit_cache_deterministically() -> None:
    regenerator = GeometryRegenerator(_request())
    first = regenerator.evaluate({"span": 12.0})
    second = regenerator.evaluate({"span": 12.0})

    assert second is first
    assert regenerator.cache_hits == 1
    assert first.shape_hash == second.shape_hash
    assert first.definition_hash == second.definition_hash


def test_gen01_derived_parameter_propagates_through_geometry() -> None:
    regenerator = GeometryRegenerator(_request())
    low = regenerator.evaluate({"rise": 4.0})
    high = regenerator.evaluate({"rise": 8.0})

    assert dict(low.resolved_parameters)["halfRise"] == 2.0
    assert dict(high.resolved_parameters)["halfRise"] == 4.0
    assert high.shape_hash != low.shape_hash
    assert _total_volume(high) > _total_volume(low)


def test_gen01_invalid_geometry_becomes_invalid_receipt() -> None:
    regenerator = GeometryRegenerator(_request())

    negative = regenerator.evaluate({"depth": -1.0})
    assert negative.valid is False
    assert negative.validity_state == "invalid"
    assert negative.components == ()
    assert any("CAD_EXECUTION_FAILED" in reason for reason in negative.invalid_reasons)

    unknown = regenerator.evaluate({"span": 12.0, "notARealParameter": 1.0})
    assert unknown.valid is False
    assert any(
        "PARAMETER_RESOLUTION_FAILED" in reason for reason in unknown.invalid_reasons
    )

    nonfinite = regenerator.evaluate({"span": float("inf")})
    assert nonfinite.valid is False
    assert any(
        "PARAMETER_VALUE_NOT_FINITE" in reason for reason in nonfinite.invalid_reasons
    )


def test_gen01_semantic_identity_survives_benign_geometry_change() -> None:
    model = _model()
    parent = regenerate(
        _request(
            model,
            semantic_assignments=(
                SemanticAssignment("face-0", "region.a", "solid-region", "body"),
            ),
        )
    )
    assert parent.valid

    child = regenerate(
        _request(
            model,
            bound_parameters={"span": 12.2},
            semantic_assignments=(
                SemanticAssignment("face-7", "region.a", "solid-region", "body"),
            ),
            parent=parent,
        )
    )
    assert child.valid
    assert child.semantic_report is not None and child.semantic_report.valid
    assert [item.semantic_key for item in child.semantic_report.persistent] == [
        "region.a"
    ]


def test_gen01_ambiguous_topology_change_fails_closed() -> None:
    model = _model()
    parent = regenerate(
        _request(
            model,
            semantic_bindings=(
                SemanticBinding("region.a", "solid_region", "region-a", "body"),
            ),
        )
    )
    assert parent.valid and parent.topology is not None

    child = regenerate(
        _request(
            model,
            semantic_bindings=(
                SemanticBinding("region.b", "solid_region", "region-b", "body"),
            ),
            parent=parent,
            permitted_topology_change="preserve",
        )
    )
    assert child.valid is False
    assert any("TOPOLOGY_AMBIGUOUS" in reason for reason in child.invalid_reasons)


def test_gen01_openmdao_component_varies_two_geometry_variables() -> None:
    import openmdao.api as om

    variables = (
        GeometryDesignVariable("span", "span", "mm"),
        GeometryDesignVariable("rise", "rise", "mm"),
    )
    component = make_geometry_regeneration_component(_request(), variables)

    problem = om.Problem(reports=False)
    indep = om.IndepVarComp()
    indep.add_output("span", val=12.0)
    indep.add_output("rise", val=4.0)
    problem.model.add_subsystem("design_vars", indep, promotes_outputs=["span", "rise"])
    problem.model.add_subsystem("geometry", component(), promotes_inputs=["span", "rise"])
    problem.setup()
    problem.run_model()

    geometry = problem.model.geometry
    assert geometry.last_receipt is not None and geometry.last_receipt.valid
    first_volume = float(problem.get_val("geometry.total_volume_mm3").item())
    first_hash = geometry.last_receipt.shape_hash

    problem.set_val("design_vars.span", 24.0)
    problem.run_model()
    second_volume = float(problem.get_val("geometry.total_volume_mm3").item())
    second_hash = geometry.last_receipt.shape_hash

    assert geometry.last_receipt.valid
    assert second_volume > first_volume
    assert second_hash != first_hash
    assert float(problem.get_val("geometry.shape_valid").item()) == 1.0
    assert len(geometry.receipts) == 2


def test_gen01_literal_api_and_export_remain_backward_compatible(tmp_path: Path) -> None:
    model = ParametricModel("literal-block", ParameterSet((ParameterDef("a", 2.0),)))
    model.add_box("body", 10.0, 5.0, 4.0)
    built = model.build()

    assert built.parameter_hash and built.shape_hash and built.definition_hash
    exported = export_artifacts(
        live_shapes(built), built.kernel, tmp_path, basename="literal", export_stl=False
    )
    records = exported["artifacts"]
    formats = {str(record["format"]) for record in records}
    assert {"step", "brep"} <= formats
    for record in records:
        digest = hashlib.sha256(Path(str(record["path"])).read_bytes()).hexdigest()
        assert digest == record["sha256"]


def test_gen01_no_application_specific_names_in_core_geometry() -> None:
    # Tokens are assembled from fragments so this guard's own source stays clean.
    forbidden = [
        "".join(pair)
        for pair in (
            ("bl", "ade"),
            ("du", "ct"),
            ("wi", "ng"),
            ("ro", "tor"),
            ("tu", "rbine"),
            ("no", "zzle"),
            ("im", "peller"),
        )
    ]
    package = (
        Path(__file__).resolve().parents[2]
        / "packages"
        / "geometry"
        / "aeroworkbench_geometry"
    )
    text = "\n".join(
        (package / name).read_text(encoding="utf-8").lower()
        for name in ("parametric.py", "parameters.py", "regeneration.py")
    )
    assert [token for token in forbidden if token in text] == []
