"""Mission closure: mass, fuel, energy, distance, and segment continuity.

A completed mission must conserve what it claims to conserve. The mass balance
compares initial minus final mass against fuel burned plus jettisoned mass; the
fuel balance compares fuel consumed against the integrated fuel flow; the energy
balance compares the drop in stored energy against the integrated stored-energy
consumption; distance and segment-boundary continuity are checked against their
tolerances. A failed balance fails closed.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any

from .errors import ClosureError
from .segments import ClosureTolerances, MissionSpec

__all__ = ["ClosureReport", "ClosureResidual", "MissionBalance", "evaluate_closure"]

_ABS_FLOOR = 1e-9


@dataclass(frozen=True, slots=True)
class MissionBalance:
    """The aggregated scalars a closure check compares."""

    initial_mass_kg: float
    final_mass_kg: float
    fuel_burned_kg: float
    jettisoned_kg: float
    initial_fuel_kg: float
    final_fuel_kg: float
    initial_energy_j: float
    final_energy_j: float
    stored_energy_consumed_j: float
    mission_distance_m: float
    segment_distance_sum_m: float
    max_boundary_discontinuity: float

    def __post_init__(self) -> None:
        for name, value in (
            ("initial_mass_kg", self.initial_mass_kg),
            ("final_mass_kg", self.final_mass_kg),
            ("fuel_burned_kg", self.fuel_burned_kg),
            ("jettisoned_kg", self.jettisoned_kg),
            ("initial_fuel_kg", self.initial_fuel_kg),
            ("final_fuel_kg", self.final_fuel_kg),
            ("initial_energy_j", self.initial_energy_j),
            ("final_energy_j", self.final_energy_j),
            ("stored_energy_consumed_j", self.stored_energy_consumed_j),
            ("mission_distance_m", self.mission_distance_m),
            ("segment_distance_sum_m", self.segment_distance_sum_m),
            ("max_boundary_discontinuity", self.max_boundary_discontinuity),
        ):
            if not isfinite(value):
                raise ClosureError(f"NONFINITE_BALANCE:{name}")


@dataclass(frozen=True, slots=True)
class ClosureResidual:
    """One closure dimension's residual and verdict."""

    dimension: str
    residual: float
    tolerance: float
    passed: bool
    detail: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "dimension": self.dimension,
            "residual": self.residual,
            "tolerance": self.tolerance,
            "passed": self.passed,
            "detail": self.detail,
        }


@dataclass(frozen=True, slots=True)
class ClosureReport:
    """The full closure verdict for one mission."""

    residuals: tuple[ClosureResidual, ...]

    @property
    def passed(self) -> bool:
        return all(item.passed for item in self.residuals)

    def residual_for(self, dimension: str) -> ClosureResidual:
        for item in self.residuals:
            if item.dimension == dimension:
                return item
        raise ClosureError(f"UNKNOWN_CLOSURE_DIMENSION:{dimension}")

    def as_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "residuals": {item.dimension: item.as_dict() for item in self.residuals},
        }


def _tol(relative: float, scale: float) -> float:
    return max(relative * abs(scale), _ABS_FLOOR)


def evaluate_closure(
    spec: MissionSpec,
    balance: MissionBalance,
    *,
    tolerances: ClosureTolerances | None = None,
) -> ClosureReport:
    """Compute every closure residual and fail closed if any exceeds its tolerance."""

    tol = spec.closure if tolerances is None else tolerances
    mass_residual = (balance.initial_mass_kg - balance.final_mass_kg) - (
        balance.fuel_burned_kg + balance.jettisoned_kg
    )
    fuel_residual = (balance.initial_fuel_kg - balance.final_fuel_kg) - balance.fuel_burned_kg
    energy_residual = (balance.initial_energy_j - balance.final_energy_j) - (
        balance.stored_energy_consumed_j
    )
    distance_residual = balance.mission_distance_m - balance.segment_distance_sum_m
    residuals = (
        ClosureResidual(
            "mass",
            mass_residual,
            _tol(tol.mass_rel, balance.initial_mass_kg),
            abs(mass_residual) <= _tol(tol.mass_rel, balance.initial_mass_kg),
            "initial-final mass vs fuel burned plus jettisoned",
        ),
        ClosureResidual(
            "fuel",
            fuel_residual,
            _tol(tol.fuel_rel, balance.initial_fuel_kg),
            abs(fuel_residual) <= _tol(tol.fuel_rel, balance.initial_fuel_kg),
            "initial-final fuel vs integrated fuel flow",
        ),
        ClosureResidual(
            "energy",
            energy_residual,
            _tol(tol.energy_rel, balance.initial_energy_j),
            abs(energy_residual) <= _tol(tol.energy_rel, balance.initial_energy_j),
            "stored-energy drop vs integrated consumption",
        ),
        ClosureResidual(
            "distance",
            distance_residual,
            _tol(tol.distance_rel, balance.mission_distance_m),
            abs(distance_residual) <= _tol(tol.distance_rel, balance.mission_distance_m),
            "final distance vs sum of segment distances",
        ),
        ClosureResidual(
            "continuity",
            balance.max_boundary_discontinuity,
            tol.continuity_abs,
            balance.max_boundary_discontinuity <= tol.continuity_abs,
            "max segment-boundary state discontinuity",
        ),
    )
    return ClosureReport(residuals)
