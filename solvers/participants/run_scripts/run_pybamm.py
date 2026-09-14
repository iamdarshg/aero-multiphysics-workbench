"""Governed PyBaMM run: executes a real cell/pack discharge in a subprocess.

Run as ``python run_pybamm.py`` with the case directory as cwd. Reads
case.json, writes result.json with per-cell and pack-level quantities, prints
a one-line summary. Only stdlib, numpy, and pybamm are imported; any
``solvers``-suffixed sys.path entry is dropped first.
"""

from __future__ import annotations

import json
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


import importlib  # noqa: E402
from typing import Any  # noqa: E402

pybamm: Any = importlib.import_module("pybamm")

CASE_FILE = Path("case.json")
RESULT_FILE = Path("result.json")


def _build_model(name: str) -> Any:
    if name == "spm":
        return pybamm.lithium_ion.SPM()
    if name == "spme":
        return pybamm.lithium_ion.SPMe()
    if name == "dfn":
        return pybamm.lithium_ion.DFN()
    if name == "thevenin":
        return pybamm.equivalent_circuit.Thevenin()
    raise RuntimeError(f"unknown PyBaMM model:{name}")


def _solve(
    model_name: str, parameter_set: str, current_a: float, duration_s: float
) -> dict[str, Any]:
    pybamm.set_logging_level("ERROR")
    model = _build_model(model_name)
    values = pybamm.ParameterValues(parameter_set)
    experiment = pybamm.Experiment(
        [f"Discharge at {current_a:g} A for {duration_s:g} seconds"]
    )
    simulation = pybamm.Simulation(model, parameter_values=values, experiment=experiment)
    solution = simulation.solve()
    variables = solution.all_models[0].variables
    if "Terminal voltage [V]" in variables:
        voltage = solution["Terminal voltage [V]"].entries
        capacity = solution["Discharge capacity [A.h]"].entries
        nominal = float(values["Nominal cell capacity [A.h]"])
        soc_end = max(0.0, min(1.0, 1.0 - float(capacity[-1]) / nominal))
        delivered = float(capacity[-1])
    else:
        voltage = solution["Battery voltage [V]"].entries
        soc_trace = solution["SoC"].entries if "SoC" in variables else None
        delivered = float(current_a * duration_s / 3600.0)
        soc_end = float(soc_trace[-1]) if soc_trace is not None else 0.0
    time_s = solution["Time [s]"].entries
    return {
        "cell_voltage_start_v": float(voltage[0]),
        "cell_voltage_end_v": float(voltage[-1]),
        "cell_delivered_ah": delivered,
        "cell_soc_end": float(soc_end),
        "solved_time_s": float(time_s[-1]),
        "solver": type(simulation.solver).__name__,
    }


def main() -> int:
    case = json.loads(CASE_FILE.read_text(encoding="utf-8"))
    n_series = int(case["n_series"])
    n_parallel = int(case["n_parallel"])
    solved = _solve(
        case["model"],
        case["parameter_set"],
        float(case["discharge_current_a"]),
        float(case["duration_s"]),
    )
    receipt = {
        "library": "pybamm",
        "solver_version": pybamm.__version__,
        "model": case["model"],
        "parameter_set": case["parameter_set"],
        "pack_voltage_start_v": solved["cell_voltage_start_v"] * n_series,
        "pack_voltage_end_v": solved["cell_voltage_end_v"] * n_series,
        "pack_delivered_ah": solved["cell_delivered_ah"] * n_parallel,
        "pack_soc_end": solved["cell_soc_end"],
        **{key: value for key, value in solved.items() if key != "solver"},
        "solver": solved["solver"],
    }
    RESULT_FILE.write_text(json.dumps(receipt, indent=2, sort_keys=True), encoding="utf-8")
    print(f"PYBAMM_OK model={case['model']} set={case['parameter_set']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
