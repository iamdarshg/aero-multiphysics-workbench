"""Milestone 4 top-level command: 80 mm three-stage EDF end-to-end workflow.

Reproducible entry point (run from the repository root)::

    uv run --directory services/api python ../../examples/edf/80mm_three_stage/run.py
    uv run --directory services/api python \
        ../../examples/edf/80mm_three_stage/run.py --variant 70mm-2stage

Pipeline (all physics through generic M1/M2/M3 facilities):

1. parametric geometry via generic ``build_duct_system`` + STEP/BREP/STL export
2. governed native jobs (single worker): Gmsh mesh coarse/medium, CAD
   interchange, ROSS Campbell + modal, PyBaMM Thevenin pack discharge
3. heavy natives (OpenFOAM MRF, Code_Aster, Elmer, preCICE) scheduled through
   the SAME job system; absent engines fail closed with explicit receipts --
   recorded as deferred, never fabricated
4. OpenMDAO scalar reconciliation of torque/RPM/power/current/voltage/losses
5. seeded screening DOE from design state with quality gating
6. fidelity-planner sequence from participant policies; analytic field transfer
7. provenance-backed design result + evidence bundle under
   ``docs/evidence/milestone-4/``

GCP spend: $0.00 -- everything executes locally.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any

EXAMPLE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(EXAMPLE_DIR))

REPO_ROOT = EXAMPLE_DIR.parents[2]

# Self-contained bootstrap so the documented one-command invocation works
# without pytest's pythonpath: expose generic core packages + solvers.
for _entry in (
    "packages/core",
    "packages/geometry",
    "packages/semantics",
    "packages/materials",
    "packages/mesh",
    "packages/coupling",
    "packages/convergence",
    "packages/optimization",
    "packages/dynamics",
    "packages/thermal",
    "packages/envelope",
    "solvers",
    "services/api",
    ".",
):
    sys.path.insert(0, str(REPO_ROOT / _entry))

from edf_config import CONSTRAINTS, EDF80Config  # noqa: E402
from edf_coupling import (  # noqa: E402
    aero_structural_transfer,
    solve_coupled_system,
)
from edf_geometry import build_edf_geometry, design_variables, export_edf_step  # noqa: E402
from edf_participants import (  # noqa: E402
    battery_inputs,
    cad_inputs,
    coupling_inputs,
    mesh_inputs,
    openfoam_inputs,
    participant_graph,
    rotor_campbell_inputs,
    rotor_modal_inputs,
    structural_inputs,
    thermal_inputs,
)
from edf_screening import screen_candidate  # noqa: E402
from edf_study import (  # noqa: E402
    assemble_design_result,
    design_state_for,
    plan_edf_fidelity,
    run_screening_doe,
    solver_identities,
)

COMPLETED = "COMPLETED"


def _run_job(
    manager: Any, participant_id: str, inputs: dict[str, object], design_id: str
) -> dict[str, Any]:
    job_id = manager.submit(participant_id, inputs, design_id=design_id, deferred=True)
    state = manager.run(job_id)
    record: dict[str, Any] = {
        "job_id": job_id,
        "participant_id": participant_id,
        "state": state,
        "status": manager.status(job_id),
        "events": manager.events(job_id),
        "artifacts": manager.artifacts(job_id),
        "provenance": manager.provenance(job_id),
    }
    if state == COMPLETED:
        record["envelope"] = manager.envelope(job_id)
    return record


def _as_float(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return float("nan")
    return float(value)


def _validation_state(result: dict[str, object]) -> object:
    quality = result.get("quality")
    if isinstance(quality, dict):
        state = quality.get("validation_state")
        if isinstance(state, str):
            return state
    return "not-validated"


def _constraint_check(
    config: EDF80Config, outputs: dict[str, float]
) -> list[dict[str, object]]:
    results = []
    for entry in CONSTRAINTS:
        item = dict(entry)
        name = str(item["name"])
        bound = str(item["bound"])
        limit = _as_float(item["limitSI"])
        value = float(outputs.get(name, float("nan")))
        if bound == "upper":
            passed = value == value and value <= limit
        elif bound == "lower":
            passed = value == value and value >= limit
        else:
            passed = value == value and value == limit
        results.append(
            {"name": name, "bound": bound, "limit": limit, "value": value, "passed": passed}
        )
    # Envelope diameter is a config identity, not a screening output.
    for result in results:
        if result["name"] == "outer_diameter_mm":
            diameter = config.outer_diameter_mm
            result["value"] = diameter
            result["passed"] = diameter <= _as_float(result["limit"])
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="80 mm three-stage EDF workflow")
    parser.add_argument(
        "--variant", default="80mm-3stage", help="80mm-3stage | 70mm-2stage | 90mm-4stage"
    )
    parser.add_argument("--evidence-dir", default=None, help="override evidence output dir")
    parser.add_argument("--jobs-dir", default=None, help="override governed job root")
    args = parser.parse_args(argv)

    variants = {config.name: config for config in EDF80Config.variants()}
    if args.variant not in variants:
        print(f"unknown variant: {args.variant} (choices: {sorted(variants)})")
        return 2
    config = variants[args.variant]
    started = time.time()

    default_evidence = REPO_ROOT / "docs" / "evidence" / "milestone-4"
    evidence = Path(args.evidence_dir) if args.evidence_dir else default_evidence
    evidence.mkdir(parents=True, exist_ok=True)
    (evidence / "cad").mkdir(parents=True, exist_ok=True)
    jobs_root = Path(args.jobs_dir) if args.jobs_dir else evidence / "jobs"

    from participants.lifecycle import NativeJobManager  # noqa: PLC0415

    manager = NativeJobManager(jobs_root)

    # 1. geometry + STEP/BREP/STL through generic CAD ---------------------------
    geometry = build_edf_geometry(config)
    step_records = export_edf_step(
        config, evidence / "cad", basename=f"edf-{config.name}"
    )

    # 2. governed native jobs (bounded, sequential, single worker) --------------
    jobs: dict[str, dict[str, Any]] = {}
    jobs["mesh-coarse"] = _run_job(
        manager, "domain-mesh", mesh_inputs(config, base_size_mm=14.0), config.design_id
    )
    jobs["mesh-medium"] = _run_job(
        manager, "domain-mesh", mesh_inputs(config, base_size_mm=10.0), config.design_id
    )
    jobs["cad"] = _run_job(
        manager, "cad-interchange", cad_inputs(config), config.design_id
    )
    jobs["campbell"] = _run_job(
        manager, "rotor-campbell", rotor_campbell_inputs(config), config.design_id
    )
    jobs["modal"] = _run_job(
        manager,
        "rotor-modal",
        rotor_modal_inputs(speed_rpm=config.rated_rpm),
        config.design_id,
    )
    jobs["battery"] = _run_job(
        manager,
        "pack-thevenin-discharge",
        battery_inputs(discharge_current_a=25.0),
        config.design_id,
    )
    # 3. heavy natives through the SAME scheduling path (fail closed) -----------
    jobs["cfd-mrf"] = _run_job(
        manager,
        "rotating-flow-mrf",
        openfoam_inputs(config, rpm=config.rated_rpm),
        config.design_id,
    )
    jobs["structural"] = _run_job(
        manager, "structural-static", structural_inputs(), config.design_id
    )
    jobs["thermal"] = _run_job(
        manager, "thermal-conduction", thermal_inputs(heat_load_w=35.0), config.design_id
    )
    jobs["coupled"] = _run_job(
        manager, "coupled-interface-validation", coupling_inputs(), config.design_id
    )

    def envelope_of(key: str) -> dict[str, Any] | None:
        record = jobs[key]
        envelope = record.get("envelope")
        return envelope if isinstance(envelope, dict) else None

    # Mesh quality inputs for gating (measured natives, fail-closed defaults) ---
    coarse_env = envelope_of("mesh-coarse")
    medium_env = envelope_of("mesh-medium")
    if coarse_env and medium_env:
        coarse_n = float(coarse_env["scalars"]["element_count"])
        medium_n = float(medium_env["scalars"]["element_count"])
        sicn_coarse = float(coarse_env["scalars"]["min_sicn"])
        sicn_medium = float(medium_env["scalars"]["min_sicn"])
        mesh_quality_sensitivity = abs(sicn_medium - sicn_coarse) / max(sicn_medium, 1e-12)
        min_sicn = min(sicn_coarse, sicn_medium)
    else:
        coarse_n = medium_n = 0.0
        min_sicn = float("nan")
        mesh_quality_sensitivity = 99.0

    modal_env = envelope_of("modal")
    whirl_hz = float(modal_env["scalars"]["first_whirl_hz"]) if modal_env else None

    # 4. OpenMDAO scalar reconciliation ------------------------------------------
    try:
        coupled = solve_coupled_system(config, rpm=config.rated_rpm)
        coupled_ok = bool(coupled.converged)
    except Exception as exc:  # noqa: BLE001 -- recorded, screening still reported
        coupled = None
        coupled_ok = False
        print(f"coupled solve failed closed: {exc}")

    # 5. screening DOE from design state -----------------------------------------
    doe = run_screening_doe(
        config,
        n_samples=6,
        seed=0,
        mesh_sensitivity=mesh_quality_sensitivity,
        min_sicn=min_sicn if min_sicn == min_sicn else 0.0,
        first_whirl_hz=whirl_hz,
    )

    # 6. fidelity sequence from participant policies ------------------------------
    fidelity = {
        "aero": plan_edf_fidelity(maturity=0.7, constraint_margin=0.05),
        "aero_finalist_hold": plan_edf_fidelity(
            maturity=0.85, constraint_margin=0.4, current="mrf-steady", cost_budget=20.0
        ),
    }
    transfer = aero_structural_transfer()

    # Design result + constraint audit --------------------------------------------
    screening = screen_candidate(config, rpm=config.rated_rpm, freestream_m_s=0.0)
    natives_summary: dict[str, Any] = {}
    for _job, record in jobs.items():
        envelope = record.get("envelope")
        if isinstance(envelope, dict):
            natives_summary[record["participant_id"]] = {
                "source": envelope.get("source"),
                "fidelity": envelope.get("fidelity"),
                "scalars": envelope.get("scalars"),
                "units": envelope.get("units"),
                "validity": envelope.get("validity"),
                "job_id": record["job_id"],
            }
        else:
            natives_summary[record["participant_id"]] = {
                "source": "deferred-unavailable-engine",
                "state": record["state"],
                "error_code": record["status"].get("error_code"),
                "job_id": record["job_id"],
            }
    result = assemble_design_result(
        config,
        native_summary=natives_summary,
        mesh_summary={
            "coarse_elements": coarse_n,
            "medium_elements": medium_n,
            "min_sicn": min_sicn,
        },
        coupled_result=coupled,
        mesh_sensitivity=(
            mesh_quality_sensitivity if mesh_quality_sensitivity < 90.0 else None
        ),
    )
    rated_outputs = dict(screening.outputs)
    rated_outputs["outer_diameter_mm"] = config.outer_diameter_mm
    dynamic_section = result.get("dynamic")
    if isinstance(dynamic_section, dict):
        rated_outputs["resonance_margin_hz"] = _as_float(
            dynamic_section.get("resonance_margin_hz")
        )
    rated_outputs["min_sicn"] = min_sicn
    constraint_audit = _constraint_check(config, rated_outputs)

    # Variant reuse proof (same code, other diameters/stage counts) ----------------
    variant_table = []
    for other in EDF80Config.variants():
        other_geo = build_edf_geometry(other)
        other_screen = screen_candidate(other, rpm=35000.0, freestream_m_s=0.0)
        try:
            other_coupled = solve_coupled_system(other, rpm=35000.0)
            other_ok = bool(other_coupled.converged)
        except Exception:  # noqa: BLE001
            other_ok = False
        variant_table.append(
            {
                "variant": other.name,
                "n_stages": other.n_stages,
                "shape_hash": other_geo.shape_hash,
                "thrust_n": other_screen.outputs["thrust_n"],
                "current_a": other_screen.outputs["current_a"],
                "coupled_converged": other_ok,
                "core_changes": 0,
            }
        )

    summary = {
        "milestone": 4,
        "variant": config.name,
        "geometry_hashes": {
            "parameter_hash": geometry.parameter_hash,
            "shape_hash": geometry.shape_hash,
        },
        "gcp_spend_usd": 0.0,
        "elapsed_s": round(time.time() - started, 1),
        "generic_capabilities": [
            "build_duct_system count-agnostic (2/3/4 rotating zones, zero core changes)",
            "openfoam N-zone MRF case builder (generic; 1/2/3/4 zones proven)",
            "domain-mesh native meshing + quality receipts",
            "cad-interchange STEP/BREP roundtrip",
            "ross campbell/modal native rotor dynamics",
            "pybamm thevenin native pack discharge",
            "ManifestCoordinator OpenMDAO scalar reconciliation",
            "transfer_field analytic pressure exchange + precice fail-closed probe",
            "plan_fidelity ladder-driven escalation",
            "run_doe LHS from design state + assess_sample quality gating",
            "assess_measure/assess_global physical closure",
            "separation/check_resonance generic resonance policy",
            "MaterialDatabase seeded revisions + region bindings",
        ],
        "design_variables": [variable.name for variable in design_variables(config)],
        "participant_graph": {
            "nodes": list(participant_graph().nodes),
            "links": [
                [link[0], link[1], list(link[2])] for link in participant_graph().links
            ],
        },
        "fidelities_executed": {
            key: {
                "source": (
                    "native_solver"
                    if record.get("envelope")
                    else "deferred-unavailable-engine"
                ),
                "state": record["state"],
                "job_id": record["job_id"],
            }
            for key, record in jobs.items()
        },
        "native_numbers": {
            key: record["envelope"]["scalars"]
            for key, record in jobs.items()
            if record.get("envelope")
        },
        "finalist_screening": {
            "thrust_n": screening.outputs["thrust_n"],
            "current_a": screening.outputs["current_a"],
            "tip_mach": screening.outputs["tip_mach"],
            "fos": screening.outputs["fos"],
            "source": screening.source,
            "fidelity": screening.fidelity,
        },
        "coupled_converged": coupled_ok,
        "doe": {
            "samples": len(doe.samples),
            "invalid": doe.invalid_count,
            "best_state": doe.best.state if doe.best else None,
            "best_point": list(doe.best.point) if doe.best else None,
            "best_outputs": dict(doe.best.outputs) if doe.best else None,
        },
        "fidelity_plans": {
            name: {
                "level": plan.level,
                "escalate": plan.escalate,
                "reasons": list(plan.reasons),
            }
            for name, plan in fidelity.items()
        },
        "field_transfer": {
            "accepted": transfer.accepted,
            "conservation_error": transfer.relative_conservation_error,
            "method": transfer.method,
        },
        "constraint_audit": constraint_audit,
        "failed_constraints": [item for item in constraint_audit if not item["passed"]],
        "mesh_independence": {
            "coarse_elements": coarse_n,
            "medium_elements": medium_n,
            "min_sicn": min_sicn,
            "quality_sensitivity": mesh_quality_sensitivity,
            "flow_solution": "not-demonstrated-heavy-cfd-deferred",
        },
        "validation_state": _validation_state(result),
        "design_result_ref": "design_result.json",
        "step_artifacts": step_records["artifacts"],
        "solver_identities": solver_identities(),
        "design_state": design_state_for(config),
        "variant_reuse": variant_table,
        "remaining_general_gaps": [
            "no native OpenFOAM/Code_Aster/Elmer/preCICE on host (fail-closed; need Linux runners)",
            "flow-solution mesh/timestep independence unproven until heavy CFD executes",
            "no dedicated motor/ESC participant manifest (analytic example-level via OpenMDAO)",
            "no transient AMI execution path demonstrated (config generic, engine absent)",
            "campbell beam-consistency gate rejects short stiff rotors (bearing modes first)",
        ],
    }
    summary_text = json.dumps(summary, indent=2, sort_keys=True, default=str)
    (evidence / "summary.json").write_text(summary_text, encoding="utf-8")
    (evidence / "design_result.json").write_text(
        json.dumps(result, indent=2, sort_keys=True, default=str), encoding="utf-8"
    )

    digest = hashlib.sha256(config.config_hash.encode()).hexdigest()[:12]
    print(f"variant: {config.name} (design {config.design_id}, rev {digest})")
    thrust = screening.outputs["thrust_n"]
    print(f"thrust(static, rated): {thrust:.2f} N [{screening.source}/{screening.fidelity}]")
    print(f"coupled converged: {coupled_ok} (engine=openmdao)")
    best_state = doe.best.state if doe.best else None
    print(f"doe samples: {len(doe.samples)} invalid={doe.invalid_count} best={best_state}")
    print(f"mesh: coarse={coarse_n:.0f} medium={medium_n:.0f} min_sicn={min_sicn:.3f}")
    failed = [
        str(item["name"]) for item in constraint_audit if not item["passed"]
    ]
    print(f"failed constraints: {failed}")
    quality_section = result.get("quality")
    state = (
        quality_section.get("validation_state")
        if isinstance(quality_section, dict)
        else "not-validated"
    )
    print(f"validation: {state}")
    print(f"evidence: {evidence / 'summary.json'}")
    print("gcp spend: $0.00")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
