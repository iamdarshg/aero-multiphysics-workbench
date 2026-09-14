"""Typed material property values with units, source, and validity ranges.

Every material value carries where it came from and the domain over which it
is valid. Out-of-range evaluation fails closed instead of extrapolating.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

ValueKind = Literal["constant", "temperature_dependent", "frequency_dependent", "tabulated"]


def _check_samples(samples: tuple[tuple[float, float], ...], label: str) -> None:
    if len(samples) < 2:
        raise ValueError(f"{label}_NEEDS_AT_LEAST_TWO_SAMPLES")
    axes = [axis for axis, _ in samples]
    if any(not axis < nxt for axis, nxt in zip(axes, axes[1:], strict=False)):
        raise ValueError(f"{label}_AXES_MUST_BE_STRICTLY_INCREASING")


def _interpolate(samples: tuple[tuple[float, float], ...], axis: float, label: str) -> float:
    if not samples[0][0] <= axis <= samples[-1][0]:
        raise ValueError(f"{label}_OUT_OF_VALIDITY_RANGE")
    for (x0, y0), (x1, y1) in zip(samples, samples[1:], strict=False):
        if x0 <= axis <= x1:
            fraction = 0.0 if x1 == x0 else (axis - x0) / (x1 - x0)
            return y0 + fraction * (y1 - y0)
    raise ValueError(f"{label}_INTERPOLATION_FAILED")  # pragma: no cover - guarded above


@dataclass(frozen=True, slots=True)
class MaterialValue:
    """One material property value in canonical SI units.

    `unit` names the canonical SI unit of `samples`/`constant` (e.g. ``Pa``,
    ``kg/m^3``, ``W/(m K)``). `axis_unit` names the independent variable unit
    (``K`` for temperature tables, ``Hz`` for frequency tables, custom label
    for generic tabulated data).
    """

    kind: ValueKind
    unit: str
    source: str
    constant: float | None = None
    samples: tuple[tuple[float, float], ...] = ()
    axis_unit: str = ""
    axis_minimum: float | None = None
    axis_maximum: float | None = None
    note: str = ""

    def __post_init__(self) -> None:
        if not self.unit.strip():
            raise ValueError("MATERIAL_VALUE_REQUIRES_UNIT")
        if not self.source.strip():
            raise ValueError("MATERIAL_VALUE_REQUIRES_SOURCE")
        if self.kind == "constant":
            if self.constant is None:
                raise ValueError("CONSTANT_REQUIRES_VALUE")
            if self.samples:
                raise ValueError("CONSTANT_MUST_NOT_HAVE_SAMPLES")
        else:
            if self.constant is not None:
                raise ValueError("TABULATED_MUST_NOT_HAVE_CONSTANT")
            if not self.axis_unit.strip():
                raise ValueError("TABULATED_REQUIRES_AXIS_UNIT")
            _check_samples(self.samples, "MATERIAL_SAMPLES")
            lo, hi = self.samples[0][0], self.samples[-1][0]
            if self.axis_minimum is not None and self.axis_minimum > lo:
                raise ValueError("AXIS_MINIMUM_EXCEEDS_SAMPLES")
            if self.axis_maximum is not None and self.axis_maximum < hi:
                raise ValueError("AXIS_MAXIMUM_BELOW_SAMPLES")

    def evaluate(
        self,
        *,
        temperature_k: float | None = None,
        frequency_hz: float | None = None,
        axis: float | None = None,
    ) -> float:
        """Evaluate the property; raises outside the validity range."""

        if self.kind == "constant":
            assert self.constant is not None
            return self.constant
        if self.kind == "temperature_dependent":
            if temperature_k is None:
                raise ValueError("TEMPERATURE_REQUIRED")
            return _interpolate(self.samples, temperature_k, "TEMPERATURE")
        if self.kind == "frequency_dependent":
            if frequency_hz is None:
                raise ValueError("FREQUENCY_REQUIRED")
            return _interpolate(self.samples, frequency_hz, "FREQUENCY")
        if axis is None:
            raise ValueError("AXIS_VALUE_REQUIRED")
        return _interpolate(self.samples, axis, "TABULATED")

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "unit": self.unit,
            "source": self.source,
            "constant": self.constant,
            "samples": [[axis, value] for axis, value in self.samples],
            "axisUnit": self.axis_unit,
            "axisMinimum": self.axis_minimum,
            "axisMaximum": self.axis_maximum,
            "note": self.note,
        }


def constant(
    value: float, unit: str, source: str, *, note: str = ""
) -> MaterialValue:
    """Build a constant property value."""

    return MaterialValue(
        kind="constant", unit=unit, source=source, constant=float(value), note=note
    )


def temperature_table(
    samples: tuple[tuple[float, float], ...],
    unit: str,
    source: str,
    *,
    note: str = "",
) -> MaterialValue:
    """Build a temperature-dependent property (axis in kelvin)."""

    return MaterialValue(
        kind="temperature_dependent",
        unit=unit,
        source=source,
        samples=tuple((float(t), float(v)) for t, v in samples),
        axis_unit="K",
        note=note,
    )


def frequency_table(
    samples: tuple[tuple[float, float], ...],
    unit: str,
    source: str,
    *,
    note: str = "",
) -> MaterialValue:
    """Build a frequency-dependent property (axis in hertz)."""

    return MaterialValue(
        kind="frequency_dependent",
        unit=unit,
        source=source,
        samples=tuple((float(f), float(v)) for f, v in samples),
        axis_unit="Hz",
        note=note,
    )
