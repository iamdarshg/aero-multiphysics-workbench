"""Native preCICE capability check and config handoff."""

from __future__ import annotations

import shutil
from dataclasses import dataclass

from aeroworkbench_coupling.precice import PreciceConfig, build_precice_config


@dataclass(frozen=True, slots=True)
class PreciceCapability:
    state: str
    executable: str
    detail: str


def inspect_precice(executable: str = "precice-config-visualizer") -> PreciceCapability:
    resolved = shutil.which(executable)
    if resolved is None:
        return PreciceCapability("unavailable", executable, "preCICE is not installed")
    return PreciceCapability("ready", resolved, "native preCICE tool is discoverable")


def prepare_config(**kwargs: object) -> PreciceConfig:
    return build_precice_config(**kwargs)  # type: ignore[arg-type]
