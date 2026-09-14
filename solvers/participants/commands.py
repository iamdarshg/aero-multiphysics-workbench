"""Allowlisted native command construction.

Callers choose a participant and an opaque case id; the participant manifest
chooses the executable and the fixed argument template. Arbitrary executable
names, argument vectors, paths, and shell text are rejected here.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from .errors import NativeErrorCode, ParticipantError
from .manifest import get_participant

_OPAQUE_CASE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")

_RUN_SCRIPTS = Path(__file__).resolve().parent / "run_scripts"


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
    if script not in {"run_ross.py", "run_pybamm.py"} or not candidate.is_file():
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
    if solver in {"ross", "pybamm"}:
        script = manifest.executable.run_script
        if script is None:
            raise ParticipantError(
                NativeErrorCode.PREPARATION_FAILED,
                f"{participant_id} declares no run script",
            )
        run_script_path(script)
        executable = python_executable or sys.executable
        if Path(executable).name.lower() not in {"python", "python.exe", "python3"}:
            raise ParticipantError(
                NativeErrorCode.PROCESS_START_FAILED,
                f"python executable not allowlisted:{Path(executable).name}",
            )
        return (executable, script)
    if solver in {"openfoam", "code-aster", "elmer", "precice"}:
        if solver == "code-aster":
            return (manifest.executable.executables[0], "case.export")
        if solver == "elmer":
            return (manifest.executable.executables[0], "case.sif")
        return (manifest.executable.executables[0],)
    raise ParticipantError(
        NativeErrorCode.PREPARATION_FAILED, f"no command template for:{solver}"
    )
