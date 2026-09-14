"""Governed subprocess execution for native solver commands.

One allowlisted argv runs with the case directory as cwd, logs streaming to
files inside the job root, RSS/timeout/cancel enforced by ProcessSupervisor.
No shell, no caller-supplied arguments, no analytical fallback.
"""

from __future__ import annotations

import os
import time
from collections.abc import Mapping
from pathlib import Path
from threading import Event

from aeroworkbench_api.process_supervisor import (
    ProcessPolicy,
    ProcessReceipt,
    ProcessSupervisor,
    SupervisorError,
    is_path_contained,
)
from participants.errors import NativeErrorCode, ParticipantError

if os.name == "nt":
    from participants.win_rss import windows_process_tree_rss_mib as _tree_probe
else:
    _tree_probe = None  # type: ignore[assignment]


def _resilient_probe(pid: int) -> float:
    """Sample tree RSS, tolerating spawn/exit visibility races briefly.

    A just-spawned or just-exited pid can be absent from one snapshot while
    the supervisor loop still observes it alive. Retry on a tight budget;
    persistent absence still fails closed.
    """

    if _tree_probe is None:
        raise SupervisorError("RSS_MONITOR_UNAVAILABLE")
    last: SupervisorError | None = None
    for _ in range(25):
        try:
            return _tree_probe(pid)
        except SupervisorError as exc:
            last = exc
            time.sleep(0.02)
    raise last if last is not None else SupervisorError("RSS_MONITOR_UNAVAILABLE")

_RSS_CEILING_MIB = 896.0


def _map_reason(reason: str | None) -> NativeErrorCode | None:
    mapping = {
        "PROCESS_RSS_LIMIT_EXCEEDED": NativeErrorCode.PROCESS_RSS_LIMIT_EXCEEDED,
        "PROCESS_TIMEOUT": NativeErrorCode.PROCESS_TIMEOUT,
        "PROCESS_CANCELLED": NativeErrorCode.CANCELLED,
        "PROCESS_EXIT_NONZERO": NativeErrorCode.PROCESS_EXIT_NONZERO,
        "RSS_MONITOR_UNAVAILABLE": NativeErrorCode.PROCESS_START_FAILED,
    }
    return mapping.get(reason) if reason is not None else None


def run_governed(
    command: tuple[str, ...],
    *,
    case_dir: Path,
    job_root: Path,
    rss_limit_mib: float = 352.0,
    timeout_s: float = 600.0,
    poll_s: float = 0.05,
    cancel: Event | None = None,
    extra_env: Mapping[str, str] | None = None,
) -> ProcessReceipt:
    """Run one allowlisted command inside the job root and return its receipt."""

    if not command:
        raise ParticipantError(NativeErrorCode.PROCESS_START_FAILED, "empty command")
    if any(not isinstance(arg, str) or not arg for arg in command):
        raise ParticipantError(NativeErrorCode.PROCESS_START_FAILED, "invalid command argv")
    if not is_path_contained(job_root, case_dir):
        raise ParticipantError(
            NativeErrorCode.PROCESS_START_FAILED, "case directory outside job root"
        )
    if not 0 < rss_limit_mib <= _RSS_CEILING_MIB:
        raise ParticipantError(NativeErrorCode.PROCESS_START_FAILED, "RSS limit out of range")
    executable_name = Path(command[0]).name
    policy = ProcessPolicy(
        job_root=job_root,
        allowed_executables=frozenset({executable_name}),
        rss_limit_mib=rss_limit_mib,
        timeout_seconds=timeout_s,
        poll_seconds=poll_s,
    )
    env: dict[str, str] | None = None
    if extra_env:
        env = dict(os.environ)
        env.update(extra_env)
    supervisor = ProcessSupervisor(
        policy, rss_probe=_resilient_probe if os.name == "nt" else None
    )
    try:
        receipt = supervisor.run(command, cwd=case_dir, cancel=cancel, env=env)
    except SupervisorError as exc:
        raise ParticipantError(
            NativeErrorCode.PROCESS_START_FAILED, f"supervisor refused launch:{exc}"
        ) from exc
    if receipt.state != "completed":
        code = _map_reason(receipt.reason) or NativeErrorCode.PROCESS_EXIT_NONZERO
        raise ParticipantError(code, f"native process failed:{receipt.reason}")
    return receipt
