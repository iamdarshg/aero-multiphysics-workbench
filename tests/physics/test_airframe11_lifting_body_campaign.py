"""Lane D: lifting-body geometry identity and generic campaign fixture."""

from __future__ import annotations

import json
from pathlib import Path

from aeroworkbench_airframe.synthesis import (
    build_lifting_body_campaign_fixture,
    compile_requirements_payload,
)
from aeroworkbench_airframe.external_aero import prepare_vspaero_case


def _requirements():
    path = Path(__file__).resolve().parents[1] / "airframe" / "synthesis" / "requirements_lifting_body.json"
    return compile_requirements_payload(json.loads(path.read_text(encoding="utf-8")))


def test_lifting_body_fixture_materializes_canonical_thick_body() -> None:
    fixture = build_lifting_body_campaign_fixture(_requirements(), evaluations=2)
    body = fixture.case.bodies[0]
    payload = fixture.case.canonical()["bodies"][0]

    assert body.role == "lifting_body"
    assert body.volume_m3 > 0.0
    assert payload["bodyId"] == "lifting-body-centerbody"
    assert payload["semanticIdentity"] == {
        "bodyId": "lifting-body-centerbody",
        "role": "lifting_body",
        "semanticKey": "lifting-body-centerbody.solid",
    }


def test_lifting_body_fixture_uses_generic_medium_native_ladder() -> None:
    fixture = build_lifting_body_campaign_fixture(_requirements(), evaluations=2)
    assert [item.name for item in fixture.spec.generic.fidelity_ladder] == [
        "analytical",
        "medium",
        "native",
    ]
    receipt = fixture.session().run()
    assert receipt.record.results
    assert all("volume_m3" in result.outputs for result in receipt.record.results)

    assert fixture.case.canonical()["bodies"]


def test_lifting_body_native_payload_preserves_body_identity(tmp_path: Path) -> None:
    fixture = build_lifting_body_campaign_fixture(_requirements(), evaluations=1)
    manifest = prepare_vspaero_case(fixture.case, fixture.case.geometry_reference(), tmp_path)
    serialized = json.loads(manifest.read_text(encoding="utf-8"))
    assert serialized["bodies"] == fixture.case.canonical()["bodies"]
    assert serialized["bodies"][0]["semanticIdentity"]["role"] == "lifting_body"
