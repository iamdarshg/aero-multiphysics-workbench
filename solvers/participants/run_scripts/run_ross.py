"""Governed ROSS run: builds a real shaft/bearing/disk model and analyzes it.

Executed by the native lifecycle as ``python run_ross.py`` with the case
directory as cwd. Reads case.json, writes result.json, prints a one-line
summary. Only stdlib, numpy, and ross are imported; any ``solvers``-suffixed
sys.path entry is dropped first so the real ROSS library always resolves.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def _isolate() -> None:
    cleaned = [
        entry
        for entry in sys.path
        if entry and Path(entry).name.lower() != "solvers"
    ]
    if len(cleaned) != len(sys.path):
        sys.path[:] = cleaned

_isolate()

os.environ.setdefault("NUMBA_DISABLE_JIT", "1")

import importlib  # noqa: E402
from typing import Any  # noqa: E402

import numpy as np  # noqa: E402

rs: Any = importlib.import_module("ross")

CASE_FILE = Path("case.json")
RESULT_FILE = Path("result.json")


def _build_rotor(case: dict[str, Any]) -> Any:
    steel = rs.Material("steel", E=211e9, G_s=81.2e9, rho=7810)
    n_elements = int(case["n_elements"])
    element_length = float(case["shaft_length_m"]) / n_elements
    diameter = float(case["shaft_diameter_m"])
    shaft = [
        rs.ShaftElement(
            L=element_length,
            idl=0.0,
            odl=diameter,
            idr=0.0,
            odr=diameter,
            material=steel,
            shear_effects=True,
            rotary_inertia=True,
            gyroscopic=True,
        )
        for _ in range(n_elements)
    ]
    stiffness = float(case["bearing_stiffness_n_m"])
    damping = float(case["bearing_damping_n_s_m"])
    bearings = [
        rs.BearingElement(0, kxx=stiffness, cxx=damping, kyy=stiffness, cyy=damping),
        rs.BearingElement(
            n_elements, kxx=stiffness, cxx=damping, kyy=stiffness, cyy=damping
        ),
    ]
    disks: list[Any] = []
    disk = case.get("disk")
    if disk is not None:
        disks.append(
            rs.DiskElement.from_geometry(
                int(disk["position"]),
                steel,
                width=float(disk["width_m"]),
                i_d=diameter,
                o_d=float(disk["outer_diameter_m"]),
            )
        )
    return rs.Rotor(shaft, disks, bearings)


def _critical_speeds(
    camp: Any, speeds_rpm: np.ndarray, *, forward_only: bool = True
) -> list[float]:
    speeds_rad = speeds_rpm * 2.0 * float(np.pi) / 60.0
    wd = np.asarray(camp.wd, dtype=float)
    whirl = np.asarray(camp.whirl_values, dtype=float)
    found: list[float] = []
    for mode in range(wd.shape[1]):
        branch = wd[:, mode]
        forward = whirl[:, mode] > 0.5
        for index in range(len(speeds_rpm) - 1):
            if forward_only and not (forward[index] and forward[index + 1]):
                continue
            gap_before = branch[index] - speeds_rad[index]
            gap_after = branch[index + 1] - speeds_rad[index + 1]
            if gap_before == 0.0:
                found.append(float(speeds_rpm[index]))
            elif gap_before * gap_after < 0.0:
                fraction = gap_before / (gap_before - gap_after)
                step = speeds_rpm[index + 1] - speeds_rpm[index]
                found.append(float(speeds_rpm[index] + fraction * step))
    unique = sorted({round(value, 6) for value in found if value > 0})
    return unique


def _run_campbell(rotor: Any, case: dict[str, Any]) -> dict[str, Any]:
    max_speed = float(case["max_speed_rpm"])
    # A dense synchronous-speed sweep keeps mode-tracked critical detection
    # stable across BLAS/LAPACK backends; a coarse sweep can miss a crossing.
    speeds_rpm = np.linspace(0.0, max_speed, 41)
    camp = rotor.run_campbell(speed_range=speeds_rpm)
    criticals = _critical_speeds(camp, speeds_rpm)
    if len(criticals) < 2:
        # Some builds classify the higher mode as backward whirl; fall back to
        # every branch crossing so a physically present critical is not lost.
        combined = sorted(
            set(criticals) | set(_critical_speeds(camp, speeds_rpm, forward_only=False))
        )
        criticals = combined
    if not criticals:
        raise RuntimeError("ROSS found no critical speeds")
    return {
        "critical_speeds_rpm": criticals[:4],
        "speed_range_rpm": [float(value) for value in speeds_rpm],
    }


def _run_modal(rotor: Any, case: dict[str, Any]) -> dict[str, Any]:
    speed_rad_s = float(case["speed_rpm"]) * 2.0 * float(np.pi) / 60.0
    modal = rotor.run_modal(speed=speed_rad_s)
    wn = [float(value) for value in modal.wn]
    zeta = [float(value) for value in modal.damping_ratio]
    if len(zeta) != len(wn):
        raise RuntimeError("ROSS modal damping ratios misaligned with frequencies")
    positive = sorted((value, index) for index, value in enumerate(wn) if value > 0)
    if not positive:
        raise RuntimeError("ROSS modal analysis returned no positive whirl")
    _, first_index = positive[0]
    return {
        "first_whirl_hz": positive[0][0] / (2.0 * float(np.pi)),
        "first_damping_ratio": zeta[first_index],
    }


def _run_forced(rotor: Any, case: dict[str, Any]) -> dict[str, Any]:
    speed_rpm = float(case["speed_rpm"])
    speed_rad_s = speed_rpm * 2.0 * float(np.pi) / 60.0
    sweep = np.linspace(max(speed_rad_s * 0.2, 1.0), max(speed_rad_s * 1.5, 10.0), 9)
    forced = rotor.run_unbalance_response(
        node=1, unbalance_magnitude=1e-4, unbalance_phase=0.0, frequency=sweep
    )
    response = np.asarray(forced.forced_resp, dtype=complex)
    if response.ndim != 2 or response.shape[1] != sweep.size:
        raise RuntimeError(f"unexpected ROSS forced response shape:{response.shape}")
    magnitude = np.abs(response).max(axis=0)
    peak_index = int(np.argmax(magnitude))
    return {
        "peak_response_m": float(magnitude[peak_index]),
        "peak_speed_rpm": float(sweep[peak_index] * 60.0 / (2.0 * float(np.pi))),
    }


def main() -> int:
    case = json.loads(CASE_FILE.read_text(encoding="utf-8"))
    rotor = _build_rotor(case)
    analysis = case["analysis"]
    if analysis == "campbell":
        payload = _run_campbell(rotor, case)
    elif analysis == "modal":
        payload = _run_modal(rotor, case)
    elif analysis == "forced":
        payload = _run_forced(rotor, case)
    else:
        raise RuntimeError(f"unknown ROSS analysis:{analysis}")
    receipt = {
        "library": "ross-rotordynamics",
        "solver_version": rs.__version__,
        "analysis": analysis,
        "ndof": int(rotor.ndof),
        **payload,
    }
    RESULT_FILE.write_text(json.dumps(receipt, indent=2, sort_keys=True), encoding="utf-8")
    print(f"ROSS_OK analysis={analysis} ndof={rotor.ndof}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
