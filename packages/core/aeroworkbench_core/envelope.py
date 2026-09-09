from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from .models.common import analytical_provenance
from .types import Provenance


class EnvelopeStatus(StrEnum):
    VIABLE = "viable"
    CONSTRAINED = "constrained"
    FAILED = "failed"


class AircraftDefinition(BaseModel):
    mass_kg: float = Field(gt=0)
    wing_area_m2: float = Field(gt=0)
    cd0: float = Field(gt=0)
    induced_drag_factor: float = Field(gt=0)
    available_thrust_n: float = Field(gt=0)


class EnvelopeLimits(BaseModel):
    max_current_a: float = Field(gt=0)
    max_temperature_k: float = Field(gt=0)
    max_load_factor: float = Field(gt=0)


class EnvelopePoint(BaseModel):
    airspeed_m_s: float = Field(gt=0)
    density_kg_m3: float = Field(gt=0)
    load_factor: float = Field(gt=0)
    current_a: float = Field(ge=0)
    temperature_k: float = Field(gt=0)


class EvaluatedEnvelopePoint(EnvelopePoint):
    required_thrust_n: float
    status: EnvelopeStatus
    violations: tuple[str, ...]


class EnvelopeResult(BaseModel):
    points: list[EvaluatedEnvelopePoint]
    provenance: Provenance


def evaluate_operating_envelope(
    aircraft: AircraftDefinition, limits: EnvelopeLimits, points: list[EnvelopePoint]
) -> EnvelopeResult:
    evaluated: list[EvaluatedEnvelopePoint] = []
    for point in points:
        dynamic_pressure = 0.5 * point.density_kg_m3 * point.airspeed_m_s**2
        lift_coefficient = (
            aircraft.mass_kg * 9.81 * point.load_factor / (dynamic_pressure * aircraft.wing_area_m2)
        )
        drag = (
            dynamic_pressure
            * aircraft.wing_area_m2
            * (aircraft.cd0 + aircraft.induced_drag_factor * lift_coefficient**2)
        )
        violations: list[str] = []
        if point.load_factor > limits.max_load_factor:
            violations.append("load_factor")
        if point.current_a > limits.max_current_a:
            violations.append("motor_current")
        if point.temperature_k > limits.max_temperature_k:
            violations.append("temperature")
        if drag > aircraft.available_thrust_n:
            violations.append("insufficient_thrust")
        near_limit = (
            point.load_factor >= 0.9 * limits.max_load_factor
            or point.current_a >= 0.9 * limits.max_current_a
            or point.temperature_k >= 0.98 * limits.max_temperature_k
            or drag >= 0.9 * aircraft.available_thrust_n
        )
        status = (
            EnvelopeStatus.FAILED
            if violations
            else (EnvelopeStatus.CONSTRAINED if near_limit else EnvelopeStatus.VIABLE)
        )
        evaluated.append(
            EvaluatedEnvelopePoint(
                **point.model_dump(),
                required_thrust_n=drag,
                status=status,
                violations=tuple(violations),
            )
        )
    return EnvelopeResult(
        points=evaluated,
        provenance=analytical_provenance(
            "aircraft-operating-envelope",
            {
                "aircraft": aircraft.model_dump(),
                "limits": limits.model_dump(),
                "points": [point.model_dump() for point in points],
            },
            "steady point drag from parabolic polar",
            "envelope status reflects only declared thrust, current, temperature, and load limits",
        ),
    )
