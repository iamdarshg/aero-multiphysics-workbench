"""Bounded analytical gas-turbine demonstrator (TDD-first)."""

from __future__ import annotations

from aeroworkbench_core.types import ResultSource
from examples.gas_turbine.system import run_gas_turbine_demo


def test_gas_turbine_demo_is_explicitly_analytical() -> None:
    result = run_gas_turbine_demo()
    assert result.result.net_shaft_power_w > 0
    assert result.result.bookkeeping_residual_fraction < 1e-12
    assert result.result.provenance.source is ResultSource.ANALYTICAL
    assert any("not pyCycle" in item for item in result.result.limitations)
    assert result.geometry_hash is not None


def test_gas_turbine_demo_rejects_infeasible_cycle() -> None:
    import pytest
    from examples.gas_turbine.system import run_gas_turbine_demo_with

    with pytest.raises(ValueError, match="turbine inlet temperature must exceed"):
        run_gas_turbine_demo_with(turbine_inlet_temperature_k=400.0)
