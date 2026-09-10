from __future__ import annotations

from pathlib import Path

from aeroworkbench_coupling.precice import (
    CouplingSession,
    InterfaceField,
    build_precice_config,
    verify_mapping,
)
from precice.config_builder import inspect_precice


def test_precice_config_is_deterministic_and_contains_implicit_quasi_newton() -> None:
    config = build_precice_config()
    fixture = (
        Path(__file__).parents[2] / "examples" / "edf" / "coupling" / "precice-config.xml"
    ).read_text(encoding="utf-8").strip()
    assert config.xml == fixture
    assert len(config.digest_sha256) == 64
    assert "IQN-ILS" in config.xml


def test_precice_rejects_undeclared_fields_and_preserves_restart_events() -> None:
    try:
        build_precice_config(fields=(InterfaceField("Pressure", "scalar", "fluid", "missing"),))
    except ValueError as error:
        assert str(error) == "FIELD_PARTICIPANT_NOT_DECLARED"
    else:
        raise AssertionError("undeclared participant must be rejected")
    session = CouplingSession()
    session.checkpoint("ckpt-1")
    session.accept_step()
    session.rollback("ckpt-1", "interface residual exceeded")
    assert [event.kind for event in session.events()] == ["checkpoint", "rollback"]


def test_precice_mapping_receipt_is_conservation_gated() -> None:
    conservative = verify_mapping(mapping="conservative", relative_conservation_error=1e-8)
    consistent = verify_mapping(mapping="consistent", relative_conservation_error=1e-3)
    assert conservative.state == "completed"
    assert consistent.state == "failed"
    assert inspect_precice("definitely-not-precice").state == "unavailable"
