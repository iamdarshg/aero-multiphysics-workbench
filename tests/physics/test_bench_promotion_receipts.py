"""Receipt-driven final promotion gate regressions."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def _module():
    path = Path(__file__).resolve().parents[2] / "scripts" / "gcp" / "bench_promotion.py"
    spec = importlib.util.spec_from_file_location("bench_promotion", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _governed_module():
    path = Path(__file__).resolve().parents[2] / "scripts" / "gcp" / "governed-blocker-run.py"
    spec = importlib.util.spec_from_file_location("governed_blocker_run", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _governed(participant: str) -> dict[str, object]:
    return {
        "participant": participant,
        "state": "COMPLETED",
        "envelope_source": "native_solver",
        "envelope_validity": {"passed": True},
    }


def test_final_gate_derives_native_participants_from_receipts() -> None:
    promotion = _module()
    receipts = {
        "issue37_openfoam.json": {"benchmarks": {"channel": {"status": "EXECUTED"}}},
        "issue39_elmer.json": {"benchmarks": {"steadyDirichlet": {"status": "EXECUTED"}}},
        "issue38_ross.json": {"status": "EXECUTED", "verificationPassed": True},
        "issue39_electrical.json": {
            "status": "EXECUTED",
            "cases": [
                {
                    "converged": True,
                    "powerBalancePassed": True,
                    "heatBalancePassed": True,
                }
            ],
        },
        "07_code_aster_static.json": _governed("structural-static"),
        "07_code_aster_modal.json": _governed("structural-modal"),
        "11_precice_native_window.json": _governed("native-coupled-window"),
    }

    states = promotion.derive_receipt_states(receipts)

    assert states == {
        "incompressible-steady-flow": True,
        "structural-static": True,
        "structural-modal": True,
        "thermal-conduction": True,
        "rotor-campbell": True,
        "rotating-electrical-machine": True,
        "coupled-interface-validation": True,
    }


def test_final_gate_rejects_failed_or_untrusted_native_receipts() -> None:
    promotion = _module()
    receipts = {
        "07_code_aster_static.json": {
            **_governed("structural-static"),
            "envelope_source": "analytical",
        },
        "07_code_aster_modal.json": {
            **_governed("structural-modal"),
            "envelope_validity": {"passed": False},
        },
        "11_precice_native_window.json": {
            **_governed("native-coupled-window"),
            "state": "FAILED",
        },
    }

    states = promotion.derive_receipt_states(receipts)

    assert states["structural-static"] is False
    assert states["structural-modal"] is False
    assert states["coupled-interface-validation"] is False


def test_final_worker_produces_governed_receipts_before_promotion() -> None:
    startup = (
        Path(__file__).resolve().parents[2] / "scripts" / "gcp" / "final-verification-startup.sh"
    ).read_text(encoding="utf-8")

    governed = startup.index("governed-blocker-run.py")
    benchmarks = startup.index("run-benchmarks.sh")
    assert governed < benchmarks
    assert "--out /var/log/proofs/receipts" in startup
    assert "--issues 07static,07modal,11" in startup


def test_final_gate_only_succeeds_for_honest_validated_set() -> None:
    promotion = _module()

    assert promotion.final_gate_succeeded(
        {
            "positiveControl": {"validatedFinal": True},
            "honestSet": {"validatedFinal": True},
            "refusesInvalid": True,
        }
    )
    assert not promotion.final_gate_succeeded(
        {
            "positiveControl": {"validatedFinal": True},
            "honestSet": {"validatedFinal": False},
            "refusesInvalid": True,
        }
    )


def test_final_worker_does_not_swallow_failed_verification() -> None:
    root = Path(__file__).resolve().parents[2]
    startup = (root / "scripts" / "gcp" / "final-verification-startup.sh").read_text(
        encoding="utf-8"
    )
    benchmarks = (root / "scripts" / "gcp" / "run-benchmarks.sh").read_text(encoding="utf-8")

    assert 'touch "$LOGDIR/final-verification.failed"' in startup
    assert 'touch "$LOGDIR/final-verification.done"' in startup
    assert 'exit "$FINAL_RC"' in startup
    assert "GATE_RC=$?" in benchmarks
    assert 'exit "$GATE_RC"' in benchmarks


def _structural_level(name: str, mesh_size: float, displacement: float) -> dict[str, object]:
    return {
        "issue": f"07_code_aster_static_{name}",
        "participant": "structural-static",
        "state": "COMPLETED",
        "envelope_source": "native_solver",
        "envelope_validity": {"passed": True},
        "scalars": {"max_displacement_m": displacement},
        "mesh_size_m": mesh_size,
        "inputs_digest": name * 64,
        "run_id": f"run-{name}",
    }


def test_code_aster_static_summary_requires_three_level_independence() -> None:
    governed = _governed_module()
    levels = [
        _structural_level("a", 0.04, 1.000e-3),
        _structural_level("b", 0.03, 0.990e-3),
        _structural_level("c", 0.02, 0.987e-3),
    ]

    summary = governed.summarize_structural_static(levels)

    assert summary["state"] == "COMPLETED"
    assert summary["envelope_source"] == "native_solver"
    assert summary["envelope_validity"]["passed"] is True
    assert summary["mesh_independence_passed"] is True
    assert summary["independence"]["accepted"] is True


def test_code_aster_static_summary_fails_closed_on_missing_native_level() -> None:
    governed = _governed_module()
    levels = [
        _structural_level("a", 0.04, 1.000e-3),
        _structural_level("b", 0.03, 0.990e-3),
        {**_structural_level("c", 0.02, 0.987e-3), "state": "FAILED"},
    ]

    summary = governed.summarize_structural_static(levels)

    assert summary["state"] == "FAILED"
    assert summary["mesh_independence_passed"] is False


def test_code_aster_static_driver_runs_three_mesh_levels(monkeypatch, tmp_path) -> None:
    governed = _governed_module()
    built_sizes: list[float] = []

    def build(_work, mesh_size_m: float):
        built_sizes.append(mesh_size_m)
        return {
            "mesh": tmp_path / f"mesh-{mesh_size_m}.med",
            "mesh_hash": f"{len(built_sizes)}" * 64,
            "tip_nodes": 4,
            "mesh_size_m": mesh_size_m,
        }

    class Driver:
        out = tmp_path

        def governed(self, issue, participant, inputs, **kwargs):
            del inputs, kwargs
            index = len([item for item in built_sizes if item <= built_sizes[-1]])
            values = {0.04: 1.000e-3, 0.03: 0.990e-3, 0.02: 0.987e-3}
            return {
                **_structural_level(
                    issue.rsplit("_", 1)[-1], built_sizes[-1], values[built_sizes[-1]]
                ),
                "issue": issue,
                "participant": participant,
                "inputs_digest": str(index) * 64,
            }

    monkeypatch.setattr(governed, "_aster_mesh", build)

    summary = governed.issue_07_static_study(Driver())

    assert built_sizes == [0.04, 0.03, 0.02]
    assert summary["mesh_independence_passed"] is True
