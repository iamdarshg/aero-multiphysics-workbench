"""Native capability detection for every declared solver.

Executable probes run the fixed ``--version`` probe without a shell and never
install anything. Python-library probes use metadata only, never an import of
the heavy module. A missing probe yields ``unavailable``; never a substitute.
"""

from __future__ import annotations

import dataclasses
import os
import re
import shutil
import subprocess
from importlib import metadata

from participants.manifest import PARTICIPANT_MANIFESTS, get_participant
from participants.receipts import CapabilityProbe

_EXECUTABLE_PROBES: dict[str, tuple[str, ...]] = {
    "openfoam": ("simpleFoam", "pimpleFoam", "rhoSimpleFoam", "rhoPimpleFoam"),
    "code-aster": ("as_run", "run_aster"),
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
    "cantera": ("cantera",),
}


def _probe_executable(
    executable: str,
    timeout_s: float = 10.0,
    *,
    probe_args: tuple[str, ...] = ("--version",),
    accept_output_on_nonzero: bool = False,
) -> tuple[str, str | None, str]:
    resolved = shutil.which(executable)
    if resolved is None:
        return ("unavailable", None, f"{executable} is not installed")
    try:
        completed = subprocess.run(
            [resolved, *probe_args],
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return ("unavailable", None, f"{executable} probe failed:{exc}")
    output = completed.stdout.strip() or completed.stderr.strip()
    if completed.returncode != 0 and not (accept_output_on_nonzero and output):
        return ("unavailable", None, f"{executable} exited {completed.returncode}")
    first_line = output.splitlines()
    version = first_line[0].strip()[:160] if first_line else None
    if version is None:
        return ("unavailable", None, f"{executable} responded with no version output")
    return ("ready", version, f"{executable} responded to {' '.join(probe_args)}")


_OPENFOAM_VERSION = re.compile(
    r"(?:Version:\s*|OpenFOAM[-_ ]?(?:version)?[-_ ]?v?)([0-9][0-9A-Za-z._-]*)",
    re.IGNORECASE,
)


def _openfoam_version_text(output: str) -> str | None:
    match = _OPENFOAM_VERSION.search(output)
    if match is not None:
        return f"OpenFOAM {match.group(1)}"
    env = os.environ.get("WM_PROJECT_VERSION")
    if env:
        return f"OpenFOAM {env}"
    return None


def _probe_openfoam(executable: str, timeout_s: float = 10.0) -> tuple[str, str | None, str]:
    """Probe an OpenFOAM solver whose ``--version``/``-help`` exits nonzero.

    OpenFOAM v2412 ``simpleFoam --version`` and ``-help`` exit 1 while still
    printing the real banner. Presence plus non-empty version/usage output is
    trusted; a genuinely missing binary or one that prints nothing is not.
    """

    resolved = shutil.which(executable)
    if resolved is None:
        return ("unavailable", None, f"{executable} is not installed")
    last_detail = f"{executable} produced no probe output"
    for probe_args in (("-help",), ("--version",), ("-version",)):
        try:
            completed = subprocess.run(
                [resolved, *probe_args],
                capture_output=True,
                text=True,
                timeout=timeout_s,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            last_detail = f"{executable} probe failed:{exc}"
            continue
        output = (completed.stdout or "") + "\n" + (completed.stderr or "")
        if not output.strip():
            continue
        version = _openfoam_version_text(output) or "OpenFOAM (version banner absent)"
        return ("ready", version[:160], f"{executable} present and reported a banner")
    env_version = os.environ.get("WM_PROJECT_VERSION")
    if env_version:
        return ("ready", f"OpenFOAM {env_version}", f"{executable} present; WM_PROJECT_VERSION set")
    return ("unavailable", None, last_detail)


def _probe_library(distribution: str) -> tuple[str, str | None, str]:
    try:
        version = metadata.version(distribution)
    except metadata.PackageNotFoundError:
        return ("unavailable", None, f"{distribution} is not installed")
    except Exception as exc:  # noqa: BLE001
        return ("unavailable", None, f"{distribution} metadata unreadable:{exc}")
    return ("ready", version, f"{distribution} {version} installed")


def _probe_precice_interpreter() -> tuple[str | None, list[str]]:
    """Find a python interpreter that imports the native ``precice`` binding."""

    try:
        from precice.interpreter import find_precice_interpreter
    except Exception as exc:  # noqa: BLE001
        return None, [f"interpreter discovery unavailable:{type(exc).__name__}:{exc}"]
    return find_precice_interpreter()


def probe_solver(solver_id: str) -> CapabilityProbe:
    """Probe one solver family, preferring its native executable."""

    for executable in _EXECUTABLE_PROBES.get(solver_id, ()):
        if solver_id == "openfoam":
            state, version, detail = _probe_openfoam(executable)
        else:
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
    if solver_id == "precice" and manifest.executable.run_script is not None:
        # A native coupled-window participant is launched through its Python
        # preCICE binding: a python interpreter that can actually import the
        # native ``precice`` module is the only valid capability. Package
        # metadata alone (and a bare ``precice-tools`` executable) is not
        # sufficient, so probing agrees exactly with run_precice.py.
        interpreter, attempts = _probe_precice_interpreter()
        if interpreter is not None:
            return CapabilityProbe(
                participant_id,
                solver_id,
                interpreter,
                "ready",
                "pyprecice",
                f"native precice binding importable by {interpreter}",
            )
        return CapabilityProbe(
            participant_id,
            solver_id,
            "pyprecice",
            "unavailable",
            None,
            "no python interpreter can import the native precice binding; "
            + "; ".join(attempts),
        )
    probe = probe_solver(solver_id)
    return dataclasses.replace(probe, participant_id=participant_id)


def probe_all() -> list[CapabilityProbe]:
    """Probe every participant; one entry per participant id, stable order."""

    return [
        probe_participant(manifest.participant_id)
        for manifest in PARTICIPANT_MANIFESTS
    ]
