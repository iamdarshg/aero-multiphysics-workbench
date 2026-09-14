"""Generic annular-duct system builder with configurable zone counts.

This is a *generic* facility: an annular flow passage with an arbitrary
number of rotating zones, stationary zones between them, a duct shell, and a
configurable set of solid bodies (shafts/hubs). It encodes no application,
stage count, or vehicle assumptions; a ducted fan is merely one instance.
"""

from __future__ import annotations

from .parameters import ParameterDef, ParameterSet
from .parametric import ParametricModel


def build_duct_system(
    *,
    outer_diameter_mm: float = 80.0,
    inner_diameter_mm: float = 70.0,
    length_mm: float = 120.0,
    hub_diameter_mm: float = 20.0,
    n_rotating: int = 2,
    n_solids: int = 2,
    zone_length_mm: float = 18.0,
    zone_gap_mm: float = 6.0,
) -> ParametricModel:
    """Build a ducted multi-zone system with ``n_rotating`` rotor zones.

    Components:

    - ``duct``: stationary annular shell (outer minus inner cylinder).
    - ``fluid``: annular flow volume (inner cylinder minus hub cylinder).
    - ``rotor_zone_<i>``: rotating fluid disks (count = ``n_rotating``).
    - ``stator_zone_<i>``: stationary fluid rings between/around rotors.
    - ``solid_<i>``: structural bodies such as shafts or hubs.
    """

    if n_rotating < 1:
        raise ValueError("N_ROTATING_MUST_BE_AT_LEAST_ONE")
    if n_solids < 1:
        raise ValueError("N_SOLIDS_MUST_BE_AT_LEAST_ONE")
    if not inner_diameter_mm < outer_diameter_mm:
        raise ValueError("INNER_MUST_BE_SMALLER_THAN_OUTER")
    if not hub_diameter_mm < inner_diameter_mm:
        raise ValueError("HUB_MUST_BE_SMALLER_THAN_INNER")

    parameters = ParameterSet(
        (
            ParameterDef("outerDiameter", outer_diameter_mm),
            ParameterDef("innerDiameter", inner_diameter_mm),
            ParameterDef("length", length_mm),
            ParameterDef("hubDiameter", hub_diameter_mm),
            ParameterDef("zoneLength", zone_length_mm),
            ParameterDef("zoneGap", zone_gap_mm),
            ParameterDef("zonePitch", expression="zoneLength+zoneGap"),
        )
    )
    model = ParametricModel(f"duct-system-R{n_rotating}S{n_solids}", parameters)

    model.add_cylinder("_outer_blank", outer_diameter_mm, length_mm)
    model.add_cylinder("_inner_blank", inner_diameter_mm, length_mm)
    model.boolean("duct", "cut", "_outer_blank", "_inner_blank")

    # The flow annulus is partitioned into exact coincident axial slices: an
    # inlet section, alternating rotor/stator slices, and an outlet section.
    # Coincident (not near-coincident) faces fragment cleanly into conformal
    # mesh interfaces instead of sliver gaps.
    zones_span = n_rotating * zone_length_mm + (n_rotating - 1) * zone_gap_mm
    half = length_mm / 2.0
    if zones_span >= length_mm:
        raise ValueError("ZONE_SPAN_EXCEEDS_LENGTH")
    cursor = -zones_span / 2.0

    def _slice(name: str, z0: float, z1: float) -> None:
        height = z1 - z0
        center = (z0 + z1) / 2.0
        model.add_cylinder(
            f"_{name}_outer", inner_diameter_mm, height,
            center_mm=(0.0, 0.0, center),
        )
        model.add_cylinder(
            f"_{name}_hub", hub_diameter_mm, height,
            center_mm=(0.0, 0.0, center),
        )
        model.boolean(name, "cut", f"_{name}_outer", f"_{name}_hub")

    model.add_frame("axis", (0.0, 0.0, -half), (0.0, 0.0, 1.0))
    model.add_frame("inlet_plane", (0.0, 0.0, -half), (0.0, 0.0, 1.0))
    model.add_frame("outlet_plane", (0.0, 0.0, half), (0.0, 0.0, 1.0))
    _slice("fluid_inlet", -half, cursor)
    for index in range(n_rotating):
        _slice(f"rotor_zone_{index}", cursor, cursor + zone_length_mm)
        cursor += zone_length_mm
        if index < n_rotating - 1:
            _slice(f"stator_zone_{index}", cursor, cursor + zone_gap_mm)
            cursor += zone_gap_mm
    _slice("fluid_outlet", cursor, half)

    for index in range(n_solids):
        diameter = hub_diameter_mm - 2.0 * index
        if diameter <= 0:
            raise ValueError("SOLID_DIAMETER_EXHAUSTED")
        model.add_cylinder(
            f"solid_{index}",
            diameter,
            length_mm * (0.9 - 0.1 * index),
            center_mm=(0.0, 0.0, 0.0),
        )
    return model


def rotating_zone_names(n_rotating: int) -> tuple[str, ...]:
    return tuple(f"rotor_zone_{i}" for i in range(n_rotating))


def stationary_zone_names(n_rotating: int) -> tuple[str, ...]:
    names = ["duct", "fluid_inlet", "fluid_outlet"]
    names.extend(f"stator_zone_{i}" for i in range(n_rotating - 1))
    return tuple(names)


def fluid_zone_names(n_rotating: int) -> tuple[str, ...]:
    """All fluid-region components: inlet, rotors, stators, outlet."""

    names = ["fluid_inlet"]
    for index in range(n_rotating):
        names.append(f"rotor_zone_{index}")
        if index < n_rotating - 1:
            names.append(f"stator_zone_{index}")
    names.append("fluid_outlet")
    return tuple(names)


def solid_names(n_solids: int) -> tuple[str, ...]:
    return tuple(f"solid_{i}" for i in range(n_solids))
