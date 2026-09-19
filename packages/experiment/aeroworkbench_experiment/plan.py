"""Typed, immutable experiment definition.

An :class:`ExperimentPlan` is the generic contract for any bench, wind-tunnel,
thrust-stand, structural, thermal, or flight/vehicle test: the tested design
revision, the configuration, the operating condition, the environmental state,
the sensors/channels with units and expected ranges, the calibration
revisions, and the sampling/timebase. It carries the test-article identity and
produces a content digest over its canonical form. Nothing product-specific is
encoded here.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, ClassVar

from aeroworkbench_optimization.design_space import content_digest

from .contracts import DEFAULT_SOFTWARE, SoftwareIdentity
from .errors import ExperimentError, finite
from .units import Quantity, require_unit

__all__ = [
    "CalibrationRevision",
    "ChannelSpec",
    "EnvironmentalState",
    "ExperimentPlan",
    "OperatingCondition",
    "SamplingSpec",
    "SensorSpec",
    "TestArticle",
    "condition_key",
    "environment_from_mapping",
    "operating_condition_from_mapping",
]


@dataclass(frozen=True, slots=True)
class CalibrationRevision:
    """One immutable calibration revision for a sensor."""

    calibration_id: str
    revision: int
    reference: str
    uncertainty: float
    unit: str
    valid_from: str = ""

    def __post_init__(self) -> None:
        if not self.calibration_id.strip():
            raise ExperimentError("CALIBRATION_ID_REQUIRED")
        if self.revision < 1:
            raise ExperimentError("CALIBRATION_REVISION_MUST_BE_POSITIVE")
        if not self.reference.strip():
            raise ExperimentError("CALIBRATION_REFERENCE_REQUIRED")
        require_unit(self.unit)
        finite(self.uncertainty, "calibration uncertainty", minimum=0.0)

    def canonical(self) -> dict[str, Any]:
        return {
            "calibrationId": self.calibration_id,
            "revision": self.revision,
            "reference": self.reference,
            "uncertainty": self.uncertainty,
            "unit": self.unit,
            "validFrom": self.valid_from,
        }


@dataclass(frozen=True, slots=True)
class SensorSpec:
    """Identity, type, calibration, uncertainty, placement, and rate of a sensor."""

    sensor_id: str
    sensor_type: str
    unit: str
    calibration_id: str
    uncertainty: float
    location_m: tuple[float, float, float]
    orientation_deg: tuple[float, float, float]
    sample_rate_hz: float
    filtering: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.sensor_id.strip():
            raise ExperimentError("SENSOR_ID_REQUIRED")
        if not self.sensor_type.strip():
            raise ExperimentError("SENSOR_TYPE_REQUIRED")
        if not self.calibration_id.strip():
            raise ExperimentError("SENSOR_CALIBRATION_REQUIRED")
        require_unit(self.unit)
        finite(self.uncertainty, "sensor uncertainty", minimum=0.0)
        finite(self.sample_rate_hz, "sensor sample rate", positive=True)
        if len(self.location_m) != 3 or len(self.orientation_deg) != 3:
            raise ExperimentError("SENSOR_PLACEMENT_MUST_BE_THREE_AXIS")
        for index, value in enumerate((*self.location_m, *self.orientation_deg)):
            finite(value, f"sensor placement axis {index}")

    def canonical(self) -> dict[str, Any]:
        return {
            "sensorId": self.sensor_id,
            "sensorType": self.sensor_type,
            "unit": self.unit,
            "calibrationId": self.calibration_id,
            "uncertainty": self.uncertainty,
            "locationM": list(self.location_m),
            "orientationDeg": list(self.orientation_deg),
            "sampleRateHz": self.sample_rate_hz,
            "filtering": list(self.filtering),
        }


@dataclass(frozen=True, slots=True)
class ChannelSpec:
    """A named measurement channel with its sensor and expected range."""

    name: str
    unit: str
    sensor: SensorSpec
    lower: float
    upper: float
    role: str = "measured"

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ExperimentError("CHANNEL_NAME_REQUIRED")
        require_unit(self.unit)
        finite(self.lower, f"channel lower range {self.name}")
        finite(self.upper, f"channel upper range {self.name}")
        if self.lower >= self.upper:
            raise ExperimentError(f"CHANNEL_RANGE_INVALID:{self.name}")
        if not self.role.strip():
            raise ExperimentError("CHANNEL_ROLE_REQUIRED")

    def contains(self, value_si: float) -> bool:
        from .units import to_si

        return to_si(self.lower, self.unit) <= value_si <= to_si(self.upper, self.unit)

    def canonical(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "unit": self.unit,
            "sensor": self.sensor.sensor_id,
            "lower": self.lower,
            "upper": self.upper,
            "role": self.role,
        }


@dataclass(frozen=True, slots=True)
class SamplingSpec:
    """Sampling rate, timebase identity, and optional trigger definition."""

    sample_rate_hz: float
    timebase_id: str
    trigger_channel: str | None = None
    trigger_level: float | None = None
    duration_s: float | None = None

    def __post_init__(self) -> None:
        finite(self.sample_rate_hz, "sampling rate", positive=True)
        if not self.timebase_id.strip():
            raise ExperimentError("TIMEBASE_ID_REQUIRED")
        if (self.trigger_channel is None) != (self.trigger_level is None):
            raise ExperimentError("TRIGGER_CHANNEL_AND_LEVEL_BOTH_REQUIRED")
        if self.trigger_level is not None:
            finite(self.trigger_level, "trigger level")
        if self.duration_s is not None:
            finite(self.duration_s, "duration", positive=True)

    def canonical(self) -> dict[str, Any]:
        return {
            "sampleRateHz": self.sample_rate_hz,
            "timebaseId": self.timebase_id,
            "triggerChannel": self.trigger_channel,
            "triggerLevel": self.trigger_level,
            "durationS": self.duration_s,
        }


@dataclass(frozen=True, slots=True)
class TestArticle:
    """The identity of the article under test (any domain)."""

    __test__: ClassVar[bool] = False

    article_id: str
    revision: str
    kind: str
    description: str = ""

    def __post_init__(self) -> None:
        if not self.article_id.strip():
            raise ExperimentError("ARTICLE_ID_REQUIRED")
        if not self.revision.strip():
            raise ExperimentError("ARTICLE_REVISION_REQUIRED")
        if not self.kind.strip():
            raise ExperimentError("ARTICLE_KIND_REQUIRED")

    def canonical(self) -> dict[str, Any]:
        return {
            "articleId": self.article_id,
            "revision": self.revision,
            "kind": self.kind,
            "description": self.description,
        }


@dataclass(frozen=True, slots=True)
class OperatingCondition:
    """A declared operating point: ordered (name, quantity) values."""

    name: str
    values: tuple[tuple[str, Quantity], ...]

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ExperimentError("CONDITION_NAME_REQUIRED")
        if not self.values:
            raise ExperimentError("CONDITION_VALUES_REQUIRED")
        seen: set[str] = set()
        for key, quantity in self.values:
            if not key.strip():
                raise ExperimentError("CONDITION_VALUE_NAME_REQUIRED")
            if key in seen:
                raise ExperimentError(f"CONDITION_VALUE_DUPLICATE:{key}")
            seen.add(key)
            if quantity.dimension == "dimensionless" and quantity.unit != "1":
                raise ExperimentError(f"CONDITION_VALUE_UNIT_MISMATCH:{key}")

    def as_mapping(self) -> dict[str, float]:
        return {key: quantity.value_si for key, quantity in self.values}

    def canonical(self) -> dict[str, Any]:
        return {"name": self.name, "values": {key: q.canonical() for key, q in self.values}}


@dataclass(frozen=True, slots=True)
class EnvironmentalState:
    """Declared environmental state during a test: ordered (name, quantity)."""

    values: tuple[tuple[str, Quantity], ...]

    def __post_init__(self) -> None:
        seen: set[str] = set()
        for key, _quantity in self.values:
            if not key.strip():
                raise ExperimentError("ENVIRONMENT_VALUE_NAME_REQUIRED")
            if key in seen:
                raise ExperimentError(f"ENVIRONMENT_VALUE_DUPLICATE:{key}")
            seen.add(key)

    def as_mapping(self) -> dict[str, float]:
        return {key: quantity.value_si for key, quantity in self.values}

    def canonical(self) -> dict[str, Any]:
        return {"values": {key: q.canonical() for key, q in self.values}}


def condition_key(condition: OperatingCondition) -> str:
    """Stable content key for matching a measurement to a simulation envelope."""

    return content_digest(condition.canonical())


def operating_condition_from_mapping(
    name: str, values: Mapping[str, tuple[float, str]]
) -> OperatingCondition:
    """Build a condition from ``{name: (value, unit)}`` in sorted key order."""

    return OperatingCondition(
        name=name,
        values=tuple(
            (key, Quantity(value=value, unit=unit)) for key, (value, unit) in sorted(values.items())
        ),
    )


def environment_from_mapping(
    values: Mapping[str, tuple[float, str]] | None = None,
) -> EnvironmentalState:
    """Build an environmental state from ``{name: (value, unit)}``."""

    if not values:
        return EnvironmentalState(())
    return EnvironmentalState(
        values=tuple(
            (key, Quantity(value=value, unit=unit)) for key, (value, unit) in sorted(values.items())
        )
    )


@dataclass(frozen=True, slots=True)
class ExperimentPlan:
    """An immutable, content-addressed experiment definition."""

    plan_id: str
    article: TestArticle
    design_revision: str
    configuration: str
    condition: OperatingCondition
    environment: EnvironmentalState
    channels: tuple[ChannelSpec, ...]
    calibrations: tuple[CalibrationRevision, ...]
    sampling: SamplingSpec
    software: SoftwareIdentity = field(default_factory=lambda: DEFAULT_SOFTWARE)
    provenance: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.plan_id.strip():
            raise ExperimentError("PLAN_ID_REQUIRED")
        if not self.design_revision.strip():
            raise ExperimentError("PLAN_DESIGN_REVISION_REQUIRED")
        if not self.configuration.strip():
            raise ExperimentError("PLAN_CONFIGURATION_REQUIRED")
        if not self.channels:
            raise ExperimentError("PLAN_CHANNELS_REQUIRED")
        names: set[str] = set()
        for channel in self.channels:
            if channel.name in names:
                raise ExperimentError(f"PLAN_CHANNEL_DUPLICATE:{channel.name}")
            names.add(channel.name)
        calibration_ids = {calibration.calibration_id for calibration in self.calibrations}
        for channel in self.channels:
            if channel.sensor.calibration_id not in calibration_ids:
                raise ExperimentError(
                    f"PLAN_UNKNOWN_CALIBRATION:{channel.name}:{channel.sensor.calibration_id}"
                )

    def channel(self, name: str) -> ChannelSpec:
        for channel in self.channels:
            if channel.name == name:
                return channel
        raise ExperimentError(f"PLAN_UNKNOWN_CHANNEL:{name}")

    def calibration(self, calibration_id: str) -> CalibrationRevision:
        for calibration in self.calibrations:
            if calibration.calibration_id == calibration_id:
                return calibration
        raise ExperimentError(f"PLAN_UNKNOWN_CALIBRATION:{calibration_id}")

    @property
    def condition_key(self) -> str:
        return condition_key(self.condition)

    def canonical(self) -> dict[str, Any]:
        return {
            "planId": self.plan_id,
            "article": self.article.canonical(),
            "designRevision": self.design_revision,
            "configuration": self.configuration,
            "condition": self.condition.canonical(),
            "environment": self.environment.canonical(),
            "channels": [channel.canonical() for channel in self.channels],
            "calibrations": [calibration.canonical() for calibration in self.calibrations],
            "sampling": self.sampling.canonical(),
            "software": self.software.canonical(),
            "provenance": dict(self.provenance),
        }

    def digest(self) -> str:
        return content_digest(self.canonical())
