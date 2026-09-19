"""Constraint-driven pruning: preflight, then envelope gate, then meanline screening.

The pipeline mirrors the issue's ordering: the cheap canonical design-space
preflight and the TURBO 05 manufacturing envelope gate reject a candidate before
CAD, and the TURBO 03 meanline screen runs before any native promotion. Native
promotion itself stays fail-closed: it requires an explicit trusted receipt.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from ..meanline import ScreeningLimits, ThroughflowResult, solve_throughflow
from . import _engine
from .mapping import meanline_stage_from_state
from .spec import GenerativeSpec

__all__ = [
    "PIPELINE_STAGES",
    "ScreeningReport",
    "admissible_candidates",
    "native_promotion_allowed",
    "screen_candidate",
    "screen_state",
]

PIPELINE_STAGES: tuple[str, ...] = (
    "design-space-preflight",
    "manufacturing-preflight",
    "meanline-screening",
    "native-promotion",
)


@dataclass(frozen=True, slots=True)
class ScreeningReport:
    """Typed, fail-closed outcome of the cheap-to-expensive screening pipeline."""

    admissible: bool
    preflight_reasons: tuple[str, ...]
    envelope_status: str
    envelope_reasons: tuple[str, ...]
    meanline_checked: bool
    meanline_screened: bool | None
    meanline_validity_passed: bool | None
    meanline_pressure_ratio: float | None
    meanline_reasons: tuple[str, ...]
    stage_reached: str
    source: str


def _meanline_reasons(result: ThroughflowResult) -> tuple[str, ...]:
    reasons: list[str] = []
    for index, row in enumerate(result.rows):
        for indicator in row.indicators:
            if not indicator.passed:
                reasons.append(f"row{index}:{indicator.name}")
    for name, passed in result.validity.checks.items():
        if not passed:
            reasons.append(f"validity:{name}")
    return tuple(reasons)


def screen_state(
    space: Mapping[str, Any],
    state: Mapping[str, Any],
    spec: GenerativeSpec,
    *,
    envelopes: Any | None = None,
    limits: ScreeningLimits | None = None,
) -> ScreeningReport:
    """Screen one design state, failing closed at the first hard rejection."""

    preflight = _engine.preflight_design_state(space, state)
    if preflight:
        return ScreeningReport(
            admissible=False,
            preflight_reasons=preflight,
            envelope_status="not-evaluated",
            envelope_reasons=(),
            meanline_checked=False,
            meanline_screened=None,
            meanline_validity_passed=None,
            meanline_pressure_ratio=None,
            meanline_reasons=(),
            stage_reached="design-space-preflight",
            source="canonical-preflight",
        )
    flat = _engine.flatten_design_state(space, state)
    envelope_status = "not-evaluated"
    envelope_reasons: tuple[str, ...] = ()
    stage_reached = "design-space-preflight"
    if envelopes is not None:
        report = _engine.manufacturability_gate(envelopes).evaluate(flat)
        envelope_status = str(report.status)
        envelope_reasons = tuple(str(item) for item in report.reasons)
        if not bool(report.admissible):
            return ScreeningReport(
                admissible=False,
                preflight_reasons=(),
                envelope_status=envelope_status,
                envelope_reasons=envelope_reasons,
                meanline_checked=False,
                meanline_screened=None,
                meanline_validity_passed=None,
                meanline_pressure_ratio=None,
                meanline_reasons=(),
                stage_reached=f"manufacturing-preflight:{report.stage_reached}",
                source="manufacturability-gate",
            )
        stage_reached = "manufacturing-preflight"

    try:
        stage = meanline_stage_from_state(space, state, spec)
        result = solve_throughflow(stage, limits=limits)
    except Exception as exc:  # noqa: BLE001 - unresolved physics fails closed
        return ScreeningReport(
            admissible=False,
            preflight_reasons=(),
            envelope_status=envelope_status,
            envelope_reasons=envelope_reasons,
            meanline_checked=False,
            meanline_screened=None,
            meanline_validity_passed=None,
            meanline_pressure_ratio=None,
            meanline_reasons=(f"MEANLINE_ERROR:{type(exc).__name__}:{exc}",),
            stage_reached=stage_reached,
            source="meanline-screening",
        )
    reasons = _meanline_reasons(result)
    admissible = bool(result.validity.passed and result.screened)
    return ScreeningReport(
        admissible=admissible,
        preflight_reasons=(),
        envelope_status=envelope_status,
        envelope_reasons=envelope_reasons,
        meanline_checked=True,
        meanline_screened=bool(result.screened),
        meanline_validity_passed=bool(result.validity.passed),
        meanline_pressure_ratio=float(result.pressure_ratio),
        meanline_reasons=reasons,
        stage_reached="meanline-screening" if admissible else stage_reached,
        source="meanline-screening",
    )


def screen_candidate(
    space: Mapping[str, Any],
    candidate: Any,
    spec: GenerativeSpec,
    *,
    envelopes: Any | None = None,
    limits: ScreeningLimits | None = None,
) -> ScreeningReport:
    """Screen an engine candidate; a preflight-invalid candidate fails closed."""

    if not bool(candidate.valid):
        return ScreeningReport(
            admissible=False,
            preflight_reasons=tuple(str(item) for item in candidate.preflight_reasons),
            envelope_status="not-evaluated",
            envelope_reasons=(),
            meanline_checked=False,
            meanline_screened=None,
            meanline_validity_passed=None,
            meanline_pressure_ratio=None,
            meanline_reasons=(),
            stage_reached="design-space-preflight",
            source="canonical-preflight",
        )
    return screen_state(
        space, candidate.state, spec, envelopes=envelopes, limits=limits
    )


def admissible_candidates(
    space: Mapping[str, Any],
    candidates: Iterable[Any],
    spec: GenerativeSpec,
    *,
    envelopes: Any | None = None,
    limits: ScreeningLimits | None = None,
) -> tuple[Any, ...]:
    """Filter a candidate stream down to those that survive the whole pipeline."""

    admitted: list[Any] = []
    for candidate in candidates:
        if screen_candidate(space, candidate, spec, envelopes=envelopes, limits=limits).admissible:
            admitted.append(candidate)
    return tuple(admitted)


def native_promotion_allowed(report: ScreeningReport, *, receipt_present: bool) -> bool:
    """Native promotion requires an admissible design *and* a trusted native receipt."""

    return bool(report.admissible and report.meanline_checked and receipt_present)
