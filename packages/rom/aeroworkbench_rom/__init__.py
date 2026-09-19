"""Generic automated performance-map, reduced-order-model, and surrogate layer.

This package turns validated analytical/native/test samples into reusable,
revisioned, hashable performance representations for system studies,
optimization, and controls, without losing validity or provenance. It is
application-agnostic: aerodynamic surfaces, propulsors, compressors/turbines,
thermal components, electrical hardware, and any other parameterized
participant use the same typed contracts.

Public API (other workstreams import these exact paths):

    from aeroworkbench_rom import (
        IndependentVariable, OutputVariable, VariableKind,
        SamplingPlan, plan_from_variables, design_space_from_variables,
        PerformanceMap, MapSample, MapPrediction, build_map,
        MapFidelity, SampleKind, ExtrapolationPolicy, Validity,
        ModelPrediction, NearestInterpolator, StructuredInterpolator,
        PolynomialResponseSurface, RBFSurrogate, PodRom, NeuralSurrogate,
        SurrogateModel, build_model,
        CrossValidationReport, cross_validate, assess_trust, map_trust,
        SampleSet, merge_samples, calibration_offsets, calibrate_simulation,
        fused_sample_set,
        RefinementCriteria, RefinementPlan, propose_refinement, refine,
        MapConsumption, consume_map, fidelity_escalation,
        MapArtifactCache, ArtifactRef,
        native_sample, native_sampling_capability, require_native_sampling,
        neural_capability, require_neural,
        CapabilityUnavailable, ExtrapolationError, MapContractError,
        RomError, ValidationError, ValidityError,
    )

Every map records independent variables and units, outputs and units, a
validity domain, source sample ids with source/fidelity labels, an
interpolation method, an uncertainty estimate, an extrapolation policy, and a
revision hash. Predictions are always labelled ``surrogate`` and are never
presented as native physics. Native sampling and neural surrogates are
capability-gated and fail closed.
"""

from .cache import ArtifactRef, MapArtifactCache
from .capabilities import (
    CapabilityState,
    NativeSamplingBackend,
    native_sample,
    native_sampling_capability,
    neural_capability,
    require_native_sampling,
    require_neural,
)
from .contracts import (
    SOFTWARE_IDENTITY,
    SOFTWARE_VERSION,
    ExtrapolationPolicy,
    MapFidelity,
    SampleKind,
    SoftwareIdentity,
    Validity,
    source_for_kind,
)
from .errors import (
    CacheImmutabilityError,
    CacheIntegrityError,
    CapabilityUnavailable,
    ExtrapolationError,
    MapContractError,
    RomError,
    ValidationError,
    ValidityError,
)
from .fusion import (
    CalibrationOffset,
    SampleSet,
    calibrate_simulation,
    calibration_offsets,
    fused_sample_set,
    merge_samples,
)
from .map import MapPrediction, MapSample, PerformanceMap, build_map, point_key
from .models import (
    ModelPrediction,
    NearestInterpolator,
    NeuralBackend,
    NeuralSurrogate,
    PodRom,
    PolynomialResponseSurface,
    RBFSurrogate,
    StructuredInterpolator,
    SurrogateModel,
    build_model,
)
from .refinement import (
    RefinementCriteria,
    RefinementPlan,
    RefinementPoint,
    RefinementResult,
    propose_refinement,
    refine,
)
from .sampling import SamplingPlan, design_space_from_variables, plan_from_variables
from .system_use import MapConsumption, consume_map, fidelity_escalation
from .validation import (
    CrossValidationReport,
    OutputErrorStats,
    TrustDecision,
    assess_trust,
    cross_validate,
    map_trust,
)
from .variables import IndependentVariable, OutputVariable, VariableKind

__all__ = [
    "SOFTWARE_IDENTITY",
    "SOFTWARE_VERSION",
    "ArtifactRef",
    "CalibrationOffset",
    "CapabilityState",
    "CapabilityUnavailable",
    "CacheImmutabilityError",
    "CacheIntegrityError",
    "CrossValidationReport",
    "ExtrapolationError",
    "ExtrapolationPolicy",
    "IndependentVariable",
    "MapArtifactCache",
    "MapConsumption",
    "MapContractError",
    "MapFidelity",
    "MapPrediction",
    "MapSample",
    "ModelPrediction",
    "NativeSamplingBackend",
    "NearestInterpolator",
    "NeuralBackend",
    "NeuralSurrogate",
    "OutputErrorStats",
    "OutputVariable",
    "PerformanceMap",
    "PodRom",
    "PolynomialResponseSurface",
    "RBFSurrogate",
    "RefinementCriteria",
    "RefinementPlan",
    "RefinementPoint",
    "RefinementResult",
    "RomError",
    "SampleKind",
    "SampleSet",
    "SamplingPlan",
    "SoftwareIdentity",
    "StructuredInterpolator",
    "SurrogateModel",
    "TrustDecision",
    "ValidationError",
    "Validity",
    "ValidityError",
    "VariableKind",
    "assess_trust",
    "build_map",
    "build_model",
    "calibrate_simulation",
    "calibration_offsets",
    "consume_map",
    "cross_validate",
    "design_space_from_variables",
    "fidelity_escalation",
    "fused_sample_set",
    "map_trust",
    "merge_samples",
    "native_sample",
    "native_sampling_capability",
    "neural_capability",
    "plan_from_variables",
    "point_key",
    "propose_refinement",
    "refine",
    "require_native_sampling",
    "require_neural",
    "source_for_kind",
]
