"""Bounded control allocation with saturation, rate limits, and failures.

:func:`allocate` distributes a desired roll/pitch/yaw moment vector across
redundant effectors through either a weighted pseudo-inverse with iterative
saturation handling or a priority-ordered daisy chain. Position limits are
intersected with slew-rate reachable bounds from the current positions, so a
demand that needs faster motion than the actuators allow is reported
infeasible rather than silently clipped. Faults (failed, stuck, degraded)
reconfigure the problem explicitly and are recorded in the result.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite
from typing import Any

from aeroworkbench_optimization.design_space import content_digest

from .contracts import ControlMeta, result_meta
from .effectiveness import AXES, ControlEffector, EffectivenessMatrix
from .errors import AllocationError, ControlContractError
from .linalg import least_squares

__all__ = [
    "ALLOCATION_METHODS",
    "AllocationRequest",
    "AllocationResult",
    "EffectorFault",
    "FaultKind",
    "allocate",
    "effective_bounds",
]

ALLOCATION_METHODS = ("pseudo-inverse", "daisy-chain")

_REL_TOL = 1e-9


class FaultKind(StrEnum):
    """Failure modes that reconfigure allocation explicitly."""

    FAILED = "failed"
    STUCK = "stuck"
    DEGRADED = "degraded"


@dataclass(frozen=True, slots=True)
class EffectorFault:
    """A declared failure: failed (dead at zero), stuck, or degraded."""

    effector: str
    kind: FaultKind
    stuck_at: float | None = None
    effectiveness_scale: float | None = None

    def __post_init__(self) -> None:
        if not self.effector.strip():
            raise ControlContractError("FAULT_EFFECTOR_REQUIRED")
        if self.kind is FaultKind.STUCK:
            if self.stuck_at is None:
                raise ControlContractError(f"STUCK_FAULT_NEEDS_POSITION:{self.effector}")
            value = self.stuck_at
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ControlContractError(f"NONFINITE_VALUE:fault.{self.effector}")
            if float(value) != float(value) or float(value) in (float("inf"), float("-inf")):
                raise ControlContractError(f"NONFINITE_VALUE:fault.{self.effector}")
        if self.kind is FaultKind.DEGRADED:
            if self.effectiveness_scale is None:
                raise ControlContractError(f"DEGRADED_FAULT_NEEDS_SCALE:{self.effector}")
            scale = self.effectiveness_scale
            if isinstance(scale, bool) or not isinstance(scale, (int, float)):
                raise ControlContractError(f"NONFINITE_VALUE:fault.{self.effector}.scale")
            if not 0.0 <= float(scale) <= 1.0:
                raise ControlContractError(f"DEGRADED_SCALE_OUT_OF_RANGE:{self.effector}")

    def canonical(self) -> dict[str, Any]:
        return {
            "effector": self.effector,
            "kind": self.kind.value,
            "stuckAt": self.stuck_at,
            "effectivenessScale": self.effectiveness_scale,
        }


@dataclass(frozen=True, slots=True)
class AllocationRequest:
    """A moment demand with current positions, step horizon, method, and faults."""

    desired: tuple[float, float, float]
    current: tuple[tuple[str, float], ...]
    dt_s: float
    method: str = "pseudo-inverse"
    faults: tuple[EffectorFault, ...] = ()

    def __post_init__(self) -> None:
        for axis, value in zip(AXES, self.desired, strict=True):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ControlContractError(f"NONFINITE_VALUE:desired.{axis}")
            if not isfinite(float(value)):
                raise ControlContractError(f"NONFINITE_VALUE:desired.{axis}")
        if self.method not in ALLOCATION_METHODS:
            raise ControlContractError(f"UNKNOWN_ALLOCATION_METHOD:{self.method}")
        if isinstance(self.dt_s, bool) or not isinstance(self.dt_s, (int, float)):
            raise ControlContractError("NONFINITE_VALUE:allocation.dt_s")
        if not isfinite(float(self.dt_s)) or float(self.dt_s) <= 0.0:
            raise ControlContractError("ALLOCATION_DT_MUST_BE_POSITIVE")
        names = [name for name, _ in self.current]
        if len(set(names)) != len(names):
            raise ControlContractError("DUPLICATE_CURRENT_POSITION")
        for name, value in self.current:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ControlContractError(f"NONFINITE_VALUE:current.{name}")
            if not isfinite(float(value)):
                raise ControlContractError(f"NONFINITE_VALUE:current.{name}")
        fault_names = [fault.effector for fault in self.faults]
        if len(set(fault_names)) != len(fault_names):
            raise ControlContractError("DUPLICATE_FAULT")

    def position(self, name: str) -> float:
        for key, value in self.current:
            if key == name:
                return float(value)
        raise ControlContractError(f"UNKNOWN_EFFECTOR:{name}")

    def canonical(self) -> dict[str, Any]:
        return {
            "desired": {axis: value for axis, value in zip(AXES, self.desired, strict=True)},
            "current": {name: value for name, value in sorted(self.current)},
            "dtS": float(self.dt_s),
            "method": self.method,
            "faults": [
                fault.canonical() for fault in sorted(self.faults, key=lambda f: f.effector)
            ],
        }


@dataclass(frozen=True, slots=True)
class AllocationResult:
    """Allocated positions with achieved moments, flags, verdict, and provenance."""

    positions: tuple[tuple[str, float], ...]
    achieved: tuple[float, float, float]
    residual: tuple[float, float, float]
    residual_norm: float
    feasible: bool
    saturated: tuple[str, ...]
    rate_limited: tuple[str, ...]
    failed: tuple[str, ...]
    reconfigured: bool
    method: str
    reasons: tuple[str, ...]
    meta: ControlMeta

    def position(self, name: str) -> float:
        for key, value in self.positions:
            if key == name:
                return value
        raise AllocationError(f"UNKNOWN_EFFECTOR:{name}")

    def as_dict(self) -> dict[str, Any]:
        return {
            "positions": {name: value for name, value in self.positions},
            "achieved": {axis: value for axis, value in zip(AXES, self.achieved, strict=True)},
            "residual": {axis: value for axis, value in zip(AXES, self.residual, strict=True)},
            "residualNorm": self.residual_norm,
            "feasible": self.feasible,
            "saturated": list(self.saturated),
            "rateLimited": list(self.rate_limited),
            "failed": list(self.failed),
            "reconfigured": self.reconfigured,
            "method": self.method,
            "reasons": list(self.reasons),
            "meta": self.meta.as_dict(),
        }

    def canonical(self) -> dict[str, Any]:
        payload = self.as_dict()
        payload["positions"] = {name: value for name, value in sorted(self.positions)}
        return payload

    @property
    def digest(self) -> str:
        return content_digest(self.canonical())


def effective_bounds(
    effector: ControlEffector, *, current: float, dt_s: float
) -> tuple[float, float]:
    """Position limits intersected with the slew-rate reachable interval."""
    reachable = effector.max_rate * dt_s
    return (
        max(effector.lower_limit, current - reachable),
        min(effector.upper_limit, current + reachable),
    )


def _fault_map(request: AllocationRequest) -> dict[str, EffectorFault]:
    return {fault.effector: fault for fault in request.faults}


def _scaled_columns(
    matrix: EffectivenessMatrix,
    effectors: tuple[ControlEffector, ...],
    faults: dict[str, EffectorFault],
) -> tuple[dict[str, tuple[float, float, float]], tuple[str, ...]]:
    columns: dict[str, tuple[float, float, float]] = {}
    failed: list[str] = []
    by_name = {effector.name: effector for effector in effectors}
    for name in matrix.effectors:
        if name not in by_name:
            raise ControlContractError(f"UNKNOWN_EFFECTOR:{name}")
        column = matrix.column(name)
        fault = faults.get(name)
        if fault is None:
            columns[name] = column
        elif fault.kind is FaultKind.FAILED or fault.kind is FaultKind.STUCK:
            columns[name] = (0.0, 0.0, 0.0)
            failed.append(name)
        else:
            scale = float(fault.effectiveness_scale or 0.0)
            columns[name] = (column[0] * scale, column[1] * scale, column[2] * scale)
    return columns, tuple(sorted(failed))


def _check_bounds(
    effectors: tuple[ControlEffector, ...],
    request: AllocationRequest,
    faults: dict[str, EffectorFault],
) -> tuple[dict[str, tuple[float, float]], tuple[str, ...]]:
    bounds: dict[str, tuple[float, float]] = {}
    problems: list[str] = []
    for effector in effectors:
        fault = faults.get(effector.name)
        current = request.position(effector.name)
        if fault is not None and fault.kind is FaultKind.STUCK:
            stuck = float(fault.stuck_at or 0.0)
            bounds[effector.name] = (stuck, stuck)
            continue
        if fault is not None and fault.kind is FaultKind.FAILED:
            bounds[effector.name] = (0.0, 0.0)
            continue
        low, high = effective_bounds(effector, current=current, dt_s=float(request.dt_s))
        bounds[effector.name] = (low, high)
        if low > high:
            problems.append(f"RATE_LIMIT_INFEASIBLE:{effector.name}")
    return bounds, tuple(problems)


def _achieved(
    scaled: dict[str, tuple[float, float, float]],
    solution: dict[str, float],
    stuck_moment: tuple[float, float, float],
) -> tuple[float, float, float]:
    total = [stuck_moment[0], stuck_moment[1], stuck_moment[2]]
    for name, position in solution.items():
        column = scaled[name]
        for axis in range(3):
            total[axis] += column[axis] * position
    return (total[0], total[1], total[2])


def _stuck_moment(
    matrix: EffectivenessMatrix,
    faults: dict[str, EffectorFault],
) -> tuple[float, float, float]:
    total = [0.0, 0.0, 0.0]
    for name, fault in faults.items():
        if fault.kind is FaultKind.STUCK:
            column = matrix.column(name)
            stuck = float(fault.stuck_at or 0.0)
            for axis in range(3):
                total[axis] += column[axis] * stuck
    return (total[0], total[1], total[2])


def _clip(value: float, low: float, high: float) -> float:
    return min(max(value, low), high)


def _solve_free(
    names: tuple[str, ...],
    scaled: dict[str, tuple[float, float, float]],
    need: tuple[float, float, float],
) -> dict[str, float]:
    if not names:
        return {}
    matrix = [[scaled[name][axis] for name in names] for axis in range(3)]
    values, _ = least_squares(matrix, list(need))
    return {name: values[index] for index, name in enumerate(names)}


def _allocate_pseudo_inverse(
    order: tuple[str, ...],
    scaled: dict[str, tuple[float, float, float]],
    bounds: dict[str, tuple[float, float]],
    need: tuple[float, float, float],
) -> dict[str, float]:
    solution = {name: (bounds[name][0] + bounds[name][1]) / 2.0 for name in order}
    fixed: dict[str, float] = {}
    free = list(order)
    for _ in range(len(order) + 1):
        residual = [need[axis] for axis in range(3)]
        for name, value in fixed.items():
            column = scaled[name]
            for axis in range(3):
                residual[axis] -= column[axis] * value
        trial = _solve_free(tuple(free), scaled, (residual[0], residual[1], residual[2]))
        newly_fixed = False
        for name in list(free):
            low, high = bounds[name]
            clipped = _clip(trial[name], low, high)
            if clipped != trial[name]:
                fixed[name] = clipped
                free.remove(name)
                newly_fixed = True
            else:
                solution[name] = clipped
        if not newly_fixed:
            for name in free:
                solution[name] = trial[name]
            break
    solution.update(fixed)
    return {name: solution[name] for name in order}


def _allocate_daisy_chain(
    groups: tuple[tuple[str, ...], ...],
    scaled: dict[str, tuple[float, float, float]],
    bounds: dict[str, tuple[float, float]],
    need: tuple[float, float, float],
) -> dict[str, float]:
    solution: dict[str, float] = {}
    remaining = [need[0], need[1], need[2]]
    for group in groups:
        trial = _solve_free(group, scaled, (remaining[0], remaining[1], remaining[2]))
        for name in group:
            low, high = bounds[name]
            solution[name] = _clip(trial[name], low, high)
            column = scaled[name]
            for axis in range(3):
                remaining[axis] -= column[axis] * solution[name]
    return solution


def allocate(
    matrix: EffectivenessMatrix,
    effectors: tuple[ControlEffector, ...],
    request: AllocationRequest,
) -> AllocationResult:
    """Allocate the desired moments, failing closed when limits cannot meet them."""
    by_name = {effector.name: effector for effector in effectors}
    if tuple(sorted(by_name)) != tuple(sorted(matrix.effectors)):
        raise ControlContractError("ALLOCATION_EFFECTOR_SET_MISMATCH")
    for name, _ in request.current:
        if name not in by_name:
            raise ControlContractError(f"UNKNOWN_EFFECTOR:{name}")
    for fault in request.faults:
        if fault.effector not in by_name:
            raise ControlContractError(f"UNKNOWN_EFFECTOR:{fault.effector}")
    faults = _fault_map(request)
    scaled, failed = _scaled_columns(matrix, effectors, faults)
    bounds, bound_problems = _check_bounds(effectors, request, faults)
    stuck = _stuck_moment(matrix, faults)
    need = (
        float(request.desired[0]) - stuck[0],
        float(request.desired[1]) - stuck[1],
        float(request.desired[2]) - stuck[2],
    )
    order = tuple(sorted(matrix.effectors))
    if bound_problems:
        solution = {name: _clip(request.position(name), *bounds[name]) for name in order}
    elif request.method == "pseudo-inverse":
        solution = _allocate_pseudo_inverse(order, scaled, bounds, need)
    else:
        priorities = sorted({by_name[name].priority for name in order})
        groups = tuple(
            tuple(sorted(name for name in order if by_name[name].priority == level))
            for level in priorities
        )
        solution = _allocate_daisy_chain(groups, scaled, bounds, need)
    achieved = _achieved(scaled, solution, stuck)
    residual = (
        float(request.desired[0]) - achieved[0],
        float(request.desired[1]) - achieved[1],
        float(request.desired[2]) - achieved[2],
    )
    residual_norm = float(sum(component * component for component in residual) ** 0.5)
    demand_norm = max(1.0, max(abs(float(v)) for v in request.desired))
    feasible = residual_norm <= _REL_TOL * demand_norm and not bound_problems
    saturated: list[str] = []
    rate_limited: list[str] = []
    for name in order:
        effector = by_name[name]
        low, high = bounds[name]
        value = solution[name]
        eps = 1e-12 * max(1.0, abs(value))
        at_bound = value <= low + eps or value >= high - eps
        if not at_bound:
            continue
        rate_active = (low > effector.lower_limit + eps) or (high < effector.upper_limit - eps)
        if rate_active:
            rate_limited.append(name)
        else:
            saturated.append(name)
    reasons: list[str] = list(bound_problems)
    if not feasible and not reasons:
        reasons.append("CONTROL_AUTHORITY_INSUFFICIENT")
        for name in sorted(set(saturated) | set(rate_limited)):
            reasons.append(f"LIMITED:{name}")
    if failed:
        reasons.append(f"RECONFIGURED_AROUND:{','.join(failed)}")
    checks = (
        ("authority-sufficient", feasible),
        ("within-position-limits", all(
            by_name[name].lower_limit - 1e-9 <= solution[name] <= by_name[name].upper_limit + 1e-9
            for name in order
        )),
        ("no-escalation", True),
    )
    inputs: dict[str, Any] = {
        "effectiveness": matrix.canonical(),
        "effectors": [effector.canonical() for effector in sorted(effectors, key=lambda e: e.name)],
        "request": request.canonical(),
    }
    meta = result_meta(
        model="vehicle-control-allocation",
        inputs=inputs,
        valid=feasible,
        checks=checks,
        detail="allocation feasible" if feasible else ";".join(reasons),
        assumptions=(
            "linear effectiveness at the allocation point",
            "position limits intersected with slew-rate reachable bounds",
            "faulted effectors are removed or fixed before solving",
        ),
    )
    return AllocationResult(
        positions=tuple((name, solution[name]) for name in order),
        achieved=achieved,
        residual=residual,
        residual_norm=residual_norm,
        feasible=feasible,
        saturated=tuple(sorted(saturated)),
        rate_limited=tuple(sorted(rate_limited)),
        failed=failed,
        reconfigured=bool(request.faults),
        method=request.method,
        reasons=tuple(reasons),
        meta=meta,
    )
