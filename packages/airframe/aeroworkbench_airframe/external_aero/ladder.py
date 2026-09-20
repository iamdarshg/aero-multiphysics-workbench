"""Fidelity ladder and dispatcher for the external-aerodynamics participant.

The ladder is declared as :class:`aeroworkbench_optimization.FidelityImplementation`
rungs so the shared fidelity planner can weigh it like any other participant:
``analytical`` (closed-form screening), ``lifting_line`` (coarse VLM lifting-line
screening), ``vlm`` (full vortex-lattice with derivatives), and ``vspaero``
(governed native). The OpenFOAM/SU2 ``full_field`` seam is deliberately not
implemented and fails closed when requested.
"""

from __future__ import annotations

from dataclasses import replace

from aeroworkbench_optimization import (
    FidelityImplementation,
    FidelityPlan,
    FidelitySignals,
    plan_fidelity,
)

from .analytic import DragComponent, evaluate_analytic
from .case import ExternalAeroCase
from .contracts import AeroReference, ExternalAeroFidelity, ExternalAeroResult
from .errors import ExternalAeroCapabilityUnavailableError, ExternalAeroValidationError
from .native import VspaeroBackend, solve_vspaero
from .vlm import VlmOptions, solve_vlm

LIFTING_LINE_PANELS = 8

EXTERNAL_AERO_LADDER: tuple[FidelityImplementation, ...] = (
    FidelityImplementation(
        name="analytical",
        rank=0,
        cost=0.0,
        capabilities=("screening", "drag_buildup", "validity_limits"),
        description="closed-form finite-wing screening and drag build-up",
    ),
    FidelityImplementation(
        name="lifting_line",
        rank=1,
        cost=0.1,
        capabilities=("screening", "lifting_line", "spanloads"),
        description="coarse vortex-lattice lifting-line screening",
    ),
    FidelityImplementation(
        name="vlm",
        rank=2,
        cost=1.0,
        capabilities=("vlm", "spanloads", "stability_derivatives", "control_derivatives"),
        description="full vortex-lattice coefficient and derivative solution",
    ),
    FidelityImplementation(
        name="vspaero",
        rank=3,
        cost=10.0,
        capabilities=("native", "thick_bodies", "stability_derivatives", "control_derivatives"),
        description="governed native OpenVSP/VSPAERO solve (capability-gated)",
    ),
)

_FIDELITY_BY_NAME: dict[str, ExternalAeroFidelity] = {
    "analytical": ExternalAeroFidelity.ANALYTICAL,
    "lifting_line": ExternalAeroFidelity.LIFTING_LINE,
    "vlm": ExternalAeroFidelity.VLM,
    "vspaero": ExternalAeroFidelity.VSPAERO,
}


def plan_external_aero_fidelity(current: str, signals: FidelitySignals) -> FidelityPlan:
    """Plan one external-aerodynamics fidelity step with explainable rules."""

    return plan_fidelity(current, EXTERNAL_AERO_LADDER, signals)


def solve_external_aero(
    case: ExternalAeroCase,
    reference: AeroReference,
    *,
    fidelity: str = "vlm",
    vlm_options: VlmOptions | None = None,
    drag_components: tuple[DragComponent, ...] = (),
    miscellaneous_drag: float = 0.0,
    deflections: tuple[tuple[str, float], ...] | None = None,
    vspaero_backend: VspaeroBackend | None = None,
    run_id: str | None = None,
) -> ExternalAeroResult:
    """Dispatch one case through the fidelity ladder.

    ``analytical`` and ``lifting_line`` are closed-form/coarse VLM screening.
    ``vlm`` is the full vortex-lattice solution. ``vspaero`` runs the governed
    native path and fails closed without a real backend. ``full_field`` (the
    OpenFOAM/SU2 seam) is not implemented and fails closed.
    """

    if fidelity == "analytical":
        return evaluate_analytic(
            case,
            reference,
            drag_components=drag_components,
            miscellaneous_drag=miscellaneous_drag,
        )
    if fidelity == "lifting_line":
        options = replace(
            vlm_options or VlmOptions(),
            panels_per_surface=vlm_options.panels_per_surface
            if vlm_options is not None
            else LIFTING_LINE_PANELS,
            include_derivatives=False,
        )
        result = solve_vlm(case, reference, options, deflections=deflections)
        return replace(
            result,
            result_id=f"{case.case_id}-lifting-line",
            fidelity=ExternalAeroFidelity.LIFTING_LINE,
        )
    if fidelity == "vlm":
        return solve_vlm(
            case, reference, vlm_options or VlmOptions(), deflections=deflections
        )
    if fidelity == "vspaero":
        return solve_vspaero(
            case, reference, backend=vspaero_backend, run_id=run_id
        )
    if fidelity == "full_field":
        raise ExternalAeroCapabilityUnavailableError(
            "FULL_FIELD_AERO_SEAM_UNAVAILABLE: OpenFOAM/SU2 external-aero seam is not wired"
        )
    raise ExternalAeroValidationError(f"UNKNOWN_EXTERNAL_AERO_FIDELITY:{fidelity}")


__all__ = [
    "EXTERNAL_AERO_LADDER",
    "LIFTING_LINE_PANELS",
    "plan_external_aero_fidelity",
    "solve_external_aero",
]
