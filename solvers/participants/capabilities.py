"""Native capability detection for every declared solver.

Executable probes run the fixed ``--version`` probe without a shell and never
install anything. Python-library probes use metadata only, never an import of
the heavy module. A missing probe yields ``unavailable``; never a substitute.
"""

from __future__ import annotations

import dataclasses
import shutil
import subprocess
from importlib import metadata

from participants.manifest import PARTICIPANT_MANIFESTS, get_participant
from participants.receipts import CapabilityProbe

_EXECUTABLE_PROBES: dict[str, tuple[str, ...]] = {
    "openfoam": ("simpleFoam", "pimpleFoam", "rhoSimpleFoam", "rhoPimpleFoam"),
    "code-aster": ("as_run",),
    "precice": ("precice-config-visualizer",),
    "elmer": ("ElmerSolver",),
    "freecad": ("FreeCADCmd",),
    "gmsh": ("gmsh",),
    "openvsp": ("vsp",),
    "cantera": ("cantera",),
    "pycycle": ("pycycle",),
    "cadquery": ("cadquery",),
}

_LIBRARY_PROBES: dict[str, tuple[str, ...]] = {
    "ross": ("ross-rotordynamics",),
    "pybamm": ("pybamm", "pybammsolvers", "casadi"),
    "gmsh": ("gmsh",),
    "cadquery": ("cadquery",),
}


def _probe_executable(executable: str, timeout_s: float = 10.0) -> tuple[str, str | None, str]:
    resolved = shutil.which(executable)
    if resolved is None:
        return ("unavailable", None, f"{executable} is not installed")
    try:
        completed = subprocess.run(
            [resolved, "--version"],
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return ("unavailable", None, f"{executable} probe failed:{exc}")
    if completed.returncode != 0:
        return ("unavailable", None, f"{executable} exited {completed.returncode}")
    first_line = (completed.stdout.strip() or completed.stderr.strip()).splitlines()
    version = first_line[0].strip()[:160] if first_line else None
    return ("ready", version, f"{executable} responded to --version")


def _probe_library(distribution: str) -> tuple[str, str | None, str]:
    try:
        version = metadata.version(distribution)
    except metadata.PackageNotFoundError:
        return ("unavailable", None, f"{distribution} is not installed")
    except Exception as exc:  # noqa: BLE001
        return ("unavailable", None, f"{distribution} metadata unreadable:{exc}")
    return ("ready", version, f"{distribution} {version} installed")


def probe_solver(solver_id: str) -> CapabilityProbe:
    """Probe one solver family, preferring its native executable."""

    for executable in _EXECUTABLE_PROBES.get(solver_id, ()):
        state, version, detail = _probe_executable(executable)
        if state == "ready":
            return CapabilityProbe(
                participant_id=solver_id,
                solver_id=solver_id,
                executable=executable,
                state=state,
                version=version,
                detail=detail,
            )
    for distribution in _LIBRARY_PROBES.get(solver_id, ()):
        state, version, detail = _probe_library(distribution)
        if state == "ready":
            return CapabilityProbe(
                participant_id=solver_id,
                solver_id=solver_id,
                executable=distribution,
                state=state,
                version=version,
                detail=detail,
            )
    fallback_executable = next(
        iter(_EXECUTABLE_PROBES.get(solver_id, ("unknown",))), "unknown"
    )
    return CapabilityProbe(
        participant_id=solver_id,
        solver_id=solver_id,
        executable=fallback_executable,
        state="unavailable",
        version=None,
        detail=f"no executable or library for {solver_id} is installed",
    )


def probe_participant(participant_id: str) -> CapabilityProbe:
    """Probe the executable capability backing one participant."""

    manifest = get_participant(participant_id)
    solver_id = manifest.executable.solver_id
    if manifest.executable.execution_mode == "in-process" and solver_id in {"gmsh", "freecad"}:
        if solver_id == "gmsh":
            state, version, detail = _probe_library("gmsh")
            if state == "ready":
                return CapabilityProbe(
                    participant_id, solver_id, "gmsh", state, version, detail
                )
            return CapabilityProbe(
                participant_id, solver_id, "gmsh", "unavailable", None, detail
            )
        native_state, native_version, native_detail = _probe_executable("FreeCADCmd")
        if native_state == "ready":
            return CapabilityProbe(
                participant_id,
                solver_id,
                "FreeCADCmd",
                native_state,
                native_version,
                native_detail,
            )
        fallback = _probe_library("cadquery")
        detail = (
            f"FreeCADCmd unavailable; OCC fallback via cadquery: {fallback[2]}"
            if fallback[0] == "ready"
            else "neither FreeCADCmd nor cadquery is installed"
        )
        return CapabilityProbe(
            participant_id,
            solver_id,
            "FreeCADCmd" if fallback[0] != "ready" else "ocp-fallback",
            fallback[0],
            fallback[1],
            detail,
        )
    if solver_id in {"ross", "pybamm"}:
        distributions = _LIBRARY_PROBES[solver_id]
        versions: list[str] = []
        for distribution in distributions:
            state, version, detail = _probe_library(distribution)
            if state != "ready":
                return CapabilityProbe(
                    participant_id, solver_id, distribution, "unavailable", None, detail
                )
            versions.append(f"{distribution}=={version}")
        return CapabilityProbe(
            participant_id,
            solver_id,
            "python",
            "ready",
            "; ".join(versions),
            f"governed python-module execution: {'; '.join(versions)}",
        )
    probe = probe_solver(solver_id)
    return dataclasses.replace(probe, participant_id=participant_id)


def probe_all() -> list[CapabilityProbe]:
    """Probe every participant; one entry per participant id, stable order."""

    return [
        probe_participant(manifest.participant_id)
        for manifest in PARTICIPANT_MANIFESTS
    ]
