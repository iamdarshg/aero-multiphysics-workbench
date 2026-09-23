"""AIRFRAME 10: bounded end-to-end family verification evidence."""

from __future__ import annotations

import json
from types import SimpleNamespace

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


def test_airframe10_seed_only_inputs_are_not_a_passed_verification() -> None:
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
    assert not ledger.passed
    assert {entry.stage for entry in ledger.entries} == {
        "requirements", "synthesis", "campaign", "mass_cg_trim", "aero_rotor",
        "fidelity_promotion", "provenance_replay",
    }
    assert all(entry.status != "passed" for entry in ledger.entries if entry.stage != "synthesis")
    assert all(entry.source != "native_solver" for entry in ledger.entries)
    rebuilt = AirframeVerificationLedger.from_dict(
        json.loads(json.dumps(ledger.as_dict()))
    )
    assert rebuilt.as_dict() == ledger.as_dict()
    assert rebuilt.digest == ledger.digest


def test_airframe10_capability_absence_is_explicit(monkeypatch) -> None:
    fixed = generate_fixed_wing_seeds(_fixed_requirements(), seed_count=1)[0]

    class Capability:
        available = False
        detail = "test VSPAERO is not installed"

        def canonical(self):
            return {"available": self.available, "detail": self.detail}

    monkeypatch.setattr(
        "aeroworkbench_airframe.external_aero.native.probe_any_vspaero_capability",
        lambda: Capability(),
    )
    ledger = verify_airframe_families(
        verification_id="capability-proof",
        fixed_wing=fixed,
        lifting_body=fixed,
        rotorcraft=fixed,
    )
    promotions = [entry for entry in ledger.entries if entry.stage == "fidelity_promotion"]
    assert len(promotions) == 3
    assert all(entry.status == "unavailable" for entry in promotions)
    assert all("not installed" in entry.detail for entry in promotions)


def test_airframe10_native_claim_requires_a_trusted_native_receipt() -> None:
    ledger = AirframeVerificationLedger("native-proof")
    with pytest.raises(ValueError, match="NATIVE_VERIFICATION_RECEIPT_REQUIRED"):
        ledger.record_family(
            family="fixed_wing",
            status="passed",
            source="native_solver",
            evidence_digest="a" * 64,
        )


def _complete_family(*, replay_digest: str = "c" * 64, native_passed: bool = True):
    campaign = SimpleNamespace(
        digest="c" * 64,
        source="analytical",
        fidelity="medium",
    )

    class Session:
        def run(self):
            return campaign

    return SimpleNamespace(
        seed=SimpleNamespace(content_hash="a" * 64),
        requirements=SimpleNamespace(digest="b" * 64),
        session=lambda: Session(),
        mass_cg_trim=SimpleNamespace(
            digest="d" * 64, source="analytical", fidelity="analytical"
        ),
        aero_result=SimpleNamespace(
            digest="e" * 64, source="analytical", fidelity="medium"
        ),
        native_receipt={
            "source": "native_solver",
            "validity": {"passed": native_passed},
            "digest": "f" * 64,
        },
        replay_receipt=SimpleNamespace(
            digest=replay_digest, source="replay", fidelity="medium"
        ),
    )


def test_airframe10_complete_observed_replay_passes_all_three_families(monkeypatch) -> None:
    capability = SimpleNamespace(
        available=True,
        detail="native VSPAERO test capability",
        canonical=lambda: {"available": True},
    )
    monkeypatch.setattr(
        "aeroworkbench_airframe.external_aero.native.probe_any_vspaero_capability",
        lambda: capability,
    )

    ledger = verify_airframe_families(
        verification_id="complete-three-family-proof",
        fixed_wing=_complete_family(),
        lifting_body=_complete_family(),
        rotorcraft=_complete_family(),
    )

    assert ledger.passed is True
    replay = [entry for entry in ledger.entries if entry.stage == "provenance_replay"]
    assert len(replay) == 3
    assert all(entry.status == "passed" for entry in replay)
    assert all(entry.replay_hash == "c" * 64 for entry in replay)


def test_airframe10_mismatched_replay_digest_fails_closed(monkeypatch) -> None:
    capability = SimpleNamespace(
        available=True,
        detail="native VSPAERO test capability",
        canonical=lambda: {"available": True},
    )
    monkeypatch.setattr(
        "aeroworkbench_airframe.external_aero.native.probe_any_vspaero_capability",
        lambda: capability,
    )

    ledger = verify_airframe_families(
        verification_id="bad-replay-proof",
        fixed_wing=_complete_family(replay_digest="0" * 64),
        lifting_body=_complete_family(),
        rotorcraft=_complete_family(),
    )

    assert ledger.passed is False
    failed = [
        entry
        for entry in ledger.entries
        if entry.family == "fixed_wing" and entry.stage == "provenance_replay"
    ]
    assert len(failed) == 1
    assert failed[0].status == "blocked"
    assert failed[0].detail == "replay digest does not match campaign digest"


def test_airframe10_failed_native_receipt_cannot_promote(monkeypatch) -> None:
    capability = SimpleNamespace(
        available=True,
        detail="native VSPAERO test capability",
        canonical=lambda: {"available": True},
    )
    monkeypatch.setattr(
        "aeroworkbench_airframe.external_aero.native.probe_any_vspaero_capability",
        lambda: capability,
    )

    ledger = verify_airframe_families(
        verification_id="failed-native-proof",
        fixed_wing=_complete_family(native_passed=False),
        lifting_body=_complete_family(),
        rotorcraft=_complete_family(),
    )

    promotion = [
        entry
        for entry in ledger.entries
        if entry.family == "fixed_wing" and entry.stage == "fidelity_promotion"
    ]
    assert len(promotion) == 1
    assert promotion[0].status == "blocked"
    assert promotion[0].detail == "native receipt validity did not pass"


def test_airframe10_rotorcraft_and_lifting_body_accept_trusted_medium_promotion(
    monkeypatch,
) -> None:
    capability = SimpleNamespace(
        available=True,
        detail="native VSPAERO test capability",
        canonical=lambda: {"available": True},
    )
    monkeypatch.setattr(
        "aeroworkbench_airframe.external_aero.native.probe_any_vspaero_capability",
        lambda: capability,
    )
    medium = SimpleNamespace(
        digest="9" * 64,
        source="benchmark",
        fidelity="medium",
        validity=SimpleNamespace(passed=True),
    )
    lifting = _complete_family()
    rotor = _complete_family()
    lifting.native_receipt = None
    rotor.native_receipt = None
    lifting.promotion_receipt = medium
    rotor.promotion_receipt = medium

    ledger = verify_airframe_families(
        verification_id="family-specific-promotion",
        fixed_wing=_complete_family(),
        lifting_body=lifting,
        rotorcraft=rotor,
    )

    assert ledger.passed is True
    promotions = {
        entry.family: entry
        for entry in ledger.entries
        if entry.stage == "fidelity_promotion"
    }
    assert promotions["fixed_wing"].source == "native_solver"
    assert promotions["lifting_body"].source == "benchmark"
    assert promotions["rotorcraft"].source == "benchmark"


def test_airframe10_rejects_untrusted_or_low_fidelity_promotion(monkeypatch) -> None:
    capability = SimpleNamespace(
        available=False,
        detail="VSPAERO not installed",
        canonical=lambda: {"available": False},
    )
    monkeypatch.setattr(
        "aeroworkbench_airframe.external_aero.native.probe_any_vspaero_capability",
        lambda: capability,
    )
    lifting = _complete_family()
    lifting.native_receipt = None
    lifting.promotion_receipt = SimpleNamespace(
        digest="9" * 64,
        source="self_asserted",
        fidelity="analytical",
        validity=SimpleNamespace(passed=True),
    )

    ledger = verify_airframe_families(
        verification_id="reject-untrusted-promotion",
        fixed_wing=_complete_family(),
        lifting_body=lifting,
        rotorcraft=_complete_family(),
    )

    promotion = next(
        entry
        for entry in ledger.entries
        if entry.family == "lifting_body" and entry.stage == "fidelity_promotion"
    )
    assert promotion.status == "unavailable"


def test_airframe10_observed_native_receipt_replays_without_local_binary(monkeypatch) -> None:
    capability = SimpleNamespace(
        available=False,
        detail="VSPAERO not installed on replay host",
        canonical=lambda: {"available": False},
    )
    monkeypatch.setattr(
        "aeroworkbench_airframe.external_aero.native.probe_any_vspaero_capability",
        lambda: capability,
    )

    ledger = verify_airframe_families(
        verification_id="native-receipt-replay",
        fixed_wing=_complete_family(),
        lifting_body=_complete_family(),
        rotorcraft=_complete_family(),
    )

    assert ledger.passed is True
    fixed = next(
        entry
        for entry in ledger.entries
        if entry.family == "fixed_wing" and entry.stage == "fidelity_promotion"
    )
    assert fixed.status == "passed"
    assert fixed.source == "native_solver"
