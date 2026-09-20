"""AIRFRAME 10: bounded end-to-end family verification evidence."""

from __future__ import annotations

import json

import pytest
from aeroworkbench_airframe.synthesis import (
    compile_requirements_payload,
    generate_fixed_wing_seeds,
    synthesize_lifting_body_seam,
    synthesize_rotorcraft_seam,
)
from aeroworkbench_airframe.verification import (
    AIRFRAME_FINAL_VERIFICATION_POLICY,
    AirframeVerificationLedger,
    VerificationBudgetExceeded,
    VerificationCostReceipt,
    verify_airframe_families,
)


def _fixed_requirements():
    return compile_requirements_payload(
        {
            "requirements": [
                {"id": "payload", "kind": "mission", "metric": "payload_mass", "operator": "at_least", "value": 100.0, "unit": "kg"},  # noqa: E501
                {"id": "stall", "kind": "performance", "metric": "stall_speed", "operator": "at_most", "value": 30.0, "unit": "m/s"},  # noqa: E501
                {"id": "cruise", "kind": "performance", "metric": "cruise_speed", "operator": "at_least", "value": 65.0, "unit": "m/s"},  # noqa: E501
            ]
        }
    )


def _lifting_requirements():
    return compile_requirements_payload(
        {
            "requirements": [
                {"id": "span", "kind": "constraint", "metric": "span_limit", "operator": "at_most", "value": 12.0, "unit": "m"},  # noqa: E501
                {"id": "volume", "kind": "constraint", "metric": "volume_limit", "operator": "at_most", "value": 8.0, "unit": "m3"},  # noqa: E501
                {"id": "speed", "kind": "performance", "metric": "max_speed", "operator": "at_least", "value": 90.0, "unit": "m/s"},  # noqa: E501
            ]
        }
    )


def test_airframe10_final_verification_budget_is_hard_capped_at_ten_cents() -> None:
    policy = AIRFRAME_FINAL_VERIFICATION_POLICY
    assert policy.currency == "USD"
    assert policy.cumulative_cap_usd == pytest.approx(0.10)
    ledger = AirframeVerificationLedger("budget-proof", policy=policy)
    ledger.record_cost(
        VerificationCostReceipt(
            provider="local",
            resource="analytical-screening",
            wall_time_seconds=1.25,
            actual_cost_usd=0.06,
            run_id="run-a",
        )
    )
    with pytest.raises(VerificationBudgetExceeded, match="AIRFRAME_VERIFICATION_BUDGET_EXCEEDED"):
        ledger.record_cost(
            VerificationCostReceipt(
                provider="local",
                resource="second-screening",
                wall_time_seconds=0.5,
                actual_cost_usd=0.05,
                run_id="run-b",
            )
        )
    assert ledger.total_cost_usd == pytest.approx(0.06)


def test_airframe10_family_verification_is_analytical_and_replayable() -> None:
    fixed = generate_fixed_wing_seeds(_fixed_requirements(), seed_count=1)[0]
    lifting = synthesize_lifting_body_seam(_lifting_requirements()).seeds[0]
    rotor = synthesize_rotorcraft_seam(_fixed_requirements()).seeds[0]
    ledger = verify_airframe_families(
        verification_id="airframe10",
        fixed_wing=fixed,
        lifting_body=lifting,
        rotorcraft=rotor,
    )
    assert ledger.total_cost_usd == pytest.approx(0.0)
    assert {entry.family for entry in ledger.entries} == {
        "fixed_wing",
        "lifting_body",
        "rotorcraft",
    }
    assert all(entry.status == "passed" for entry in ledger.entries)
    assert all(entry.source == "analytical" for entry in ledger.entries)
    assert all(entry.native_receipt is None for entry in ledger.entries)
    rebuilt = AirframeVerificationLedger.from_dict(
        json.loads(json.dumps(ledger.as_dict()))
    )
    assert rebuilt.as_dict() == ledger.as_dict()
    assert rebuilt.digest == ledger.digest


def test_airframe10_native_claim_requires_a_trusted_native_receipt() -> None:
    ledger = AirframeVerificationLedger("native-proof")
    with pytest.raises(ValueError, match="NATIVE_VERIFICATION_RECEIPT_REQUIRED"):
        ledger.record_family(
            family="fixed_wing",
            status="passed",
            source="native_solver",
            evidence_digest="a" * 64,
        )
