"""Physics-driven meshing: intent, wall resolution, refinement, and budget.

This package turns meshing from a mostly geometric operation into a
physics-aware one. It is product-neutral and reuses the shared mesh contracts
(``ZoneSpec``/``InterfaceSpec``/``MeshSpec``/``SemanticMeshRequest``) and the
native Gmsh path without duplicating them.

Public API (other workstreams import these exact paths):

    from aeroworkbench_meshing import (
        PhysicsIntent, PhysicsIntentKind, PhysicsState, FlowRegime,
        intents_from_physics, intents_from_blade_rows, intents_from_propeller,
        intent_digest,
        FlowReference, WallResolutionTarget, BoundaryLayerPlan,
        plan_boundary_layer, flow_reference_from_state,
        FeatureGeometry, ResolutionConfig, ResolutionRule, ResolutionDerivation,
        derive_local_size, resolution_rules_from_intents, required_min_size_mm,
        MeshBudget, RegionResolution, BudgetAssessment, assess_budget,
        require_feasible, estimate_cells,
        ErrorIndicator, IndicatorKind, MeshRevision, AdaptationPolicy,
        AdaptationResult, adapt, next_revision,
        MeshQualityReceipt, RegionCellCount, InterfaceQuality,
        build_quality_receipt,
        MeshUpdateDecision, decide_physics_mesh_update,
        MeshPlan, MeshPlanRequest, plan_physics_mesh, mesh_independence_levels,
        MesherCapability, NativeMeshResult, probe_mesher, require_native_mesher,
        mesh_box_native, build_native_mesh_physics,
        ResultEnvelope, SoftwareIdentity, Validity, MeshFidelity,
        analytical_envelope, native_envelope,
        MeshingError, MeshContractError, InsufficientResolutionError,
        MeshBudgetError, MesherCapabilityUnavailable, AdaptationError,
        MeshQualityGateError,
    )

Every plan and receipt carries source, fidelity, units, validity, an input
hash, software identity, and provenance. Native meshing is capability-gated and
fails closed; requested physics that cannot fit the budget returns an explicit
insufficient-resolution state instead of silently coarsening.
"""

from .adaptation import (
    AdaptationPolicy,
    AdaptationResult,
    ErrorIndicator,
    IndicatorKind,
    MeshRevision,
    adapt,
    adaptation_policy_from_budget,
    next_revision,
)
from .boundary_layer import (
    BoundaryLayerPlan,
    FlowReference,
    WallResolutionTarget,
    flow_reference_from_state,
    layer_heights_mm,
    plan_boundary_layer,
    total_thickness_mm,
)
from .budget import (
    BudgetAssessment,
    MeshBudget,
    RegionResolution,
    assess_budget,
    estimate_cells,
    require_feasible,
)
from .contracts import (
    MESH_SCHEMA_VERSION,
    SOFTWARE_IDENTITY,
    SOFTWARE_VERSION,
    MeshFidelity,
    ResultEnvelope,
    SoftwareIdentity,
    Validity,
    analytical_envelope,
    content_digest,
    native_envelope,
)
from .errors import (
    AdaptationError,
    InsufficientResolutionError,
    MeshBudgetError,
    MeshContractError,
    MesherCapabilityUnavailable,
    MeshingError,
    MeshQualityGateError,
)
from .intents import (
    FlowRegime,
    PhysicsIntent,
    PhysicsIntentKind,
    PhysicsState,
    intent_digest,
    intents_from_blade_rows,
    intents_from_physics,
    intents_from_propeller,
)
from .native import (
    MesherCapability,
    NativeMeshResult,
    build_native_mesh_physics,
    mesh_box_native,
    probe_mesher,
    require_native_mesher,
)
from .planner import (
    MeshPlan,
    MeshPlanRequest,
    mesh_independence_levels,
    plan_physics_mesh,
)
from .quality import (
    InterfaceQuality,
    MeshQualityReceipt,
    RegionCellCount,
    build_quality_receipt,
)
from .resolution import (
    FeatureGeometry,
    ResolutionConfig,
    ResolutionDerivation,
    ResolutionRule,
    derive_local_size,
    required_min_size_mm,
    resolution_rules_from_intents,
)
from .update import MeshUpdateDecision, decide_physics_mesh_update

__all__ = [
    "MESH_SCHEMA_VERSION",
    "SOFTWARE_IDENTITY",
    "SOFTWARE_VERSION",
    "AdaptationError",
    "AdaptationPolicy",
    "AdaptationResult",
    "BoundaryLayerPlan",
    "BudgetAssessment",
    "ErrorIndicator",
    "FeatureGeometry",
    "FlowReference",
    "FlowRegime",
    "IndicatorKind",
    "InsufficientResolutionError",
    "InterfaceQuality",
    "MeshBudget",
    "MeshBudgetError",
    "MeshContractError",
    "MeshFidelity",
    "MeshPlan",
    "MeshPlanRequest",
    "MeshQualityGateError",
    "MeshQualityReceipt",
    "MeshRevision",
    "MeshUpdateDecision",
    "MesherCapability",
    "MesherCapabilityUnavailable",
    "MeshingError",
    "NativeMeshResult",
    "PhysicsIntent",
    "PhysicsIntentKind",
    "PhysicsState",
    "RegionCellCount",
    "RegionResolution",
    "ResolutionConfig",
    "ResolutionDerivation",
    "ResolutionRule",
    "ResultEnvelope",
    "SoftwareIdentity",
    "Validity",
    "WallResolutionTarget",
    "adapt",
    "adaptation_policy_from_budget",
    "analytical_envelope",
    "assess_budget",
    "build_native_mesh_physics",
    "build_quality_receipt",
    "content_digest",
    "decide_physics_mesh_update",
    "derive_local_size",
    "estimate_cells",
    "flow_reference_from_state",
    "intent_digest",
    "intents_from_blade_rows",
    "intents_from_physics",
    "intents_from_propeller",
    "layer_heights_mm",
    "mesh_box_native",
    "mesh_independence_levels",
    "native_envelope",
    "next_revision",
    "plan_boundary_layer",
    "plan_physics_mesh",
    "probe_mesher",
    "require_feasible",
    "require_native_mesher",
    "required_min_size_mm",
    "resolution_rules_from_intents",
    "total_thickness_mm",
]
