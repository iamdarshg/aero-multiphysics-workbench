"""Allowlisted native command construction.

Callers choose a participant and an opaque case id; the participant manifest
chooses the executable and the fixed argument template. Arbitrary executable
names, argument vectors, paths, and shell text are rejected here.
"""

from __future__ import annotations

import re
import shutil
import sys
import threading
from pathlib import Path

from .errors import NativeErrorCode, ParticipantError
from .manifest import get_participant

_OPAQUE_CASE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")

_RUN_SCRIPTS = Path(__file__).resolve().parent / "run_scripts"

_ALLOWED_RUN_SCRIPTS = frozenset({"run_ross.py", "run_pybamm.py", "run_precice.py"})

# prepare() records the executable it selected for a case so build_command() can
# honor declared physics (steady/transient, compressible/incompressible) without
# the caller passing a solver-chosen argument vector. Keyed by opaque case id.
_CASE_EXECUTABLES: dict[str, str] = {}
_CASE_LOCK = threading.Lock()


def register_case_executable(case_id: str, executable: str) -> None:
    """Record the allowlisted executable selected during prepare for one case."""

    require_opaque_case_id(case_id)
    if not executable.strip() or "/" in executable or "\\" in executable:
        raise ParticipantError(
            NativeErrorCode.PREPARATION_FAILED, f"invalid case executable:{executable!r}"
        )
    with _CASE_LOCK:
        _CASE_EXECUTABLES[case_id] = executable


def case_executable(case_id: str) -> str | None:
    with _CASE_LOCK:
        return _CASE_EXECUTABLES.get(case_id)


def _select_available(executables: tuple[str, ...]) -> str:
    """Prefer the first manifest-declared executable that is present on PATH."""

    for executable in executables:
        if shutil.which(executable) is not None:
            return executable
    return executables[0]


def is_opaque_case_id(value: str) -> bool:
    return (
        isinstance(value, str)
        and _OPAQUE_CASE_ID.match(value) is not None
        and value not in {".", ".."}
    )


def require_opaque_case_id(value: str) -> str:
    if not is_opaque_case_id(value):
        raise ParticipantError(
            NativeErrorCode.PREPARATION_FAILED, f"case id is not opaque:{value!r}"
        )
    return value


def run_script_path(script: str) -> Path:
    candidate = _RUN_SCRIPTS / script
    if script not in _ALLOWED_RUN_SCRIPTS or not candidate.is_file():
        raise ParticipantError(
            NativeErrorCode.PREPARATION_FAILED, f"run script not allowlisted:{script}"
        )
    return candidate


def build_command(
    participant_id: str, case_id: str, *, python_executable: str | None = None
) -> tuple[str, ...]:
    """Build the fixed argv for one participant case; no caller-supplied args."""

    manifest = get_participant(participant_id)
    require_opaque_case_id(case_id)
    if manifest.executable.execution_mode == "in-process":
        raise ParticipantError(
            NativeErrorCode.PREPARATION_FAILED,
            f"{participant_id} executes in-process; no native command applies",
        )
    solver = manifest.executable.solver_id
    script = manifest.executable.run_script
    if script is not None:
        run_script_path(script)
        executable = python_executable or sys.executable
        if Path(executable).name.lower() not in {"python", "python.exe", "python3"}:
            raise ParticipantError(
                NativeErrorCode.PROCESS_START_FAILED,
                f"python executable not allowlisted:{Path(executable).name}",
            )
        return (executable, script)
    if solver in {"openfoam", "code-aster", "elmer", "precice"}:
        if solver == "openfoam":
            selected = case_executable(case_id) or manifest.executable.executables[0]
            if selected not in manifest.executable.executables:
                raise ParticipantError(
                    NativeErrorCode.PREPARATION_FAILED,
                    f"selected executable not in manifest allowlist:{selected}",
                )
            return (selected,)
        if solver == "code-aster":
            resolved = _select_available(manifest.executable.executables)
            return (resolved, "case.export")
        if solver == "elmer":
            return (manifest.executable.executables[0], "case.sif")
        return (manifest.executable.executables[0],)
    raise ParticipantError(
        NativeErrorCode.PREPARATION_FAILED, f"no command template for:{solver}"
    )
