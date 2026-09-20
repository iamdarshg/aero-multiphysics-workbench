"""External-aerodynamics fidelity ladder for generic lifting configurations.

Three implemented levels share one typed contract:

* ``analytical`` - closed-form finite-wing lifting-line screening and a
  component parasite-drag build-up;
* ``lifting_line`` - a coarse vortex-lattice lifting-line solution;
* ``vlm`` - a full horseshoe vortex-lattice solution producing ``CL``/``CD``/
  ``CY``/``Cl``/``Cm``/``Cn``, distributed span loads, and stability/control
  derivatives.

The governed native level (``vspaero``) is capability-gated and fails closed
when OpenVSP/VSPAERO is absent; the OpenFOAM/SU2 ``full_field`` seam is not
implemented and also fails closed. No analytical or VLM result is ever labelled
native.

Public API for downstream AIRFRAME/trim work::

    from aeroworkbench_airframe.external_aero import (
        ExternalAeroCase,
        ExternalAeroResult,
        AeroCoefficients,
        AeroDerivatives,
        AeroReference,
        ExternalAeroFidelity,
        VlmOptions,
        solve_vlm,
        evaluate_analytic,
        solve_external_aero,
        study_vlm_convergence,
    )
"""

from .analytic import (
    ANALYTIC_MODEL,
    DragComponent,
    compressibility_friction_factor,
    drag_buildup,
    evaluate_analytic,
    finite_wing_lift_curve_slope,
    flat_plate_friction_coefficient,
    oswald_efficiency,
)
from .case import (
    MM_TO_M,
    SYMMETRY_MODES,
    ExternalAeroCase,
    GeometryReference,
    control_alpha_increment_deg,
    control_effectiveness,
    cosine_fractions,
    derive_geometry_reference,
    interpolate_stations,
    station_aero,
)
from .contracts import (
    ANALYTICAL_VALIDITY_LIMITS,
    SOFTWARE_IDENTITY,
    SOFTWARE_NAME,
    SOFTWARE_VERSION,
    VLM_VALIDITY_LIMITS,
    VSPAERO_VALIDITY_LIMITS,
    AeroCoefficients,
    AeroDerivatives,
    AeroReference,
    AeroValidity,
    AeroValidityLimits,
    ConvergenceRecord,
    ExternalAeroFidelity,
    ExternalAeroResult,
    SpanLoad,
    evaluate_aero_validity,
)
from .convergence import (
    DEFAULT_PANEL_LADDER,
    run_vlm_independence_report,
    study_vlm_convergence,
    vlm_convergence_record,
    with_vlm_convergence,
)
from .errors import (
    ExternalAeroCapabilityUnavailableError,
    ExternalAeroError,
    ExternalAeroValidationError,
    ExternalAeroValidityError,
)
from .ladder import (
    EXTERNAL_AERO_LADDER,
    LIFTING_LINE_PANELS,
    plan_external_aero_fidelity,
    solve_external_aero,
)
from .native import (
    VSPAERO_EXECUTABLES,
    VspaeroBackend,
    VspaeroCapability,
    VspaeroSolution,
    prepare_vspaero_case,
    probe_any_vspaero_capability,
    probe_vspaero_capability,
    require_vspaero_capability,
    solve_vspaero,
    vspaero_case_manifest,
)
from .polar import (
    PolarPoint,
    ProfilePolar,
    SectionCoefficients,
    SectionModel,
    TabulatedPolarSection,
    ThinAirfoilSection,
    polar_from_points,
    section_model_for_profile,
)
from .reference import reference_from_altitude, reference_from_conditions
from .vlm import (
    VLM_MODEL,
    VlmOptions,
    solve_vlm,
    vlm_panel_digest,
)

__all__ = [
    "ANALYTIC_MODEL",
    "ANALYTICAL_VALIDITY_LIMITS",
    "DEFAULT_PANEL_LADDER",
    "EXTERNAL_AERO_LADDER",
    "LIFTING_LINE_PANELS",
    "MM_TO_M",
    "SOFTWARE_IDENTITY",
    "SOFTWARE_NAME",
    "SOFTWARE_VERSION",
    "SYMMETRY_MODES",
    "VLM_MODEL",
    "VLM_VALIDITY_LIMITS",
    "VSPAERO_EXECUTABLES",
    "VSPAERO_VALIDITY_LIMITS",
    "AeroCoefficients",
    "AeroDerivatives",
    "AeroReference",
    "AeroValidity",
    "AeroValidityLimits",
    "ConvergenceRecord",
    "DragComponent",
    "ExternalAeroCapabilityUnavailableError",
    "ExternalAeroCase",
    "ExternalAeroError",
    "ExternalAeroFidelity",
    "ExternalAeroResult",
    "ExternalAeroValidationError",
    "ExternalAeroValidityError",
    "GeometryReference",
    "ProfilePolar",
    "PolarPoint",
    "SectionCoefficients",
    "SectionModel",
    "SpanLoad",
    "TabulatedPolarSection",
    "ThinAirfoilSection",
    "VlmOptions",
    "VspaeroBackend",
    "VspaeroCapability",
    "VspaeroSolution",
    "compressibility_friction_factor",
    "control_alpha_increment_deg",
    "control_effectiveness",
    "cosine_fractions",
    "derive_geometry_reference",
    "drag_buildup",
    "evaluate_aero_validity",
    "evaluate_analytic",
    "finite_wing_lift_curve_slope",
    "flat_plate_friction_coefficient",
    "interpolate_stations",
    "oswald_efficiency",
    "plan_external_aero_fidelity",
    "polar_from_points",
    "prepare_vspaero_case",
    "probe_any_vspaero_capability",
    "probe_vspaero_capability",
    "reference_from_altitude",
    "reference_from_conditions",
    "require_vspaero_capability",
    "run_vlm_independence_report",
    "section_model_for_profile",
    "solve_external_aero",
    "solve_vlm",
    "solve_vspaero",
    "station_aero",
    "study_vlm_convergence",
    "vlm_convergence_record",
    "vlm_panel_digest",
    "vspaero_case_manifest",
    "with_vlm_convergence",
]
