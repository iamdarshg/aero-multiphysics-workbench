"""Ground-effect aerodynamic correction and its native-capability seam.

Near the ground the induced drag of a lifting surface is reduced. The correction
is a declared closed-form function of height-to-span ratio; it never claims a
full CFD solution. When a native ground-effect solve is requested, the seam is
capability-gated and fails closed if the backend is absent.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import pi
from typing import Any

from .contracts import (
    LandingGearFidelity,
    ResultMeta,
    result_meta,
)
from .errors import CapabilityUnavailable, finite

_NATIVE_REQUIREMENT = "ground-effect-cfd"


def ground_effect_factor(height_m: float, span_m: float) -> float:
    """Multiplier on induced drag at a height (0 at the ground, ->1 far away)."""

    height = finite(height_m, "height_m", minimum=0.0)
    span = finite(span_m, "span_m", positive=True)
    ratio = 16.0 * height / span
    return ratio * ratio / (1.0 + ratio * ratio)


@dataclass(frozen=True, slots=True)
class GroundEffectResult:
    """Ground-effect-corrected drag polar at one height."""

    height_m: float
    span_m: float
    factor: float
    cd0: float
    cl: float
    cd_free_air: float
    cd_ground_effect: float
    meta: ResultMeta

    def units(self) -> dict[str, str]:
        return {"height_m": "m", "span_m": "m", "dimensionless": "1"}

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "heightM": self.height_m,
            "spanM": self.span_m,
            "factor": self.factor,
            "cd0": self.cd0,
            "cl": self.cl,
            "cdFreeAir": self.cd_free_air,
            "cdGroundEffect": self.cd_ground_effect,
            "meta": self.meta.canonical(),
        }


def apply_ground_effect(
    *,
    cd0: float,
    cl: float,
    aspect_ratio: float,
    height_m: float,
    span_m: float,
    oswald_efficiency: float = 0.8,
    model: str = "ground-effect.lifting-line-image",
) -> GroundEffectResult:
    """Apply the induced-drag ground correction to a declared drag polar."""

    zero_lift = finite(cd0, "cd0", minimum=0.0)
    lift_coefficient = finite(cl, "cl")
    aspect = finite(aspect_ratio, "aspect_ratio", positive=True)
    efficiency = finite(oswald_efficiency, "oswald_efficiency", positive=True)
    factor = ground_effect_factor(height_m, span_m)
    induced = lift_coefficient * lift_coefficient / (pi * aspect * efficiency)
    cd_free_air = zero_lift + induced
    cd_ground = zero_lift + factor * induced
    meta = result_meta(
        model=f"vehicle-systems.landing-gear.{model}",
        inputs={
            "cd0": zero_lift,
            "cl": lift_coefficient,
            "aspectRatio": aspect,
            "heightM": height_m,
            "spanM": span_m,
            "oswaldEfficiency": efficiency,
        },
        valid=True,
        checks={
            "height_non_negative": height_m >= 0.0,
            "induced_reduced": cd_ground <= cd_free_air,
        },
        detail="closed-form induced-drag ground correction",
        fidelity=LandingGearFidelity.ANALYTICAL,
        assumptions=("image-system induced-drag correction; not a CFD solve",),
    )
    return GroundEffectResult(
        height_m=height_m,
        span_m=span_m,
        factor=factor,
        cd0=zero_lift,
        cl=lift_coefficient,
        cd_free_air=cd_free_air,
        cd_ground_effect=cd_ground,
        meta=meta,
    )


@dataclass(frozen=True, slots=True)
class NativeGroundEffectStatus:
    """Whether a native ground-effect CFD backend is wired."""

    available: bool
    backend: str | None
    requirement: str
    meta: ResultMeta


def native_ground_effect_status(
    *, present: bool = False, backend: str | None = None
) -> NativeGroundEffectStatus:
    meta = result_meta(
        model="vehicle-systems.landing-gear.ground-effect-native-status",
        inputs={"present": present, "backend": backend},
        valid=present,
        detail="native ground-effect capability probe",
        fidelity=LandingGearFidelity.NATIVE if present else LandingGearFidelity.ANALYTICAL,
        checks={"native_backend_available": present},
    )
    return NativeGroundEffectStatus(
        available=present, backend=backend, requirement=_NATIVE_REQUIREMENT, meta=meta
    )


def require_native_ground_effect(*, present: bool = False) -> None:
    """A native ground-effect solve requires the backend; else fail closed."""

    if not present:
        raise CapabilityUnavailable(
            f"{_NATIVE_REQUIREMENT} is not available; native ground effect cannot be claimed"
        )


__all__ = [
    "GroundEffectResult",
    "NativeGroundEffectStatus",
    "apply_ground_effect",
    "ground_effect_factor",
    "native_ground_effect_status",
    "require_native_ground_effect",
]
