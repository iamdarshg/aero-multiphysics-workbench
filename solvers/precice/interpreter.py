"""Native preCICE Python-binding interpreter discovery.

The native coupled-window participant is launched as ``python run_precice.py``
and must import the real ``precice`` binding in its own interpreter. A conda
preCICE prefix provides that binding for its bundled interpreter, while the
governed uv venv may provide a separate one. This module enumerates the known
prefixes, tests each candidate with a bounded ``import precice`` probe, exposes
the exact attempts for fail-closed reporting, and is shared by the capability
probe and the run script.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from collections.abc import Sequence

DEFAULT_PRECICE_PREFIXES: tuple[str, ...] = (
    "/opt/precice",
    "/opt/precice-env",
    "/opt/pyprecice",
)


def precice_prefixes(env: dict[str, str] | None = None) -> tuple[str, ...]:
    """Explicit prefixes (``PRECICE_PREFIXES``) followed by the defaults."""

    source = os.environ if env is None else env
    raw = source.get("PRECICE_PREFIXES", "")
    extra = tuple(item for item in raw.split(os.pathsep) if item.strip()) if raw else ()
    ordered: list[str] = []
    for prefix in (*extra, *DEFAULT_PRECICE_PREFIXES):
        if prefix not in ordered:
            ordered.append(prefix)
    return tuple(ordered)


def precice_library_path(env: dict[str, str] | None = None) -> str:
    """Prepend every known prefix ``lib`` dir to ``LD_LIBRARY_PATH``."""

    source = dict(os.environ if env is None else env)
    parts = [os.path.join(prefix, "lib") for prefix in precice_prefixes(source)]
    existing = source.get("LD_LIBRARY_PATH", "")
    if existing:
        parts.append(existing)
    return os.pathsep.join(parts)


def candidate_interpreters(env: dict[str, str] | None = None) -> tuple[str, ...]:
    """Ordered interpreters to test, de-duplicated and existence-filtered."""

    source = dict(os.environ if env is None else env)
    candidates: list[str] = []
    explicit = source.get("PRECICE_PYTHON")
    if explicit:
        candidates.append(explicit)
    for prefix in precice_prefixes(source):
        candidates.append(os.path.join(prefix, "bin", "python"))
        candidates.append(os.path.join(prefix, "bin", "python3"))
    for name in ("python3", "python"):
        resolved = shutil.which(name)
        if resolved:
            candidates.append(resolved)
    candidates.append(sys.executable)
    ordered: list[str] = []
    for candidate in candidates:
        if candidate and candidate not in ordered:
            ordered.append(candidate)
    return tuple(ordered)


def probe_interpreter(
    interpreter: str, env: dict[str, str] | None = None, timeout_s: float = 120.0
) -> tuple[bool, str]:
    """Bounded ``import precice`` probe; returns ``(ok, detail)``."""

    probe_env = dict(os.environ if env is None else env)
    probe_env["LD_LIBRARY_PATH"] = precice_library_path(probe_env)
    # The repository ships a sibling ``precice`` package; a leaked PYTHONPATH
    # would shadow the native binding and produce a false negative.
    probe_env.pop("PYTHONPATH", None)
    try:
        completed = subprocess.run(
            [
                interpreter,
                "-c",
                "import precice; print(getattr(precice, '__version__', 'unknown'))",
            ],
            capture_output=True,
            text=True,
            timeout=timeout_s,
            env=probe_env,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"{interpreter}: probe failed:{type(exc).__name__}"
    if completed.returncode == 0:
        version = (completed.stdout or "").strip().splitlines()
        return True, f"{interpreter}: {version[0] if version else 'precice'}"
    detail = (completed.stderr or completed.stdout or "").strip().splitlines()
    reason = detail[-1][:200] if detail else f"exit {completed.returncode}"
    return False, f"{interpreter}: {reason}"


def find_precice_interpreter(
    env: dict[str, str] | None = None,
) -> tuple[str | None, list[str]]:
    """Return the first interpreter that imports ``precice`` and every attempt."""

    attempts: list[str] = []
    for interpreter in candidate_interpreters(env):
        ok, detail = probe_interpreter(interpreter, env)
        attempts.append(detail)
        if ok:
            return interpreter, attempts
    return None, attempts


def interpreter_attempts_summary(attempts: Sequence[str]) -> str:
    return "; ".join(attempts) if attempts else "no candidate interpreters found"
