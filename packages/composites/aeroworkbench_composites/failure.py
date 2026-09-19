"""Provenance-visible composite failure criteria and first/progressive ply failure.

Criteria never collapse to an isotropic factor of safety: maximum stress/strain,
Tsai-Hill, Tsai-Wu, and Hashin-style fiber/matrix modes are evaluated explicitly,
each declaring its assumptions and required allowables. A criterion whose
required allowables are absent fails closed, and an interlaminar/delamination
indicator is only available when transverse/interlaminar strength data exists.
First-ply failure is always available; progressive ply discard is opt-in.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import sqrt
from typing import Any

from aeroworkbench_core.types import Provenance

from .clt import (
    LaminateAnalysis,
    LaminateLoad,
    PlyResponse,
    ply_stresses,
    ply_stresses_for,
)
from .ply import PlyStrength
from .provenance import analytical_provenance
from .validity import CompositesError, DataUnavailable, Validity, finite

__all__ = [
    "CRITERION_ASSUMPTIONS",
    "CRITERION_REQUIRED_ALLOWABLES",
    "FailureCriterion",
    "FailureIndex",
    "FirstPlyResult",
    "PlyDiscardPolicy",
    "PlyStrainLimits",
    "PlyStress",
    "ProgressiveResult",
    "StrengthLibrary",
    "evaluate_interlaminar",
    "evaluate_ply_failure",
    "first_ply_failure",
    "progressive_failure",
]


class FailureCriterion(StrEnum):
    """Selectable in-plane composite failure criteria."""

    MAX_STRESS = "max-stress"
    MAX_STRAIN = "max-strain"
    TSAI_HILL = "tsai-hill"
    TSAI_WU = "tsai-wu"
    HASHIN = "hashin"
    FIRST_PLY = "first-ply"


CRITERION_REQUIRED_ALLOWABLES: dict[FailureCriterion, tuple[str, ...]] = {
    FailureCriterion.MAX_STRESS: (
        "x_tension_pa",
        "x_compression_pa",
        "y_tension_pa",
        "y_compression_pa",
        "shear_pa",
    ),
    FailureCriterion.MAX_STRAIN: (
        "x_tension_pa",
        "x_compression_pa",
        "y_tension_pa",
        "y_compression_pa",
        "shear_pa",
    ),
    FailureCriterion.TSAI_HILL: (
        "x_tension_pa",
        "x_compression_pa",
        "y_tension_pa",
        "y_compression_pa",
        "shear_pa",
    ),
    FailureCriterion.TSAI_WU: (
        "x_tension_pa",
        "x_compression_pa",
        "y_tension_pa",
        "y_compression_pa",
        "shear_pa",
    ),
    FailureCriterion.HASHIN: (
        "x_tension_pa",
        "x_compression_pa",
        "y_tension_pa",
        "y_compression_pa",
        "shear_pa",
    ),
    FailureCriterion.FIRST_PLY: (
        "x_tension_pa",
        "x_compression_pa",
        "y_tension_pa",
        "y_compression_pa",
        "shear_pa",
    ),
}

CRITERION_ASSUMPTIONS: dict[FailureCriterion, tuple[str, ...]] = {
    FailureCriterion.MAX_STRESS: (
        "first-mode (non-interacting) failure: no stress interaction is modelled",
        "tension/compression allowables selected by the sign of the stress",
    ),
    FailureCriterion.MAX_STRAIN: (
        "first-mode (non-interacting) strain-limit failure",
        "engineering shear strain compared against the shear strain limit",
    ),
    FailureCriterion.TSAI_HILL: (
        "quadratic interaction assumes equal tensile/compressive fibre response in sign",
        "valid only for an orthotropic ply in plane stress",
    ),
    FailureCriterion.TSAI_WU: (
        "quadratic tensor criterion with an F12 interaction term",
        "F12 defaults to -0.5*sqrt(F11*F22) unless a declared F12* is supplied",
    ),
    FailureCriterion.HASHIN: (
        "Hashin-style distinct fibre and matrix failure modes",
        "plane-stress Hashin; three-dimensional shear non-linearity is not modelled",
    ),
    FailureCriterion.FIRST_PLY: (
        "laminate first-ply failure: the weakest ply governs the load",
        "each ply is evaluated with its own material allowables",
    ),
}

_LINEAR = frozenset({FailureCriterion.MAX_STRESS, FailureCriterion.MAX_STRAIN})


@dataclass(frozen=True, slots=True)
class PlyStress:
    """In-material-axes ply stress (and optional strain) in SI units."""

    sigma_1_pa: float
    sigma_2_pa: float
    tau_12_pa: float
    eps_1: float = 0.0
    eps_2: float = 0.0
    gamma_12: float = 0.0
    sigma_3_pa: float | None = None
    tau_13_pa: float | None = None
    tau_23_pa: float | None = None

    def __post_init__(self) -> None:
        for name in ("sigma_1_pa", "sigma_2_pa", "tau_12_pa", "eps_1", "eps_2", "gamma_12"):
            finite(getattr(self, name), name)
        for name in ("sigma_3_pa", "tau_13_pa", "tau_23_pa"):
            value = getattr(self, name)
            if value is not None:
                finite(value, name)

    def units(self) -> dict[str, str]:
        return {
            "sigma_1_pa": "Pa",
            "sigma_2_pa": "Pa",
            "tau_12_pa": "Pa",
            "eps_1": "1",
            "eps_2": "1",
            "gamma_12": "1",
        }


@dataclass(frozen=True, slots=True)
class PlyStrainLimits:
    """Allowable strains for the maximum-strain criterion, bound to a material."""

    material_digest: str
    source: str
    revision: str
    x_tension: float
    x_compression: float
    y_tension: float
    y_compression: float
    shear: float

    def __post_init__(self) -> None:
        if len(self.material_digest) != 64:
            raise DataUnavailable("STRAIN_LIMITS_REQUIRE_MATERIAL_DIGEST")
        if not self.source.strip() or not self.revision.strip():
            raise DataUnavailable("STRAIN_LIMITS_SOURCE_AND_REVISION_REQUIRED")
        for name in ("x_tension", "x_compression", "y_tension", "y_compression", "shear"):
            finite(getattr(self, name), name, positive=True)

    @property
    def identity(self) -> str:
        return f"ply-strain-limits@{self.revision}"


@dataclass(frozen=True, slots=True)
class FailureIndex:
    """A single-ply failure index with its criterion, mode, and provenance."""

    criterion: FailureCriterion
    index: float
    reserve_factor: float
    mode: str
    failed: bool
    assumptions: tuple[str, ...]
    required_allowables: tuple[str, ...]
    provenance: Provenance

    def units(self) -> dict[str, str]:
        return {"index": "1", "reserve_factor": "1"}

    def as_dict(self) -> dict[str, Any]:
        return {
            "criterion": self.criterion.value,
            "index": self.index,
            "reserveFactor": self.reserve_factor,
            "failed": self.failed,
            "mode": self.mode,
            "assumptions": list(self.assumptions),
            "requiredAllowables": list(self.required_allowables),
            "inputsHash": self.provenance.inputs_hash,
            "source": self.provenance.source.value,
        }


def _require_allowables(strength: PlyStrength, criterion: FailureCriterion) -> None:
    missing = [
        name
        for name in CRITERION_REQUIRED_ALLOWABLES[criterion]
        if strength.value(name) is None
    ]
    if missing:
        raise DataUnavailable(
            f"CRITERION_REQUIRES_ALLOWABLES:{criterion.value}:{','.join(missing)}"
        )


def _reserve(index: float, *, linear: bool) -> float:
    if index <= 0.0:
        return float("inf")
    return 1.0 / index if linear else 1.0 / sqrt(index)


def _sign_allowable(positive: float, negative: float, value: float) -> float:
    return positive if value >= 0.0 else negative


def _linear_index(
    stress: PlyStress,
    x_t: float,
    x_c: float,
    y_t: float,
    y_c: float,
    s: float,
    *,
    strain_mode: bool,
    strain: PlyStrainLimits | None,
) -> tuple[float, str]:
    if strain_mode:
        assert strain is not None
        first, second, shear = stress.eps_1, stress.eps_2, stress.gamma_12
        x_allow = _sign_allowable(strain.x_tension, strain.x_compression, first)
        y_allow = _sign_allowable(strain.y_tension, strain.y_compression, second)
        shear_allow = strain.shear
    else:
        first, second, shear = stress.sigma_1_pa, stress.sigma_2_pa, stress.tau_12_pa
        x_allow = _sign_allowable(x_t, x_c, first)
        y_allow = _sign_allowable(y_t, y_c, second)
        shear_allow = s
    ratios = {
        "fibre-1": abs(first) / x_allow,
        "transverse-2": abs(second) / y_allow,
        "in-plane-shear-12": abs(shear) / shear_allow,
    }
    mode = max(ratios, key=lambda key: ratios[key])
    return ratios[mode], mode


def _tsai_hill(stress: PlyStress, strength: PlyStrength) -> tuple[float, str]:
    x = _sign_allowable(strength.x_tension_pa, strength.x_compression_pa, stress.sigma_1_pa)
    y = _sign_allowable(strength.y_tension_pa, strength.y_compression_pa, stress.sigma_2_pa)
    s = strength.shear_pa
    s1, s2, t12 = stress.sigma_1_pa, stress.sigma_2_pa, stress.tau_12_pa
    index = (s1 / x) ** 2 - (s1 * s2 / (x * x)) + (s2 / y) ** 2 + (t12 / s) ** 2
    return index, "tsai-hill-interaction"


def _tsai_wu(
    stress: PlyStress, strength: PlyStrength, *, f12_star: float | None
) -> tuple[float, str]:
    x_t, x_c = strength.x_tension_pa, strength.x_compression_pa
    y_t, y_c = strength.y_tension_pa, strength.y_compression_pa
    s = strength.shear_pa
    f1 = 1.0 / x_t - 1.0 / x_c
    f2 = 1.0 / y_t - 1.0 / y_c
    f11 = 1.0 / (x_t * x_c)
    f22 = 1.0 / (y_t * y_c)
    f66 = 1.0 / (s * s)
    star = -0.5 if f12_star is None else finite(f12_star, "tsai_wu_f12_star")
    if not -1.0 <= star <= 1.0:
        raise DataUnavailable("TSAI_WU_F12_STAR_OUT_OF_RANGE")
    f12 = star * sqrt(f11 * f22)
    s1, s2, t12 = stress.sigma_1_pa, stress.sigma_2_pa, stress.tau_12_pa
    index = (
        f1 * s1
        + f2 * s2
        + f11 * s1 * s1
        + f22 * s2 * s2
        + f66 * t12 * t12
        + 2.0 * f12 * s1 * s2
    )
    return index, "tsai-wu-interaction"


def _hashin(stress: PlyStress, strength: PlyStrength) -> tuple[float, str]:
    x_t, x_c = strength.x_tension_pa, strength.x_compression_pa
    y_t, y_c = strength.y_tension_pa, strength.y_compression_pa
    s = strength.shear_pa
    s1, s2, t12 = stress.sigma_1_pa, stress.sigma_2_pa, stress.tau_12_pa
    shear_term = (t12 / s) ** 2
    if s1 >= 0.0:
        fibre_index, fibre_mode = (s1 / x_t) ** 2 + shear_term, "fibre-tension"
    else:
        fibre_index, fibre_mode = (s1 / x_c) ** 2, "fibre-compression"
    if s2 >= 0.0:
        matrix_index, matrix_mode = (s2 / y_t) ** 2 + shear_term, "matrix-tension"
    else:
        matrix_index = (
            (s2 / (2.0 * s)) ** 2
            + ((y_c / (2.0 * s)) ** 2 - 1.0) * (s2 / y_c)
            + shear_term
        )
        matrix_mode = "matrix-compression"
    if fibre_index >= matrix_index:
        return fibre_index, fibre_mode
    return matrix_index, matrix_mode


def evaluate_ply_failure(
    stress: PlyStress,
    strength: PlyStrength,
    criterion: FailureCriterion,
    *,
    strain_limits: PlyStrainLimits | None = None,
    tsai_wu_f12_star: float | None = None,
) -> FailureIndex:
    """Evaluate one ply's stress state against a selectable failure criterion."""

    if criterion is FailureCriterion.FIRST_PLY:
        raise CompositesError(
            "FIRST_PLY_CRITERION_REQUIRES_A_LAMINATE:use first_ply_failure"
        )
    _require_allowables(strength, criterion)
    linear = criterion in _LINEAR
    strain_mode = criterion is FailureCriterion.MAX_STRAIN
    if strain_mode and strain_limits is None:
        raise DataUnavailable("MAX_STRAIN_REQUIRES_PLY_STRAIN_LIMITS")
    if strain_limits is not None and strain_limits.material_digest != strength.material_digest:
        raise DataUnavailable("STRAIN_LIMITS_DIGEST_MISMATCH")
    if criterion is FailureCriterion.MAX_STRESS:
        index, mode = _linear_index(
            stress,
            strength.x_tension_pa,
            strength.x_compression_pa,
            strength.y_tension_pa,
            strength.y_compression_pa,
            strength.shear_pa,
            strain_mode=False,
            strain=None,
        )
    elif criterion is FailureCriterion.MAX_STRAIN:
        index, mode = _linear_index(
            stress,
            strength.x_tension_pa,
            strength.x_compression_pa,
            strength.y_tension_pa,
            strength.y_compression_pa,
            strength.shear_pa,
            strain_mode=True,
            strain=strain_limits,
        )
    elif criterion is FailureCriterion.TSAI_HILL:
        index, mode = _tsai_hill(stress, strength)
    elif criterion is FailureCriterion.TSAI_WU:
        index, mode = _tsai_wu(stress, strength, f12_star=tsai_wu_f12_star)
    else:
        index, mode = _hashin(stress, strength)
    provenance = analytical_provenance(
        f"failure-{criterion.value}",
        {
            "materialDigest": strength.material_digest,
            "strengthRevision": strength.revision,
            "criterion": criterion.value,
            "sigma1Pa": stress.sigma_1_pa,
            "sigma2Pa": stress.sigma_2_pa,
            "tau12Pa": stress.tau_12_pa,
            "eps1": stress.eps_1,
            "eps2": stress.eps_2,
            "gamma12": stress.gamma_12,
            "tsaiWuF12Star": tsai_wu_f12_star,
        },
        assumptions=CRITERION_ASSUMPTIONS[criterion],
    )
    return FailureIndex(
        criterion=criterion,
        index=index,
        reserve_factor=_reserve(index, linear=linear),
        mode=mode,
        failed=index >= 1.0,
        assumptions=CRITERION_ASSUMPTIONS[criterion],
        required_allowables=CRITERION_REQUIRED_ALLOWABLES[criterion],
        provenance=provenance,
    )


@dataclass(frozen=True, slots=True)
class StrengthLibrary:
    """Allowables keyed by the exact material digest they belong to."""

    entries: tuple[PlyStrength, ...]

    def __post_init__(self) -> None:
        if not self.entries:
            raise DataUnavailable("STRENGTH_LIBRARY_REQUIRES_ENTRIES")
        digests = [entry.material_digest for entry in self.entries]
        if len(digests) != len(set(digests)):
            raise DataUnavailable("STRENGTH_LIBRARY_DUPLICATE_MATERIAL_DIGEST")

    def for_material(self, material_digest: str) -> PlyStrength:
        for entry in self.entries:
            if entry.material_digest == material_digest:
                return entry
        raise DataUnavailable(
            f"STRENGTH_ALLOWABLES_UNAVAILABLE_FOR_MATERIAL:{material_digest}"
        )

    def digests(self) -> tuple[str, ...]:
        return tuple(entry.material_digest for entry in self.entries)


@dataclass(frozen=True, slots=True)
class FirstPlyResult:
    """Laminate first-ply failure index across an ordered ply stack."""

    criterion: FailureCriterion
    index: float
    reserve_factor: float
    critical_ply_index: int
    mode: str
    ply_indices: tuple[float, ...]
    provenance: Provenance
    validity: Validity

    @property
    def failed(self) -> bool:
        return self.index >= 1.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "criterion": self.criterion.value,
            "index": self.index,
            "reserveFactor": self.reserve_factor,
            "failed": self.failed,
            "criticalPlyIndex": self.critical_ply_index,
            "mode": self.mode,
            "plyIndices": list(self.ply_indices),
            "validity": self.validity.as_dict(),
            "inputsHash": self.provenance.inputs_hash,
            "source": self.provenance.source.value,
        }


def _evaluate_stack(
    responses: tuple[PlyResponse, ...],
    strengths: StrengthLibrary,
    criterion: FailureCriterion,
    *,
    strain_limits: PlyStrainLimits | None,
    tsai_wu_f12_star: float | None,
) -> tuple[tuple[float, ...], FailureIndex, int]:
    indices: list[float] = []
    worst: FailureIndex | None = None
    worst_index = 0
    for position, response in enumerate(responses):
        strength = strengths.for_material(response.material_digest)
        stress = PlyStress(
            sigma_1_pa=response.sigma_1_pa,
            sigma_2_pa=response.sigma_2_pa,
            tau_12_pa=response.tau_12_pa,
            eps_1=response.eps_1,
            eps_2=response.eps_2,
            gamma_12=response.gamma_12,
        )
        result = evaluate_ply_failure(
            stress,
            strength,
            criterion,
            strain_limits=strain_limits,
            tsai_wu_f12_star=tsai_wu_f12_star,
        )
        indices.append(result.index)
        if worst is None or result.index > worst.index:
            worst = result
            worst_index = position
    assert worst is not None
    return tuple(indices), worst, worst_index


def first_ply_failure(
    analysis: LaminateAnalysis,
    load: LaminateLoad,
    strengths: StrengthLibrary,
    *,
    criterion: FailureCriterion = FailureCriterion.TSAI_WU,
    strain_limits: PlyStrainLimits | None = None,
    tsai_wu_f12_star: float | None = None,
) -> FirstPlyResult:
    """Scan every ply and return the governing first-ply failure index."""

    responses = ply_stresses(analysis, load)
    indices, worst, worst_index = _evaluate_stack(
        responses,
        strengths,
        criterion,
        strain_limits=strain_limits,
        tsai_wu_f12_star=tsai_wu_f12_star,
    )
    provenance = analytical_provenance(
        "first-ply-failure",
        {
            "laminate": analysis.laminate_identity,
            "laminateDigest": analysis.laminate_digest,
            "criterion": criterion.value,
            "load": load.as_dict(),
            "plyIndices": list(indices),
        },
        assumptions=(
            *CRITERION_ASSUMPTIONS[criterion],
            "first-ply failure is a laminate-level screen; it is not an isotropic FOS",
        ),
    )
    return FirstPlyResult(
        criterion=criterion,
        index=worst.index,
        reserve_factor=worst.reserve_factor,
        critical_ply_index=worst_index,
        mode=worst.mode,
        ply_indices=indices,
        provenance=provenance,
        validity=Validity(
            passed=worst.index < 1.0,
            checks={"first_ply_index_below_one": worst.index < 1.0},
            detail=f"first-ply:{analysis.laminate_identity}",
        ),
    )


@dataclass(frozen=True, slots=True)
class PlyDiscardPolicy:
    """Declared progressive ply-discard policy (opt-in)."""

    mode: str = "immediate"
    max_iterations: int = 20

    def __post_init__(self) -> None:
        if self.mode not in ("immediate", "maximum"):
            raise DataUnavailable("PLY_DISCARD_MODE_UNKNOWN")
        if self.max_iterations < 1:
            raise DataUnavailable("PLY_DISCARD_MAX_ITERATIONS_INVALID")


@dataclass(frozen=True, slots=True)
class ProgressiveResult:
    """Progressive first-ply-to-last-ply failure with explicit ply discard."""

    criterion: FailureCriterion
    first_ply_index: float
    last_ply_index: float
    first_failed_ply: int
    failed_plies: tuple[int, ...]
    iterations: int
    converged: bool
    provenance: Provenance
    validity: Validity

    def as_dict(self) -> dict[str, Any]:
        return {
            "criterion": self.criterion.value,
            "firstPlyIndex": self.first_ply_index,
            "lastPlyIndex": self.last_ply_index,
            "firstFailedPly": self.first_failed_ply,
            "failedPlies": list(self.failed_plies),
            "iterations": self.iterations,
            "converged": self.converged,
            "validity": self.validity.as_dict(),
            "inputsHash": self.provenance.inputs_hash,
            "source": self.provenance.source.value,
        }


def progressive_failure(
    analysis: LaminateAnalysis,
    load: LaminateLoad,
    strengths: StrengthLibrary,
    *,
    criterion: FailureCriterion = FailureCriterion.TSAI_WU,
    discard_policy: PlyDiscardPolicy | None = None,
    strain_limits: PlyStrainLimits | None = None,
    tsai_wu_f12_star: float | None = None,
    delta_temperature_k: float = 0.0,
) -> ProgressiveResult:
    """Discard failed plies and re-solve until no active ply exceeds one."""

    policy = discard_policy or PlyDiscardPolicy()
    count = len(analysis.plies)
    active = [True] * count
    first_index: float | None = None
    last_index = 0.0
    first_failed: int | None = None
    iteration = 0
    converged = False
    for step in range(1, policy.max_iterations + 1):
        iteration = step
        responses = ply_stresses_for(
            analysis.plies, load, active=tuple(active), delta_temperature_k=delta_temperature_k
        )
        active_positions = [i for i in range(count) if active[i]]
        stack = tuple(responses[i] for i in active_positions)
        if not stack:
            converged = True
            break
        indices, worst, worst_local = _evaluate_stack(
            stack,
            strengths,
            criterion,
            strain_limits=strain_limits,
            tsai_wu_f12_star=tsai_wu_f12_star,
        )
        last_index = worst.index
        if first_index is None:
            first_index = worst.index
            first_failed = active_positions[worst_local]
        failing = [
            active_positions[local]
            for local, index in enumerate(indices)
            if index >= 1.0
        ]
        if not failing:
            converged = True
            break
        if policy.mode == "maximum":
            failing = [active_positions[worst_local]]
        for position in failing:
            active[position] = False
    failed = tuple(i for i in range(count) if not active[i])
    provenance = analytical_provenance(
        "progressive-ply-failure",
        {
            "laminate": analysis.laminate_identity,
            "laminateDigest": analysis.laminate_digest,
            "criterion": criterion.value,
            "discardMode": policy.mode,
            "load": load.as_dict(),
            "deltaTemperatureK": delta_temperature_k,
            "failedPlies": list(failed),
        },
        assumptions=(
            *CRITERION_ASSUMPTIONS[criterion],
            "failed plies are discarded to negligible stiffness, not healed",
            "progressive analysis is declared opt-in; first-ply screening is preferred",
        ),
    )
    return ProgressiveResult(
        criterion=criterion,
        first_ply_index=1.0 if first_index is None else first_index,
        last_ply_index=last_index,
        first_failed_ply=-1 if first_failed is None else first_failed,
        failed_plies=failed,
        iterations=iteration,
        converged=converged,
        provenance=provenance,
        validity=Validity(
            passed=converged,
            checks={"progressive_converged": converged},
            detail=f"progressive:{analysis.laminate_identity}",
        ),
    )


def evaluate_interlaminar(stress: PlyStress, strength: PlyStrength) -> FailureIndex:
    """Interlaminar/delamination indicator; requires through-thickness allowables."""

    required = ("z_tension_pa", "z_compression_pa", "interlaminar_shear_pa")
    missing = [name for name in required if strength.value(name) is None]
    if missing:
        raise DataUnavailable(
            f"INTERLAMINAR_CRITERION_REQUIRES_ALLOWABLES:{','.join(missing)}"
        )
    if stress.sigma_3_pa is None or stress.tau_13_pa is None or stress.tau_23_pa is None:
        raise DataUnavailable("INTERLAMINAR_CRITERION_REQUIRES_THROUGH_THICKNESS_STRESS")
    z_t = strength.value("z_tension_pa")
    z_c = strength.value("z_compression_pa")
    s_il = strength.value("interlaminar_shear_pa")
    assert z_t is not None and z_c is not None and s_il is not None
    normal = _sign_allowable(z_t, z_c, stress.sigma_3_pa)
    index = (stress.sigma_3_pa / normal) ** 2 + (
        (stress.tau_13_pa**2 + stress.tau_23_pa**2) / (s_il * s_il)
    )
    provenance = analytical_provenance(
        "failure-interlaminar",
        {
            "materialDigest": strength.material_digest,
            "criterion": "interlaminar",
            "sigma3Pa": stress.sigma_3_pa,
            "tau13Pa": stress.tau_13_pa,
            "tau23Pa": stress.tau_23_pa,
        },
        assumptions=(
            "interlaminar/delamination indicator in out-of-plane normal+shear",
            "requires through-thickness and interlaminar shear allowables",
        ),
    )
    return FailureIndex(
        criterion=FailureCriterion.HASHIN,
        index=index,
        reserve_factor=_reserve(index, linear=False),
        mode="interlaminar",
        failed=index >= 1.0,
        assumptions=(
            "interlaminar/delamination indicator in out-of-plane normal+shear",
        ),
        required_allowables=required,
        provenance=provenance,
    )
