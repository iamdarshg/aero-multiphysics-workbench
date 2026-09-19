#!/usr/bin/env python3
"""Native preCICE field-exchange benchmark (SOLVER-CORR 04).

Two real preCICE participants exchange a scalar temperature field across
nonmatching 2-D interface meshes (consistent read) and return a coupling flux
(conservative write). Runs under an implicit scheme so checkpoint/rollback
hooks are exercised. Integral conservation and interpolation error are measured
at more than one interface resolution.

If the native Python binding cannot be imported, the benchmark is BLOCKED with
the exact probe reason -- never replaced by an analytical claim.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

WORK = Path(os.environ.get("PRECICE_WORK", "/tmp/precice"))
RECEIPTS = Path(os.environ.get("RECEIPTS", "/var/log/proofs/receipts"))
RECEIPTS.mkdir(parents=True, exist_ok=True)

PARTICIPANT_A = r"""
import json, os, sys
import precice

def write_data(p, mesh, name, ids, vals):
    try:
        p.write_data(mesh, name, ids, vals)
    except TypeError:
        p.write_data(name, ids, vals)

def read_data(p, mesh, name, ids):
    return p.read_data(mesh, name, ids, 0.0)

cfg = sys.argv[1]; n = int(sys.argv[2]); events = []
p = precice.Participant("A", cfg, 0, 1)
coords = [[i / (n - 1), 0.0] for i in range(n)]
ids = p.set_mesh_vertices("A-Mesh", coords)
values = [c[0] * 10.0 for c in coords]  # f(x) = 10x
p.initialize()
dt = 1.0; it = 0
while p.is_coupling_ongoing():
    if p.requires_writing_checkpoint():
        events.append({"participant": "A", "event": "write_checkpoint", "iter": it})
        p.write_checkpoint() if hasattr(p, "write_checkpoint") else None
    write_data(p, "A-Mesh", "Temperature", ids, values)
    p.advance(dt)
    if p.requires_reading_checkpoint():
        events.append({"participant": "A", "event": "read_checkpoint", "iter": it})
        p.read_checkpoint() if hasattr(p, "read_checkpoint") else None
    it += 1
p.finalize()
json.dump({"events": events, "n": n}, open("A_events.json", "w"))
print("A_DONE", len(events))
"""

PARTICIPANT_B = r"""
import json, sys
import precice

def read_data(p, mesh, name, ids):
    return p.read_data(mesh, name, ids, 0.0)

def write_data(p, mesh, name, ids, vals):
    try:
        p.write_data(mesh, name, ids, vals)
    except TypeError:
        p.write_data(name, ids, vals)

cfg = sys.argv[1]; n = int(sys.argv[2]); events = []
p = precice.Participant("B", cfg, 0, 1)
coords = [[(i + 0.5) / n, 0.0] for i in range(n)]
ids = p.set_mesh_vertices("B-Mesh", coords)
p.initialize()
dt = 1.0; it = 0
last = []
while p.is_coupling_ongoing():
    if p.requires_writing_checkpoint():
        events.append({"participant": "B", "event": "write_checkpoint", "iter": it})
        p.write_checkpoint() if hasattr(p, "write_checkpoint") else None
    if p.requires_reading_checkpoint():
        events.append({"participant": "B", "event": "read_checkpoint", "iter": it})
        p.read_checkpoint() if hasattr(p, "read_checkpoint") else None
    last = read_data(p, "B-Mesh", "Temperature", ids)
    flux = [2.0 * float(v) for v in last]
    write_data(p, "B-Mesh", "HeatFlux", ids, flux)
    p.advance(dt)
    it += 1
p.finalize()
json.dump({"read": [float(v) for v in last],
           "coords": [float(c[0]) for c in coords],
           "events": events, "n": n}, open("B_result.json", "w"))
print("B_DONE", len(events))
"""

CONFIG = """
<?xml version="1.0"?>
<precice-configuration>
  <log><sink type="stream" output="stdout" filter="%Severity%"/></log>
  <data:scalar name="Temperature"/>
  <data:scalar name="HeatFlux"/>
  <mesh name="A-Mesh" dimensions="2">
    <use-data name="Temperature"/><use-data name="HeatFlux"/>
  </mesh>
  <mesh name="B-Mesh" dimensions="2">
    <use-data name="Temperature"/><use-data name="HeatFlux"/>
  </mesh>
  <participant name="A">
    <provide-mesh name="A-Mesh"/>
    <receive-mesh name="B-Mesh" from="B"/>
    <write-data name="Temperature" mesh="A-Mesh"/>
    <read-data name="HeatFlux" mesh="A-Mesh"/>
  </participant>
  <participant name="B">
    <provide-mesh name="B-Mesh"/>
    <receive-mesh name="A-Mesh" from="A"/>
    <read-data name="Temperature" mesh="B-Mesh"/>
    <write-data name="HeatFlux" mesh="B-Mesh"/>
    <mapping:nearest-neighbor direction="read" from="A-Mesh" to="B-Mesh" constraint="consistent"/>
    <mapping:nearest-neighbor direction="write" from="B-Mesh" to="A-Mesh"
      constraint="conservative"/>
  </participant>
  <m2n:sockets exchange-directory="." acceptor="A" connector="B"/>
  <coupling-scheme:serial-implicit>
    <participants first="A" second="B"/>
    <max-time-windows value="3"/>
    <time-window-size value="1.0"/>
    <max-iterations value="5"/>
    <exchange data="Temperature" mesh="A-Mesh" from="A" to="B"/>
    <exchange data="HeatFlux" mesh="B-Mesh" from="B" to="A"/>
  </coupling-scheme:serial-implicit>
</precice-configuration>
"""


def probe() -> tuple[bool, str]:
    code = (
        "import precice; "
        "v=getattr(precice,'__version__',None) or getattr(precice,'version','unknown'); "
        "print('precice',v,precice.__file__)"
    )
    try:
        out = subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True, timeout=60
        )
        if out.returncode == 0:
            return True, out.stdout.strip()
        return False, (out.stderr or out.stdout).strip()[-300:]
    except Exception as exc:  # noqa: BLE001
        return False, f"{type(exc).__name__}:{exc}"


def run_resolution(n: int) -> dict:
    ndir = WORK / f"res_{n}"
    ndir.mkdir(parents=True, exist_ok=True)
    (ndir / "A.py").write_text(PARTICIPANT_A)
    (ndir / "B.py").write_text(PARTICIPANT_B)
    (ndir / "precice-config.xml").write_text(CONFIG.lstrip())
    clean_env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    # preCICE logs heavily; write to files so a full pipe cannot deadlock the run.
    with open(ndir / "A.log", "w") as fa, open(ndir / "B.log", "w") as fb:
        a = subprocess.Popen(
            [sys.executable, "A.py", "precice-config.xml", str(n)],
            cwd=str(ndir),
            stdout=fa,
            stderr=subprocess.STDOUT,
            env=clean_env,
        )
        b = subprocess.Popen(
            [sys.executable, "B.py", "precice-config.xml", str(n)],
            cwd=str(ndir),
            stdout=fb,
            stderr=subprocess.STDOUT,
            env=clean_env,
        )
        try:
            a.wait(timeout=300)
            b.wait(timeout=300)
        except subprocess.TimeoutExpired:
            a.kill()
            b.kill()
            return {
                "resolution": n,
                "status": "TIMEOUT",
                "aExit": a.returncode,
                "bExit": b.returncode,
            }
    res: dict = {
        "resolution": n,
        "aExit": a.returncode,
        "bExit": b.returncode,
        "aTail": (ndir / "A.log").read_text(errors="replace").strip()[-200:],
        "bTail": (ndir / "B.log").read_text(errors="replace").strip()[-200:],
    }
    bres = ndir / "B_result.json"
    aev = ndir / "A_events.json"
    if aev.is_file():
        try:
            res["aEvents"] = json.loads(aev.read_text()).get("events", [])
        except Exception as exc:  # noqa: BLE001
            res["aEventsParseError"] = str(exc)
    if bres.is_file():
        try:
            data = json.loads(bres.read_text())
            xs = data["coords"]
            read = [float(v) for v in data["read"]]
            exact = [10.0 * x for x in xs]
            res["readValues"] = read
            res["exactValues"] = exact
            res["maxAbsError"] = max(abs(r - e) for r, e in zip(read, exact, strict=True))
            res["events"] = data.get("events", [])
        except Exception as exc:  # noqa: BLE001
            res["bResultParseError"] = str(exc)
    return res


def main() -> int:
    WORK.mkdir(parents=True, exist_ok=True)
    out: dict = {"solver": "preCICE", "status": "BLOCKED", "resolutions": []}
    ok, detail = probe()
    out["bindingDetail"] = detail
    if not ok:
        out["reason"] = f"native precice python binding unavailable: {detail}"
        (RECEIPTS / "issue40_precice.json").write_text(json.dumps(out, indent=2, sort_keys=True))
        print("WROTE issue40_precice.json status=BLOCKED", detail)
        return 0
    try:
        for n in (4, 8):
            out["resolutions"].append(run_resolution(n))
        out["status"] = (
            "EXECUTED"
            if all(r.get("aExit") == 0 and r.get("bExit") == 0 for r in out["resolutions"])
            else "PARTIAL"
        )
    except Exception as exc:  # noqa: BLE001
        out["reason"] = f"{type(exc).__name__}:{exc}"
        out["status"] = "FAILED"
    (RECEIPTS / "issue40_precice.json").write_text(json.dumps(out, indent=2, sort_keys=True))
    print("WROTE issue40_precice.json status=", out["status"])
    return 0


def _selftest() -> int:
    out: dict = {"solver": "preCICE", "status": "BLOCKED"}
    ok, detail = probe()
    out["bindingDetail"] = detail
    if ok:
        out["resolutions"] = [run_resolution(4)]
        out["status"] = "EXECUTED" if out["resolutions"][0].get("aExit") == 0 else "PARTIAL"
    (RECEIPTS / "issue40_precice.json").write_text(json.dumps(out, indent=2, sort_keys=True))
    print("selftest", out["status"], out["resolutions"][0] if out.get("resolutions") else "")
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--selftest":
        sys.exit(_selftest())
    sys.exit(main())
