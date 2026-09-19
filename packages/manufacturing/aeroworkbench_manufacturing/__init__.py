"""Generic manufacturability, buildability, and mechanical operating limits.

TURBO 05. Envelopes are revisioned data bound into the canonical design-revision
system; hard limits are first-class constraints enforced during candidate
generation and at staged screening gates before expensive CFD/FEA. Missing
native capability fails closed.
"""

from .design_space import (
    envelope_design_constraints,
    envelope_summary,
    evaluate_candidate,
    merge_envelope_constraints,
    select_admissible,
)
from .envelopes import (
    BOUND_LIMIT_KINDS,
    LIMIT_SCHEMA_VERSION,
    STAGE_ORDER,
    ConstraintClass,
    EnvelopeBinding,
    EnvelopeError,
    EnvelopeSet,
    EvaluationStage,
    HardwareLimitEnvelope,
    LimitProvenance,
    LimitRelation,
    LimitSourceKind,
    ManufacturingProcessEnvelope,
    ScalarLimit,
    bind_envelopes,
    verify_binding,
)
from .gate import (
    ConstraintViolation,
    EnvelopeReport,
    ManufacturabilityGate,
    Measurement,
    MeasurementError,
    evaluate_envelopes,
)
from .predicates import PredicateError, evaluate_predicate, predicate_variables
from .scoring import (
    DEFAULT_SOFT_WEIGHTS,
    SOFT_METRIC_NAMES,
    manufacturability_score,
    rank_by_manufacturability,
)
from .units import SUPPORTED_UNITS, UnitConversionError, from_si, to_si, unit_dimension

__all__ = [
    "BOUND_LIMIT_KINDS",
    "ConstraintClass",
    "ConstraintViolation",
    "DEFAULT_SOFT_WEIGHTS",
    "EnvelopeBinding",
    "EnvelopeError",
    "EnvelopeReport",
    "EnvelopeSet",
    "EvaluationStage",
    "HardwareLimitEnvelope",
    "LIMIT_SCHEMA_VERSION",
    "LimitProvenance",
    "LimitRelation",
    "LimitSourceKind",
    "ManufacturabilityGate",
    "ManufacturingProcessEnvelope",
    "Measurement",
    "MeasurementError",
    "PredicateError",
    "SOFT_METRIC_NAMES",
    "STAGE_ORDER",
    "SUPPORTED_UNITS",
    "ScalarLimit",
    "UnitConversionError",
    "bind_envelopes",
    "envelope_design_constraints",
    "envelope_summary",
    "evaluate_candidate",
    "evaluate_envelopes",
    "evaluate_predicate",
    "from_si",
    "manufacturability_score",
    "merge_envelope_constraints",
    "predicate_variables",
    "rank_by_manufacturability",
    "select_admissible",
    "to_si",
    "unit_dimension",
    "verify_binding",
]
