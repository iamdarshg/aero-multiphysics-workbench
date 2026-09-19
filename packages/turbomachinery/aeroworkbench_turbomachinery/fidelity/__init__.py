"""Rotating-gas fidelity ladder and multidisciplinary promotion policy (TURBO 07).

This subpackage reuses the shared optimization fidelity planner, the convergence
promotion gate, and the canonical turbomachinery architecture contracts. It adds
the rotating-gas-specific ladder, the physics-derived multi-physics dependency
graph, measured promotion signals, disagreement-aware ranking, warm-start
validity rules, and fail-closed native capability gating. Public API:

    from aeroworkbench_turbomachinery.fidelity import (
        LadderLevel,
        AnalysisKind,
        FidelityRung,
        RotatingGasFidelityLadder,
        default_rotating_gas_ladder,
        ladder_from_payload,
        ArchitectureFeatures,
        architecture_features,
        MultiphysicsDependencyGraph,
        MultiphysicsParticipant,
        default_multiphysics_graph,
        PromotionSignals,
        PromotionOutcome,
        plan_promotion,
        ParticipantGate,
        FinalValidation,
        validate_final,
        FidelityEvidence,
        CandidateFidelityLedger,
        RankingReport,
        RankedCandidate,
        rank_candidates,
        WarmStartKey,
        WarmStartAsset,
        WarmStartDecision,
        WarmStartPolicy,
        plan_warm_start,
        NativeCapabilityState,
        CapabilityStatus,
        NativeCapabilityGate,
        NativeReceipt,
        capability_status,
    )
"""

from .dependencies import (
    CONDITIONS,
    MultiphysicsDependencyGraph,
    MultiphysicsParticipant,
    default_multiphysics_graph,
)
from .evidence import (
    CandidateFidelityLedger,
    FidelityEvidence,
    RankedCandidate,
    RankingReport,
    rank_candidates,
)
from .features import ArchitectureFeatures, architecture_features
from .ladder import (
    AnalysisKind,
    FidelityRung,
    LadderLevel,
    RotatingGasFidelityLadder,
    default_rotating_gas_ladder,
    ladder_from_payload,
)
from .native import (
    CapabilityProbe,
    CapabilityStatus,
    NativeCapabilityGate,
    NativeCapabilityState,
    NativeReceipt,
    capability_status,
)
from .promotion import (
    FinalValidation,
    ParticipantGate,
    PromotionOutcome,
    plan_promotion,
    validate_final,
)
from .signals import PromotionSignals
from .warmstart import (
    WARM_START_RULES,
    WarmStartAsset,
    WarmStartDecision,
    WarmStartKey,
    WarmStartPolicy,
    plan_warm_start,
)

__all__ = [
    "AnalysisKind",
    "ArchitectureFeatures",
    "CONDITIONS",
    "CandidateFidelityLedger",
    "CapabilityProbe",
    "CapabilityStatus",
    "FidelityEvidence",
    "FidelityRung",
    "FinalValidation",
    "LadderLevel",
    "MultiphysicsDependencyGraph",
    "MultiphysicsParticipant",
    "NativeCapabilityGate",
    "NativeCapabilityState",
    "NativeReceipt",
    "ParticipantGate",
    "PromotionOutcome",
    "PromotionSignals",
    "RankedCandidate",
    "RankingReport",
    "RotatingGasFidelityLadder",
    "WARM_START_RULES",
    "WarmStartAsset",
    "WarmStartDecision",
    "WarmStartKey",
    "WarmStartPolicy",
    "architecture_features",
    "capability_status",
    "default_multiphysics_graph",
    "default_rotating_gas_ladder",
    "ladder_from_payload",
    "plan_promotion",
    "plan_warm_start",
    "rank_candidates",
    "validate_final",
]
