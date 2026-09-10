"""Six-cell battery contract; native PyBaMM remains capability-gated."""

from __future__ import annotations

import shutil
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PybammCapability:
    state: str
    executable: str
    detail: str


@dataclass(frozen=True, slots=True)
class PackState:
    cells_in_series: int
    voltage_v: float
    current_a: float
    soc: float
    temperature_c: float
    fidelity: str


def inspect_pybamm(executable: str = "pybamm") -> PybammCapability:
    resolved = shutil.which(executable)
    if resolved is None:
        return PybammCapability("unavailable", executable, "PyBaMM is not installed")
    return PybammCapability("ready", resolved, "native PyBaMM command is discoverable")


def six_cell_series_state(
    *,
    voltage_per_cell_v: float,
    current_a: float,
    soc: float,
    temperature_c: float = 25.0,
    fidelity: str = "ecm",
) -> PackState:
    if voltage_per_cell_v <= 0 or current_a < 0 or not 0 <= soc <= 1:
        raise ValueError("INVALID_PACK_STATE")
    if fidelity not in {"ecm", "spme", "dfn"}:
        raise ValueError("INVALID_BATTERY_FIDELITY")
    return PackState(6, voltage_per_cell_v * 6.0, current_a, soc, temperature_c, fidelity)
