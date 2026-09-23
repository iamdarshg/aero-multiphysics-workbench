#!/usr/bin/env python3
"""Bounded native ROSS rotor-dynamic benchmarks (SOLVER-CORR 02).

Executes the repo's governed native run script
(``solvers/participants/run_scripts/run_ross.py``) on canonical cases and
compares the first whirl/critical speed against closed-form expectations:

  * Jeffcott rotor: central disk on a simply-supported shaft,
    k = 48*E*I/L^3, omega = sqrt(k/m) -> rpm;
  * flexible shaft with soft bearings: first critical must drop vs rigid;
  * unbalance response: peak speed near the first critical;
  * short/stiff shaft: high critical speed.

Numbers are parsed from real ROSS ``result.json``; failures are BLOCKED.
"""

from __future__ import annotations

import json
import math
import os
import subprocess
import sys
from pathlib import Path

WORK = Path(os.environ.get("ROSS_WORK", "/tmp/ross"))
RECEIPTS = Path(os.environ.get("RECEIPTS", "/var/log/proofs/receipts"))
RECEIPTS.mkdir(parents=True, exist_ok=True)
REPO = Path(os.environ.get("REPO_ROOT", "/opt/repo"))
RUN_SCRIPT = REPO / "solvers" / "participants" / "run_scripts" / "run_ross.py"
PY = os.environ.get("PY", "/opt/py312/bin/python")

STEEL = {
    "name": "steel",
    "youngs_modulus_pa": 2.1e11,
    "shear_modulus_pa": 8.1e10,
    "density_kg_m3": 7850.0,
}

JEFFCOTT_REFERENCE_REL_TOL = 0.25
MODAL_CAMPBELL_REL_TOL = 0.05
FORCED_PEAK_REL_TOL = 0.20
DISCRETIZATION_REL_TOL = 0.05


def gov_case(analysis: str, model: dict, speed_rpm: float, max_speed_rpm: float, name: str) -> dict:
    ndir = WORK / name
    ndir.mkdir(parents=True, exist_ok=True)
    case = {
        "analysis": analysis,
        "model": model,
        "speed_rpm": speed_rpm,
        "max_speed_rpm": max_speed_rpm,
        "forcings": [],
        "forcing_warning_margin_hz": 5.0,
        "forcing_critical_margin_hz": 2.0,
        "library": "ross-rotordynamics",
        "min_version": "2.0.0",
    }
    (ndir / "case.json").write_text(json.dumps(case, indent=2, sort_keys=True))
    try:
        done = subprocess.run(
            [PY, str(RUN_SCRIPT)],
            cwd=str(ndir),
            capture_output=True,
            text=True,
            timeout=600,
            env={**os.environ, "NUMBA_DISABLE_JIT": "1"},
        )
    except subprocess.TimeoutExpired as exc:
        return {"name": name, "status": "BLOCKED", "reason": f"timeout:{exc}"}
    result = {
        "name": name,
        "analysis": analysis,
        "exit": done.returncode,
        "stdout": done.stdout.strip()[:200],
        "stderr": done.stderr.strip()[-300:],
    }
    rj = ndir / "result.json"
    if rj.is_file():
        result.update(json.loads(rj.read_text()))
    return result


def jeffcott_model(
    nseg: int = 4,
    length_m: float = 0.4,
    dia_m: float = 0.02,
    disk_mass_scale: float = 1.0,
    bearing_k: float = 1e9,
) -> dict:
    seg = [
        {"length_m": length_m / nseg, "outer_diameter_m": dia_m, "inner_diameter_m": 0.0}
        for _ in range(nseg)
    ]
    rho = STEEL["density_kg_m3"]
    shaft_mass = rho * math.pi * (dia_m / 2) ** 2 * length_m
    disk_mass = shaft_mass * disk_mass_scale
    # DiskElement.from_geometry uses i_d/o_d/width; pick width so mass matches scale.
    o_d = 0.15
    i_d = 0.02
    disk_area = math.pi * ((o_d / 2) ** 2 - (i_d / 2) ** 2)
    width = disk_mass / (rho * disk_area)
    return {
        "material": STEEL,
        "segments": seg,
        "disks": [
            {
                "position": nseg // 2,
                "width_m": width,
                "inner_diameter_m": i_d,
                "outer_diameter_m": o_d,
            }
        ],
        "bearings": [
            {"node": 0, "kxx": bearing_k, "cxx": 0.0},
            {"node": nseg, "kxx": bearing_k, "cxx": 0.0},
        ],
        "gyroscopic": True,
        "shear_effects": True,
        "rotary_inertia": True,
        "unbalance": {"node": nseg // 2, "magnitude_kg_m": 1e-4, "phase_deg": 0.0},
        "_declaredDiskMassKg": disk_mass,
    }


def jeffcott_analytic_rpm(model: dict) -> float:
    L = sum(s["length_m"] for s in model["segments"])
    d = model["segments"][0]["outer_diameter_m"]
    I = math.pi * d**4 / 64.0  # noqa: E741
    k = 48.0 * STEEL["youngs_modulus_pa"] * I / L**3
    m = model["_declaredDiskMassKg"]
    omega = math.sqrt(k / m)
    return omega * 60.0 / (2.0 * math.pi)


def bench_ross() -> dict:
    out: dict = {
        "solver": "ROSS",
        "status": "BLOCKED",
        "verificationPassed": False,
        "checks": {},
        "cases": [],
    }
    if not RUN_SCRIPT.is_file():
        out["reason"] = f"governed run script missing: {RUN_SCRIPT}"
        return out
    try:
        m_rigid = jeffcott_model(bearing_k=1e9)
        m_refined = jeffcott_model(nseg=8, bearing_k=1e9)
        m_soft = jeffcott_model(bearing_k=1e5)
        m_short = jeffcott_model(length_m=0.15, dia_m=0.03, bearing_k=1e9)
        analytic_rigid = jeffcott_analytic_rpm(m_rigid)

        camp = gov_case("campbell", m_rigid, 3000.0, 60000.0, "jeffcott_campbell")
        refined = gov_case(
            "campbell", m_refined, 3000.0, 60000.0, "jeffcott_refined_campbell"
        )
        crit_rigid = camp.get("critical_speeds_rpm") or []
        forced_target_rpm = float(crit_rigid[0]) if crit_rigid else 3000.0
        soft = gov_case("campbell", m_soft, 3000.0, 60000.0, "soft_bearing_campbell")
        modal = gov_case("modal", m_rigid, 3000.0, 60000.0, "jeffcott_modal")
        short = gov_case("campbell", m_short, 3000.0, 120000.0, "short_stiff_campbell")
        forced = gov_case(
            "forced",
            m_rigid,
            forced_target_rpm,
            max(60000.0, forced_target_rpm * 1.5),
            "jeffcott_forced",
        )

        cases = {
            "jeffcottCampbell": camp,
            "jeffcottRefinedCampbell": refined,
            "softBearingCampbell": soft,
            "jeffcottModal": modal,
            "shortStiffCampbell": short,
            "jeffcottForced": forced,
        }
        out["cases"] = cases
        out["analyticFirstCriticalRpm"] = analytic_rigid
        crit_soft = soft.get("critical_speeds_rpm") or []
        crit_short = short.get("critical_speeds_rpm") or []
        crit_refined = refined.get("critical_speeds_rpm") or []
        if crit_rigid:
            out["nativeFirstCriticalRpm"] = crit_rigid[0]
            out["criticalRelError"] = abs(crit_rigid[0] - analytic_rigid) / analytic_rigid
        if crit_rigid and crit_soft:
            out["softBearingDropsCritical"] = crit_soft[0] < crit_rigid[0]
        if crit_rigid and crit_short:
            out["shortStiffCriticalRpm"] = crit_short[0]
        if crit_rigid and crit_refined:
            out["discretizationRelDelta"] = abs(
                float(crit_refined[0]) - float(crit_rigid[0])
            ) / max(abs(float(crit_refined[0])), 1e-9)
            out["discretizationIndependencePassed"] = (
                out["discretizationRelDelta"] <= DISCRETIZATION_REL_TOL
            )
        if modal.get("first_whirl_hz"):
            out["modalFirstWhirlRpm"] = modal["first_whirl_hz"] * 60.0
            out["modalVsCampbellRelDelta"] = abs(
                modal["first_whirl_hz"] * 60.0 - (crit_rigid[0] if crit_rigid else 0)
            ) / max(modal["first_whirl_hz"] * 60.0, 1e-9)
        if forced.get("peak_speed_rpm") and crit_rigid:
            out["unbalancePeakRpm"] = forced["peak_speed_rpm"]
            out["peakNearCritical"] = abs(forced["peak_speed_rpm"] - crit_rigid[0]) / crit_rigid[0]
        executed = all(c.get("exit") == 0 for c in cases.values())
        checks = {
            "all_cases_executed": executed,
            "jeffcott_reference_within_tolerance": (
                out.get("criticalRelError", float("inf")) <= JEFFCOTT_REFERENCE_REL_TOL
            ),
            "soft_bearing_lowers_first_critical": out.get("softBearingDropsCritical") is True,
            "short_stiff_raises_first_critical": (
                bool(crit_rigid)
                and out.get("shortStiffCriticalRpm", 0.0) > float(crit_rigid[0])
            ),
            "modal_campbell_agree": (
                out.get("modalVsCampbellRelDelta", float("inf"))
                <= MODAL_CAMPBELL_REL_TOL
            ),
            "forced_peak_near_first_critical": (
                out.get("peakNearCritical", float("inf")) <= FORCED_PEAK_REL_TOL
            ),
            "discretization_independence": (
                out.get("discretizationIndependencePassed") is True
            ),
        }
        out["checks"] = checks
        out["verificationPassed"] = all(checks.values())
        out["verificationFailureReasons"] = [
            name for name, passed in checks.items() if not passed
        ]
        out["status"] = "EXECUTED" if executed else "PARTIAL"
    except Exception as exc:  # noqa: BLE001
        out["reason"] = f"{type(exc).__name__}:{exc}"
        out["status"] = "FAILED"
    return out


def direct_unbalance() -> dict:
    """Minimal direct native ROSS 3.x unbalance response (governed script is 2.x API)."""
    import inspect

    # The workspace puts solvers/ on sys.path, which shadows the pip ROSS with
    # the workbench's own `ross` package; drop it so the real library resolves.
    original_path = list(sys.path)
    try:
        sys.path[:] = [p for p in sys.path if Path(p).name.lower() != "solvers"]
        import numpy as np
        import ross as rs

        if not hasattr(rs, "Material"):
            return {
                "status": "BLOCKED",
                "reason": f"wrong ross module resolved: {getattr(rs, '__file__', '?')}",
            }
    except Exception as exc:  # noqa: BLE001
        return {"status": "BLOCKED", "reason": f"import:{type(exc).__name__}:{exc}"}
    finally:
        sys.path[:] = original_path
    m = jeffcott_model()
    mat = rs.Material(
        STEEL["name"],
        E=STEEL["youngs_modulus_pa"],
        G_s=STEEL["shear_modulus_pa"],
        rho=STEEL["density_kg_m3"],
    )
    shaft = [
        rs.ShaftElement(
            L=s["length_m"],
            idl=0.0,
            odl=s["outer_diameter_m"],
            idr=0.0,
            odr=s["outer_diameter_m"],
            material=mat,
            shear_effects=True,
            rotary_inertia=True,
            gyroscopic=True,
        )
        for s in m["segments"]
    ]
    node = len(m["segments"]) // 2
    disk = rs.DiskElement.from_geometry(
        node,
        mat,
        width=m["disks"][0]["width_m"],
        i_d=m["disks"][0]["inner_diameter_m"],
        o_d=m["disks"][0]["outer_diameter_m"],
    )
    bearings = [
        rs.BearingElement(0, kxx=1e9, cxx=0.0),
        rs.BearingElement(len(m["segments"]), kxx=1e9, cxx=0.0),
    ]
    rotor = rs.Rotor(shaft, [disk], bearings)
    params = list(inspect.signature(rotor.run_unbalance_response).parameters)
    freq_key = next((k for k in params if "freq" in k.lower() or "speed" in k.lower()), None)
    if freq_key is None:
        return {"status": "BLOCKED", "reason": f"no frequency kwarg in {params}"}
    speed_rad = 300.0
    modal = rotor.run_modal(speed=speed_rad)
    positive = sorted(float(w) for w in modal.wn if float(w) > 0)
    whirl = positive[0] if positive else 900.0
    sweep = np.linspace(whirl * 0.5, whirl * 1.5, 25)
    kwargs = {freq_key: sweep, "node": node, "unbalance_magnitude": 1e-4, "unbalance_phase": 0.0}
    kwargs = {k: v for k, v in kwargs.items() if k in params}
    forced = rotor.run_unbalance_response(**kwargs)
    resp = np.asarray(forced.forced_resp, dtype=complex)
    mag = np.abs(resp).max(axis=0)
    peak = int(np.argmax(mag))
    xaxis = getattr(forced, "frequency_range", None)
    if xaxis is None:
        xaxis = getattr(forced, "speed_range", None)
    xval = float(np.asarray(xaxis)[peak]) if xaxis is not None else float(sweep[peak])
    first_rpm = whirl * 60.0 / (2 * 3.141592653589793)
    return {
        "status": "EXECUTED",
        "signature": params,
        "frequencyKey": freq_key,
        "peakResponseM": float(mag[peak]),
        "peakX": xval,
        "peakIndex": peak,
        "firstWhirlRpm": first_rpm,
        "responseShape": list(resp.shape),
    }


def main() -> int:
    WORK.mkdir(parents=True, exist_ok=True)
    out = bench_ross()
    try:
        out["directUnbalance"] = direct_unbalance()
    except Exception as exc:  # noqa: BLE001 - supplementary probe must not erase receipt
        out["directUnbalance"] = {
            "status": "BLOCKED",
            "reason": f"{type(exc).__name__}:{exc}",
        }
    (RECEIPTS / "issue38_ross.json").write_text(json.dumps(out, indent=2, sort_keys=True))
    print(
        "WROTE issue38_ross.json",
        f"status={out['status']}",
        f"verificationPassed={out.get('verificationPassed', False)}",
    )
    return 0 if out["status"] == "EXECUTED" and out.get("verificationPassed") is True else 1


if __name__ == "__main__":
    sys.exit(main())
