"""Canonical flying-vehicle state: frames, mass properties, flight quantities.

One immutable, hashable model carries the complete generic physical state of a
flying vehicle: declared reference frames, aerodynamic reference quantities,
mass/centre-of-gravity/inertia, rig-body motion and attitude, unit-safe flight
quantities, atmosphere/gravity references, generic controls, and six-axis loads.
It is deliberately application-agnostic: no fixed-wing, rotorcraft, or
multi-rotor concept is mandatory.

The canonical serialization and hash are mirrored byte-for-byte by
``packages/schema/src/vehicle_state.ts``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, cast

from aeroworkbench_core.types import FidelityLevel, Provenance, ResultSource

from .canonical import content_digest, normalize_numbers
from .derived import DerivedQuantity, dynamic_pressure, mach_number, weight_force
from .frames import FRAME_CONVENTIONS, Frame, frame_index
from .state import (
    AtmosphereReference,
    Attitude,
    Controls,
    FlightQuantities,
    FlightState,
    ForceMoment,
    InertiaTensor,
    MassProperties,
    ReferenceGeometry,
)
from .units import Quantity, Vec3, dimension_of, si_unit_for_dimension

SCHEMA_VERSION = 1

REFERENCE_SECTION = "geometry"
MOTION_SECTION = "motionFrames"
MASS_SECTION = "parameters"
OPERATING_SECTION = "operatingPoints"


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"EXPECTED_OBJECT:{label}")
    return value


def _sequence(value: Any, label: str) -> Sequence[Any]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ValueError(f"EXPECTED_ARRAY:{label}")
    return cast(Sequence[Any], value)


def _string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"EXPECTED_NONEMPTY_STRING:{label}")
    return value


def _optional_string(value: Any, label: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"EXPECTED_STRING:{label}")
    return value


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"EXPECTED_NUMBER:{label}")
    number = float(value)
    if number != number or number in (float("inf"), float("-inf")):
        raise ValueError(f"NONFINITE_NUMBER:{label}")
    return number


def _quantity(value: Any, label: str) -> Quantity | None:
    if value is None:
        return None
    item = _mapping(value, label)
    if "unit" in item:
        value = _number(item.get("value"), label)
        return Quantity(value=value, unit=_string(item["unit"], f"{label}.unit"))
    if "valueSI" in item:
        dimension = _string(item.get("dimension"), f"{label}.dimension")
        number = _number(item.get("valueSI"), label)
        return _quantity_from_si(number, dimension)
    raise ValueError(f"QUANTITY_NEEDS_VALUE_AND_UNIT:{label}")


def _quantity_from_si(value_si: float, dimension: str) -> Quantity:
    return Quantity(value=value_si, unit=si_unit_for_dimension(dimension))


def _vec3(value: Any, label: str) -> Vec3 | None:
    if value is None:
        return None
    item = _mapping(value, label)
    frame = _string(item.get("frame"), f"{label}.frame")
    if "unit" in item:
        return Vec3(
            x=_number(item.get("x"), f"{label}.x"),
            y=_number(item.get("y"), f"{label}.y"),
            z=_number(item.get("z"), f"{label}.z"),
            unit=_string(item["unit"], f"{label}.unit"),
            frame=frame,
        )
    dimension = _string(item.get("dimension"), f"{label}.dimension")
    unit = si_unit_for_dimension(dimension)
    return Vec3(
        x=_number(item.get("x"), f"{label}.x"),
        y=_number(item.get("y"), f"{label}.y"),
        z=_number(item.get("z"), f"{label}.z"),
        unit=unit,
        frame=frame,
    )


def _inertia_quantity(item: Mapping[str, Any], key: str, label: str) -> Quantity:
    raw = item.get(key)
    if isinstance(raw, Mapping):
        quantity = _quantity(raw, f"{label}.{key}")
        assert quantity is not None
        return quantity
    return _quantity_from_si(_number(raw, f"{label}.{key}"), "moment_of_inertia")


def _named_quantities(value: Any, label: str) -> tuple[tuple[str, Quantity], ...]:
    if value is None:
        return ()
    mapping = _mapping(value, label)
    items: list[tuple[str, Quantity]] = []
    for name, raw in mapping.items():
        quantity = _quantity(raw, f"{label}.{name}")
        assert quantity is not None
        items.append((str(name), quantity))
    return tuple(items)


def _frame(value: Any, label: str) -> Frame:
    item = _mapping(value, label)
    return Frame(
        frame_id=_string(item.get("id"), f"{label}.id"),
        kind=_string(item.get("kind"), f"{label}.kind"),
        parent=_optional_string(item.get("parent"), f"{label}.parent"),
        convention=_optional_string(item.get("convention"), f"{label}.convention"),
        parameters=_named_quantities(item.get("parameters"), f"{label}.parameters"),
    )


def _attitude(value: Any, label: str) -> Attitude:
    item = _mapping(value, label)
    quaternion_raw = item.get("quaternion")
    quaternion: tuple[float, float, float, float] | None = None
    if quaternion_raw is not None:
        components = tuple(
            _number(component, f"{label}.quaternion[{index}]")
            for index, component in enumerate(_sequence(quaternion_raw, f"{label}.quaternion"))
        )
        if len(components) != 4:
            raise ValueError(f"ATTITUDE_QUATERNION_REQUIRED:{label}")
        quaternion = (components[0], components[1], components[2], components[3])
    return Attitude(
        from_frame=_string(item.get("fromFrame"), f"{label}.fromFrame"),
        to_frame=_string(item.get("toFrame"), f"{label}.toFrame"),
        convention=_string(item.get("convention"), f"{label}.convention"),
        angles=_named_quantities(item.get("angles"), f"{label}.angles"),
        quaternion=quaternion,
    )


def _flight_quantities(value: Any, label: str) -> FlightQuantities:
    item = _mapping(value, label)
    airspeed = _mapping(item.get("airspeed", {}), f"{label}.airspeed")
    return FlightQuantities(
        altitude=_quantity(item.get("altitude"), f"{label}.altitude"),
        calibrated_airspeed=_quantity(airspeed.get("calibrated"), f"{label}.airspeed.calibrated"),
        equivalent_airspeed=_quantity(airspeed.get("equivalent"), f"{label}.airspeed.equivalent"),
        true_airspeed=_quantity(airspeed.get("true"), f"{label}.airspeed.true"),
        mach=_quantity(item.get("mach"), f"{label}.mach"),
        dynamic_pressure=_quantity(item.get("dynamicPressure"), f"{label}.dynamicPressure"),
        angle_of_attack=_quantity(item.get("angleOfAttack"), f"{label}.angleOfAttack"),
        sideslip=_quantity(item.get("sideslip"), f"{label}.sideslip"),
        load_factor=_quantity(item.get("loadFactor"), f"{label}.loadFactor"),
        reynolds=_quantity(item.get("reynolds"), f"{label}.reynolds"),
    )


def _atmosphere(value: Any, label: str) -> AtmosphereReference:
    item = _mapping(value, label)
    return AtmosphereReference(
        model=_string(item.get("model"), f"{label}.model"),
        reference_altitude=_quantity(item.get("referenceAltitude"), f"{label}.referenceAltitude"),
        density=_quantity(item.get("density"), f"{label}.density"),
        temperature=_quantity(item.get("temperature"), f"{label}.temperature"),
        pressure=_quantity(item.get("pressure"), f"{label}.pressure"),
        speed_of_sound=_quantity(item.get("speedOfSound"), f"{label}.speedOfSound"),
        gas_constant=_quantity(item.get("gasConstant"), f"{label}.gasConstant"),
        gravity=_quantity(item.get("gravity"), f"{label}.gravity"),
    )


def _mass_properties(value: Any, label: str) -> MassProperties:
    item = _mapping(value, label)
    mass = _quantity(item.get("mass"), f"{label}.mass")
    assert mass is not None
    cg = _vec3(item.get("cg"), f"{label}.cg")
    assert cg is not None
    inertia_item = _mapping(item.get("inertia"), f"{label}.inertia")
    inertia = InertiaTensor(
        ixx=_inertia_quantity(inertia_item, "ixx", f"{label}.inertia"),
        iyy=_inertia_quantity(inertia_item, "iyy", f"{label}.inertia"),
        izz=_inertia_quantity(inertia_item, "izz", f"{label}.inertia"),
        ixy=_inertia_quantity(inertia_item, "ixy", f"{label}.inertia"),
        ixz=_inertia_quantity(inertia_item, "ixz", f"{label}.inertia"),
        iyz=_inertia_quantity(inertia_item, "iyz", f"{label}.inertia"),
        frame=_string(inertia_item.get("frame"), f"{label}.inertia.frame"),
    )
    return MassProperties(mass=mass, cg=cg, inertia=inertia)


def _reference(value: Any, label: str) -> ReferenceGeometry:
    item = _mapping(value, label)
    return ReferenceGeometry(
        frame=_string(item.get("frame"), f"{label}.frame"),
        area=_quantity(item.get("area"), f"{label}.area"),
        span=_quantity(item.get("span"), f"{label}.span"),
        chord=_quantity(item.get("chord"), f"{label}.chord"),
        aerodynamic_reference_point=_vec3(
            item.get("aerodynamicReferencePoint"), f"{label}.aerodynamicReferencePoint"
        ),
    )


def _controls(value: Any, label: str) -> Controls:
    item = _mapping(value, label)
    return Controls(
        surface_deflections=_named_quantities(
            item.get("surfaceDeflections"), f"{label}.surfaceDeflections"
        ),
        throttle=_quantity(item.get("throttle"), f"{label}.throttle"),
        rpm=_quantity(item.get("rpm"), f"{label}.rpm"),
        collective=_quantity(item.get("collective"), f"{label}.collective"),
        cyclic=_named_quantities(item.get("cyclic"), f"{label}.cyclic"),
        tilt=_named_quantities(item.get("tilt"), f"{label}.tilt"),
    )


def _loads(value: Any, label: str) -> ForceMoment | None:
    if value is None:
        return None
    item = _mapping(value, label)
    force = _vec3(item.get("force"), f"{label}.force")
    moment = _vec3(item.get("moment"), f"{label}.moment")
    reference_point = _vec3(item.get("referencePoint"), f"{label}.referencePoint")
    assert force is not None and moment is not None and reference_point is not None
    return ForceMoment(
        force=force,
        moment=moment,
        reference_point=reference_point,
        axes_frame=_string(item.get("axesFrame"), f"{label}.axesFrame"),
        sign_convention=_string(item.get("signConvention"), f"{label}.signConvention"),
    )


@dataclass(frozen=True, slots=True)
class FlyingVehicleState:
    """Immutable canonical flying-vehicle state."""

    vehicle_id: str
    architecture_type: str
    reference: ReferenceGeometry
    frames: tuple[Frame, ...]
    mass_properties: MassProperties
    flight: FlightState
    controls: Controls
    loads: ForceMoment | None = None
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(f"SCHEMA_VERSION_UNSUPPORTED:{self.schema_version}")
        if not self.vehicle_id.strip():
            raise ValueError("VEHICLE_ID_REQUIRED")
        if not self.architecture_type.strip():
            raise ValueError("ARCHITECTURE_TYPE_REQUIRED")
        index = frame_index(self.frames)
        self._validate_frame_references(index)
        self._validate_conventions(index)

    def _require_frame(self, index: Mapping[str, Frame], frame_id: str, label: str) -> None:
        if frame_id not in index:
            raise ValueError(f"UNKNOWN_FRAME:{label}:{frame_id}")

    def _validate_frame_references(self, index: Mapping[str, Frame]) -> None:
        self._require_frame(index, self.reference.frame, "reference")
        if self.reference.aerodynamic_reference_point is not None:
            self._require_frame(
                index, self.reference.aerodynamic_reference_point.frame, "referencePoint"
            )
        self._require_frame(index, self.mass_properties.cg.frame, "cg")
        self._require_frame(index, self.mass_properties.inertia.frame, "inertia")
        self._require_frame(index, self.flight.position.frame, "position")
        self._require_frame(index, self.flight.velocity.frame, "velocity")
        self._require_frame(index, self.flight.angular_rates.frame, "angularRates")
        self._require_frame(index, self.flight.attitude.from_frame, "attitude.fromFrame")
        self._require_frame(index, self.flight.attitude.to_frame, "attitude.toFrame")
        if self.loads is not None:
            self._require_frame(index, self.loads.force.frame, "loads.force")
            self._require_frame(index, self.loads.moment.frame, "loads.moment")
            self._require_frame(index, self.loads.reference_point.frame, "loads.referencePoint")
            self._require_frame(index, self.loads.axes_frame, "loads.axesFrame")

    def _validate_conventions(self, index: Mapping[str, Frame]) -> None:
        attitude = self.flight.attitude
        target = index[attitude.to_frame]
        if target.convention is not None and attitude.convention != target.convention:
            raise ValueError(
                f"FRAME_CONVENTION_MISMATCH:{attitude.to_frame}:"
                f"{attitude.convention}:{target.convention}"
            )
        if attitude.convention not in FRAME_CONVENTIONS[target.kind]:
            raise ValueError(
                f"ATTITUDE_CONVENTION_NOT_ALLOWED:{attitude.to_frame}:{attitude.convention}"
            )

    def canonical_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "schemaVersion": self.schema_version,
            "vehicleId": self.vehicle_id,
            "architectureType": self.architecture_type,
            "reference": self.reference.canonical(),
            "frames": [
                frame.canonical() for frame in sorted(self.frames, key=lambda f: f.frame_id)
            ],
            "massProperties": self.mass_properties.canonical(),
            "flight": self.flight.canonical(),
            "controls": self.controls.canonical(),
            "loads": None if self.loads is None else self.loads.canonical(),
        }
        return cast(dict[str, object], normalize_numbers(payload))

    @property
    def state_hash(self) -> str:
        return content_digest(self.canonical_payload())

    def derived_quantities(self) -> tuple[DerivedQuantity, ...]:
        results: list[DerivedQuantity] = []
        truth = self.flight.flight.true_airspeed
        atmosphere = self.flight.atmosphere
        if truth is not None and atmosphere.speed_of_sound is not None:
            results.append(mach_number(truth, atmosphere.speed_of_sound))
        if truth is not None and atmosphere.density is not None:
            results.append(dynamic_pressure(atmosphere.density, truth))
        if atmosphere.gravity is not None:
            results.append(weight_force(self.mass_properties.mass, atmosphere.gravity))
        return tuple(results)


def vehicle_state_from_payload(payload: Mapping[str, Any]) -> FlyingVehicleState:
    """Build and validate a vehicle state from its canonical JSON document."""
    document = _mapping(payload, "vehicleState")
    version = document.get("schemaVersion")
    if version is not None and not isinstance(version, bool) and isinstance(version, int):
        schema_version = version
    else:
        schema_version = SCHEMA_VERSION
    frames = tuple(
        _frame(item, f"frames[{index}]")
        for index, item in enumerate(_sequence(document.get("frames") or [], "frames"))
    )
    flight_item = _mapping(document.get("flight"), "flight")
    flight = FlightState(
        position=_vec3_required(flight_item.get("position"), "flight.position"),
        attitude=_attitude(flight_item.get("attitude"), "flight.attitude"),
        velocity=_vec3_required(flight_item.get("velocity"), "flight.velocity"),
        angular_rates=_vec3_required(flight_item.get("angularRates"), "flight.angularRates"),
        flight=_flight_quantities(flight_item.get("flight"), "flight.flight"),
        atmosphere=_atmosphere(flight_item.get("atmosphere"), "flight.atmosphere"),
    )
    return FlyingVehicleState(
        vehicle_id=_string(document.get("vehicleId"), "vehicleId"),
        architecture_type=_string(document.get("architectureType"), "architectureType"),
        reference=_reference(document.get("reference"), "reference"),
        frames=frames,
        mass_properties=_mass_properties(document.get("massProperties"), "massProperties"),
        flight=flight,
        controls=_controls(document.get("controls"), "controls"),
        loads=_loads(document.get("loads"), "loads"),
        schema_version=schema_version,
    )


def _vec3_required(value: Any, label: str) -> Vec3:
    result = _vec3(value, label)
    if result is None:
        raise ValueError(f"VECTOR_REQUIRED:{label}")
    return result


def _as_state(value: FlyingVehicleState | Mapping[str, Any]) -> FlyingVehicleState:
    if isinstance(value, FlyingVehicleState):
        return value
    return vehicle_state_from_payload(value)


def canonical_vehicle_state(
    value: FlyingVehicleState | Mapping[str, Any],
) -> dict[str, object]:
    """Canonical, deterministic payload for a vehicle state (or its raw JSON)."""
    return _as_state(value).canonical_payload()


def vehicle_state_hash(value: FlyingVehicleState | Mapping[str, Any]) -> str:
    """Deterministic SHA-256 content hash of the full vehicle state."""
    return content_digest(canonical_vehicle_state(value))


def vehicle_state_provenance(
    value: FlyingVehicleState | Mapping[str, Any],
) -> Provenance:
    """Schema identity/provenance for any downstream result derived from the model."""
    state = _as_state(value)
    return Provenance.from_inputs(
        source=ResultSource.ANALYTICAL,
        model="airframe-vehicle-state",
        model_version=str(state.schema_version),
        fidelity=FidelityLevel.ANALYTICAL,
        inputs=state.canonical_payload(),
        assumptions=(
            "Canonical frame/mass/flight/control/load schema only; no solver execution.",
        ),
    )


def _sections(before: FlyingVehicleState, after: FlyingVehicleState) -> set[str]:
    sections: set[str] = set()
    if before.reference.canonical() != after.reference.canonical():
        sections.add(REFERENCE_SECTION)
    before_motion = (
        [frame.canonical() for frame in before.frames],
        before.flight.position.canonical(),
        before.flight.attitude.canonical(),
        before.flight.velocity.canonical(),
        before.flight.angular_rates.canonical(),
    )
    after_motion = (
        [frame.canonical() for frame in after.frames],
        after.flight.position.canonical(),
        after.flight.attitude.canonical(),
        after.flight.velocity.canonical(),
        after.flight.angular_rates.canonical(),
    )
    if before_motion != after_motion:
        sections.add(MOTION_SECTION)
    if before.mass_properties.canonical() != after.mass_properties.canonical():
        sections.add(MASS_SECTION)
    before_operating = (
        before.flight.flight.canonical(),
        before.flight.atmosphere.canonical(),
        None if before.loads is None else before.loads.canonical(),
    )
    after_operating = (
        after.flight.flight.canonical(),
        after.flight.atmosphere.canonical(),
        None if after.loads is None else after.loads.canonical(),
    )
    if before_operating != after_operating:
        sections.add(OPERATING_SECTION)
    if before.controls.canonical() != after.controls.canonical():
        sections.add(MASS_SECTION)
    return sections


def vehicle_state_change_sections(
    before: FlyingVehicleState | Mapping[str, Any],
    after: FlyingVehicleState | Mapping[str, Any],
) -> tuple[str, ...]:
    """Classify a vehicle-state delta onto the existing design-section vocabulary."""
    return tuple(sorted(_sections(_as_state(before), _as_state(after))))


def airframe_invalidated_families(
    before: FlyingVehicleState | Mapping[str, Any],
    after: FlyingVehicleState | Mapping[str, Any],
) -> tuple[str, ...]:
    """Map a vehicle-state delta to invalidated node families via the coupling DAG."""
    from aeroworkbench_coupling.dag import invalidated_families

    families = invalidated_families(vehicle_state_change_sections(before, after))
    return tuple(str(family) for family in families)


def vehicle_design_parameters(
    value: FlyingVehicleState | Mapping[str, Any],
) -> dict[str, object]:
    """Subset of the vehicle state that the existing design contract can carry.

    Only quantities whose unit is supported by ``aeroworkbench_core`` are exposed,
    so a vehicle state can round-trip through a ``PhysicalDesignState`` without a
    parallel unit framework.
    """
    from aeroworkbench_core.types import Quantity as DesignQuantity

    state = _as_state(value)
    parameters: dict[str, object] = {}

    def add_length(name: str, quantity: Quantity | None) -> None:
        if quantity is None:
            return
        if dimension_of(quantity.unit) != "length":
            return
        parameters[name] = DesignQuantity(value=quantity.value_si, unit="m")

    add_length("reference_span", state.reference.span)
    add_length("reference_chord", state.reference.chord)
    add_length("altitude", state.flight.flight.altitude)
    parameters["cg_x"] = DesignQuantity(value=state.mass_properties.cg.value_si[0], unit="m")
    parameters["cg_y"] = DesignQuantity(value=state.mass_properties.cg.value_si[1], unit="m")
    parameters["cg_z"] = DesignQuantity(value=state.mass_properties.cg.value_si[2], unit="m")
    if state.loads is not None and dimension_of(state.loads.force.unit) == "force":
        force_si = state.loads.force.value_si
        parameters["load_fx"] = DesignQuantity(value=force_si[0], unit="N")
        parameters["load_fy"] = DesignQuantity(value=force_si[1], unit="N")
        parameters["load_fz"] = DesignQuantity(value=force_si[2], unit="N")
    return parameters
