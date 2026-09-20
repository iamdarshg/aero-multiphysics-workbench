"""AIRFRAME 05: trim, static/dynamic stability, and control-authority solvers.

Public API (later AIRFRAME issues import these exact paths):

    from aeroworkbench_airframe.trim import (
        AerodynamicCoefficientProvider,
        AeroReference,
        AeroState,
        AeroCoefficients,
        DerivativeBundle,
        LongitudinalDerivatives,
        LateralDirectionalDerivatives,
        LinearAeroModel,
        FlightCondition,
        TrimVariable,
        TrimSpec,
        solve_trim,
        trim_level_flight,
        evaluate_static_stability,
        evaluate_dynamic_stability,
        evaluate_control_authority,
        verify_trim_nonlinear,
    )

The aerodynamic seam is the structural :class:`AerodynamicCoefficientProvider`
protocol, so AIRFRAME 05 never depends on VSPAERO/OpenVSP internals. Every
result carries source/fidelity/units/validity/input-hash/software identity and
provenance; missing coefficients, derivatives, or CG fail closed. Screening trim
is kept distinct from the capability-gated native/nonlinear verification seam.
"""

from .analytic_aero import LinearAeroModel, analytic_lift_curve_slope
from .authority import (
    ControlAuthorityReport,
    ControlSurfaceAuthority,
    evaluate_control_authority,
)
from .contract import (
    DEFAULT_SOFTWARE,
    TRIM_RESULT_UNITS,
    AeroCoefficients,
    AerodynamicCoefficientProvider,
    AeroReference,
    AeroState,
    DerivativeBundle,
    FlightCondition,
    LateralDirectionalDerivatives,
    LongitudinalDerivatives,
    ResultMeta,
    SoftwareIdentity,
    TrimFidelity,
    Validity,
    result_meta,
)
from .dynamics import (
    DynamicStabilityReport,
    FlightMode,
    classify_lateral_modes,
    classify_longitudinal_modes,
    evaluate_dynamic_stability,
    extract_modes,
    lateral_state_matrix,
    longitudinal_state_matrix,
)
from .equilibrium import (
    INFEASIBLE,
    NOT_CONVERGED,
    PREFLIGHT_INVALID,
    TRIMMED,
    NewtonSettings,
    TrimResiduals,
    TrimResult,
    TrimSolution,
    TrimSpec,
    TrimVariable,
    solve_trim,
    trim_level_flight,
)
from .errors import (
    AeroCoefficientError,
    ControlAuthorityError,
    NativeTrimCapabilityError,
    TrimError,
    TrimSolverError,
)
from .native import (
    NativeTrimCapability,
    NativeTrimRequirement,
    native_trim_capability,
    require_native_trim,
    verification_fidelity,
    verify_trim_nonlinear,
)
from .stability import (
    StabilityFinding,
    StaticStabilityReport,
    evaluate_static_stability,
    neutral_point,
    static_margin,
)

__all__ = [
    "AeroCoefficientError",
    "AeroCoefficients",
    "AeroReference",
    "AeroState",
    "AerodynamicCoefficientProvider",
    "ControlAuthorityError",
    "ControlAuthorityReport",
    "ControlSurfaceAuthority",
    "DEFAULT_SOFTWARE",
    "DerivativeBundle",
    "DynamicStabilityReport",
    "FlightCondition",
    "FlightMode",
    "INFEASIBLE",
    "LateralDirectionalDerivatives",
    "LinearAeroModel",
    "LongitudinalDerivatives",
    "NOT_CONVERGED",
    "NativeTrimCapability",
    "NativeTrimCapabilityError",
    "NativeTrimRequirement",
    "NewtonSettings",
    "PREFLIGHT_INVALID",
    "ResultMeta",
    "StaticStabilityReport",
    "StabilityFinding",
    "SoftwareIdentity",
    "TRIM_RESULT_UNITS",
    "TRIMMED",
    "TrimError",
    "TrimFidelity",
    "TrimResiduals",
    "TrimResult",
    "TrimSolution",
    "TrimSolverError",
    "TrimSpec",
    "TrimVariable",
    "Validity",
    "analytic_lift_curve_slope",
    "classify_lateral_modes",
    "classify_longitudinal_modes",
    "evaluate_control_authority",
    "evaluate_dynamic_stability",
    "evaluate_static_stability",
    "extract_modes",
    "lateral_state_matrix",
    "longitudinal_state_matrix",
    "native_trim_capability",
    "neutral_point",
    "require_native_trim",
    "result_meta",
    "solve_trim",
    "static_margin",
    "trim_level_flight",
    "verification_fidelity",
    "verify_trim_nonlinear",
]
