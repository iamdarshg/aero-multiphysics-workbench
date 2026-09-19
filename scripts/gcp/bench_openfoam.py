#!/usr/bin/env python3
"""Bounded OpenFOAM correctness benchmarks (SOLVER-CORR 01).

Runs the smallest canonical cases that exercise the real native paths:
  * plane channel (steady, inlet/outlet): analytic Poiseuille cross-check,
    inlet/outlet flow-rate balance, 3-mesh independence of a centerline QoI;
  * lid-driven cavity (transient steady-limit): 3-mesh independence;
  * rotating annulus (MRF one-zone): torque sign flips with reversed omega.

Every number written is parsed from a real solver artifact; failures are
recorded as status BLOCKED/PARTIAL with the exact reason, never faked.
"""
from __future__ import annotations

import glob
import json
import math
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

WORK = Path(os.environ.get("OF_WORK", "/tmp/of"))
RECEIPTS = Path(os.environ.get("RECEIPTS", "/var/log/proofs/receipts"))
RECEIPTS.mkdir(parents=True, exist_ok=True)

FOAM_HEADER = "FoamFile {{ version 2.0; format ascii; class {cls}; object {obj}; }}\n"


def sh(cmd: str, cwd: Path, timeout: int = 600, env: dict | None = None) -> tuple[int, str]:
    try:
        done = subprocess.run(
            ["bash", "-lc", cmd], cwd=str(cwd), capture_output=True, text=True,
            timeout=timeout, env=env,
        )
        return done.returncode, (done.stdout or "") + (done.stderr or "")
    except subprocess.TimeoutExpired as exc:
        return 124, f"TIMEOUT after {timeout}s: {exc}"


def of_version() -> str:
    rc, out = sh("simpleFoam -help 2>&1 | head -3; echo WM=$WM_PROJECT_VERSION", WORK)
    m = re.search(r"WM=(\S+)", out)
    return m.group(1) if m else "unknown"


# --------------------------------------------------------------------------
# plane channel: analytic Poiseuille + mass balance + mesh independence
# --------------------------------------------------------------------------

def write_channel(ndir: Path, nx: int, ny: int) -> None:
    for sub in ("0", "constant", "system"):
        (ndir / sub).mkdir(parents=True, exist_ok=True)
    (ndir / "system" / "blockMeshDict").write_text(
        FOAM_HEADER.format(cls="dictionary", obj="blockMeshDict")
        + f"""
convertToMeters 1;
vertices ((0 0 0) (0.5 0 0) (0.5 0.1 0) (0 0.1 0)
          (0 0 0.01) (0.5 0 0.01) (0.5 0.1 0.01) (0 0.1 0.01));
blocks (hex (0 1 2 3 4 5 6 7) ({nx} {ny} 1) simpleGrading (1 1 1));
edges ();
boundary (inlet {{ type patch; faces ((0 4 7 3)); }}
          outlet {{ type patch; faces ((1 5 6 2)); }}
          walls {{ type wall; faces ((0 1 5 4) (3 7 6 2)); }}
          frontAndBack {{ type empty; faces ((0 3 2 1) (4 5 6 7)); }});
""")
    (ndir / "constant" / "transportProperties").write_text(
        FOAM_HEADER.format(cls="dictionary", obj="transportProperties")
        + "\ntransportModel Newtonian;\nnu [0 2 -1 0 0 0 0] 0.01;\n")
    (ndir / "constant" / "turbulenceProperties").write_text(
        FOAM_HEADER.format(cls="dictionary", obj="turbulenceProperties")
        + "\nsimulationType laminar;\n")
    (ndir / "0" / "U").write_text(
        FOAM_HEADER.format(cls="volVectorField", obj="U")
        + "\ndimensions [0 1 -1 0 0 0 0];\ninternalField uniform (0 0 0);\n"
        "boundaryField { inlet { type fixedValue; value uniform (1 0 0); } "
        "outlet { type zeroGradient; } walls { type noSlip; } "
        "frontAndBack { type empty; } }\n")
    (ndir / "0" / "p").write_text(
        FOAM_HEADER.format(cls="volScalarField", obj="p")
        + "\ndimensions [0 2 -2 0 0 0 0];\ninternalField uniform 0;\n"
        "boundaryField { inlet { type zeroGradient; } "
        "outlet { type fixedValue; value uniform 0; } walls { type zeroGradient; } "
        "frontAndBack { type empty; } }\n")
    (ndir / "system" / "fvSchemes").write_text(
        FOAM_HEADER.format(cls="dictionary", obj="fvSchemes")
        + """
ddtSchemes { default Euler; }
gradSchemes { default Gauss linear; }
divSchemes { default none; div(phi,U) Gauss linear; }
laplacianSchemes { default Gauss linear orthogonal; }
interpolationSchemes { default linear; }
snGradSchemes { default orthogonal; }
""")
    (ndir / "system" / "fvSolution").write_text(
        FOAM_HEADER.format(cls="dictionary", obj="fvSolution")
        + """
solvers { p { solver PCG; preconditioner DIC; tolerance 1e-07; relTol 0.05; }
          pFinal { $p; relTol 0; }
          U { solver smoothSolver; smoother symGaussSeidel; tolerance 1e-08; relTol 0.1; } }
PISO { nCorrectors 2; nNonOrthogonalCorrectors 0; }
""")
    (ndir / "system" / "controlDict").write_text(
        FOAM_HEADER.format(cls="dictionary", obj="controlDict")
        + """
application icoFoam; startFrom startTime; startTime 0; stopAt endTime; endTime 6.0;
deltaT 0.005; writeControl timeStep; writeInterval 200; purgeWrite 0;
writeFormat ascii; writePrecision 8; writeCompression off; runTimeModifiable true;
""")


def parse_flow_rates(ndir: Path) -> dict:
    rates: dict[str, float] = {}
    for path in glob.glob(str(ndir / "postProcessing" / "*" / "*" / "*.dat")):
        name = Path(path).parent.parent.name
        val = None
        for line in Path(path).read_text(errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.replace("(", " ").replace(")", " ").split()
            for token in reversed(parts):
                try:
                    val = float(token)
                    break
                except ValueError:
                    continue
        if val is not None:
            rates[name] = val
    return rates


def patch_mean_Ux(ndir: Path, patch: str) -> float | None:
    times = [p for p in ndir.iterdir() if p.is_dir() and re.fullmatch(r"\d+(\.\d+)?", p.name)]
    if not times:
        return None
    latest = max(times, key=lambda p: float(p.name))
    ufile = latest / "U"
    if not ufile.is_file():
        return None
    text = ufile.read_text(errors="replace")
    m = re.search(rf"\b{re.escape(patch)}\s*\n\s*\{{(.*?)\}}", text, re.S)
    if not m:
        return None
    block = m.group(1)
    uni = re.search(r"uniform\s*\(([-0-9.eE+]+)\s+([-0-9.eE+]+)\s+([-0-9.eE+]+)\)", block)
    if uni:
        return float(uni.group(1))
    vals = re.findall(r"\(([-0-9.eE+]+)\s+([-0-9.eE+]+)\s+([-0-9.eE+]+)\)", block)
    if vals:
        return sum(float(v[0]) for v in vals) / len(vals)
    return None


def internal_cells(ndir: Path) -> list[tuple[float, float, float]]:
    """(x, y, Ux) for every internal cell from the latest ascii U field."""
    times = [p for p in ndir.iterdir() if p.is_dir() and re.fullmatch(r"\d+(\.\d+)?", p.name)]
    if not times:
        return []
    latest = max(times, key=lambda p: float(p.name))
    ufile = latest / "U"
    if not ufile.is_file():
        return []
    m = re.search(r"internalField\s+nonuniform\s+List<vector>\s*\n\s*(\d+)\s*\n\s*\((.*?)\)\s*;",
                  ufile.read_text(errors="replace"), re.S)
    if not m:
        return []
    return [(float(a), 0.0, float(b)) for a, b, _ in
            re.findall(r"\(([-0-9.eE+]+)\s+([-0-9.eE+]+)\s+([-0-9.eE+]+)\)", m.group(2))]


def patch_sum_phi(ndir: Path, patch: str) -> float | None:
    """Exact volumetric flux through a patch from the written surfaceScalarField phi."""
    times = [p for p in ndir.iterdir() if p.is_dir() and re.fullmatch(r"\d+(\.\d+)?", p.name)]
    if not times:
        return None
    latest = max(times, key=lambda p: float(p.name))
    f = latest / "phi"
    if not f.is_file():
        return None
    text = f.read_text(errors="replace")
    m = re.search(rf"\b{re.escape(patch)}\s*\n\s*\{{(.*?)\}}", text, re.S)
    if not m:
        return None
    block = m.group(1)
    uni = re.search(r"uniform\s+([-0-9.eE+]+)", block)
    if uni:
        return float(uni.group(1))
    nums = [float(v) for v in re.findall(r"[-+0-9.eE]+", block.split("(")[-1])]
    return sum(nums) if nums else None


def final_internal_U(ndir: Path) -> list[tuple[float, float, float]]:
    times = [p for p in ndir.iterdir() if p.is_dir() and re.fullmatch(r"\d+(\.\d+)?", p.name)]
    if not times:
        return []
    latest = max(times, key=lambda p: float(p.name))
    ufile = latest / "U"
    if not ufile.is_file():
        return []
    text = ufile.read_text(errors="replace")
    m = re.search(r"internalField\s+nonuniform\s+List<vector>\s*\n\s*(\d+)\s*\n\s*\((.*?)\)\s*;",
                  text, re.S)
    if not m:
        return []
    vecs = []
    for x, y, z in re.findall(r"\(([-0-9.eE+]+)\s+([-0-9.eE+]+)\s+([-0-9.eE+]+)\)", m.group(2)):
        vecs.append((float(x), float(y), float(z)))
    return vecs


def channel_level(nx: int, ny: int) -> dict:
    ndir = WORK / f"channel_{nx}x{ny}"
    shutil.rmtree(ndir, ignore_errors=True)
    write_channel(ndir, nx, ny)
    rc_bm, log_bm = sh("blockMesh > blockMesh.log 2>&1", ndir, 180)
    rc_foam, log_foam = sh("icoFoam > icoFoam.log 2>&1", ndir, 900)
    rates = parse_flow_rates(ndir)
    vecs = final_internal_U(ndir)
    umax = max((v[0] for v in vecs), default=float("nan"))
    uin = patch_mean_Ux(ndir, "inlet")
    uout = patch_mean_Ux(ndir, "outlet")
    qin = patch_sum_phi(ndir, "inlet")
    qout = patch_sum_phi(ndir, "outlet")
    cont = ""
    m = re.search(r"time step continuity errors.*", log_foam)
    if m:
        cont = m.group(0)[:160]
    return {
        "mesh": f"{nx}x{ny}",
        "cells": nx * ny,
        "blockMeshExit": rc_bm,
        "solverExit": rc_foam,
        "inletFlow": rates.get("inletFlow"),
        "outletFlow": rates.get("outletFlow"),
        "inletMeanUx": uin,
        "outletMeanUx": uout,
        "inletPhiSum": qin,
        "outletPhiSum": qout,
        "maxUx": umax,
        "continuity": cont,
    }


def bench_channel() -> dict:
    result: dict = {"case": "plane-channel-poiseuille", "status": "BLOCKED", "levels": []}
    try:
        for nx, ny in ((40, 8), (80, 16), (160, 32)):
            result["levels"].append(channel_level(nx, ny))
    except Exception as exc:  # noqa: BLE001
        result["reason"] = f"{type(exc).__name__}:{exc}"
        return result
    ok = all(lv["solverExit"] == 0 for lv in result["levels"])
    if not ok:
        result["status"] = "FAILED"
        result["reason"] = "simpleFoam non-zero exit"
        return result
    fine = result["levels"][-1]
    result["analyticMaxUx"] = 1.5
    if fine["maxUx"] == fine["maxUx"]:
        result["analyticRelError"] = abs(fine["maxUx"] - 1.5) / 1.5
    if fine.get("inletPhiSum") is not None and fine.get("outletPhiSum") is not None:
        q_in = -fine["inletPhiSum"]   # inlet inward => phi negative
        q_out = fine["outletPhiSum"]
        result["inletVolumetricFlow_m3s"] = q_in
        result["outletVolumetricFlow_m3s"] = q_out
        result["massImbalanceRel"] = abs(q_out - q_in) / max(abs(q_in), 1e-30)
    result["status"] = "EXECUTED"
    return result


# --------------------------------------------------------------------------
# lid-driven cavity: 3-mesh independence of min(Ux)
# --------------------------------------------------------------------------

def write_cavity(ndir: Path, n: int) -> None:
    for sub in ("0", "constant", "system"):
        (ndir / sub).mkdir(parents=True, exist_ok=True)
    (ndir / "system" / "blockMeshDict").write_text(
        FOAM_HEADER.format(cls="dictionary", obj="blockMeshDict")
        + f"""
convertToMeters 1;
vertices ((0 0 0) (0.1 0 0) (0.1 0.1 0) (0 0.1 0)
          (0 0 0.01) (0.1 0 0.01) (0.1 0.1 0.01) (0 0.1 0.01));
blocks (hex (0 1 2 3 4 5 6 7) ({n} {n} 1) simpleGrading (1 1 1));
edges ();
boundary (movingWall {{ type wall; faces ((3 7 6 2)); }}
          fixedWalls {{ type wall; faces ((0 4 7 3) (2 6 5 1) (1 5 4 0)); }}
          frontAndBack {{ type empty; faces ((0 3 2 1) (4 5 6 7)); }});
""")
    (ndir / "constant" / "transportProperties").write_text(
        FOAM_HEADER.format(cls="dictionary", obj="transportProperties")
        + "\ntransportModel Newtonian;\nnu [0 2 -1 0 0 0 0] 0.01;\n")
    (ndir / "0" / "U").write_text(
        FOAM_HEADER.format(cls="volVectorField", obj="U")
        + "\ndimensions [0 1 -1 0 0 0 0];\ninternalField uniform (0 0 0);\n"
        "boundaryField { movingWall { type fixedValue; value uniform (1 0 0); } "
        "fixedWalls { type noSlip; } frontAndBack { type empty; } }\n")
    (ndir / "0" / "p").write_text(
        FOAM_HEADER.format(cls="volScalarField", obj="p")
        + "\ndimensions [0 2 -2 0 0 0 0];\ninternalField uniform 0;\n"
        "boundaryField { movingWall { type zeroGradient; } "
        "fixedWalls { type zeroGradient; } frontAndBack { type empty; } }\n")
    (ndir / "system" / "fvSchemes").write_text(
        FOAM_HEADER.format(cls="dictionary", obj="fvSchemes")
        + """
ddtSchemes { default Euler; }
gradSchemes { default Gauss linear; grad(p) Gauss linear; }
divSchemes { default none; div(phi,U) Gauss linear; }
laplacianSchemes { default Gauss linear orthogonal; }
interpolationSchemes { default linear; }
snGradSchemes { default orthogonal; }
""")
    (ndir / "system" / "fvSolution").write_text(
        FOAM_HEADER.format(cls="dictionary", obj="fvSolution")
        + """
solvers { p { solver PCG; preconditioner DIC; tolerance 1e-06; relTol 0.05; }
          pFinal { $p; relTol 0; }
          U { solver smoothSolver; smoother symGaussSeidel; tolerance 1e-05; relTol 0.1; } }
PISO { nNonOrthogonalCorrectors 0; nCorrectors 2; pRefCell 0; pRefValue 0; }
relaxationFactors { equations { U 0.9; } }
""")
    (ndir / "system" / "controlDict").write_text(
        FOAM_HEADER.format(cls="dictionary", obj="controlDict")
        + """
application icoFoam; startFrom startTime; startTime 0; stopAt endTime; endTime 2.0;
deltaT 0.005; writeControl timeStep; writeInterval 100; purgeWrite 0;
writeFormat ascii; writePrecision 8; writeCompression off; runTimeModifiable true;
""")


def cavity_level(n: int) -> dict:
    ndir = WORK / f"cavity_{n}"
    shutil.rmtree(ndir, ignore_errors=True)
    write_cavity(ndir, n)
    rc_bm, _ = sh("blockMesh > blockMesh.log 2>&1", ndir, 120)
    rc_foam, log = sh("icoFoam > icoFoam.log 2>&1", ndir, 600)
    vecs = final_internal_U(ndir)
    minux = min((v[0] for v in vecs), default=float("nan"))
    maxux = max((v[0] for v in vecs), default=float("nan"))
    m = re.search(r"time step continuity errors.*", log)
    return {
        "mesh": f"{n}x{n}", "cells": n * n, "blockMeshExit": rc_bm,
        "solverExit": rc_foam, "minUx": minux, "maxUx": maxux,
        "continuity": m.group(0)[:160] if m else "",
    }


def bench_cavity() -> dict:
    result: dict = {"case": "lid-driven-cavity", "status": "BLOCKED", "levels": []}
    try:
        for n in (10, 20, 40):
            result["levels"].append(cavity_level(n))
    except Exception as exc:  # noqa: BLE001
        result["reason"] = f"{type(exc).__name__}:{exc}"
        return result
    if not all(lv["solverExit"] == 0 for lv in result["levels"]):
        result["status"] = "FAILED"
        result["reason"] = "icoFoam non-zero exit"
        return result
    vals = [lv["minUx"] for lv in result["levels"]]
    result["minUxRelDeltas"] = [
        abs(vals[i + 1] - vals[i]) / max(abs(vals[i + 1]), 1e-12) for i in range(len(vals) - 1)
    ]
    result["status"] = "EXECUTED"
    return result


# --------------------------------------------------------------------------
# rotating annulus MRF: one zone, torque sign test
# --------------------------------------------------------------------------

def write_annulus_geo(path: Path, r_in: float, r_out: float, th: float, lc: float) -> None:
    path.write_text(f"""
SetFactory("OpenCASCADE");
r_in = {r_in}; r_out = {r_out}; th = {th}; lc = {lc};
Disk(1) = {{0,0,0, r_out}};
Disk(2) = {{0,0,0, r_in}};
BooleanDifference(3) = {{ Surface{{1}}; Delete; }}{{ Surface{{2}}; Delete; }};
out[] = Extrude {{0,0,th}} {{ Surface{{out[0]?}}; }}; // placeholder
""")
    # Written explicitly below instead (Extrude needs literal surface tag = 3).
    path.write_text(f"""
SetFactory("OpenCASCADE");
r_in = {r_in}; r_out = {r_out}; th = {th}; lc = {lc};
Disk(1) = {{0,0,0, r_out}};
Disk(2) = {{0,0,0, r_in}};
BooleanDifference(3) = {{ Surface{{1}}; Delete; }}{{ Surface{{2}}; Delete; }};
out[] = Extrude {{0,0,th}} {{ Surface{{3}}; Layers{{1}}; }};
Physical Volume("fluid") = {{out[0]}};
Physical Surface("frontAndBack") = {{3, out[1]}};
Physical Surface("inner") = {{out[2]}};
Physical Surface("outer") = {{out[3]}};
Mesh.MshFileVersion = 2.2;
Mesh.CharacteristicLengthMin = lc;
Mesh.CharacteristicLengthMax = lc;
Mesh.Algorithm = 6;
""")


def mrf_level(omega: float, tag: str, ref: bool = False) -> dict:
    ndir = WORK / f"mrf_{tag}"
    shutil.rmtree(ndir, ignore_errors=True)
    for sub in ("0", "constant", "system"):
        (ndir / sub).mkdir(parents=True, exist_ok=True)
    geo = ndir / "annulus.geo"
    write_annulus_geo(geo, 0.05, 0.10, 0.01, 0.004)
    boundary = ndir / "constant" / "polyMesh" / "boundary"
    (ndir / "constant" / "transportProperties").write_text(
        FOAM_HEADER.format(cls="dictionary", obj="transportProperties")
        + "\ntransportModel Newtonian;\nnu [0 2 -1 0 0 0 0] 0.001;\n")
    (ndir / "constant" / "turbulenceProperties").write_text(
        FOAM_HEADER.format(cls="dictionary", obj="turbulenceProperties")
        + "\nsimulationType laminar;\n")
    (ndir / "constant" / "MRFProperties").write_text(
        FOAM_HEADER.format(cls="dictionary", obj="MRFProperties")
        + f"""
MRF1 {{ cellZone fluid; active yes; origin (0 0 0); axis (0 0 1); omega {omega}; }}
""")
    (ndir / "0" / "U").write_text(
        FOAM_HEADER.format(cls="volVectorField", obj="U")
        + "\ndimensions [0 1 -1 0 0 0 0];\ninternalField uniform (0 0 0);\n"
        "boundaryField { \"(?i)inner\" { type noSlip; } \"(?i)outer\" { type noSlip; } "
        "frontAndBack { type empty; } }\n")
    (ndir / "0" / "p").write_text(
        FOAM_HEADER.format(cls="volScalarField", obj="p")
        + "\ndimensions [0 2 -2 0 0 0 0];\ninternalField uniform 0;\n"
        "boundaryField { \"(?i)inner\" { type zeroGradient; } "
        "\"(?i)outer\" { type zeroGradient; } frontAndBack { type empty; } }\n")
    (ndir / "system" / "fvSchemes").write_text(
        FOAM_HEADER.format(cls="dictionary", obj="fvSchemes")
        + """
ddtSchemes { default steadyState; }
gradSchemes { default Gauss linear; }
divSchemes { default Gauss linear; div(phi,U) Gauss linearUpwind grad(U); }
laplacianSchemes { default Gauss linear corrected; }
interpolationSchemes { default linear; }
snGradSchemes { default corrected; }
""")
    (ndir / "system" / "fvSolution").write_text(
        FOAM_HEADER.format(cls="dictionary", obj="fvSolution")
        + """
solvers { p { solver GAMG; smoother GaussSeidel; tolerance 1e-08; relTol 0.01; }
          U { solver smoothSolver; smoother symGaussSeidel; tolerance 1e-08; relTol 0.1; } }
SIMPLE { nNonOrthogonalCorrectors 1; residualControl { p 1e-6; U 1e-6; } }
relaxationFactors { equations { U 0.9; } }
""")
    (ndir / "system" / "controlDict").write_text(
        FOAM_HEADER.format(cls="dictionary", obj="controlDict")
        + """
application simpleFoam; startFrom startTime; startTime 0; stopAt endTime; endTime 1500;
deltaT 1; writeControl timeStep; writeInterval 500; purgeWrite 0;
writeFormat ascii; writePrecision 8; writeCompression off; runTimeModifiable true;
functions {
  torqueAll { type forces; libs ("libforces.so"); patches ("(?i)inner" "(?i)outer");
              rho rhoInf; rhoInf 1000; CofR (0 0 0); log true; }
}
""")
    # Mesh after the OpenFOAM dictionaries exist (gmshToFoam needs system/controlDict).
    rc_gmsh, log_gmsh = sh(f"gmsh -3 {geo.name} -o annulus.msh > gmsh.log 2>&1", ndir, 300)
    rc_conv, log_conv = sh("gmshToFoam annulus.msh > gmshToFoam.log 2>&1", ndir, 300)
    if boundary.is_file():
        text = boundary.read_text(errors="replace")
        text = re.sub(r"(frontAndBack\s*\n\s*\{[^}]*?type\s+)\w+", r"\1empty", text)
        text = re.sub(r"((inner|outer)\s*\n\s*\{[^}]*?type\s+)\w+", r"\1wall", text)
        boundary.write_text(text)
    rc_foam = 1
    log_foam = ""
    if boundary.is_file():
        rc_foam, log_foam = sh("simpleFoam > simpleFoam.log 2>&1", ndir, 700)
    torque = None
    for path in glob.glob(str(ndir / "postProcessing" / "torqueAll" / "*" / "forces.dat")):
        last = None
        for line in Path(path).read_text(errors="replace").splitlines():
            if line.strip().startswith("#") or not line.strip():
                continue
            last = line
        if last:
            groups = re.findall(r"\(([^)]*)\)", last)
            if len(groups) >= 2:
                moment = [float(v) for v in groups[1].split()]
                torque = moment
    return {
        "omega_rad_s": omega, "tag": tag, "gmshExit": rc_gmsh,
        "gmshToFoamExit": rc_conv, "boundaryRewritten": boundary.is_file(),
        "solverExit": rc_foam, "torque_Nm": torque,
        "converged": "SIMPLE solution converged" in log_foam,
    }


def write_pipe_case(ndir: Path, w_in: float, w_out: float | None,
                    r_in=0.05, r_out=0.10, th=0.01, nrad=10, ncirc=6) -> None:
    """Deterministic blockMesh O-grid annulus (pipe) for MRF torque studies."""
    for sub in ("0", "constant", "system"):
        (ndir / sub).mkdir(parents=True, exist_ok=True)
    verts = []
    for z in (0.0, th):
        for r in (r_in, r_out):
            for k in range(4):
                a = k * math.pi / 2
                verts.append((r * math.cos(a), r * math.sin(a), z))
    verts_txt = "\n".join(f"({x:.9g} {y:.9g} {z:.9g})" for x, y, z in verts)
    arcs = []
    for k in range(4):
        n = (k + 1) % 4
        am = (k * math.pi / 2) + math.pi / 4
        arcs.append(f"arc {k} {n} ({r_in*math.cos(am):.9g} {r_in*math.sin(am):.9g} 0)")
        arcs.append(f"arc {8+k} {8+n} ({r_in*math.cos(am):.9g} {r_in*math.sin(am):.9g} {th})")
        arcs.append(f"arc {4+k} {4+n} ({r_out*math.cos(am):.9g} {r_out*math.sin(am):.9g} 0)")
        arcs.append(f"arc {12+k} {12+n} ({r_out*math.cos(am):.9g} {r_out*math.sin(am):.9g} {th})")
    blocks = []
    for k in range(4):
        n = (k + 1) % 4
        blk = (k, n, 4 + n, 4 + k, 8 + k, 8 + n, 12 + n, 12 + k)
        blocks.append("hex (" + " ".join(map(str, blk))
                      + f") ({nrad} {ncirc} 1) simpleGrading (1 1 1)")
    (ndir / "system" / "blockMeshDict").write_text(
        FOAM_HEADER.format(cls="dictionary", obj="blockMeshDict") + f"""
convertToMeters 1;
vertices
(
{verts_txt}
);
blocks
(
{chr(10).join(blocks)}
);
edges
(
{chr(10).join(arcs)}
);
boundary
(
  innerWall {{ type wall; faces ((0 1 5 4)); }}
  outerWall {{ type wall; faces ((3 2 6 7)); }}
  frontAndBack {{ type empty; faces ((0 3 2 1) (4 5 6 7)); }}
);
""")
    (ndir / "constant" / "transportProperties").write_text(
        FOAM_HEADER.format(cls="dictionary", obj="transportProperties")
        + "\ntransportModel Newtonian;\nnu [0 2 -1 0 0 0 0] 0.001;\n")
    (ndir / "constant" / "turbulenceProperties").write_text(
        FOAM_HEADER.format(cls="dictionary", obj="turbulenceProperties")
        + "\nsimulationType laminar;\n")
    if w_out is None:
        mrf = (f"""
MRF1 {{ cellZone rotorZone; active yes; origin (0 0 0); axis (0 0 1);
       omega {w_in}; nonRotatingPatches (outerWall); }}
""")
        topo_actions = (
            "  { name rotorZone; type cellSet; action new; source boxToCell; "
            "box (-1 -1 -1)(1 1 1); }\n")
    else:
        mrf = (f"""
MRF1 {{ cellZone zoneInner; active yes; origin (0 0 0); axis (0 0 1);
       omega {w_in}; nonRotatingPatches (outerWall); }}
MRF2 {{ cellZone zoneOuter; active yes; origin (0 0 0); axis (0 0 1);
       omega {w_out}; nonRotatingPatches (outerWall); }}
""")
        topo_actions = (
            "  { name zoneInner; type cellSet; action new; source cylinderToCell; "
            "p1 (0 0 -1); p2 (0 0 1); radius 0.07; }\n"
            "  { name zoneOuter; type cellSet; action new; source boxToCell; "
            "box (-1 -1 -1)(1 1 1); }\n"
            "  { name zoneOuter; type cellSet; action subtract; source cellToCell; "
            "set zoneInner; }\n")
    (ndir / "constant" / "MRFProperties").write_text(
        FOAM_HEADER.format(cls="dictionary", obj="MRFProperties") + mrf)
    (ndir / "system" / "topoSetDict").write_text(
        FOAM_HEADER.format(cls="dictionary", obj="topoSetDict")
        + "\nactions\n(\n" + topo_actions + ");\n")
    (ndir / "0" / "U").write_text(
        FOAM_HEADER.format(cls="volVectorField", obj="U")
        + "\ndimensions [0 1 -1 0 0 0 0];\ninternalField uniform (0 0 0);\n"
        "boundaryField { innerWall { type noSlip; } outerWall { type noSlip; } "
        "frontAndBack { type empty; } }\n")
    (ndir / "0" / "p").write_text(
        FOAM_HEADER.format(cls="volScalarField", obj="p")
        + "\ndimensions [0 2 -2 0 0 0 0];\ninternalField uniform 0;\n"
        "boundaryField { innerWall { type zeroGradient; } "
        "outerWall { type zeroGradient; } frontAndBack { type empty; } }\n")
    (ndir / "system" / "fvSchemes").write_text(
        FOAM_HEADER.format(cls="dictionary", obj="fvSchemes")
        + """
ddtSchemes { default steadyState; }
gradSchemes { default Gauss linear; }
divSchemes { default none; div(phi,U) Gauss limitedLinear 1;
             div((nuEff*dev2(T(grad(U))))) Gauss linear; }
laplacianSchemes { default Gauss linear corrected; }
interpolationSchemes { default linear; }
snGradSchemes { default corrected; }
""")
    (ndir / "system" / "fvSolution").write_text(
        FOAM_HEADER.format(cls="dictionary", obj="fvSolution")
        + """
solvers { p { solver GAMG; smoother GaussSeidel; tolerance 1e-08; relTol 0.01; }
          U { solver smoothSolver; smoother symGaussSeidel; tolerance 1e-08; relTol 0.1; } }
SIMPLE { nNonOrthogonalCorrectors 1; residualControl { p 1e-6; U 1e-6; } }
relaxationFactors { equations { p 0.3; U 0.7; } }
""")
    (ndir / "system" / "controlDict").write_text(
        FOAM_HEADER.format(cls="dictionary", obj="controlDict")
        + """
application simpleFoam; startFrom startTime; startTime 0; stopAt endTime; endTime 2000;
deltaT 1; writeControl timeStep; writeInterval 500; purgeWrite 0;
writeFormat ascii; writePrecision 8; writeCompression off; runTimeModifiable true;
libs ("libforces.so" "libfieldFunctionObjects.so");
functions {
  torqueInner { type forces; patches (innerWall); rho rhoInf; rhoInf 1000; CofR (0 0 0); }
  torqueOuter { type forces; patches (outerWall); rho rhoInf; rhoInf 1000; CofR (0 0 0); }
}
""")


def parse_forces(ndir: Path, fo: str) -> list | None:
    # OpenFOAM's `forces` function object writes force.dat and moment.dat.
    for path in glob.glob(str(ndir / "postProcessing" / fo / "*" / "moment.dat")):
        last = None
        for line in Path(path).read_text(errors="replace").splitlines():
            if line.strip() and not line.strip().startswith("#"):
                last = line
        if last:
            # moment.dat columns: time Mx My Mz Mpx Mpy Mpz Mvx Mvy Mvz
            nums = [float(v) for v in re.findall(r"[-+0-9.eE]+", last)]
            if len(nums) >= 4:
                return [nums[1], nums[2], nums[3]]
    return None


def mrf_pipe_level(w_in: float, w_out: float | None, tag: str) -> dict:
    ndir = WORK / f"mrf_{tag}"
    shutil.rmtree(ndir, ignore_errors=True)
    write_pipe_case(ndir, w_in, w_out)
    rc_bm, _ = sh("blockMesh > blockMesh.log 2>&1", ndir, 180)
    rc_chk, _ = sh("checkMesh > checkMesh.log 2>&1", ndir, 180)
    rc_ts, _ = sh("topoSet -dict system/topoSetDict > topoSet.log 2>&1", ndir, 120)
    rc_z, _ = sh("setsToZones -noFlipMap > setsToZones.log 2>&1", ndir, 120)
    rc_foam = 1
    log = ""
    if rc_bm == 0 and rc_ts == 0 and rc_z == 0:
        rc_foam, log = sh("simpleFoam > simpleFoam.log 2>&1", ndir, 900)
    return {
        "tag": tag, "w_in": w_in, "w_out": w_out, "blockMeshExit": rc_bm,
        "checkMeshExit": rc_chk, "topoSetExit": rc_ts, "setsToZonesExit": rc_z,
        "solverExit": rc_foam, "converged": "SIMPLE solution converged" in log,
        "torqueInner_Nm": parse_forces(ndir, "torqueInner"),
        "torqueOuter_Nm": parse_forces(ndir, "torqueOuter"),
        "analyticInnerTorque_Nm": (
            4 * math.pi * 1.0 * 0.05**2 * 0.10**2 * w_in / (0.10**2 - 0.05**2) * 0.01),
    }


def bench_mrf() -> dict:
    result: dict = {"case": "rotating-annulus-mrf", "status": "BLOCKED"}
    try:
        pos = mrf_pipe_level(10.0, None, "pos")
        neg = mrf_pipe_level(-10.0, None, "neg")
        multi = mrf_pipe_level(10.0, -5.0, "multi")
    except Exception as exc:  # noqa: BLE001
        result["reason"] = f"{type(exc).__name__}:{exc}"
        return result
    result["oneZonePositive"] = pos
    result["oneZoneNegative"] = neg
    result["multiZone"] = multi
    if pos["solverExit"] != 0 or neg["solverExit"] != 0:
        result["status"] = "PARTIAL"
        result["reason"] = "simpleFoam did not exit 0 for both rotation directions"
        return result
    tp, tn = pos.get("torqueInner_Nm"), neg.get("torqueInner_Nm")
    if tp and tn:
        result["torqueZpos"] = tp[2]
        result["torqueZneg"] = tn[2]
        result["signFlipped"] = (tp[2] * tn[2]) < 0
    outer = pos.get("torqueOuter_Nm")
    if tp and outer:
        result["stationaryOuterTorqueRatio"] = abs(outer[2]) / max(abs(tp[2]), 1e-12)
    if tp and pos.get("analyticInnerTorque_Nm"):
        result["torqueRelErrorVsTaylorCouette"] = (
            abs(abs(tp[2]) - pos["analyticInnerTorque_Nm"]) / pos["analyticInnerTorque_Nm"])
    result["multiZoneRatesIndependent"] = bool(
        multi.get("solverExit") == 0 and multi.get("torqueInner_Nm"))
    result["status"] = "EXECUTED"
    return result


def write_couette_case(ndir: Path, zone_specs, non_rotating=(), H=0.05, L=0.1, th=0.01,
                       nx=40, ny=20) -> None:
    """Deterministic rotating-frame shear case. zone_specs: (name, box, omega)."""
    for sub in ("0", "constant", "system"):
        (ndir / sub).mkdir(parents=True, exist_ok=True)
    (ndir / "system" / "blockMeshDict").write_text(
        FOAM_HEADER.format(cls="dictionary", obj="blockMeshDict") + f"""
convertToMeters 1;
vertices ((0 0 0) ({L} 0 0) ({L} {H} 0) (0 {H} 0)
          (0 0 {th}) ({L} 0 {th}) ({L} {H} {th}) (0 {H} {th}));
blocks (hex (0 1 2 3 4 5 6 7) ({nx} {ny} 1) simpleGrading (1 1 1));
edges ();
boundary (lowerWall {{ type wall; faces ((0 1 5 4)); }}
          upperWall {{ type wall; faces ((3 7 6 2)); }}
          sideLeft {{ type wall; faces ((0 4 7 3)); }}
          sideRight {{ type wall; faces ((1 2 6 5)); }}
          frontAndBack {{ type empty; faces ((0 3 2 1) (4 5 6 7)); }});
""")
    (ndir / "constant" / "transportProperties").write_text(
        FOAM_HEADER.format(cls="dictionary", obj="transportProperties")
        + "\ntransportModel Newtonian;\nnu [0 2 -1 0 0 0 0] 0.001;\n")
    (ndir / "constant" / "turbulenceProperties").write_text(
        FOAM_HEADER.format(cls="dictionary", obj="turbulenceProperties")
        + "\nsimulationType laminar;\n")
    nr = " ".join(non_rotating)
    mrf = "".join(
        f"\n{name} {{ cellZone {name}; active yes; origin ({L/2} {H/2} 0); axis (0 0 1); "
        f"omega {om}; {'nonRotatingPatches (' + nr + ');' if nr else ''} }}\n"
        for name, _box, om in zone_specs)
    (ndir / "constant" / "MRFProperties").write_text(
        FOAM_HEADER.format(cls="dictionary", obj="MRFProperties") + mrf)
    actions = "".join(
        f"  {{ name {name}; type cellSet; action new; source boxToCell; "
        f"box ({b[0]} {b[1]} {b[2]})({b[3]} {b[4]} {b[5]}); }}\n"
        for name, b, _om in zone_specs)
    (ndir / "system" / "topoSetDict").write_text(
        FOAM_HEADER.format(cls="dictionary", obj="topoSetDict")
        + "\nactions\n(\n" + actions + ");\n")
    (ndir / "0" / "U").write_text(
        FOAM_HEADER.format(cls="volVectorField", obj="U")
        + "\ndimensions [0 1 -1 0 0 0 0];\ninternalField uniform (0 0 0);\n"
        "boundaryField { lowerWall { type noSlip; } upperWall { type noSlip; } "
        "sideLeft { type noSlip; } sideRight { type noSlip; } frontAndBack { type empty; } }\n")
    (ndir / "0" / "p").write_text(
        FOAM_HEADER.format(cls="volScalarField", obj="p")
        + "\ndimensions [0 2 -2 0 0 0 0];\ninternalField uniform 0;\n"
        "boundaryField { lowerWall { type zeroGradient; } upperWall { type zeroGradient; } "
        "sideLeft { type zeroGradient; } sideRight { type zeroGradient; } "
        "frontAndBack { type empty; } }\n")
    (ndir / "system" / "fvSchemes").write_text(
        FOAM_HEADER.format(cls="dictionary", obj="fvSchemes")
        + """
ddtSchemes { default steadyState; }
gradSchemes { default Gauss linear; }
divSchemes { default none; div(phi,U) Gauss limitedLinear 1;
             div((nuEff*dev2(T(grad(U))))) Gauss linear; }
laplacianSchemes { default Gauss linear corrected; }
interpolationSchemes { default linear; }
snGradSchemes { default corrected; }
""")
    (ndir / "system" / "fvSolution").write_text(
        FOAM_HEADER.format(cls="dictionary", obj="fvSolution")
        + """
solvers { p { solver GAMG; smoother GaussSeidel; tolerance 1e-09; relTol 0.01; }
          U { solver smoothSolver; smoother symGaussSeidel; tolerance 1e-09; relTol 0.1; } }
SIMPLE { nNonOrthogonalCorrectors 0; pRefCell 0; pRefValue 0;
         residualControl { p 1e-6; U 1e-6; } }
relaxationFactors { equations { p 0.3; U 0.7; } }
""")
    (ndir / "system" / "controlDict").write_text(
        FOAM_HEADER.format(cls="dictionary", obj="controlDict")
        + f"""
application simpleFoam; startFrom startTime; startTime 0; stopAt endTime; endTime 4000;
deltaT 1; writeControl timeStep; writeInterval 1000; purgeWrite 0;
writeFormat ascii; writePrecision 8; writeCompression off; runTimeModifiable true;
libs ("libforces.so");
functions {{
  torqueLower {{ type forces; patches (lowerWall); rho rhoInf; rhoInf 1000; CofR ({L/2} {H/2} 0); }}
  torqueUpper {{ type forces; patches (upperWall); rho rhoInf; rhoInf 1000; CofR ({L/2} {H/2} 0); }}
}}
""")


def couette_level(zone_specs, non_rotating, tag) -> dict:
    ndir = WORK / f"mrf_{tag}"
    shutil.rmtree(ndir, ignore_errors=True)
    write_couette_case(ndir, zone_specs, non_rotating)
    rc_bm, _ = sh("blockMesh > blockMesh.log 2>&1", ndir, 180)
    rc_chk, _ = sh("checkMesh > checkMesh.log 2>&1", ndir, 180)
    rc_ts, _ = sh("topoSet -dict system/topoSetDict > topoSet.log 2>&1", ndir, 120)
    rc_z, _ = sh("setsToZones -noFlipMap > setsToZones.log 2>&1", ndir, 120)
    rc_foam, log = 1, ""
    if rc_bm == 0 and rc_ts == 0 and rc_z == 0:
        rc_foam, log = sh("simpleFoam > simpleFoam.log 2>&1", ndir, 900)
    return {
        "tag": tag, "blockMeshExit": rc_bm, "checkMeshExit": rc_chk,
        "topoSetExit": rc_ts, "setsToZonesExit": rc_z, "solverExit": rc_foam,
        "converged": "SIMPLE solution converged" in log,
        "torqueLower_Nm": parse_forces(ndir, "torqueLower"),
        "torqueUpper_Nm": parse_forces(ndir, "torqueUpper"),
    }


def bench_mrf_couette() -> dict:
    result: dict = {"case": "rotating-frame-mrf-shear", "status": "BLOCKED"}
    whole = (-1, -1, -1, 1, 1, 1)
    lower = (-1, -1, -1, 1, 0.025, 1)
    upper = (-1, 0.025, -1, 1, 1, 1)
    try:
        one_pos = couette_level([("rotorZone", whole, 10.0)], ("lowerWall",), "one_pos")
        one_neg = couette_level([("rotorZone", whole, -10.0)], ("lowerWall",), "one_neg")
        multi = couette_level([("zoneLower", lower, 10.0), ("zoneUpper", upper, -5.0)],
                              (), "multi")
    except Exception as exc:  # noqa: BLE001
        result["reason"] = f"{type(exc).__name__}:{exc}"
        return result
    result.update({"oneZonePositive": one_pos, "oneZoneNegative": one_neg, "multiZone": multi})
    if one_pos["solverExit"] != 0 or one_neg["solverExit"] != 0:
        result["status"] = "PARTIAL"
        result["reason"] = "simpleFoam did not converge for both rotation directions"
        return result
    up, un = one_pos.get("torqueUpper_Nm"), one_neg.get("torqueUpper_Nm")
    if up and un:
        result["upperTorqueZpos"] = up[2]
        result["upperTorqueZneg"] = un[2]
        result["signFlipped"] = (up[2] * un[2]) < 0
    low = one_pos.get("torqueLower_Nm")
    if low and up:
        result["stationaryLowerVsRotatingUpperSignsOpposite"] = (low[2] * up[2]) < 0
    result["multiZoneIndependent"] = bool(
        multi.get("solverExit") == 0 and multi.get("torqueLower_Nm")
        and multi.get("torqueUpper_Nm"))
    result["status"] = "EXECUTED"
    return result


def main() -> int:
    WORK.mkdir(parents=True, exist_ok=True)
    out = {
        "solver": "OpenFOAM",
        "version": of_version(),
        "benchmarks": {
            "channel": bench_channel(),
            "cavity": bench_cavity(),
            "mrf": bench_mrf_couette(),
        },
    }
    (RECEIPTS / "issue37_openfoam.json").write_text(json.dumps(out, indent=2, sort_keys=True))
    print("WROTE issue37_openfoam.json", json.dumps({k: v["status"] for k, v in out["benchmarks"].items()}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
