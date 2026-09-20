"""VEHICLE-SYSTEMS 05: aircraft control allocation and handling qualities.

This subpackage moves from trim and generic controller primitives to
vehicle-level control: a control-effectiveness Jacobian contract across
surfaces, rotors, differential thrust, and tilt axes; bounded allocation with
saturation, rate limits, failures, and redundant actuators; bounded
gain-scheduled PID synthesis from trim/stability data; closed-loop
verification through the generic actuator/transient contracts; typed
handling-quality constraints that participate in campaign feasibility; and a
flight-test comparison seam. Every result carries source, fidelity, units,
validity, input hash, software identity, and provenance.

Public API (other workstreams import these exact paths):

    from aeroworkbench_vehicle_systems.control import (
        AXES, AllocationRequest, AllocationResult, AxisGains, AxisLoop,
        AxisPlant, CapabilityState, ClosedLoopReport, ClosedLoopSpec,
        ControlEffector, ControlFidelity, ControlMeta, ControlValidity,
        EffectivenessMatrix, EffectorFault, FaultKind, FlightTestComparison,
        GainBounds, GainSchedule, HandlingMetric, HandlingQualityCheck,
        HandlingQualityConstraint, HandlingQualityReport, StepMetrics,
        SynthesizedController, SynthesisTarget, TrimEffectivenessMap,
        actuators_for_effectors, allocate, build_effectiveness,
        closed_loop_campaign_evaluator, closed_loop_study_constraints,
        compare_flight_test, control_anticipation_parameter,
        effective_bounds, effectiveness_from_trim, evaluate_closed_loop,
        evaluate_handling_qualities, handling_campaign_outputs,
        handling_evaluator, handling_study_constraint, mode_metrics,
        require_native_closed_loop, native_closed_loop_status,
        roll_time_constant, simulate_step, solve_native_closed_loop,
        synthesize_axis_pid, synthesize_schedule,
        AllocationError, AllocationInfeasible, CapabilityUnavailable,
        ControlContractError, ControlError, HandlingQualityError,
        SynthesisError,
    )
"""

from .allocation import (
    ALLOCATION_METHODS,
    AllocationRequest,
    AllocationResult,
    EffectorFault,
    FaultKind,
    allocate,
    effective_bounds,
)
from .closedloop import (
    AxisLoop,
    ClosedLoopReport,
    ClosedLoopSpec,
    FlightTestComparison,
    StepMetrics,
    closed_loop_campaign_evaluator,
    closed_loop_study_constraints,
    compare_flight_test,
    evaluate_closed_loop,
    simulate_step,
)
from .contracts import (
    CONTROL_UNITS,
    SOFTWARE_NAME,
    SOFTWARE_VERSION,
    ControlFidelity,
    ControlMeta,
    ControlValidity,
)
from .effectiveness import (
    AXES,
    ControlEffector,
    EffectivenessMatrix,
    TrimEffectivenessMap,
    build_effectiveness,
    effectiveness_from_trim,
)
from .errors import (
    AllocationError,
    AllocationInfeasible,
    CapabilityUnavailable,
    ControlContractError,
    ControlError,
    HandlingQualityError,
    SynthesisError,
)
from .handling import (
    HandlingMetric,
    HandlingQualityCheck,
    HandlingQualityConstraint,
    HandlingQualityReport,
    control_anticipation_parameter,
    evaluate_handling_qualities,
    handling_campaign_outputs,
    handling_evaluator,
    handling_study_constraint,
    mode_metrics,
    roll_time_constant,
)
from .native import (
    CapabilityState,
    NativeClosedLoopBackend,
    NativeClosedLoopOutcome,
    native_closed_loop_status,
    require_native_closed_loop,
    solve_native_closed_loop,
)
from .synthesis import (
    AxisGains,
    AxisPlant,
    GainBounds,
    GainSchedule,
    SynthesisTarget,
    SynthesizedController,
    actuators_for_effectors,
    synthesize_axis_pid,
    synthesize_schedule,
)

__all__ = [
    "ALLOCATION_METHODS",
    "AXES",
    "CONTROL_UNITS",
    "SOFTWARE_NAME",
    "SOFTWARE_VERSION",
    "AllocationError",
    "AllocationInfeasible",
    "AllocationRequest",
    "AllocationResult",
    "AxisGains",
    "AxisLoop",
    "AxisPlant",
    "CapabilityState",
    "CapabilityUnavailable",
    "ClosedLoopReport",
    "ClosedLoopSpec",
    "ControlContractError",
    "ControlEffector",
    "ControlError",
    "ControlFidelity",
    "ControlMeta",
    "ControlValidity",
    "EffectivenessMatrix",
    "EffectorFault",
    "FaultKind",
    "FlightTestComparison",
    "GainBounds",
    "GainSchedule",
    "HandlingMetric",
    "HandlingQualityCheck",
    "HandlingQualityConstraint",
    "HandlingQualityError",
    "HandlingQualityReport",
    "NativeClosedLoopBackend",
    "NativeClosedLoopOutcome",
    "StepMetrics",
    "SynthesisError",
    "SynthesisTarget",
    "SynthesizedController",
    "TrimEffectivenessMap",
    "actuators_for_effectors",
    "allocate",
    "build_effectiveness",
    "closed_loop_campaign_evaluator",
    "closed_loop_study_constraints",
    "compare_flight_test",
    "control_anticipation_parameter",
    "effective_bounds",
    "effectiveness_from_trim",
    "evaluate_closed_loop",
    "evaluate_handling_qualities",
    "handling_campaign_outputs",
    "handling_evaluator",
    "handling_study_constraint",
    "mode_metrics",
    "native_closed_loop_status",
    "require_native_closed_loop",
    "roll_time_constant",
    "simulate_step",
    "solve_native_closed_loop",
    "synthesize_axis_pid",
    "synthesize_schedule",
]
