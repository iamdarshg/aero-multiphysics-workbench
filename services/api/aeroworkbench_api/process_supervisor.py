"""Bounded, shell-free worker process supervision.

This module owns the last safety boundary before a native solver is started. It
does not install tools or provide analytical fallbacks: an executable must be
explicitly allowlisted, the working directory must be below the job root, and
the completion receipt records the observed process outcome and log digests.
"""

from __future__ import annotations

import hashlib
import os
import signal
import subprocess
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from threading import Event


class SupervisorError(RuntimeError):
    """Raised when a process cannot be admitted safely."""


RssProbe = Callable[[int], float]


@dataclass(frozen=True, slots=True)
class ProcessPolicy:
    """Immutable admission and runtime limits for one local worker."""

    job_root: Path
    allowed_executables: frozenset[str]
    rss_limit_mib: float = 896.0
    timeout_seconds: float = 3600.0
    poll_seconds: float = 0.05


@dataclass(frozen=True, slots=True)
class ProcessReceipt:
    """Auditable result of a supervised process attempt."""

    state: str
    exit_code: int | None
    reason: str | None
    peak_rss_mib: float
    stdout_path: str
    stderr_path: str
    stdout_sha256: str
    stderr_sha256: str
    started_at: float
    finished_at: float


def is_path_contained(root: Path, candidate: Path) -> bool:
    """Return true only when candidate is root or a descendant of root."""

    try:
        root_resolved = root.resolve(strict=False)
        candidate_resolved = candidate.resolve(strict=False)
        candidate_resolved.relative_to(root_resolved)
        return True
    except (OSError, ValueError):
        return False


def _digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _executable_name(executable: str) -> str:
    return Path(executable).name.lower()


class ProcessSupervisor:
    """Run one allowlisted command with timeout, cancellation, and RSS limits."""

    def __init__(self, policy: ProcessPolicy, rss_probe: RssProbe | None = None) -> None:
        if policy.rss_limit_mib <= 0 or policy.rss_limit_mib > 896:
            raise SupervisorError("INVALID_RSS_LIMIT")
        if policy.timeout_seconds <= 0 or policy.poll_seconds <= 0:
            raise SupervisorError("INVALID_PROCESS_TIMING")
        if not policy.allowed_executables:
            raise SupervisorError("EMPTY_EXECUTABLE_ALLOWLIST")
        self._policy = policy
        self._rss_probe = rss_probe or self._default_rss_probe

    @staticmethod
    def _default_rss_probe(pid: int) -> float:
        """Best-effort root RSS probe; callers may inject a process-tree probe.

        Linux hosts expose `/proc` directly. Windows and macOS intentionally
        fail closed unless the embedding worker supplies a platform probe; a
        missing measurement must never be treated as zero RSS.
        """

        if os.name == "posix":
            status = Path(f"/proc/{pid}/status")
            try:
                for line in status.read_text(encoding="utf-8").splitlines():
                    if line.startswith("VmRSS:"):
                        return float(line.split()[1]) / 1024.0
            except (FileNotFoundError, OSError, ValueError, IndexError):
                raise SupervisorError("RSS_MONITOR_UNAVAILABLE") from None
        raise SupervisorError("RSS_MONITOR_UNAVAILABLE")

    def _validate(self, command: Sequence[str], cwd: Path) -> tuple[str, ...]:
        invalid = any(not isinstance(arg, str) or not arg or "\x00" in arg for arg in command)
        if not command or invalid:
            raise SupervisorError("INVALID_COMMAND")
        executable = command[0]
        allowed = {_executable_name(value) for value in self._policy.allowed_executables}
        if _executable_name(executable) not in allowed:
            raise SupervisorError("COMMAND_NOT_ALLOWLISTED")
        if not is_path_contained(self._policy.job_root, cwd):
            raise SupervisorError("WORKING_DIRECTORY_OUTSIDE_ALLOWLIST")
        if not cwd.exists() or not cwd.is_dir():
            raise SupervisorError("WORKING_DIRECTORY_NOT_FOUND")
        if any("\r" in arg or "\n" in arg for arg in command):
            raise SupervisorError("ARGUMENTS_NOT_ALLOWLISTED")
        return tuple(command)

    @staticmethod
    def _terminate(process: subprocess.Popen[bytes]) -> None:
        if process.poll() is not None:
            return
        if os.name == "nt":
            process.kill()
            return
        killpg = getattr(os, "killpg", None)
        if killpg is None:
            process.kill()
            return
        try:
            killpg(process.pid, getattr(signal, "SIGKILL", signal.SIGTERM))
        except ProcessLookupError:
            return

    def run(
        self,
        command: Sequence[str],
        *,
        cwd: Path,
        cancel: Event | None = None,
        env: Mapping[str, str] | None = None,
    ) -> ProcessReceipt:
        """Execute command and return a digest-backed receipt.

        Logs are streamed to files inside the approved job root instead of
        accumulating unbounded stdout/stderr in worker memory.
        """

        validated = self._validate(command, cwd)
        cwd.mkdir(parents=True, exist_ok=True)
        stdout_path = cwd / "stdout.log"
        stderr_path = cwd / "stderr.log"
        started_at = time.time()
        creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) if os.name == "nt" else 0
        start_new_session = os.name != "nt"
        try:
            with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
                process = subprocess.Popen(
                    validated,
                    cwd=cwd,
                    env=dict(env) if env is not None else None,
                    shell=False,
                    stdin=subprocess.DEVNULL,
                    stdout=stdout,
                    stderr=stderr,
                    close_fds=os.name != "nt",
                    creationflags=creationflags,
                    start_new_session=start_new_session,
                )
                peak_rss = 0.0
                reason: str | None = None
                while process.poll() is None:
                    try:
                        current_rss = float(self._rss_probe(process.pid))
                    except SupervisorError:
                        reason = "RSS_MONITOR_UNAVAILABLE"
                        self._terminate(process)
                        break
                    if current_rss < 0 or current_rss != current_rss:
                        reason = "RSS_MONITOR_UNAVAILABLE"
                        self._terminate(process)
                        break
                    peak_rss = max(peak_rss, current_rss)
                    if current_rss > self._policy.rss_limit_mib:
                        reason = "PROCESS_RSS_LIMIT_EXCEEDED"
                        self._terminate(process)
                        break
                    if cancel is not None and cancel.is_set():
                        reason = "PROCESS_CANCELLED"
                        self._terminate(process)
                        break
                    if time.time() - started_at > self._policy.timeout_seconds:
                        reason = "PROCESS_TIMEOUT"
                        self._terminate(process)
                        break
                    time.sleep(self._policy.poll_seconds)
                process.wait(timeout=2)
                exit_code = process.returncode
        except (OSError, subprocess.SubprocessError) as error:
            finished_at = time.time()
            raise SupervisorError(f"PROCESS_START_FAILED:{error}") from error
        finished_at = time.time()
        if reason is None and exit_code != 0:
            reason = "PROCESS_EXIT_NONZERO"
        return ProcessReceipt(
            state="completed" if reason is None else "failed",
            exit_code=exit_code,
            reason=reason,
            peak_rss_mib=peak_rss,
            stdout_path=str(stdout_path),
            stderr_path=str(stderr_path),
            stdout_sha256=_digest(stdout_path),
            stderr_sha256=_digest(stderr_path),
            started_at=started_at,
            finished_at=finished_at,
        )
