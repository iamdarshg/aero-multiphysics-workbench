"""Sensor provenance: what every channel records about its measurement chain.

For each plan channel this module resolves the sensor identity/type, the
calibration revision actually applied, the uncertainty, the location and
orientation, the sample rate, and any filtering performed. The record is
derived from the immutable plan, so the provenance of a channel cannot drift
away from its declared sensor.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ExperimentError
from .plan import CalibrationRevision, ExperimentPlan, SensorSpec

__all__ = [
    "ChannelProvenance",
    "channel_provenance",
    "dataset_sensor_provenance",
]


@dataclass(frozen=True, slots=True)
class ChannelProvenance:
    """The resolved measurement chain for one channel."""

    channel: str
    sensor_id: str
    sensor_type: str
    calibration_id: str
    calibration_revision: int
    calibration_reference: str
    uncertainty: float
    uncertainty_unit: str
    location_m: tuple[float, float, float]
    orientation_deg: tuple[float, float, float]
    sample_rate_hz: float
    filtering: tuple[str, ...]

    def canonical(self) -> dict[str, Any]:
        return {
            "channel": self.channel,
            "sensorId": self.sensor_id,
            "sensorType": self.sensor_type,
            "calibrationId": self.calibration_id,
            "calibrationRevision": self.calibration_revision,
            "calibrationReference": self.calibration_reference,
            "uncertainty": self.uncertainty,
            "uncertaintyUnit": self.uncertainty_unit,
            "locationM": list(self.location_m),
            "orientationDeg": list(self.orientation_deg),
            "sampleRateHz": self.sample_rate_hz,
            "filtering": list(self.filtering),
        }


def _resolve(sensor: SensorSpec, calibration: CalibrationRevision) -> ChannelProvenance:
    if calibration.calibration_id != sensor.calibration_id:
        raise ExperimentError(
            f"SENSOR_CALIBRATION_MISMATCH:{sensor.sensor_id}:{sensor.calibration_id}"
        )
    return ChannelProvenance(
        channel="",
        sensor_id=sensor.sensor_id,
        sensor_type=sensor.sensor_type,
        calibration_id=calibration.calibration_id,
        calibration_revision=calibration.revision,
        calibration_reference=calibration.reference,
        uncertainty=sensor.uncertainty,
        uncertainty_unit=sensor.unit,
        location_m=sensor.location_m,
        orientation_deg=sensor.orientation_deg,
        sample_rate_hz=sensor.sample_rate_hz,
        filtering=sensor.filtering,
    )


def channel_provenance(plan: ExperimentPlan, channel_name: str) -> ChannelProvenance:
    """Resolve the measurement-chain provenance for one plan channel."""

    channel = plan.channel(channel_name)
    calibration = plan.calibration(channel.sensor.calibration_id)
    resolved = _resolve(channel.sensor, calibration)
    return ChannelProvenance(
        channel=channel_name,
        sensor_id=resolved.sensor_id,
        sensor_type=resolved.sensor_type,
        calibration_id=resolved.calibration_id,
        calibration_revision=resolved.calibration_revision,
        calibration_reference=resolved.calibration_reference,
        uncertainty=resolved.uncertainty,
        uncertainty_unit=resolved.uncertainty_unit,
        location_m=resolved.location_m,
        orientation_deg=resolved.orientation_deg,
        sample_rate_hz=resolved.sample_rate_hz,
        filtering=resolved.filtering,
    )


def dataset_sensor_provenance(plan: ExperimentPlan) -> tuple[ChannelProvenance, ...]:
    """Resolve provenance for every declared channel, in declaration order."""

    return tuple(channel_provenance(plan, channel.name) for channel in plan.channels)
