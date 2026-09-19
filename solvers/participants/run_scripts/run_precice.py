#!/usr/bin/env python3
"""Governed native preCICE implicit coupling window.

Launched by the allowlisted command ``python run_precice.py`` with the case
directory as cwd. Two small participants (A provides ``A-Mesh``, B provides
``B-Mesh``) exchange a scalar field across nonmatching generated interface
meshes over a real preCICE serial-implicit scheme. Checkpoint/rollback hooks and
per-iteration interface residuals are recorded; the run fails closed if no
interpreter can import the native ``precice`` binding. No analytical transfer
is ever substituted: a blocked engine exits nonzero with the exact reason.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

CASE_DIR = Path.cwd()
CONFIG_NAME = "precice-config.xml"


def _fail(detail: str, code: int = 3) -> int:
    sys.stderr.write(f"PRECICE_NATIVE_BLOCKED:{detail}\n")
    return code


def find_precice_python() -> str | None:
    candidates: list[str] = []
    env = os.environ.get("PRECICE_PYTHON")
    if env:
        candidates.append(env)
    candidates.extend(
        [
            "/opt/precice/bin/python",
            shutil.which("python3") or "",
            shutil.which("python") or "",
            sys.executable,
        ]
    )
    seen: set[str] = set()
    for candidate in candidates:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        try:
            probe = subprocess.run(
                [candidate, "-c", "import precice"], capture_output=True, timeout=120
            )
        except (OSError, subprocess.SubprocessError):
            continue
        if probe.returncode == 0:
            return candidate
    return None


PARTICIPANT_A = """
import json, sys
import precice

field_a, field_b, n, cfg, dt = (
    sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4], float(sys.argv[5])
)


def write_data(p, mesh, name, ids, values):
    try:
        p.write_data(mesh, name, ids, values)
    except TypeError:
        p.write_data(name, ids, values)


def read_data(p, mesh, name, ids):
    try:
        return p.read_data(mesh, name, ids)
    except TypeError:
        try:
            return p.read_data(mesh, name, ids, 0.0)
        except TypeError:
            return p.read_data(name, ids)


p = precice.Participant("A", cfg, 0, 1)
coords = [[i / (n - 1), 0.0] for i in range(n)]
ids = p.set_mesh_vertices("A-Mesh", coords)
base = [10.0 * c[0] for c in coords]
state = list(base)
p.initialize()
events = []
it = 0
received = [0.0] * n
while p.is_coupling_ongoing():
    if p.requires_writing_checkpoint():
        events.append({"participant": "A", "event": "write_checkpoint", "iter": it})
        try:
            p.write_checkpoint()
        except Exception:
            pass
    write_data(p, "A-Mesh", field_a, ids, state)
    p.advance(dt)
    if p.requires_reading_checkpoint():
        events.append({"participant": "A", "event": "read_checkpoint", "iter": it})
        try:
            p.read_checkpoint()
        except Exception:
            pass
    received = [float(v) for v in read_data(p, "A-Mesh", field_b, ids)]
    state = [b + 0.1 * r for b, r in zip(base, received)]
    it += 1
p.finalize()
json.dump(
    {"coords": [c[0] for c in coords], "received": received, "iterations": it,
     "events": events},
    open("A_result.json", "w"),
)
print("A_DONE", it)
"""

PARTICIPANT_B = """
import json, sys
import precice

field_a, field_b, n, cfg, dt = (
    sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4], float(sys.argv[5])
)


def write_data(p, mesh, name, ids, values):
    try:
        p.write_data(mesh, name, ids, values)
    except TypeError:
        p.write_data(name, ids, values)


def read_data(p, mesh, name, ids):
    try:
        return p.read_data(mesh, name, ids)
    except TypeError:
        try:
            return p.read_data(mesh, name, ids, 0.0)
        except TypeError:
            return p.read_data(name, ids)


p = precice.Participant("B", cfg, 0, 1)
coords = [[(i + 0.5) / n, 0.0] for i in range(n)]
ids = p.set_mesh_vertices("B-Mesh", coords)
p.initialize()
events = []
it = 0
residual_trace = []
previous = None
read_values = [0.0] * n
flush = [0.0] * n
while p.is_coupling_ongoing():
    if p.requires_writing_checkpoint():
        events.append({"participant": "B", "event": "write_checkpoint", "iter": it})
        try:
            p.write_checkpoint()
        except Exception:
            pass
    if p.requires_reading_checkpoint():
        events.append({"participant": "B", "event": "read_checkpoint", "iter": it})
        try:
            p.read_checkpoint()
        except Exception:
            pass
    read_values = [float(v) for v in read_data(p, "B-Mesh", field_a, ids)]
    if previous is not None:
        residual_trace.append(max(abs(a - b) for a, b in zip(read_values, previous)))
    previous = list(read_values)
    flush = [2.0 * v for v in read_values]
    write_data(p, "B-Mesh", field_b, ids, flush)
    p.advance(dt)
    it += 1
p.finalize()
json.dump(
    {"coords": [c[0] for c in coords], "source_flux": flush, "read": read_values,
     "iterations": it, "residual_trace": residual_trace, "events": events},
    open("B_result.json", "w"),
)
print("B_DONE", it)
"""


def _trapezoid(coords: list[float], values: list[float]) -> float:
    total = 0.0
    for index in range(len(coords) - 1):
        total += 0.5 * (values[index] + values[index + 1]) * (coords[index + 1] - coords[index])
    return total


def main() -> int:
    config = CASE_DIR / CONFIG_NAME
    if not config.is_file():
        return _fail("precice-config.xml is missing")
    try:
        case = json.loads((CASE_DIR / "case.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return _fail(f"case.json unreadable:{exc}")
    field_a = str(case.get("field_a_to_b", "Temperature"))
    field_b = str(case.get("field_b_to_a", "HeatFlux"))
    n_points = int(case.get("n_interface_points", 8))
    tolerance = float(case.get("tolerance", 1e-6))
    dt = float(case.get("coupling_dt_s", 1.0))

    interpreter = find_precice_python()
    if interpreter is None:
        return _fail("no python interpreter can import the native precice binding")

    (CASE_DIR / "A.py").write_text(PARTICIPANT_A, encoding="utf-8")
    (CASE_DIR / "B.py").write_text(PARTICIPANT_B, encoding="utf-8")
    clean_env = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
    argv = [interpreter, "A.py", field_a, field_b, str(n_points), CONFIG_NAME, repr(dt)]
    argv_b = [interpreter, "B.py", field_a, field_b, str(n_points), CONFIG_NAME, repr(dt)]
    with open(CASE_DIR / "A.log", "w") as log_a, open(CASE_DIR / "B.log", "w") as log_b:
        proc_a = subprocess.Popen(
            argv, cwd=str(CASE_DIR), stdout=log_a, stderr=subprocess.STDOUT, env=clean_env
        )
        proc_b = subprocess.Popen(
            argv_b, cwd=str(CASE_DIR), stdout=log_b, stderr=subprocess.STDOUT, env=clean_env
        )
        try:
            (proc_a.wait(timeout=300), proc_b.wait(timeout=300))
        except subprocess.TimeoutExpired:
            proc_a.kill()
            proc_b.kill()
            return _fail("native coupling timed out")

    (CASE_DIR / "solver.log").write_text(
        (CASE_DIR / "A.log").read_text(errors="replace")[-100000:]
        + "\n--- B ---\n"
        + (CASE_DIR / "B.log").read_text(errors="replace")[-100000:],
        encoding="utf-8",
    )
    if proc_a.returncode != 0 or proc_b.returncode != 0:
        return _fail(f"participant exit codes A={proc_a.returncode} B={proc_b.returncode}")
    try:
        result_a = json.loads((CASE_DIR / "A_result.json").read_text(encoding="utf-8"))
        result_b = json.loads((CASE_DIR / "B_result.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return _fail(f"participant result unreadable:{exc}")

    events = list(result_a.get("events", [])) + list(result_b.get("events", []))
    checkpoints = sum(1 for event in events if event.get("event") == "write_checkpoint")
    rollbacks = sum(1 for event in events if event.get("event") == "read_checkpoint")
    residual_trace = [float(value) for value in result_b.get("residual_trace", [])]
    residual = residual_trace[-1] if residual_trace else float("inf")
    coords_a = [float(value) for value in result_a.get("coords", [])]
    received = [float(value) for value in result_a.get("received", [])]
    coords_b = [float(value) for value in result_b.get("coords", [])]
    source_flux = [float(value) for value in result_b.get("source_flux", [])]
    source_integral = _trapezoid(coords_b, source_flux)
    target_integral = _trapezoid(coords_a, received)
    denominator = max(abs(source_integral), 1e-30)
    conservation = abs(target_integral - source_integral) / denominator
    converged = residual <= tolerance

    payload = {
        "engine": "precice-native",
        "coupling_completed": True,
        "converged": bool(converged),
        "interface_residual": residual,
        "residual_trace": residual_trace,
        "conservation_error": conservation,
        "source_integral": source_integral,
        "target_integral": target_integral,
        "coupling_iterations": int(result_b.get("iterations", 0)),
        "checkpoints": checkpoints,
        "rollbacks": rollbacks,
        "participants": case.get("participants", ["A", "B"]),
        "n_interface_points": n_points,
    }
    (CASE_DIR / "result.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(
        "PRECICE_NATIVE_DONE iterations={} residual={:.3e} conservation={:.3e}".format(
            result_b.get("iterations"), residual, conservation
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
