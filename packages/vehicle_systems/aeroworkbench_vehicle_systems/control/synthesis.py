"""Bounded controller synthesis from trim effectiveness and stability data.

:func:`synthesize_axis_pid` places the closed-loop poles of one attitude axis
at a declared bandwidth and damping ratio through exact pole placement on the
screening plant ``I s^2 + c s + k`` driven by a PID deflection actuator, then
refuses the design when a gain leaves its declared bounds or when the
available control authority cannot meet the required moment. Gain schedules
interpolate synthesized point designs over a scheduling variable. Every
synthesized design materializes as real
:class:`aeroworkbench_system_dynamics.controls.PIDController` and
:class:`aeroworkbench_system_dynamics.actuators.ActuatorSpec` objects, so
control code never bypasses the generic actuator/transient contracts: the PID
output is a deflection command in radians, the actuator enforces position,
rate, and lag limits, and the plant converts achieved deflection to moment
through the declared effectiveness.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import pi
from typing import Any

import numpy as np
from aeroworkbench_system_dynamics.actuators import ActuatorSpec
from aeroworkbench_system_dynamics.controls import PIDController

from .contracts import ControlMeta, result_meta
from .effectiveness import AXES, ControlEffector
from .errors import ControlContractError, SynthesisError

__all__ = [
    "AxisGains",
    "AxisPlant",
    "GainBounds",
    "GainSchedule",
    "SynthesizedController",
    "SynthesisTarget",
    "actuators_for_effectors",
    "synthesize_axis_pid",
    "synthesize_schedule",
]


def _finite(value: float, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ControlContractError(f"NONFINITE_VALUE:{label}")
    number = float(value)
    if number != number or number in (float("inf"), float("-inf")):
        raise ControlContractError(f"NONFINITE_VALUE:{label}")
    return number


@dataclass(frozen=True, slots=True)
class AxisPlant:
    """Screening attitude plant for one axis: inertia, damping, stiffness."""

    axis: str
    inertia: float
    effectiveness: float
    damping: float = 0.0
    stiffness: float = 0.0
    max_deflection: float = 0.0
    required_moment: float = 0.0

    def __post_init__(self) -> None:
        if self.axis not in AXES:
            raise ControlContractError(f"UNKNOWN_AXIS:{self.axis}")
        _finite(self.inertia, f"plant.{self.axis}.inertia")
        _finite(self.effectiveness, f"plant.{self.axis}.effectiveness")
        _finite(self.damping, f"plant.{self.axis}.damping")
        _finite(self.stiffness, f"plant.{self.axis}.stiffness")
        _finite(self.max_deflection, f"plant.{self.axis}.maxDeflection")
        _finite(self.required_moment, f"plant.{self.axis}.requiredMoment")
        if self.inertia <= 0.0:
            raise ControlContractError(f"PLANT_INERTIA_NONPOSITIVE:{self.axis}")
        if self.effectiveness <= 0.0:
            raise SynthesisError(f"PLANT_UNCONTROLLABLE:{self.axis}")
        if self.damping < 0.0:
            raise ControlContractError(f"PLANT_DAMPING_NEGATIVE:{self.axis}")
        if self.max_deflection < 0.0 or self.required_moment < 0.0:
            raise ControlContractError(f"PLANT_MOMENT_NEGATIVE:{self.axis}")

    def canonical(self) -> dict[str, Any]:
        return {
            "axis": self.axis,
            "inertia": self.inertia,
            "effectiveness": self.effectiveness,
            "damping": self.damping,
            "stiffness": self.stiffness,
            "maxDeflection": self.max_deflection,
            "requiredMoment": self.required_moment,
        }


@dataclass(frozen=True, slots=True)
class GainBounds:
    """Hard bounds every synthesized gain must lie inside."""

    kp: tuple[float, float]
    ki: tuple[float, float]
    kd: tuple[float, float]

    def __post_init__(self) -> None:
        for label, bound in (("kp", self.kp), ("ki", self.ki), ("kd", self.kd)):
            if len(bound) != 2 or bound[0] > bound[1]:
                raise ControlContractError(f"GAIN_BOUNDS_UNORDERED:{label}")
            _finite(bound[0], f"gainBounds.{label}.lower")
            _finite(bound[1], f"gainBounds.{label}.upper")

    def contains(self, kp: float, ki: float, kd: float) -> bool:
        return (
            self.kp[0] <= kp <= self.kp[1]
            and self.ki[0] <= ki <= self.ki[1]
            and self.kd[0] <= kd <= self.kd[1]
        )

    def canonical(self) -> dict[str, Any]:
        return {"kp": list(self.kp), "ki": list(self.ki), "kd": list(self.kd)}


@dataclass(frozen=True, slots=True)
class SynthesisTarget:
    """Desired closed-loop bandwidth, damping, and third-pole separation."""

    bandwidth_hz: float
    damping_ratio: float
    third_pole_ratio: float = 3.0

    def __post_init__(self) -> None:
        _finite(self.bandwidth_hz, "target.bandwidthHz")
        _finite(self.damping_ratio, "target.dampingRatio")
        _finite(self.third_pole_ratio, "target.thirdPoleRatio")
        if self.bandwidth_hz <= 0.0:
            raise ControlContractError("TARGET_BANDWIDTH_NONPOSITIVE")
        if not 0.0 < self.damping_ratio < 2.0:
            raise ControlContractError("TARGET_DAMPING_OUT_OF_RANGE")
        if self.third_pole_ratio <= 1.0:
            raise ControlContractError("TARGET_POLE_SEPARATION_TOO_SMALL")

    def canonical(self) -> dict[str, Any]:
        return {
            "bandwidthHz": self.bandwidth_hz,
            "dampingRatio": self.damping_ratio,
            "thirdPoleRatio": self.third_pole_ratio,
        }


@dataclass(frozen=True, slots=True)
class AxisGains:
    """Synthesized PID gains for one axis with their design point."""

    axis: str
    kp: float
    ki: float
    kd: float
    bandwidth_hz: float
    damping_ratio: float

    def canonical(self) -> dict[str, Any]:
        return {
            "axis": self.axis,
            "kp": self.kp,
            "ki": self.ki,
            "kd": self.kd,
            "bandwidthHz": self.bandwidth_hz,
            "dampingRatio": self.damping_ratio,
        }

    def to_pid(
        self,
        controller_id: str,
        *,
        setpoint: float = 0.0,
        output_min: float | None = None,
        output_max: float | None = None,
        max_rate: float | None = None,
    ) -> PIDController:
        """Materialize these gains as a generic PID deflection controller."""
        return PIDController(
            controller_id,
            f"{self.axis}_deflection",
            measured_variable=f"{self.axis}_angle",
            setpoint=setpoint,
            kp=self.kp,
            ki=self.ki,
            kd=self.kd,
            unit="rad",
            output_min=output_min,
            output_max=output_max,
            max_rate=max_rate,
        )


@dataclass(frozen=True, slots=True)
class SynthesizedController:
    """One axis design: plant, gains, verdict, and full result metadata."""

    plant: AxisPlant
    gains: AxisGains
    within_bounds: bool
    authority_sufficient: bool
    closed_loop_poles: tuple[complex, ...]
    meta: ControlMeta

    def as_dict(self) -> dict[str, Any]:
        return {
            "plant": self.plant.canonical(),
            "gains": self.gains.canonical(),
            "withinBounds": self.within_bounds,
            "authoritySufficient": self.authority_sufficient,
            "closedLoopPoles": [
                {"real": pole.real, "imag": pole.imag} for pole in self.closed_loop_poles
            ],
            "meta": self.meta.as_dict(),
        }


def _closed_loop_poles(
    plant: AxisPlant, kp: float, ki: float, kd: float
) -> tuple[complex, ...]:
    coefficients = (
        plant.inertia,
        plant.damping + plant.effectiveness * kd,
        plant.stiffness + plant.effectiveness * kp,
        plant.effectiveness * ki,
    )
    roots = np.roots(np.asarray(coefficients, dtype=np.float64))
    ordered = sorted(
        (complex(root) for root in roots),
        key=lambda root: (round(root.real, 12), round(root.imag, 12)),
    )
    return tuple(ordered)


def synthesize_axis_pid(
    plant: AxisPlant,
    target: SynthesisTarget,
    bounds: GainBounds,
) -> SynthesizedController:
    """Place closed-loop poles at the target bandwidth/damping, bounded.

    Raises :class:`SynthesisError` when authority is insufficient, when a
    placed gain leaves its bounds, or when the verified closed-loop poles are
    not all stable.
    """
    available = plant.effectiveness * plant.max_deflection
    authority_sufficient = available >= plant.required_moment
    if not authority_sufficient:
        raise SynthesisError(
            f"CONTROL_AUTHORITY_INSUFFICIENT:{plant.axis}",
        )
    omega = 2.0 * pi * target.bandwidth_hz
    zeta = target.damping_ratio
    third = target.third_pole_ratio * omega
    kp = (plant.inertia * (omega * omega + 2.0 * zeta * omega * third) - plant.stiffness) / (
        plant.effectiveness
    )
    ki = plant.inertia * omega * omega * third / plant.effectiveness
    kd = (plant.inertia * (2.0 * zeta * omega + third) - plant.damping) / plant.effectiveness
    if not bounds.contains(kp, ki, kd):
        raise SynthesisError(f"SYNTHESIS_GAINS_OUT_OF_BOUNDS:{plant.axis}")
    poles = _closed_loop_poles(plant, kp, ki, kd)
    if any(pole.real >= 0.0 for pole in poles):
        raise SynthesisError(f"SYNTHESIZED_LOOP_UNSTABLE:{plant.axis}")
    gains = AxisGains(
        axis=plant.axis,
        kp=kp,
        ki=ki,
        kd=kd,
        bandwidth_hz=target.bandwidth_hz,
        damping_ratio=target.damping_ratio,
    )
    inputs: dict[str, Any] = {
        "plant": plant.canonical(),
        "target": target.canonical(),
        "bounds": bounds.canonical(),
        "gains": gains.canonical(),
    }
    meta = result_meta(
        model="vehicle-control-synthesis",
        inputs=inputs,
        valid=True,
        checks=(
            ("within-bounds", True),
            ("authority-sufficient", True),
            ("closed-loop-stable", True),
        ),
        detail=f"synthesized {plant.axis} PID at {target.bandwidth_hz} Hz",
        assumptions=(
            "screening plant I s^2 + c s + k with PID moment actuation",
            "exact pole placement at (s^2 + 2 z w s + w^2)(s + a)",
            "gains verified inside declared bounds and poles verified stable",
        ),
    )
    return SynthesizedController(
        plant=plant,
        gains=gains,
        within_bounds=True,
        authority_sufficient=True,
        closed_loop_poles=poles,
        meta=meta,
    )


@dataclass(frozen=True, slots=True)
class GainSchedule:
    """Gain-scheduled PID designs over one scheduling variable."""

    variable: str
    points: tuple[tuple[float, AxisGains], ...]

    def __post_init__(self) -> None:
        if not self.variable.strip():
            raise ControlContractError("SCHEDULE_VARIABLE_REQUIRED")
        if len(self.points) < 2:
            raise ControlContractError("SCHEDULE_NEEDS_TWO_POINTS")
        values = [value for value, _ in self.points]
        if len(set(values)) != len(values):
            raise ControlContractError("SCHEDULE_POINTS_MUST_BE_UNIQUE")
        if tuple(sorted(values)) != tuple(values):
            raise ControlContractError("SCHEDULE_POINTS_MUST_BE_ORDERED")
        axes = {gains.axis for _, gains in self.points}
        if len(axes) != 1:
            raise ControlContractError("SCHEDULE_MUST_COVER_ONE_AXIS")

    @property
    def axis(self) -> str:
        return self.points[0][1].axis

    def evaluate(self, value: float) -> AxisGains:
        """Interpolate gains at the scheduling value, clamped at the ends."""
        schedule = _finite(value, f"schedule.{self.variable}")
        points = self.points
        if schedule <= points[0][0]:
            return points[0][1]
        if schedule >= points[-1][0]:
            return points[-1][1]
        for (low_value, low_gains), (high_value, high_gains) in zip(
            points, points[1:], strict=False
        ):
            if low_value <= schedule <= high_value:
                span = high_value - low_value
                fraction = 0.0 if span == 0.0 else (schedule - low_value) / span
                return AxisGains(
                    axis=low_gains.axis,
                    kp=low_gains.kp + (high_gains.kp - low_gains.kp) * fraction,
                    ki=low_gains.ki + (high_gains.ki - low_gains.ki) * fraction,
                    kd=low_gains.kd + (high_gains.kd - low_gains.kd) * fraction,
                    bandwidth_hz=low_gains.bandwidth_hz
                    + (high_gains.bandwidth_hz - low_gains.bandwidth_hz) * fraction,
                    damping_ratio=low_gains.damping_ratio
                    + (high_gains.damping_ratio - low_gains.damping_ratio) * fraction,
                )
        return points[-1][1]

    def canonical(self) -> dict[str, Any]:
        return {
            "variable": self.variable,
            "axis": self.axis,
            "points": [
                {"schedule": value, "gains": gains.canonical()} for value, gains in self.points
            ],
        }


def synthesize_schedule(
    variable: str,
    designs: tuple[tuple[float, AxisPlant, SynthesisTarget], ...],
    bounds: GainBounds,
) -> GainSchedule:
    """Synthesize one bounded point design per schedule station."""
    if len(designs) < 2:
        raise ControlContractError("SCHEDULE_NEEDS_TWO_POINTS")
    points: list[tuple[float, AxisGains]] = []
    for value, plant, target in designs:
        schedule = _finite(value, f"schedule.{variable}")
        points.append((schedule, synthesize_axis_pid(plant, target, bounds).gains))
    ordered = tuple(sorted(points, key=lambda item: item[0]))
    values = [value for value, _ in ordered]
    if len(set(values)) != len(values):
        raise ControlContractError("SCHEDULE_POINTS_MUST_BE_UNIQUE")
    return GainSchedule(variable=variable, points=ordered)


def actuators_for_effectors(
    effectors: tuple[ControlEffector, ...],
    *,
    initial: dict[str, float] | None = None,
    unit: str = "rad",
) -> tuple[ActuatorSpec, ...]:
    """Map every effector onto a generic actuator contract with its limits."""
    specs: list[ActuatorSpec] = []
    for effector in sorted(effectors, key=lambda item: item.name):
        start = 0.0 if initial is None else float(initial.get(effector.name, 0.0))
        start = min(max(start, effector.lower_limit), effector.upper_limit)
        specs.append(
            ActuatorSpec(
                actuator_id=effector.name,
                command_name=f"{effector.name}_cmd",
                output_name=effector.name,
                unit=unit,
                lower_limit=effector.lower_limit,
                upper_limit=effector.upper_limit,
                max_rate=effector.max_rate,
                time_constant_s=effector.time_constant_s,
                initial_position=start,
            )
        )
    return tuple(specs)
