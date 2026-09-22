"""Code_Aster case selection with explicit analysis intent."""

from __future__ import annotations

import shutil
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CodeAsterCapability:
    state: str
    executable: str
    detail: str


@dataclass(frozen=True, slots=True)
class StructuralCase:
    analysis: str
    prestress: bool
    thermal_load: bool
    contact: bool
    command: tuple[str, ...]
    contact_mode: str | None = None
    constraint_mode: str = "fixed"


def inspect_code_aster(executable: str | None = None) -> CodeAsterCapability:
    candidates = (executable,) if executable is not None else ("as_run", "run_aster")
    for candidate in candidates:
        resolved = shutil.which(candidate)
        if resolved is not None:
            return CodeAsterCapability(
                "ready", resolved, "native Code_Aster executable is discoverable"
            )
    selected = executable or "as_run"
    return CodeAsterCapability("unavailable", selected, "Code_Aster is not installed")


def prepare_structural_case(
    *,
    analysis: str = "static",
    prestress: bool = False,
    thermal_load: bool = False,
    contact: bool = False,
    contact_mode: str | None = None,
    constraint_mode: str = "fixed",
) -> StructuralCase:
    if analysis not in {"static", "modal", "harmonic", "transient"}:
        raise ValueError("INVALID_STRUCTURAL_ANALYSIS")
    if prestress and analysis not in {"modal", "harmonic", "transient"}:
        raise ValueError("PRESTRESS_REQUIRES_DYNAMIC_ANALYSIS")
    if constraint_mode not in {"fixed", "kinematic"}:
        raise ValueError("UNSUPPORTED_CONSTRAINT_MODE")
    if contact:
        if contact_mode is None:
            contact_mode = "discrete"
        if contact_mode not in {"discrete"}:
            raise ValueError("UNSUPPORTED_CONTACT_MODE")
    elif contact_mode is not None:
        raise ValueError("CONTACT_MODE_WITHOUT_CONTACT")
    return StructuralCase(
        analysis,
        prestress,
        thermal_load,
        contact,
        ("as_run", "--numthreads", "1"),
        contact_mode,
        constraint_mode,
    )
