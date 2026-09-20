"""Control-authority screening: available versus required control moments.

Each control surface contributes a moment per radian of deflection at the
dynamic pressure of the trim state. Its available authority is that
effectiveness times the declared deflection limit; the required authority is
the moment the trim point actually needs. An over-subscribed surface is reported
as an explicit constraint violation, never hidden.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..units import Quantity
from .contract import (
    AerodynamicCoefficientProvider,
    AeroReference,
    AeroState,
    ResultMeta,
    result_meta,
)
from .errors import AeroCoefficientError

MODEL = "airframe-trim-control-authority"

_ASSUMPTIONS = (
    "Linear control effectiveness at the trim dynamic pressure, normalized per radian.",
    "Authority is the effectiveness times the declared mechanical deflection limit.",
    "A required moment exceeding available authority is an infeasible constraint.",
)

AXES = ("pitch", "roll", "yaw")


@dataclass(frozen=True, slots=True)
class ControlSurfaceAuthority:
    surface: str
    axis: str
    deflection_limit: Quantity
    moment_per_rad: Quantity
    required_moment: Quantity
    ratio: float
    within_authority: bool

    @property
    def available_moment(self) -> Quantity:
        return Quantity(abs(self.moment_per_rad.value_si * self.deflection_limit.value_si), "N.m")

    def as_dict(self) -> dict[str, Any]:
        available = self.available_moment
        return {
            "surface": self.surface,
            "axis": self.axis,
            "deflectionLimit": self.deflection_limit.canonical(),
            "momentPerRad": self.moment_per_rad.canonical(),
            "requiredMoment": self.required_moment.canonical(),
            "availableMoment": available.canonical(),
            "ratio": self.ratio,
            "withinAuthority": self.within_authority,
        }


@dataclass(frozen=True, slots=True)
class ControlAuthorityReport:
    surfaces: tuple[ControlSurfaceAuthority, ...]
    within_authority: bool
    meta: ResultMeta

    @property
    def reasons(self) -> tuple[str, ...]:
        return tuple(
            f"CONTROL_AUTHORITY_EXCEEDED:{item.surface}"
            for item in self.surfaces
            if not item.within_authority
        )

    def surface(self, name: str) -> ControlSurfaceAuthority:
        for item in self.surfaces:
            if item.surface == name:
                return item
        raise KeyError(f"UNKNOWN_CONTROL_SURFACE:{name}")

    def as_dict(self) -> dict[str, Any]:
        return {
            "surfaces": [item.as_dict() for item in self.surfaces],
            "withinAuthority": self.within_authority,
            "reasons": list(self.reasons),
            "meta": self.meta.as_dict(),
        }


def _moment_per_rad(
    derivative: float | None,
    *,
    scale: float,
    name: str,
) -> Quantity:
    if derivative is None:
        raise AeroCoefficientError(f"MISSING_DERIVATIVE:{name}")
    return Quantity(scale * derivative, "N.m")


def evaluate_control_authority(
    provider: AerodynamicCoefficientProvider,
    state: AeroState,
    *,
    reference: AeroReference,
    dynamic_pressure: float,
    required_pitch_moment: float = 0.0,
    required_roll_moment: float = 0.0,
    required_yaw_moment: float = 0.0,
    elevator_limit: Quantity | None = None,
    aileron_limit: Quantity | None = None,
    rudder_limit: Quantity | None = None,
) -> ControlAuthorityReport:
    """Evaluate pitch/roll/yaw control authority at one state, failing closed."""

    bundle = provider.derivatives(state)
    lon = bundle.longitudinal
    lat = bundle.lateral_directional
    area = reference.area.value_si
    chord = reference.chord.value_si
    span = reference.span.value_si
    pitch_scale = dynamic_pressure * area * chord
    lateral_scale = dynamic_pressure * area * span

    requested: list[
        tuple[str, str, float | None, Quantity | None, float, float]
    ] = [
        ("elevator", "pitch", lon.cm_de, elevator_limit, pitch_scale, required_pitch_moment),
        ("aileron", "roll", lat.cl_da, aileron_limit, lateral_scale, required_roll_moment),
        ("rudder", "yaw", lat.cn_dr, rudder_limit, lateral_scale, required_yaw_moment),
    ]
    surfaces: list[ControlSurfaceAuthority] = []
    for name, axis, derivative, limit, scale, required in requested:
        if limit is None:
            continue
        if limit.value_si <= 0:
            raise ValueError(f"NONPOSITIVE_CONTROL_LIMIT:{name}")
        if limit.dimension != "angle":
            raise ValueError(f"CONTROL_LIMIT_NOT_ANGLE:{name}")
        moment_per_rad = _moment_per_rad(derivative, scale=scale, name=name)
        available = abs(moment_per_rad.value_si * limit.value_si)
        magnitude = abs(required)
        ratio = magnitude / available if available > 0.0 else float("inf")
        surfaces.append(
            ControlSurfaceAuthority(
                surface=name,
                axis=axis,
                deflection_limit=limit,
                moment_per_rad=moment_per_rad,
                required_moment=Quantity(required, "N.m"),
                ratio=ratio,
                within_authority=ratio <= 1.0,
            )
        )
    if not surfaces:
        raise ValueError("CONTROL_AUTHORITY_NEEDS_AT_LEAST_ONE_LIMIT")
    within = all(item.within_authority for item in surfaces)
    inputs = {
        "state": {
            "alpha": state.alpha.canonical(),
            "beta": state.beta.canonical(),
            "velocity": state.velocity.canonical(),
            "deflections": {
                name: quantity.canonical() for name, quantity in state.deflections
            },
        },
        "reference": reference.as_dict(),
        "dynamicPressure": dynamic_pressure,
        "surfaces": [item.as_dict() for item in surfaces],
    }
    meta = result_meta(
        model=MODEL,
        inputs=inputs,
        valid=within,
        notes=tuple(
            f"CONTROL_AUTHORITY_EXCEEDED:{item.surface}"
            for item in surfaces
            if not item.within_authority
        ),
        assumptions=_ASSUMPTIONS,
    )
    return ControlAuthorityReport(surfaces=tuple(surfaces), within_authority=within, meta=meta)


__all__ = [
    "AXES",
    "ControlAuthorityReport",
    "ControlSurfaceAuthority",
    "evaluate_control_authority",
]
