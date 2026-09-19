"""Declared analytical sizing relations with explicit validity envelopes.

Every relation is an analytical or empirical screening method, never a solver
execution. Each returned :class:`SynthesisQuantity` carries the method identity,
the declared validity envelope it was evaluated inside, an inputs hash, and
provenance, so a value outside its envelope is rejected rather than trusted.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import acos, isfinite, sqrt
from typing import cast

from aeroworkbench_core.types import FidelityLevel, Provenance, ResultSource

from ..canonical import normalize_numbers
from ..units import Quantity, require_dimension

SYNTHESIS_MODEL = "airframe-initial-synthesis"
SYNTHESIS_MODEL_VERSION = "1"

METHODS: tuple[str, ...] = (
    "isa-density",
    "isa-speed-of-sound",
    "max-takeoff-mass",
    "wing-loading",
    "wing-area",
    "wing-span",
    "mean-chord",
    "aspect-ratio-choice",
    "planform-area",
    "thickness-ratio-from-volume",
    "thrust-to-weight-climb",
    "thrust-to-weight-cruise",
    "required-thrust",
    "required-power",
    "sweep-drag-divergence",
    "horizontal-tail-area",
    "dynamic-pressure",
    "range-energy-fraction",
    "requirement-reference",
)

_ASSUMPTIONS: tuple[str, ...] = (
    "Screening evidence only: analytical/empirical relation, not native solver execution.",
    "All inputs are normalized to SI before evaluation.",
)


@dataclass(frozen=True, slots=True)
class ValidityCheck:
    """One declared envelope bound evaluated against the method input."""

    name: str
    value: float
    lower: float
    upper: float
    inside: bool

    def canonical(self) -> dict[str, object]:
        return {
            "name": self.name,
            "value": self.value,
            "lower": self.lower,
            "upper": self.upper,
            "inside": self.inside,
        }


@dataclass(frozen=True, slots=True)
class MethodValidity:
    """The validity verdict of one method application."""

    method: str
    valid: bool
    checks: tuple[ValidityCheck, ...]
    violations: tuple[str, ...]
    assumptions: tuple[str, ...] = _ASSUMPTIONS

    def canonical(self) -> dict[str, object]:
        return {
            "method": self.method,
            "valid": self.valid,
            "checks": [check.canonical() for check in self.checks],
            "violations": list(self.violations),
            "assumptions": list(self.assumptions),
        }


@dataclass(frozen=True, slots=True)
class SynthesisQuantity:
    """A synthesized value with units, method identity, validity, and provenance."""

    name: str
    quantity: Quantity
    method: str
    validity: MethodValidity
    provenance: Provenance

    def canonical(self) -> dict[str, object]:
        return cast(
            dict[str, object],
            normalize_numbers(
                {
                    "name": self.name,
                    "quantity": self.quantity.canonical(),
                    "method": self.method,
                    "validity": self.validity.canonical(),
                    "provenance": self.provenance.model_dump(mode="json"),
                }
            ),
        )


def _check(name: str, value: float, lower: float, upper: float) -> ValidityCheck:
    if not isfinite(value):
        raise ValueError(f"NONFINITE_METHOD_VALUE:{name}")
    inside = lower <= value <= upper
    return ValidityCheck(name=name, value=value, lower=lower, upper=upper, inside=inside)


def _validity(method: str, checks: tuple[ValidityCheck, ...]) -> MethodValidity:
    violations = tuple(f"{check.name}:OUT_OF_ENVELOPE" for check in checks if not check.inside)
    return MethodValidity(method=method, valid=not violations, checks=checks, violations=violations)


def _provenance(method: str, inputs: dict[str, float]) -> Provenance:
    return Provenance.from_inputs(
        source=ResultSource.ANALYTICAL,
        model=f"{SYNTHESIS_MODEL}:{method}",
        model_version=SYNTHESIS_MODEL_VERSION,
        fidelity=FidelityLevel.ANALYTICAL,
        inputs=inputs,
        assumptions=_ASSUMPTIONS,
    )


def _result(
    name: str,
    value: float,
    unit: str,
    method: str,
    checks: tuple[ValidityCheck, ...],
    inputs: dict[str, float],
) -> SynthesisQuantity:
    return SynthesisQuantity(
        name=name,
        quantity=Quantity(value=value, unit=unit),
        method=method,
        validity=_validity(method, checks),
        provenance=_provenance(method, inputs),
    )


def isa_density(altitude: Quantity) -> SynthesisQuantity:
    """International Standard Atmosphere density (troposphere validity)."""
    require_dimension(altitude, "length", "altitude")
    height = altitude.value_si
    ratio = 1.0 - 0.0065 * height / 288.15
    density = 0.0 if ratio <= 0.0 else 1.225 * ratio**4.25588
    checks = (_check("altitude", height, 0.0, 11000.0),)
    return _result("density", density, "kg/m3", "isa-density", checks, {"altitude": height})


def isa_speed_of_sound(altitude: Quantity) -> SynthesisQuantity:
    """ISA speed of sound (troposphere validity)."""
    require_dimension(altitude, "length", "altitude")
    height = altitude.value_si
    temperature = 288.15 - 0.0065 * height
    speed = 340.294 * sqrt(temperature / 288.15) if temperature > 0.0 else 0.0
    checks = (_check("altitude", height, 0.0, 11000.0),)
    return _result(
        "speed_of_sound", speed, "m/s", "isa-speed-of-sound", checks, {"altitude": height}
    )


def max_takeoff_mass(payload_mass: Quantity, empty_mass_fraction: float) -> SynthesisQuantity:
    """First-order mass closure from payload and an empty-mass fraction."""
    require_dimension(payload_mass, "mass", "payloadMass")
    if not 0.0 < empty_mass_fraction < 1.0:
        raise ValueError("EMPTY_MASS_FRACTION_OUT_OF_RANGE")
    takeoff_mass = payload_mass.value_si / (1.0 - empty_mass_fraction)
    checks = (_check("emptyMassFraction", empty_mass_fraction, 0.3, 0.75),)
    return _result(
        "max_takeoff_mass",
        takeoff_mass,
        "kg",
        "max-takeoff-mass",
        checks,
        {"payloadMass": payload_mass.value_si, "emptyMassFraction": empty_mass_fraction},
    )


def wing_loading(
    stall_speed: Quantity, density: Quantity, max_lift_coefficient: float
) -> SynthesisQuantity:
    """Wing loading from stall speed: ``W/S = 0.5 * rho * V^2 * CLmax``."""
    require_dimension(stall_speed, "velocity", "stallSpeed")
    require_dimension(density, "density", "density")
    if density.value_si <= 0.0:
        raise ValueError("NONPOSITIVE_DENSITY")
    if max_lift_coefficient <= 0.0:
        raise ValueError("NONPOSITIVE_LIFT_COEFFICIENT")
    speed = stall_speed.value_si
    loading = 0.5 * density.value_si * speed * speed * max_lift_coefficient
    checks = (
        _check("stallSpeed", speed, 10.0, 120.0),
        _check("maxLiftCoefficient", max_lift_coefficient, 0.6, 3.0),
    )
    return _result(
        "wing_loading",
        loading,
        "Pa",
        "wing-loading",
        checks,
        {
            "stallSpeed": speed,
            "density": density.value_si,
            "maxLiftCoefficient": max_lift_coefficient,
        },
    )


def wing_area(weight_force: Quantity, wing_loading_quantity: Quantity) -> SynthesisQuantity:
    """Reference wing area ``S = W / (W/S)``."""
    require_dimension(weight_force, "force", "weightForce")
    require_dimension(wing_loading_quantity, "pressure", "wing_loading")
    loading = wing_loading_quantity.value_si
    if loading <= 0.0:
        raise ValueError("NONPOSITIVE_WING_LOADING")
    area = weight_force.value_si / loading
    checks = (_check("wing_loading", loading, 100.0, 5000.0),)
    return _result(
        "wing_area",
        area,
        "m2",
        "wing-area",
        checks,
        {"weightForce": weight_force.value_si, "wing_loading": loading},
    )


def wing_span(area: Quantity, aspect_ratio: float) -> SynthesisQuantity:
    """Span from area and aspect ratio: ``b = sqrt(AR * S)``."""
    require_dimension(area, "area", "wing_area")
    if aspect_ratio <= 0.0:
        raise ValueError("NONPOSITIVE_ASPECT_RATIO")
    span = sqrt(aspect_ratio * area.value_si)
    checks = (_check("aspect_ratio", aspect_ratio, 3.0, 25.0),)
    return _result(
        "wing_span",
        span,
        "m",
        "wing-span",
        checks,
        {"wing_area": area.value_si, "aspect_ratio": aspect_ratio},
    )


def mean_chord(area: Quantity, span: Quantity) -> SynthesisQuantity:
    """Mean geometric chord ``c = S / b``."""
    require_dimension(area, "area", "wing_area")
    require_dimension(span, "length", "wing_span")
    length = span.value_si
    if length <= 0.0:
        raise ValueError("NONPOSITIVE_SPAN")
    chord = area.value_si / length
    checks = (_check("wing_span", length, 0.1, 200.0),)
    return _result(
        "mean_chord",
        chord,
        "m",
        "mean-chord",
        checks,
        {"wing_area": area.value_si, "wing_span": length},
    )


def aspect_ratio_choice(aspect_ratio: float) -> SynthesisQuantity:
    """A chosen aspect ratio inside the declared envelope."""
    checks = (_check("aspect_ratio", aspect_ratio, 3.0, 25.0),)
    return _result(
        "aspect_ratio",
        aspect_ratio,
        "dimensionless",
        "aspect-ratio-choice",
        checks,
        {"aspect_ratio": aspect_ratio},
    )


def planform_area(span: Quantity, aspect_ratio: float) -> SynthesisQuantity:
    """Blended/lifting-body planform area ``S = b^2 / AR``."""
    require_dimension(span, "length", "span")
    if aspect_ratio <= 0.0:
        raise ValueError("NONPOSITIVE_ASPECT_RATIO")
    area = span.value_si * span.value_si / aspect_ratio
    checks = (_check("aspect_ratio", aspect_ratio, 0.5, 3.0),)
    return _result(
        "planform_area",
        area,
        "m2",
        "planform-area",
        checks,
        {"span": span.value_si, "aspect_ratio": aspect_ratio},
    )


def thickness_ratio_from_volume(
    volume_si: float, area: Quantity, span: Quantity
) -> SynthesisQuantity:
    """Thickness ratio from a volume cap: ``t/c = V * b / S^2`` for ``V = S^2 (t/c) / b``."""
    require_dimension(area, "area", "planform_area")
    require_dimension(span, "length", "span")
    if not isfinite(volume_si) or volume_si <= 0.0:
        raise ValueError("NONPOSITIVE_VOLUME_LIMIT")
    if area.value_si <= 0.0 or span.value_si <= 0.0:
        raise ValueError("NONPOSITIVE_PLANFORM")
    ratio = volume_si * span.value_si / (area.value_si * area.value_si)
    checks = (
        _check("thickness_ratio", ratio, 0.06, 0.20),
        _check("planform_area", area.value_si, 0.1, 500.0),
    )
    return _result(
        "thickness_ratio",
        ratio,
        "dimensionless",
        "thickness-ratio-from-volume",
        checks,
        {"volume": volume_si, "area": area.value_si, "span": span.value_si},
    )


def thrust_to_weight_climb(climb_gradient: float, lift_to_drag: float) -> SynthesisQuantity:
    """Climb thrust loading ``T/W = gamma + 1/(L/D)``."""
    if lift_to_drag <= 0.0:
        raise ValueError("NONPOSITIVE_LIFT_TO_DRAG")
    ratio = climb_gradient + 1.0 / lift_to_drag
    checks = (
        _check("climbGradient", climb_gradient, 0.0, 0.5),
        _check("liftToDrag", lift_to_drag, 3.0, 30.0),
    )
    return _result(
        "thrust_to_weight",
        ratio,
        "dimensionless",
        "thrust-to-weight-climb",
        checks,
        {"climbGradient": climb_gradient, "liftToDrag": lift_to_drag},
    )


def thrust_to_weight_cruise(lift_to_drag: float) -> SynthesisQuantity:
    """Cruise thrust loading ``T/W = 1/(L/D)``."""
    if lift_to_drag <= 0.0:
        raise ValueError("NONPOSITIVE_LIFT_TO_DRAG")
    ratio = 1.0 / lift_to_drag
    checks = (_check("liftToDrag", lift_to_drag, 3.0, 30.0),)
    return _result(
        "thrust_to_weight",
        ratio,
        "dimensionless",
        "thrust-to-weight-cruise",
        checks,
        {"liftToDrag": lift_to_drag},
    )


def required_thrust(weight_force: Quantity, thrust_to_weight_ratio: float) -> SynthesisQuantity:
    """Required thrust ``T = (T/W) * W``."""
    require_dimension(weight_force, "force", "weightForce")
    if thrust_to_weight_ratio <= 0.0:
        raise ValueError("NONPOSITIVE_THRUST_TO_WEIGHT")
    thrust = weight_force.value_si * thrust_to_weight_ratio
    checks = (_check("thrust_to_weight", thrust_to_weight_ratio, 0.02, 1.5),)
    return _result(
        "required_thrust",
        thrust,
        "N",
        "required-thrust",
        checks,
        {"weightForce": weight_force.value_si, "thrust_to_weight": thrust_to_weight_ratio},
    )


def required_power(
    weight_force: Quantity,
    cruise_speed: Quantity,
    climb_gradient: float,
    lift_to_drag: float,
    propulsive_efficiency: float,
) -> SynthesisQuantity:
    """Shaft power ``P = (D + W*gamma) * V / eta`` with ``D = W/(L/D)``."""
    require_dimension(weight_force, "force", "weightForce")
    require_dimension(cruise_speed, "velocity", "cruiseSpeed")
    if lift_to_drag <= 0.0 or propulsive_efficiency <= 0.0:
        raise ValueError("NONPOSITIVE_EFFICIENCY_OR_LIFT_TO_DRAG")
    speed = cruise_speed.value_si
    drag = weight_force.value_si / lift_to_drag
    power = (drag + weight_force.value_si * climb_gradient) * speed / propulsive_efficiency
    checks = (
        _check("cruiseSpeed", speed, 10.0, 300.0),
        _check("climbGradient", climb_gradient, 0.0, 0.5),
        _check("liftToDrag", lift_to_drag, 3.0, 30.0),
        _check("propulsiveEfficiency", propulsive_efficiency, 0.1, 1.0),
    )
    return _result(
        "required_power",
        power,
        "W",
        "required-power",
        checks,
        {
            "weightForce": weight_force.value_si,
            "cruiseSpeed": speed,
            "climbGradient": climb_gradient,
            "liftToDrag": lift_to_drag,
            "propulsiveEfficiency": propulsive_efficiency,
        },
    )


def sweep_drag_divergence(
    max_speed: Quantity,
    speed_of_sound: Quantity,
    drag_divergence_mach: float,
    max_sweep: float,
) -> SynthesisQuantity:
    """Quarter-chord sweep from simple sweep theory to hold ``M cos(L) <= M_dd``."""
    require_dimension(max_speed, "velocity", "maxSpeed")
    require_dimension(speed_of_sound, "velocity", "speed_of_sound")
    if speed_of_sound.value_si <= 0.0:
        raise ValueError("NONPOSITIVE_SPEED_OF_SOUND")
    if drag_divergence_mach <= 0.0:
        raise ValueError("NONPOSITIVE_DRAG_DIVERGENCE_MACH")
    mach = max_speed.value_si / speed_of_sound.value_si
    if mach > drag_divergence_mach:
        sweep = min(acos(min(1.0, drag_divergence_mach / mach)), max_sweep)
    else:
        sweep = 0.0
    checks = (
        _check("mach", mach, 0.0, 3.0),
        _check("dragDivergenceMach", drag_divergence_mach, 0.5, 0.95),
        _check("maxSweep", max_sweep, 0.0, 1.4),
    )
    return _result(
        "quarter_chord_sweep",
        sweep,
        "rad",
        "sweep-drag-divergence",
        checks,
        {
            "mach": mach,
            "dragDivergenceMach": drag_divergence_mach,
            "maxSweep": max_sweep,
        },
    )


def horizontal_tail_area(
    tail_volume_coefficient: float,
    wing_area_quantity: Quantity,
    mean_chord_quantity: Quantity,
    tail_arm: float,
) -> SynthesisQuantity:
    """Horizontal tail area from the tail-volume heuristic ``S_h = V_h S c / l_h``."""
    require_dimension(wing_area_quantity, "area", "wing_area")
    require_dimension(mean_chord_quantity, "length", "mean_chord")
    if tail_arm <= 0.0:
        raise ValueError("NONPOSITIVE_TAIL_ARM")
    area = (
        tail_volume_coefficient
        * wing_area_quantity.value_si
        * mean_chord_quantity.value_si
        / tail_arm
    )
    checks = (
        _check("tailVolumeCoefficient", tail_volume_coefficient, 0.3, 1.2),
        _check("tailArm", tail_arm, 0.5, 50.0),
    )
    return _result(
        "horizontal_tail_area",
        area,
        "m2",
        "horizontal-tail-area",
        checks,
        {
            "tailVolumeCoefficient": tail_volume_coefficient,
            "wing_area": wing_area_quantity.value_si,
            "mean_chord": mean_chord_quantity.value_si,
            "tailArm": tail_arm,
        },
    )


def dynamic_pressure(density: Quantity, speed: Quantity) -> SynthesisQuantity:
    """Incompressible dynamic pressure ``q = 0.5 * rho * V^2``."""
    require_dimension(density, "density", "density")
    require_dimension(speed, "velocity", "speed")
    pressure = 0.5 * density.value_si * speed.value_si * speed.value_si
    checks = (_check("speed", speed.value_si, 5.0, 400.0),)
    return _result(
        "dynamic_pressure",
        pressure,
        "Pa",
        "dynamic-pressure",
        checks,
        {"density": density.value_si, "speed": speed.value_si},
    )


def range_energy_fraction(
    range_quantity: Quantity,
    takeoff_mass: Quantity,
    gravity: float,
    lift_to_drag: float,
    specific_energy: float,
    propulsive_efficiency: float,
) -> SynthesisQuantity:
    """Stored-energy mass fraction for a range: ``D*R/eta`` over ``m * e``."""
    require_dimension(range_quantity, "length", "range")
    require_dimension(takeoff_mass, "mass", "takeoffMass")
    if lift_to_drag <= 0.0 or specific_energy <= 0.0 or propulsive_efficiency <= 0.0:
        raise ValueError("NONPOSITIVE_ENERGY_METHOD_INPUT")
    energy = (
        (takeoff_mass.value_si * gravity / lift_to_drag)
        * range_quantity.value_si
        / propulsive_efficiency
    )
    stored = takeoff_mass.value_si * specific_energy
    fraction = energy / stored
    checks = (
        _check("liftToDrag", lift_to_drag, 3.0, 30.0),
        _check("specificEnergy", specific_energy, 1e6, 5e7),
        _check("propulsiveEfficiency", propulsive_efficiency, 0.1, 1.0),
    )
    return _result(
        "fuel_mass_fraction",
        fraction,
        "dimensionless",
        "range-energy-fraction",
        checks,
        {
            "range": range_quantity.value_si,
            "takeoffMass": takeoff_mass.value_si,
            "liftToDrag": lift_to_drag,
            "specificEnergy": specific_energy,
            "propulsiveEfficiency": propulsive_efficiency,
        },
    )


def reference_quantity(name: str, quantity: Quantity) -> SynthesisQuantity:
    """Pass a declared requirement value through with its unit and provenance."""
    return SynthesisQuantity(
        name=name,
        quantity=quantity,
        method="requirement-reference",
        validity=_validity("requirement-reference", ()),
        provenance=_provenance("requirement-reference", {}),
    )
