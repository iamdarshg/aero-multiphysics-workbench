"""Reference benchmark matrix proving portability (issue TURBO 11, part D).

Four compact, non-product-specific rotating-gas architectures share the same
generic architecture/cycle/off-design machinery:
- electrically driven axial fan / ducted rotor;
- multi-stage axial compressor/turbine shaft system;
- radial compressor plus diffuser path;
- heat-addition Brayton core with combustor/turbine/nozzle.

Expectations pin architecture hashes and screening scalars with tolerances so
future changes cannot silently alter sign conventions or cycle closure.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from aeroworkbench_core.types import ResultSource

from .. import architecture_from_payload, architecture_hash
from ..canonical import content_digest
from ..cycle import AIR, COMBUSTION_GAS, CycleDesign, compile_cycle_model, solve_cycle
from ..cycle.components import ComponentParameters
from .errors import CalibrationInputError
from .results import (
    CalibrationFidelity,
    CalibrationSoftware,
    CalibrationValidity,
    calibration_provenance,
)

CASE_AXIAL_FAN = "t11-axial-fan"
CASE_AXIAL_SHAFT = "t11-axial-shaft"
CASE_RADIAL = "t11-radial-path"
CASE_BRAYTON_CORE = "t11-brayton-core"

REFERENCE_CASES: tuple[str, ...] = (
    CASE_AXIAL_FAN,
    CASE_AXIAL_SHAFT,
    CASE_RADIAL,
    CASE_BRAYTON_CORE,
)


def _station(
    station_id: str,
    pressures: tuple[float, float] | None = None,
    mass_flow: float | None = None,
) -> dict[str, Any]:
    state: dict[str, Any] = {}
    if pressures is not None:
        state["totalPressure"] = {"value": pressures[0], "unit": "Pa"}
        state["totalTemperature"] = {"value": pressures[1], "unit": "K"}
    if mass_flow is not None:
        state["massFlow"] = {"value": mass_flow, "unit": "kg/s"}
    return {"id": station_id, "state": state}


def _row(
    row_id: str,
    node: str,
    role: str,
    frame: str,
    station_in: str,
    station_out: str,
    shaft: str | None,
    family: str,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": row_id,
        "node": node,
        "role": role,
        "frame": frame,
        "stationIn": station_in,
        "stationOut": station_out,
        "rowCount": 1,
        "periodicity": 12,
        "family": family,
    }
    if shaft is not None:
        payload["shaft"] = shaft
    return payload


def reference_architecture_payload(case_id: str) -> dict[str, Any]:
    if case_id == CASE_AXIAL_FAN:
        return {
            "schemaVersion": 1,
            "architectureId": case_id,
            "defaultFluid": {"identity": "dry-air"},
            "nodes": [
                {"id": "ambient", "kind": "ambient"},
                {"id": "inlet", "kind": "inlet"},
                {"id": "fan", "kind": "fan_stage"},
                {"id": "nozzle", "kind": "nozzle"},
                {"id": "exhaust", "kind": "exhaust"},
                {"id": "motor", "kind": "motor_coupling"},
            ],
            "edges": [
                {"from": "ambient", "to": "inlet", "kind": "flow", "station": "0"},
                {"from": "inlet", "to": "fan", "kind": "flow", "station": "1"},
                {"from": "fan", "to": "nozzle", "kind": "flow", "station": "2"},
                {"from": "nozzle", "to": "exhaust", "kind": "flow", "station": "3"},
            ],
            "stations": [
                _station("0", (101325.0, 288.15)),
                _station("1", (95000.0, 288.15), 4.5),
                _station("2", (110000.0, 305.0)),
                _station("3", (109000.0, 304.5)),
            ],
            "rows": [
                _row("fan-rotor", "fan", "work_adding", "rotating", "1", "2", "fan-spool", "axial")
            ],
            "shafts": [
                {
                    "id": "fan-spool",
                    "kind": "single",
                    "members": ["fan-rotor"],
                    "speed": {"kind": "speed", "value": {"value": 3000, "unit": "rpm"}},
                    "mechanicalLossFraction": 0.0,
                    "couplings": [
                        {
                            "id": "motor-drive",
                            "kind": "electric_motor",
                            "targetNode": "motor",
                            "efficiency": 0.95,
                        }
                    ],
                }
            ],
        }
    if case_id == CASE_AXIAL_SHAFT:
        return {
            "schemaVersion": 1,
            "architectureId": case_id,
            "defaultFluid": {"identity": "combustion-gas"},
            "nodes": [
                {"id": "ambient", "kind": "ambient"},
                {"id": "inlet", "kind": "inlet"},
                {"id": "c1", "kind": "compressor_stage"},
                {"id": "c2", "kind": "compressor_stage"},
                {"id": "combustor", "kind": "combustor"},
                {"id": "t1", "kind": "turbine_stage"},
                {"id": "exhaust", "kind": "exhaust"},
                {"id": "load", "kind": "mechanical_load"},
            ],
            "edges": [
                {"from": "ambient", "to": "inlet", "kind": "flow", "station": "0"},
                {"from": "inlet", "to": "c1", "kind": "flow", "station": "1"},
                {"from": "c1", "to": "c2", "kind": "flow", "station": "2"},
                {"from": "c2", "to": "combustor", "kind": "flow", "station": "3"},
                {"from": "combustor", "to": "t1", "kind": "flow", "station": "4"},
                {"from": "t1", "to": "exhaust", "kind": "flow", "station": "5"},
            ],
            "stations": [
                _station("0", (101325.0, 288.15)),
                _station("1", (99000.0, 288.15), 6.0),
                _station("2", (188000.0, 340.0)),
                _station("3", (357000.0, 400.0)),
                _station("4", (343000.0, 1350.0)),
                _station("5", (110000.0, 1000.0)),
            ],
            "rows": [
                _row("c1-rotor", "c1", "work_adding", "rotating", "1", "2", "core-spool", "axial"),
                _row("c2-rotor", "c2", "work_adding", "rotating", "2", "3", "core-spool", "axial"),
                _row(
                    "t1-rotor",
                    "t1",
                    "work_extracting",
                    "rotating",
                    "4",
                    "5",
                    "core-spool",
                    "axial",
                ),
            ],
            "shafts": [
                {
                    "id": "core-spool",
                    "kind": "common",
                    "members": ["c1-rotor", "c2-rotor", "t1-rotor"],
                    "speed": None,
                    "mechanicalLossFraction": 0.02,
                    "couplings": [
                        {
                            "id": "power-offtake",
                            "kind": "mechanical_load",
                            "targetNode": "load",
                            "efficiency": 0.98,
                        }
                    ],
                }
            ],
        }
    if case_id == CASE_RADIAL:
        return {
            "schemaVersion": 1,
            "architectureId": case_id,
            "defaultFluid": {"identity": "dry-air"},
            "nodes": [
                {"id": "ambient", "kind": "ambient"},
                {"id": "inlet", "kind": "inlet"},
                {"id": "impeller", "kind": "compressor_stage"},
                {"id": "diffuser", "kind": "diffuser"},
                {"id": "outlet", "kind": "exhaust"},
                {"id": "motor", "kind": "motor_coupling"},
            ],
            "edges": [
                {"from": "ambient", "to": "inlet", "kind": "flow", "station": "0"},
                {"from": "inlet", "to": "impeller", "kind": "flow", "station": "1"},
                {"from": "impeller", "to": "diffuser", "kind": "flow", "station": "2"},
                {"from": "diffuser", "to": "outlet", "kind": "flow", "station": "3"},
            ],
            "stations": [
                _station("0", (101325.0, 288.15)),
                _station("1", (98000.0, 288.15), 0.8),
                _station("2", (340000.0, 420.0)),
                _station("3", (330000.0, 421.0)),
            ],
            "rows": [
                _row(
                    "impeller-rotor",
                    "impeller",
                    "work_adding",
                    "rotating",
                    "1",
                    "2",
                    "rc-spool",
                    "radial",
                ),
                _row(
                    "diffuser-vanes",
                    "diffuser",
                    "diffuser_guide",
                    "stationary",
                    "2",
                    "3",
                    None,
                    "radial",
                ),
            ],
            "shafts": [
                {
                    "id": "rc-spool",
                    "kind": "single",
                    "members": ["impeller-rotor"],
                    "speed": {"kind": "speed", "value": {"value": 45000, "unit": "rpm"}},
                    "mechanicalLossFraction": 0.0,
                    "couplings": [
                        {
                            "id": "motor-drive",
                            "kind": "electric_motor",
                            "targetNode": "motor",
                            "efficiency": 0.93,
                        }
                    ],
                }
            ],
        }
    if case_id == CASE_BRAYTON_CORE:
        return {
            "schemaVersion": 1,
            "architectureId": case_id,
            "defaultFluid": {"identity": "combustion-gas"},
            "nodes": [
                {"id": "ambient", "kind": "ambient"},
                {"id": "inlet", "kind": "inlet"},
                {"id": "compressor", "kind": "compressor_stage"},
                {"id": "combustor", "kind": "combustor"},
                {"id": "turbine", "kind": "turbine_stage"},
                {"id": "nozzle", "kind": "nozzle"},
                {"id": "exhaust", "kind": "exhaust"},
                {"id": "load", "kind": "mechanical_load"},
            ],
            "edges": [
                {"from": "ambient", "to": "inlet", "kind": "flow", "station": "0"},
                {"from": "inlet", "to": "compressor", "kind": "flow", "station": "1"},
                {"from": "compressor", "to": "combustor", "kind": "flow", "station": "2"},
                {"from": "combustor", "to": "turbine", "kind": "flow", "station": "3"},
                {"from": "turbine", "to": "nozzle", "kind": "flow", "station": "4"},
                {"from": "nozzle", "to": "exhaust", "kind": "flow", "station": "5"},
            ],
            "stations": [
                _station("0", (101325.0, 288.15)),
                _station("1", (99000.0, 288.15), 12.0),
                _station("2", (792000.0, 600.0)),
                _station("3", (760000.0, 1450.0)),
                _station("4", (280000.0, 1050.0)),
                _station("5", (270000.0, 1040.0)),
            ],
            "rows": [
                _row(
                    "comp-rotor",
                    "compressor",
                    "work_adding",
                    "rotating",
                    "1",
                    "2",
                    "core-spool",
                    "axial",
                ),
                _row(
                    "turbine-rotor",
                    "turbine",
                    "work_extracting",
                    "rotating",
                    "3",
                    "4",
                    "core-spool",
                    "axial",
                ),
            ],
            "shafts": [
                {
                    "id": "core-spool",
                    "kind": "common",
                    "members": ["comp-rotor", "turbine-rotor"],
                    "speed": None,
                    "mechanicalLossFraction": 0.02,
                    "couplings": [
                        {
                            "id": "power-offtake",
                            "kind": "mechanical_load",
                            "targetNode": "load",
                            "efficiency": 0.98,
                        }
                    ],
                }
            ],
        }
    raise CalibrationInputError(f"UNKNOWN_REFERENCE_CASE:{case_id}")


def _component_params(case_id: str) -> tuple[tuple[str, ComponentParameters], ...]:
    if case_id == CASE_AXIAL_FAN:
        return (
            ("inlet", ComponentParameters(pressure_recovery=0.94)),
            ("fan", ComponentParameters(pressure_ratio=1.158, isentropic_efficiency=0.90)),
            ("nozzle", ComponentParameters(ambient_pressure_pa=101325.0)),
            ("motor", ComponentParameters(machine_efficiency=0.95)),
        )
    if case_id == CASE_AXIAL_SHAFT:
        return (
            ("inlet", ComponentParameters(pressure_recovery=0.977)),
            ("c1", ComponentParameters(pressure_ratio=1.9, isentropic_efficiency=0.87)),
            ("c2", ComponentParameters(pressure_ratio=1.9, isentropic_efficiency=0.87)),
            (
                "combustor",
                ComponentParameters(
                    exit_total_temperature_k=1350.0,
                    pressure_loss_fraction=0.04,
                    fuel_lower_heating_value_j_kg=43.0e6,
                    combustion_efficiency=0.99,
                ),
            ),
            ("t1", ComponentParameters(expansion_ratio=3.1, isentropic_efficiency=0.90)),
            ("load", ComponentParameters(electric_power_w=0.0)),
        )
    if case_id == CASE_RADIAL:
        return (
            ("inlet", ComponentParameters(pressure_recovery=0.97)),
            (
                "impeller",
                ComponentParameters(pressure_ratio=3.4, isentropic_efficiency=0.82),
            ),
            ("motor", ComponentParameters(machine_efficiency=0.93)),
        )
    return (
        ("inlet", ComponentParameters(pressure_recovery=0.977)),
        ("compressor", ComponentParameters(pressure_ratio=8.0, isentropic_efficiency=0.86)),
        (
            "combustor",
            ComponentParameters(
                exit_total_temperature_k=1450.0,
                pressure_loss_fraction=0.04,
                fuel_lower_heating_value_j_kg=43.0e6,
                combustion_efficiency=0.99,
            ),
        ),
        ("turbine", ComponentParameters(expansion_ratio=2.714, isentropic_efficiency=0.90)),
        ("nozzle", ComponentParameters(ambient_pressure_pa=101325.0)),
        ("load", ComponentParameters(electric_power_w=0.0)),
    )


def _case_flows(case_id: str) -> tuple[float, float, float]:
    if case_id == CASE_AXIAL_FAN:
        return (101325.0, 288.15, 4.5)
    if case_id == CASE_AXIAL_SHAFT:
        return (101325.0, 288.15, 6.0)
    if case_id == CASE_RADIAL:
        return (101325.0, 288.15, 0.8)
    return (101325.0, 288.15, 12.0)


def reference_cycle_design(case_id: str) -> CycleDesign:
    payload = reference_architecture_payload(case_id)
    architecture = architecture_from_payload(payload)
    ambient_p, ambient_t, mass_flow = _case_flows(case_id)
    gas = AIR if case_id in (CASE_AXIAL_FAN, CASE_RADIAL) else COMBUSTION_GAS
    return CycleDesign(
        architecture=architecture,
        component_parameters=_component_params(case_id),
        gas=gas,
        ambient_total_pressure_pa=ambient_p,
        ambient_total_temperature_k=ambient_t,
        mass_flow_kg_s=mass_flow,
    )


@dataclass(frozen=True, slots=True)
class BenchmarkExpectation:
    case_id: str
    architecture_hash: str
    converged: bool
    thrust_n: float
    thrust_tolerance_n: float
    fuel_flow_kg_s: float | None
    fuel_tolerance_kg_s: float | None


@dataclass(frozen=True, slots=True)
class ReferenceOutcome:
    case_id: str
    architecture_hash: str
    model_digest: str
    converged: bool
    thrust_n: float
    fuel_flow_kg_s: float
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
            "modelDigest": self.model_digest,
            "converged": self.converged,
            "thrustN": self.thrust_n,
            "fuelFlowKgS": self.fuel_flow_kg_s,
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


_OUTCOME_UNITS: tuple[tuple[str, str], ...] = (
    ("thrustN", "N"),
    ("fuelFlowKgS", "kg/s"),
)


def run_reference_case(case_id: str) -> ReferenceOutcome:
    if case_id not in REFERENCE_CASES:
        raise CalibrationInputError(f"UNKNOWN_REFERENCE_CASE:{case_id}")
    design = reference_cycle_design(case_id)
    model = compile_cycle_model(design)
    solved = solve_cycle(model)
    payload = {
        "caseId": case_id,
        "architectureHash": architecture_hash(design.architecture),
        "modelDigest": model.digest,
    }
    digest = content_digest(payload)
    checks = {
        "cycle-converged": solved.converged,
        "architecture-hashable": True,
        "screening-labelled": True,
    }
    return ReferenceOutcome(
        case_id=case_id,
        architecture_hash=architecture_hash(design.architecture),
        model_digest=model.digest,
        converged=solved.converged,
        thrust_n=float(solved.thrust_n),
        fuel_flow_kg_s=float(solved.fuel_flow_kg_s),
        source=ResultSource.ANALYTICAL.value,
        fidelity=CalibrationFidelity.ANALYTICAL_SCREENING.value,
        units=_OUTCOME_UNITS,
        validity=CalibrationValidity(
            passed=all(checks.values()),
            checks=checks,
            detail="" if all(checks.values()) else "cycle screening did not converge",
        ),
        input_hash=digest,
        software=CalibrationSoftware(),
        provenance=calibration_provenance(
            ResultSource.ANALYTICAL,
            CalibrationFidelity.ANALYTICAL_SCREENING,
            payload,
            (
                "Analytical screening only; explicitly not validated.",
                "Reference configuration is synthetic and non-product-specific.",
            ),
        ),
    )


@dataclass(frozen=True, slots=True)
class BenchmarkCheck:
    case_id: str
    passed: bool
    failures: tuple[str, ...]

    def canonical(self) -> dict[str, Any]:
        return {
            "caseId": self.case_id,
            "passed": self.passed,
            "failures": list(self.failures),
        }


def check_reference_case(
    outcome: ReferenceOutcome, expectation: BenchmarkExpectation
) -> BenchmarkCheck:
    if outcome.case_id != expectation.case_id:
        raise CalibrationInputError("BENCHMARK_CASE_MISMATCH")
    failures: list[str] = []
    if outcome.architecture_hash != expectation.architecture_hash:
        failures.append("architecture-hash")
    if outcome.converged != expectation.converged:
        failures.append("converged")
    if abs(outcome.thrust_n - expectation.thrust_n) > expectation.thrust_tolerance_n:
        failures.append("thrust-n")
    if (
        expectation.fuel_flow_kg_s is not None
        and expectation.fuel_tolerance_kg_s is not None
        and abs(outcome.fuel_flow_kg_s - expectation.fuel_flow_kg_s)
        > expectation.fuel_tolerance_kg_s
    ):
        failures.append("fuel-flow")
    return BenchmarkCheck(
        case_id=outcome.case_id, passed=not failures, failures=tuple(failures)
    )


def benchmark_matrix_digest(outcomes: Mapping[str, ReferenceOutcome]) -> str:
    return content_digest(
        {
            case_id: outcomes[case_id].result_hash
            for case_id in sorted(outcomes)
            if case_id in REFERENCE_CASES
        }
    )


__all__ = [
    "CASE_AXIAL_FAN",
    "CASE_AXIAL_SHAFT",
    "CASE_BRAYTON_CORE",
    "CASE_RADIAL",
    "REFERENCE_CASES",
    "BenchmarkCheck",
    "BenchmarkExpectation",
    "ReferenceOutcome",
    "benchmark_matrix_digest",
    "check_reference_case",
    "reference_architecture_payload",
    "reference_cycle_design",
    "run_reference_case",
]
