"""Regression: governed ROSS forced analysis must work on ROSS 2.x and 3.x.

Issue #47: the governed run script hard-coded the ROSS 2.x ``frequency``
keyword, which ROSS 3.x removed in favour of ``speed_range``. The adapter must
select the supported keyword from the callable signature so the governed
``analysis="forced"`` path produces a native receipt on any pinned worker.
"""

from __future__ import annotations

import importlib.util
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


def _load_run_script() -> Any:
    spec = importlib.util.spec_from_file_location("run_ross_under_test", RUN_SCRIPT)
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
