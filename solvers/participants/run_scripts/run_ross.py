"""Governed ROSS run: builds a real shaft/disk/bearing model and analyzes it.

Executed by the native lifecycle as ``python run_ross.py`` with the case
directory as cwd. Reads case.json (a canonical rotating-assembly model plus any
participant-declared forcing spectra), writes result.json, prints a one-line
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
TWO_PI = 2.0 * float(np.pi)


def _material(model: dict[str, Any]) -> Any:
    spec = model["material"]
    return rs.Material(
        str(spec.get("name", "steel")),
        E=float(spec["youngs_modulus_pa"]),
        G_s=float(spec["shear_modulus_pa"]),
        rho=float(spec["density_kg_m3"]),
    )


def _build_rotor(case: dict[str, Any]) -> Any:
    model = case["model"]
    material = _material(model)
    gyroscopic = bool(model.get("gyroscopic", True))
    shear_effects = bool(model.get("shear_effects", True))
    rotary_inertia = bool(model.get("rotary_inertia", True))
    shaft = []
    for segment in model["segments"]:
        bore = float(segment.get("inner_diameter_m", 0.0))
        outer = float(segment["outer_diameter_m"])
        shaft.append(
            rs.ShaftElement(
                L=float(segment["length_m"]),
                idl=bore,
                odl=outer,
                idr=bore,
                odr=outer,
                material=material,
                shear_effects=shear_effects,
                rotary_inertia=rotary_inertia,
                gyroscopic=gyroscopic,
            )
        )
    disks = [
        rs.DiskElement.from_geometry(
            int(disk["position"]),
            material,
            width=float(disk["width_m"]),
            i_d=float(disk["inner_diameter_m"]),
            o_d=float(disk["outer_diameter_m"]),
        )
        for disk in model.get("disks", [])
    ]
    bearings = []
    for bearing in model.get("bearings", []):
        kwargs: dict[str, float] = {
            "kxx": float(bearing["kxx"]),
            "cxx": float(bearing["cxx"]),
        }
        for key in ("kyy", "cyy", "kxy", "kyx", "cxy", "cyx"):
            if bearing.get(key) is not None:
                kwargs[key] = float(bearing[key])
        bearings.append(rs.BearingElement(int(bearing["node"]), **kwargs))
    return rs.Rotor(shaft, disks, bearings)


def _critical_speeds(
    camp: Any, speeds_rpm: np.ndarray, *, forward_only: bool = True
) -> list[float]:
    speeds_rad = speeds_rpm * TWO_PI / 60.0
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
    return sorted({round(value, 6) for value in found if value > 0})


def _resolved_forcing(line: dict[str, Any], speed_rpm: float) -> dict[str, Any] | None:
    order = line.get("order")
    frequency = line.get("frequency_hz")
    dependence = str(line.get("speed_dependence", "fixed"))
    if dependence == "synchronous":
        resolved = speed_rpm / 60.0
    elif order is not None and (frequency is None or dependence == "order"):
        resolved = float(order) * speed_rpm / 60.0
    elif frequency is not None:
        resolved = float(frequency)
    elif order is not None:
        resolved = float(order) * speed_rpm / 60.0
    else:
        return None
    return {
        "source": str(line.get("source", "participant")),
        "label": str(line.get("label", "forcing")),
        "frequency_hz": resolved,
        "amplitude": line.get("amplitude"),
        "order": order,
        "speed_dependence": dependence,
        "harmonic_family": line.get("harmonic_family"),
    }


def _assess_forcing(
    mode_rows: list[np.ndarray],
    speeds_rpm: np.ndarray,
    forcings: list[dict[str, Any]],
    warning_margin_hz: float,
    critical_margin_hz: float,
) -> dict[str, Any] | None:
    best: dict[tuple[Any, ...], dict[str, Any]] = {}
    for index, speed in enumerate(speeds_rpm):
        modes = np.asarray(mode_rows[index], dtype=float)
        modes = np.abs(modes[np.isfinite(modes) & (modes > 0.0)]) / TWO_PI
        if modes.size == 0:
            continue
        for declared in forcings:
            line = _resolved_forcing(declared, float(speed))
            if line is None:
                continue
            nearest = float(modes[np.argmin(np.abs(modes - line["frequency_hz"]))])
            margin = abs(nearest - line["frequency_hz"])
            key = (
                line["source"],
                line["label"],
                line["order"],
                round(line["frequency_hz"], 9),
            )
            previous = best.get(key)
            if previous is None or margin < previous["margin_hz"]:
                best[key] = {
                    **line,
                    "nearest_mode_hz": nearest,
                    "margin_hz": margin,
                    "at_speed_rpm": float(speed),
                }
    if not best:
        return None
    lines = sorted(best.values(), key=lambda item: item["margin_hz"])
    minima = float(lines[0]["margin_hz"])
    if minima <= critical_margin_hz:
        state = "triggered"
        capability: str | None = "transient"
    elif minima <= warning_margin_hz:
        state = "watch"
        capability = "harmonic"
    else:
        state = "clear"
        capability = None
    return {
        "min_separation_hz": minima,
        "state": state,
        "required_capability": capability,
        "warning_margin_hz": warning_margin_hz,
        "critical_margin_hz": critical_margin_hz,
        "lines": lines,
    }


def _case_forcings(case: dict[str, Any]) -> list[dict[str, Any]]:
    raw = case.get("forcings") or []
    return [line for line in raw if isinstance(line, dict)]


def _with_forcing(
    payload: dict[str, Any],
    mode_rows: list[np.ndarray],
    speeds_rpm: np.ndarray,
    case: dict[str, Any],
) -> dict[str, Any]:
    forcings = _case_forcings(case)
    if not forcings:
        return payload
    report = _assess_forcing(
        mode_rows,
        speeds_rpm,
        forcings,
        float(case.get("forcing_warning_margin_hz", 5.0)),
        float(case.get("forcing_critical_margin_hz", 2.0)),
    )
    if report is not None:
        payload["forcing_separation"] = report
        payload["min_forcing_separation_hz"] = report["min_separation_hz"]
    return payload


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
    payload: dict[str, Any] = {
        "critical_speeds_rpm": criticals[:4],
        "speed_range_rpm": [float(value) for value in speeds_rpm],
    }
    wd = np.asarray(camp.wd, dtype=float)
    mode_rows = [wd[index, :] for index in range(wd.shape[0])]
    return _with_forcing(payload, mode_rows, speeds_rpm, case)


def _run_modal(rotor: Any, case: dict[str, Any]) -> dict[str, Any]:
    speed_rpm = float(case["speed_rpm"])
    speed_rad_s = speed_rpm * TWO_PI / 60.0
    modal = rotor.run_modal(speed=speed_rad_s)
    wn = [float(value) for value in modal.wn]
    zeta = [float(value) for value in modal.damping_ratio]
    if len(zeta) != len(wn):
        raise RuntimeError("ROSS modal damping ratios misaligned with frequencies")
    positive = sorted((value, index) for index, value in enumerate(wn) if value > 0)
    if not positive:
        raise RuntimeError("ROSS modal analysis returned no positive whirl")
    first_whirl, first_index = positive[0]
    payload: dict[str, Any] = {
        "first_whirl_hz": first_whirl / TWO_PI,
        "first_damping_ratio": zeta[first_index],
    }
    log_dec = None
    if hasattr(modal, "log_dec"):
        raw = np.asarray(modal.log_dec, dtype=float)
        if raw.size > first_index:
            value = float(raw[first_index])
            if np.isfinite(value):
                log_dec = value
    if log_dec is not None:
        payload["first_log_decrement"] = log_dec
    mode_rows = [np.asarray([value for value in wn if value > 0], dtype=float)]
    return _with_forcing(payload, mode_rows, np.asarray([speed_rpm]), case)


def _unbalance(case: dict[str, Any]) -> dict[str, Any]:
    definition = case["model"].get("unbalance")
    if not definition:
        return {"node": 1, "magnitude_kg_m": 1e-4, "phase_deg": 0.0}
    return dict(definition)


def _unbalance_response(rotor: Any, sweep: np.ndarray, unbalance: dict[str, Any]) -> Any:
    """Call ROSS unbalance response with the supported frequency keyword.

    ROSS 2.x uses ``frequency`` while ROSS 3.x uses ``speed_range`` (both in
    rad/s). Select by the function signature so the governed path works on any
    pinned worker stack instead of hard-coding one API generation.
    """

    import inspect

    parameters = inspect.signature(rotor.run_unbalance_response).parameters
    frequency_keyword = "speed_range" if "speed_range" in parameters else "frequency"
    return rotor.run_unbalance_response(
        node=int(unbalance["node"]),
        unbalance_magnitude=float(unbalance["magnitude_kg_m"]),
        unbalance_phase=float(unbalance["phase_deg"]),
        **{frequency_keyword: sweep},
    )


def _run_forced(rotor: Any, case: dict[str, Any]) -> dict[str, Any]:
    speed_rpm = float(case["speed_rpm"])
    speed_rad_s = speed_rpm * TWO_PI / 60.0
    unbalance = _unbalance(case)
    # `sweep` is in rad/s for both the legacy and current ROSS APIs.
    sweep = np.linspace(max(speed_rad_s * 0.2, 1.0), max(speed_rad_s * 1.5, 10.0), 9)
    forced = _unbalance_response(rotor, sweep, unbalance)
    response = np.asarray(forced.forced_resp, dtype=complex)
    if response.ndim != 2 or response.shape[1] != sweep.size:
        raise RuntimeError(f"unexpected ROSS forced response shape:{response.shape}")
    magnitude = np.abs(response).max(axis=0)
    peak_index = int(np.argmax(magnitude))
    payload: dict[str, Any] = {
        "peak_response_m": float(magnitude[peak_index]),
        "peak_speed_rpm": float(sweep[peak_index] * 60.0 / TWO_PI),
    }
    modal = rotor.run_modal(speed=speed_rad_s)
    positive = [float(value) for value in modal.wn if float(value) > 0]
    mode_rows = [np.asarray(positive, dtype=float)]
    return _with_forcing(payload, mode_rows, np.asarray([speed_rpm]), case)


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
