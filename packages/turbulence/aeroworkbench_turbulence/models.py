"""Model/fidelity policy: which turbulence model is valid where, and escalation.

The catalog is an explicit, provenance-backed ladder from laminar through
fully-turbulent RANS, transition-sensitive RANS, hybrid RANS/LES, LES, and DNS.
Selection is based on declared validity (Reynolds/Mach ranges, transition
support, wall-treatment compatibility, native requirement) and physics signals,
never on product names. Escalation is delegated to the generic fidelity planner
in :mod:`aeroworkbench_optimization`.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite
from typing import Any

from aeroworkbench_core.types import Provenance
from aeroworkbench_fluid_properties import SoftwareIdentity
from aeroworkbench_optimization import (
    FidelityImplementation,
    FidelityPlan,
    FidelitySignals,
    plan_fidelity,
)

from .contracts import (
    SOFTWARE_IDENTITY,
    TurbulenceFidelity,
    analytical_provenance,
)
from .errors import TurbulenceValidationError, TurbulenceValidityError
from .regimes import FlowRegime, FlowState, RegimeClassification, TransitionState
from .wall import WallTreatmentMode, WallTreatmentRequirement


class TurbulenceModel(StrEnum):
    """Concrete turbulence/transition closures the platform can select."""

    LAMINAR = "laminar"
    SPALART_ALLMARAS = "spalartAllmaras"
    K_EPSILON = "kEpsilon"
    K_OMEGA_SST = "kOmegaSST"
    TRANSITION_GAMMA_RETHETA = "gammaReTheta"
    TRANSITION_KKL_OMEGA = "kklOmega"
    SA_DDES = "spalartAllmarasDDES"
    WMLES = "wallModelledLES"
    LES_SMAGORINSKY = "lesSmagorinsky"
    DNS = "dns"


FIDELITY_RANK: dict[TurbulenceFidelity, int] = {
    TurbulenceFidelity.LAMINAR: 0,
    TurbulenceFidelity.RANS: 1,
    TurbulenceFidelity.TRANSITION_RANS: 2,
    TurbulenceFidelity.HYBRID_RANS_LES: 3,
    TurbulenceFidelity.LES: 4,
    TurbulenceFidelity.DNS: 5,
}


@dataclass(frozen=True, slots=True)
class ModelValidity:
    """Declared validity of one model: ranges, transition support, wall modes."""

    model: TurbulenceModel
    fidelity: TurbulenceFidelity
    min_reynolds: float
    max_reynolds: float
    max_mach: float
    supports_transition: bool
    wall_modes: frozenset[WallTreatmentMode]
    requires_native: bool
    source: str
    revision: str = "1"
    description: str = ""

    def __post_init__(self) -> None:
        if not self.source.strip() or not self.revision.strip():
            raise TurbulenceValidationError("MODEL_VALIDITY_SOURCE_REQUIRED")
        if not isfinite(self.min_reynolds) or not isfinite(self.max_reynolds):
            raise TurbulenceValidationError("MODEL_REYNOLDS_BOUNDS_NONFINITE")
        if not 0.0 <= self.min_reynolds < self.max_reynolds:
            raise TurbulenceValidationError("MODEL_REYNOLDS_BOUNDS_INVALID")
        if not isfinite(self.max_mach) or self.max_mach <= 0.0:
            raise TurbulenceValidationError("MODEL_MACH_BOUND_INVALID")
        if not self.wall_modes:
            raise TurbulenceValidationError("MODEL_WALL_MODES_REQUIRED")

    def valid_for(self, *, reynolds: float, mach: float) -> bool:
        return (
            self.min_reynolds <= reynolds <= self.max_reynolds and mach <= self.max_mach
        )

    def near_limit(self, *, reynolds: float, mach: float, margin: float = 0.1) -> bool:
        re_span = self.max_reynolds - self.min_reynolds
        re_margin = margin * re_span
        near_re = (
            reynolds <= self.min_reynolds + re_margin
            or reynolds >= self.max_reynolds - re_margin
        )
        return near_re or mach >= self.max_mach * (1.0 - margin)

    def canonical(self) -> dict[str, Any]:
        return {
            "model": self.model.value,
            "fidelity": self.fidelity.value,
            "minReynolds": self.min_reynolds,
            "maxReynolds": self.max_reynolds,
            "maxMach": self.max_mach,
            "supportsTransition": self.supports_transition,
            "wallModes": sorted(mode.value for mode in self.wall_modes),
            "requiresNative": self.requires_native,
            "revision": self.revision,
            "source": self.source,
            "description": self.description,
        }


_RAS_WALLS = frozenset(
    {
        WallTreatmentMode.WALL_FUNCTION,
        WallTreatmentMode.WALL_RESOLVED,
        WallTreatmentMode.LOW_REYNOLDS,
        WallTreatmentMode.ADAPTIVE,
    }
)

MODEL_CATALOG: dict[TurbulenceModel, ModelValidity] = {
    TurbulenceModel.LAMINAR: ModelValidity(
        model=TurbulenceModel.LAMINAR,
        fidelity=TurbulenceFidelity.LAMINAR,
        min_reynolds=1.0,
        max_reynolds=1.0e6,
        max_mach=0.6,
        supports_transition=False,
        wall_modes=frozenset(
            {
                WallTreatmentMode.NONE,
                WallTreatmentMode.WALL_RESOLVED,
                WallTreatmentMode.LOW_REYNOLDS,
            }
        ),
        requires_native=False,
        source="laminar Navier-Stokes; no turbulence closure",
        description="laminar flow with no turbulence model",
    ),
    TurbulenceModel.SPALART_ALLMARAS: ModelValidity(
        model=TurbulenceModel.SPALART_ALLMARAS,
        fidelity=TurbulenceFidelity.RANS,
        min_reynolds=1.0e4,
        max_reynolds=1.0e8,
        max_mach=1.5,
        supports_transition=False,
        wall_modes=_RAS_WALLS,
        requires_native=False,
        source="Spalart-Allmaras one-equation RANS (declared range)",
        description="one-equation fully turbulent RANS",
    ),
    TurbulenceModel.K_EPSILON: ModelValidity(
        model=TurbulenceModel.K_EPSILON,
        fidelity=TurbulenceFidelity.RANS,
        min_reynolds=1.0e4,
        max_reynolds=1.0e8,
        max_mach=1.5,
        supports_transition=False,
        wall_modes=frozenset(
            {WallTreatmentMode.WALL_FUNCTION, WallTreatmentMode.ADAPTIVE}
        ),
        requires_native=False,
        source="standard k-epsilon RANS with wall functions (declared range)",
        description="two-equation fully turbulent RANS with wall functions",
    ),
    TurbulenceModel.K_OMEGA_SST: ModelValidity(
        model=TurbulenceModel.K_OMEGA_SST,
        fidelity=TurbulenceFidelity.RANS,
        min_reynolds=1.0e3,
        max_reynolds=1.0e8,
        max_mach=2.5,
        supports_transition=False,
        wall_modes=_RAS_WALLS,
        requires_native=False,
        source="Menter k-omega SST RANS (declared range)",
        description="two-equation fully turbulent RANS with near-wall blending",
    ),
    TurbulenceModel.TRANSITION_GAMMA_RETHETA: ModelValidity(
        model=TurbulenceModel.TRANSITION_GAMMA_RETHETA,
        fidelity=TurbulenceFidelity.TRANSITION_RANS,
        min_reynolds=1.0e4,
        max_reynolds=1.0e7,
        max_mach=0.6,
        supports_transition=True,
        wall_modes=frozenset(
            {
                WallTreatmentMode.WALL_RESOLVED,
                WallTreatmentMode.LOW_REYNOLDS,
                WallTreatmentMode.ADAPTIVE,
            }
        ),
        requires_native=False,
        source="Langtry-Menter gamma-Re_theta transition RANS (declared range)",
        description="transition-sensitive four-equation RANS closure",
    ),
    TurbulenceModel.TRANSITION_KKL_OMEGA: ModelValidity(
        model=TurbulenceModel.TRANSITION_KKL_OMEGA,
        fidelity=TurbulenceFidelity.TRANSITION_RANS,
        min_reynolds=1.0e3,
        max_reynolds=5.0e6,
        max_mach=0.6,
        supports_transition=True,
        wall_modes=frozenset(
            {WallTreatmentMode.WALL_RESOLVED, WallTreatmentMode.LOW_REYNOLDS}
        ),
        requires_native=False,
        source="Walters-Cokljat k-kL-omega transition RANS (declared range)",
        description="three-equation transition-sensitive RANS closure",
    ),
    TurbulenceModel.SA_DDES: ModelValidity(
        model=TurbulenceModel.SA_DDES,
        fidelity=TurbulenceFidelity.HYBRID_RANS_LES,
        min_reynolds=1.0e5,
        max_reynolds=1.0e9,
        max_mach=2.0,
        supports_transition=False,
        wall_modes=frozenset(
            {
                WallTreatmentMode.WALL_RESOLVED,
                WallTreatmentMode.LOW_REYNOLDS,
                WallTreatmentMode.ADAPTIVE,
            }
        ),
        requires_native=True,
        source="Spalart-Allmaras DDES hybrid RANS/LES (native engine required)",
        description="delayed detached-eddy hybrid closure",
    ),
    TurbulenceModel.WMLES: ModelValidity(
        model=TurbulenceModel.WMLES,
        fidelity=TurbulenceFidelity.HYBRID_RANS_LES,
        min_reynolds=1.0e6,
        max_reynolds=1.0e10,
        max_mach=3.0,
        supports_transition=False,
        wall_modes=frozenset(
            {
                WallTreatmentMode.WALL_FUNCTION,
                WallTreatmentMode.WALL_RESOLVED,
                WallTreatmentMode.ADAPTIVE,
            }
        ),
        requires_native=True,
        source="wall-modelled LES hybrid (native engine required)",
        description="wall-modelled large-eddy hybrid closure",
    ),
    TurbulenceModel.LES_SMAGORINSKY: ModelValidity(
        model=TurbulenceModel.LES_SMAGORINSKY,
        fidelity=TurbulenceFidelity.LES,
        min_reynolds=1.0e5,
        max_reynolds=1.0e10,
        max_mach=3.0,
        supports_transition=False,
        wall_modes=frozenset(
            {
                WallTreatmentMode.WALL_RESOLVED,
                WallTreatmentMode.LOW_REYNOLDS,
                WallTreatmentMode.ADAPTIVE,
            }
        ),
        requires_native=True,
        source="Smagorinsky LES (native engine required)",
        description="resolved large-eddy simulation closure",
    ),
    TurbulenceModel.DNS: ModelValidity(
        model=TurbulenceModel.DNS,
        fidelity=TurbulenceFidelity.DNS,
        min_reynolds=1.0e3,
        max_reynolds=1.0e8,
        max_mach=5.0,
        supports_transition=True,
        wall_modes=frozenset(
            {WallTreatmentMode.WALL_RESOLVED, WallTreatmentMode.LOW_REYNOLDS}
        ),
        requires_native=True,
        source="direct numerical simulation (native engine required)",
        description="all turbulence scales resolved",
    ),
}


@dataclass(frozen=True, slots=True)
class TurbulencePolicy:
    """Declared policy bounding which models may be selected."""

    allow_transition_models: bool = True
    allow_hybrid_models: bool = True
    allow_les: bool = True
    allow_native: bool = True
    max_fidelity: TurbulenceFidelity = TurbulenceFidelity.DNS

    def allows(self, validity: ModelValidity) -> bool:
        if validity.fidelity is TurbulenceFidelity.TRANSITION_RANS:
            return self.allow_transition_models
        if validity.fidelity is TurbulenceFidelity.HYBRID_RANS_LES:
            return self.allow_hybrid_models
        if validity.fidelity in (TurbulenceFidelity.LES, TurbulenceFidelity.DNS):
            return self.allow_les
        return True

    def canonical(self) -> dict[str, Any]:
        return {
            "allowTransitionModels": self.allow_transition_models,
            "allowHybridModels": self.allow_hybrid_models,
            "allowLes": self.allow_les,
            "allowNative": self.allow_native,
            "maxFidelity": self.max_fidelity.value,
        }


DEFAULT_TURBULENCE_POLICY = TurbulencePolicy()


@dataclass(frozen=True, slots=True)
class ModelSelection:
    """The selected model with its validity, wall need, and escalation signals."""

    model: TurbulenceModel
    validity: ModelValidity
    fidelity: TurbulenceFidelity
    regime: FlowRegime
    transition_model_required: bool
    wall_treatment_required: WallTreatmentMode | None
    near_limit: bool
    escalation_reasons: tuple[str, ...]
    provenance: Provenance
    software: SoftwareIdentity = SOFTWARE_IDENTITY

    def canonical(self) -> dict[str, Any]:
        return {
            "model": self.model.value,
            "fidelity": self.fidelity.value,
            "regime": self.regime.value,
            "transitionModelRequired": self.transition_model_required,
            "wallTreatmentRequired": (
                self.wall_treatment_required.value
                if self.wall_treatment_required is not None
                else None
            ),
            "nearLimit": self.near_limit,
            "escalationReasons": list(self.escalation_reasons),
            "validity": self.validity.canonical(),
            "units": {"reynoldsNumber": "1", "machNumber": "1"},
            "inputsHash": self.provenance.inputs_hash,
            "source": self.provenance.source.value,
            "software": self.software.canonical(),
        }


def model_validity(model: TurbulenceModel) -> ModelValidity:
    """Return the declared validity for a model or fail closed."""
    try:
        return MODEL_CATALOG[model]
    except KeyError:
        raise TurbulenceValidationError(f"MODEL_NOT_DECLARED:{model.value}") from None


def _transition_required(flow: FlowState, classification: RegimeClassification) -> bool:
    if flow.transition_state is TransitionState.FULLY_TURBULENT:
        return False
    if classification.regime is FlowRegime.TRANSITIONAL:
        return True
    return flow.transition_state in (
        TransitionState.NATURAL,
        TransitionState.FORCED,
        TransitionState.LAMINAR_SEPARATION,
    )


_CATALOG_ORDER: dict[TurbulenceModel, int] = {
    model: index for index, model in enumerate(MODEL_CATALOG)
}


def _ordered_models() -> list[tuple[TurbulenceModel, ModelValidity]]:
    return sorted(
        MODEL_CATALOG.items(),
        key=lambda item: (FIDELITY_RANK[item[1].fidelity], _CATALOG_ORDER[item[0]]),
    )


def _candidates(
    flow: FlowState,
    classification: RegimeClassification,
    *,
    policy: TurbulencePolicy,
    wall_requirement: WallTreatmentRequirement | None,
    fidelity: TurbulenceFidelity | None,
) -> list[tuple[TurbulenceModel, ModelValidity]]:
    candidates: list[tuple[TurbulenceModel, ModelValidity]] = []
    for model, validity in _ordered_models():
        if fidelity is not None and validity.fidelity is not fidelity:
            continue
        if not policy.allows(validity):
            continue
        if validity.requires_native and not policy.allow_native:
            continue
        if FIDELITY_RANK[validity.fidelity] > FIDELITY_RANK[policy.max_fidelity]:
            continue
        if validity.fidelity is TurbulenceFidelity.LAMINAR:
            if classification.regime is not FlowRegime.LAMINAR:
                continue
        elif classification.regime is FlowRegime.LAMINAR:
            continue
        if not validity.valid_for(
            reynolds=flow.reynolds_number, mach=flow.mach_number
        ):
            continue
        if wall_requirement is not None and wall_requirement.mode not in validity.wall_modes:
            continue
        candidates.append((model, validity))
    return candidates


def _selection(
    flow: FlowState,
    classification: RegimeClassification,
    model: TurbulenceModel,
    validity: ModelValidity,
    *,
    policy: TurbulencePolicy,
    transition_required: bool,
    escalation_reasons: tuple[str, ...],
) -> ModelSelection:
    near_limit = validity.near_limit(
        reynolds=flow.reynolds_number, mach=flow.mach_number
    )
    reasons = list(escalation_reasons)
    if near_limit:
        reasons.append("NEAR_MODEL_VALIDITY_LIMIT")
    if validity.requires_native:
        reasons.append("NATIVE_MODEL_REQUIRED")
    provenance = analytical_provenance(
        "turbulence.model.selection",
        {
            "flow": flow.canonical(),
            "regime": classification.regime.value,
            "policy": policy.canonical(),
            "model": validity.canonical(),
        },
        f"model source: {validity.source}",
        "selection follows declared validity and physics signals",
    )
    return ModelSelection(
        model=model,
        validity=validity,
        fidelity=validity.fidelity,
        regime=classification.regime,
        transition_model_required=transition_required,
        wall_treatment_required=None,
        near_limit=near_limit,
        escalation_reasons=tuple(reasons),
        provenance=provenance,
    )


def select_turbulence_model(
    flow: FlowState,
    classification: RegimeClassification,
    *,
    policy: TurbulencePolicy = DEFAULT_TURBULENCE_POLICY,
    wall_requirement: WallTreatmentRequirement | None = None,
) -> ModelSelection:
    """Select the lowest-fidelity model valid for the declared flow state.

    Transition-sensitive models are required for a transitional state; when the
    policy forbids them the selection falls back to the lowest valid model and
    records the reason so the caller can escalate.
    """
    transition_required = _transition_required(flow, classification)
    candidates = _candidates(
        flow,
        classification,
        policy=policy,
        wall_requirement=wall_requirement,
        fidelity=None,
    )
    if not candidates:
        raise TurbulenceValidityError(
            f"NO_VALID_TURBULENCE_MODEL:Re={flow.reynolds_number:.6g}:"
            f"Ma={flow.mach_number:.6g}:{classification.regime.value}"
        )
    reasons: list[str] = []
    pool = candidates
    if transition_required:
        transition_pool = [
            item
            for item in candidates
            if item[1].fidelity is TurbulenceFidelity.TRANSITION_RANS
        ]
        if transition_pool:
            pool = transition_pool
        else:
            reasons.append("TRANSITION_MODEL_UNAVAILABLE")
    model, validity = pool[0]
    return _selection(
        flow,
        classification,
        model,
        validity,
        policy=policy,
        transition_required=transition_required,
        escalation_reasons=tuple(reasons),
    )


def select_turbulence_model_for_fidelity(
    flow: FlowState,
    classification: RegimeClassification,
    *,
    fidelity: TurbulenceFidelity,
    policy: TurbulencePolicy = DEFAULT_TURBULENCE_POLICY,
    wall_requirement: WallTreatmentRequirement | None = None,
) -> ModelSelection:
    """Select a model restricted to one fidelity rung (used after escalation)."""
    transition_required = _transition_required(flow, classification)
    candidates = _candidates(
        flow,
        classification,
        policy=policy,
        wall_requirement=wall_requirement,
        fidelity=fidelity,
    )
    if not candidates:
        raise TurbulenceValidityError(
            f"NO_VALID_MODEL_AT_FIDELITY:{fidelity.value}:Re={flow.reynolds_number:.6g}"
        )
    model, validity = candidates[0]
    return _selection(
        flow,
        classification,
        model,
        validity,
        policy=policy,
        transition_required=transition_required,
        escalation_reasons=(),
    )


def fidelity_implementations(
    policy: TurbulencePolicy = DEFAULT_TURBULENCE_POLICY,
) -> tuple[FidelityImplementation, ...]:
    """Build a contiguous rank ladder of policy-allowed fidelity rungs."""
    fidelities = [
        fidelity
        for fidelity in sorted(FIDELITY_RANK, key=lambda item: FIDELITY_RANK[item])
        if any(
            policy.allows(validity)
            and (policy.allow_native or not validity.requires_native)
            and validity.fidelity is fidelity
            for validity in MODEL_CATALOG.values()
        )
    ]
    implementations: list[FidelityImplementation] = []
    for rank, fidelity in enumerate(fidelities):
        wall_modes = sorted(
            {
                mode.value
                for validity in MODEL_CATALOG.values()
                if validity.fidelity is fidelity
                for mode in validity.wall_modes
            }
        )
        implementations.append(
            FidelityImplementation(
                name=fidelity.value,
                rank=rank,
                cost=float(rank + 1) * 10.0,
                capabilities=tuple(wall_modes),
                description=f"turbulence fidelity rung {fidelity.value}",
            )
        )
    return tuple(implementations)


def plan_fidelity_escalation(
    selection: ModelSelection,
    flow: FlowState,
    *,
    disagreement: float,
    sensitivity: float = 0.0,
    convergence_difficulty: float = 0.0,
    mesh_dependence: float = 0.0,
    timestep_dependence: float = 0.0,
    maturity: float = 0.5,
    constraint_margin: float = 1.0,
    cost_budget: float = 1.0e9,
    policy: TurbulencePolicy = DEFAULT_TURBULENCE_POLICY,
) -> FidelityPlan:
    """Delegate an escalation decision to the generic fidelity planner."""
    implementations = fidelity_implementations(policy)
    names = [item.name for item in implementations]
    current = selection.fidelity.value
    if current not in names:
        raise TurbulenceValidityError(f"CURRENT_FIDELITY_NOT_ALLOWED:{current}")
    validity_ok: dict[str, bool] = {}
    for fidelity in FIDELITY_RANK:
        models = [
            validity
            for validity in MODEL_CATALOG.values()
            if validity.fidelity is fidelity
        ]
        validity_ok[fidelity.value] = any(
            policy.allows(validity)
            and (policy.allow_native or not validity.requires_native)
            and validity.valid_for(
                reynolds=flow.reynolds_number, mach=flow.mach_number
            )
            for validity in models
        )
    signals = FidelitySignals(
        question=flow.label,
        maturity=maturity,
        constraint_margin=constraint_margin,
        disagreement=disagreement,
        sensitivity=sensitivity,
        convergence_difficulty=convergence_difficulty,
        mesh_dependence=mesh_dependence,
        timestep_dependence=timestep_dependence,
        resonance_proximity=1.0,
        validity_ok=validity_ok,
        cost_budget=cost_budget,
    )
    return plan_fidelity(current, implementations, signals)


__all__ = [
    "DEFAULT_TURBULENCE_POLICY",
    "FIDELITY_RANK",
    "MODEL_CATALOG",
    "ModelSelection",
    "ModelValidity",
    "TurbulenceModel",
    "TurbulencePolicy",
    "fidelity_implementations",
    "model_validity",
    "plan_fidelity_escalation",
    "select_turbulence_model",
    "select_turbulence_model_for_fidelity",
]
