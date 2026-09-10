from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path
from threading import Event

import pytest

from aeroworkbench_api.process_supervisor import (
    ProcessPolicy,
    ProcessSupervisor,
    SupervisorError,
)


def _policy(root: Path, *, limit: float = 64) -> ProcessPolicy:
    return ProcessPolicy(
        job_root=root,
        allowed_executables=frozenset({Path(sys.executable).name}),
        rss_limit_mib=limit,
        timeout_seconds=2,
        poll_seconds=0.01,
    )


def _command(code: str) -> list[str]:
    return [sys.executable, "-c", code]


def test_supervisor_runs_shell_free_and_hashes_streamed_logs(tmp_path: Path) -> None:
    supervisor = ProcessSupervisor(_policy(tmp_path), rss_probe=lambda _pid: 1.0)
    receipt = supervisor.run(_command("print('ready')"), cwd=tmp_path)

    assert receipt.state == "completed"
    assert receipt.exit_code == 0
    assert receipt.reason is None
    assert receipt.peak_rss_mib == 1.0
    assert len(receipt.stdout_sha256) == 64
    assert Path(receipt.stdout_path).read_text(encoding="utf-8").strip() == "ready"


def test_supervisor_fails_closed_for_rss_timeout_and_cancel(tmp_path: Path) -> None:
    too_large = ProcessSupervisor(_policy(tmp_path, limit=4), rss_probe=lambda _pid: 5.0)
    too_large_receipt = too_large.run(_command("import time; time.sleep(1)"), cwd=tmp_path)
    assert too_large_receipt.reason == "PROCESS_RSS_LIMIT_EXCEEDED"

    timed = ProcessSupervisor(
        replace(_policy(tmp_path), timeout_seconds=0.05), rss_probe=lambda _pid: 1.0
    )
    timed_receipt = timed.run(_command("import time; time.sleep(1)"), cwd=tmp_path)
    assert timed_receipt.reason == "PROCESS_TIMEOUT"

    cancel = Event()
    cancel.set()
    cancelled = ProcessSupervisor(_policy(tmp_path), rss_probe=lambda _pid: 1.0)
    cancelled_receipt = cancelled.run(
        _command("import time; time.sleep(1)"), cwd=tmp_path, cancel=cancel
    )
    assert cancelled_receipt.reason == "PROCESS_CANCELLED"


def test_supervisor_rejects_untrusted_command_and_path(tmp_path: Path) -> None:
    supervisor = ProcessSupervisor(_policy(tmp_path), rss_probe=lambda _pid: 1.0)
    with pytest.raises(SupervisorError, match="COMMAND_NOT_ALLOWLISTED"):
        supervisor.run(["definitely-not-a-solver", "--version"], cwd=tmp_path)
    outside = tmp_path.parent / "outside"
    outside.mkdir()
    with pytest.raises(SupervisorError, match="WORKING_DIRECTORY_OUTSIDE_ALLOWLIST"):
        supervisor.run(_command("print('no')"), cwd=outside)


def test_supervisor_does_not_treat_missing_rss_as_zero(tmp_path: Path) -> None:
    def missing_rss(_pid: int) -> float:
        raise SupervisorError("missing")

    supervisor = ProcessSupervisor(_policy(tmp_path), rss_probe=missing_rss)
    receipt = supervisor.run(_command("import time; time.sleep(.2)"), cwd=tmp_path)
    assert receipt.reason == "RSS_MONITOR_UNAVAILABLE"


def test_solver_catalog_is_explicit_and_bounded() -> None:
    catalog_path = Path(__file__).parents[2] / "solvers" / "manifests" / "catalog.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    assert catalog["policy"] == {
        "trustModel": "native-only",
        "shell": False,
        "remoteDefault": False,
        "rssBudgetMiB": 896,
    }
    assert len(catalog["solvers"]) == 12
    assert all(solver["executables"] and solver["checkpoint"] for solver in catalog["solvers"])
