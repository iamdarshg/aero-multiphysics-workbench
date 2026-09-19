#!/usr/bin/env python3
"""Emit a machine-readable capability manifest for a solver worker image.

Runs at image build time and again at first start. The probe semantics mirror
``solvers/participants/capabilities.py`` exactly (executables are probed with
``--version``, libraries through importlib metadata only -- never an import of
the heavy module). The manifest is the receipt that runtime participant
probing must agree with before native results can publish.

This file is generic infrastructure: it contains no application cases and
performs no solver installation.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from importlib import metadata
from pathlib import Path

SCHEMA_VERSION = 1

# Mirrors capabilities._EXECUTABLE_PROBES for the solvers the images provide.
EXECUTABLE_PROBES: dict[str, tuple[str, ...]] = {
    "openfoam": ("simpleFoam", "pimpleFoam", "rhoSimpleFoam", "rhoPimpleFoam"),
    "code-aster": ("as_run",),
    "precice": ("precice-config-visualizer",),
    "elmer": ("ElmerSolver",),
    "gmsh": ("gmsh",),
}

# Mirrors capabilities._LIBRARY_PROBES plus the additional participant stack.
LIBRARY_PROBES: dict[str, tuple[str, ...]] = {
    "ross": ("ross-rotordynamics",),
    "pybamm": ("pybamm", "pybammsolvers", "casadi"),
    "gmsh": ("gmsh",),
    "cadquery": ("cadquery",),
    "cantera": ("cantera",),
    "openmdao": ("openmdao",),
}

# Stable, catalog-aligned presentation order.
SOLVER_ORDER = (
    "openfoam",
    "code-aster",
    "elmer",
    "precice",
    "gmsh",
    "ross",
    "pybamm",
    "cadquery",
    "cantera",
    "openmdao",
)


def probe_executable(executable: str, timeout_s: float = 10.0) -> dict[str, object]:
    resolved = shutil.which(executable)
    if resolved is None:
        return {"state": "unavailable", "kind": "executable", "path": executable,
                "version": None, "detail": f"{executable} is not installed"}
    try:
        completed = subprocess.run(
            [resolved, "--version"], capture_output=True, text=True,
            timeout=timeout_s, check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return {"state": "unavailable", "kind": "executable", "path": resolved,
                "version": None, "detail": f"{executable} probe failed:{exc}"}
    if completed.returncode != 0:
        return {"state": "unavailable", "kind": "executable", "path": resolved,
                "version": None, "detail": f"{executable} exited {completed.returncode}"}
    lines = (completed.stdout.strip() or completed.stderr.strip()).splitlines()
    version = lines[0].strip()[:160] if lines else None
    return {"state": "ready", "kind": "executable", "path": resolved,
            "version": version, "detail": f"{executable} responded to --version"}


def probe_library(distribution: str) -> tuple[str, str | None, str]:
    try:
        version = metadata.version(distribution)
    except metadata.PackageNotFoundError:
        return ("unavailable", None, f"{distribution} is not installed")
    except Exception as exc:  # noqa: BLE001
        return ("unavailable", None, f"{distribution} metadata unreadable:{exc}")
    return ("ready", version, f"{distribution} {version} installed")


def probe_solver(solver_id: str) -> dict[str, object]:
    """Executable-first, library-fallback probe matching capabilities.py."""
    for executable in EXECUTABLE_PROBES.get(solver_id, ()):
        entry = probe_executable(executable)
        if entry["state"] == "ready":
            return {"id": solver_id, **entry}
    for distribution in LIBRARY_PROBES.get(solver_id, ()):
        state, version, detail = probe_library(distribution)
        if state == "ready":
            return {"id": solver_id, "state": state, "kind": "library",
                    "path": distribution, "version": version, "detail": detail}
    return {"id": solver_id, "state": "unavailable", "kind": "executable",
            "path": solver_id, "version": None,
            "detail": f"no executable or library for {solver_id} is installed"}


def build_manifest(*, image: str, role: str, digest: str, base_ref: str,
                   base_digest: str, python_path: str, python_version: str) -> dict[str, object]:
    return {
        "schemaVersion": SCHEMA_VERSION,
        "image": {
            "name": image,
            "role": role,
            "digest": digest,
            "builtAt": datetime.now(UTC).isoformat(),
            "baseRef": base_ref,
            "baseDigest": base_digest,
        },
        "python": {"path": python_path, "version": python_version},
        "solvers": [probe_solver(solver_id) for solver_id in SOLVER_ORDER],
    }


def python_reports_ready(manifest: dict[str, object], solver_id: str) -> bool:
    for entry in manifest.get("solvers", []):
        if entry.get("id") == solver_id:
            return entry.get("state") == "ready"
    return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Emit a worker capability manifest.")
    parser.add_argument("--out", required=True, help="Output JSON path.")
    parser.add_argument("--image", default="aero-worker:local")
    parser.add_argument("--role", default="native-solvers",
                        choices=("python-participants", "native-solvers"))
    parser.add_argument("--digest", default="PENDING")
    parser.add_argument("--base-ref", default="unknown")
    parser.add_argument("--base-digest",
                        default="sha256:" + "0" * 64)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--python-version", default=sys.version.split()[0])
    args = parser.parse_args(argv)

    manifest = build_manifest(
        image=args.image, role=args.role, digest=args.digest,
        base_ref=args.base_ref, base_digest=args.base_digest,
        python_path=args.python, python_version=args.python_version,
    )
    target = Path(args.out)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    ready = [entry["id"] for entry in manifest["solvers"] if entry["state"] == "ready"]
    print(f"capability-manifest {target} ready={','.join(ready) or 'none'}")
    # Fail closed when the image's own base participant stack is unusable: a
    # manifest with no ready solver is evidence of a broken build, not success.
    return 0 if ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
