"""Fail-closed error taxonomy for physics-driven meshing.

Every failure mode is explicit: a structurally invalid mesh contract, a physics
resolution that cannot fit the declared budget, a missing native mesher, a
refinement loop that violates its quality or lineage gates, or a quality receipt
that cannot be trusted. No error path ever fabricates a mesh metric.
"""

from __future__ import annotations

__all__ = [
    "AdaptationError",
    "InsufficientResolutionError",
    "MeshBudgetError",
    "MeshContractError",
    "MeshQualityGateError",
    "MesherCapabilityUnavailable",
    "MeshingError",
]


class MeshingError(ValueError):
    """Base class for physics-driven meshing failures."""


class MeshContractError(MeshingError):
    """A mesh intent, resolution rule, target, budget, or revision is invalid."""


class InsufficientResolutionError(MeshingError):
    """Requested physics cannot fit the declared mesh budget without coarsening."""


class MeshBudgetError(MeshingError):
    """A declared mesh budget is structurally invalid or already exhausted."""


class MesherCapabilityUnavailable(MeshingError):
    """A requested native mesher capability is not wired; fail closed."""


class AdaptationError(MeshingError):
    """An adaptive-refinement revision broke lineage, budget, or quality gates."""


class MeshQualityGateError(MeshingError):
    """A measured mesh-quality gate failed and the mesh must not be accepted."""
