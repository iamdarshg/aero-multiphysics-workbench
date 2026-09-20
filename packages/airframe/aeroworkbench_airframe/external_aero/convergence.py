"""Numerical-independence signals for the vortex-lattice fidelity level.

The convergence study runs the declared panel-refinement ladder through
:func:`aeroworkbench_convergence.run_independence_study`, so the verdict is made
from the participant-declared quantities of interest (``CL``, ``CD``, ``Cm``)
alone, exactly like every other mesh-independence study on the platform. The
evidence is reduced onto the typed :class:`ConvergenceRecord` carried by the
external-aerodynamics result.
"""

from __future__ import annotations

from dataclasses import replace

from aeroworkbench_convergence import (
    IndependenceReport,
    QuantityOfInterest,
    RefinementLevel,
    StudyRun,
    run_independence_study,
)

from ..canonical import content_digest
from .case import ExternalAeroCase
from .contracts import AeroReference, ConvergenceRecord, ExternalAeroResult
from .errors import ExternalAeroValidationError
from .vlm import VlmOptions, solve_vlm

DEFAULT_PANEL_LADDER: tuple[int, ...] = (8, 16, 32)
_QUANTITY_ATTRIBUTES: dict[str, str] = {"CL": "lift", "CD": "drag", "Cm": "pitch"}


def _panel_count(level: RefinementLevel) -> int:
    declared = level.declared_dict()
    if "panels" not in declared:
        raise ExternalAeroValidationError(f"CONVERGENCE_LEVEL_MISSING_PANELS:{level.name}")
    return int(round(declared["panels"]))


def run_vlm_independence_report(
    case: ExternalAeroCase,
    reference: AeroReference,
    *,
    panel_ladder: tuple[int, ...] = DEFAULT_PANEL_LADDER,
    relative_tolerance: float = 0.05,
    require_all_valid: bool = True,
) -> IndependenceReport:
    """Execute the panel-refinement ladder and return the independence report."""

    if len(panel_ladder) < 2:
        raise ExternalAeroValidationError("CONVERGENCE_LADDER_REQUIRES_TWO_LEVELS")
    quantities = tuple(_QUANTITY_ATTRIBUTES)
    levels = tuple(
        RefinementLevel(
            name=f"panels-{count}",
            resolution=1.0 / count,
            declared=(("panels", float(count)),),
        )
        for count in panel_ladder
    )
    qoi = tuple(
        QuantityOfInterest(
            name=name, relative_tolerance=relative_tolerance, reference_scale=1.0
        )
        for name in quantities
    )

    def execute(level: RefinementLevel) -> StudyRun:
        count = _panel_count(level)
        result = solve_vlm(
            case, reference, VlmOptions(panels_per_surface=count, include_derivatives=False)
        )
        values = tuple(
            (name, float(getattr(result.coefficients, _QUANTITY_ATTRIBUTES[name])))
            for name in quantities
        )
        return StudyRun(
            level=level.name,
            run_id=f"{case.case_id}:{level.name}",
            input_hash=content_digest(
                {"case": case.digest, "panels": count, "reference": reference.canonical()}
            ),
            qoi=values,
            valid=result.validity.passed,
            source="analytical",
        )

    return run_independence_study(
        "mesh",
        levels,
        qoi,
        execute,
        min_levels=2,
        require_all_valid=require_all_valid,
    )


def vlm_convergence_record(report: IndependenceReport) -> ConvergenceRecord:
    """Reduce an independence report to the typed convergence record."""

    observed = next(
        (trend.observed_order for trend in report.trends if trend.observed_order is not None),
        None,
    )
    return ConvergenceRecord(
        kind=report.kind,
        levels=report.levels,
        quantity_names=tuple(trend.name for trend in report.trends),
        quantity_values=tuple(trend.values for trend in report.trends),
        observed_order=observed,
        accepted=report.accepted,
        reason=report.reason,
    )


def study_vlm_convergence(
    case: ExternalAeroCase,
    reference: AeroReference,
    *,
    panel_ladder: tuple[int, ...] = DEFAULT_PANEL_LADDER,
    relative_tolerance: float = 0.05,
    require_all_valid: bool = True,
) -> ConvergenceRecord:
    """Convenience wrapper returning only the convergence record."""

    report = run_vlm_independence_report(
        case,
        reference,
        panel_ladder=panel_ladder,
        relative_tolerance=relative_tolerance,
        require_all_valid=require_all_valid,
    )
    return vlm_convergence_record(report)


def with_vlm_convergence(
    result: ExternalAeroResult,
    case: ExternalAeroCase,
    reference: AeroReference,
    *,
    panel_ladder: tuple[int, ...] = DEFAULT_PANEL_LADDER,
    relative_tolerance: float = 0.05,
) -> ExternalAeroResult:
    """Return a copy of a VLM result carrying its numerical-independence record."""

    record = study_vlm_convergence(
        case, reference, panel_ladder=panel_ladder, relative_tolerance=relative_tolerance
    )
    return replace(result, convergence=record)


__all__ = [
    "DEFAULT_PANEL_LADDER",
    "run_vlm_independence_report",
    "study_vlm_convergence",
    "vlm_convergence_record",
    "with_vlm_convergence",
]
