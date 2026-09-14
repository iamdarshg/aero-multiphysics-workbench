"""Example-level participant graph: generic M2 manifests wired for the EDF.

Every participant id comes from the generic registry
(``participants.manifest``); this module only selects ids, fills validated
job inputs from the example configuration, and declares per-discipline
fidelity ladders consumed by the generic fidelity planner. Heavy-native
execution stays behind capability probes -- never faked.
"""

from __future__ import annotations

from dataclasses import dataclass

from aeroworkbench_optimization.planner import FidelityImplementation
from edf_config import EDF80Config
from edf_screening import screen_candidate


@dataclass(frozen=True, slots=True)
class ParticipantGraph:
    nodes: tuple[str, ...]
    links: tuple[tuple[str, str, tuple[str, ...]], ...]
    detail: str


def participant_graph() -> ParticipantGraph:
    """Physics participants able to serve the EDF workflow (generic ids)."""

    nodes = (
        "rotating-flow-mrf",
        "compressible-steady-flow",
        "structural-static",
        "structural-modal",
        "thermal-conduction",
        "rotor-campbell",
        "rotor-modal",
        "cell-spm-discharge",
        "pack-thevenin-discharge",
        "coupled-interface-validation",
        "domain-mesh",
        "cad-interchange",
    )
    links = (
        ("rotating-flow-mrf", "structural-static", ("pressure",)),
        ("structural-static", "structural-modal", ("displacement",)),
        ("rotor-campbell", "rotor-modal", ("critical-speeds",)),
        ("pack-thevenin-discharge", "thermal-conduction", ("heat-flow",)),
        ("rotating-flow-mrf", "thermal-conduction", ("temperature",)),
    )
    return ParticipantGraph(
        nodes=nodes,
        links=links,
        detail="aero/CFD, structural, thermal, rotor-dynamics, battery, mesh, CAD, coupling",
    )


def fidelity_ladders() -> dict[str, tuple[FidelityImplementation, ...]]:
    """Per-discipline fidelity policies; the planner derives the sequence."""

    return {
        "aero": (
            FidelityImplementation("screening-analytic", 0, 1.0, ()),
            FidelityImplementation("mrf-steady", 1, 10.0, ("rotating",)),
            FidelityImplementation("ami-transient", 2, 100.0, ("rotating", "transient")),
        ),
        "structural": (
            FidelityImplementation("analytic-ring", 0, 1.0, ()),
            FidelityImplementation("linear-static", 1, 10.0, ()),
            FidelityImplementation("prestressed-modal", 2, 20.0, ("prestress",)),
        ),
        "thermal": (
            FidelityImplementation("analytic-lumped", 0, 1.0, ()),
            FidelityImplementation("steady-conduction", 1, 10.0, ()),
        ),
        "electrical": (
            FidelityImplementation("analytic-motor", 0, 1.0, ()),
            FidelityImplementation("spm", 1, 5.0, ()),
            FidelityImplementation("thevenin", 2, 8.0, ()),
        ),
        "rotor": (
            FidelityImplementation("beam-estimate", 0, 1.0, ()),
            FidelityImplementation("beam-campbell", 1, 5.0, ("campbell",)),
        ),
        "coupled": (
            FidelityImplementation("analytic-transfer", 0, 1.0, ()),
            FidelityImplementation("implicit-iqn", 1, 50.0, ("field-coupled",)),
        ),
    }


# -- governed job inputs (validated by each participant's prepare) -------------

def mesh_inputs(config: EDF80Config, *, base_size_mm: float) -> dict[str, object]:
    return {
        "base_size_mm": base_size_mm,
        "n_rotating": config.n_stages,
        "length_mm": config.length_mm,
        "inner_diameter_mm": config.inner_diameter_mm,
        "outer_diameter_mm": config.outer_diameter_mm,
        "zone_length_mm": config.zone_length_mm,
        "zone_gap_mm": config.axial_gap_mm,
    }


def cad_inputs(config: EDF80Config) -> dict[str, object]:
    return {
        "n_rotating": config.n_stages,
        "source_format": "step",
        "length_mm": config.length_mm,
        "inner_diameter_mm": config.inner_diameter_mm,
        "outer_diameter_mm": config.outer_diameter_mm,
        "zone_length_mm": config.zone_length_mm,
        "zone_gap_mm": config.axial_gap_mm,
    }


def rotor_campbell_inputs(config: EDF80Config | None = None) -> dict[str, object]:
    _ = config
    # Impeller-equivalent disk on miniature-bearing stiffness (example-level
    # modelling choice, documented in the milestone-4 evidence). NOTE: on this
    # short stiff shaft the first forward criticals are bearing/disk rigid-body
    # modes, so the generic Campbell beam-consistency gate is expected to fail
    # closed -- a reported GENERAL gap; rotor-modal carries native dynamics.
    return {
        "analysis": "campbell",
        "shaft_length_m": 0.15,
        "shaft_diameter_m": 0.008,
        "n_elements": 6,
        "bearing_stiffness_n_m": 5.0e6,
        "bearing_damping_n_s_m": 2000.0,
        "disk": {
            "position": 3.0,
            "outer_diameter_m": 0.05,
            "width_m": 0.02,
        },
        "max_speed_rpm": 160000.0,
    }


def rotor_modal_inputs(*, speed_rpm: float) -> dict[str, object]:
    inputs = rotor_campbell_inputs()
    inputs["analysis"] = "modal"
    inputs["speed_rpm"] = speed_rpm
    del inputs["max_speed_rpm"]
    return inputs


def battery_inputs(*, discharge_current_a: float) -> dict[str, object]:
    return {
        "model": "thevenin",
        "parameter_set": "ECM_Example",
        "discharge_current_a": discharge_current_a,
        "duration_s": 60.0,
        "n_series": 6,
        "n_parallel": 1,
    }


def openfoam_inputs(config: EDF80Config, *, rpm: float) -> dict[str, object]:
    """Generic rotating-flow case config with one MRF zone per blade row."""

    screening = screen_candidate(config, rpm=rpm, freestream_m_s=0.0)
    compressible = screening.outputs["tip_mach"] > 0.3
    return {
        "participant_id": "rotating-flow-mrf",
        "compressibility": "compressible" if compressible else "incompressible",
        "rotating_model": "MRF",
        "thermal_model": "isothermal",
        "turbulence": "kOmegaSST",
        "steady": True,
        "inlet_velocity_m_s": 12.0,
        "outlet_pressure_pa": 0.0,
        "density_kg_m3": 1.225,
        "viscosity_pa_s": 1.81e-5,
        "rotation_rate_rpm": rpm,
        "rotating_zones": [
            {"name": name, "rotation_rate_rpm": rpm} for name in config.rotor_names
        ],
    }


def openfoam_job_inputs() -> dict[str, object]:
    """Manifest-port-shaped probe input for the governed MRF job path."""

    return {
        "inlet_velocity_m_s": 12.0,
        "outlet_pressure_pa": 0.0,
        "density_kg_m3": 1.225,
        "viscosity_pa_s": 1.81e-5,
        "rotation_rate_rpm": 35000.0,
    }


def structural_inputs() -> dict[str, object]:
    return {
        "analysis": "static",
        "youngs_modulus_pa": 70.0e9,
        "poisson_ratio": 0.33,
        "density_kg_m3": 1600.0,
        "applied_force_n": 18.0,
        "n_modes": 4,
        "mesh_file": "blade.med",
    }


def thermal_inputs(*, heat_load_w: float) -> dict[str, object]:
    return {
        "model": "thermal",
        "conductivity_w_m_k": 167.0,
        "heat_load_w": heat_load_w,
        "ambient_k": 288.15,
    }


def coupling_inputs() -> dict[str, object]:
    return {
        "participants": ["rotating-flow-mrf", "structural-static"],
        "coupling_dt_s": 1e-4,
        "max_iterations": 25,
        "tolerance": 1e-4,
    }


__all__ = [
    "ParticipantGraph",
    "battery_inputs",
    "cad_inputs",
    "coupling_inputs",
    "fidelity_ladders",
    "mesh_inputs",
    "openfoam_inputs",
    "openfoam_job_inputs",
    "participant_graph",
    "rotor_campbell_inputs",
    "rotor_modal_inputs",
    "structural_inputs",
    "thermal_inputs",
]
