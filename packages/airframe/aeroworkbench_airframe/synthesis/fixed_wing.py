"""Fixed-wing initial sizing from normalized requirements.

The generator chains declared analytical/empirical relations (wing loading from
stall speed, wing area, span/chord, thrust/power loading, sweep, tail volume, and
mission energy) into one or more diverse seeds. It never overwrites a user hard
constraint: if a synthesized value would violate a declared bound it fails closed
with an explicit reason, and any value outside a method's validity envelope is
rejected rather than reported.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import radians

from aeroworkbench_core.types import FidelityLevel, Provenance, ResultSource

from ..canonical import content_digest
from ..units import Quantity
from . import methods
from .errors import SynthesisInfeasibleError
from .requirements import CompiledRequirements
from .seeds import VehicleSeed

_ANALYTICAL = ResultSource.ANALYTICAL
_FIDELITY = FidelityLevel.ANALYTICAL


@dataclass(frozen=True, slots=True)
class FixedWingAssumptions:
    """Declared empirical assumptions used where AIRFRAME 02/03 data is absent."""

    max_lift_coefficient: float = 1.6
    lift_to_drag: float = 15.0
    empty_mass_fraction: float = 0.55
    propulsive_efficiency: float = 0.8
    specific_energy: float = 43.5e6
    drag_divergence_mach: float = 0.78
    max_sweep_deg: float = 35.0
    aspect_ratio_lower: float = 6.0
    aspect_ratio_upper: float = 10.0
    tail_volume_coefficient: float = 0.9
    tail_arm_to_chord: float = 2.5
    gravity: float = 9.80665

    def canonical(self) -> dict[str, float]:
        return {
            "maxLiftCoefficient": self.max_lift_coefficient,
            "liftToDrag": self.lift_to_drag,
            "emptyMassFraction": self.empty_mass_fraction,
            "propulsiveEfficiency": self.propulsive_efficiency,
            "specificEnergy": self.specific_energy,
            "dragDivergenceMach": self.drag_divergence_mach,
            "maxSweepDeg": self.max_sweep_deg,
            "aspectRatioLower": self.aspect_ratio_lower,
            "aspectRatioUpper": self.aspect_ratio_upper,
            "tailVolumeCoefficient": self.tail_volume_coefficient,
            "tailArmToChord": self.tail_arm_to_chord,
            "gravity": self.gravity,
        }


def requirement_bounds(
    compiled: CompiledRequirements,
) -> dict[str, tuple[float | None, float | None]]:
    """Aggregate each metric's tightest SI lower/upper bound."""
    raw: dict[str, list[float | None]] = {}
    for requirement in compiled.requirements:
        current = raw.setdefault(requirement.metric, [None, None])
        if requirement.lower_si is not None:
            current[0] = (
                requirement.lower_si
                if current[0] is None
                else max(current[0], requirement.lower_si)
            )
        if requirement.upper_si is not None:
            current[1] = (
                requirement.upper_si
                if current[1] is None
                else min(current[1], requirement.upper_si)
            )
    return {metric: (values[0], values[1]) for metric, values in raw.items()}


def _required_lower(
    bounds: dict[str, tuple[float | None, float | None]], metric: str
) -> float:
    lower, _ = bounds.get(metric, (None, None))
    if lower is None:
        raise SynthesisInfeasibleError(f"REQUIRED_METRIC_MISSING:{metric}")
    return lower


def _required_upper(
    bounds: dict[str, tuple[float | None, float | None]], metric: str
) -> float:
    _, upper = bounds.get(metric, (None, None))
    if upper is None:
        raise SynthesisInfeasibleError(f"REQUIRED_METRIC_MISSING:{metric}")
    return upper


def _reference_value(
    bounds: dict[str, tuple[float | None, float | None]],
    metric: str,
    default: float | None,
) -> float | None:
    lower, upper = bounds.get(metric, (None, None))
    if lower is not None:
        return lower
    if upper is not None:
        return upper
    return default


def _diverse_values(lower: float, upper: float, count: int) -> tuple[float, ...]:
    if count <= 1 or upper <= lower + 1e-9:
        return (lower,)
    return tuple(lower + index * (upper - lower) / (count - 1) for index in range(count))


def _seed_assumptions(assumptions: FixedWingAssumptions, cl_max: float) -> tuple[str, ...]:
    return (
        f"empty_mass_fraction={assumptions.empty_mass_fraction}",
        f"max_lift_coefficient={cl_max}",
        f"lift_to_drag={assumptions.lift_to_drag}",
        f"propulsive_efficiency={assumptions.propulsive_efficiency}",
        f"specific_energy_J_per_kg={assumptions.specific_energy}",
        f"drag_divergence_mach={assumptions.drag_divergence_mach}",
        f"tail_volume_coefficient={assumptions.tail_volume_coefficient}",
        f"tail_arm_to_chord={assumptions.tail_arm_to_chord}",
        "Empirical/analytical screening relations; native validation required before commitment.",
    )


def _reference_quantities(
    bounds: dict[str, tuple[float | None, float | None]],
    stall_speed: float,
    cruise_speed: float,
    cruise_altitude: float,
) -> list[methods.SynthesisQuantity]:
    references = [
        methods.reference_quantity("stall_speed", Quantity(value=stall_speed, unit="m/s")),
        methods.reference_quantity("cruise_speed", Quantity(value=cruise_speed, unit="m/s")),
        methods.reference_quantity("cruise_altitude", Quantity(value=cruise_altitude, unit="m")),
    ]
    max_speed = _reference_value(bounds, "max_speed", None)
    if max_speed is not None:
        references.append(
            methods.reference_quantity("max_speed", Quantity(value=max_speed, unit="m/s"))
        )
    load_factor = _reference_value(bounds, "load_factor", None)
    if load_factor is not None:
        references.append(
            methods.reference_quantity(
                "load_factor", Quantity(value=load_factor, unit="dimensionless")
            )
        )
    range_value = _reference_value(bounds, "range", None)
    if range_value is not None:
        references.append(
            methods.reference_quantity("range", Quantity(value=range_value, unit="m"))
        )
    return references


def _build_seed(
    compiled: CompiledRequirements,
    assumptions: FixedWingAssumptions,
    bounds: dict[str, tuple[float | None, float | None]],
    *,
    aspect_ratio: float,
    index: int,
) -> VehicleSeed:
    payload = _required_lower(bounds, "payload_mass")
    stall_speed = _required_upper(bounds, "stall_speed")
    cruise_speed = _reference_value(bounds, "cruise_speed", None)
    if cruise_speed is None:
        raise SynthesisInfeasibleError("REQUIRED_METRIC_MISSING:cruise_speed")
    cruise_altitude = _reference_value(bounds, "cruise_altitude", 0.0)
    assert cruise_altitude is not None
    cl_max = _reference_value(bounds, "max_lift_coefficient", assumptions.max_lift_coefficient)
    assert cl_max is not None

    density = methods.isa_density(Quantity(value=cruise_altitude, unit="m"))
    speed_of_sound = methods.isa_speed_of_sound(Quantity(value=cruise_altitude, unit="m"))
    takeoff_mass = methods.max_takeoff_mass(
        Quantity(value=payload, unit="kg"), assumptions.empty_mass_fraction
    )
    weight = takeoff_mass.quantity.value_si * assumptions.gravity
    loading = methods.wing_loading(
        Quantity(value=stall_speed, unit="m/s"), density.quantity, cl_max
    )
    area = methods.wing_area(Quantity(value=weight, unit="N"), loading.quantity)
    span = methods.wing_span(area.quantity, aspect_ratio)
    chord = methods.mean_chord(area.quantity, span.quantity)

    span_limit = bounds.get("span_limit", (None, None))[1]
    if span_limit is not None and span.quantity.value_si > span_limit + 1e-9:
        raise SynthesisInfeasibleError(
            f"SPAN_LIMIT_EXCEEDED:{span.quantity.value_si}>{span_limit}"
        )

    climb_gradient = _reference_value(bounds, "climb_gradient", None)
    climb_rate = _reference_value(bounds, "climb_rate", None)
    if climb_gradient is None and climb_rate is None:
        gradient = 0.0
        thrust_loading = methods.thrust_to_weight_cruise(assumptions.lift_to_drag)
    else:
        gradient = (
            climb_gradient if climb_gradient is not None else (climb_rate or 0.0) / cruise_speed
        )
        thrust_loading = methods.thrust_to_weight_climb(gradient, assumptions.lift_to_drag)
    thrust = methods.required_thrust(
        Quantity(value=weight, unit="N"), thrust_loading.quantity.value_si
    )
    power = methods.required_power(
        Quantity(value=weight, unit="N"),
        Quantity(value=cruise_speed, unit="m/s"),
        gradient,
        assumptions.lift_to_drag,
        assumptions.propulsive_efficiency,
    )

    max_speed = _reference_value(bounds, "max_speed", None)
    sweep_speed = max_speed if max_speed is not None else cruise_speed
    sweep = methods.sweep_drag_divergence(
        Quantity(value=sweep_speed, unit="m/s"),
        speed_of_sound.quantity,
        assumptions.drag_divergence_mach,
        radians(assumptions.max_sweep_deg),
    )

    tail_arm = assumptions.tail_arm_to_chord * chord.quantity.value_si
    tail = methods.horizontal_tail_area(
        assumptions.tail_volume_coefficient, area.quantity, chord.quantity, tail_arm
    )
    pressure = methods.dynamic_pressure(density.quantity, Quantity(value=cruise_speed, unit="m/s"))
    ratio = methods.aspect_ratio_choice(aspect_ratio)

    quantities: list[methods.SynthesisQuantity] = [
        takeoff_mass,
        loading,
        area,
        ratio,
        span,
        chord,
        thrust_loading,
        thrust,
        power,
        sweep,
        tail,
        pressure,
    ]
    range_value = _reference_value(bounds, "range", None)
    if range_value is not None:
        fuel = methods.range_energy_fraction(
            Quantity(value=range_value, unit="m"),
            takeoff_mass.quantity,
            assumptions.gravity,
            assumptions.lift_to_drag,
            assumptions.specific_energy,
            assumptions.propulsive_efficiency,
        )
        if fuel.quantity.value_si >= 1.0:
            raise SynthesisInfeasibleError(
                f"RANGE_ENERGY_INFEASIBLE:{fuel.quantity.value_si}"
            )
        quantities.append(fuel)

    references = _reference_quantities(bounds, stall_speed, cruise_speed, cruise_altitude)
    all_quantities = [*quantities, *references]
    for quantity in all_quantities:
        if not quantity.validity.valid:
            raise SynthesisInfeasibleError(
                f"VALIDITY_ENVELOPE_VIOLATION:{quantity.name}:"
                f"{','.join(quantity.validity.violations)}"
            )

    seed_assumptions = _seed_assumptions(assumptions, cl_max)
    digest = content_digest(
        {
            "architecture": "fixed-wing",
            "requirements": compiled.content_hash,
            "aspectRatio": aspect_ratio,
        }
    )[:12]
    provenance = Provenance.from_inputs(
        source=_ANALYTICAL,
        model=f"{methods.SYNTHESIS_MODEL}:fixed-wing-seed",
        model_version=methods.SYNTHESIS_MODEL_VERSION,
        fidelity=_FIDELITY,
        inputs={
            "requirementsHash": compiled.content_hash,
            "aspectRatio": aspect_ratio,
            "seedIndex": index,
        },
        assumptions=seed_assumptions,
    )
    return VehicleSeed(
        seed_id=f"fixed-wing-{index:02d}-{digest}",
        architecture_type="fixed_wing",
        quantities=tuple(all_quantities),
        provenance=provenance,
        assumptions=seed_assumptions,
    )


def generate_fixed_wing_seeds(
    compiled: CompiledRequirements,
    *,
    assumptions: FixedWingAssumptions | None = None,
    seed_count: int = 2,
) -> tuple[VehicleSeed, ...]:
    """Generate diverse fixed-wing seeds; fail closed on any unmet requirement."""
    if seed_count <= 0:
        raise SynthesisInfeasibleError("SEED_COUNT_MUST_BE_POSITIVE")
    settings = assumptions if assumptions is not None else FixedWingAssumptions()
    bounds = requirement_bounds(compiled)
    raw_lower, raw_upper = bounds.get("aspect_ratio", (None, None))
    aspect_lower = raw_lower if raw_lower is not None else settings.aspect_ratio_lower
    aspect_upper = raw_upper if raw_upper is not None else settings.aspect_ratio_upper
    if raw_lower is None and raw_upper is not None:
        aspect_lower = min(aspect_lower, raw_upper)
    if raw_upper is None and raw_lower is not None:
        aspect_upper = max(aspect_upper, raw_lower)
    if aspect_lower > aspect_upper:
        aspect_lower, aspect_upper = aspect_upper, aspect_lower

    seeds: list[VehicleSeed] = []
    failures: list[str] = []
    for index, aspect_ratio in enumerate(_diverse_values(aspect_lower, aspect_upper, seed_count)):
        try:
            seeds.append(
                _build_seed(
                    compiled,
                    settings,
                    bounds,
                    aspect_ratio=aspect_ratio,
                    index=index,
                )
            )
        except SynthesisInfeasibleError as error:
            failures.append(str(error))
    if not seeds:
        reason = failures[0] if failures else "NO_SEED_GENERATED"
        raise SynthesisInfeasibleError(reason)
    return tuple(seeds)
