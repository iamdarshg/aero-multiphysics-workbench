"""Generic uncertainty propagation, reliability constraints, and robust design.

This subpackage makes vehicle/system optimization uncertainty-aware without
adding a second optimizer: it reuses the existing campaign evaluator/selector
seams, the shared result contracts, and the reduced-order-model fidelity
vocabulary.

Public API (other workstreams import these exact paths):

    from aeroworkbench_vehicle_systems.robust import (
        UncertaintyClass, UncertaintySource, VariableProvenance,
        UncertainVariable, CorrelationSpec, ModelFormUncertainty, UncertaintySpec,
        Distribution, DistributionKind, normal_cdf, normal_inv_cdf,
        SamplingPlan, SamplingMethod, UncertainSamples, sample_uncertainty,
        sample_model_form, unit_hypercube, correlation_matrix, cholesky,
        MomentEstimates, moment_estimates, quantile,
        PropagationResult, PropagationSamples, ModelFormReport,
        propagate, sample_responses, result_digest,
        LimitDirection, ReliabilityMethod, ReliabilityConstraint,
        ReliabilityEstimate, monte_carlo_reliability, first_order_reliability,
        estimate_reliability, reliability_index_from_failure_probability,
        RobustObjective, RobustObjectiveKind, evaluate_robust_objective,
        robust_objective_values,
        RobustEvaluationSpec, RobustEvaluator, RobustSelector,
        NominalEvaluator, robust_evaluator, robust_study_objectives,
        robust_study_constraints, build_campaign_spec,
        tolerance_variable, material_scatter_variable,
        calibration_variable, calibration_model_form,
        UncertaintyError, SamplingError, PropagationError, ReliabilityError,
        RobustOptimizationError, CapabilityUnavailable,
    )

Every result carries a source, a fidelity, units, a validity verdict, an
input hash, a software identity, and provenance. Reliability claims are only
admissible at a trusted fidelity; model-form discrepancy is provenance-visible
and distinct from manufacturing/aleatory scatter.
"""

from .campaign import (
    NominalEvaluator,
    RobustEvaluationSpec,
    RobustEvaluator,
    RobustSelector,
    build_campaign_spec,
    robust_evaluator,
    robust_study_constraints,
    robust_study_objectives,
)
from .contracts import (
    SOFTWARE_NAME,
    SOFTWARE_VERSION,
    CorrelationSpec,
    ModelFormUncertainty,
    UncertaintyClass,
    UncertaintySource,
    UncertaintySpec,
    UncertainVariable,
    VariableProvenance,
    deterministic_variable,
)
from .distributions import (
    Distribution,
    DistributionKind,
    normal_cdf,
    normal_inv_cdf,
)
from .errors import (
    CapabilityUnavailable,
    PropagationError,
    ReliabilityError,
    RobustOptimizationError,
    SamplingError,
    UncertaintyError,
)
from .objectives import (
    RobustObjective,
    RobustObjectiveKind,
    evaluate_robust_objective,
    robust_objective_values,
)
from .propagation import (
    DEFAULT_PROBABILITIES,
    ModelFormReport,
    MomentEstimates,
    PropagationResult,
    PropagationSamples,
    moment_estimates,
    propagate,
    quantile,
    result_digest,
    sample_responses,
)
from .reliability import (
    LimitDirection,
    ReliabilityConstraint,
    ReliabilityEstimate,
    ReliabilityMethod,
    estimate_reliability,
    first_order_reliability,
    monte_carlo_reliability,
    reliability_index_from_failure_probability,
)
from .sampling import (
    DEFAULT_MAX_SAMPLES,
    SamplingMethod,
    SamplingPlan,
    UncertainSamples,
    cholesky,
    correlation_matrix,
    sample_model_form,
    sample_uncertainty,
    unit_hypercube,
)
from .sources import (
    calibration_model_form,
    calibration_variable,
    material_scatter_variable,
    tolerance_variable,
)

__all__ = [
    "DEFAULT_MAX_SAMPLES",
    "DEFAULT_PROBABILITIES",
    "SOFTWARE_NAME",
    "SOFTWARE_VERSION",
    "CapabilityUnavailable",
    "CorrelationSpec",
    "Distribution",
    "DistributionKind",
    "LimitDirection",
    "ModelFormReport",
    "ModelFormUncertainty",
    "MomentEstimates",
    "NominalEvaluator",
    "PropagationError",
    "PropagationResult",
    "PropagationSamples",
    "ReliabilityConstraint",
    "ReliabilityError",
    "ReliabilityEstimate",
    "ReliabilityMethod",
    "RobustEvaluationSpec",
    "RobustEvaluator",
    "RobustObjective",
    "RobustObjectiveKind",
    "RobustOptimizationError",
    "RobustSelector",
    "SamplingError",
    "SamplingMethod",
    "SamplingPlan",
    "UncertainSamples",
    "UncertainVariable",
    "UncertaintyClass",
    "UncertaintyError",
    "UncertaintySource",
    "UncertaintySpec",
    "VariableProvenance",
    "build_campaign_spec",
    "calibration_model_form",
    "calibration_variable",
    "cholesky",
    "correlation_matrix",
    "deterministic_variable",
    "material_scatter_variable",
    "estimate_reliability",
    "evaluate_robust_objective",
    "first_order_reliability",
    "moment_estimates",
    "monte_carlo_reliability",
    "normal_cdf",
    "normal_inv_cdf",
    "propagate",
    "quantile",
    "reliability_index_from_failure_probability",
    "result_digest",
    "robust_evaluator",
    "robust_objective_values",
    "robust_study_constraints",
    "robust_study_objectives",
    "sample_model_form",
    "sample_responses",
    "sample_uncertainty",
    "tolerance_variable",
    "unit_hypercube",
]
