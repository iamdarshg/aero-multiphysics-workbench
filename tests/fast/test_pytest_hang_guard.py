from __future__ import annotations

import pytest_hang_guard as hang_guard


def test_configure_is_inert_without_env(monkeypatch) -> None:
    hang_guard._cancel()
    monkeypatch.delenv("AERO_TEST_TIMEOUT_SECONDS", raising=False)
    hang_guard.pytest_configure(None)
    assert hang_guard._TIMEOUT_SECONDS == 0.0
    hang_guard._arm("demo::test")
    assert hang_guard._timer is None


def test_configure_parses_positive_seconds(monkeypatch) -> None:
    hang_guard._cancel()
    monkeypatch.setenv("AERO_TEST_TIMEOUT_SECONDS", "12.5")
    hang_guard.pytest_configure(None)
    assert hang_guard._TIMEOUT_SECONDS == 12.5


def test_configure_ignores_garbage(monkeypatch) -> None:
    hang_guard._cancel()
    monkeypatch.setenv("AERO_TEST_TIMEOUT_SECONDS", "soon")
    hang_guard.pytest_configure(None)
    assert hang_guard._TIMEOUT_SECONDS == 0.0


def test_arm_and_cancel_track_the_timer(monkeypatch) -> None:
    hang_guard._cancel()
    monkeypatch.setenv("AERO_TEST_TIMEOUT_SECONDS", "30")
    hang_guard.pytest_configure(None)
    hang_guard._arm("demo::slow")
    assert hang_guard._timer is not None
    hang_guard._cancel()
    assert hang_guard._timer is None
