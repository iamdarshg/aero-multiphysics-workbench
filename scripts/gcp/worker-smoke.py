#!/usr/bin/env python3
"""Bounded worker-image smoke proof (issue #43, deliverable D).

Runs tiny proofs through the repository's governed native participant path and
records a digest-verified receipt:

  * capability agreement -- the image manifest must agree with live runtime
    participant probing, or the smoke exits non-zero (fail closed);
  * light participants (gmsh / PyBaMM / ROSS) are submitted through
    ``NativeJobManager`` with bounded inputs;
  * heavy native families reuse the existing bounded governed bench scripts
    where one exists; where none exists the family is reported SKIPPED with an
    explicit reason rather than fabricated.

No solver is installed here. Any unavailable capability is BLOCKED/SKIPPED
with its probe detail; correctness remains owned by SOLVER-CORR.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

# Solvers the runtime participant prober authoritatively covers.
AUTHORITATIVE = ("openfoam", "code-aster", "elmer", "precice", "gmsh", "ross", "pybamm")

# Bounded governed fixtures for cheap light participants.
JOB_FIXTURES: dict[str, dict[str, object]] = {
    "domain-mesh": {
        "base_size_mm": 6.0,
        "n_rotating": 0,
        "length_mm": 100.0,
        "inner_diameter_mm": 20.0,
        "outer_diameter_mm": 40.0,
        "zone_length_mm": 20.0,
        "zone_gap_mm": 5.0,
    },
    "rotor-modal": {
        "shaft_length_m": 0.4,
        "shaft_diameter_m": 0.02,
        "n_elements": 4,
        "bearing_stiffness_n_m": 1e9,
        "speed_rpm": 3000.0,
    },
    "cell-spm-discharge": {
        "discharge_current_a": 5.0,
        "duration_s": 60.0,
        "n_series": 1,
        "n_parallel": 1,
    },
}

# Existing bounded governed benches for the heavy families.
BENCH_SCRIPTS: dict[str, str] = {
    "openfoam": "scripts/gcp/bench_openfoam.py",
    "elmer": "scripts/gcp/bench_elmer.py",
    "precice": "scripts/gcp/bench_precice.py",
    "ross": "scripts/gcp/bench_ross.py",
}

_VERSION_RE = re.compile(r"\d+(?:\.\d+)+")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def versions_compatible(manifest_version: object, probed_version: object) -> bool:
    a = "" if manifest_version is None else str(manifest_version).strip().lower()
    b = "" if probed_version is None else str(probed_version).strip().lower()
    if not a or not b:
        return a == b
    if a == b or a in b or b in a:
        return True
    tokens_a = set(_VERSION_RE.findall(a))
    tokens_b = set(_VERSION_RE.findall(b))
    return bool(tokens_a & tokens_b)


def capability_agreement(manifest: dict[str, object]) -> dict[str, object]:
    """Compare the image manifest against live participant probing."""
    from participants.capabilities import probe_solver

    entries = {entry["id"]: entry for entry in manifest.get("solvers", [])}
    mismatches: list[str] = []
    checked: list[str] = []
    for solver_id in AUTHORITATIVE:
        entry = entries.get(solver_id)
        if entry is None:
            mismatches.append(f"{solver_id}:missing-from-manifest")
            continue
        probe = probe_solver(solver_id)
        checked.append(solver_id)
        if probe.state != entry["state"]:
            mismatches.append(f"{solver_id}:state manifest={entry['state']} live={probe.state}")
            continue
        if probe.state == "ready" and not versions_compatible(entry.get("version"), probe.version):
            mismatches.append(
                f"{solver_id}:version manifest={entry.get('version')!r} live={probe.version!r}"
            )
    # Non-authoritative library entries are verified directly against metadata.
    for solver_id, entry in entries.items():
        if solver_id in AUTHORITATIVE or entry.get("kind") != "library":
            continue
        try:
            actual = importlib.metadata.version(str(entry["path"]))
        except importlib.metadata.PackageNotFoundError:
            mismatches.append(f"{solver_id}:advisory-library-missing")
            continue
        if entry["state"] == "ready" and not versions_compatible(entry.get("version"), actual):
            mismatches.append(
                f"{solver_id}:advisory-version manifest={entry.get('version')!r} live={actual!r}"
            )
    return {"checked": checked, "mismatches": mismatches}


def run_governed_job(
    participant_id: str, inputs: dict[str, object], jobs_root: Path, timeout_s: float
) -> dict[str, object]:
    from participants.lifecycle import NativeJobManager

    manager = NativeJobManager(jobs_root, timeout_s=timeout_s)
    try:
        job_id = manager.submit(participant_id, inputs)
        deadline = time.time() + timeout_s + 30.0
        while time.time() < deadline:
            status = manager.status(job_id)
            if status["state"] in {"COMPLETED", "FAILED", "CANCELLED"}:
                break
            time.sleep(0.25)
        else:
            return {
                "participant_id": participant_id,
                "status": "BLOCKED",
                "reason": f"timeout waiting for job {job_id}",
            }
        result: dict[str, object] = {
            "participant_id": participant_id,
            "job_id": job_id,
            "state": status["state"],
            "status": "EXECUTED" if status["state"] == "COMPLETED" else "FAILED",
        }
        if status["state"] == "COMPLETED":
            envelope = manager.envelope(job_id)
            result["result_id"] = status.get("result_id")
            result["solver_version"] = envelope.get("evidence", {}).get("solver_version")
            artifacts = manager.artifacts(job_id)
            result["artifacts"] = [
                {"name": item["name"], "sha256": item["sha256"], "bytes": item["bytes"]}
                for item in artifacts
            ]
        else:
            result["error"] = status.get("error_detail") or status.get("error_code")
        return result
    finally:
        manager.close()


def run_bench(
    repo: Path, solver_id: str, env: dict[str, str], timeout_s: float
) -> dict[str, object]:
    script = repo / BENCH_SCRIPTS[solver_id]
    if not script.is_file():
        return {
            "solver_id": solver_id,
            "status": "SKIPPED",
            "reason": f"bounded bench missing: {script}",
        }
    try:
        completed = subprocess.run(
            [sys.executable, str(script)],
            cwd=str(repo),
            capture_output=True,
            text=True,
            timeout=timeout_s,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return {"solver_id": solver_id, "status": "BLOCKED", "reason": f"timeout {timeout_s}s"}
    return {
        "solver_id": solver_id,
        "status": "EXECUTED" if completed.returncode == 0 else "FAILED",
        "exit": completed.returncode,
        "stdout": completed.stdout.strip()[-200:],
        "stderr": completed.stderr.strip()[-200:],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bounded worker-image smoke proof.")
    parser.add_argument("--manifest", default="/opt/worker/capability-manifest.json")
    parser.add_argument("--repo", default=os.environ.get("AERO_REPO_ROOT", "/opt/repo"))
    parser.add_argument("--out-dir", default="/var/log/proofs/receipts")
    parser.add_argument("--timeout-s", type=float, default=300.0, dest="timeout_s")
    args = parser.parse_args(argv)

    repo = Path(args.repo)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    receipt: dict[str, object] = {
        "proof": "worker-image-smoke",
        "startedAt": datetime.now(UTC).isoformat(),
        "manifest": args.manifest,
        "repo": str(repo),
        "solvers": [],
    }

    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    agreement = capability_agreement(manifest)
    receipt["capabilityAgreement"] = agreement
    if agreement["mismatches"]:
        receipt["status"] = "MISMATCH"
        receipt["reason"] = "image manifest disagrees with runtime participant probing"
        _write_receipt(out_dir, receipt)
        print(f"SMOKE MISMATCH {agreement['mismatches']}", file=sys.stderr)
        return 2

    env = dict(os.environ)
    env.setdefault("RECEIPTS", str(out_dir))
    jobs_root = Path(tempfile.mkdtemp(prefix="aero-smoke-"))

    # Light governed participants (actual participant path).
    from participants.capabilities import probe_participant

    for participant_id, inputs in JOB_FIXTURES.items():
        probe = probe_participant(participant_id)
        if probe.state != "ready":
            receipt["solvers"].append(
                {
                    "solver_id": probe.solver_id,
                    "participant_id": participant_id,
                    "status": "BLOCKED",
                    "reason": probe.detail,
                }
            )
            continue
        entry = run_governed_job(participant_id, inputs, jobs_root, args.timeout_s)
        entry["solver_id"] = probe.solver_id
        receipt["solvers"].append(entry)

    # Heavy families: reuse bounded governed benches where they exist.
    seen = {entry.get("solver_id") for entry in receipt["solvers"]}
    for solver_id in BENCH_SCRIPTS:
        if solver_id in seen:
            continue
        receipt["solvers"].append(run_bench(repo, solver_id, env, args.timeout_s))
        seen.add(solver_id)

    # Code_Aster has no bounded governed bench in this repository; report
    # SKIPPED honestly instead of substituting an analytical claim.
    probe_aster = probe_participant("structural-static")
    if "code-aster" not in seen:
        if probe_aster.state == "ready":
            receipt["solvers"].append(
                {
                    "solver_id": "code-aster",
                    "status": "SKIPPED",
                    "reason": "no bounded governed fixture; SOLVER-CORR owns correctness",
                }
            )
        else:
            receipt["solvers"].append(
                {
                    "solver_id": "code-aster",
                    "status": "BLOCKED",
                    "reason": probe_aster.detail,
                }
            )

    executed = [e for e in receipt["solvers"] if e.get("status") == "EXECUTED"]
    receipt["status"] = "EXECUTED" if executed else "BLOCKED"
    receipt["finishedAt"] = datetime.now(UTC).isoformat()
    _write_receipt(out_dir, receipt)
    print(f"SMOKE {receipt['status']} executed={len(executed)}")
    return 0


def _write_receipt(out_dir: Path, receipt: dict[str, object]) -> None:
    target = out_dir / "worker-image-smoke.json"
    target.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    digest = sha256_file(target)
    (out_dir / "worker-image-smoke.json.sha256").write_text(
        f"{digest}  worker-image-smoke.json\n", encoding="utf-8"
    )


if __name__ == "__main__":
    raise SystemExit(main())
