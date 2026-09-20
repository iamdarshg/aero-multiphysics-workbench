"""Oleo-pneumatic shock-absorber stroke response to a touchdown impact.

The strut is modelled as a gas spring (polytropic compression of a fixed gas
charge) plus quadratic hydraulic damping. The effective sprung mass is reduced
by the wing lift still acting at touchdown. A bounded deterministic fixed-step
integration (Heun/RK2, zero-order-held inputs) returns the peak stroke, the peak
load, and a limit verdict. Exceeding the declared stroke fails closed.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from aeroworkbench_system_dynamics import (
    DerivativeFn,
    IntegrationMethod,
    IntegratorReceipt,
    advance,
)

from .contracts import LandingGearFidelity, ResultMeta, result_meta
from .errors import LimitExceeded, finite
from .geometry import ShockAbsorberSpec

_GRAVITY = 9.80665


@dataclass(frozen=True, slots=True)
class ShockStrokeResult:
    """Peak compression and load of one shock strut under a sink-rate impact."""

    absorber_id: str
    effective_mass_kg: float
    sink_rate_m_s: float
    lift_fraction: float
    peak_stroke_m: float
    max_stroke_m: float
    peak_load_n: float
    max_gas_load_n: float
    max_damping_load_n: float
    time_to_peak_s: float
    stroke_limit_exceeded: bool
    receipt: IntegratorReceipt
    meta: ResultMeta

    def units(self) -> dict[str, str]:
        return {
            "peak_stroke_m": "m",
            "peak_load_n": "N",
            "sink_rate_m_s": "m/s",
            "time_to_peak_s": "s",
            "effective_mass_kg": "kg",
        }

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "absorberId": self.absorber_id,
            "effectiveMassKg": self.effective_mass_kg,
            "sinkRateMS": self.sink_rate_m_s,
            "liftFraction": self.lift_fraction,
            "peakStrokeM": self.peak_stroke_m,
            "maxStrokeM": self.max_stroke_m,
            "peakLoadN": self.peak_load_n,
            "maxGasLoadN": self.max_gas_load_n,
            "maxDampingLoadN": self.max_damping_load_n,
            "timeToPeakS": self.time_to_peak_s,
            "strokeLimitExceeded": self.stroke_limit_exceeded,
            "receipt": self.receipt.canonical(),
            "meta": self.meta.canonical(),
        }


def _derivative(
    spec: ShockAbsorberSpec,
    effective_mass_kg: float,
    lift_fraction: float,
    damping_scale: float,
) -> DerivativeFn:
    def derivative(
        time_s: float, state: Mapping[str, float], inputs: Mapping[str, float]
    ) -> Mapping[str, float]:
        del time_s, inputs
        stroke = state["stroke"]
        rate = state["rate"]
        gas = spec.gas_force_n(max(stroke, 0.0))
        damping = damping_scale * spec.damping_force_n(rate)
        acceleration = _GRAVITY * (1.0 - lift_fraction) - (gas + damping) / effective_mass_kg
        return {"stroke": rate, "rate": acceleration}

    return derivative


def evaluate_shock_stroke(
    spec: ShockAbsorberSpec,
    *,
    effective_mass_kg: float,
    sink_rate_m_s: float,
    lift_fraction: float = 0.0,
    damping_scale: float = 1.0,
    step_size_s: float = 1.0e-4,
    max_time_s: float = 1.0,
    model: str = "shock.absorber-stroke",
) -> ShockStrokeResult:
    """Integrate the compression phase and return the peak stroke and load."""

    mass = finite(effective_mass_kg, "effective_mass_kg", positive=True)
    sink = finite(sink_rate_m_s, "sink_rate_m_s", positive=True)
    lift = finite(lift_fraction, "lift_fraction", minimum=0.0, maximum=1.0)
    scale = finite(damping_scale, "damping_scale", minimum=0.0)
    step = finite(step_size_s, "step_size_s", positive=True)
    horizon = finite(max_time_s, "max_time_s", positive=True)
    max_stroke = spec.max_stroke.value_si

    derivative = _derivative(spec, mass, lift, scale)
    state: dict[str, float] = {"stroke": 0.0, "rate": sink}
    time = 0.0
    steps = 0
    peak_stroke = 0.0
    peak_load = 0.0
    max_gas = 0.0
    max_damping = 0.0
    time_to_peak = 0.0

    while True:
        gas = spec.gas_force_n(max(state["stroke"], 0.0))
        damping = scale * spec.damping_force_n(state["rate"])
        load = gas + damping
        if load > peak_load:
            peak_load = load
            time_to_peak = time
        max_gas = max(max_gas, gas)
        max_damping = max(max_damping, damping)
        if state["stroke"] >= max_stroke:
            peak_stroke = max(peak_stroke, max_stroke)
            raise LimitExceeded(
                f"SHOCK_STROKE_LIMIT_EXCEEDED:{spec.absorber_id}:"
                f"{peak_stroke:.6g}>{max_stroke:.6g}"
            )
        peak_stroke = max(peak_stroke, state["stroke"])
        if state["rate"] <= 0.0:
            break
        if time >= horizon:
            raise LimitExceeded("SHOCK_STROKE_DID_NOT_REACH_PEAK_WITHIN_HORIZON")
        state = dict(advance(derivative, IntegrationMethod.HEUN, time, state, step, {}))
        time += step
        steps += 1

    receipt = IntegratorReceipt(
        method=IntegrationMethod.HEUN.value,
        step_size_s=step,
        steps=steps,
        duration_s=time,
        recorded_points=steps + 1,
    )
    meta = result_meta(
        model=f"vehicle-systems.landing-gear.{model}",
        inputs={
            "absorber": spec.canonical_payload(),
            "effectiveMassKg": mass,
            "sinkRateMS": sink,
            "liftFraction": lift,
            "dampingScale": scale,
            "stepSizeS": step,
        },
        valid=True,
        checks={"stroke_within_limit": True, "peak_load_positive": peak_load > 0.0},
        detail="oleo-pneumatic compression phase; zero-order-held inputs",
        fidelity=LandingGearFidelity.GROUND_TRANSIENT,
        assumptions=(
            "compression phase only; rebound damping not modelled",
            "lift at touchdown acts on the declared effective sprung mass",
        ),
    )
    return ShockStrokeResult(
        absorber_id=spec.absorber_id,
        effective_mass_kg=mass,
        sink_rate_m_s=sink,
        lift_fraction=lift,
        peak_stroke_m=peak_stroke,
        max_stroke_m=max_stroke,
        peak_load_n=peak_load,
        max_gas_load_n=max_gas,
        max_damping_load_n=max_damping,
        time_to_peak_s=time_to_peak,
        stroke_limit_exceeded=False,
        receipt=receipt,
        meta=meta,
    )


__all__ = [
    "ShockStrokeResult",
    "evaluate_shock_stroke",
]
