"""Requirements compiler and physics-based initial vehicle synthesis (AIRFRAME 06).

The compiler normalizes typed mission/performance/constraint requirements into a
unit-safe SI set with provenance and explicit conflict detection. Synthesis then
derives fixed-wing seeds from declared analytical/empirical relations, exposes
rotorcraft and lifting-body architecture seams, and projects seeds onto the
existing design-space and design-state contracts. All results are deterministic,
hashable, screening evidence only, and fail closed.
"""

from .errors import (
    RequirementCompileError,
    RequirementConflict,
    RequirementConflictError,
    RequirementError,
    SynthesisError,
    SynthesisInfeasibleError,
)
from .fixed_wing import (
    FixedWingAssumptions,
    generate_fixed_wing_seeds,
    requirement_bounds,
)
from .methods import (
    METHODS,
    SYNTHESIS_MODEL,
    SYNTHESIS_MODEL_VERSION,
    MethodValidity,
    SynthesisQuantity,
    ValidityCheck,
)
from .report import SynthesisReport, synthesize_initial_seeds
from .requirements import (
    KINDS,
    METRIC_CATEGORIES,
    METRIC_DIMENSIONS,
    OPERATORS,
    REQUIREMENTS_MODEL,
    REQUIREMENTS_MODEL_VERSION,
    CompiledRequirements,
    NormalizedRequirement,
    RequirementSpec,
    compile_requirements,
    compile_requirements_payload,
    detect_conflicts,
    requirement_spec_from_payload,
)
from .seams import SeamResult, synthesize_lifting_body_seam, synthesize_rotorcraft_seam
from .seeds import VehicleSeed, build_seed_design_space

__all__ = [
    "KINDS",
    "METHODS",
    "METRIC_CATEGORIES",
    "METRIC_DIMENSIONS",
    "OPERATORS",
    "REQUIREMENTS_MODEL",
    "REQUIREMENTS_MODEL_VERSION",
    "SYNTHESIS_MODEL",
    "SYNTHESIS_MODEL_VERSION",
    "CompiledRequirements",
    "FixedWingAssumptions",
    "MethodValidity",
    "NormalizedRequirement",
    "RequirementCompileError",
    "RequirementConflict",
    "RequirementConflictError",
    "RequirementError",
    "RequirementSpec",
    "SeamResult",
    "SynthesisError",
    "SynthesisInfeasibleError",
    "SynthesisQuantity",
    "SynthesisReport",
    "ValidityCheck",
    "VehicleSeed",
    "build_seed_design_space",
    "compile_requirements",
    "compile_requirements_payload",
    "detect_conflicts",
    "generate_fixed_wing_seeds",
    "requirement_bounds",
    "requirement_spec_from_payload",
    "synthesize_initial_seeds",
    "synthesize_lifting_body_seam",
    "synthesize_rotorcraft_seam",
]
