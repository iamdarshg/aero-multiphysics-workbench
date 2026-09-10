"""Physics-driven OpenFOAM case selection without shell execution."""

from __future__ import annotations

import shutil
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class OpenFoamCapability:
    state: str
    executable: str
    detail: str


@dataclass(frozen=True, slots=True)
class OpenFoamCase:
    compressibility: str
    rotating_model: str
    thermal_model: str
    application: str
    turbulence: str
    expert_overrides: tuple[tuple[str, str], ...]


def inspect_openfoam(executable: str = "simpleFoam") -> OpenFoamCapability:
    resolved = shutil.which(executable)
    if resolved is None:
        return OpenFoamCapability("unavailable", executable, "OpenFOAM is not installed")
    return OpenFoamCapability("ready", resolved, "native OpenFOAM executable is discoverable")


def prepare_case(
    *,
    compressibility: str = "incompressible",
    rotating_model: str = "none",
    thermal_model: str = "isothermal",
    turbulence: str = "kOmegaSST",
    expert_overrides: tuple[tuple[str, str], ...] = (),
) -> OpenFoamCase:
    if compressibility not in {"incompressible", "compressible"}:
        raise ValueError("INVALID_COMPRESSIBILITY")
    if rotating_model not in {"none", "MRF", "AMI"}:
        raise ValueError("INVALID_ROTATING_MODEL")
    if thermal_model not in {"isothermal", "CHT"}:
        raise ValueError("INVALID_THERMAL_MODEL")
    if not turbulence:
        raise ValueError("TURBULENCE_REQUIRED")
    if compressibility == "compressible":
        application = "rhoPimpleFoam"
    elif rotating_model == "AMI":
        application = "pimpleFoam"
    else:
        application = "simpleFoam"
    return OpenFoamCase(
        compressibility, rotating_model, thermal_model, application, turbulence, expert_overrides
    )
