"""AIRFRAME 97 Lane A: executable downstream requirement constraints."""

from __future__ import annotations

import pytest
from aeroworkbench_airframe.synthesis import (
    METRIC_DIMENSIONS,
    METRIC_ENFORCEMENT_ROUTES,
    ConstraintObservation,
    RequirementSpec,
    evaluate_downstream_requirements,
    compile_requirements,
)
from aeroworkbench_airframe.constraints import DOWNSTREAM_CONSTRAINT_ADAPTERS


def _spec(metric: str, operator: str = "at_most", value: float = 1.0):
    units = {
        "mass": "kg",
        "velocity": "m/s",
        "length": "m",
        "time": "s",
        "dimensionless": "dimensionless",
        "pressure": "Pa",
        "power": "W",
        "energy": "J",
        "volume": "m3",
    }
    return {
        "requirement_id": f"REQ-{metric}",
        "kind": "constraint",
        "metric": metric,
        "operator": operator,
        "value": value,
        "unit": units[METRIC_DIMENSIONS[metric]],
    }


DOWNSTREAM_METRICS = tuple(
    sorted(
        metric
        for metric, (mode, _target) in METRIC_ENFORCEMENT_ROUTES.items()
        if mode == "downstream"
    )
)


@pytest.mark.parametrize("metric", DOWNSTREAM_METRICS)
def test_registered_downstream_metric_has_executable_consumer(metric: str) -> None:
    compiled = compile_requirements([RequirementSpec(**_spec(metric))])
    result = evaluate_downstream_requirements(
        compiled,
        {metric: ConstraintObservation(metric=metric, value_si=0.5)},
    )
    assert result.feasible
    assert result.campaign_status == "campaign-feasible"
    assert result.findings[0].consumer_id


def test_hard_downstream_violation_is_campaign_infeasible_with_margin() -> None:
    compiled = compile_requirements([RequirementSpec(**_spec("power_limit"))])
    result = evaluate_downstream_requirements(
        compiled,
        {"power_limit": ConstraintObservation(metric="power_limit", value_si=2.5)},
    )
    finding = result.findings[0]
    assert result.campaign_status == "campaign-infeasible"
    assert not result.feasible
    assert finding.passed is False
    assert finding.margin == pytest.approx(-1.5)
    assert finding.requirement_ids == ("REQ-power_limit",)


def test_missing_consumer_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    compiled = compile_requirements([RequirementSpec(**_spec("service_ceiling"))])
    monkeypatch.delitem(DOWNSTREAM_CONSTRAINT_ADAPTERS, "service_ceiling")
    result = evaluate_downstream_requirements(
        compiled,
        {"service_ceiling": ConstraintObservation(metric="service_ceiling", value_si=0.5)},
    )
    assert result.campaign_status == "campaign-infeasible"
    assert result.findings[0].status == "unsupported"
    assert result.findings[0].margin is None
