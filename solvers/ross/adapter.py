"""Rotor-dynamics preparation without claiming a ROSS run."""

from __future__ import annotations

import math
import shutil
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RossCapability:
    state: str
    executable: str
    detail: str


@dataclass(frozen=True, slots=True)
class CriticalSpeed:
    natural_frequency_hz: float
    rpm: float
    method: str


def inspect_ross(executable: str = "ross") -> RossCapability:
    resolved = shutil.which(executable)
    if resolved is None:
        return RossCapability("unavailable", executable, "ROSS is not installed")
    return RossCapability("ready", resolved, "native ROSS command is discoverable")


def first_critical_speed(*, stiffness_n_m: float, modal_mass_kg: float) -> CriticalSpeed:
    if stiffness_n_m <= 0 or modal_mass_kg <= 0:
        raise ValueError("INVALID_ROTOR_PROPERTIES")
    frequency = math.sqrt(stiffness_n_m / modal_mass_kg) / (2.0 * math.pi)
    return CriticalSpeed(frequency, frequency * 60.0, "single-mode screening; native ROSS not run")
