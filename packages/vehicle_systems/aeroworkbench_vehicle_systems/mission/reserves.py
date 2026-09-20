"""Reserve requirements enforced explicitly at mission end.

A reserve is never inferred from a nominal range. Fuel and energy reserves are
compared against the *actual* residual state at mission end; a time reserve is
satisfied only by an actually-flown reserve segment. Any shortfall fails closed
with a typed :class:`ReserveError` when the caller asks for a mandatory verdict.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ReserveError
from .segments import MissionSpec, ReserveKind, ReserveSpec, VehicleSpec
from .state import MissionState

__all__ = ["ReserveReport", "ReserveVerdict", "evaluate_reserves"]


@dataclass(frozen=True, slots=True)
class ReserveReport:
    """One reserve's required/achieved margin at mission end."""

    label: str
    kind: ReserveKind
    unit: str
    required: float
    achieved: float
    passed: bool

    @property
    def margin(self) -> float:
        return self.achieved - self.required

    def as_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "kind": self.kind.value,
            "unit": self.unit,
            "required": self.required,
            "achieved": self.achieved,
            "margin": self.margin,
            "passed": self.passed,
        }


@dataclass(frozen=True, slots=True)
class ReserveVerdict:
    """The aggregate reserve verdict for a mission."""

    reports: tuple[ReserveReport, ...]

    @property
    def passed(self) -> bool:
        return all(report.passed for report in self.reports)

    def report_for(self, label: str) -> ReserveReport:
        for report in self.reports:
            if report.label == label:
                return report
        raise ReserveError(f"UNKNOWN_RESERVE:{label}")

    def as_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "reports": [report.as_dict() for report in self.reports],
        }


def _reserve_achieved(
    reserve: ReserveSpec,
    vehicle: VehicleSpec,
    final_state: MissionState,
    reserve_duration_s: float,
) -> float:
    if reserve.kind is ReserveKind.FUEL:
        return final_state.fuel_kg
    if reserve.kind is ReserveKind.ENERGY:
        return final_state.stored_energy_j(vehicle)
    return reserve_duration_s


def evaluate_reserves(
    spec: MissionSpec,
    final_state: MissionState,
    *,
    reserve_duration_s: float,
    raise_on_failure: bool = False,
) -> ReserveVerdict:
    """Evaluate every declared reserve against the actual final state."""

    if not spec.reserves:
        return ReserveVerdict(())
    reports: list[ReserveReport] = []
    for reserve in spec.reserves:
        achieved = _reserve_achieved(reserve, spec.vehicle, final_state, reserve_duration_s)
        reports.append(
            ReserveReport(
                label=reserve.label,
                kind=reserve.kind,
                unit=reserve.unit(),
                required=reserve.amount,
                achieved=achieved,
                passed=achieved + 1e-9 >= reserve.amount,
            )
        )
    verdict = ReserveVerdict(tuple(reports))
    if raise_on_failure and not verdict.passed:
        failed = next(report for report in verdict.reports if not report.passed)
        raise ReserveError(
            f"RESERVE_NOT_MET:{failed.label}:{failed.kind.value}:"
            f"required={failed.required}:achieved={failed.achieved}"
        )
    return verdict
