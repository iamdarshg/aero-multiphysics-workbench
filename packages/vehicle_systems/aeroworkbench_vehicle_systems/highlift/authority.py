"""Control-authority screening at approach and stall conditions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aeroworkbench_core.types import ResultSource

from .contracts import HighLiftFidelity, ResultMeta, result_meta
from .errors import HighLiftError, finite
from .wing import FiniteWingResult

MODEL_AUTHORITY = "vehicle-systems.highlift.control-authority"

_ASSUMPTIONS = (
    "Linear control effectiveness evaluated at the approach dynamic pressure.",
    "Available moment is effectiveness times the declared deflection limit.",
    "High-lift pitching-moment increment is carried as the required trim moment.",
)


@dataclass(frozen=True, slots=True)
class AuthoritySurface:
    surface_id: str
    axis: str
    moment_per_rad_n_m: float
    deflection_limit_deg: float
    required_moment_n_m: float

    def __post_init__(self) -> None:
        if not self.surface_id.strip():
            raise HighLiftError("AUTHORITY_SURFACE_ID_REQUIRED")
        if self.axis not in ("pitch", "roll", "yaw"):
            raise HighLiftError(f"UNKNOWN_AUTHORITY_AXIS:{self.axis}")
        finite(self.moment_per_rad_n_m, "moment_per_rad_n_m")
        finite(self.deflection_limit_deg, "deflection_limit_deg", positive=True)
        finite(self.required_moment_n_m, "required_moment_n_m")

    @property
    def available_moment_n_m(self) -> float:
        from math import pi

        return abs(self.moment_per_rad_n_m) * self.deflection_limit_deg * pi / 180.0

    @property
    def ratio(self) -> float:
        available = self.available_moment_n_m
        if available <= 0.0:
            return float("inf")
        return abs(self.required_moment_n_m) / available

    def canonical(self) -> dict[str, Any]:
        return {
            "surfaceId": self.surface_id,
            "axis": self.axis,
            "momentPerRadNm": self.moment_per_rad_n_m,
            "deflectionLimitDeg": self.deflection_limit_deg,
            "requiredMomentNm": self.required_moment_n_m,
            "availableMomentNm": self.available_moment_n_m,
            "ratio": self.ratio,
        }


@dataclass(frozen=True, slots=True)
class ControlAuthorityVerdict:
    passed: bool
    condition: str
    surfaces: tuple[AuthoritySurface, ...]
    reasons: tuple[str, ...]
    meta: ResultMeta

    def canonical(self) -> dict[str, Any]:
        meta = self.meta
        return {
            "passed": self.passed,
            "condition": self.condition,
            "surfaces": [surface.canonical() for surface in self.surfaces],
            "reasons": list(self.reasons),
            "meta": meta.canonical(),
        }


def check_control_authority(
    wing: FiniteWingResult,
    surfaces: tuple[AuthoritySurface, ...],
    *,
    condition: str,
    dynamic_pressure_pa: float,
    area_m2: float,
    chord_m: float,
) -> ControlAuthorityVerdict:
    finite(dynamic_pressure_pa, "dynamic_pressure_pa", positive=True)
    finite(area_m2, "area_m2", positive=True)
    finite(chord_m, "chord_m", positive=True)
    if not condition.strip():
        raise HighLiftError("AUTHORITY_CONDITION_REQUIRED")
    if not surfaces:
        raise HighLiftError("AUTHORITY_REQUIRES_SURFACES")
    reasons: list[str] = []
    for surface in surfaces:
        if surface.ratio > 1.0:
            reasons.append(
                f"CONTROL_AUTHORITY_EXCEEDED:{surface.surface_id}:{surface.ratio:.3g}"
            )
    if wing.regime in ("poststall", "deepstall"):
        reasons.append(f"AUTHORITY_ASSESSED_POST_STALL:{wing.regime}")
    passed = not reasons
    meta: ResultMeta = result_meta(
        model=MODEL_AUTHORITY,
        inputs={
            "wing": wing.canonical(),
            "surfaces": [surface.canonical() for surface in surfaces],
            "condition": condition,
            "dynamicPressurePa": dynamic_pressure_pa,
            "areaM2": area_m2,
            "chordM": chord_m,
        },
        valid=passed,
        fidelity=HighLiftFidelity.FINITE_WING_NONLINEAR,
        checks={"within_authority": passed},
        detail="authority held" if passed else ";".join(reasons),
        assumptions=_ASSUMPTIONS,
        source=ResultSource.ANALYTICAL,
    )
    return ControlAuthorityVerdict(
        passed=passed,
        condition=condition,
        surfaces=surfaces,
        reasons=tuple(reasons),
        meta=meta,
    )


__all__ = [
    "MODEL_AUTHORITY",
    "AuthoritySurface",
    "ControlAuthorityVerdict",
    "check_control_authority",
]
