"""CLI for the GEN 12 generic generative-engineering release benchmark.

Usage (bounded, no native binaries):

    uv run --directory services/api python ../../benchmarks/independence/run.py \
        --output gen12-benchmark.json

Full-science (solver-equipped runner; opt-in, never fakes success):

    uv run --directory services/api python ../../benchmarks/independence/run.py \
        --execute-native --require-native --output gen12-full.json

Exit codes:

* ``0``  benchmark ran, its report is reproducible, and no step FAILED; with
        ``--require-native`` every required capability is also PASS/PARTIAL
        rather than BLOCKED.
* ``1``  a step failed, the report was not reproducible, or a required native
        capability is still blocked under ``--require-native``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _bootstrap_path() -> None:
    """Make the uninstalled workspace importable for a plain-script run."""

    candidates = [_REPO_ROOT, _REPO_ROOT / "solvers", _REPO_ROOT / "services" / "api"]
    packages = _REPO_ROOT / "packages"
    if packages.is_dir():
        candidates.extend(sorted(package for package in packages.glob("*") if package.is_dir()))
        candidates.extend(
            sorted(package / "src" for package in packages.glob("*") if package.is_dir())
        )
    for candidate in reversed(candidates):
        if candidate.is_dir() and str(candidate) not in sys.path:
            sys.path.insert(0, str(candidate))


_bootstrap_path()


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=None, help="write the JSON report here")
    parser.add_argument("--workspace", type=Path, default=None, help="scratch directory")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--max-candidates", type=int, default=18)
    parser.add_argument("--no-cad", action="store_true", help="skip real CAD regeneration")
    parser.add_argument("--no-mesh", action="store_true", help="skip real Gmsh meshing")
    parser.add_argument(
        "--execute-native",
        action="store_true",
        help="allow heavyweight native solver execution when the capability is present",
    )
    parser.add_argument(
        "--require-native",
        action="store_true",
        help="fail if any required native capability is still BLOCKED",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    from benchmarks.independence.generic_benchmark import (
        BenchmarkConfig,
        run_generic_benchmark,
    )

    args = _parse_args(argv)
    config = BenchmarkConfig(
        seed=args.seed,
        max_candidates=args.max_candidates,
        execute_cad=not args.no_cad,
        execute_mesh=not args.no_mesh,
        execute_native=args.execute_native,
    )
    report = run_generic_benchmark(args.workspace, config=config)
    payload = report.as_dict()
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
        )
    failed = [step.step for step in report.steps if step.status == "FAILED"]
    blocked = [entry["capability"] for entry in report.audit if entry["status"] == "BLOCKED"]
    partial = [entry["capability"] for entry in report.audit if entry["status"] == "PARTIAL"]
    summary = {
        "benchmarkId": report.benchmark_id,
        "reproducible": report.reproducible,
        "failedSteps": failed,
        "blockedCapabilities": blocked,
        "partialCapabilities": partial,
        "validatedFinalCandidates": sum(
            1 for item in report.candidate_set if item["validatedFinal"]
        ),
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    if failed or not report.reproducible:
        return 1
    if args.require_native and blocked:
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    sys.exit(main())
