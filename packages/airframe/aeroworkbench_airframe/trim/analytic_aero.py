"""Deterministic linear aerodynamic model plus a derivative-bundle adapter.

:class:`LinearAeroModel` is a tiny analytic coefficient provider used for
fixtures and as the reference implementation of the AIRFRAME 04 seam. It fails
closed whenever a non-zero state variable needs a derivative the provider does
not carry, so a missing coefficient is never silently treated as a zero term.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import pi
from typing import Any

from .contract import (
    AeroCoefficients,
    AeroReference,
    AeroState,
    DerivativeBundle,
    LateralDirectionalDerivatives,
    LongitudinalDerivatives,
    finite,
)
from .errors import AeroCoefficientError


@dataclass(frozen=True, slots=True)
class LinearAeroModel:
    """A linear derivative model in stability axes (the analytical reference)."""

    model_id: str
    reference_geometry: AeroReference
    longitudinal: LongitudinalDerivatives
    lateral_directional: LateralDirectionalDerivatives
    induced_drag_factor: float = 0.0

    def __post_init__(self) -> None:
        if not self.model_id.strip():
            raise ValueError("AERO_MODEL_ID_REQUIRED")
        finite(self.induced_drag_factor, "inducedDragFactor")
        if self.induced_drag_factor < 0.0:
            raise ValueError("NEGATIVE_INDUCED_DRAG_FACTOR")

    @property
    def provider_id(self) -> str:
        return self.model_id

    def reference(self) -> AeroReference:
        return self.reference_geometry

    def _lift_derivative(self, alpha: float) -> float:
        if alpha == 0.0:
            return 0.0
        value = self.longitudinal.cl_alpha
        if value is None:
            raise AeroCoefficientError("MISSING_LONGITUDINAL_DERIVATIVES:cl_alpha")
        return value * alpha

    def _pitch_derivative(self, alpha: float) -> float:
        if alpha == 0.0:
            return 0.0
        value = self.longitudinal.cm_alpha
        if value is None:
            raise AeroCoefficientError("MISSING_LONGITUDINAL_DERIVATIVES:cm_alpha")
        return value * alpha

    def _term(self, derivative: float | None, variable: float, name: str) -> float:
        if variable == 0.0:
            return 0.0
        if derivative is None:
            raise AeroCoefficientError(f"MISSING_DERIVATIVE:{name}")
        return derivative * variable

    def coefficients(self, state: AeroState) -> AeroCoefficients:
        reference = self.reference_geometry
        chord = reference.chord.value_si
        span = reference.span.value_si
        velocity = state.velocity.value_si
        alpha = state.alpha.value_si
        beta = state.beta.value_si
        elevator = state.deflection("elevator")
        aileron = state.deflection("aileron")
        rudder = state.deflection("rudder")
        q_hat = 0.0 if velocity == 0.0 else state.pitch_rate.value_si * chord / (2.0 * velocity)
        p_hat = 0.0 if velocity == 0.0 else state.roll_rate.value_si * span / (2.0 * velocity)
        r_hat = 0.0 if velocity == 0.0 else state.yaw_rate.value_si * span / (2.0 * velocity)
        lon = self.longitudinal
        lat = self.lateral_directional

        c_lift = (
            lon.cl_0
            + self._lift_derivative(alpha)
            + self._term(lon.cl_de, elevator, "cl_de")
            + self._term(lon.cl_q, q_hat, "cl_q")
        )
        c_drag = (
            lon.cd_0
            + self._term(lon.cd_alpha, alpha, "cd_alpha")
            + (self.induced_drag_factor * c_lift * c_lift)
        )
        c_pitch = (
            lon.cm_0
            + self._pitch_derivative(alpha)
            + self._term(lon.cm_de, elevator, "cm_de")
            + self._term(lon.cm_q, q_hat, "cm_q")
        )
        c_side = self._term(lat.cy_beta, beta, "cy_beta")
        c_roll = (
            self._term(lat.cl_beta, beta, "cl_beta")
            + self._term(lat.cl_p, p_hat, "cl_p")
            + self._term(lat.cl_r, r_hat, "cl_r")
            + self._term(lat.cl_da, aileron, "cl_da")
            + self._term(lat.cl_dr, rudder, "cl_dr")
        )
        c_yaw = (
            self._term(lat.cn_beta, beta, "cn_beta")
            + self._term(lat.cn_p, p_hat, "cn_p")
            + self._term(lat.cn_r, r_hat, "cn_r")
            + self._term(lat.cn_da, aileron, "cn_da")
            + self._term(lat.cn_dr, rudder, "cn_dr")
        )
        return AeroCoefficients(
            c_lift=c_lift,
            c_drag=c_drag,
            c_pitch=c_pitch,
            c_side=c_side,
            c_roll=c_roll,
            c_yaw=c_yaw,
        )

    def derivatives(self, state: AeroState) -> DerivativeBundle:
        return DerivativeBundle(
            longitudinal=self.longitudinal,
            lateral_directional=self.lateral_directional,
            valid=True,
            notes=(f"linear model {self.model_id}",),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "modelId": self.model_id,
            "reference": self.reference_geometry.as_dict(),
            "inducedDragFactor": self.induced_drag_factor,
        }


def analytic_lift_curve_slope(aspect_ratio: float, *, efficiency: float = 1.0) -> float:
    """Finite-wing lift-curve slope ``2 pi AR / (AR + 2)`` in per radian."""

    if aspect_ratio <= 0.0:
        raise ValueError("NONPOSITIVE_ASPECT_RATIO")
    if not 0.0 < efficiency <= 1.0:
        raise ValueError("EFFICIENCY_OUT_OF_RANGE")
    return 2.0 * pi * aspect_ratio / (aspect_ratio + 2.0) * efficiency


__all__ = ["LinearAeroModel", "analytic_lift_curve_slope"]
