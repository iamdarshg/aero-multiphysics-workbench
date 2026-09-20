"""Turbomachinery calibration, uncertainty, benchmarks, and design proof (TURBO 11).

Public API (downstream issues import these exact paths):

    from aeroworkbench_turbomachinery.calibration import (
        CalibrationDatum, CalibrationDataset, DatumKind, IngestReceipt,
        datum_from_mapping,
        BiasModel, AffineResponseModel, TurboCalibrationReceipt,
        calibrate_model, estimate_only,
        build_spec, build_plan, propagate_predictions,
        robust_constraint_margin, fidelity_escalation_decision,
        REFERENCE_CASES, BenchmarkExpectation, ReferenceOutcome,
        run_reference_case, check_reference_case,
        DesignProof, run_design_proof,
        native_calibration_status, request_native_calibration,
    )

Fitting reuses ``aeroworkbench_experiment`` identification; uncertainty
variables, sampling, and propagation reuse
``aeroworkbench_vehicle_systems.robust``. Native paths fail closed.
"""

from .benchmarks import (
    CASE_AXIAL_FAN,
    CASE_AXIAL_SHAFT,
    CASE_BRAYTON_CORE,
    CASE_RADIAL,
    REFERENCE_CASES,
    BenchmarkCheck,
    BenchmarkExpectation,
    ReferenceOutcome,
    benchmark_matrix_digest,
    check_reference_case,
    reference_architecture_payload,
    reference_cycle_design,
    run_reference_case,
)
from .calibrate import (
    MAX_CALIBRATION_POINTS,
    AffineResponseModel,
    BiasModel,
    TurboCalibrationReceipt,
    calibrate_model,
    estimate_only,
)
from .data import (
    DATUM_KINDS,
    DATUM_SOURCES,
    CalibrationDataset,
    CalibrationDatum,
    DatumKind,
    IngestReceipt,
    datum_from_mapping,
)
from .errors import (
    CalibrationCapabilityUnavailable,
    CalibrationError,
    CalibrationInputError,
)
from .native import (
    NATIVE_CALIBRATION_CAPABILITY,
    NativeCalibrationRequest,
    native_calibration_status,
    request_native_calibration,
)
from .proof import (
    PROOF_CASE,
    PROOF_EFFICIENCY_BASE,
    DesignProof,
    proof_rig_dataset,
    run_design_proof,
)
from .results import (
    DEFAULT_CALIBRATION_SOFTWARE,
    SOFTWARE_IDENTITY,
    SOFTWARE_VERSION,
    CalibrationFidelity,
    CalibrationSoftware,
    CalibrationValidity,
    calibration_provenance,
    screening_label,
)
from .uncertainty import (
    MAX_PROPAGATION_SAMPLES,
    ConstraintMargin,
    FidelityEscalation,
    ambient_condition_input,
    build_plan,
    build_spec,
    fidelity_escalation_decision,
    geometry_tolerance_input,
    map_correlation_input,
    material_scatter_input,
    propagate_predictions,
    robust_constraint_margin,
    uncertainty_digest,
)

__all__ = [
    "DATUM_KINDS",
    "DATUM_SOURCES",
    "DEFAULT_CALIBRATION_SOFTWARE",
    "MAX_CALIBRATION_POINTS",
    "MAX_PROPAGATION_SAMPLES",
    "NATIVE_CALIBRATION_CAPABILITY",
    "PROOF_CASE",
    "PROOF_EFFICIENCY_BASE",
    "REFERENCE_CASES",
    "SOFTWARE_IDENTITY",
    "SOFTWARE_VERSION",
    "CASE_AXIAL_FAN",
    "CASE_AXIAL_SHAFT",
    "CASE_BRAYTON_CORE",
    "CASE_RADIAL",
    "AffineResponseModel",
    "BenchmarkCheck",
    "BenchmarkExpectation",
    "BiasModel",
    "CalibrationCapabilityUnavailable",
    "CalibrationDataset",
    "CalibrationDatum",
    "CalibrationError",
    "CalibrationFidelity",
    "CalibrationInputError",
    "CalibrationSoftware",
    "CalibrationValidity",
    "ConstraintMargin",
    "DatumKind",
    "DesignProof",
    "FidelityEscalation",
    "IngestReceipt",
    "NativeCalibrationRequest",
    "ReferenceOutcome",
    "TurboCalibrationReceipt",
    "ambient_condition_input",
    "benchmark_matrix_digest",
    "build_plan",
    "build_spec",
    "calibrate_model",
    "calibration_provenance",
    "check_reference_case",
    "datum_from_mapping",
    "estimate_only",
    "fidelity_escalation_decision",
    "geometry_tolerance_input",
    "map_correlation_input",
    "material_scatter_input",
    "native_calibration_status",
    "propagate_predictions",
    "proof_rig_dataset",
    "reference_architecture_payload",
    "reference_cycle_design",
    "request_native_calibration",
    "robust_constraint_margin",
    "run_design_proof",
    "run_reference_case",
    "screening_label",
    "uncertainty_digest",
]
