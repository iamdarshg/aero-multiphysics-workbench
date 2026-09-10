"""Elmer native executable discovery."""

from __future__ import annotations

import shutil
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ElmerCapability:
    state: str
    executable: str
    detail: str


def inspect_elmer(executable: str = "ElmerSolver") -> ElmerCapability:
    resolved = shutil.which(executable)
    if resolved is None:
        return ElmerCapability("unavailable", executable, "ElmerSolver is not installed")
    return ElmerCapability("ready", resolved, "native Elmer command is discoverable")
