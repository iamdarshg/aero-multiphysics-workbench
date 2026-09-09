from __future__ import annotations

from datetime import UTC, datetime

import pytest
from aeroworkbench_core.dag import ComputationNode
from aeroworkbench_core.design import PhysicalDesignState
from aeroworkbench_core.types import (
    FidelityLevel,
    Provenance,
    Quantity,
    ResultSource,
)
from pydantic import ValidationError


def test_quantity_converts_to_canonical_si_without_losing_dimension() -> None:
    length = Quantity(value=70.0, unit="mm")

    assert length.dimension == "length"
    assert length.si_value == pytest.approx(0.070)
    assert length.to("in").value == pytest.approx(2.7559055)


def test_quantity_rejects_unknown_or_dimensionally_incompatible_units() -> None:
    with pytest.raises(ValidationError, match="Unsupported unit"):
        Quantity(value=1.0, unit="furlong")

    with pytest.raises(ValueError, match="Cannot convert length to power"):
        Quantity(value=70.0, unit="mm").to("W")


def test_native_provenance_requires_real_solver_execution_identity() -> None:
    with pytest.raises(ValidationError, match="solver_name, solver_version, and run_id"):
        Provenance(source=ResultSource.NATIVE_SOLVER, model="openfoam")


def test_analytical_provenance_is_explicit_and_hashes_its_inputs() -> None:
    provenance = Provenance.from_inputs(
        source=ResultSource.ANALYTICAL,
        model="actuator-disk",
        model_version="1.0",
        fidelity=FidelityLevel.ANALYTICAL,
        inputs={"power_w": 700.0, "diameter_m": 0.07},
        assumptions=("uniform disk loading",),
    )

    assert provenance.source is ResultSource.ANALYTICAL
    assert provenance.fidelity is FidelityLevel.ANALYTICAL
    assert len(provenance.inputs_hash) == 64
    assert provenance.assumptions == ("uniform disk loading",)


def test_physical_design_hash_is_deterministic_across_mapping_order() -> None:
    first = PhysicalDesignState(
        design_id="edf-70",
        variant_id="baseline",
        parameters={
            "rotor.diameter": Quantity(value=70, unit="mm"),
            "battery.voltage": Quantity(value=22.2, unit="V"),
        },
        geometry_hash="a" * 64,
        material_hash="b" * 64,
    )
    second = PhysicalDesignState(
        design_id="edf-70",
        variant_id="baseline-copy",
        parameters={
            "battery.voltage": Quantity(value=22.2, unit="V"),
            "rotor.diameter": Quantity(value=0.07, unit="m"),
        },
        geometry_hash="a" * 64,
        material_hash="b" * 64,
    )

    assert first.content_hash == second.content_hash


def test_design_variant_is_immutable_and_records_change_provenance() -> None:
    baseline = PhysicalDesignState(
        design_id="edf-70",
        variant_id="baseline",
        parameters={"rotor.tip_clearance": Quantity(value=0.30, unit="mm")},
        geometry_hash="a" * 64,
        material_hash="b" * 64,
    )

    variant = baseline.create_variant(
        variant_id="clearance-036",
        changes={"rotor.tip_clearance": Quantity(value=0.36, unit="mm")},
        author="engineer",
        reason="increase hot clearance margin",
        created_at=datetime(2026, 9, 9, tzinfo=UTC),
    )

    assert baseline.parameters["rotor.tip_clearance"].value == 0.30
    assert variant.parent_variant_id == "baseline"
    assert variant.change_record is not None
    assert variant.change_record.changed_fields["rotor.tip_clearance"].before.value == 0.30
    assert variant.change_record.changed_fields["rotor.tip_clearance"].after.value == 0.36
    with pytest.raises(ValidationError):
        variant.variant_id = "mutated"  # type: ignore[misc]


def test_computation_node_key_changes_only_for_physics_dependencies() -> None:
    base = ComputationNode(
        node_type="edf.analytical",
        inputs={"diameter_m": 0.07, "shaft_power_w": 900.0},
        dependencies={"geometry": "a" * 64, "material": "b" * 64},
        implementation_version="1.0",
    )
    reordered = ComputationNode(
        node_type="edf.analytical",
        inputs={"shaft_power_w": 900.0, "diameter_m": 0.07},
        dependencies={"material": "b" * 64, "geometry": "a" * 64},
        implementation_version="1.0",
    )
    changed = base.model_copy(update={"dependencies": {"geometry": "c" * 64}})

    assert base.cache_key == reordered.cache_key
    assert changed.cache_key != base.cache_key
