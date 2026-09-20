"""Generic thermodynamic cycle and multi-spool matching (TURBO 04).

Public API (later issues import these exact paths):

    from aeroworkbench_turbomachinery.cycle import (
        CycleDesign,
        compile_cycle_model,
        solve_cycle,
        solve_with_openmdao,
        build_screening_map,
    )

The analytical screening solver is cheap and explicitly labelled. The generic
OpenMDAO component network executes a real ``openmdao.Problem`` at its own
labelled fidelity. pyCycle is capability-gated and fails closed when absent.
"""

from .adapter import (
    OpenMdaoCycleEngine,
    OpenMdaoPolicy,
    PyCycleCase,
    PyCycleExecutionReceipt,
    PyCycleRunReceipt,
    parse_pycycle_result,
    prepare_pycycle_case,
    pycycle_supported_topology,
    request_pycycle_execution,
    request_pycycle_run,
    solve_with_openmdao,
    solve_with_pycycle,
)
from .brayton import (
    BRAYTON_SCREENING_FIDELITY,
    BraytonScreening,
    ideal_brayton_screening,
)
from .components import (
    COMPONENT_KINDS,
    ComponentEvaluation,
    ComponentParameters,
    evaluate_component,
)
from .contracts import (
    CycleCapabilityUnavailable,
    CycleEngineStatus,
    CycleFidelity,
    CycleModelError,
    CycleParserError,
    CycleValidity,
    OutOfEnvelopePolicy,
    probe_cycle_engine,
    probe_cycle_engines,
)
from .gas import AIR, COMBUSTION_GAS, GasProperties
from .maps import (
    MapEvaluation,
    MapLine,
    MapProvenance,
    OperatingMap,
    build_screening_map,
)
from .matching import (
    MatchingResiduals,
    ShaftPower,
    compute_residuals,
)
from .model import (
    CycleDesign,
    CycleModel,
    CycleNodeSpec,
    CycleShaftSpec,
    compile_cycle_model,
    edge_key,
    map_coefficients,
)
from .solver import (
    CycleOperatingPoint,
    CycleResult,
    CycleStationResult,
    resolve_spool_speeds,
    solve_cycle,
)

__all__ = [
    "AIR",
    "BRAYTON_SCREENING_FIDELITY",
    "COMBUSTION_GAS",
    "COMPONENT_KINDS",
    "BraytonScreening",
    "ComponentEvaluation",
    "ComponentParameters",
    "CycleCapabilityUnavailable",
    "CycleDesign",
    "CycleEngineStatus",
    "CycleFidelity",
    "CycleModel",
    "CycleModelError",
    "CycleNodeSpec",
    "CycleOperatingPoint",
    "CycleParserError",
    "CycleResult",
    "CycleShaftSpec",
    "CycleStationResult",
    "CycleValidity",
    "GasProperties",
    "MapEvaluation",
    "MapLine",
    "MapProvenance",
    "MatchingResiduals",
    "OpenMdaoCycleEngine",
    "OpenMdaoPolicy",
    "OperatingMap",
    "OutOfEnvelopePolicy",
    "PyCycleCase",
    "PyCycleExecutionReceipt",
    "PyCycleRunReceipt",
    "ShaftPower",
    "build_screening_map",
    "compile_cycle_model",
    "compute_residuals",
    "edge_key",
    "evaluate_component",
    "ideal_brayton_screening",
    "map_coefficients",
    "parse_pycycle_result",
    "prepare_pycycle_case",
    "probe_cycle_engine",
    "probe_cycle_engines",
    "pycycle_supported_topology",
    "request_pycycle_execution",
    "request_pycycle_run",
    "resolve_spool_speeds",
    "solve_cycle",
    "solve_with_openmdao",
    "solve_with_pycycle",
]
