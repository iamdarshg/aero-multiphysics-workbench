"""End-to-end three-family AIRFRAME verification driver."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def _module():
    path = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "gcp"
        / "bench_airframe_families.py"
    )
    spec = importlib.util.spec_from_file_location("bench_airframe_families", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _native_receipt(*, passed: bool = True) -> dict[str, object]:
    return {
        "resultId": "fixed-wing-vspaero",
        "source": "native_solver",
        "fidelity": "vspaero",
        "solver": {"name": "VSPAERO", "version": "3.52.1", "runId": "native-1"},
        "validity": {"passed": passed, "checks": {"converged": passed}},
    }


def test_driver_produces_complete_deterministic_three_family_ledger() -> None:
    module = _module()

    first = module.run_verification(_native_receipt())
    second = module.run_verification(_native_receipt())

    assert first["passed"] is True
    assert first["ledger"]["digest"] == second["ledger"]["digest"]
    entries = first["ledger"]["entries"]
    assert len(entries) == 21
    assert {entry["family"] for entry in entries} == {
        "fixed_wing",
        "lifting_body",
        "rotorcraft",
    }
    assert all(entry["status"] == "passed" for entry in entries)
    assert all(
        entry["replayHash"]
        for entry in entries
        if entry["stage"] == "provenance_replay"
    )


def test_driver_fails_closed_on_invalid_fixed_wing_native_receipt() -> None:
    module = _module()

    result = module.run_verification(_native_receipt(passed=False))

    assert result["passed"] is False
    promotion = next(
        entry
        for entry in result["ledger"]["entries"]
        if entry["family"] == "fixed_wing"
        and entry["stage"] == "fidelity_promotion"
    )
    assert promotion["status"] == "blocked"


def test_openvsp_worker_runs_three_family_gate_after_native_receipt() -> None:
    startup = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "gcp"
        / "run-openvsp-native-startup.sh"
    ).read_text(encoding="utf-8")

    native = startup.index("run-vspaero-native.py")
    families = startup.index("bench_airframe_families.py")
    assert native < families
    assert "VSPAERO_RECEIPT=\"$LOGDIR/vspaero-native-result.json\"" in startup
    assert "RECEIPTS=\"$LOGDIR/receipts\"" in startup
