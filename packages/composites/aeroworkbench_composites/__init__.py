"""Generic composite, laminate, and anisotropic structural design.

This package makes lightweight anisotropic structures first-class citizens of
the multiphysics workbench. It extends the revisioned material and laminate
contracts with ply architecture, strength allowables, classical-laminate-theory
analysis (A/B/D, thermal resultants, per-ply stresses), selectable failure
criteria (maximum stress/strain, Tsai-Hill, Tsai-Wu, Hashin, first/progressive
ply failure), manufacturing constraints enforced before expensive analysis,
capability-gated native structural mapping, and dynamic/thermal/durability
coupling. Every output is deterministic, hashable, and carries
source/fidelity/units/validity/input-hash/software-identity/provenance.
"""

from .clt import (
    LaminateAnalysis as LaminateAnalysis,
)
from .clt import (
    LaminateDefinition as LaminateDefinition,
)
from .clt import (
    LaminateLoad as LaminateLoad,
)
from .clt import (
    MembraneProperties as MembraneProperties,
)
from .clt import (
    PlyResponse as PlyResponse,
)
from .clt import (
    ThermalResultants as ThermalResultants,
)
from .clt import (
    abd_from_plies as abd_from_plies,
)
from .clt import (
    analyze_laminate as analyze_laminate,
)
from .clt import (
    is_balanced as is_balanced,
)
from .clt import (
    is_symmetric as is_symmetric,
)
from .clt import (
    laminate_definition_digest as laminate_definition_digest,
)
from .clt import (
    ply_qbar as ply_qbar,
)
from .clt import (
    ply_stresses as ply_stresses,
)
from .clt import (
    ply_stresses_for as ply_stresses_for,
)
from .coupling import (
    ModalEstimate as ModalEstimate,
)
from .coupling import (
    analyze_and_estimate as analyze_and_estimate,
)
from .coupling import (
    areal_mass_kg_m2 as areal_mass_kg_m2,
)
from .coupling import (
    cantilever_bending_frequency_hz as cantilever_bending_frequency_hz,
)
from .coupling import (
    centrifugal_membrane_load as centrifugal_membrane_load,
)
from .coupling import (
    composite_fatigue_damage as composite_fatigue_damage,
)
from .coupling import (
    pressure_hoop_load as pressure_hoop_load,
)
from .coupling import (
    to_aeroelastic_inputs as to_aeroelastic_inputs,
)
from .design import (
    CompositeDesignResult as CompositeDesignResult,
)
from .design import (
    CompositeInputs as CompositeInputs,
)
from .design import (
    composite_change_sections as composite_change_sections,
)
from .design import (
    composite_invalidated_families as composite_invalidated_families,
)
from .design import (
    composite_invalidated_for as composite_invalidated_for,
)
from .design import (
    evaluate_composite_design as evaluate_composite_design,
)
from .failure import (
    CRITERION_ASSUMPTIONS as CRITERION_ASSUMPTIONS,
)
from .failure import (
    CRITERION_REQUIRED_ALLOWABLES as CRITERION_REQUIRED_ALLOWABLES,
)
from .failure import (
    FailureCriterion as FailureCriterion,
)
from .failure import (
    FailureIndex as FailureIndex,
)
from .failure import (
    FirstPlyResult as FirstPlyResult,
)
from .failure import (
    PlyDiscardPolicy as PlyDiscardPolicy,
)
from .failure import (
    PlyStrainLimits as PlyStrainLimits,
)
from .failure import (
    PlyStress as PlyStress,
)
from .failure import (
    ProgressiveResult as ProgressiveResult,
)
from .failure import (
    StrengthLibrary as StrengthLibrary,
)
from .failure import (
    evaluate_interlaminar as evaluate_interlaminar,
)
from .failure import (
    evaluate_ply_failure as evaluate_ply_failure,
)
from .failure import (
    first_ply_failure as first_ply_failure,
)
from .failure import (
    progressive_failure as progressive_failure,
)
from .manufacturing import (
    ManufacturingFinding as ManufacturingFinding,
)
from .manufacturing import (
    ManufacturingReport as ManufacturingReport,
)
from .manufacturing import (
    PlyProcessLimits as PlyProcessLimits,
)
from .manufacturing import (
    evaluate_manufacturability as evaluate_manufacturability,
)
from .manufacturing import (
    laminate_measurements as laminate_measurements,
)
from .manufacturing import (
    manufacturing_envelope as manufacturing_envelope,
)
from .manufacturing import (
    manufacturing_limits as manufacturing_limits,
)
from .manufacturing import (
    require_manufacturable as require_manufacturable,
)
from .manufacturing import (
    screen_with_turbo05 as screen_with_turbo05,
)
from .native import (
    COMPOSITES_PARTICIPANTS as COMPOSITES_PARTICIPANTS,
)
from .native import (
    CompositesParticipant as CompositesParticipant,
)
from .native import (
    CompositesPort as CompositesPort,
)
from .native import (
    LocalFrame as LocalFrame,
)
from .native import (
    NativeStructuralReceipt as NativeStructuralReceipt,
)
from .native import (
    NativeStructuralRequest as NativeStructuralRequest,
)
from .native import (
    PlyMapping as PlyMapping,
)
from .native import (
    PrestressState as PrestressState,
)
from .native import (
    StructuralMapping as StructuralMapping,
)
from .native import (
    SurfaceLoad as SurfaceLoad,
)
from .native import (
    composites_participant_ids as composites_participant_ids,
)
from .native import (
    map_laminate_to_structural as map_laminate_to_structural,
)
from .native import (
    native_structural_capability as native_structural_capability,
)
from .native import (
    reject_isotropic_reduction as reject_isotropic_reduction,
)
from .native import (
    require_native_structural as require_native_structural,
)
from .native import (
    solve_native_structural as solve_native_structural,
)
from .ply import (
    MoistureModifier as MoistureModifier,
)
from .ply import (
    PlyArchitecture as PlyArchitecture,
)
from .ply import (
    PlyConstants as PlyConstants,
)
from .ply import (
    PlyStrength as PlyStrength,
)
from .ply import (
    StrengthAssessment as StrengthAssessment,
)
from .ply import (
    apply_environment as apply_environment,
)
from .ply import (
    ply_constants as ply_constants,
)
from .provenance import (
    SOFTWARE_IDENTITY as SOFTWARE_IDENTITY,
)
from .provenance import (
    SOFTWARE_VERSION as SOFTWARE_VERSION,
)
from .provenance import (
    analytical_provenance as analytical_provenance,
)
from .provenance import (
    benchmark_provenance as benchmark_provenance,
)
from .provenance import (
    native_provenance as native_provenance,
)
from .provenance import (
    reduced_provenance as reduced_provenance,
)
from .units import (
    SI_UNITS as SI_UNITS,
)
from .units import (
    UnitError as UnitError,
)
from .units import (
    require_unit as require_unit,
)
from .validity import (
    CapabilityUnavailable as CapabilityUnavailable,
)
from .validity import (
    CompositesError as CompositesError,
)
from .validity import (
    DataUnavailable as DataUnavailable,
)
from .validity import (
    DurabilityError as DurabilityError,
)
from .validity import (
    Fidelity as Fidelity,
)
from .validity import (
    ManufacturingViolation as ManufacturingViolation,
)
from .validity import (
    Validity as Validity,
)
from .validity import (
    finite as finite,
)
from .validity import (
    flag as flag,
)
from .validity import (
    integer as integer,
)

__all__ = [
    "COMPOSITES_PARTICIPANTS",
    "CRITERION_ASSUMPTIONS",
    "CRITERION_REQUIRED_ALLOWABLES",
    "SI_UNITS",
    "SOFTWARE_IDENTITY",
    "SOFTWARE_VERSION",
    "CapabilityUnavailable",
    "CompositeDesignResult",
    "CompositeInputs",
    "CompositesError",
    "CompositesParticipant",
    "CompositesPort",
    "DataUnavailable",
    "DurabilityError",
    "FailureCriterion",
    "FailureIndex",
    "Fidelity",
    "FirstPlyResult",
    "LaminateAnalysis",
    "LaminateDefinition",
    "LaminateLoad",
    "LocalFrame",
    "ManufacturingFinding",
    "ManufacturingReport",
    "ManufacturingViolation",
    "MembraneProperties",
    "ModalEstimate",
    "MoistureModifier",
    "NativeStructuralReceipt",
    "NativeStructuralRequest",
    "PlyArchitecture",
    "PlyConstants",
    "PlyDiscardPolicy",
    "PlyMapping",
    "PlyProcessLimits",
    "PlyResponse",
    "PlyStrainLimits",
    "PlyStrength",
    "PlyStress",
    "PrestressState",
    "ProgressiveResult",
    "StrengthAssessment",
    "StrengthLibrary",
    "StructuralMapping",
    "SurfaceLoad",
    "ThermalResultants",
    "UnitError",
    "Validity",
    "abd_from_plies",
    "analytical_provenance",
    "analyze_and_estimate",
    "analyze_laminate",
    "apply_environment",
    "areal_mass_kg_m2",
    "benchmark_provenance",
    "cantilever_bending_frequency_hz",
    "centrifugal_membrane_load",
    "composite_change_sections",
    "composite_fatigue_damage",
    "composite_invalidated_families",
    "composite_invalidated_for",
    "composites_participant_ids",
    "evaluate_composite_design",
    "evaluate_interlaminar",
    "evaluate_manufacturability",
    "evaluate_ply_failure",
    "finite",
    "first_ply_failure",
    "flag",
    "integer",
    "is_balanced",
    "is_symmetric",
    "laminate_definition_digest",
    "laminate_measurements",
    "manufacturing_envelope",
    "manufacturing_limits",
    "map_laminate_to_structural",
    "native_provenance",
    "native_structural_capability",
    "ply_constants",
    "ply_qbar",
    "ply_stresses",
    "ply_stresses_for",
    "pressure_hoop_load",
    "progressive_failure",
    "reduced_provenance",
    "reject_isotropic_reduction",
    "require_manufacturable",
    "require_native_structural",
    "require_unit",
    "screen_with_turbo05",
    "solve_native_structural",
    "to_aeroelastic_inputs",
]
