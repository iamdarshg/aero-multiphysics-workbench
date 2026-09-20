"""High-lift geometry semantics: deployable surfaces and deflection schedules."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from .errors import HighLiftError, finite

DEVICE_KINDS: tuple[str, ...] = ("flap", "slat", "elevon", "flaperon", "multi_element")

MODEL_DEVICES = "vehicle-systems.highlift.devices"


@dataclass(frozen=True, slots=True)
class DeviceIncrements:
    dcl_per_deg: float
    dcd_per_deg: float
    dcd_quad_per_deg2: float
    dcm_per_deg: float
    dstall_per_deg: float
    area_gain_per_deg: float = 0.0

    def __post_init__(self) -> None:
        for label, value in (
            ("DCL", self.dcl_per_deg),
            ("DCD", self.dcd_per_deg),
            ("DCD_QUAD", self.dcd_quad_per_deg2),
            ("DCM", self.dcm_per_deg),
            ("DSTALL", self.dstall_per_deg),
            ("AREA_GAIN", self.area_gain_per_deg),
        ):
            finite(value, f"INCREMENT_{label}")

    def canonical(self) -> dict[str, float]:
        return {
            "dclPerDeg": self.dcl_per_deg,
            "dcdPerDeg": self.dcd_per_deg,
            "dcdQuadPerDeg2": self.dcd_quad_per_deg2,
            "dcmPerDeg": self.dcm_per_deg,
            "dstallPerDeg": self.dstall_per_deg,
            "areaGainPerDeg": self.area_gain_per_deg,
        }


@dataclass(frozen=True, slots=True)
class HighLiftDevice:
    device_id: str
    parent_id: str
    kind: str
    chord_fraction: float
    span_fraction: tuple[float, float]
    deflection_deg: float = 0.0
    deflection_limits_deg: tuple[float, float] = (0.0, 40.0)
    increments: DeviceIncrements = DeviceIncrements(
        dcl_per_deg=0.02,
        dcd_per_deg=0.0004,
        dcd_quad_per_deg2=0.00002,
        dcm_per_deg=-0.004,
        dstall_per_deg=-0.05,
    )

    def __post_init__(self) -> None:
        if not self.device_id.strip():
            raise HighLiftError("DEVICE_ID_REQUIRED")
        if not self.parent_id.strip():
            raise HighLiftError("DEVICE_PARENT_REQUIRED")
        if self.kind not in DEVICE_KINDS:
            raise HighLiftError(f"UNKNOWN_DEVICE_KIND:{self.kind}")
        finite(self.chord_fraction, "chord_fraction", minimum=0.0, maximum=1.0)
        if self.chord_fraction <= 0.0:
            raise HighLiftError("chord_fraction must be positive")
        start, end = self.span_fraction
        finite(start, "span_fraction[0]")
        finite(end, "span_fraction[1]")
        if not 0.0 <= start < end <= 1.0:
            raise HighLiftError("span_fraction must satisfy 0 <= start < end <= 1")
        low, high = self.deflection_limits_deg
        finite(low, "deflection_limits_deg[0]")
        finite(high, "deflection_limits_deg[1]")
        if low >= high:
            raise HighLiftError("deflection limits must satisfy low < high")
        finite(self.deflection_deg, "deflection_deg")
        if not low <= self.deflection_deg <= high:
            raise HighLiftError("deflection_deg outside deflection limits")

    def with_deflection(self, deflection_deg: float) -> HighLiftDevice:
        finite(deflection_deg, "deflection_deg")
        low, high = self.deflection_limits_deg
        if not low <= deflection_deg <= high:
            raise HighLiftError("deflection_deg outside deflection limits")
        return HighLiftDevice(
            device_id=self.device_id,
            parent_id=self.parent_id,
            kind=self.kind,
            chord_fraction=self.chord_fraction,
            span_fraction=self.span_fraction,
            deflection_deg=deflection_deg,
            deflection_limits_deg=self.deflection_limits_deg,
            increments=self.increments,
        )

    def canonical(self) -> dict[str, Any]:
        return {
            "deviceId": self.device_id,
            "parentId": self.parent_id,
            "kind": self.kind,
            "chordFraction": self.chord_fraction,
            "spanFraction": list(self.span_fraction),
            "deflectionDeg": self.deflection_deg,
            "deflectionLimitsDeg": list(self.deflection_limits_deg),
            "increments": self.increments.canonical(),
        }


@dataclass(frozen=True, slots=True)
class ScheduleEntry:
    config_name: str
    deflections: tuple[tuple[str, float], ...]

    def __post_init__(self) -> None:
        if not self.config_name.strip():
            raise HighLiftError("SCHEDULE_CONFIG_NAME_REQUIRED")
        seen: set[str] = set()
        for device_id, deflection in self.deflections:
            if not device_id.strip():
                raise HighLiftError("SCHEDULE_DEVICE_ID_REQUIRED")
            if device_id in seen:
                raise HighLiftError(f"DUPLICATE_SCHEDULE_DEVICE:{device_id}")
            seen.add(device_id)
            finite(deflection, f"schedule deflection {device_id}")

    def canonical(self) -> dict[str, Any]:
        return {
            "configName": self.config_name,
            "deflections": [
                {"deviceId": device_id, "deflectionDeg": deflection}
                for device_id, deflection in self.deflections
            ],
        }


@dataclass(frozen=True, slots=True)
class DeflectionSchedule:
    schedule_id: str
    entries: tuple[ScheduleEntry, ...]

    def __post_init__(self) -> None:
        if not self.schedule_id.strip():
            raise HighLiftError("SCHEDULE_ID_REQUIRED")
        if not self.entries:
            raise HighLiftError("SCHEDULE_REQUIRES_ENTRIES")
        names = [entry.config_name for entry in self.entries]
        if len(set(names)) != len(names):
            raise HighLiftError("SCHEDULE_CONFIG_NAMES_NOT_UNIQUE")

    def deflections_for(self, config_name: str) -> tuple[tuple[str, float], ...]:
        for entry in self.entries:
            if entry.config_name == config_name:
                return entry.deflections
        raise HighLiftError(f"UNKNOWN_SCHEDULE_CONFIG:{config_name}")

    def canonical(self) -> dict[str, Any]:
        return {
            "scheduleId": self.schedule_id,
            "entries": [entry.canonical() for entry in self.entries],
        }


@dataclass(frozen=True, slots=True)
class ConfigurationDelta:
    dcl0: float
    dclmax: float
    dcd: float
    dcm: float
    dstall_deg: float
    area_gain: float

    def canonical(self) -> dict[str, float]:
        return {
            "dcl0": self.dcl0,
            "dclmax": self.dclmax,
            "dcd": self.dcd,
            "dcm": self.dcm,
            "dstallDeg": self.dstall_deg,
            "areaGain": self.area_gain,
        }


@dataclass(frozen=True, slots=True)
class HighLiftConfiguration:
    config_id: str
    devices: tuple[HighLiftDevice, ...]
    schedule_id: str = "declared"

    def __post_init__(self) -> None:
        if not self.config_id.strip():
            raise HighLiftError("CONFIG_ID_REQUIRED")
        if not self.devices:
            raise HighLiftError("CONFIG_REQUIRES_DEVICES")
        ids = [device.device_id for device in self.devices]
        if len(set(ids)) != len(ids):
            raise HighLiftError("CONFIG_DEVICE_IDS_NOT_UNIQUE")

    def with_schedule_config(
        self, config_id: str, schedule: DeflectionSchedule
    ) -> HighLiftConfiguration:
        targets = dict(schedule.deflections_for(config_id))
        deployed = tuple(
            device.with_deflection(targets.get(device.device_id, device.deflection_deg))
            for device in self.devices
        )
        return HighLiftConfiguration(
            config_id=config_id, devices=deployed, schedule_id=schedule.schedule_id
        )

    def delta(self) -> ConfigurationDelta:
        dcl0 = 0.0
        dclmax = 0.0
        dcd = 0.0
        dcm = 0.0
        dstall = 0.0
        area = 0.0
        for device in self.devices:
            span = device.span_fraction[1] - device.span_fraction[0]
            inc = device.increments
            d = device.deflection_deg
            dcl0 += inc.dcl_per_deg * d * span
            dclmax += 0.8 * inc.dcl_per_deg * d * span
            dcd += (inc.dcd_per_deg * d + inc.dcd_quad_per_deg2 * d * d) * span
            dcm += inc.dcm_per_deg * d * span
            dstall += inc.dstall_per_deg * d * span
            area += inc.area_gain_per_deg * d * span
        return ConfigurationDelta(
            dcl0=dcl0, dclmax=dclmax, dcd=dcd, dcm=dcm, dstall_deg=dstall, area_gain=area
        )

    def effective_area_m2(self, clean_area_m2: float) -> float:
        finite(clean_area_m2, "clean_area_m2", positive=True)
        return clean_area_m2 * (1.0 + self.delta().area_gain)

    def canonical(self) -> dict[str, Any]:
        return {
            "configId": self.config_id,
            "scheduleId": self.schedule_id,
            "devices": [device.canonical() for device in self.devices],
            "delta": self.delta().canonical(),
        }

    @property
    def digest(self) -> str:
        payload = json.dumps(self.canonical(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()


__all__ = [
    "DEVICE_KINDS",
    "MODEL_DEVICES",
    "ConfigurationDelta",
    "DeflectionSchedule",
    "DeviceIncrements",
    "HighLiftConfiguration",
    "HighLiftDevice",
    "ScheduleEntry",
]
