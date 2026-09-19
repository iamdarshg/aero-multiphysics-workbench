"""Evaluated fluid state, hydraulic resistance, and loss-evaluation receipts."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any

from .correlations import CorrelationRef, DeclaredCoefficient
from .errors import InternalFlowValidationError

ModelReference = CorrelationRef | DeclaredCoefficient


@dataclass(frozen=True, slots=True)
class BranchState:
    """Fluid state at a network node, evaluated from the shared property system."""

    pressure_pa: float
    temperature_k: float
    density_kg_m3: float
    viscosity_pa_s: float | None
    cp_j_kg_k: float
    enthalpy_j_kg: float

    def canonical(self) -> dict[str, Any]:
        return {
            "pressurePa": self.pressure_pa,
            "temperatureK": self.temperature_k,
            "densityKgM3": self.density_kg_m3,
            "viscosityPaS": self.viscosity_pa_s,
            "cpJkgK": self.cp_j_kg_k,
            "enthalpyJkg": self.enthalpy_j_kg,
        }


@dataclass(frozen=True, slots=True)
class HydraulicResistance:
    """Flow law ``dp = R_lin * Q + R_quad * Q * |Q|`` with ``Q = m_dot / rho``.

    Units: ``R_lin`` in ``Pa*s/m^3`` and ``R_quad`` in ``Pa*s^2/m^6``. This is
    the single generic contract every branch loss model produces, so the solver
    never needs to know which correlation generated the coefficients.
    """

    linear_pa_s_m3: float = 0.0
    quadratic_pa_s2_m6: float = 0.0

    def __post_init__(self) -> None:
        if not isfinite(self.linear_pa_s_m3) or self.linear_pa_s_m3 < 0.0:
            raise InternalFlowValidationError("INVALID_LINEAR_RESISTANCE")
        if not isfinite(self.quadratic_pa_s2_m6) or self.quadratic_pa_s2_m6 < 0.0:
            raise InternalFlowValidationError("INVALID_QUADRATIC_RESISTANCE")

    def pressure_drop_pa(self, volumetric_flow_m3_s: float) -> float:
        return self.linear_pa_s_m3 * volumetric_flow_m3_s + self.quadratic_pa_s2_m6 * (
            volumetric_flow_m3_s * abs(volumetric_flow_m3_s)
        )

    def canonical(self) -> dict[str, Any]:
        return {
            "linearPaSM3": self.linear_pa_s_m3,
            "quadraticPaS2M6": self.quadratic_pa_s2_m6,
        }


@dataclass(frozen=True, slots=True)
class LossEvaluation:
    """Receipt of one loss-model evaluation, with the correlations it cited."""

    reynolds_number: float | None
    friction_factor: float | None
    correlation_refs: tuple[ModelReference, ...]
    notes: tuple[str, ...] = ()

    def canonical(self) -> dict[str, Any]:
        return {
            "reynoldsNumber": self.reynolds_number,
            "frictionFactor": self.friction_factor,
            "correlations": [ref.canonical() for ref in self.correlation_refs],
            "notes": list(self.notes),
        }
