from __future__ import annotations

import json
from pathlib import Path

from aeroworkbench_thermal import ThermalNetwork
from code_aster.adapter import inspect_code_aster, prepare_structural_case
from openfoam.adapter import inspect_openfoam, prepare_case


def test_solver_case_builders_are_physics_specific_and_fail_closed() -> None:
    assert prepare_case(rotating_model="AMI", thermal_model="CHT").application == "pimpleFoam"
    assert prepare_case(compressibility="compressible").application == "rhoPimpleFoam"
    assert prepare_structural_case(analysis="modal", prestress=True).prestress
    assert inspect_openfoam("missing-openfoam").state == "unavailable"
    assert inspect_code_aster("missing-code-aster").state == "unavailable"


def test_thermal_network_keeps_global_closure_explicit() -> None:
    network = ThermalNetwork()
    network.connect("motor", "ambient", 0.5)
    network.add_load("motor", 10)
    result = network.solve()
    assert dict(result.temperatures_c)["motor"] > 25
    assert result.converged is True
    assert result.energy_residual_w < 1e-6


def test_benchmark_manifest_marks_native_requirements() -> None:
    manifest = json.loads(
        (Path(__file__).parents[2] / "benchmarks" / "manifest.json").read_text(encoding="utf-8")
    )
    assert len(manifest["benchmarks"]) == 4
    assert manifest["benchmarks"][1]["requiredCapability"] == "code-aster"
