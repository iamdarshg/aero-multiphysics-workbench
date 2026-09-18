"""Adaptive fidelity, quality-gated studies, and DOE/optimization drivers."""

from .design_space import (
    DesignSpaceError,
    active_variable_ids,
    candidate_hash,
    flatten_design_state,
    numeric_vector,
    preflight_design_state,
    unflatten_design_state,
    validate_design_space,
)
from .drivers import (
    DesignVariable,
    OperatingPointEval,
    SampleReport,
    StudyConstraint,
    StudyObjective,
    StudyResult,
    pareto_front,
    rank_valid,
    run_doe,
    run_optimize,
    run_sweep,
    study_from_design_state,
)
from .fidelity import FidelityDecision, select_fidelity
from .planner import (
    FidelityImplementation,
    FidelityPlan,
    FidelitySignals,
    plan_fidelity,
)
from .quality import PhysicsFlags, QualityPolicy, SampleVerdict, assess_sample

__all__ = [
    "DesignSpaceError",
    "DesignVariable",
    "FidelityDecision",
    "FidelityImplementation",
    "FidelityPlan",
    "FidelitySignals",
    "OperatingPointEval",
    "PhysicsFlags",
    "QualityPolicy",
    "SampleReport",
    "SampleVerdict",
    "StudyConstraint",
    "StudyObjective",
    "StudyResult",
    "active_variable_ids",
    "assess_sample",
    "candidate_hash",
    "flatten_design_state",
    "numeric_vector",
    "pareto_front",
    "plan_fidelity",
    "preflight_design_state",
    "rank_valid",
    "run_doe",
    "run_optimize",
    "run_sweep",
    "select_fidelity",
    "study_from_design_state",
    "unflatten_design_state",
    "validate_design_space",
]
