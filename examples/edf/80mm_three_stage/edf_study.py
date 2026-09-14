"""Example-level study: DOE, fidelity planning, quality gating, design result.

Generic M3 machinery (``study_from_design_state``, ``run_doe``,
``plan_fidelity``, ``assess_sample``, ``assess_measure``, ``assess_global``,
``separation``/``check_resonance``) is driven by example data. No optimizer,
planner, or quality code is EDF-aware.
"""

from __future__ import annotations

from collections.abc import Mapping
from importlib import metadata as importlib_metadata

from aeroworkbench_convergence.measures import (
    DEFAULT_MEASURES,
    assess_global,
    assess_measure,
)
from aeroworkbench_coupling.manifest_coordinator import CoordinatorResult
from aeroworkbench_coupling.resonance import (
    ResonancePolicy,
    check_resonance,
    separation,
)
from aeroworkbench_materials import MaterialDatabase
from aeroworkbench_optimization.drivers import (
    DesignVariable,
    EvaluateFunction,
    StudyResult,
    run_doe,
    study_from_design_state,
)
from aeroworkbench_optimization.planner import (
    FidelityPlan,
    FidelitySignals,
    plan_fidelity,
)
from aeroworkbench_optimization.quality import PhysicsFlags, QualityPolicy, assess_sample
from edf_config import (
    CONSTRAINTS,
    MATERIAL_BINDINGS,
    OBJECTIVES,
    OPERATING_POINTS,
    EDF80Config,
)
from edf_coupling import forcing_spectra, modal_spectrum, solve_coupled_system
from edf_geometry import build_edf_geometry, motion_frames
from edf_participants import fidelity_ladders
from edf_screening import energy_closure_error, screen_candidate
from ross.rotor import beam_first_critical_rpm

FREESTREAM_BY_POINT = {"static": 0.0, "forward-flow": 18.0, "max-rpm": 0.0}

def _solver_entry(
    participant: str, solver: str, version: str, settings: dict[str, object]
) -> dict[str, object]:
    return {
        "participant": participant,
        "solver": solver,
        "version": version,
        "settings": settings,
    }


PARTICIPANT_SOLVERS: tuple[dict[str, object], ...] = (
    _solver_entry("rotating-flow-mrf", "openfoam", "native-or-deferred", {"rotating_model": "MRF"}),
    _solver_entry("structural-static", "code-aster", "native-or-deferred", {"analysis": "static"}),
    _solver_entry("thermal-conduction", "elmer", "native-or-deferred", {"model": "thermal"}),
    _solver_entry("rotor-campbell", "ross", "native", {"analysis": "campbell"}),
    _solver_entry("rotor-modal", "ross", "native", {"analysis": "modal"}),
    _solver_entry("pack-thevenin-discharge", "pybamm", "native", {"model": "thevenin"}),
    _solver_entry("domain-mesh", "gmsh", "native", {}),
    _solver_entry("cad-interchange", "freecad-occ", "native", {}),
)


def design_state_for(config: EDF80Config) -> dict[str, object]:
    """DesignRevision-shaped state: objectives/constraints/points live in design."""

    database = MaterialDatabase.seeded()
    bindings = []
    for entry in MATERIAL_BINDINGS:
        material_id = getattr(config, entry["material"])
        bindings.append(
            {
                "region": entry["region"],
                "materialIdentity": material_id,
                "materialDigest": database.material_digest(material_id),
            }
        )
    parameters = {
        "outerDiameter": {"value": config.outer_diameter_mm, "unit": "mm"},
        "hubDiameter": {"value": config.hub_diameter_mm, "unit": "mm"},
        "stages": {"value": float(config.n_stages), "unit": "dimensionless"},
        "chord": {"value": config.chord_mm, "unit": "mm"},
        "ratedRpm": {"value": config.rated_rpm, "unit": "rpm"},
    }
    return {
        "designId": config.design_id,
        "revisionId": config.config_hash[:12],
        "parentRevisionHash": None,
        "parameters": parameters,
        "materials": {"bindings": bindings},
        "operatingPoints": [dict(point) for point in OPERATING_POINTS],
        "objectives": [dict(item) for item in OBJECTIVES],
        "constraints": [dict(item) for item in CONSTRAINTS],
        "participantSolvers": [dict(item) for item in PARTICIPANT_SOLVERS],
        "motionFrames": [dict(frame) for frame in motion_frames(config, config.rated_rpm)],
    }


def _study_variables() -> tuple[DesignVariable, ...]:
    return (
        DesignVariable("rpm", "rpm", "continuous", 28000.0, 45000.0),
        DesignVariable("chord_mm", "mm", "continuous", 10.0, 16.0),
    )


def run_screening_doe(
    config: EDF80Config,
    *,
    n_samples: int = 6,
    seed: int = 0,
    mesh_sensitivity: float = 0.02,
    min_sicn: float = 0.25,
    first_whirl_hz: float | None = None,
) -> StudyResult:
    """Seeded LHS screening DOE from design state with quality gating.

    ``mesh_sensitivity``/``min_sicn`` are measured native-mesh inputs (the DOE
    itself is analytic); ``first_whirl_hz`` is a native ROSS measurement when
    available, else the analytic beam estimate (labelled by the caller).
    """

    whirl = (
        first_whirl_hz
        if first_whirl_hz is not None
        else beam_first_critical_rpm(shaft_length_m=0.15, shaft_diameter_m=0.008) / 60.0
    )
    policy = QualityPolicy(
        require_converged=True,
        require_closure=True,
        max_mesh_sensitivity=0.05,
        max_timestep_sensitivity=0.05,
        require_validity=True,
        min_resonance_margin_hz=config.min_resonance_margin_hz,
    )

    def evaluate(
        point: Mapping[str, float], operating_point: str
    ) -> tuple[Mapping[str, float], PhysicsFlags]:
        receipt = screen_candidate(
            config,
            rpm=point["rpm"],
            freestream_m_s=FREESTREAM_BY_POINT[operating_point],
            chord_mm=point["chord_mm"],
        )
        forcing = forcing_spectra(
            rpm=point["rpm"],
            blade_counts=config.blade_counts,
            stator_counts=config.stator_counts,
        )
        margin = separation(forcing, (modal_spectrum(whirl),)).min_separation_hz
        outputs = dict(receipt.outputs)
        outputs["outer_diameter_mm"] = config.outer_diameter_mm
        outputs["resonance_margin_hz"] = margin
        outputs["min_sicn"] = min_sicn
        flags = PhysicsFlags(
            converged=True,
            closure_passed=energy_closure_error(receipt) < 0.05,
            validity_ok=receipt.validity_ok,
            mesh_sensitivity=mesh_sensitivity,
            timestep_sensitivity=0.0,
            resonance_margin_hz=margin,
        )
        return outputs, flags

    study = study_from_design_state(design_state_for(config), _study_variables())
    evaluate_typed: EvaluateFunction = evaluate
    return run_doe(
        study, evaluate_typed, method="lhs", n=n_samples, seed=seed,
        quality=policy, source="analytical",
    )


def plan_edf_fidelity(
    *,
    maturity: float,
    constraint_margin: float,
    current: str = "screening-analytic",
    cost_budget: float = 20.0,
) -> FidelityPlan:
    """One planner step on the aero ladder; reasons come from generic rules."""

    ladder = fidelity_ladders()["aero"]
    names = [item.name for item in ladder]
    signals = FidelitySignals(
        question="finalist-rotating-flow",
        maturity=maturity,
        constraint_margin=constraint_margin,
        disagreement=0.0,
        sensitivity=0.0,
        convergence_difficulty=0.0,
        mesh_dependence=0.0,
        timestep_dependence=0.0,
        resonance_proximity=10.0,
        validity_ok={name: True for name in names},
        cost_budget=cost_budget,
    )
    return plan_fidelity(current, ladder, signals)


def _solver_version(distribution: str) -> str:
    try:
        return importlib_metadata.version(distribution)
    except importlib_metadata.PackageNotFoundError:
        return "absent"


def solver_identities() -> dict[str, str]:
    """Real solver identities from installed distribution metadata."""

    return {
        "ross": _solver_version("ross-rotordynamics"),
        "pybamm": _solver_version("pybamm"),
        "gmsh": _solver_version("gmsh"),
        "cadquery": _solver_version("cadquery"),
        "openmdao": _solver_version("openmdao"),
        "openfoam": "absent-no-binary",
        "code-aster": "absent-no-binary",
        "elmer": "absent-no-binary",
        "precice": "absent-no-library",
    }


def _as_float(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("EXPECTED_NUMERIC_VALUE")
    return float(value)


def _is_native(summary: Mapping[str, object], key: str) -> bool:
    entry = summary.get(key)
    return isinstance(entry, Mapping) and entry.get("source") == "native_solver"


def _native_scalar(summary: Mapping[str, object], key: str, name: str) -> float | None:
    entry = summary.get(key)
    if isinstance(entry, Mapping) and entry.get("source") == "native_solver":
        scalars = entry.get("scalars")
        if isinstance(scalars, Mapping):
            raw = scalars.get(name)
            if isinstance(raw, (int, float)) and not isinstance(raw, bool):
                return float(raw)
    return None


def assemble_design_result(
    config: EDF80Config,
    *,
    native_summary: Mapping[str, object] | None = None,
    mesh_summary: Mapping[str, object] | None = None,
    coupled_result: CoordinatorResult | None = None,
    mesh_sensitivity: float | None = None,
    validation_state: str | None = None,
) -> dict[str, object]:
    """Complete provenance-backed design result (4.md section K)."""

    natives: Mapping[str, object] = native_summary or {}
    meshes: Mapping[str, object] = mesh_summary or {}
    geometry = build_edf_geometry(config)
    screening = screen_candidate(config, rpm=config.rated_rpm, freestream_m_s=0.0)
    if coupled_result is not None:
        coupled_values = dict(coupled_result.values)
        coupled_converged = bool(coupled_result.converged)
    else:
        try:
            coupled = solve_coupled_system(config, rpm=config.rated_rpm)
            coupled_values = dict(coupled.values)
            coupled_converged = bool(coupled.converged)
        except Exception:  # noqa: BLE001 -- screening fallback stays labelled analytical
            coupled_values = {}
            coupled_converged = False

    first_whirl = (
        beam_first_critical_rpm(shaft_length_m=0.15, shaft_diameter_m=0.008) / 60.0
    )
    whirl_source = "analytical"
    whirl_fidelity = "beam-estimate"
    modal_whirl = _native_scalar(natives, "rotor-modal", "first_whirl_hz")
    if modal_whirl is not None:
        first_whirl = modal_whirl
        whirl_source = "native_solver"
        whirl_fidelity = "beam-modal"
    else:
        critical_rpm = _native_scalar(natives, "rotor-campbell", "first_critical_rpm")
        if critical_rpm is not None:
            first_whirl = critical_rpm / 60.0
            whirl_source = "native_solver"
            whirl_fidelity = "beam-campbell"
    forcing = forcing_spectra(
        rpm=config.rated_rpm,
        blade_counts=config.blade_counts,
        stator_counts=config.stator_counts,
    )
    proximity = separation(forcing, (modal_spectrum(first_whirl),))
    trigger = check_resonance(
        forcing,
        (modal_spectrum(first_whirl),),
        ResonancePolicy(
            warning_margin_hz=100.0,
            critical_margin_hz=25.0,
            watch_activate=("transient",),
            critical_activate=("transient",),
            available=("transient",),
        ),
    )
    coarse = _as_float(meshes.get("coarse_elements", 0.0))
    medium = _as_float(meshes.get("medium_elements", 0.0))
    # Measured mesher-quality sensitivity (SICN-based) supplied by the caller
    # from the native mesh pair; absent means unreported (quality gate fails
    # closed). Element-count scaling is reported separately and is NOT a
    # solution-sensitivity claim.
    measured = float(mesh_sensitivity) if mesh_sensitivity is not None else float("nan")
    mesh_sensitivity_out: float | None = measured if measured == measured else None
    min_sicn_raw = _as_float(meshes.get("min_sicn", float("nan")))
    min_sicn_out: float | None = min_sicn_raw if min_sicn_raw == min_sicn_raw else None

    power_measure = assess_measure(
        DEFAULT_MEASURES["shaft-power"],
        screening.outputs["shaft_power_w"],
        float(coupled_values.get("aero.shaft_power_w", screening.outputs["shaft_power_w"])),
    )
    energy_measure = assess_measure(
        DEFAULT_MEASURES["energy"],
        screening.outputs["electrical_power_w"],
        float(
            coupled_values.get(
                "motor.electrical_power_w", screening.outputs["electrical_power_w"]
            )
        ),
    )
    current_measure = assess_measure(
        DEFAULT_MEASURES["current"],
        screening.outputs["current_a"],
        float(coupled_values.get("motor.current_a", screening.outputs["current_a"])),
    )
    global_report = assess_global(
        participants={
            "aero": True,
            "motor": coupled_converged,
            "battery": coupled_converged,
            "thermal": coupled_converged,
        },
        interfaces={"motor-terminals": (0.0, 1e-6)},
        closures={
            "shaft-power": power_measure,
            "energy": energy_measure,
            "current": current_measure,
        },
        quality={
            "mesh": (measured == measured and measured < 0.35),
            "validity": screening.validity_ok,
        },
    )
    sample_flags = PhysicsFlags(
        converged=coupled_converged,
        closure_passed=global_report.closure_passed,
        validity_ok=screening.validity_ok,
        mesh_sensitivity=measured if measured == measured else 99.0,
        timestep_sensitivity=0.0,
        resonance_margin_hz=proximity.min_separation_hz,
    )
    verdict = assess_sample(
        sample_flags,
        QualityPolicy(min_resonance_margin_hz=config.min_resonance_margin_hz),
    )
    heavy_present = any(
        _is_native(natives, key)
        for key in ("rotating-flow-mrf", "structural-static", "thermal-conduction")
    )
    state = validation_state or (
        "validated" if (verdict.state == "valid" and heavy_present) else "not-validated"
    )

    electrical: dict[str, object] = {
        "voltage_v": coupled_values.get("motor.voltage_v", screening.outputs["voltage_v"]),
        "current_a": coupled_values.get("motor.current_a", screening.outputs["current_a"]),
        "electrical_power_w": coupled_values.get(
            "motor.electrical_power_w", screening.outputs["electrical_power_w"]
        ),
        "source": "openmdao-coupled-analytic"
        if coupled_values
        else screening.source,
        "fidelity": "coupled-analytic" if coupled_values else screening.fidelity,
    }
    return {
        "identity": {
            "designId": config.design_id,
            "revisionId": config.config_hash[:12],
            "configHash": config.config_hash,
            "configName": config.name,
        },
        "geometry": {
            "n_stages": config.n_stages,
            "outer_diameter_mm": config.outer_diameter_mm,
            "parameter_hash": geometry.parameter_hash,
            "shape_hash": geometry.shape_hash,
            "kernel_available": geometry.kernel_available,
            "source": "native_solver" if geometry.kernel_available else "unavailable",
        },
        "meshes": {
            "coarse_elements": coarse,
            "medium_elements": medium,
            "min_sicn": min_sicn_out,
            "mesh_sensitivity": mesh_sensitivity_out,
            "source": "native_solver" if medium > 0 else "deferred",
        },
        "aerodynamic": {
            "thrust_n": screening.outputs["thrust_n"],
            "mass_flow_kg_s": screening.outputs["mass_flow_kg_s"],
            "torque_n_m": screening.outputs["torque_n_m"],
            "tip_mach": screening.outputs["tip_mach"],
            "figure_of_merit": screening.outputs["figure_of_merit"],
            "source": screening.source,
            "fidelity": screening.fidelity,
            "native_cfd": "deferred-unavailable-engine",
        },
        "electrical": electrical,
        "thermal": {
            "winding_temp_k": screening.outputs["winding_temp_k"],
            "esc_temp_k": screening.outputs["esc_temp_k"],
            "source": screening.source,
            "fidelity": screening.fidelity,
            "native_conduction": "deferred-unavailable-engine",
        },
        "structural": {
            "centrifugal_stress_pa": screening.outputs["centrifugal_stress_pa"],
            "fos": screening.outputs["fos"],
            "tip_deflection_mm": screening.outputs["tip_deflection_mm"],
            "source": screening.source,
            "fidelity": screening.fidelity,
            "native_statics": "deferred-unavailable-engine",
        },
        "dynamic": {
            "first_whirl_hz": first_whirl,
            "whirl_source": whirl_source,
            "whirl_fidelity": whirl_fidelity,
            "resonance_margin_hz": proximity.min_separation_hz,
            "resonance_trigger": trigger.state,
        },
        "quality": {
            "convergence": {
                "coupled_converged": coupled_converged,
                "closure_passed": global_report.closure_passed,
                "global": global_report.detail,
            },
            "physical_closure": {
                "shaft-power": power_measure.passed,
                "energy": energy_measure.passed,
                "current": current_measure.passed,
            },
            "mesh_independence": mesh_sensitivity_out,
            "timestep_independence": "not-applicable-steady-mrf",
            "fidelity": "screening-analytic-plus-native-rotor-battery-mesh-cad",
            "validation_state": state,
            "sample_state": verdict.state,
            "warnings": list(screening.warnings) + list(verdict.reasons),
        },
        "provenance": {
            "solver_identities": solver_identities(),
            "input_hash": screening.input_hash,
            "design_hash": config.config_hash,
            "native_summary": dict(natives),
        },
    }


__all__ = [
    "FREESTREAM_BY_POINT",
    "PARTICIPANT_SOLVERS",
    "assemble_design_result",
    "design_state_for",
    "plan_edf_fidelity",
    "run_screening_doe",
    "solver_identities",
]
