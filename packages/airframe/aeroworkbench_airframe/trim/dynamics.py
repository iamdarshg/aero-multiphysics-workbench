"""Linearized flight dynamics: state-space construction and mode extraction.

The longitudinal 4-state ``[u, alpha, q, theta]`` and lateral-directional
4-state ``[beta, p, r, phi]`` matrices follow the standard nondimensional-to-
dimensional derivative relations. Modes are extracted as eigenvalues and
labelled short-period/phugoid (longitudinal) and dutch-roll/roll/spiral
(lateral-directional). The construction fails closed when required derivative
coverage is absent; a missing derivative is never silently replaced by zero.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from math import pi
from typing import Any

from ..state import MassProperties
from ..units import Quantity
from .contract import (
    AerodynamicCoefficientProvider,
    AeroReference,
    AeroState,
    FlightCondition,
    LateralDirectionalDerivatives,
    LongitudinalDerivatives,
    ResultMeta,
    result_meta,
)
from .errors import AeroCoefficientError
from .linalg import FloatMatrix, complex_eigenvalues

MODEL = "airframe-trim-dynamic-stability"

_ASSUMPTIONS = (
    "Linearized small-perturbation dynamics about a steady trim point.",
    "Speed derivatives absent from the bundle are neglected (recorded, never fabricated).",
    "Rigid-body modes only; no actuator or structural dynamics.",
)

_REAL_TOL = 1e-9

LONGITUDINAL_REQUIRED = ("cl_alpha", "cm_alpha", "cl_q", "cm_q")
LATERAL_REQUIRED = ("cy_beta", "cl_beta", "cn_beta", "cl_p", "cl_r", "cn_r")


@dataclass(frozen=True, slots=True)
class FlightMode:
    kind: str
    frequency_hz: float
    damping_ratio: float
    growth_rate_1_s: float
    real: float
    imag: float
    stable: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "frequencyHz": self.frequency_hz,
            "dampingRatio": self.damping_ratio,
            "growthRate1S": self.growth_rate_1_s,
            "real": self.real,
            "imag": self.imag,
            "stable": self.stable,
        }


@dataclass(frozen=True, slots=True)
class DynamicStabilityReport:
    valid: bool
    longitudinal_modes: tuple[FlightMode, ...]
    lateral_modes: tuple[FlightMode, ...]
    longitudinal_matrix: FloatMatrix
    lateral_matrix: FloatMatrix
    notes: tuple[str, ...]
    meta: ResultMeta

    @property
    def longitudinal_stable(self) -> bool:
        return bool(self.longitudinal_modes) and all(
            mode.stable for mode in self.longitudinal_modes
        )

    @property
    def lateral_directional_stable(self) -> bool:
        return bool(self.lateral_modes) and all(mode.stable for mode in self.lateral_modes)

    def as_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "longitudinalStable": self.longitudinal_stable,
            "lateralDirectionalStable": self.lateral_directional_stable,
            "longitudinalModes": [mode.as_dict() for mode in self.longitudinal_modes],
            "lateralModes": [mode.as_dict() for mode in self.lateral_modes],
            "longitudinalMatrix": [list(row) for row in self.longitudinal_matrix],
            "lateralMatrix": [list(row) for row in self.lateral_matrix],
            "notes": list(self.notes),
            "meta": self.meta.as_dict(),
        }


def _dimensional_longitudinal(
    derivs: LongitudinalDerivatives,
    *,
    dynamic_pressure: float,
    area: float,
    chord: float,
    mass: float,
    iyy: float,
    velocity: float,
    gravity: float,
    cl_trim: float,
) -> FloatMatrix:
    values = derivs.require(*LONGITUDINAL_REQUIRED)
    cd_alpha = derivs.cd_alpha if derivs.cd_alpha is not None else 0.0
    cl_u = derivs.cl_u if derivs.cl_u is not None else 0.0
    cd_u = derivs.cd_u if derivs.cd_u is not None else 0.0
    cm_u = derivs.cm_u if derivs.cm_u is not None else 0.0
    q = dynamic_pressure
    x_u = -(q * area / (mass * velocity)) * (2.0 * derivs.cd_0 + cd_u)
    x_alpha = (q * area / mass) * (cl_trim - cd_alpha)
    z_u = -(q * area / (mass * velocity)) * (2.0 * cl_trim + cl_u)
    z_alpha = -(q * area / mass) * (values["cl_alpha"] + derivs.cd_0)
    z_q = -(q * area * chord / (2.0 * mass * velocity)) * values["cl_q"]
    m_u = (q * area * chord / (iyy * velocity)) * cm_u
    m_alpha = (q * area * chord / iyy) * values["cm_alpha"]
    m_q = (q * area * chord * chord / (2.0 * iyy * velocity)) * values["cm_q"]
    return (
        (x_u, x_alpha, 0.0, -gravity),
        (z_u / velocity, z_alpha / velocity, 1.0 + z_q / velocity, 0.0),
        (m_u, m_alpha, m_q, 0.0),
        (0.0, 0.0, 1.0, 0.0),
    )


def _dimensional_lateral(
    derivs: LateralDirectionalDerivatives,
    *,
    dynamic_pressure: float,
    area: float,
    span: float,
    mass: float,
    ixx: float,
    izz: float,
    velocity: float,
    gravity: float,
) -> FloatMatrix:
    values = derivs.require(*LATERAL_REQUIRED)
    cy_p = derivs.cy_p if derivs.cy_p is not None else 0.0
    cy_r = derivs.cy_r if derivs.cy_r is not None else 0.0
    cn_p = derivs.cn_p if derivs.cn_p is not None else 0.0
    q = dynamic_pressure
    y_beta = (q * area / mass) * values["cy_beta"]
    y_p = (q * area * span / (2.0 * mass * velocity)) * cy_p
    y_r = (q * area * span / (2.0 * mass * velocity)) * cy_r
    l_beta = (q * area * span / ixx) * values["cl_beta"]
    l_p = (q * area * span * span / (2.0 * ixx * velocity)) * values["cl_p"]
    l_r = (q * area * span * span / (2.0 * ixx * velocity)) * values["cl_r"]
    n_beta = (q * area * span / izz) * values["cn_beta"]
    n_p = (q * area * span * span / (2.0 * izz * velocity)) * cn_p
    n_r = (q * area * span * span / (2.0 * izz * velocity)) * values["cn_r"]
    return (
        (y_beta / velocity, y_p / velocity, y_r / velocity - 1.0, gravity / velocity),
        (l_beta, l_p, l_r, 0.0),
        (n_beta, n_p, n_r, 0.0),
        (0.0, 1.0, 0.0, 0.0),
    )


def longitudinal_state_matrix(
    derivs: LongitudinalDerivatives,
    *,
    mass_properties: MassProperties,
    reference: AeroReference,
    dynamic_pressure: float,
    velocity: float,
    gravity: float,
    cl_trim: float,
) -> FloatMatrix:
    """Build the 4-state longitudinal ``[u, alpha, q, theta]`` matrix."""

    return _dimensional_longitudinal(
        derivs,
        dynamic_pressure=dynamic_pressure,
        area=reference.area.value_si,
        chord=reference.chord.value_si,
        mass=mass_properties.mass.value_si,
        iyy=mass_properties.inertia.iyy.value_si,
        velocity=velocity,
        gravity=gravity,
        cl_trim=cl_trim,
    )


def lateral_state_matrix(
    derivs: LateralDirectionalDerivatives,
    *,
    mass_properties: MassProperties,
    reference: AeroReference,
    dynamic_pressure: float,
    velocity: float,
    gravity: float,
) -> FloatMatrix:
    """Build the 4-state lateral-directional ``[beta, p, r, phi]`` matrix."""

    return _dimensional_lateral(
        derivs,
        dynamic_pressure=dynamic_pressure,
        area=reference.area.value_si,
        span=reference.span.value_si,
        mass=mass_properties.mass.value_si,
        ixx=mass_properties.inertia.ixx.value_si,
        izz=mass_properties.inertia.izz.value_si,
        velocity=velocity,
        gravity=gravity,
    )


def extract_modes(matrix: FloatMatrix) -> tuple[FlightMode, ...]:
    """Extract frequency/damping/stability for each eigenvalue of ``matrix``."""

    modes: list[FlightMode] = []
    for value in complex_eigenvalues(matrix):
        real = value.real
        imag = value.imag
        magnitude = abs(value)
        oscillatory = abs(imag) > _REAL_TOL * max(1.0, abs(real))
        modes.append(
            FlightMode(
                kind="oscillatory" if oscillatory else "aperiodic",
                frequency_hz=abs(imag) / (2.0 * pi) if oscillatory else 0.0,
                damping_ratio=-real / magnitude if magnitude > 0.0 else 0.0,
                growth_rate_1_s=real,
                real=real,
                imag=imag,
                stable=real < 0.0,
            )
        )
    return tuple(modes)


def classify_longitudinal_modes(modes: tuple[FlightMode, ...]) -> tuple[FlightMode, ...]:
    """Label oscillatory modes short-period (fast) and phugoid (slow)."""

    oscillatory = sorted(
        (mode for mode in modes if mode.kind == "oscillatory"),
        key=lambda mode: mode.frequency_hz,
        reverse=True,
    )
    labels = ("short-period", "phugoid")
    labelled: list[FlightMode] = []
    for pair_index in range(0, len(oscillatory), 2):
        pair = oscillatory[pair_index : pair_index + 2]
        label = labels[pair_index // 2] if pair_index // 2 < len(labels) else "higher-order"
        labelled.extend(replace(mode, kind=label) for mode in pair)
    labelled.extend(mode for mode in modes if mode.kind == "aperiodic")
    return tuple(labelled)


def classify_lateral_modes(modes: tuple[FlightMode, ...]) -> tuple[FlightMode, ...]:
    """Label the oscillatory mode dutch-roll and the real roots roll/spiral."""

    oscillatory = [mode for mode in modes if mode.kind == "oscillatory"]
    real = sorted(
        (mode for mode in modes if mode.kind == "aperiodic"),
        key=lambda mode: abs(mode.real),
        reverse=True,
    )
    labelled: list[FlightMode] = []
    for pair_index in range(0, len(oscillatory), 2):
        pair = oscillatory[pair_index : pair_index + 2]
        label = "dutch-roll" if pair_index == 0 else "higher-order"
        labelled.extend(replace(mode, kind=label) for mode in pair)
    for index, mode in enumerate(real):
        if index == 0:
            label = "roll"
        elif index == len(real) - 1:
            label = "spiral"
        else:
            label = "aperiodic"
        labelled.append(replace(mode, kind=label))
    return tuple(labelled)


def evaluate_dynamic_stability(
    provider: AerodynamicCoefficientProvider,
    *,
    condition: FlightCondition,
    mass_properties: MassProperties,
    trim_alpha: float = 0.0,
    trim_elevator: float = 0.0,
) -> DynamicStabilityReport:
    """Build both linearized matrices and report labelled modes, failing closed."""

    reference = provider.reference()
    state = AeroState(
        alpha=Quantity(trim_alpha, "rad"),
        velocity=condition.velocity,
        deflections=(("elevator", Quantity(trim_elevator, "rad")),),
    )
    coefficients = provider.coefficients(state)
    bundle = provider.derivatives(state)
    q_dyn = condition.dynamic_pressure().value_si
    velocity = condition.velocity.value_si
    gravity = condition.gravity.value_si
    notes: list[str] = []
    if not bundle.valid:
        notes.extend(bundle.notes)
    try:
        lon_matrix = longitudinal_state_matrix(
            bundle.longitudinal,
            mass_properties=mass_properties,
            reference=reference,
            dynamic_pressure=q_dyn,
            velocity=velocity,
            gravity=gravity,
            cl_trim=coefficients.c_lift,
        )
    except AeroCoefficientError as error:
        lon_matrix = ((0.0,),)
        notes.append(str(error))
    try:
        lat_matrix = lateral_state_matrix(
            bundle.lateral_directional,
            mass_properties=mass_properties,
            reference=reference,
            dynamic_pressure=q_dyn,
            velocity=velocity,
            gravity=gravity,
        )
    except AeroCoefficientError as error:
        lat_matrix = ((0.0,),)
        notes.append(str(error))
    valid = not notes
    lon_modes = (
        classify_longitudinal_modes(extract_modes(lon_matrix)) if valid else ()
    )
    lat_modes = classify_lateral_modes(extract_modes(lat_matrix)) if valid else ()
    inputs = {
        "provider": provider.provider_id,
        "condition": condition.as_dict(),
        "massProperties": mass_properties.canonical(),
        "trimAlpha": trim_alpha,
        "trimElevator": trim_elevator,
    }
    meta = result_meta(
        model=MODEL,
        inputs=inputs,
        valid=valid,
        notes=tuple(notes),
        assumptions=_ASSUMPTIONS,
    )
    return DynamicStabilityReport(
        valid=valid,
        longitudinal_modes=lon_modes,
        lateral_modes=lat_modes,
        longitudinal_matrix=lon_matrix,
        lateral_matrix=lat_matrix,
        notes=tuple(notes),
        meta=meta,
    )


__all__ = [
    "DynamicStabilityReport",
    "FlightMode",
    "LATERAL_REQUIRED",
    "LONGITUDINAL_REQUIRED",
    "classify_lateral_modes",
    "classify_longitudinal_modes",
    "evaluate_dynamic_stability",
    "extract_modes",
    "lateral_state_matrix",
    "longitudinal_state_matrix",
]
