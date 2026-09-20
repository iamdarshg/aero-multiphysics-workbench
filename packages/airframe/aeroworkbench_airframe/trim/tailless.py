"""Analytical tailless/lifting-body trim and volume closure."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TaillessClosureSpec:
    cg_mac_fraction: float
    neutral_point_mac_fraction: float
    zero_control_pitch_coefficient: float
    elevon_pitch_derivative_per_rad: float
    elevon_limit_rad: float
    required_internal_volume_m3: float
    available_internal_volume_m3: float


@dataclass(frozen=True, slots=True)
class TaillessClosureReport:
    spec: TaillessClosureSpec
    feasible: bool
    static_margin: float
    required_elevon_rad: float
    reasons: tuple[str, ...]


def evaluate_tailless_closure(spec: TaillessClosureSpec) -> TaillessClosureReport:
    margin = spec.neutral_point_mac_fraction - spec.cg_mac_fraction
    required = 0.0
    if spec.elevon_pitch_derivative_per_rad == 0.0:
        reasons: tuple[str, ...] = ("TAILESS_ELEVON_AUTHORITY_ZERO",)
    else:
        required = -spec.zero_control_pitch_coefficient / spec.elevon_pitch_derivative_per_rad
        reasons = ()
    if margin <= 0.0:
        reasons += ("TAILESS_STATIC_MARGIN_NONPOSITIVE",)
    if abs(required) > spec.elevon_limit_rad:
        reasons += ("TAILESS_ELEVON_AUTHORITY_INSUFFICIENT",)
    if spec.required_internal_volume_m3 > spec.available_internal_volume_m3:
        reasons += ("TAILESS_INTERNAL_VOLUME_INSUFFICIENT",)
    return TaillessClosureReport(spec, not reasons, margin, required, reasons)


__all__ = ["TaillessClosureSpec", "TaillessClosureReport", "evaluate_tailless_closure"]
