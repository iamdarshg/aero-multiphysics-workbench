#!/usr/bin/env python3
"""Bounded native Elmer thermal benchmarks (SOLVER-CORR 03).

Reference problems with closed-form answers:
  1. steady 1-D conduction, Dirichlet both ends -> linear profile;
  2. prescribed heat flux (Neumann) -> linear profile with analytic end value;
  3. transient uniform volumetric heating with insulated boundaries ->
     T(t) = q*t/(rho*cp) (energy accumulation);
and a 3-mesh independence check on the steady QoI.

All numbers are parsed from the real Elmer VTU result; failures are BLOCKED.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

WORK = Path(os.environ.get("ELMER_WORK", "/tmp/elmer"))
RECEIPTS = Path(os.environ.get("RECEIPTS", "/var/log/proofs/receipts"))
RECEIPTS.mkdir(parents=True, exist_ok=True)


def sh(cmd: str, cwd: Path, timeout: int = 600) -> tuple[int, str]:
    try:
        done = subprocess.run(["bash", "-lc", cmd], cwd=str(cwd), capture_output=True,
                              text=True, timeout=timeout)
        return done.returncode, (done.stdout or "") + (done.stderr or "")
    except subprocess.TimeoutExpired as exc:
        return 124, f"TIMEOUT {timeout}s: {exc}"


def elmer_version() -> str:
    rc, out = sh("ElmerSolver --version 2>&1 | head -1; ElmerSolver 2>&1 | head -3", WORK)
    return out.strip().replace("\n", " | ")[:200]


def write_geo(path: Path, L: float, H: float, lc: float) -> None:
    nx = max(2, int(round(L / lc)))
    ny = max(2, int(round(H / lc)))
    path.write_text(f"""
SetFactory("OpenCASCADE");
lc = {lc};
Point(1) = {{0,0,0,lc}}; Point(2) = {{{L},0,0,lc}};
Point(3) = {{{L},{H},0,lc}}; Point(4) = {{0,{H},0,lc}};
Line(1) = {{1,2}}; Line(2) = {{2,3}}; Line(3) = {{3,4}}; Line(4) = {{4,1}};
Curve Loop(1) = {{1,2,3,4}};
Plane Surface(1) = {{1}};
Transfinite Curve {{1,3}} = {nx}+1;
Transfinite Curve {{2,4}} = {ny}+1;
Transfinite Surface {{1}};
Recombine Surface {{1}};
Physical Line("right") = {{2}};
Physical Line("left") = {{4}};
Physical Line("bottom") = {{1}};
Physical Line("top") = {{3}};
Physical Surface("domain") = {{1}};
Mesh.MshFileVersion = 2.2;
""")


def read_names(meshdir: Path) -> dict[str, int]:
    names: dict[str, int] = {}
    f = meshdir / "mesh.names"
    if f.is_file():
        for line in f.read_text(errors="replace").splitlines():
            m = re.match(r"\s*\$?\s*(\w+)\s*=\s*(\d+)", line)
            if m:
                names[m.group(1).lower()] = int(m.group(2))
    return names


def parse_temperature(vtu: Path) -> dict:
    text = vtu.read_text(errors="replace")
    pts = []
    # Elmer's Points DataArray is unnamed; match the <Points> block directly.
    m = re.search(r"<Points>\s*<DataArray[^>]*>(.*?)</DataArray>", text, re.S)
    if m:
        nums = [float(x) for x in re.findall(r"[-+0-9.eE]+", m.group(1))]
        pts = [(nums[i], nums[i + 1], nums[i + 2]) for i in range(0, len(nums) - 2, 3)]
    temp = None
    for m in re.finditer(r'<DataArray[^>]*Name="[Tt]emperature"[^>]*>(.*?)</DataArray>',
                         text, re.S):
        nums = [float(x) for x in re.findall(r"[-+0-9.eE]+", m.group(1))]
        if nums:
            temp = nums
            break
    if not temp or not pts:
        return {}
    n = min(len(pts), len(temp))
    tvals = {i: temp[i] for i in range(n)}
    tmax = max(tvals.values())
    tmin = min(tvals.values())
    # nearest node to x = L/2 (and mid-height) for the steady profile QoI
    xmid = (max(p[0] for p in pts) + min(p[0] for p in pts)) / 2.0
    ymid = (max(p[1] for p in pts) + min(p[1] for p in pts)) / 2.0
    best = min(range(n), key=lambda i: (pts[i][0] - xmid) ** 2 + (pts[i][1] - ymid) ** 2)
    # nearest node to left boundary x=0
    left = min(range(n), key=lambda i: (pts[i][0] - min(p[0] for p in pts)) ** 2)
    return {
        "tmax": tmax, "tmin": tmin,
        "tMid": temp[best], "tMidAt": pts[best][:2],
        "tLeft": temp[left], "nNodes": n,
    }


def run_case(tag: str, L: float, H: float, lc: float, sif: str, want_vtu: bool = True) -> dict:
    ndir = WORK / tag
    shutil.rmtree(ndir, ignore_errors=True)
    ndir.mkdir(parents=True, exist_ok=True)
    write_geo(ndir / "geom.geo", L, H, lc)
    rc_g, log_g = sh("gmsh -2 geom.geo -o geom.msh > gmsh.log 2>&1", ndir, 240)
    meshdir = ndir / "mesh"
    rc_e, log_e = sh(f"ElmerGrid 14 2 geom.msh -out mesh > elmergrid.log 2>&1",
                     ndir, 240)
    names = read_names(meshdir)
    rendered = sif
    for name in ("left", "right", "top", "bottom", "domain"):
        rendered = rendered.replace(f"@@{name}@@", str(names.get(name, 0)))
    (ndir / "case.sif").write_text(rendered)
    rc_s, log_s = sh("ElmerSolver case.sif > elmersolver.log 2>&1", ndir, 600)
    data = {}
    # Elmer's ResultOutputSolver writes into the mesh directory as case_tNNNN.vtu.
    vtus = sorted((ndir / "mesh").glob("case_t*.vtu"),
                  key=lambda p: int(re.sub(r"\D", "", p.stem) or 0))
    if rc_s == 0 and vtus:
        data = parse_temperature(vtus[-1])
    return {
        "tag": tag, "lc": lc, "gmshExit": rc_g, "elmerGridExit": rc_e,
        "solverExit": rc_s, "names": names, "data": data,
        "solverVersion": "present" if "ElmerSolver" in log_s or rc_s == 0 else "unknown",
    }


BASE = """
Header
  CHECK KEYWORDS Warn
  Mesh DB "." "mesh"
  Include Path ""
  Results Directory ""
End

Simulation
  Max Output Level = 4
  Coordinate System = Cartesian
  Coordinate Mapping(3) = 1 2 3
  Simulation Type = {simtype}
  Steady State Max Iterations = 1
  {timestep}
  Output Intervals = 1
  Solver Input File = case.sif
End

Constants
End

Body 1
  Target Bodies(1) = @@domain@@
  Name = "Body 1"
  Equation = 1
  Material = 1
  {bodyforce_ref}
  {initial_ref}
End

Solver 1
  Equation = Heat Equation
  Procedure = "HeatSolve" "HeatSolver"
  Variable = Temperature
  Exec Solver = Always
  Steady State Convergence Tolerance = 1.0e-9
  Linear System Solver = Direct
  Linear System Direct Method = Banded
End

Solver 2
  Equation = Result Output
  Procedure = "ResultOutputSolve" "ResultOutputSolver"
  Output File Name = case
  Output Format = vtu
  Exec Solver = Always
  Binary Output = False
End

Material 1
  Heat Conductivity = 1.0
  Density = 1.0
  Heat Capacity = 1.0
End

Equation 1
  Active Solvers(1) = 1
End

{bc}

{bodyforce}
{initial}
"""


def steady_sif(bc: str) -> str:
    return BASE.format(
        simtype="Steady State", timestep="", bodyforce_ref="", initial_ref="",
        bc=bc, bodyforce="", initial="",
    )


def dirichlet_sif() -> str:
    bc = ('Boundary Condition 1\n  Target Boundaries(1) = @@left@@\n  Name = "left"\n'
          '  Temperature = 100.0\nEnd\n\n'
          'Boundary Condition 2\n  Target Boundaries(1) = @@right@@\n  Name = "right"\n'
          '  Temperature = 0.0\nEnd\n')
    return steady_sif(bc)


def flux_sif() -> str:
    bc = ('Boundary Condition 1\n  Target Boundaries(1) = @@right@@\n  Name = "right"\n'
          '  Temperature = 0.0\nEnd\n\n'
          'Boundary Condition 2\n  Target Boundaries(1) = @@left@@\n  Name = "left"\n'
          '  Heat Flux = 10.0\nEnd\n')
    return steady_sif(bc)


def transient_sif() -> str:
    return BASE.format(
        simtype="Transient",
        timestep="Timestep Sizes = 0.01\n  Timestep Intervals = 10",
        bodyforce_ref="Body Force = 1",
        initial_ref="Initial Condition = 1",
        bc="",
        bodyforce='Body Force 1\n  Heat Source = 10.0\nEnd',
        initial='Initial Condition 1\n  Temperature = 0.0\nEnd',
    )


def bench_steady() -> dict:
    out: dict = {"case": "steady-1d-dirichlet", "status": "BLOCKED", "levels": []}
    try:
        for lc in (0.1, 0.05, 0.025):
            out["levels"].append(run_case(f"steady_{lc}", 1.0, 0.1, lc, dirichlet_sif()))
    except Exception as exc:  # noqa: BLE001
        out["reason"] = f"{type(exc).__name__}:{exc}"
        return out
    if not all(lv["solverExit"] == 0 for lv in out["levels"]):
        out["status"] = "FAILED"
        out["reason"] = "ElmerSolver non-zero exit"
        return out
    fine = out["levels"][-1]["data"]
    out["analyticTmid"] = 50.0
    if fine:
        out["relErrorTmid"] = abs(fine["tMid"] - 50.0) / 50.0
        out["tmax"] = fine["tmax"]
        out["tmin"] = fine["tmin"]
    mids = [lv["data"].get("tMid") for lv in out["levels"]]
    if all(v is not None for v in mids):
        out["tMidRelDeltas"] = [
            abs(mids[i + 1] - mids[i]) / max(abs(mids[i + 1]), 1e-12)
            for i in range(len(mids) - 1)
        ]
    out["status"] = "EXECUTED"
    return out


def bench_flux() -> dict:
    out: dict = {"case": "steady-1d-prescribed-flux", "status": "BLOCKED"}
    try:
        lv = run_case("flux", 1.0, 0.1, 0.02, flux_sif())
    except Exception as exc:  # noqa: BLE001
        out["reason"] = f"{type(exc).__name__}:{exc}"
        return out
    out["level"] = lv
    if lv["solverExit"] != 0:
        out["status"] = "FAILED"
        out["reason"] = "ElmerSolver non-zero exit"
        return out
    data = lv["data"]
    out["analyticTleft"] = 10.0
    if data:
        out["tLeft"] = data["tLeft"]
        out["relErrorTleft"] = abs(data["tLeft"] - 10.0) / 10.0
    out["status"] = "EXECUTED"
    return out


def bench_transient() -> dict:
    out: dict = {"case": "transient-uniform-heating-energy-accumulation", "status": "BLOCKED"}
    try:
        lv = run_case("transient", 1.0, 0.1, 0.02, transient_sif())
    except Exception as exc:  # noqa: BLE001
        out["reason"] = f"{type(exc).__name__}:{exc}"
        return out
    out["level"] = lv
    if lv["solverExit"] != 0:
        out["status"] = "FAILED"
        out["reason"] = "ElmerSolver non-zero exit"
        return out
    data = lv["data"]
    # q=10, rho=1, cp=1, t=0.1  ->  T = 1.0 uniformly
    out["analyticTfinal"] = 1.0
    if data:
        out["tmax"] = data["tmax"]
        out["tmin"] = data["tmin"]
        out["tMid"] = data["tMid"]
        out["relErrorTfinal"] = abs(data["tMid"] - 1.0) / 1.0
    out["status"] = "EXECUTED"
    return out


def main() -> int:
    WORK.mkdir(parents=True, exist_ok=True)
    out = {
        "solver": "Elmer",
        "version": elmer_version(),
        "benchmarks": {
            "steadyDirichlet": bench_steady(),
            "prescribedFlux": bench_flux(),
            "transient": bench_transient(),
        },
    }
    (RECEIPTS / "issue39_elmer.json").write_text(json.dumps(out, indent=2, sort_keys=True))
    print("WROTE issue39_elmer.json", json.dumps(
        {k: v["status"] for k, v in out["benchmarks"].items()}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
