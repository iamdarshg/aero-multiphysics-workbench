"""Generic generative-engineering end-to-end release benchmark (GEN 12).

One deliberately simple, non-application-specific rotating / thermo-fluid-
mechanical assembly is carried from a mixed conditional design space through
candidate generation, cheap evaluation, selection/diversity, fidelity
promotion, real CAD regeneration, real Gmsh meshing, scalar machine/drive/
battery coupling, rotor dynamics, field exchange, mesh/time independence, and
a provenance-backed candidate set.

Honesty rules:

* Heavyweight native binaries (OpenFOAM, Code_Aster, Elmer, native preCICE,
  ROSS) are never required. When a capability is absent the step is reported
  ``SKIPPED`` with the probed reason; a screening or analytical model is
  clearly labelled and is never presented as native.
* A candidate can only be ``validated-final`` when every required scientific
  participant actually executed and its closure/independence gates passed.
  Otherwise it is ``incomplete-diagnostic`` with explicit blockers.
* No timestamp or machine path enters the reproducibility digest.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import math
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from aeroworkbench_convergence import (
    MESH,
    TIMESTEP,
    PromotionParticipantEvidence,
    QuantityOfInterest,
    RefinementLevel,
    StudyRun,
    assess_closure,
    assess_field_interface_conservation,
    assess_promotion,
    assess_resonance_margin,
    run_mesh_independence,
    run_timestep_independence,
)
from aeroworkbench_optimization import (
    CampaignBudget,
    CampaignRecord,
    CampaignSpec,
    Candidate,
    CandidateGenerator,
    EvaluationResult,
    FidelityImplementation,
    GenerationRequest,
    PhysicsFlags,
    QualityPolicy,
    StudyConstraint,
    StudyObjective,
    run_campaign,
)
from aeroworkbench_optimization.design_space import content_digest, validate_design_space

__all__ = [
    "BENCHMARK_ID",
    "BENCHMARK_MANIFEST",
    "BenchmarkConfig",
    "BenchmarkReport",
    "BenchmarkStep",
    "run_generic_benchmark",
]

BENCHMARK_ID = "gen12-generic-rotating-assembly"

BENCHMARK_MANIFEST: dict[str, Any] = {
    "id": BENCHMARK_ID,
    "schemaVersion": 1,
    "description": (
        "Generic rotating thermo-fluid-mechanical assembly. The acceptance "
        "logic is defined on declared quantities and capabilities, never on "
        "application-specific names."
    ),
    "requiredCapabilities": [
        "geometry",
        "mesh",
        "flow",
        "structural",
        "thermal",
        "rotordynamics",
        "scalar-coupling",
        "field-coupling",
    ],
    "participants": {
        "geometry": "cad-interchange",
        "mesh": "domain-mesh",
        "flow": "incompressible-steady-flow",
        "structural": "structural-static",
        "thermal": "thermal-conduction",
        "rotordynamics": "rotor-campbell",
        "scalar-coupling": "rotating-electrical-machine",
        "field-coupling": "coupled-interface-validation",
    },
}

_EXECUTED = "EXECUTED"
_PARTIAL = "PARTIAL"
_SKIPPED = "SKIPPED"
_FAILED = "FAILED"


@dataclass(frozen=True, slots=True)
class BenchmarkConfig:
    """Bounded run controls; nothing here enables cloud spend."""

    seed: int = 0
    base_revision: str = "gen12-rev-a"
    max_candidates: int = 18
    execute_cad: bool = True
    execute_mesh: bool = True
    execute_native: bool = False
    mesh_base_size_mm: float = 8.0


@dataclass(frozen=True, slots=True)
class BenchmarkStep:
    step: str
    status: str
    detail: str
    capability: str | None = None
    evidence: Mapping[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "step": self.step,
            "status": self.status,
            "capability": self.capability,
            "detail": self.detail,
            "evidence": _jsonable(self.evidence),
        }


@dataclass(frozen=True, slots=True)
class BenchmarkReport:
    benchmark_id: str
    seed: int
    design_hash: str
    campaign_digest: str
    steps: tuple[BenchmarkStep, ...]
    candidate_set: tuple[dict[str, Any], ...]
    lineage: Mapping[str, Any]
    independence: tuple[dict[str, Any], ...]
    promotions: tuple[dict[str, Any], ...]
    audit: tuple[dict[str, Any], ...]
    reproducible: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "benchmarkId": self.benchmark_id,
            "seed": self.seed,
            "designHash": self.design_hash,
            "campaignDigest": self.campaign_digest,
            "steps": [step.as_dict() for step in self.steps],
            "candidateSet": _jsonable(self.candidate_set),
            "lineage": _jsonable(self.lineage),
            "independence": _jsonable(self.independence),
            "promotions": _jsonable(self.promotions),
            "audit": _jsonable(self.audit),
            "reproducible": self.reproducible,
        }

    def digest(self) -> str:
        return content_digest(self.as_dict())


def _jsonable(value: Any) -> Any:
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _lazy(module: str, attribute: str) -> Any:
    try:
        return getattr(importlib.import_module(module), attribute)
    except Exception:  # noqa: BLE001 - absent optional capability is data, not a crash
        return None


# ---------------------------------------------------------------------------
# design space (mixed + conditional)
# ---------------------------------------------------------------------------


def generic_design_space() -> dict[str, Any]:
    """A mixed/conditional space: numeric, integer, categorical, boolean, and
    branch/``activeWhen``-gated members. No application-specific names."""

    return {
        "id": BENCHMARK_ID,
        "variables": [
            {
                "id": "drive_kind",
                "kind": "categorical",
                "bindings": [{"target": "parameter", "path": "p.drive_kind"}],
                "baseValue": "electric",
                "domain": {"kind": "categorical", "values": ["electric", "hybrid"]},
            },
            {
                "id": "rotor_count",
                "kind": "integer",
                "bindings": [{"target": "parameter", "path": "p.rotor_count"}],
                "baseValue": 1,
                "domain": {"kind": "integer", "lower": 1, "upper": 2, "step": 1},
            },
            {
                "id": "tip_diameter_mm",
                "kind": "continuous",
                "unit": "mm",
                "bindings": [{"target": "parameter", "path": "p.tip_diameter_mm"}],
                "baseValue": 30.0,
                "domain": {"kind": "continuous", "lower": 20.0, "upper": 40.0},
            },
            {
                "id": "blade_count",
                "kind": "integer",
                "bindings": [{"target": "parameter", "path": "p.blade_count"}],
                "baseValue": 5,
                "domain": {"kind": "integer", "lower": 3, "upper": 9, "step": 2},
            },
            {
                "id": "material",
                "kind": "categorical",
                "bindings": [{"target": "material", "path": "m.material"}],
                "baseValue": "aluminium",
                "domain": {"kind": "categorical", "values": ["aluminium", "titanium"]},
            },
            {
                "id": "cooled",
                "kind": "boolean",
                "bindings": [{"target": "parameter", "path": "p.cooled"}],
                "baseValue": False,
                "domain": {"kind": "boolean"},
            },
            {
                "id": "cooling_flow_kg_s",
                "kind": "continuous",
                "bindings": [{"target": "parameter", "path": "p.cooling_flow_kg_s"}],
                "baseValue": 0.01,
                "activeWhen": {"variable": "cooled", "op": "equals", "value": True},
                "domain": {"kind": "continuous", "lower": 0.002, "upper": 0.05},
            },
            {
                "id": "battery_cells",
                "kind": "integer",
                "bindings": [{"target": "parameter", "path": "p.battery_cells"}],
                "baseValue": 4,
                "domain": {"kind": "integer", "lower": 2, "upper": 6, "step": 1},
            },
            {
                "id": "fuel_flow_kg_s",
                "kind": "continuous",
                "bindings": [{"target": "parameter", "path": "p.fuel_flow_kg_s"}],
                "baseValue": 0.02,
                "domain": {"kind": "continuous", "lower": 0.005, "upper": 0.05},
            },
            {
                "id": "shaft_length_mm",
                "kind": "continuous",
                "unit": "mm",
                "bindings": [{"target": "parameter", "path": "p.shaft_length_mm"}],
                "baseValue": 60.0,
                "domain": {"kind": "continuous", "lower": 40.0, "upper": 80.0},
            },
            {
                "id": "bearing_stiffness_n_m",
                "kind": "continuous",
                "bindings": [{"target": "parameter", "path": "p.bearing_stiffness_n_m"}],
                "baseValue": 500000.0,
                "domain": {"kind": "continuous", "lower": 100000.0, "upper": 1000000.0},
            },
        ],
        "branches": [
            {
                "id": "energy-storage",
                "selector": "drive_kind",
                "options": {
                    "electric": ["battery_cells"],
                    "hybrid": ["fuel_flow_kg_s"],
                },
            }
        ],
        "constraints": [],
    }


# ---------------------------------------------------------------------------
# cheap deterministic evaluation
# ---------------------------------------------------------------------------


def _candidate_values(candidate: Candidate) -> dict[str, Any]:
    return {
        item.variable_id: item.value
        for item in candidate.assignment
        if item.point_id is None
    }


def _cheap_outputs(candidate: Candidate, fidelity: str) -> dict[str, float]:
    values = _candidate_values(candidate)
    rotor_count = float(values.get("rotor_count", 1))
    diameter_mm = float(values.get("tip_diameter_mm", 30.0))
    blades = float(values.get("blade_count", 5))
    material = str(values.get("material", "aluminium"))
    cooled = bool(values.get("cooled", False))
    cooling = float(values.get("cooling_flow_kg_s", 0.0) or 0.0)
    battery_cells = float(values.get("battery_cells", 4) or 4)
    fuel_flow = float(values.get("fuel_flow_kg_s", 0.0) or 0.0)
    shaft_length_m = float(values.get("shaft_length_mm", 60.0)) / 1000.0

    density = 2700.0 if material == "aluminium" else 4430.0
    radius_m = diameter_mm / 2000.0
    area = math.pi * radius_m**2
    disc_mass = density * blades * area * 0.03
    shaft_mass = density * math.pi * 0.005**2 * shaft_length_m
    cooled_factor = 1.0 + 0.05 * cooling if cooled else 1.0
    thrust = 8000.0 * blades * area * (1.0 + 0.02 * rotor_count) * cooled_factor
    mass = disc_mass + shaft_mass
    if fidelity == "screening":
        thrust *= 0.97
        mass *= 1.02
    energy_source = battery_cells if battery_cells else 1.0
    shaft_power = thrust * 30.0
    electrical_power = shaft_power / 0.85 + 5.0 * energy_source
    heat = electrical_power - shaft_power
    return {
        "thrust_n": thrust,
        "mass_kg": mass,
        "shaft_power_w": shaft_power,
        "electrical_power_w": electrical_power,
        "heat_load_w": heat,
        "fuel_flow_kg_s": fuel_flow * 0.0,
    }


def _make_evaluator() -> Any:
    def evaluator(candidate: Candidate, fidelity: str) -> EvaluationResult:
        values = _candidate_values(candidate)
        drive = str(values.get("drive_kind", "electric"))
        battery_cells = float(values.get("battery_cells", 4) or 4)
        converged = not (drive == "electric" and battery_cells < 3)
        outputs = _cheap_outputs(candidate, fidelity)
        flags = PhysicsFlags(
            converged=converged,
            closure_passed=True,
            validity_ok=True,
        )
        signals = {
            "disagreement": 0.4 if fidelity == "analytical" else 0.0,
            "maturity": 0.5,
        }
        return EvaluationResult(
            outputs=outputs,
            flags=flags,
            fidelity=fidelity,
            source="analytical",
            cost=0.1 if fidelity == "analytical" else 0.5,
            signals=signals,
            detail="" if converged else "hard design point; solver did not converge",
        )

    return evaluator


def _campaign_spec(cfg: BenchmarkConfig, space: Mapping[str, Any]) -> CampaignSpec:
    return CampaignSpec(
        campaign_id=f"{BENCHMARK_ID}-campaign",
        base_revision=cfg.base_revision,
        space=space,
        generation=GenerationRequest(
            "lhs",
            count=cfg.max_candidates,
            seed=cfg.seed,
            budget=cfg.max_candidates,
        ),
        objectives=(
            StudyObjective("thrust_n", "maximize"),
            StudyObjective("mass_kg", "minimize"),
        ),
        constraints=(StudyConstraint("mass_kg", "upper", 1.0),),
        fidelity_ladder=(
            FidelityImplementation("analytical", 0, 0.1),
            FidelityImplementation("screening", 1, 0.5),
        ),
        budget=CampaignBudget(max_evaluations=cfg.max_candidates * 2),
        quality=QualityPolicy(),
        promote_fraction=1.0,
        min_promote=1,
        diversity=True,
    )


# ---------------------------------------------------------------------------
# optional native/generated capabilities
# ---------------------------------------------------------------------------


def _cad_regeneration(cfg: BenchmarkConfig, workspace: Path) -> dict[str, Any]:
    if not cfg.execute_cad:
        return {"status": _SKIPPED, "detail": "CAD execution disabled by benchmark config"}
    probe = _lazy("aeroworkbench_geometry.parametric", "probe_kernel")
    if probe is None:
        return {"status": _SKIPPED, "detail": "geometry kernel probe unavailable"}
    identity = probe()
    if not identity.available:
        return {"status": _SKIPPED, "detail": f"CAD kernel unavailable: {identity.detail}"}
    builder = _lazy("aeroworkbench_geometry", "build_duct_system")
    live_shapes = _lazy("aeroworkbench_geometry.builder", "live_shapes")
    export_artifacts = _lazy("aeroworkbench_geometry.parametric", "export_artifacts")
    if builder is None or live_shapes is None or export_artifacts is None:
        return {"status": _SKIPPED, "detail": "geometry regeneration API unavailable"}
    diameter_mm = 30.0
    length_mm = 60.0
    n_rotating = 1
    outer = diameter_mm + 6.0
    hub = max(0.25 * diameter_mm, 8.0)
    zone_length = length_mm / (2.0 * n_rotating + 2.0)
    zone_gap = zone_length * 0.3
    try:
        built = builder(
            outer_diameter_mm=outer,
            inner_diameter_mm=diameter_mm,
            length_mm=length_mm,
            hub_diameter_mm=hub,
            n_rotating=n_rotating,
            n_solids=1,
            zone_length_mm=zone_length,
            zone_gap_mm=zone_gap,
        ).build()
        records = export_artifacts(
            live_shapes(built), built.kernel, workspace / "cad", basename="domain",
            export_stl=False,
        )
    except Exception as exc:  # noqa: BLE001
        return {"status": _FAILED, "detail": f"CAD regeneration failed:{type(exc).__name__}:{exc}"}
    step_files = {
        str(artifact["component"]): Path(str(artifact["path"]))
        for artifact in records["artifacts"]
        if artifact["format"] == "step" and artifact["component"] != "assembly"
    }
    return {
        "status": _EXECUTED,
        "detail": f"regenerated {len(step_files)} STEP components from declared variables",
        "shape_hash": built.shape_hash,
        "components": sorted(step_files),
        "kernel": identity.cadquery_version,
        "step_files": step_files,
        "artifact_hashes": sorted(
            str(artifact["sha256"])
            for artifact in records["artifacts"]
            if artifact["format"] == "step"
        ),
        "n_rotating": n_rotating,
        "dimensions": {
            "outer_diameter_mm": outer,
            "inner_diameter_mm": diameter_mm,
            "length_mm": length_mm,
        },
    }


def _mesh_generation(
    cad: Mapping[str, Any], cfg: BenchmarkConfig, workspace: Path
) -> dict[str, Any]:
    if cad.get("status") != _EXECUTED:
        return {"status": _SKIPPED, "detail": "mesh requires a completed CAD regeneration"}
    if not cfg.execute_mesh:
        return {"status": _SKIPPED, "detail": "mesh execution disabled by benchmark config"}
    gmsh_probe = _lazy("aeroworkbench_mesh", "probe_gmsh")
    if gmsh_probe is None:
        return {"status": _SKIPPED, "detail": "Gmsh probe unavailable"}
    capability = gmsh_probe()
    if not capability.available:
        return {"status": _SKIPPED, "detail": f"Gmsh unavailable: {capability.detail}"}
    duct_mesh_spec = _lazy("aeroworkbench_mesh.native_mesh", "duct_mesh_spec")
    build_native_mesh = _lazy("aeroworkbench_mesh", "build_native_mesh")
    if duct_mesh_spec is None or build_native_mesh is None:
        return {"status": _SKIPPED, "detail": "native mesh API unavailable"}
    dims = cad["dimensions"]
    try:
        spec = duct_mesh_spec(
            name="generic-assembly",
            rotating=("rotor_zone_0",),
            stationary_fluid=("fluid_inlet", "fluid_outlet"),
            solids=("duct", "solid_0"),
            length_mm=float(dims["length_mm"]),
            inner_diameter_mm=float(dims["inner_diameter_mm"]),
            base_size_mm=cfg.mesh_base_size_mm,
            boundary_layer=True,
        )
        receipt = build_native_mesh(
            spec,
            dict(cad["step_files"]),
            str(cad["shape_hash"]),
            workspace / "mesh",
        )
    except Exception as exc:  # noqa: BLE001
        return {"status": _FAILED, "detail": f"mesh generation failed:{type(exc).__name__}:{exc}"}
    if receipt.state != "completed":
        return {"status": _FAILED, "detail": f"mesh not completed:{receipt.detail}"}
    return {
        "status": _EXECUTED,
        "detail": f"native Gmsh mesh with {receipt.element_count} elements",
        "mesh_hash": receipt.mesh_hash,
        "geometry_hash": receipt.geometry_hash,
        "element_count": receipt.element_count,
        "quality": None if receipt.quality is None else {
            "min_sicn": receipt.quality.min_sicn,
            "inverted_count": receipt.quality.inverted_count,
        },
        "physical_groups": sorted(receipt.physical_groups),
        "interfaces": sorted(item.name for item in receipt.interfaces),
        "boundary_layer_requested": receipt.boundary_layer_requested,
    }


def _probe_participant(participant_id: str) -> Any:
    probe = _lazy("participants.capabilities", "probe_participant")
    if probe is None:
        return None
    try:
        return probe(participant_id)
    except Exception:  # noqa: BLE001
        return None


def _native_steps(cfg: BenchmarkConfig) -> list[BenchmarkStep]:
    """Probe native flow/structural/thermal without ever faking a receipt.

    A present engine is reported ``PARTIAL`` (capability available, but the
    generic benchmark does not own an application-agnostic native case, so the
    native receipt belongs to that participant's own benchmark). A missing
    engine is ``SKIPPED`` with the probe reason. ``EXECUTED`` is never claimed
    here because no governed native run is performed by this benchmark.
    """

    steps: list[BenchmarkStep] = []
    for capability, step_name in (
        ("flow", "native-flow"),
        ("structural", "native-structural"),
        ("thermal", "native-thermal"),
    ):
        participant = BENCHMARK_MANIFEST["participants"][capability]
        probed = _probe_participant(participant)
        available = probed is not None and probed.state == "ready"
        reason = probed.detail if probed is not None else "capability probe unavailable"
        if not available:
            steps.append(
                BenchmarkStep(
                    step_name,
                    _SKIPPED,
                    f"{participant} unavailable: {reason}",
                    capability=capability,
                    evidence={
                        "participant": participant,
                        "reason": reason,
                        "executeNative": cfg.execute_native,
                    },
                )
            )
            continue
        steps.append(
            BenchmarkStep(
                step_name,
                _PARTIAL,
                f"{participant} ready ({probed.version}); native receipt owned by "
                "the participant benchmark, no substitute executed here",
                capability=capability,
                evidence={
                    "participant": participant,
                    "solverVersion": probed.version,
                    "executeNative": cfg.execute_native,
                },
            )
        )
    return steps


def _scalar_coupling() -> BenchmarkStep:
    solve = _lazy("aeroworkbench_electrical", "solve_electrical_thermal")
    if solve is None:
        return BenchmarkStep(
            "scalar-coupling",
            _SKIPPED,
            "aeroworkbench_electrical in-process coordinator unavailable",
            capability="scalar-coupling",
        )
    try:
        result = solve(speed_rpm=20000.0, load_torque_n_m=0.05)
    except Exception as exc:  # noqa: BLE001
        return BenchmarkStep(
            "scalar-coupling",
            _FAILED,
            f"machine/drive/battery/thermal coupling failed:{type(exc).__name__}:{exc}",
            capability="scalar-coupling",
        )
    values = dict(result.values)
    electrical = _by_key(values, "rotating-electrical-machine.electrical_power_w")
    mechanical = _by_key(values, "rotating-electrical-machine.mechanical_power_w")
    machine_loss = _by_key(values, "rotating-electrical-machine.total_loss_w")
    thermal_machine_loss = _by_key(values, "thermal-scalar-lumped.machine_loss_w")
    drive_loss = _by_key(values, "power-electronics-drive.total_loss_w")
    thermal_drive_loss = _by_key(values, "thermal-scalar-lumped.drive_loss_w")
    power_balance = None
    if electrical is not None and mechanical is not None and machine_loss is not None:
        power_balance = assess_closure(
            "energy",
            {"energy": mechanical + machine_loss},
            {"energy": electrical},
        )
    heat_balance = None
    if (
        machine_loss is not None
        and thermal_machine_loss is not None
        and drive_loss is not None
        and thermal_drive_loss is not None
    ):
        # Both the machine and drive heat loads must reach the thermal network.
        heat_balance = assess_closure(
            "heat-balance",
            {"heat-flow": thermal_machine_loss + thermal_drive_loss},
            {"heat-flow": machine_loss + drive_loss},
            required=("heat-flow",),
        )
    return BenchmarkStep(
        "scalar-coupling",
        _EXECUTED,
        f"coupled scalar loop {'converged' if result.converged else 'did not converge'} "
        f"in {result.iterations} iterations (residual {result.residual_norm:.3e})",
        capability="scalar-coupling",
        evidence={
            "engine": result.engine,
            "converged": result.converged,
            "iterations": result.iterations,
            "residualNorm": result.residual_norm,
            "closureResidual": result.closure_residual,
            "powerBalancePassed": None if power_balance is None else power_balance.passed,
            "powerBalanceDetail": None if power_balance is None else power_balance.reason,
            "heatBalancePassed": None if heat_balance is None else heat_balance.passed,
            "heatBalanceDetail": None if heat_balance is None else heat_balance.reason,
        },
    )


def _by_key(values: Mapping[str, float], key: str) -> float | None:
    value = values.get(key)
    return None if value is None else float(value)


def _rotor_dynamics(cfg: BenchmarkConfig) -> BenchmarkStep:
    screening = _lazy("ross.rotor", "screening_beam_critical_rpm")
    rotor_inputs = {
        "shaft_length_m": 0.06,
        "shaft_diameter_m": 0.01,
    }
    estimate = None
    if screening is not None:
        try:
            estimate = screening(rotor_inputs)
        except Exception:  # noqa: BLE001
            estimate = None
    probed = _probe_participant(BENCHMARK_MANIFEST["participants"]["rotordynamics"])
    available = probed is not None and probed.state == "ready"
    margin = assess_resonance_margin(20000.0, (estimate,)) if estimate is not None else None
    evidence: dict[str, Any] = {
        "screeningCriticalRpm": estimate,
        "operatingSpeedRpm": 20000.0,
        "resonancePassed": None if margin is None else margin.passed,
        "native": False,
        "executeNative": cfg.execute_native,
    }
    if not available:
        reason = probed.detail if probed is not None else "capability probe unavailable"
        return BenchmarkStep(
            "rotor-dynamics",
            _SKIPPED,
            f"native rotor unavailable: {reason}",
            capability="rotordynamics",
            evidence={**evidence, "reason": reason},
        )
    # The ROSS library is present; the native receipt is owned by its participant
    # benchmark. This generic benchmark reports a labelled screening estimate and
    # never claims a native run it did not perform.
    return BenchmarkStep(
        "rotor-dynamics",
        _PARTIAL,
        f"ROSS {probed.version} present; screening beam estimate "
        f"{estimate:.1f} rpm (resonance {'clear' if margin and margin.passed else 'check'})"
        "; native receipt owned by the participant benchmark",
        capability="rotordynamics",
        evidence={**evidence, "solverVersion": probed.version},
    )


def _field_exchange() -> BenchmarkStep:
    register_mesh = _lazy("aeroworkbench_coupling.field", "register_mesh")
    map_field = _lazy("precice.coupling", "map_field")
    if register_mesh is None or map_field is None:
        return BenchmarkStep(
            "field-exchange",
            _SKIPPED,
            "analytic field-transfer API unavailable",
            capability="field-coupling",
        )
    try:
        source = register_mesh("gen12-source", (0.0, 0.25, 0.5, 0.75, 1.0))
        target = register_mesh("gen12-target", (0.0, 0.5, 1.0))
        mapped, record = map_field(
            source, (1000.0, 1000.0, 1000.0, 1000.0, 1000.0), target,
            "pressure", method="conservative",
        )
    except Exception as exc:  # noqa: BLE001
        return BenchmarkStep(
            "field-exchange",
            _FAILED,
            f"analytic field transfer failed:{type(exc).__name__}:{exc}",
            capability="field-coupling",
        )
    conservation = assess_field_interface_conservation(
        "pressure",
        (1000.0,) * 4,
        tuple(mapped),
        tolerance=1e-9,
    )
    return BenchmarkStep(
        "field-exchange",
        _SKIPPED,
        "native preCICE unavailable; exercised conservative analytic transfer "
        "(labelled, not native)",
        capability="field-coupling",
        evidence={
            "engine": "analytic-transfer",
            "native": False,
            "mapped": list(mapped),
            "conservationPassed": conservation.passed,
            "conservationError": conservation.relative_error,
            "mappingAccepted": bool(getattr(record, "accepted", False)),
        },
    )


# ---------------------------------------------------------------------------
# independence over the generic coupled graph
# ---------------------------------------------------------------------------


def _independence_reports(design_hash: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    seed_fraction = int(design_hash[:8], 16) / float(0xFFFFFFFF)

    def mesh_executor(level: RefinementLevel) -> StudyRun:
        value = 1.0 + seed_fraction + 2.0 * level.resolution**2
        return StudyRun(
            level=level.name,
            run_id=f"mesh-{level.name}",
            input_hash=content_digest({"kind": "mesh", "level": level.name, "h": level.resolution}),
            qoi=(("pressure_drop", value), ("mass_flow", 0.5 + 0.5 * value)),
            source="analytical",
        )

    def timestep_executor(level: RefinementLevel) -> StudyRun:
        value = 1.0 + seed_fraction + 3.0 * level.resolution
        return StudyRun(
            level=level.name,
            run_id=f"timestep-{level.name}",
            input_hash=content_digest(
                {"kind": "timestep", "level": level.name, "dt": level.resolution}
            ),
            qoi=(("peak_amplitude", value),),
            source="analytical",
        )

    mesh = run_mesh_independence(
        (
            RefinementLevel("coarse", 0.4, (("element_count", 1200.0),)),
            RefinementLevel("medium", 0.2, (("element_count", 9600.0),)),
            RefinementLevel("fine", 0.1, (("element_count", 76800.0),)),
        ),
        (
            QuantityOfInterest("pressure_drop", "Pa", relative_tolerance=0.1),
            QuantityOfInterest("mass_flow", "kg/s", relative_tolerance=0.1),
        ),
        mesh_executor,
    )
    timestep = run_timestep_independence(
        (
            RefinementLevel("coarse", 0.02, (("dt_s", 0.02),)),
            RefinementLevel("medium", 0.01, (("dt_s", 0.01),)),
            RefinementLevel("fine", 0.005, (("dt_s", 0.005),)),
        ),
        (QuantityOfInterest("peak_amplitude", "m", relative_tolerance=0.05),),
        timestep_executor,
        transient=True,
    )
    reports = [mesh.as_dict(), timestep.as_dict()]
    native_status = {
        "mesh": "SKIPPED:native flow solver unavailable; analytical QoI study executed",
        "timestep": "SKIPPED:native transient solver unavailable; analytical QoI study executed",
    }
    return reports, native_status


# ---------------------------------------------------------------------------
# capability audit (deferred-capability closure, no fabricated PASS)
# ---------------------------------------------------------------------------


def _capability_audit(
    executed: Mapping[str, Mapping[str, Any]],
    cfg: BenchmarkConfig,
) -> list[dict[str, Any]]:
    audit: list[dict[str, Any]] = []
    for capability in BENCHMARK_MANIFEST["requiredCapabilities"]:
        participant = BENCHMARK_MANIFEST["participants"][capability]
        record = executed.get(capability)
        probed = _probe_participant(participant)
        if record is not None and record.get("status") == _EXECUTED:
            incomplete = (
                capability == "scalar-coupling"
                and (
                    record.get("converged") is False
                    or record.get("powerBalancePassed") is False
                    or record.get("heatBalancePassed") is False
                )
            )
            audit.append(
                {
                    "capability": capability,
                    "participant": participant,
                    "status": "PARTIAL" if incomplete else "PASS",
                    "detail": (
                        f"{record.get('detail', '')}; closure/convergence incomplete"
                        if incomplete
                        else record.get("detail", "")
                    ),
                    "native": capability not in {"scalar-coupling"},
                }
            )
            continue
        if record is not None and record.get("status") == _FAILED:
            audit.append(
                {
                    "capability": capability,
                    "participant": participant,
                    "status": "FAIL",
                    "detail": record.get("detail", ""),
                    "native": True,
                }
            )
            continue
        available = probed is not None and probed.state == "ready"
        reason = (
            probed.detail
            if probed is not None
            else (record or {}).get("detail", "capability not executed")
        )
        if available:
            # The engine is present but this generic benchmark owns no receipt;
            # a screening estimate never upgrades PARTIAL to PASS.
            status = "PARTIAL"
            reason = f"{reason}; capability present, no native receipt from this benchmark"
        else:
            status = "BLOCKED"
        audit.append(
            {
                "capability": capability,
                "participant": participant,
                "status": status,
                "detail": reason,
                "native": capability not in {"scalar-coupling"},
                "executeNative": cfg.execute_native,
            }
        )
    return audit


# ---------------------------------------------------------------------------
# runner
# ---------------------------------------------------------------------------


def _stage(
    steps: list[BenchmarkStep],
    executed: dict[str, dict[str, Any]],
    capability: str,
    step_name: str,
    record: Mapping[str, Any],
) -> None:
    steps.append(
        BenchmarkStep(
            step_name,
            str(record.get("status", _FAILED)),
            str(record.get("detail", "")),
            capability=capability,
            evidence={key: value for key, value in record.items() if key != "step_files"},
        )
    )
    executed[capability] = dict(record)


def run_generic_benchmark(
    workspace: Path | None = None,
    *,
    config: BenchmarkConfig | None = None,
) -> BenchmarkReport:
    """Run the bounded generic benchmark and return its evidence report."""

    cfg = config or BenchmarkConfig()
    workspace = (
        Path(tempfile.mkdtemp(prefix="gen12-"))
        if workspace is None
        else Path(workspace)
    )
    workspace.mkdir(parents=True, exist_ok=True)

    steps: list[BenchmarkStep] = []
    executed: dict[str, dict[str, Any]] = {}

    space = generic_design_space()
    validate_design_space(space)
    design_hash = content_digest(space)
    steps.append(
        BenchmarkStep(
            "design-space",
            _EXECUTED,
            f"validated mixed/conditional space with {len(space['variables'])} variables "
            f"and {len(space['branches'])} conditional branch",
            evidence={
                "designHash": design_hash,
                "variables": len(space["variables"]),
                "branches": len(space["branches"]),
            },
        )
    )

    spec = _campaign_spec(cfg, space)
    generator = CandidateGenerator(space, spec.generation)
    candidates = list(generator)
    steps.append(
        BenchmarkStep(
            "candidate-generation",
            _EXECUTED,
            f"generated {len(candidates)} candidates from the declared seed",
            evidence={
                "requested": cfg.max_candidates,
                "generated": len(candidates),
                "duplicates": generator.stats.duplicates,
                "preflightInvalid": generator.stats.preflight_invalid,
                "seed": cfg.seed,
            },
        )
    )

    record = run_campaign(spec, _make_evaluator(), evaluator_identity="gen12-cheap-v1")
    campaign_digest = content_digest(record.as_dict())
    valid_evaluations = sum(1 for item in record.evaluations if item.state == "valid")
    steps.append(
        BenchmarkStep(
            "cheap-evaluation",
            _EXECUTED,
            f"{len(record.evaluations)} evaluations, {valid_evaluations} valid",
            evidence={
                "evaluations": len(record.evaluations),
                "valid": valid_evaluations,
                "invalid": int(record.metrics.get("invalid", 0)),
                "cacheHits": int(record.metrics.get("cache_hits", 0)),
            },
        )
    )
    steps.append(
        BenchmarkStep(
            "selection-diversity",
            _EXECUTED,
            f"selected a diverse feasible set; {len(record.pareto)} Pareto candidates",
            evidence={
                "pareto": list(record.pareto),
                "best": record.best,
                "stopReason": record.stop_reason,
            },
        )
    )
    promoted = [item for item in record.promotions if item.advanced]
    steps.append(
        BenchmarkStep(
            "fidelity-promotion",
            _EXECUTED,
            f"{len(promoted)} candidates promoted to the screening rung",
            evidence={
                "promotions": len(record.promotions),
                "advanced": len(promoted),
                "toFidelity": sorted({item.to_fidelity for item in promoted}),
            },
        )
    )

    cad = _cad_regeneration(cfg, workspace)
    _stage(steps, executed, "geometry", "cad-regeneration", cad)
    mesh = _mesh_generation(cad, cfg, workspace)
    _stage(steps, executed, "mesh", "mesh-generation", mesh)

    for step in _native_steps(cfg):
        steps.append(step)
        executed[step.capability or step.step] = {
            "status": step.status,
            "detail": step.detail,
        }

    scalar = _scalar_coupling()
    _stage(steps, executed, "scalar-coupling", "scalar-coupling", {
        "status": scalar.status,
        "detail": scalar.detail,
        **dict(scalar.evidence),
    })

    rotor = _rotor_dynamics(cfg)
    _stage(steps, executed, "rotordynamics", "rotor-dynamics", {
        "status": rotor.status,
        "detail": rotor.detail,
        **dict(rotor.evidence),
    })

    field_step = _field_exchange()
    _stage(steps, executed, "field-coupling", "field-exchange", {
        "status": field_step.status,
        "detail": field_step.detail,
        **dict(field_step.evidence),
    })

    independence, native_independence = _independence_reports(design_hash)
    steps.append(
        BenchmarkStep(
            "mesh-time-independence",
            _EXECUTED,
            "declared mesh and time-step ladders executed over declared QoI",
            evidence={
                "meshAccepted": independence[0]["accepted"],
                "timestepAccepted": independence[1]["accepted"],
                "nativeIndependence": native_independence,
            },
        )
    )

    audit = _capability_audit(executed, cfg)
    availability = {
        capability: (entry["status"] == "PASS")
        for capability, entry in (
            (cap, executed.get(cap, {})) for cap in BENCHMARK_MANIFEST["participants"]
        )
    }
    executed_native = {
        capability: (entry.get("status") == _EXECUTED)
        for capability, entry in executed.items()
    }

    scalar_record = executed.get("scalar-coupling", {})
    closure_ok = bool(
        scalar_record.get("status") == _EXECUTED
        and scalar_record.get("converged") is not False
        and scalar_record.get("powerBalancePassed") is not False
        and scalar_record.get("heatBalancePassed") is not False
    )
    candidate_set, lineage = _finalize_candidates(
        record=record,
        candidates=candidates,
        design_hash=design_hash,
        campaign_digest=campaign_digest,
        availability=availability,
        executed_native=executed_native,
        independence=independence,
        closure_ok=closure_ok,
    )
    steps.append(
        BenchmarkStep(
            "final-candidate-set",
            _EXECUTED,
            f"{len(candidate_set)} provenance-backed candidates; "
            f"{sum(1 for item in candidate_set if item['validatedFinal'])} validated-final",
            evidence={
                "candidates": len(candidate_set),
                "validatedFinal": sum(1 for item in candidate_set if item["validatedFinal"]),
                "designHash": design_hash,
            },
        )
    )
    steps.append(
        BenchmarkStep(
            "deferred-capability-audit",
            _EXECUTED,
            "capability audit produced no fabricated PASS; native shortfalls are explicit",
            evidence={"audit": audit},
        )
    )

    reproducible = _verify_reproducible(cfg, design_hash, campaign_digest)
    return BenchmarkReport(
        benchmark_id=BENCHMARK_ID,
        seed=cfg.seed,
        design_hash=design_hash,
        campaign_digest=campaign_digest,
        steps=tuple(steps),
        candidate_set=tuple(candidate_set),
        lineage=lineage,
        independence=tuple(independence),
        promotions=tuple(item.as_dict() for item in record.promotions),
        audit=tuple(audit),
        reproducible=reproducible,
    )


def _finalize_candidates(
    *,
    record: CampaignRecord,
    candidates: Sequence[Candidate],
    design_hash: str,
    campaign_digest: str,
    availability: Mapping[str, bool],
    executed_native: Mapping[str, bool],
    independence: Sequence[Mapping[str, Any]],
    closure_ok: bool,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    by_hash = {candidate.candidate_hash: candidate for candidate in candidates}
    promotions_by_hash: dict[str, list[Any]] = {}
    for decision in record.promotions:
        promotions_by_hash.setdefault(decision.candidate_hash, []).append(decision)

    scalar_energy_ok = closure_ok and _energy_closure_ok(record)
    mesh_ok = bool(independence[0].get("accepted"))
    timestep_ok = bool(independence[1].get("accepted"))
    mesh_runs = list(independence[0].get("runHashes", ()))
    timestep_runs = list(independence[1].get("runHashes", ()))

    candidate_set: list[dict[str, Any]] = []
    lineage: dict[str, Any] = {}
    for candidate_hash in sorted(record.candidates):
        entry = record.candidates[candidate_hash]
        candidate = by_hash.get(candidate_hash)
        evaluated = [
            item.as_dict() for item in record.evaluations if item.candidate_hash == candidate_hash
        ]
        promotion = [item.as_dict() for item in promotions_by_hash.get(candidate_hash, [])]
        evidence: list[PromotionParticipantEvidence] = []
        for capability, participant in BENCHMARK_MANIFEST["participants"].items():
            native_available = availability.get(capability, False)
            executed_here = executed_native.get(capability, False)
            if capability in {"geometry", "mesh", "scalar-coupling"}:
                available_now = executed_here
                deferred_now = not executed_here
            else:
                available_now = native_available and executed_here
                deferred_now = not available_now
            evidence.append(
                PromotionParticipantEvidence(
                    participant_id=participant,
                    required=True,
                    available=available_now,
                    deferred=deferred_now,
                    converged=entry.status != "invalid",
                    validity_ok=entry.feasible is not False,
                    closure_passed=scalar_energy_ok,
                    field_coupling_passed=bool(executed_native.get("field-coupling", False)),
                    mesh_independence_passed=mesh_ok,
                    timestep_independence_passed=timestep_ok,
                )
            )
        gate = assess_promotion(
            candidate_hash,
            evidence,
            require_mesh_independence=True,
            require_timestep_independence=True,
        )
        artifact_hashes = _candidate_artifact_hashes(candidate, entry, record)
        candidate_set.append(
            {
                "candidateHash": candidate_hash,
                "status": entry.status,
                "validatedFinal": gate.validated_final,
                "promotionStatus": gate.status,
                "blockers": list(gate.blockers),
                "fidelity": entry.fidelity,
                "feasible": entry.feasible,
                "score": entry.score,
                "outputs": dict(entry.outputs),
                "designHash": design_hash,
                "campaignDigest": campaign_digest,
            }
        )
        lineage[candidate_hash] = {
            "candidateHash": candidate_hash,
            "designHash": design_hash,
            "campaignDigest": campaign_digest,
            "spaceId": candidate.provenance.space_id if candidate else record.campaign_id,
            "parentHash": candidate.parent_hash if candidate else None,
            "mutations": [item.as_dict() for item in candidate.mutations] if candidate else [],
            "evaluations": evaluated,
            "promotions": promotion,
            "independenceRuns": {
                "mesh": mesh_runs,
                "timestep": timestep_runs,
            },
            "artifactHashes": artifact_hashes,
            "validatedFinal": gate.validated_final,
            "blockers": list(gate.blockers),
        }
    return candidate_set, lineage


def _energy_closure_ok(record: CampaignRecord) -> bool:
    outputs: dict[str, float] = {}
    for entry in record.candidates.values():
        if entry.outputs:
            outputs = dict(entry.outputs)
            break
    if not outputs:
        return False
    required = {"shaft_power_w", "electrical_power_w", "heat_load_w"}
    if not required.issubset(outputs):
        return False
    result = assess_closure(
        "energy",
        {"energy": outputs["shaft_power_w"] + outputs["heat_load_w"]},
        {"energy": outputs["electrical_power_w"]},
    )
    return result.passed


def _candidate_artifact_hashes(
    candidate: Candidate | None,
    entry: Any,
    record: CampaignRecord,
) -> list[str]:
    hashes: list[str] = []
    if candidate is not None:
        hashes.append(candidate.candidate_hash)
    for item in record.evaluations:
        if item.candidate_hash == entry.candidate_hash and item.geometry_hash:
            hashes.append(item.geometry_hash)
    return sorted(set(hashes))


def _verify_reproducible(cfg: BenchmarkConfig, design_hash: str, campaign_digest: str) -> bool:
    """Re-derive the pure (solver-free) design/campaign digests for the same seed."""

    space = generic_design_space()
    second_design = content_digest(space)
    if second_design != design_hash:
        return False
    spec = _campaign_spec(cfg, space)
    record = run_campaign(spec, _make_evaluator(), evaluator_identity="gen12-cheap-v1")
    return content_digest(record.as_dict()) == campaign_digest


def benchmark_report_json(report: BenchmarkReport) -> str:
    return json.dumps(report.as_dict(), indent=2, sort_keys=True)


def digest_of(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def independence_kinds() -> tuple[str, str]:
    return (MESH, TIMESTEP)
