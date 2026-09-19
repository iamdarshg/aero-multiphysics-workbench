"""Generic environmental degradation, icing, contamination, erosion, and FOD.

The package represents how environment and service exposure change geometry,
material properties, and aerodynamic/thermal performance over time, for wings,
propellers, rotors, ducts, compressors/turbines, inlets, and any other exposed
hardware. It is application-agnostic: it operates from typed physical contracts,
not product-specific assumptions.

Public API (other workstreams import these exact paths):

    from aeroworkbench_environmental import (
        ExposureKind,
        ExposureSpec,
        EnvironmentState,
        DegradationKind,
        DegradationModifier,
        DegradationState,
        EnvelopeModel,
        DEFAULT_ENVELOPE_MODEL,
        evaluate_degradation,
        IceAccretionRequest,
        evaluate_ice_accretion_envelope,
        ice_geometry_change,
        solve_native_icing,
        evaluate_contamination,
        evaluate_erosion,
        ImpactEvent,
        evaluate_impact,
        require_residual_strength,
        apply_degradation,
        degraded_invalidated_families,
        degrade_material_revision,
        RobustConstraint,
        evaluate_robust_constraint,
    )

Every result retains source/fidelity/units/validity/input-hash/software-identity/
provenance. Native paths are capability-gated and fail closed.
"""

from .contamination import ContaminationAssessment, evaluate_contamination
from .contracts import (
    DEFAULT_SOFTWARE,
    SOFTWARE_IDENTITY,
    SOFTWARE_VERSION,
    EnvironmentalFidelity,
    SoftwareIdentity,
    Validity,
)
from .coupling import (
    DegradedDesign,
    apply_degradation,
    degradation_change_sections,
    degraded_invalidated_families,
)
from .degradation import (
    DEFAULT_ENVELOPE_MODEL,
    DEGRADATION_QUANTITIES,
    DESIGN_SECTIONS,
    ENVELOPE_MODELS,
    DegradationKind,
    DegradationModifier,
    DegradationState,
    EnvelopeModel,
    evaluate_degradation,
)
from .erosion import ErosionAssessment, evaluate_erosion
from .errors import (
    CapabilityUnavailable,
    EnvironmentalError,
    LimitViolation,
    UnitError,
    ValidityError,
)
from .exposure import (
    EXPOSURE_DRIVERS,
    EnvironmentState,
    ExposureKind,
    ExposureSpec,
)
from .fod import (
    ImpactEvent,
    ImpactReport,
    StructuralDamageFeed,
    evaluate_impact,
    native_impact_capability,
    require_residual_strength,
)
from .icing import (
    GeometryChange,
    IceAccretionRequest,
    IceAccretionResult,
    IcingCapability,
    NativeIcingBackend,
    evaluate_ice_accretion_envelope,
    ice_geometry_change,
    native_icing_capability,
    solve_native_icing,
)
from .material import DegradedMaterial, degrade_material_revision
from .participants import (
    ENVIRONMENTAL_PARTICIPANTS,
    CapabilityState,
    EnvironmentalParticipant,
    PortSpec,
    environmental_participants,
    native_environmental_capability,
    participant_ids,
    require_native_environmental,
)
from .provenance import analytical_provenance, empirical_provenance, native_provenance
from .robust import (
    ConstraintDirection,
    RobustCondition,
    RobustConstraint,
    RobustVerdict,
    degradation_digest_for,
    evaluate_robust_constraint,
    robust_conditions_for,
)
from .units import SI_UNITS, Quantity, require_unit

__all__ = [
    "DEFAULT_ENVELOPE_MODEL",
    "DEFAULT_SOFTWARE",
    "DEGRADATION_QUANTITIES",
    "DESIGN_SECTIONS",
    "ENVIRONMENTAL_PARTICIPANTS",
    "ENVELOPE_MODELS",
    "EXPOSURE_DRIVERS",
    "SI_UNITS",
    "SOFTWARE_IDENTITY",
    "SOFTWARE_VERSION",
    "CapabilityState",
    "CapabilityUnavailable",
    "ConstraintDirection",
    "ContaminationAssessment",
    "DegradedDesign",
    "DegradedMaterial",
    "DegradationKind",
    "DegradationModifier",
    "DegradationState",
    "EnvironmentalError",
    "EnvironmentalFidelity",
    "EnvironmentalParticipant",
    "EnvelopeModel",
    "EnvironmentState",
    "ErosionAssessment",
    "ExposureKind",
    "ExposureSpec",
    "GeometryChange",
    "IceAccretionRequest",
    "IceAccretionResult",
    "IcingCapability",
    "ImpactEvent",
    "ImpactReport",
    "LimitViolation",
    "NativeIcingBackend",
    "PortSpec",
    "Quantity",
    "RobustCondition",
    "RobustConstraint",
    "RobustVerdict",
    "SoftwareIdentity",
    "StructuralDamageFeed",
    "UnitError",
    "Validity",
    "ValidityError",
    "analytical_provenance",
    "apply_degradation",
    "degradation_change_sections",
    "degradation_digest_for",
    "degrade_material_revision",
    "degraded_invalidated_families",
    "empirical_provenance",
    "environmental_participants",
    "evaluate_contamination",
    "evaluate_degradation",
    "evaluate_erosion",
    "evaluate_ice_accretion_envelope",
    "evaluate_impact",
    "evaluate_robust_constraint",
    "ice_geometry_change",
    "native_environmental_capability",
    "native_icing_capability",
    "native_impact_capability",
    "native_provenance",
    "participant_ids",
    "require_native_environmental",
    "require_residual_strength",
    "require_unit",
    "robust_conditions_for",
    "solve_native_icing",
]
