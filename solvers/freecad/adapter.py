"""Headless FreeCAD admission; conversion is never silently emulated."""

from __future__ import annotations

import shutil
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FreeCADReceipt:
    state: str
    executable: str
    detail: str


def inspect_freecad(executable: str = "FreeCADCmd") -> FreeCADReceipt:
    """Report native availability without launching or installing FreeCAD."""

    resolved = shutil.which(executable)
    if resolved is None:
        return FreeCADReceipt("unavailable", executable, "FreeCADCmd is not installed")
    return FreeCADReceipt(
        "ready", resolved, "native executable is discoverable; conversion not run"
    )
