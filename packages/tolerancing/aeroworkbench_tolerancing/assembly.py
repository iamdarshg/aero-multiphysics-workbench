"""Generic assembly-constraint checks over the tolerance contract.

Clearance/interference fits, insertion and tool-access paths, fastener
edge-distance and pitch rules, and datum consistency are all evaluated from
typed contracts. A tolerance-driven collision is rejected on the requested
worst case, not hidden behind a nominal clearance.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from aeroworkbench_manufacturing.units import from_si, to_si, unit_dimension

from .contracts import (
    ResultEnvelope,
    ToleranceCallout,
    ToleranceContract,
    build_envelope,
    deviation_scale,
)
from .errors import AssemblyError, ToleranceContractError

__all__ = [
    "AssemblyReport",
    "AssemblyViolation",
    "EdgeDistanceRule",
    "FastenerJoint",
    "FitAssessment",
    "FitSpec",
    "FitType",
    "InsertionPath",
    "JointCheck",
    "PathCheck",
    "assess_fit",
    "check_assembly",
    "check_datums",
]

MAX_FIT_SAMPLES = 200_000
DEFAULT_FIT_SAMPLES = 10_000
_INTERVAL_EPS_SI = 1e-12


class FitType(StrEnum):
    """Requested fit condition for a hole/shaft pair."""

    CLEARANCE = "clearance"
    TRANSITION = "transition"
    INTERFERENCE = "interference"


@dataclass(frozen=True, slots=True)
class FitSpec:
    """A hole/shaft pair and the fit condition it must satisfy."""

    fit_id: str
    hole: ToleranceCallout
    shaft: ToleranceCallout
    required_fit: FitType = FitType.CLEARANCE
    min_clearance: float = 0.0
    min_interference: float = 0.0

    def __post_init__(self) -> None:
        if not self.fit_id.strip():
            raise AssemblyError("FIT_ID_REQUIRED")
        if unit_dimension(self.hole.unit) != unit_dimension(self.shaft.unit):
            raise AssemblyError(f"FIT_UNIT_DIMENSION_MISMATCH:{self.fit_id}")
        for label, value in (
            ("min_clearance", self.min_clearance),
            ("min_interference", self.min_interference),
        ):
            if not math.isfinite(value):
                raise AssemblyError(f"NONFINITE_{label.upper()}:{self.fit_id}")

    def inputs_payload(self) -> dict[str, Any]:
        return {
            "fitId": self.fit_id,
            "hole": self.hole.as_dict(),
            "shaft": self.shaft.as_dict(),
            "requiredFit": self.required_fit.value,
            "minClearance": self.min_clearance,
            "minInterference": self.min_interference,
        }


@dataclass(frozen=True, slots=True)
class FitAssessment:
    """Worst-case and statistical clearance/interference for one fit."""

    fit_id: str
    unit: str
    required_fit: FitType
    nominal_clearance: float
    worst_case_min_clearance: float
    worst_case_max_clearance: float
    statistical_sigma: float
    interference_probability: float
    clearance_probability: float
    satisfied: bool
    violations: tuple[str, ...]
    envelope: ResultEnvelope

    def as_dict(self) -> dict[str, Any]:
        return {
            "fitId": self.fit_id,
            "unit": self.unit,
            "requiredFit": self.required_fit.value,
            "nominalClearance": self.nominal_clearance,
            "worstCaseMinClearance": self.worst_case_min_clearance,
            "worstCaseMaxClearance": self.worst_case_max_clearance,
            "statisticalSigma": self.statistical_sigma,
            "interferenceProbability": self.interference_probability,
            "clearanceProbability": self.clearance_probability,
            "satisfied": self.satisfied,
            "violations": list(self.violations),
            "envelope": self.envelope.as_dict(),
        }


def _clearance_sigma_si(hole: ToleranceCallout, shaft: ToleranceCallout) -> float:
    return math.hypot(hole.to_distribution_sigma_si(), shaft.to_distribution_sigma_si())


def assess_fit(
    spec: FitSpec,
    *,
    samples: int = DEFAULT_FIT_SAMPLES,
    seed: int = 0,
) -> FitAssessment:
    """Evaluate a fit; a requested interference/clearance must hold worst-case."""

    if samples < 1:
        raise AssemblyError("FIT_SAMPLES_MUST_BE_POSITIVE")
    if samples > MAX_FIT_SAMPLES:
        raise AssemblyError(f"FIT_SAMPLES_EXCEED_BOUND:{MAX_FIT_SAMPLES}")
    hole = spec.hole
    shaft = spec.shaft
    nominal_si = hole.nominal_si - shaft.nominal_si
    min_si = hole.lower_si - shaft.upper_si
    max_si = hole.upper_si - shaft.lower_si
    sigma_si = _clearance_sigma_si(hole, shaft)
    rng = random.Random(seed)
    interference = 0
    for _ in range(samples):
        clearance = (hole.nominal_si - shaft.nominal_si) + (
            hole.sample_deviation(rng) * deviation_scale(hole.unit)
            - shaft.sample_deviation(rng) * deviation_scale(shaft.unit)
        )
        if clearance < 0.0:
            interference += 1
    interference_probability = interference / samples
    violations: list[str] = []
    min_clearance_si = to_si(spec.min_clearance, hole.unit)
    min_interference_si = to_si(spec.min_interference, hole.unit)
    if spec.required_fit is FitType.CLEARANCE:
        if min_si < min_clearance_si - _INTERVAL_EPS_SI:
            violations.append("WORST_CASE_CLEARANCE_BELOW_MINIMUM")
    elif spec.required_fit is FitType.INTERFERENCE:
        if max_si > _INTERVAL_EPS_SI:
            violations.append("WORST_CASE_INTERFERENCE_NOT_ASSURED")
        if -min_si < min_interference_si - _INTERVAL_EPS_SI:
            violations.append("WORST_CASE_INTERFERENCE_BELOW_MINIMUM")
    envelope = build_envelope(
        model="advphys10-assembly-fit",
        inputs={**spec.inputs_payload(), "samples": samples, "seed": seed},
        unit=hole.unit,
        assumptions=(
            "clearance is hole size minus shaft size in matching units",
            "worst-case bound uses drawing limits; statistical term uses declared distributions",
            "fixed seed for reproducibility",
        ),
    )
    return FitAssessment(
        fit_id=spec.fit_id,
        unit=hole.unit,
        required_fit=spec.required_fit,
        nominal_clearance=from_si(nominal_si, hole.unit),
        worst_case_min_clearance=from_si(min_si, hole.unit),
        worst_case_max_clearance=from_si(max_si, hole.unit),
        statistical_sigma=from_si(sigma_si, hole.unit),
        interference_probability=interference_probability,
        clearance_probability=1.0 - interference_probability,
        satisfied=not violations,
        violations=tuple(violations),
        envelope=envelope,
    )


@dataclass(frozen=True, slots=True)
class InsertionPath:
    """A straight insertion/tool-access path with required and available length."""

    path_id: str
    direction: tuple[float, float, float]
    required_length_m: float
    available_length_m: float

    def __post_init__(self) -> None:
        if not self.path_id.strip():
            raise AssemblyError("PATH_ID_REQUIRED")
        if len(self.direction) != 3 or any(not math.isfinite(item) for item in self.direction):
            raise AssemblyError(f"PATH_DIRECTION_INVALID:{self.path_id}")
        if math.sqrt(sum(item * item for item in self.direction)) <= 0.0:
            raise AssemblyError(f"PATH_DIRECTION_ZERO:{self.path_id}")
        if not math.isfinite(self.required_length_m) or not math.isfinite(self.available_length_m):
            raise AssemblyError(f"NONFINITE_PATH_LENGTH:{self.path_id}")

    def check(self) -> PathCheck:
        if self.available_length_m < self.required_length_m:
            return PathCheck(
                path_id=self.path_id,
                satisfied=False,
                reason="INSUFFICIENT_INSERTION_LENGTH",
            )
        return PathCheck(path_id=self.path_id, satisfied=True, reason="OK")

    def as_dict(self) -> dict[str, Any]:
        return {
            "pathId": self.path_id,
            "direction": list(self.direction),
            "requiredLengthM": self.required_length_m,
            "availableLengthM": self.available_length_m,
        }


@dataclass(frozen=True, slots=True)
class PathCheck:
    """Outcome of one insertion/tool-access path check."""

    path_id: str
    satisfied: bool
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return {"pathId": self.path_id, "satisfied": self.satisfied, "reason": self.reason}


@dataclass(frozen=True, slots=True)
class EdgeDistanceRule:
    """Fastener edge-distance rule: edge >= ratio * diameter."""

    rule_id: str
    hole_diameter_m: float
    edge_distance_m: float
    min_ratio: float = 2.0

    def __post_init__(self) -> None:
        if not self.rule_id.strip():
            raise AssemblyError("EDGE_RULE_ID_REQUIRED")
        for label, value in (
            ("hole_diameter_m", self.hole_diameter_m),
            ("edge_distance_m", self.edge_distance_m),
            ("min_ratio", self.min_ratio),
        ):
            if not math.isfinite(value):
                raise AssemblyError(f"NONFINITE_{label.upper()}:{self.rule_id}")
        if self.hole_diameter_m <= 0 or self.min_ratio <= 0:
            raise AssemblyError(f"EDGE_RULE_DIMENSIONS_MUST_BE_POSITIVE:{self.rule_id}")

    def check(self) -> JointCheck:
        required = self.min_ratio * self.hole_diameter_m
        reasons: list[str] = []
        if self.edge_distance_m < required:
            reasons.append("EDGE_DISTANCE_BELOW_MINIMUM")
        return JointCheck(
            joint_id=self.rule_id, satisfied=not reasons, reasons=tuple(reasons)
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "ruleId": self.rule_id,
            "holeDiameterM": self.hole_diameter_m,
            "edgeDistanceM": self.edge_distance_m,
            "minRatio": self.min_ratio,
        }


@dataclass(frozen=True, slots=True)
class FastenerJoint:
    """Fastener joint with edge-distance and optional pitch rules."""

    joint_id: str
    fastener_diameter_m: float
    edge_distance_m: float
    min_edge_ratio: float = 2.0
    pitch_m: float | None = None
    min_pitch_ratio: float | None = None

    def __post_init__(self) -> None:
        if not self.joint_id.strip():
            raise AssemblyError("JOINT_ID_REQUIRED")
        for label, value in (
            ("fastener_diameter_m", self.fastener_diameter_m),
            ("edge_distance_m", self.edge_distance_m),
            ("min_edge_ratio", self.min_edge_ratio),
        ):
            if not math.isfinite(value):
                raise AssemblyError(f"NONFINITE_{label.upper()}:{self.joint_id}")
        if self.fastener_diameter_m <= 0 or self.min_edge_ratio <= 0:
            raise AssemblyError(f"JOINT_DIMENSIONS_MUST_BE_POSITIVE:{self.joint_id}")
        if self.pitch_m is not None and (
            not math.isfinite(self.pitch_m) or self.pitch_m <= 0
        ):
            raise AssemblyError(f"INVALID_PITCH:{self.joint_id}")
        if self.min_pitch_ratio is not None and (
            not math.isfinite(self.min_pitch_ratio) or self.min_pitch_ratio <= 0
        ):
            raise AssemblyError(f"INVALID_PITCH_RATIO:{self.joint_id}")

    def check(self) -> JointCheck:
        reasons: list[str] = []
        if self.edge_distance_m < self.min_edge_ratio * self.fastener_diameter_m:
            reasons.append("EDGE_DISTANCE_BELOW_MINIMUM")
        if (
            self.pitch_m is not None
            and self.min_pitch_ratio is not None
            and self.pitch_m < self.min_pitch_ratio * self.fastener_diameter_m
        ):
            reasons.append("PITCH_BELOW_MINIMUM")
        return JointCheck(joint_id=self.joint_id, satisfied=not reasons, reasons=tuple(reasons))

    def as_dict(self) -> dict[str, Any]:
        return {
            "jointId": self.joint_id,
            "fastenerDiameterM": self.fastener_diameter_m,
            "edgeDistanceM": self.edge_distance_m,
            "minEdgeRatio": self.min_edge_ratio,
            "pitchM": self.pitch_m,
            "minPitchRatio": self.min_pitch_ratio,
        }


@dataclass(frozen=True, slots=True)
class JointCheck:
    """Outcome of one fastener/joint rule check."""

    joint_id: str
    satisfied: bool
    reasons: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "jointId": self.joint_id,
            "satisfied": self.satisfied,
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True, slots=True)
class AssemblyViolation:
    """A typed reason an assembly constraint was rejected."""

    kind: str
    subject_id: str
    detail: str

    def as_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "subjectId": self.subject_id, "detail": self.detail}


@dataclass(frozen=True, slots=True)
class AssemblyReport:
    """Aggregate assembly-constraint outcome with its result envelope."""

    satisfied: bool
    violations: tuple[AssemblyViolation, ...]
    fit_assessments: tuple[FitAssessment, ...]
    path_checks: tuple[PathCheck, ...]
    joint_checks: tuple[JointCheck, ...]
    datum_consistent: bool
    envelope: ResultEnvelope

    def as_dict(self) -> dict[str, Any]:
        return {
            "satisfied": self.satisfied,
            "violations": [item.as_dict() for item in self.violations],
            "fits": [item.as_dict() for item in self.fit_assessments],
            "paths": [item.as_dict() for item in self.path_checks],
            "joints": [item.as_dict() for item in self.joint_checks],
            "datumConsistent": self.datum_consistent,
            "envelope": self.envelope.as_dict(),
        }


def check_datums(contract: ToleranceContract) -> tuple[AssemblyViolation, ...]:
    """Reject conflicting datum-feature bindings across a contract."""

    violations: list[AssemblyViolation] = []
    try:
        contract.datum_index()
    except ToleranceContractError as error:
        violations.append(
            AssemblyViolation(
                kind="datum-conflict", subject_id=contract.contract_id, detail=str(error)
            )
        )
    return tuple(violations)


def check_assembly(
    *,
    contract: ToleranceContract | None = None,
    fits: tuple[FitSpec, ...] = (),
    paths: tuple[InsertionPath, ...] = (),
    joints: tuple[FastenerJoint | EdgeDistanceRule, ...] = (),
    require_datums: bool = True,
    samples: int = DEFAULT_FIT_SAMPLES,
    seed: int = 0,
) -> AssemblyReport:
    """Evaluate all declared assembly constraints; any failure rejects."""

    violations: list[AssemblyViolation] = []
    fit_assessments: list[FitAssessment] = []
    for fit in fits:
        assessment = assess_fit(fit, samples=samples, seed=seed)
        fit_assessments.append(assessment)
        for reason in assessment.violations:
            violations.append(
                AssemblyViolation(kind="fit", subject_id=fit.fit_id, detail=reason)
            )
    path_checks: list[PathCheck] = []
    for path in paths:
        check = path.check()
        path_checks.append(check)
        if not check.satisfied:
            violations.append(
                AssemblyViolation(
                    kind="insertion-path", subject_id=path.path_id, detail=check.reason
                )
            )
    joint_checks: list[JointCheck] = []
    for joint in joints:
        joint_result = joint.check()
        joint_checks.append(joint_result)
        for reason in joint_result.reasons:
            violations.append(
                AssemblyViolation(
                    kind="fastener-joint", subject_id=joint_result.joint_id, detail=reason
                )
            )
    datum_violations: tuple[AssemblyViolation, ...] = ()
    if contract is not None and require_datums:
        datum_violations = check_datums(contract)
        violations.extend(datum_violations)
    envelope = build_envelope(
        model="advphys10-assembly-check",
        inputs={
            "contractHash": None if contract is None else contract.content_hash,
            "fits": [fit.inputs_payload() for fit in fits],
            "paths": [path.as_dict() for path in paths],
            "joints": [joint.as_dict() for joint in joints],
            "samples": samples,
            "seed": seed,
        },
        unit="1",
        assumptions=(
            "fit feasibility is judged on worst-case drawing limits",
            "insertion paths are straight, as declared",
            "datum consistency is checked across the tolerance contract",
        ),
        validity="valid" if not violations else "rejected",
    )
    return AssemblyReport(
        satisfied=not violations,
        violations=tuple(violations),
        fit_assessments=tuple(fit_assessments),
        path_checks=tuple(path_checks),
        joint_checks=tuple(joint_checks),
        datum_consistent=not datum_violations,
        envelope=envelope,
    )
