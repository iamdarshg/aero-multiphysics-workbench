"""VEHICLE-SYSTEMS 02: mission simulation and trajectory optimization.

This subpackage evaluates and optimizes a complete mission rather than isolated
operating points: a canonical graph of typed segments (taxi/takeoff/climb/
acceleration/cruise/loiter/dash/descent/approach/landing/reserve/user-defined),
deterministic time integration of vehicle mass/fuel/energy/thermal state,
performance-map/aero consumption through a typed participant seam (#68 maps),
explicit end-of-mission reserve requirements, mass/fuel/energy/distance/
continuity closure, and a bounded energy-state trajectory optimizer. The same
engine accepts fixed-wing and rotorcraft participants, and every result carries
source/fidelity/units/validity/input-hash/software-identity/provenance.

Public API (other workstreams import these exact paths):

    from aeroworkbench_vehicle_systems.mission import (
        SegmentKind, SegmentMode, SegmentSpec, SegmentConstraints,
        ReserveKind, ReserveSpec, VehicleSpec, MissionSpec, ClosureTolerances,
        ControlName, MissionState,
        OperatingPoint, AeroPoint, PropulsionPoint, PerformanceParticipant,
        AnalyticalFixedWingParticipant, AnalyticalRotorcraftParticipant,
        PerformanceMapParticipant,
        PropagationPolicy, SegmentTrace, MissionTrace, propagate_mission,
        MissionBalance, ClosureReport, ClosureResidual, evaluate_closure,
        ReserveReport, ReserveVerdict, evaluate_reserves,
        MissionResult, run_mission, MissionSet, MissionSetResult,
        evaluate_mission_set, mission_design_outputs, mission_campaign_objectives,
        CampaignEvaluator, mission_evaluator,
        ControlVariable, TrajectoryOptimization, TrajectoryOptimizationResult,
        apply_controls, objective_value, optimize_trajectory, trajectory_study,
        CapabilityState, NativeMissionBackend, NativeMissionOutcome,
        native_mission_status, require_native_mission, solve_native_mission,
        MissionFidelity, MissionMeta, MissionValidity,
        MissionError, MissionContractError, MissionValidationError,
        ReserveError, ClosureError, PerformanceRejected,
        MissionOptimizationError, CapabilityUnavailable,
    )
"""

from .closure import (
    ClosureReport,
    ClosureResidual,
    MissionBalance,
    evaluate_closure,
)
from .contracts import (
    MISSION_UNITS,
    SOFTWARE_NAME,
    SOFTWARE_VERSION,
    MissionFidelity,
    MissionMeta,
    MissionValidity,
)
from .errors import (
    CapabilityUnavailable,
    ClosureError,
    MissionContractError,
    MissionError,
    MissionOptimizationError,
    MissionValidationError,
    PerformanceRejected,
    ReserveError,
)
from .evaluation import (
    CampaignEvaluator,
    MissionResult,
    MissionSet,
    MissionSetResult,
    evaluate_mission_set,
    mission_campaign_objectives,
    mission_design_outputs,
    mission_evaluator,
    run_mission,
)
from .native import (
    CapabilityState,
    NativeMissionBackend,
    NativeMissionOutcome,
    native_mission_status,
    require_native_mission,
    solve_native_mission,
)
from .optimizer import (
    ControlVariable,
    TrajectoryOptimization,
    TrajectoryOptimizationResult,
    apply_controls,
    objective_value,
    optimize_trajectory,
    trajectory_study,
)
from .performance import (
    GRAVITY_M_S2,
    AeroPoint,
    AnalyticalFixedWingParticipant,
    AnalyticalRotorcraftParticipant,
    OperatingPoint,
    PerformanceMapParticipant,
    PerformanceParticipant,
    PropulsionPoint,
)
from .propagator import (
    MissionTrace,
    PropagationPolicy,
    SegmentTrace,
    propagate_mission,
)
from .reserves import (
    ReserveReport,
    ReserveVerdict,
    evaluate_reserves,
)
from .segments import (
    CLOSURE_DIMENSIONS,
    ClosureTolerances,
    ControlName,
    MissionSpec,
    ReserveKind,
    ReserveSpec,
    SegmentConstraints,
    SegmentKind,
    SegmentMode,
    SegmentSpec,
    VehicleSpec,
)
from .state import INTEGRATED_STATE, MissionState

__all__ = [
    "CLOSURE_DIMENSIONS",
    "GRAVITY_M_S2",
    "INTEGRATED_STATE",
    "MISSION_UNITS",
    "SOFTWARE_NAME",
    "SOFTWARE_VERSION",
    "AeroPoint",
    "AnalyticalFixedWingParticipant",
    "AnalyticalRotorcraftParticipant",
    "CampaignEvaluator",
    "CapabilityState",
    "CapabilityUnavailable",
    "ClosureError",
    "ClosureReport",
    "ClosureResidual",
    "ClosureTolerances",
    "ControlName",
    "ControlVariable",
    "MissionBalance",
    "MissionContractError",
    "MissionError",
    "MissionFidelity",
    "MissionMeta",
    "MissionOptimizationError",
    "MissionResult",
    "MissionSet",
    "MissionSetResult",
    "MissionSpec",
    "MissionState",
    "MissionTrace",
    "MissionValidationError",
    "MissionValidity",
    "NativeMissionBackend",
    "NativeMissionOutcome",
    "OperatingPoint",
    "PerformanceMapParticipant",
    "PerformanceParticipant",
    "PerformanceRejected",
    "PropagationPolicy",
    "PropulsionPoint",
    "ReserveError",
    "ReserveKind",
    "ReserveReport",
    "ReserveSpec",
    "ReserveVerdict",
    "SegmentConstraints",
    "SegmentKind",
    "SegmentMode",
    "SegmentSpec",
    "SegmentTrace",
    "TrajectoryOptimization",
    "TrajectoryOptimizationResult",
    "VehicleSpec",
    "apply_controls",
    "evaluate_closure",
    "evaluate_mission_set",
    "evaluate_reserves",
    "mission_campaign_objectives",
    "mission_design_outputs",
    "mission_evaluator",
    "native_mission_status",
    "objective_value",
    "optimize_trajectory",
    "propagate_mission",
    "require_native_mission",
    "run_mission",
    "solve_native_mission",
    "trajectory_study",
]
