"""CLI entry point for the Python half of the perf smoke suite.

Usage (from the repo root):
  uv run --directory services/api python scripts/perf/perf_suite.py --json out.json

Writes a machine-readable JSON report and prints a short human summary. It is
also imported by ``tests/perf``; the CLI exists so the Node orchestrator
(``perf-smoke.mjs``) can merge Python and Node measurements into one report.
"""

# ruff: noqa: E501 -- CLI help text and report keys read better unwrapped.

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from _bootstrap import ensure_sys_path, path_entries, python_path_string
from perf_metrics import (
    REPO_ROOT,
    SCHEMA_VERSION,
    Context,
    environment_notes,
    python_profile,
    run_python_benchmarks,
)


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bounded Python performance microbenchmarks")
    parser.add_argument("--json", dest="json_path", default=None, help="write the JSON report here")
    parser.add_argument("--deadline-ms", dest="deadline_ms", type=float, default=None)
    parser.add_argument("--only", dest="only", default="", help="comma-separated benchmark-name substrings")
    parser.add_argument("--extended", action="store_true", help="enable heavier opt-in benchmarks")
    parser.add_argument("--profile", action="store_true", help="cProfile the run into a .prof file")
    return parser.parse_args(argv)


def build_context(deadline_ms: float | None, only: str, extended: bool, temp_root: Path) -> Context:
    deadline = None if deadline_ms is None else time.monotonic() + deadline_ms / 1000.0
    return Context(
        repo_root=REPO_ROOT,
        api_dir=REPO_ROOT / "services" / "api",
        temp_root=temp_root,
        deadline=deadline,
        extended=extended,
        only=tuple(token.strip() for token in only.split(",") if token.strip()),
        python_path=python_path_string(),
    )


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(list(argv if argv is not None else sys.argv[1:]))
    ensure_sys_path()
    profile_target = REPO_ROOT / "benchmarks" / "perf" / "reports" / "perf-python.prof"
    # ignore_cleanup_errors: Windows can hold SQLite handles from the app under
    # measurement after the run; the temp dir is outside the workspace and may
    # be reclaimed by the OS. Measurement results are unaffected.
    with tempfile.TemporaryDirectory(prefix="aero-perf-python-", ignore_cleanup_errors=True) as temp:
        context = build_context(args.deadline_ms, args.only, args.extended, Path(temp))
        with python_profile(args.profile, profile_target):
            benchmarks = run_python_benchmarks(context)
        report: dict[str, Any] = {
            "schemaVersion": SCHEMA_VERSION,
            "tool": "aero-perf-python",
            "group": "python",
            "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "environment": environment_notes(context.temp_root),
            "pythonPathEntries": [str(item) for item in path_entries()],
            "benchmarks": benchmarks,
            "summary": _summarize(benchmarks),
        }
    if args.json_path:
        target = Path(args.json_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    _print_summary(report)
    return 0


def _summarize(benchmarks: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "measured": sum(1 for item in benchmarks if item["status"] == "measured"),
        "skipped": sum(1 for item in benchmarks if item["status"] == "skipped"),
        "failed": sum(1 for item in benchmarks if item["status"] == "failed"),
        "wallMs": round(sum(item.get("wallMs", 0.0) for item in benchmarks), 3),
    }


def _print_summary(report: dict[str, Any]) -> None:
    print(f"[perf:python] {report['summary']}")
    for item in report["benchmarks"]:
        if item["status"] == "measured":
            print(
                f"  measured {item['id']}: median={item['median']}ms p95={item['p95']}ms"
                + (f" ({item['itemsPerSecond']}/s)" if item.get("itemsPerSecond") else "")
            )
        else:
            print(f"  {item['status']} {item['id']}: {item['reason']}")


if __name__ == "__main__":
    raise SystemExit(main())
