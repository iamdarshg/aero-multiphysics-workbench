"""Generic transient system dynamics, controls, actuators, and protection.

The package provides a product-neutral transient capability: typed continuous
state (shaft/spool speed, rotational inertia, storage, electrical, actuator,
control, thermal capacitance, vehicle/airflow), deterministic declared
integrators, a controller contract (PID, schedule, lookup, state machine,
sensor filter), actuator dynamics with rate/position limits and lags, typed
protection logic (limits, trips, interlocks, hysteresis), discrete events,
and solver coupling through the shared core contracts. Every result carries
source/fidelity/units/validity/input-hash/software-identity/provenance; native
transient coordinators are capability-gated and fail closed when absent.
"""

from .actuators import ActuatorResult, ActuatorSpec
from .controls import (
    Controller,
    ControllerState,
    FirstOrderSensorFilter,
    LookupController,
    PIDController,
    ScheduleController,
    StateMachineController,
    StateTransition,
)
from .coupling import CouplingExchange, CouplingPort, SolverCoupling
from .errors import (
    CapabilityUnavailable,
    LimitExceeded,
    ProtectionTrip,
    SystemDynamicsError,
    TransientValidationError,
)
from .events import DiscreteEvent, EventKind, EventSchedule
from .integrators import (
    DerivativeFn,
    InputProvider,
    IntegrationHistory,
    IntegrationMethod,
    IntegratorSpec,
    advance,
    integrate_fixed_step,
)
from .models import (
    BatteryStateOfChargeModel,
    CompositePlant,
    FirstOrderLagModel,
    PlantModel,
    SpoolModel,
    StorageVolumeModel,
    ThermalCapacitanceModel,
    VehicleSpeedModel,
)
from .native import (
    DEFAULT_NATIVE_REQUIREMENT,
    NativeTransientBackend,
    NativeTransientStatus,
    native_transient_status,
    require_native_transient,
    solve_native_transient,
)
from .participants import (
    SYSTEM_DYNAMICS_PARTICIPANTS,
    PortSpec,
    SystemParticipant,
    participant_ids,
    system_participants,
)
from .protection import (
    InterlockSpec,
    ProtectionKind,
    ProtectionLimit,
    ProtectionResult,
    apply_interlocks,
    evaluate_protection,
)
from .provenance import (
    SOFTWARE_IDENTITY,
    SOFTWARE_VERSION,
    analytical_provenance,
    native_provenance,
    reduced_provenance,
)
from .results import (
    EventRecord,
    IntegratorReceipt,
    SteadyStateResult,
    TimeSeries,
    TransientResult,
)
from .state import DynamicStateSpec, StateKind, StateVariable
from .transient import TransientScenario, find_steady_state, simulate_transient
from .units import SI_UNITS, UnitError, require_unit
from .validity import Fidelity, Validity, finite

__all__ = [
    "DEFAULT_NATIVE_REQUIREMENT",
    "SI_UNITS",
    "SOFTWARE_IDENTITY",
    "SOFTWARE_VERSION",
    "SYSTEM_DYNAMICS_PARTICIPANTS",
    "ActuatorResult",
    "ActuatorSpec",
    "BatteryStateOfChargeModel",
    "CapabilityUnavailable",
    "CompositePlant",
    "Controller",
    "ControllerState",
    "CouplingExchange",
    "CouplingPort",
    "DerivativeFn",
    "DiscreteEvent",
    "DynamicStateSpec",
    "EventKind",
    "EventRecord",
    "EventSchedule",
    "Fidelity",
    "FirstOrderLagModel",
    "FirstOrderSensorFilter",
    "InputProvider",
    "IntegrationHistory",
    "IntegrationMethod",
    "IntegratorReceipt",
    "IntegratorSpec",
    "InterlockSpec",
    "LimitExceeded",
    "LookupController",
    "NativeTransientBackend",
    "NativeTransientStatus",
    "PIDController",
    "PlantModel",
    "PortSpec",
    "ProtectionKind",
    "ProtectionLimit",
    "ProtectionResult",
    "ProtectionTrip",
    "ScheduleController",
    "SolverCoupling",
    "SpoolModel",
    "StateKind",
    "StateMachineController",
    "StateTransition",
    "StateVariable",
    "SteadyStateResult",
    "StorageVolumeModel",
    "SystemDynamicsError",
    "SystemParticipant",
    "ThermalCapacitanceModel",
    "TimeSeries",
    "TransientResult",
    "TransientScenario",
    "TransientValidationError",
    "UnitError",
    "Validity",
    "VehicleSpeedModel",
    "advance",
    "analytical_provenance",
    "apply_interlocks",
    "evaluate_protection",
    "find_steady_state",
    "finite",
    "integrate_fixed_step",
    "native_provenance",
    "native_transient_status",
    "participant_ids",
    "reduced_provenance",
    "require_native_transient",
    "require_unit",
    "simulate_transient",
    "solve_native_transient",
    "system_participants",
]
