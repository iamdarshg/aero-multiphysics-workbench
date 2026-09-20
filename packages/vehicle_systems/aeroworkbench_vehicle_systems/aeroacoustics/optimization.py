"""Noise objectives and constraints feeding the generic optimization campaign.

A declared noise trade model maps design variables (rotor speed, observer
distance proxy) onto a noise output plus a performance output, so vehicle or
mission studies can minimize noise, constrain it, and expose the
noise/performance trade-off through the shared drivers. Evaluations are
deterministic; inadmissible points are flagged invalid, never silently fixed.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from math import isfinite, log10
from typing import Any

from aeroworkbench_optimization import StudyConstraint, StudyObjective
from aeroworkbench_optimization.drivers import EvaluateFunction
from aeroworkbench_optimization.quality import PhysicsFlags

from .errors import ContractError
from .propagation import ObserverNoiseResult

__all__ = [
    "NoiseTradeModel",
    "noise_campaign_outputs",
    "noise_constraint",
    "noise_objective",
    "noise_trade_evaluator",
]

NOISE_OUTPUT = "noise_db"
THRUST_OUTPUT = "thrust_n"


@dataclass(frozen=True, slots=True)
class NoiseTradeModel:
    """Declared noise/performance trade: reference point plus scaling exponents."""

    reference_rpm: float
    reference_noise_db: float
    rpm_exponent: float = 5.0
    reference_distance_m: float = 100.0
    thrust_per_rpm_n: float = 0.5

    def __post_init__(self) -> None:
        for label, value in (
            ("reference_rpm", self.reference_rpm),
            ("reference_distance_m", self.reference_distance_m),
        ):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ContractError(f"{label} must be a number")
            if not isfinite(float(value)) or float(value) <= 0.0:
                raise ContractError(f"{label} must be positive")
        for label, value in (
            ("reference_noise_db", self.reference_noise_db),
            ("rpm_exponent", self.rpm_exponent),
            ("thrust_per_rpm_n", self.thrust_per_rpm_n),
        ):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ContractError(f"{label} must be a number")
            if not isfinite(float(value)):
                raise ContractError(f"{label} must be finite")

    def canonical(self) -> dict[str, Any]:
        return {
            "referenceRpm": self.reference_rpm,
            "referenceNoiseDb": self.reference_noise_db,
            "rpmExponent": self.rpm_exponent,
            "referenceDistanceM": self.reference_distance_m,
            "thrustPerRpmN": self.thrust_per_rpm_n,
        }


def noise_objective(
    name: str = NOISE_OUTPUT, *, unit: str = "dB", weight: float = 1.0
) -> StudyObjective:
    """A minimize-noise study objective fed from a declared noise output."""

    if not name.strip():
        raise ContractError("noise objective name is required")
    return StudyObjective(name, "minimize", weight, unit)


def noise_constraint(
    limit_db: float, *, name: str = NOISE_OUTPUT, bound: str = "upper", unit: str = "dB"
) -> StudyConstraint:
    """A noise study constraint (default: upper bound on the noise output)."""

    if not name.strip():
        raise ContractError("noise constraint name is required")
    if isinstance(limit_db, bool) or not isinstance(limit_db, (int, float)):
        raise ContractError("noise constraint limit must be a number")
    if not isfinite(float(limit_db)):
        raise ContractError("noise constraint limit must be finite")
    return StudyConstraint(name, bound, float(limit_db), unit)


def noise_campaign_outputs(result: ObserverNoiseResult) -> dict[str, float]:
    """Map an observer result onto campaign outputs (noise plus distance)."""

    return {NOISE_OUTPUT: result.overall_level_db, "observer_distance_m": result.distance_m}


def noise_trade_evaluator(
    model: NoiseTradeModel, *, rpm_key: str = "rpm", distance_key: str = "distance_m"
) -> EvaluateFunction:
    """Build a deterministic noise/performance evaluator for shared drivers.

    Noise rises with rotor speed by the declared exponent and falls with
    observer distance by spherical spreading; thrust rises linearly with
    speed, which exposes the trade-off. Non-positive inputs are reported
    invalid instead of evaluated.
    """

    if not rpm_key.strip() or not distance_key.strip():
        raise ContractError("noise trade evaluator needs variable keys")

    def evaluate(
        point: Mapping[str, float], operating_point: str
    ) -> tuple[Mapping[str, float], PhysicsFlags]:
        _ = operating_point
        rpm = point.get(rpm_key, float("nan"))
        distance = point.get(distance_key, float("nan"))
        valid = (
            isinstance(rpm, (int, float))
            and isinstance(distance, (int, float))
            and not isinstance(rpm, bool)
            and not isinstance(distance, bool)
            and isfinite(float(rpm))
            and isfinite(float(distance))
            and float(rpm) > 0.0
            and float(distance) > 0.0
        )
        if not valid:
            outputs: Mapping[str, float] = {NOISE_OUTPUT: model.reference_noise_db,
                                            THRUST_OUTPUT: 0.0}
            flags = PhysicsFlags(
                converged=True, closure_passed=True, validity_ok=False,
                mesh_sensitivity=0.0, timestep_sensitivity=0.0,
            )
            return outputs, flags
        speed = float(rpm)
        slant = float(distance)
        noise = (
            model.reference_noise_db
            + 10.0 * model.rpm_exponent * log10(speed / model.reference_rpm)
            - 20.0 * log10(slant / model.reference_distance_m)
        )
        thrust = model.thrust_per_rpm_n * speed
        flags = PhysicsFlags(
            converged=True, closure_passed=True, validity_ok=True,
            mesh_sensitivity=0.0, timestep_sensitivity=0.0,
        )
        return {NOISE_OUTPUT: noise, THRUST_OUTPUT: thrust}, flags

    return evaluate
