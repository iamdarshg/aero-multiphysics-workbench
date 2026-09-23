"""Regression: governed ROSS forced analysis must work on ROSS 2.x and 3.x.

Issue #47: the governed run script hard-coded the ROSS 2.x ``frequency``
keyword, which ROSS 3.x removed in favour of ``speed_range``. The adapter must
select the supported keyword from the callable signature so the governed
``analysis="forced"`` path produces a native receipt on any pinned worker.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pytest

RUN_SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "solvers"
    / "participants"
    / "run_scripts"
    / "run_ross.py"
)
BENCH_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "gcp" / "bench_ross.py"


def _load_run_script() -> Any:
    spec = importlib.util.spec_from_file_location("run_ross_under_test", RUN_SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_bench_script(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Any:
    monkeypatch.setenv("RECEIPTS", str(tmp_path / "receipts"))
    monkeypatch.setenv("ROSS_WORK", str(tmp_path / "work"))
    monkeypatch.setenv("REPO_ROOT", str(Path(__file__).resolve().parents[2]))
    spec = importlib.util.spec_from_file_location("bench_ross_under_test", BENCH_SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _RotorWithSpeedRange:
    """ROSS 3.x-style signature."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def run_unbalance_response(
        self,
        node: int,
        unbalance_magnitude: float,
        unbalance_phase: float,
        speed_range: Any,
    ) -> Any:
        self.calls.append({"node": node, "speed_range": speed_range})
        size = len(speed_range)
        return type("Forced", (), {"forced_resp": np.ones((1, size), dtype=complex)})


class _RotorWithFrequency:
    """ROSS 2.x-style signature."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def run_unbalance_response(
        self,
        node: int,
        unbalance_magnitude: float,
        unbalance_phase: float,
        frequency: Any,
    ) -> Any:
        self.calls.append({"node": node, "frequency": frequency})
        size = len(frequency)
        return type("Forced", (), {"forced_resp": np.ones((1, size), dtype=complex)})


def test_governed_run_module_restores_solver_import_path() -> None:
    before = list(sys.path)

    _load_run_script()

    assert sys.path == before


@pytest.mark.parametrize("rotor_cls", [_RotorWithSpeedRange, _RotorWithFrequency])
def test_unbalance_response_selects_supported_keyword(rotor_cls: type) -> None:
    module = _load_run_script()
    rotor = rotor_cls()
    sweep = np.linspace(1.0, 10.0, 9)
    unbalance = {"node": 1, "magnitude_kg_m": 1e-4, "phase_deg": 0.0}

    result = module._unbalance_response(rotor, sweep, unbalance)

    assert len(rotor.calls) == 1
    call = rotor.calls[0]
    assert call["node"] == 1
    keyword = "speed_range" if rotor_cls is _RotorWithSpeedRange else "frequency"
    assert keyword in call
    assert call[keyword] is sweep
    assert result.forced_resp.shape == (1, sweep.size)


def test_unbalance_response_rejects_unsupported_signature() -> None:
    module = _load_run_script()

    class _RotorMissingKeyword:
        def run_unbalance_response(self, node: int, unbalance_magnitude: float,
                                   unbalance_phase: float, unknown: Any) -> Any:
            raise AssertionError("should not be called with an unsupported keyword")

    with pytest.raises(TypeError):
        module._unbalance_response(
            _RotorMissingKeyword(),
            np.linspace(1.0, 2.0, 3),
            {"node": 1, "magnitude_kg_m": 1e-4, "phase_deg": 0.0},
        )


def test_direct_probe_restores_solver_import_path(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_bench_script(monkeypatch, Path("/tmp"))
    solver_path = str(Path(__file__).resolve().parents[2] / "solvers")
    monkeypatch.setattr(sys, "path", [solver_path, *sys.path])
    monkeypatch.setitem(sys.modules, "ross", type("WrongRoss", (), {"__file__": "fake"})())
    before = list(sys.path)

    result = module.direct_unbalance()

    assert result["status"] == "BLOCKED"
    assert sys.path == before


def test_benchmark_targets_forced_sweep_at_detected_critical_and_passes_checks(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    module = _load_bench_script(monkeypatch, tmp_path)
    forced_targets: list[float] = []

    def native_case(
        analysis: str, model: dict[str, Any], speed_rpm: float,
        max_speed_rpm: float, name: str,
    ) -> dict[str, Any]:
        del model, max_speed_rpm
        if name == "jeffcott_campbell":
            return {"exit": 0, "critical_speeds_rpm": [10000.0, 20000.0]}
        if name == "jeffcott_refined_campbell":
            return {"exit": 0, "critical_speeds_rpm": [10050.0, 20020.0]}
        if name == "soft_bearing_campbell":
            return {"exit": 0, "critical_speeds_rpm": [6000.0, 18000.0]}
        if name == "jeffcott_modal":
            return {"exit": 0, "first_whirl_hz": 10000.0 / 60.0}
        if name == "short_stiff_campbell":
            return {"exit": 0, "critical_speeds_rpm": [25000.0]}
        assert analysis == "forced"
        forced_targets.append(speed_rpm)
        return {"exit": 0, "peak_speed_rpm": speed_rpm, "peak_response_m": 1e-4}

    monkeypatch.setattr(module, "gov_case", native_case)

    receipt = module.bench_ross()

    assert forced_targets == [pytest.approx(10000.0)]
    assert receipt["status"] == "EXECUTED"
    assert receipt["verificationPassed"] is True
    assert receipt["discretizationIndependencePassed"] is True
    assert all(receipt["checks"].values())


def test_benchmark_rejects_executed_forced_case_that_misses_resonance(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    module = _load_bench_script(monkeypatch, tmp_path)

    def native_case(
        analysis: str, model: dict[str, Any], speed_rpm: float,
        max_speed_rpm: float, name: str,
    ) -> dict[str, Any]:
        del analysis, model, speed_rpm, max_speed_rpm
        cases = {
            "jeffcott_campbell": {"exit": 0, "critical_speeds_rpm": [10000.0, 20000.0]},
            "jeffcott_refined_campbell": {
                "exit": 0, "critical_speeds_rpm": [10050.0, 20020.0],
            },
            "soft_bearing_campbell": {"exit": 0, "critical_speeds_rpm": [6000.0]},
            "jeffcott_modal": {"exit": 0, "first_whirl_hz": 10000.0 / 60.0},
            "short_stiff_campbell": {"exit": 0, "critical_speeds_rpm": [25000.0]},
            "jeffcott_forced": {
                "exit": 0, "peak_speed_rpm": 3000.0, "peak_response_m": 1e-4,
            },
        }
        return cases[name]

    monkeypatch.setattr(module, "gov_case", native_case)

    receipt = module.bench_ross()

    assert receipt["status"] == "EXECUTED"
    assert receipt["verificationPassed"] is False
    assert receipt["checks"]["forced_peak_near_first_critical"] is False


def test_main_returns_nonzero_and_direct_probe_cannot_mask_governed_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    module = _load_bench_script(monkeypatch, tmp_path)
    monkeypatch.setattr(
        module,
        "bench_ross",
        lambda: {
            "solver": "ROSS", "status": "PARTIAL", "verificationPassed": False,
            "checks": {"all_cases_executed": False},
        },
    )
    monkeypatch.setattr(module, "direct_unbalance", lambda: {"status": "EXECUTED"})

    assert module.main() == 1
    receipt = json.loads((module.RECEIPTS / "issue38_ross.json").read_text())
    assert receipt["status"] == "PARTIAL"
    assert receipt["verificationPassed"] is False


def test_main_contains_supplementary_direct_probe_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    module = _load_bench_script(monkeypatch, tmp_path)
    monkeypatch.setattr(
        module,
        "bench_ross",
        lambda: {
            "solver": "ROSS",
            "status": "EXECUTED",
            "verificationPassed": True,
            "checks": {"all_cases_executed": True},
        },
    )

    def fail_direct_probe() -> dict[str, Any]:
        raise RuntimeError("optional probe failed")

    monkeypatch.setattr(module, "direct_unbalance", fail_direct_probe)

    assert module.main() == 0
    receipt = json.loads((module.RECEIPTS / "issue38_ross.json").read_text())
    assert receipt["directUnbalance"] == {
        "status": "BLOCKED",
        "reason": "RuntimeError:optional probe failed",
    }
