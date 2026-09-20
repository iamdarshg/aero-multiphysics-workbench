"""Control-effectiveness contract across surfaces, rotors, and other actuators.

An :class:`ControlEffector` declares moment effectiveness per radian of travel
about the roll/pitch/yaw axes together with position limits, a slew-rate
limit, and a lag time constant. An :class:`EffectivenessMatrix` is the
deterministic 3-by-N Jacobian the allocator consumes. The trim seam builds
surface effectiveness from AIRFRAME 05 derivative coverage; missing coverage
fails closed instead of substituting a fabricated zero.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aeroworkbench_airframe.trim.contract import DerivativeBundle
from aeroworkbench_airframe.trim.errors import AeroCoefficientError

from .errors import ControlContractError

__all__ = [
    "AXES",
    "ControlEffector",
    "EffectivenessMatrix",
    "TrimEffectivenessMap",
    "build_effectiveness",
    "effectiveness_from_trim",
]

AXES: tuple[str, str, str] = ("roll", "pitch", "yaw")


def _finite(value: float, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ControlContractError(f"NONFINITE_VALUE:{label}")
    number = float(value)
    if number != number or number in (float("inf"), float("-inf")):
        raise ControlContractError(f"NONFINITE_VALUE:{label}")
    return number


@dataclass(frozen=True, slots=True)
class ControlEffector:
    """One allocatable effector: moment Jacobian row plus its physical limits."""

    name: str
    gains: tuple[float, float, float]
    lower_limit: float
    upper_limit: float
    max_rate: float
    time_constant_s: float = 0.0
    priority: int = 0

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ControlContractError("EFFECTOR_NAME_REQUIRED")
        for axis, gain in zip(AXES, self.gains, strict=True):
            _finite(gain, f"effector.{self.name}.{axis}")
        _finite(self.lower_limit, f"effector.{self.name}.lower_limit")
        _finite(self.upper_limit, f"effector.{self.name}.upper_limit")
        _finite(self.max_rate, f"effector.{self.name}.max_rate")
        _finite(self.time_constant_s, f"effector.{self.name}.time_constant_s")
        if self.lower_limit >= self.upper_limit:
            raise ControlContractError(f"EFFECTOR_LIMITS_UNORDERED:{self.name}")
        if self.max_rate <= 0.0:
            raise ControlContractError(f"EFFECTOR_RATE_NONPOSITIVE:{self.name}")
        if self.time_constant_s < 0.0:
            raise ControlContractError(f"EFFECTOR_LAG_NEGATIVE:{self.name}")
        if not isinstance(self.priority, int) or isinstance(self.priority, bool):
            raise ControlContractError(f"EFFECTOR_PRIORITY_NOT_INT:{self.name}")

    def canonical(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "gains": {axis: gain for axis, gain in zip(AXES, self.gains, strict=True)},
            "lowerLimit": self.lower_limit,
            "upperLimit": self.upper_limit,
            "maxRate": self.max_rate,
            "timeConstantS": self.time_constant_s,
            "priority": self.priority,
        }


@dataclass(frozen=True, slots=True)
class EffectivenessMatrix:
    """The deterministic 3-by-N control Jacobian over ``AXES``."""

    axes: tuple[str, str, str]
    effectors: tuple[str, ...]
    rows: tuple[tuple[float, ...], ...]

    def __post_init__(self) -> None:
        if tuple(self.axes) != AXES:
            raise ControlContractError("EFFECTIVENESS_AXES_MUST_BE_ROLL_PITCH_YAW")
        if not self.effectors:
            raise ControlContractError("EFFECTIVENESS_NEEDS_EFFECTORS")
        if len(set(self.effectors)) != len(self.effectors):
            raise ControlContractError("DUPLICATE_EFFECTOR_NAME")
        if len(self.rows) != 3 or any(len(row) != len(self.effectors) for row in self.rows):
            raise ControlContractError("EFFECTIVENESS_SHAPE_MUST_BE_3_BY_N")
        for row in self.rows:
            for value in row:
                _finite(value, "effectiveness.entry")

    def column(self, name: str) -> tuple[float, float, float]:
        try:
            index = self.effectors.index(name)
        except ValueError as error:
            raise ControlContractError(f"UNKNOWN_EFFECTOR:{name}") from error
        return (self.rows[0][index], self.rows[1][index], self.rows[2][index])

    def canonical(self) -> dict[str, Any]:
        return {
            "axes": list(self.axes),
            "effectors": list(self.effectors),
            "rows": [list(row) for row in self.rows],
        }


def build_effectiveness(effectors: tuple[ControlEffector, ...]) -> EffectivenessMatrix:
    """Assemble the Jacobian columns from declared effector gains."""
    if not effectors:
        raise ControlContractError("EFFECTIVENESS_NEEDS_EFFECTORS")
    names = tuple(effector.name for effector in effectors)
    rows = tuple(
        tuple(effector.gains[axis] for effector in effectors) for axis in range(3)
    )
    return EffectivenessMatrix(axes=AXES, effectors=names, rows=rows)


@dataclass(frozen=True, slots=True)
class TrimEffectivenessMap:
    """Which trim derivative drives one effector column on which moment axis."""

    effector: str
    axis: str
    derivative: str
    moment_scale: float

    def __post_init__(self) -> None:
        if not self.effector.strip() or not self.derivative.strip():
            raise ControlContractError("TRIM_MAP_NEEDS_EFFECTOR_AND_DERIVATIVE")
        if self.axis not in AXES:
            raise ControlContractError(f"UNKNOWN_TRIM_MAP_AXIS:{self.axis}")
        _finite(self.moment_scale, f"trimMap.{self.effector}.momentScale")
        if self.moment_scale <= 0.0:
            raise ControlContractError(f"TRIM_MAP_SCALE_NONPOSITIVE:{self.effector}")


def effectiveness_from_trim(
    bundle: DerivativeBundle,
    entries: tuple[TrimEffectivenessMap, ...],
    *,
    axes: tuple[str, str, str] = AXES,
) -> EffectivenessMatrix:
    """Build effector columns from AIRFRAME 05 derivative coverage, fail closed.

    Each entry names a trim derivative (for example ``cm_de``) and a moment
    scale (for example ``q * S * c``); the resolved derivative times the scale
    is the moment per radian on the entry axis. A missing derivative raises
    instead of contributing a fabricated zero.
    """
    if not entries:
        raise ControlContractError("TRIM_MAP_NEEDS_ENTRIES")
    if tuple(axes) != AXES:
        raise ControlContractError("EFFECTIVENESS_AXES_MUST_BE_ROLL_PITCH_YAW")
    longitudinal = {
        field: getattr(bundle.longitudinal, field)
        for field in (
            "cl_alpha", "cd_alpha", "cm_alpha", "cl_q", "cm_q",
            "cl_de", "cm_de", "cl_u", "cd_u", "cm_u",
        )
    }
    lateral = {
        field: getattr(bundle.lateral_directional, field)
        for field in (
            "cy_beta", "cl_beta", "cn_beta", "cy_p", "cy_r", "cl_p",
            "cl_r", "cn_p", "cn_r", "cl_da", "cl_dr", "cn_da",
            "cn_dr", "cy_da", "cy_dr",
        )
    }
    names: list[str] = []
    columns: list[tuple[float, float, float]] = []
    for entry in entries:
        if entry.effector in names:
            raise ControlContractError(f"DUPLICATE_EFFECTOR_NAME:{entry.effector}")
        derivative: float | None = longitudinal.get(entry.derivative, lateral.get(entry.derivative))
        if derivative is None:
            raise ControlContractError(f"MISSING_DERIVATIVE:{entry.derivative}")
        try:
            value = float(derivative)
        except (TypeError, ValueError) as error:
            raise ControlContractError(
                f"NONFINITE_VALUE:trimMap.{entry.effector}"
            ) from error
        if value != value or value in (float("inf"), float("-inf")):
            raise ControlContractError(f"NONFINITE_VALUE:trimMap.{entry.effector}")
        axis_index = AXES.index(entry.axis)
        moment_per_rad = value * entry.moment_scale
        column = [0.0, 0.0, 0.0]
        column[axis_index] = moment_per_rad
        names.append(entry.effector)
        columns.append((column[0], column[1], column[2]))
    rows = tuple(
        tuple(columns[index][axis] for index in range(len(columns))) for axis in range(3)
    )
    try:
        return EffectivenessMatrix(axes=AXES, effectors=tuple(names), rows=rows)
    except ControlContractError as error:
        raise AeroCoefficientError(str(error)) from error
