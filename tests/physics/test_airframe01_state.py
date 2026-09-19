"""AIRFRAME 01: canonical flying-vehicle state, frames, unit-safe flight quantities.

The fixtures under ``tests/airframe/state`` are schema-only portability
documents. This module proves the canonical hash is unit-invariant and matches
the TypeScript mirror (``tests/unit/airframe01_state.test.ts``), that frame
transforms are deterministic, that mixed/unknown conventions fail closed, and
that the full mass properties and six-axis loads round-trip through the existing
design-revision contract.
"""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from aeroworkbench_airframe import (
    FRAME_CONVENTIONS,
    IDENTITY,
    Attitude,
    Frame,
    MassProperties,
    Quantity,
    airframe_invalidated_families,
    canonical_vehicle_state,
    dynamic_pressure,
    equivalent_airspeed,
    mach_number,
    matmul,
    rotate_vector,
    rotation_between,
    transpose,
    vehicle_design_parameters,
    vehicle_state_change_sections,
    vehicle_state_from_payload,
    vehicle_state_hash,
    vehicle_state_provenance,
    weight_force,
)
from aeroworkbench_core.design import PhysicalDesignState
from aeroworkbench_core.types import Quantity as DesignQuantity
from aeroworkbench_coupling.dag import CHANGE_IMPACT

_TESTS_ROOT = Path(__file__).resolve().parents[1]
_FIXTURE_DIR = _TESTS_ROOT / "airframe" / "state"
_EXPECTED_HASHES: dict[str, str] = json.loads(
    (_FIXTURE_DIR / "expected_hashes.json").read_text(encoding="utf-8")
)
_MINIMAL = "minimal_vehicle_state.json"
_EQUIVALENT = "equivalent_units_vehicle_state.json"


def load_fixture(name: str) -> dict[str, Any]:
    return json.loads((_FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _flat(matrix: tuple[tuple[float, ...], ...]) -> list[float]:
    return [component for row in matrix for component in row]


def test_airframe01_every_fixture_validates_and_matches_shared_hash() -> None:
    for name in (_MINIMAL, _EQUIVALENT):
        payload = load_fixture(name)
        state = vehicle_state_from_payload(payload)
        expected = _EXPECTED_HASHES[state.vehicle_id]
        assert vehicle_state_hash(state) == expected
        assert state.state_hash == expected


def test_airframe01_equivalent_units_hash_identically() -> None:
    assert vehicle_state_hash(load_fixture(_MINIMAL)) == vehicle_state_hash(
        load_fixture(_EQUIVALENT)
    )


def test_airframe01_canonical_roundtrip_is_lossless() -> None:
    for name in (_MINIMAL, _EQUIVALENT):
        state = vehicle_state_from_payload(load_fixture(name))
        canonical = canonical_vehicle_state(state)
        rebuilt = vehicle_state_from_payload(canonical)
        assert canonical_vehicle_state(rebuilt) == canonical
        assert vehicle_state_hash(rebuilt) == vehicle_state_hash(state)


def test_airframe01_hash_is_key_and_array_order_independent() -> None:
    payload = load_fixture(_MINIMAL)
    reordered = {
        "loads": payload["loads"],
        "controls": payload["controls"],
        "flight": payload["flight"],
        "massProperties": payload["massProperties"],
        "frames": list(reversed(payload["frames"])),
        "reference": payload["reference"],
        "architectureType": payload["architectureType"],
        "vehicleId": payload["vehicleId"],
        "schemaVersion": payload["schemaVersion"],
    }
    assert vehicle_state_hash(reordered) == vehicle_state_hash(payload)


def test_airframe01_mass_properties_and_six_axis_loads_round_trip() -> None:
    state = vehicle_state_from_payload(load_fixture(_MINIMAL))
    assert isinstance(state.mass_properties, MassProperties)
    assert state.mass_properties.mass.value_si == pytest.approx(1.5)
    assert state.mass_properties.inertia.ixx.value_si == pytest.approx(0.02)
    assert state.mass_properties.inertia.ixz.value_si == pytest.approx(0.001)
    loads = state.loads
    assert loads is not None
    assert loads.sign_convention == "body_axes_aerodynamic"
    assert loads.axes_frame == "body"
    assert loads.force.value_si == pytest.approx((12.0, 0.0, -4.0))
    assert loads.moment.value_si == pytest.approx((0.1, 0.5, 0.02))
    canonical = canonical_vehicle_state(state)
    rebuilt = vehicle_state_from_payload(canonical)
    assert rebuilt.mass_properties.canonical() == state.mass_properties.canonical()
    assert rebuilt.loads is not None
    assert rebuilt.loads.canonical() == loads.canonical()


def test_airframe01_frame_transforms_are_deterministic_and_orthonormal() -> None:
    state = vehicle_state_from_payload(load_fixture(_MINIMAL))
    frames = state.frames
    assert rotation_between(frames, "inertial", "inertial") == IDENTITY
    body_from_ned = rotation_between(frames, "ned", "body")
    assert _flat(matmul(body_from_ned, transpose(body_from_ned))) == pytest.approx(
        _flat(IDENTITY), abs=1e-12
    )
    assert _flat(rotation_between(frames, "body", "inertial")) == pytest.approx(
        _flat(transpose(rotation_between(frames, "inertial", "body"))), abs=1e-12
    )

    yaw_only = (
        Frame("inertial", "inertial"),
        Frame("ecef", "ecef", "inertial"),
        Frame(
            "ned",
            "ned",
            "ecef",
            "geodetic",
            (("latitude", Quantity(0.0, "deg")), ("longitude", Quantity(0.0, "deg"))),
        ),
        Frame(
            "body",
            "body",
            "ned",
            "euler_321",
            (
                ("yaw", Quantity(90.0, "deg")),
                ("pitch", Quantity(0.0, "deg")),
                ("roll", Quantity(0.0, "deg")),
            ),
        ),
    )
    assert _flat(rotation_between(yaw_only, "ned", "body")) == pytest.approx(
        _flat(((0.0, -1.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0))), abs=1e-12
    )


def test_airframe01_rotate_vector_preserves_magnitude_and_dimension() -> None:
    state = vehicle_state_from_payload(load_fixture(_MINIMAL))
    velocity = state.flight.velocity
    rotated = rotate_vector(velocity, state.frames, "wind")
    assert rotated.frame == "wind"
    assert rotated.dimension == "velocity"
    source = velocity.value_si
    target = rotated.value_si
    assert sum(component * component for component in target) == pytest.approx(
        sum(component * component for component in source)
    )


def test_airframe01_attitude_quaternion_convention_round_trips() -> None:
    payload = deepcopy(load_fixture(_MINIMAL))
    for frame in payload["frames"]:
        if frame["id"] == "body":
            frame["convention"] = "quaternion"
            frame["parameters"] = {
                "qw": {"value": 1.0, "unit": "dimensionless"},
                "qx": {"value": 0.0, "unit": "dimensionless"},
                "qy": {"value": 0.0, "unit": "dimensionless"},
                "qz": {"value": 0.0, "unit": "dimensionless"},
            }
    payload["flight"]["attitude"] = {
        "fromFrame": "ned",
        "toFrame": "body",
        "convention": "quaternion",
        "angles": None,
        "quaternion": [1.0, 0.0, 0.0, 0.0],
    }
    state = vehicle_state_from_payload(payload)
    attitude = state.flight.attitude
    assert isinstance(attitude, Attitude)
    assert attitude.convention == "quaternion"
    assert _flat(rotation_between(state.frames, "ned", "body")) == pytest.approx(
        _flat(IDENTITY), abs=1e-12
    )


def test_airframe01_mixed_coordinate_conventions_fail_closed() -> None:
    mismatch = deepcopy(load_fixture(_MINIMAL))
    mismatch["flight"]["attitude"]["convention"] = "alpha_beta"
    with pytest.raises(ValueError, match="FRAME_CONVENTION_MISMATCH|ATTITUDE_CONVENTION"):
        vehicle_state_from_payload(mismatch)

    undeclared = deepcopy(load_fixture(_MINIMAL))
    undeclared["flight"]["velocity"]["frame"] = "geodetic"
    with pytest.raises(ValueError, match="UNKNOWN_FRAME"):
        vehicle_state_from_payload(undeclared)

    bad_parent = deepcopy(load_fixture(_MINIMAL))
    for frame in bad_parent["frames"]:
        if frame["id"] == "wind":
            frame["parent"] = "ned"
    with pytest.raises(ValueError, match="FRAME_PARENT_KIND_MISMATCH"):
        vehicle_state_from_payload(bad_parent)

    unknown_kind = deepcopy(load_fixture(_MINIMAL))
    for frame in unknown_kind["frames"]:
        if frame["id"] == "ecef":
            frame["kind"] = "geocentric"
    with pytest.raises(ValueError, match="UNKNOWN_FRAME_KIND"):
        vehicle_state_from_payload(unknown_kind)


def test_airframe01_invalid_units_and_dimensions_fail_closed() -> None:
    unknown_unit = deepcopy(load_fixture(_MINIMAL))
    unknown_unit["massProperties"]["mass"]["unit"] = "furlongs"
    with pytest.raises(ValueError, match="UNKNOWN_UNIT"):
        vehicle_state_from_payload(unknown_unit)

    wrong_dimension = deepcopy(load_fixture(_MINIMAL))
    wrong_dimension["flight"]["flight"]["altitude"]["unit"] = "N"
    with pytest.raises(ValueError, match="QUANTITY_DIMENSION_MISMATCH"):
        vehicle_state_from_payload(wrong_dimension)


def test_airframe01_invalid_mass_and_control_values_fail_closed() -> None:
    nonpositive_mass = deepcopy(load_fixture(_MINIMAL))
    nonpositive_mass["massProperties"]["mass"]["value"] = 0.0
    with pytest.raises(ValueError, match="NONPOSITIVE_MASS"):
        vehicle_state_from_payload(nonpositive_mass)

    throttle = deepcopy(load_fixture(_MINIMAL))
    throttle["controls"]["throttle"]["value"] = 1.5
    with pytest.raises(ValueError, match="THROTTLE_OUT_OF_RANGE"):
        vehicle_state_from_payload(throttle)

    quaternion = deepcopy(load_fixture(_MINIMAL))
    quaternion["flight"]["attitude"] = {
        "fromFrame": "ned",
        "toFrame": "body",
        "convention": "quaternion",
        "angles": None,
        "quaternion": [1.0, 1.0, 1.0, 1.0],
    }
    with pytest.raises(ValueError, match="ATTITUDE_CONVENTION_NOT_ALLOWED|QUATERNION_NOT_UNIT"):
        vehicle_state_from_payload(quaternion)


def test_airframe01_derived_quantities_carry_analytical_provenance() -> None:
    state = vehicle_state_from_payload(load_fixture(_MINIMAL))
    derived = {item.name: item for item in state.derived_quantities()}
    assert set(derived) == {"mach", "dynamicPressure", "weight"}
    for item in derived.values():
        assert item.provenance.source.value == "analytical"
        assert len(item.provenance.inputs_hash) == 64
        assert item.provenance.solver_name is None
        assert item.provenance.assumptions
    assert derived["dynamicPressure"].quantity.value_si == pytest.approx(540.0)
    assert derived["mach"].quantity.value_si == pytest.approx(30.0 / 340.29)
    assert derived["weight"].quantity.value_si == pytest.approx(1.5 * 9.80665)

    eas = equivalent_airspeed(
        Quantity(30.0, "m/s"), Quantity(1.2, "kg/m3"), Quantity(1.2, "kg/m3")
    )
    assert eas.quantity.value_si == pytest.approx(30.0)
    assert (
        mach_number(Quantity(340.29, "m/s"), Quantity(340.29, "m/s")).quantity.value_si
        == pytest.approx(1.0)
    )
    assert (
        dynamic_pressure(Quantity(1.2, "kg/m3"), Quantity(30.0, "m/s")).quantity.value_si
        == pytest.approx(540.0)
    )
    assert (
        weight_force(Quantity(2.0, "kg"), Quantity(9.81, "m/s2")).quantity.value_si
        == pytest.approx(19.62)
    )


def test_airframe01_provenance_records_schema_identity() -> None:
    state = vehicle_state_from_payload(load_fixture(_MINIMAL))
    provenance = vehicle_state_provenance(state)
    assert provenance.source.value == "analytical"
    assert provenance.model == "airframe-vehicle-state"
    assert len(provenance.inputs_hash) == 64
    assert provenance.solver_name is None


def test_airframe01_state_changes_project_onto_existing_invalidation() -> None:
    before = vehicle_state_from_payload(load_fixture(_MINIMAL))
    changed = deepcopy(load_fixture(_MINIMAL))
    changed["reference"]["span"]["value"] = 0.7
    sections = vehicle_state_change_sections(before, changed)
    assert sections == ("geometry",)
    for section in sections:
        assert section in CHANGE_IMPACT
    families = airframe_invalidated_families(before, changed)
    assert "mesh" in families and "analysis" in families

    motion = deepcopy(load_fixture(_MINIMAL))
    motion["flight"]["attitude"]["angles"]["yaw"]["value"] = 20.0
    assert vehicle_state_change_sections(before, motion) == ("motionFrames",)

    operating = deepcopy(load_fixture(_MINIMAL))
    operating["flight"]["flight"]["altitude"]["value"] = 600.0
    assert vehicle_state_change_sections(before, operating) == ("operatingPoints",)

    mass = deepcopy(load_fixture(_MINIMAL))
    mass["massProperties"]["mass"]["value"] = 1.6
    assert vehicle_state_change_sections(before, mass) == ("parameters",)


def test_airframe01_vehicle_fixture_round_trips_through_design_revision() -> None:
    state = vehicle_state_from_payload(load_fixture(_MINIMAL))
    equivalent = vehicle_state_from_payload(load_fixture(_EQUIVALENT))
    parameters = vehicle_design_parameters(state)
    assert parameters["altitude"] == DesignQuantity(value=500.0, unit="m")
    assert parameters["reference_span"] == DesignQuantity(value=0.6, unit="m")
    design = PhysicalDesignState(
        design_id="airframe01",
        variant_id="v1",
        parameters=parameters,  # type: ignore[arg-type]
        geometry_hash="a" * 64,
        material_hash="b" * 64,
    )
    rebuilt = PhysicalDesignState.model_validate_json(design.model_dump_json())
    assert rebuilt == design
    assert rebuilt.content_hash == design.content_hash
    assert vehicle_design_parameters(equivalent) == parameters

    variant = design.create_variant(
        variant_id="v2",
        changes={"altitude": DesignQuantity(value=600.0, unit="m")},
        author="airframe01",
        reason="climb",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    assert variant.parent_variant_id == "v1"
    assert variant.parameters["altitude"].si_value == pytest.approx(600.0)


def test_airframe01_unrelated_document_fails_closed() -> None:
    with pytest.raises(ValueError):
        canonical_vehicle_state({"vehicleId": "x"})


def test_airframe01_frame_conventions_cover_declared_kinds() -> None:
    state = vehicle_state_from_payload(load_fixture(_MINIMAL))
    declared = {frame.kind for frame in state.frames}
    assert {"inertial", "ecef", "ned", "body", "wind"} <= declared
    assert FRAME_CONVENTIONS["wind"] == ("alpha_beta",)
