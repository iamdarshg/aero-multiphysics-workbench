"""Screening limits and stability indicators for preliminary design.

Every indicator is a named comparison against a declared limit. The indicators
are cheap rejection tests that fire before any geometry or 3-D work: choking,
excessive incidence/deviation, excessive diffusion/loading, stall/surge
proximity, tip/relative Mach limits, excessive turning, clearance sensitivity,
and Reynolds/correlation validity.
"""

from __future__ import annotations

from dataclasses import dataclass

from .errors import MeanlineInputError


@dataclass(frozen=True, slots=True)
class LimitIndicator:
    """One named screening comparison."""

    name: str
    value: float
    limit: float
    unit: str
    passed: bool
    detail: str

    def canonical(self) -> dict[str, object]:
        return {
            "name": self.name,
            "value": self.value,
            "limit": self.limit,
            "unit": self.unit,
            "passed": self.passed,
            "detail": self.detail,
        }


@dataclass(frozen=True, slots=True)
class ScreeningLimits:
    """Declared, configurable preliminary-design limits (not solver output)."""

    max_relative_mach: float = 1.0
    max_diffusion_factor: float = 0.6
    min_de_haller: float = 0.35
    max_incidence_deg: float = 12.0
    max_turning_deg: float = 120.0
    max_loading_coefficient: float = 0.6
    min_reaction: float = 0.15
    max_clearance_loss_fraction: float = 0.35
    min_reynolds: float = 5.0e4
    max_exit_mach: float = 1.2

    def __post_init__(self) -> None:
        for label, value in (
            ("max_relative_mach", self.max_relative_mach),
            ("max_diffusion_factor", self.max_diffusion_factor),
            ("max_incidence_deg", self.max_incidence_deg),
            ("max_turning_deg", self.max_turning_deg),
            ("max_loading_coefficient", self.max_loading_coefficient),
            ("max_clearance_loss_fraction", self.max_clearance_loss_fraction),
            ("max_exit_mach", self.max_exit_mach),
        ):
            if not value > 0.0:
                raise MeanlineInputError(f"SCREENING_LIMIT_NOT_POSITIVE:{label}")
        if not 0.0 <= self.min_reaction < 1.0:
            raise MeanlineInputError("SCREENING_MIN_REACTION_OUT_OF_RANGE")
        if not 0.0 < self.min_de_haller <= 1.0:
            raise MeanlineInputError("SCREENING_MIN_DE_HALLER_OUT_OF_RANGE")
        if self.min_reynolds < 0.0:
            raise MeanlineInputError("SCREENING_MIN_REYNOLDS_NEGATIVE")

    def canonical(self) -> dict[str, object]:
        return {
            "maxRelativeMach": self.max_relative_mach,
            "maxDiffusionFactor": self.max_diffusion_factor,
            "minDeHaller": self.min_de_haller,
            "maxIncidenceDeg": self.max_incidence_deg,
            "maxTurningDeg": self.max_turning_deg,
            "maxLoadingCoefficient": self.max_loading_coefficient,
            "minReaction": self.min_reaction,
            "maxClearanceLossFraction": self.max_clearance_loss_fraction,
            "minReynolds": self.min_reynolds,
            "maxExitMach": self.max_exit_mach,
        }


def _indicator(
    name: str, value: float, limit: float, unit: str, passed: bool, detail: str
) -> LimitIndicator:
    return LimitIndicator(
        name=name, value=value, limit=limit, unit=unit, passed=passed, detail=detail
    )


def screen_row(
    *,
    relative_mach_in: float,
    relative_mach_out: float,
    exit_mach: float,
    diffusion_factor: float,
    de_haller: float,
    uses_lieblein: bool,
    incidence_deg: float,
    turning_deg: float,
    loading_coefficient: float,
    reaction: float,
    clearance_loss_fraction: float,
    reynolds_number: float,
    role: str,
    limits: ScreeningLimits | None = None,
) -> tuple[LimitIndicator, ...]:
    """Evaluate every declared screening indicator for one row."""

    active = limits or ScreeningLimits()
    indicators: list[LimitIndicator] = [
        _indicator(
            "relative_mach_in",
            relative_mach_in,
            active.max_relative_mach,
            "dimensionless",
            relative_mach_in <= active.max_relative_mach,
            "inlet relative Mach number below the declared limit",
        ),
        _indicator(
            "choking",
            relative_mach_out,
            active.max_relative_mach,
            "dimensionless",
            relative_mach_out <= active.max_relative_mach,
            "outlet relative Mach number (choking proxy) below the declared limit",
        ),
        _indicator(
            "incidence",
            abs(incidence_deg),
            active.max_incidence_deg,
            "deg",
            abs(incidence_deg) <= active.max_incidence_deg,
            "incidence magnitude below the excessive-incidence limit",
        ),
        _indicator(
            "turning",
            abs(turning_deg),
            active.max_turning_deg,
            "deg",
            abs(turning_deg) <= active.max_turning_deg,
            "flow turning magnitude below the excessive-turning limit",
        ),
        _indicator(
            "clearance_loss_fraction",
            clearance_loss_fraction,
            active.max_clearance_loss_fraction,
            "dimensionless",
            clearance_loss_fraction <= active.max_clearance_loss_fraction,
            "tip-clearance loss share below the clearance-sensitivity limit",
        ),
        _indicator(
            "reynolds",
            reynolds_number,
            active.min_reynolds,
            "dimensionless",
            reynolds_number >= active.min_reynolds,
            "blade-chord Reynolds number above the correlation-validity floor",
        ),
        _indicator(
            "exit_mach",
            exit_mach,
            active.max_exit_mach,
            "dimensionless",
            exit_mach <= active.max_exit_mach,
            "outlet absolute Mach number below the exit-Mach limit",
        ),
    ]
    if uses_lieblein:
        indicators.append(
            _indicator(
                "stall_surge_proxy",
                diffusion_factor,
                active.max_diffusion_factor,
                "dimensionless",
                diffusion_factor <= active.max_diffusion_factor,
                "Lieblein diffusion factor as a stall/surge proximity proxy",
            )
        )
    elif role in ("turning_only", "work_extracting", "work_adding"):
        indicators.append(
            _indicator(
                "de_haller",
                de_haller,
                active.min_de_haller,
                "dimensionless",
                de_haller >= active.min_de_haller,
                "de Haller ratio (W_out/W_in) above the diffusion floor",
            )
        )
    if role == "work_adding":
        indicators.append(
            _indicator(
                "loading_coefficient",
                loading_coefficient,
                active.max_loading_coefficient,
                "dimensionless",
                loading_coefficient <= active.max_loading_coefficient,
                "flow/loading coefficient below the loading limit",
            )
        )
        indicators.append(
            _indicator(
                "reaction",
                reaction,
                active.min_reaction,
                "dimensionless",
                reaction >= active.min_reaction,
                "degree of reaction above the minimum-reaction floor",
            )
        )
    return tuple(indicators)


__all__ = ["LimitIndicator", "ScreeningLimits", "screen_row"]
