"""Transition/separation/model-disagreement diagnostics and escalation triggers.

These are declared, deterministic analytical diagnostics: transition location
from a critical Reynolds number, flat-plate skin-friction and pressure-
coefficient distributions, model-to-model disagreement, and finite-difference
sensitivity to turbulence intensity and roughness. Large disagreement or
operation near a model limit is surfaced as an escalation reason so the caller
can invoke the generic fidelity planner.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from math import isfinite
from typing import Any

from aeroworkbench_core.types import Provenance
from aeroworkbench_fluid_properties import SoftwareIdentity

from .contracts import (
    SOFTWARE_IDENTITY,
    Validity,
    analytical_provenance,
)
from .errors import TurbulenceValidationError
from .models import ModelSelection, TurbulenceModel
from .regimes import FlowRegime, FlowState, RegimeClassification
from .wall import (
    CorrelationRef,
    skin_friction_coefficient_flat_plate,
)


@dataclass(frozen=True, slots=True)
class ModelDisagreement:
    """Normalized spread of a scalar prediction across several models."""

    metric: str
    values: tuple[tuple[TurbulenceModel, float], ...]
    spread: float
    threshold: float
    exceeded: bool
    detail: str

    def canonical(self) -> dict[str, Any]:
        return {
            "metric": self.metric,
            "values": [[model.value, value] for model, value in self.values],
            "spread": self.spread,
            "threshold": self.threshold,
            "exceeded": self.exceeded,
            "detail": self.detail,
        }


def compare_model_predictions(
    metric: str,
    predictions: Mapping[TurbulenceModel, float],
    *,
    threshold: float = 0.2,
) -> ModelDisagreement:
    """Compare a scalar prediction across models with a normalized spread."""
    if len(predictions) < 2:
        raise TurbulenceValidationError("DISAGREEMENT_REQUIRES_TWO_MODELS")
    if not isfinite(threshold) or threshold <= 0.0:
        raise TurbulenceValidationError("DISAGREEMENT_THRESHOLD_INVALID")
    ordered = tuple(
        (model, float(value))
        for model, value in sorted(predictions.items(), key=lambda item: item[0].value)
    )
    numbers = [value for _, value in ordered]
    if not all(isfinite(value) for value in numbers):
        raise TurbulenceValidationError("DISAGREEMENT_VALUE_NONFINITE")
    low = min(numbers)
    high = max(numbers)
    mean = sum(numbers) / len(numbers)
    spread = (high - low) / max(abs(mean), 1e-12)
    exceeded = spread > threshold
    detail = (
        f"{metric}: spread {spread:.4g} across {len(ordered)} models "
        f"({'exceeds' if exceeded else 'within'} threshold {threshold:.4g})"
    )
    return ModelDisagreement(
        metric=metric,
        values=ordered,
        spread=spread,
        threshold=threshold,
        exceeded=exceeded,
        detail=detail,
    )


def transition_location_fraction(
    flow: FlowState, *, critical_reynolds: float, source: str
) -> tuple[float, CorrelationRef]:
    """Streamwise transition location as a fraction of the reference length.

    ``Re_x = Re_c`` gives ``x/L = Re_c/Re_L``. A value above 1 means transition
    is predicted beyond the reference length; the caller decides how to treat
    that. The correlation cites the declared critical Reynolds source.
    """
    if not isfinite(critical_reynolds) or critical_reynolds <= 0.0:
        raise TurbulenceValidationError("CRITICAL_REYNOLDS_INVALID")
    if not source.strip():
        raise TurbulenceValidationError("TRANSITION_SOURCE_REQUIRED")
    reference = CorrelationRef(
        correlation_id="critical-reynolds-transition",
        version="1",
        source=source,
    )
    return critical_reynolds / flow.reynolds_number, reference


def skin_friction_distribution_flat_plate(
    flow: FlowState,
    *,
    sample_count: int = 8,
    regime: FlowRegime | None = None,
) -> tuple[tuple[float, ...], CorrelationRef]:
    """Analytical flat-plate skin-friction distribution along the reference."""
    if sample_count < 1:
        raise TurbulenceValidationError("SAMPLE_COUNT_INVALID")
    resolved = regime or flow.thresholds.classify_reynolds(flow.reynolds_number)
    values: list[float] = []
    reference = None
    for index in range(1, sample_count + 1):
        fraction = index / sample_count
        local_reynolds = flow.reynolds_number * fraction
        coefficient, reference = skin_friction_coefficient_flat_plate(
            local_reynolds, regime=resolved
        )
        values.append(coefficient)
    assert reference is not None
    return tuple(values), reference


def pressure_coefficient(
    *, pressure_pa: float, freestream_pressure_pa: float, dynamic_pressure_pa: float
) -> float:
    """``Cp = (p - p_inf) / q_inf`` with a strictly positive dynamic pressure."""
    if not isfinite(dynamic_pressure_pa) or dynamic_pressure_pa <= 0.0:
        raise TurbulenceValidationError("DYNAMIC_PRESSURE_INVALID")
    if not isfinite(pressure_pa) or not isfinite(freestream_pressure_pa):
        raise TurbulenceValidationError("PRESSURE_NONFINITE")
    return (pressure_pa - freestream_pressure_pa) / dynamic_pressure_pa


def _normalized_difference(base: float, perturbed: float) -> float:
    if not isfinite(base) or not isfinite(perturbed):
        raise TurbulenceValidationError("SENSITIVITY_VALUE_NONFINITE")
    return abs(perturbed - base) / max(abs(base), 1e-12)


def intensity_sensitivity(
    flow: FlowState,
    *,
    model_fn: Callable[[FlowState], float],
    intensity_delta: float = 0.005,
) -> float:
    """Normalized finite-difference sensitivity to turbulence intensity."""
    if not isfinite(intensity_delta) or intensity_delta <= 0.0:
        raise TurbulenceValidationError("INTENSITY_DELTA_INVALID")
    perturbed_intensity = min(1.0, flow.turbulence_intensity + intensity_delta)
    base = model_fn(flow)
    perturbed = model_fn(replace(flow, turbulence_intensity=perturbed_intensity))
    return _normalized_difference(base, perturbed)


def roughness_sensitivity(
    flow: FlowState,
    *,
    model_fn: Callable[[FlowState], float],
    roughness_delta_m: float = 1.0e-5,
) -> float:
    """Normalized finite-difference sensitivity to equivalent sand-grain roughness."""
    if flow.roughness is None:
        raise TurbulenceValidationError("ROUGHNESS_SENSITIVITY_REQUIRES_ROUGHNESS")
    if not isfinite(roughness_delta_m) or roughness_delta_m <= 0.0:
        raise TurbulenceValidationError("ROUGHNESS_DELTA_INVALID")
    from .roughness import make_roughness

    perturbed = make_roughness(
        surface=flow.roughness.surface,
        model=flow.roughness.model,
        equivalent_sand_grain_m=flow.roughness.equivalent_sand_grain_m + roughness_delta_m,
        source="declared sensitivity perturbation",
    )
    base = model_fn(flow)
    perturbed_value = model_fn(replace(flow, roughness=perturbed))
    return _normalized_difference(base, perturbed_value)


@dataclass(frozen=True, slots=True)
class DiagnosticsReport:
    """Transition/separation/disagreement diagnostics with escalation triggers."""

    label: str
    transition_location_fraction: float | None
    separation_fraction: float
    reattachment: bool
    skin_friction: tuple[float, ...]
    pressure_coefficient: tuple[float, ...]
    disagreement: ModelDisagreement | None
    intensity_sensitivity: float
    roughness_sensitivity: float
    near_model_limit: bool
    escalation_reasons: tuple[str, ...]
    validity: Validity
    provenance: Provenance
    software: SoftwareIdentity = SOFTWARE_IDENTITY

    def canonical(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "transitionLocationFraction": self.transition_location_fraction,
            "separationFraction": self.separation_fraction,
            "reattachment": self.reattachment,
            "skinFriction": list(self.skin_friction),
            "pressureCoefficient": list(self.pressure_coefficient),
            "disagreement": (
                self.disagreement.canonical() if self.disagreement is not None else None
            ),
            "intensitySensitivity": self.intensity_sensitivity,
            "roughnessSensitivity": self.roughness_sensitivity,
            "nearModelLimit": self.near_model_limit,
            "escalationReasons": list(self.escalation_reasons),
            "validity": self.validity.canonical(),
            "units": {
                "transitionLocationFraction": "1",
                "separationFraction": "1",
                "skinFriction": "1",
                "pressureCoefficient": "1",
            },
            "inputsHash": self.provenance.inputs_hash,
            "software": self.software.canonical(),
        }


def assess_diagnostics(
    flow: FlowState,
    classification: RegimeClassification,
    selection: ModelSelection,
    *,
    model_predictions: Mapping[TurbulenceModel, float] | None = None,
    skin_friction: Sequence[float] = (),
    pressure_coefficient_values: Sequence[float] = (),
    transition_location: float | None = None,
    intensity_sensitivity_value: float = 0.0,
    roughness_sensitivity_value: float = 0.0,
    disagreement_threshold: float = 0.2,
    sensitivity_threshold: float = 0.3,
    separation_threshold: float = 0.2,
) -> DiagnosticsReport:
    """Assemble the diagnostics report and its escalation triggers."""
    disagreement = (
        compare_model_predictions(
            "scalar-prediction", model_predictions, threshold=disagreement_threshold
        )
        if model_predictions is not None
        else None
    )
    reasons: list[str] = []
    if disagreement is not None and disagreement.exceeded:
        reasons.append(f"MODEL_DISAGREEMENT:{disagreement.spread:.4g}")
    if intensity_sensitivity_value > sensitivity_threshold:
        reasons.append(f"TURBULENCE_INTENSITY_SENSITIVITY:{intensity_sensitivity_value:.4g}")
    if roughness_sensitivity_value > sensitivity_threshold:
        reasons.append(f"ROUGHNESS_SENSITIVITY:{roughness_sensitivity_value:.4g}")
    if selection.near_limit:
        reasons.append("NEAR_MODEL_VALIDITY_LIMIT")
    if flow.separation_fraction > separation_threshold:
        reasons.append(f"LARGE_SEPARATED_REGION:{flow.separation_fraction:.4g}")
    if (
        classification.regime is FlowRegime.TRANSITIONAL
        and not selection.validity.supports_transition
    ):
        reasons.append("TRANSITION_MODEL_REQUIRED")
    checks = {
        "transition_state_declared": flow.transition_state.value != "unknown",
        "skin_friction_available": len(skin_friction) > 0,
        "pressure_coefficient_available": len(pressure_coefficient_values) > 0,
        "disagreement_evaluated": disagreement is not None,
    }
    validity = Validity(
        passed=True,
        checks=checks,
        detail="; ".join(reasons) if reasons else "no escalation triggers fired",
    )
    provenance = analytical_provenance(
        "turbulence.diagnostics",
        {
            "flow": flow.canonical(),
            "regime": classification.regime.value,
            "selection": selection.canonical(),
            "transitionLocationFraction": transition_location,
            "separationFraction": flow.separation_fraction,
            "skinFriction": list(skin_friction),
            "pressureCoefficient": list(pressure_coefficient_values),
            "disagreement": (
                disagreement.canonical() if disagreement is not None else None
            ),
            "intensitySensitivity": intensity_sensitivity_value,
            "roughnessSensitivity": roughness_sensitivity_value,
        },
        "declared analytical transition/separation/sensitivity diagnostics",
    )
    return DiagnosticsReport(
        label=flow.label,
        transition_location_fraction=transition_location,
        separation_fraction=flow.separation_fraction,
        reattachment=flow.separation_fraction > 0.0 and flow.pressure_gradient_parameter < 0.0,
        skin_friction=tuple(float(value) for value in skin_friction),
        pressure_coefficient=tuple(float(value) for value in pressure_coefficient_values),
        disagreement=disagreement,
        intensity_sensitivity=intensity_sensitivity_value,
        roughness_sensitivity=roughness_sensitivity_value,
        near_model_limit=selection.near_limit,
        escalation_reasons=tuple(reasons),
        validity=validity,
        provenance=provenance,
    )


__all__ = [
    "DiagnosticsReport",
    "ModelDisagreement",
    "assess_diagnostics",
    "compare_model_predictions",
    "intensity_sensitivity",
    "pressure_coefficient",
    "roughness_sensitivity",
    "skin_friction_distribution_flat_plate",
    "transition_location_fraction",
]
