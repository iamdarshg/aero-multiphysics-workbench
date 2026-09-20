"""End-to-end rotary-gas design proof (issue TURBO 11, part E).

One compact reference runs the complete new stack deterministically:
architecture -> meanline triangles -> cycle screening -> off-design
multipoint -> calibration -> uncertainty propagation -> provenance-backed
candidate. Heavy native stages (CAD/mesh/native campaign) are recorded as
explicitly unavailable; this proof never fabricates validation.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Any

from aeroworkbench_core.types import ResultSource

from .. import architecture_from_payload, architecture_hash
from ..canonical import content_digest
from ..cycle import CycleDesign, build_screening_map, compile_cycle_model, solve_cycle
from ..meanline import euler_work_j_kg, solve_triangle
from ..offdesign import (
    MapReference,
    OffdesignFidelity,
    OperatingPoint,
    evaluate_multipoint,
    point_result,
)
from .benchmarks import (
    CASE_AXIAL_FAN,
    reference_architecture_payload,
    reference_cycle_design,
)
from .calibrate import BiasModel, TurboCalibrationReceipt, calibrate_model
from .data import CalibrationDataset, CalibrationDatum, DatumKind
from .errors import CalibrationInputError
from .native import NATIVE_CALIBRATION_CAPABILITY, native_calibration_status
from .results import (
    CalibrationFidelity,
    CalibrationSoftware,
    CalibrationValidity,
    calibration_provenance,
)
from .uncertainty import (
    ambient_condition_input,
    build_plan,
    build_spec,
    fidelity_escalation_decision,
    map_correlation_input,
    propagate_predictions,
    robust_constraint_margin,
)

PROOF_CASE = CASE_AXIAL_FAN
PROOF_EFFICIENCY_BASE = 0.90


def proof_rig_dataset() -> CalibrationDataset:
    data = tuple(
        CalibrationDatum(
            datum_id=f"t11-proof-rig-{index:02d}",
            kind=DatumKind.RIG_MEASUREMENT,
            quantity="fan_efficiency",
            measured=0.90 + (0.002 if index % 2 == 0 else -0.002),
            uncertainty=0.005,
            unit="1",
            source="synthetic-test-rig",
            revision="t11-1",
            inputs=(("corrected_flow", 3.6 + 0.2 * float(index)),),
            conditions=(("facility", "synthetic-rig-t11"),),
            validity_range=(("corrected_flow", 3.6), ("corrected_flow", 4.8)),
        )
        for index in range(6)
    )
    return CalibrationDataset(
        dataset_id="t11-proof-fan-efficiency", data=data, source="synthetic-test-rig"
    )


@dataclass(frozen=True, slots=True)
class DesignProof:
    case_id: str
    architecture_hash: str
    triangle_work_j_kg: float
    cycle_thrust_n: float
    cycle_converged: bool
    multipoint_ids: tuple[str, ...]
    multipoint_passed: bool
    calibration: TurboCalibrationReceipt
    thrust_mean_n: float
    thrust_std_n: float
    thrust_margin_n: float
    robust_pass: bool
    escalation: bool
    native_status: str
    source: str
    fidelity: str
    units: tuple[tuple[str, str], ...]
    validity: CalibrationValidity
    input_hash: str
    software: CalibrationSoftware
    provenance: Any

    def canonical(self) -> dict[str, Any]:
        return {
            "caseId": self.case_id,
            "architectureHash": self.architecture_hash,
            "triangleWorkJkg": self.triangle_work_j_kg,
            "cycleThrustN": self.cycle_thrust_n,
            "cycleConverged": self.cycle_converged,
            "multipointIds": list(self.multipoint_ids),
            "multipointPassed": self.multipoint_passed,
            "calibrationHash": self.calibration.result_hash,
            "thrustMeanN": self.thrust_mean_n,
            "thrustStdN": self.thrust_std_n,
            "thrustMarginN": self.thrust_margin_n,
            "robustPass": self.robust_pass,
            "escalation": self.escalation,
            "nativeStatus": self.native_status,
            "source": self.source,
            "fidelity": self.fidelity,
            "units": [[n, u] for n, u in self.units],
            "validity": self.validity.canonical(),
            "inputHash": self.input_hash,
            "software": self.software.canonical(),
            "provenance": self.provenance.model_dump(mode="json"),
        }

    @property
    def result_hash(self) -> str:
        return content_digest(self.canonical())


_PROOF_UNITS: tuple[tuple[str, str], ...] = (
    ("triangleWorkJkg", "J/kg"),
    ("cycleThrustN", "N"),
    ("thrustMeanN", "N"),
    ("thrustStdN", "N"),
    ("thrustMarginN", "N"),
)


def run_design_proof(case_id: str = PROOF_CASE) -> DesignProof:
    if case_id != PROOF_CASE:
        raise CalibrationInputError(f"PROOF_CASE_UNSUPPORTED:{case_id}")
    payload = reference_architecture_payload(case_id)
    architecture = architecture_from_payload(payload)
    arch_hash = architecture_hash(architecture)

    inlet = solve_triangle(
        station_id="1",
        blade_speed_m_s=150.0,
        axial_velocity_m_s=140.0,
        tangential_velocity_m_s=0.0,
    )
    outlet = solve_triangle(
        station_id="2",
        blade_speed_m_s=150.0,
        axial_velocity_m_s=140.0,
        tangential_velocity_m_s=55.0,
    )
    work = euler_work_j_kg(inlet=inlet, outlet=outlet)

    design = reference_cycle_design(case_id)
    model = compile_cycle_model(design)
    solved = solve_cycle(model)

    fan_map = MapReference(
        node_id="fan",
        component_map=build_screening_map(
            machine="fan",
            design_corrected_speed=3000.0,
            design_corrected_flow=4.5,
            design_pressure_ratio=1.158,
            design_efficiency=PROOF_EFFICIENCY_BASE,
        ),
        design_corrected_flow=4.5,
    )
    points = (
        OperatingPoint(point_id="takeoff", mass_flow_kg_s=4.5, throttle=0.9, weight=0.5),
        OperatingPoint(point_id="cruise", mass_flow_kg_s=3.8, throttle=0.7, weight=0.3),
        OperatingPoint(point_id="idle", mass_flow_kg_s=3.6, throttle=0.3, weight=0.2),
    )
    matches, _ = evaluate_multipoint(design, points, maps=(fan_map,))
    multipoint_passed = all(m.converged and m.hard_passed for m in matches)
    by_id = {p.point_id: p for p in points}
    for match in matches:
        result = point_result(
            by_id[match.point_id], match, fidelity=OffdesignFidelity.MAP_PRELIMINARY
        )
        if result.validity.passed is False:
            multipoint_passed = False

    dataset = proof_rig_dataset()
    receipt = calibrate_model(
        BiasModel(PROOF_EFFICIENCY_BASE),
        dataset,
        ("efficiency_bias",),
        {"efficiency_bias": (-0.05, 0.05)},
        max_validation_rmse=0.01,
    )
    bias = receipt.parameters[0][1]
    bias_std = max(receipt.parameters[0][2], 1e-6)

    spec = build_spec(
        "t11-proof-uncertainty",
        (
            map_correlation_input(
                "fan_efficiency", "1", PROOF_EFFICIENCY_BASE + bias, bias_std
            ),
            ambient_condition_input("ambient_pressure", "Pa", 101325.0, 1500.0),
        ),
    )
    plan = build_plan("t11-proof-plan", 32, seed=11)
    base_params = dict(design.component_parameters)

    def _evaluate(sample: Mapping[str, float]) -> Mapping[str, float]:
        params = dict(base_params)
        fan = params["fan"]
        params["fan"] = replace(
            fan,
            isentropic_efficiency=max(0.5, min(1.0, float(sample["fan_efficiency"]))),
        )
        candidate = CycleDesign(
            architecture=design.architecture,
            component_parameters=tuple(params.items()),
            gas=design.gas,
            ambient_total_pressure_pa=float(sample["ambient_pressure"]),
            ambient_total_temperature_k=design.ambient_total_temperature_k,
            mass_flow_kg_s=design.mass_flow_kg_s,
        )
        outcome = solve_cycle(compile_cycle_model(candidate))
        if not outcome.converged:
            raise CalibrationInputError("PROOF_PROPAGATION_SAMPLE_DID_NOT_CONVERGE")
        return {"thrust_n": float(outcome.thrust_n)}

    propagated = propagate_predictions(spec, plan, _evaluate, ("thrust_n",))
    margin = robust_constraint_margin(
        "thrust_n", "N", 0.5 * float(solved.thrust_n), propagated, upper_bound=False
    )
    escalation = fidelity_escalation_decision(propagated)
    native = native_calibration_status()
    native_label = f"{NATIVE_CALIBRATION_CAPABILITY}:{native.state.value}"

    checks = {
        "architecture-hashable": True,
        "meanline-triangles-solved": work > 0.0,
        "cycle-converged": solved.converged,
        "multipoint-passed": multipoint_passed,
        "calibration-passed": receipt.validity.passed,
        "robust-margin-passed": margin.robust_pass,
        "native-fails-closed": not native.available,
    }
    passed = all(checks.values())
    digest_payload = {
        "caseId": case_id,
        "architectureHash": arch_hash,
        "modelDigest": model.digest,
        "calibrationHash": receipt.result_hash,
        "uncertaintyDigest": propagated.samples_digest,
    }
    digest = content_digest(digest_payload)
    return DesignProof(
        case_id=case_id,
        architecture_hash=arch_hash,
        triangle_work_j_kg=work,
        cycle_thrust_n=float(solved.thrust_n),
        cycle_converged=solved.converged,
        multipoint_ids=tuple(m.point_id for m in matches),
        multipoint_passed=multipoint_passed,
        calibration=receipt,
        thrust_mean_n=propagated.moment_for("thrust_n").mean,
        thrust_std_n=propagated.moment_for("thrust_n").std,
        thrust_margin_n=margin.margin,
        robust_pass=margin.robust_pass,
        escalation=escalation.escalate,
        native_status=native_label,
        source=ResultSource.ANALYTICAL.value,
        fidelity=CalibrationFidelity.CALIBRATED_SCREENING.value,
        units=_PROOF_UNITS,
        validity=CalibrationValidity(
            passed=passed,
            checks=checks,
            detail="" if passed else "design proof gate failed",
        ),
        input_hash=digest,
        software=CalibrationSoftware(),
        provenance=calibration_provenance(
            ResultSource.ANALYTICAL,
            CalibrationFidelity.CALIBRATED_SCREENING,
            digest_payload,
            (
                "Calibrated screening proof; heavy native stages explicitly unavailable.",
                "Synthetic rig data only; not a validation claim.",
            ),
        ),
    )


__all__ = [
    "PROOF_CASE",
    "PROOF_EFFICIENCY_BASE",
    "DesignProof",
    "proof_rig_dataset",
    "run_design_proof",
]
