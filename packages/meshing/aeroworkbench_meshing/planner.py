"""Physics-driven mesh planning that ties intent, resolution, budget, and BL.

:func:`plan_physics_mesh` assembles a :class:`MeshPlan` from a shared
:class:`MeshSpec`, a :class:`PhysicsState`, generic intents, feature geometry,
an optional wall-resolution target, and a :class:`MeshBudget`. The plan carries
an analytical provenance envelope, a deterministic digest, and an explicit
budget verdict. When the requested physics cannot fit the budget it returns an
``insufficient_resolution`` state and never coarsens the request; callers can
fail closed with :meth:`MeshPlan.require_feasible`.
"""

from __future__ import annotations

from dataclasses import dataclass

from aeroworkbench_convergence import RefinementLevel
from aeroworkbench_mesh import MeshSpec, SemanticTopologyReceipt, mesh_spec_digest

from .boundary_layer import (
    BoundaryLayerPlan,
    FlowReference,
    WallResolutionTarget,
    flow_reference_from_state,
    plan_boundary_layer,
)
from .budget import (
    BudgetAssessment,
    MeshBudget,
    RegionResolution,
    assess_budget,
    require_feasible,
)
from .contracts import ResultEnvelope, Validity, analytical_envelope, content_digest
from .errors import InsufficientResolutionError, MeshContractError
from .intents import PhysicsIntent, PhysicsState, intent_digest, intents_from_physics
from .resolution import (
    FeatureGeometry,
    ResolutionConfig,
    ResolutionRule,
    required_min_size_mm,
    resolution_rules_from_intents,
)

__all__ = [
    "MeshPlan",
    "MeshPlanRequest",
    "mesh_independence_levels",
    "plan_physics_mesh",
]


@dataclass(frozen=True, slots=True)
class MeshPlanRequest:
    """All declared inputs for one physics-driven mesh plan."""

    name: str
    spec: MeshSpec
    physics: PhysicsState
    budget: MeshBudget
    region_volumes_mm3: tuple[tuple[str, float], ...]
    topology: SemanticTopologyReceipt | None = None
    extra_intents: tuple[PhysicsIntent, ...] = ()
    features: tuple[tuple[str, FeatureGeometry], ...] = ()
    wall_resolution: WallResolutionTarget | None = None
    flow_reference: FlowReference | None = None
    curvature_radius_mm: float | None = None
    clearance_mm: float | None = None
    resolution_config: ResolutionConfig | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise MeshContractError("MESH_PLAN_NAME_REQUIRED")
        if not self.region_volumes_mm3:
            raise MeshContractError("MESH_PLAN_NEEDS_REGION_VOLUMES")
        for region, volume in self.region_volumes_mm3:
            if not region.strip():
                raise MeshContractError("MESH_PLAN_REGION_NAME_REQUIRED")
            if volume <= 0.0:
                raise MeshContractError(f"MESH_PLAN_REGION_VOLUME_INVALID:{region}")


@dataclass(frozen=True, slots=True)
class MeshPlan:
    """A physics-driven mesh plan with provenance and a budget verdict."""

    name: str
    spec_digest: str
    dimension: int
    intents: tuple[PhysicsIntent, ...]
    resolution_rules: tuple[ResolutionRule, ...]
    boundary_layer: BoundaryLayerPlan | None
    budget: BudgetAssessment
    required_min_size_mm: float
    per_region_sizes_mm: tuple[tuple[str, float], ...]
    estimated_cells: int
    validity: Validity
    envelope: ResultEnvelope
    digest: str

    @property
    def feasible(self) -> bool:
        return self.budget.feasible and (
            self.boundary_layer is None or self.boundary_layer.valid
        )

    def require_feasible(self) -> None:
        if self.boundary_layer is not None and not self.boundary_layer.valid:
            raise MeshContractError(
                "BOUNDARY_LAYER_INVALID:"
                + ",".join(self.boundary_layer.limited_by)
                + (" collision" if self.boundary_layer.collision else "")
            )
        require_feasible(self.budget)

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "specDigest": self.spec_digest,
            "dimension": self.dimension,
            "intents": [item.as_dict() for item in self.intents],
            "resolutionRules": [item.as_dict() for item in self.resolution_rules],
            "boundaryLayer": None if self.boundary_layer is None else self.boundary_layer.as_dict(),
            "budget": self.budget.as_dict(),
            "requiredMinSizeMm": self.required_min_size_mm,
            "perRegionSizesMm": {region: size for region, size in self.per_region_sizes_mm},
            "estimatedCells": self.estimated_cells,
            "validity": self.validity.canonical(),
            "digest": self.digest,
        }


def _merge_intents(
    derived: tuple[PhysicsIntent, ...], extra: tuple[PhysicsIntent, ...]
) -> tuple[PhysicsIntent, ...]:
    merged: dict[tuple[str, tuple[str, ...]], PhysicsIntent] = {}
    for intent in (*derived, *extra):
        merged.setdefault((intent.kind.value, intent.semantic_keys), intent)
    return tuple(
        sorted(merged.values(), key=lambda item: (item.kind.value, item.semantic_keys))
    )


def _region_size(
    region: str,
    rules: tuple[ResolutionRule, ...],
    topology: SemanticTopologyReceipt | None,
    base_size_mm: float,
) -> float:
    if topology is None:
        return base_size_mm
    keys = {entity.semantic_key for entity in topology.entities if entity.region == region}
    sizes = [rule.size_mm for rule in rules if set(rule.semantic_keys) & keys]
    return min(sizes) if sizes else base_size_mm


def plan_physics_mesh(request: MeshPlanRequest) -> MeshPlan:
    """Assemble a physics-driven mesh plan from declared typed inputs."""

    spec = request.spec
    derived = (
        intents_from_physics(request.physics, request.topology)
        if request.topology is not None
        else ()
    )
    intents = _merge_intents(derived, request.extra_intents)
    features = dict(request.features)
    rules = resolution_rules_from_intents(
        intents,
        features,
        base_size_mm=spec.base_size_mm,
        min_size_mm=spec.min_size_mm,
        config=request.resolution_config,
    )
    required_min = required_min_size_mm(rules, fallback_mm=spec.base_size_mm)

    reference = request.flow_reference or flow_reference_from_state(request.physics)
    boundary_layer: BoundaryLayerPlan | None = None
    if request.wall_resolution is not None:
        boundary_layer = plan_boundary_layer(
            request.wall_resolution,
            reference=reference,
            curvature_radius_mm=request.curvature_radius_mm,
            clearance_mm=request.clearance_mm,
        )

    per_region = tuple(
        (
            region,
            _region_size(region, rules, request.topology, spec.base_size_mm),
        )
        for region, _ in request.region_volumes_mm3
    )
    resolutions = tuple(
        RegionResolution(region, size, volume)
        for (region, volume), (_, size) in zip(
            request.region_volumes_mm3, per_region, strict=True
        )
    )
    assessment = assess_budget(
        resolutions,
        required_min_size_mm=required_min,
        budget=request.budget,
        base_size_mm=spec.base_size_mm,
        dimension=spec.dimension,
        floor_size_mm=spec.min_size_mm,
    )

    checks = {
        "boundary_layer_valid": boundary_layer is None or boundary_layer.valid,
        "budget_feasible": assessment.feasible,
        "resolution_at_or_above_floor": not any(rule.below_floor for rule in rules),
    }
    validity = Validity(
        passed=all(checks.values()),
        checks=checks,
        detail=assessment.state,
    )
    spec_digest = mesh_spec_digest(spec)
    payload = {
        "name": request.name,
        "specDigest": spec_digest,
        "dimension": spec.dimension,
        "physics": request.physics.as_dict(),
        "intentDigest": intent_digest(intents),
        "rules": [rule.as_dict() for rule in rules],
        "requiredMinSizeMm": required_min,
        "perRegionSizesMm": {region: size for region, size in per_region},
        "budgetState": assessment.state,
    }
    envelope = analytical_envelope(
        model="physics-mesh-plan",
        inputs=payload,
        units=(("length", "mm"), ("dimensionless", "1")),
        validity=validity,
        assumptions=(
            "resolution derived from declared physics and feature scales",
            "budget feasibility estimated analytically; no mesh was generated",
        ),
    )
    return MeshPlan(
        name=request.name,
        spec_digest=spec_digest,
        dimension=spec.dimension,
        intents=intents,
        resolution_rules=rules,
        boundary_layer=boundary_layer,
        budget=assessment,
        required_min_size_mm=required_min,
        per_region_sizes_mm=per_region,
        estimated_cells=assessment.estimated_cells,
        validity=validity,
        envelope=envelope,
        digest=content_digest(payload),
    )


def mesh_independence_levels(
    plan: MeshPlan, *, factors: tuple[float, ...] = (1.0, 0.7, 0.5)
) -> tuple[RefinementLevel, ...]:
    """Build a coarse-to-fine mesh ladder for GEN 12 independence studies."""

    if len(factors) < 2:
        raise InsufficientResolutionError("MESH_INDEPENDENCE_NEEDS_TWO_LEVELS")
    ordered = sorted(factors, reverse=True)
    for previous, current in zip(ordered, ordered[1:], strict=False):
        if current >= previous:
            raise InsufficientResolutionError("MESH_INDEPENDENCE_FACTORS_NOT_DECREASING")
    return tuple(
        RefinementLevel(
            name=f"{plan.name}-L{index}",
            resolution=plan.required_min_size_mm * factor,
            declared=(("estimatedCells", float(plan.estimated_cells)),),
        )
        for index, factor in enumerate(ordered)
    )
