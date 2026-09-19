"""Generative rotating-gas design space and candidate engine (TURBO 06).

Composes the existing mixed/conditional/hierarchical design space, the
deterministic candidate generator, the manufacturing envelopes, and the TURBO 03
meanline screen. Public API:

    from aeroworkbench_turbomachinery.generative import (
        GenerativeSpec,
        build_design_space,
        default_generation_request,
        cardinality_report,
        candidate_generator,
        architecture_from_state,
        meanline_stage_from_state,
        row_plan,
        MutationChange,
        MutationOutcome,
        MUTATION_OPERATORS,
        apply_mutation,
        design_identity,
        ScreeningReport,
        screen_state,
        screen_candidate,
    )
"""

from ._engine import candidate_generator
from .mapping import RowPlan, architecture_from_state, meanline_stage_from_state, row_plan
from .mutations import (
    MUTATION_OPERATORS,
    GenerativeMutationError,
    MutationChange,
    MutationOperator,
    MutationOutcome,
    apply_mutation,
    design_identity,
    operator_names,
    parented_generation_request,
)
from .screening import (
    PIPELINE_STAGES,
    ScreeningReport,
    admissible_candidates,
    native_promotion_allowed,
    screen_candidate,
    screen_state,
)
from .space import (
    ARRANGEMENTS,
    BYPASS_TOPOLOGIES,
    DIFFUSER_TYPES,
    FAMILIES,
    MACHINE_KINDS,
    CardinalityReport,
    SpaceSummary,
    build_design_space,
    cardinality_report,
    default_generation_request,
    run_generative_campaign,
    space_summary,
)
from .spec import DEFAULT_MATERIALS, DEFAULT_PROCESSES, GenerativeSpec, default_spec

__all__ = [
    "ARRANGEMENTS",
    "BYPASS_TOPOLOGIES",
    "DEFAULT_MATERIALS",
    "DEFAULT_PROCESSES",
    "DIFFUSER_TYPES",
    "FAMILIES",
    "MACHINE_KINDS",
    "MUTATION_OPERATORS",
    "PIPELINE_STAGES",
    "CardinalityReport",
    "GenerativeMutationError",
    "GenerativeSpec",
    "MutationChange",
    "MutationOperator",
    "MutationOutcome",
    "RowPlan",
    "ScreeningReport",
    "SpaceSummary",
    "admissible_candidates",
    "apply_mutation",
    "architecture_from_state",
    "build_design_space",
    "candidate_generator",
    "cardinality_report",
    "default_generation_request",
    "default_spec",
    "design_identity",
    "meanline_stage_from_state",
    "native_promotion_allowed",
    "operator_names",
    "parented_generation_request",
    "row_plan",
    "run_generative_campaign",
    "screen_candidate",
    "screen_state",
    "space_summary",
]
