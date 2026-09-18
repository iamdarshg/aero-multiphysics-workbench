"""ParticipantManifest contract: the architecture's per-physics-role declaration.

A ParticipantManifest is NOT a SolverManifest. A SolverManifest binds one
native executable plus its version probe; a ParticipantManifest declares one
executable physics role (typed I/O, units, geometry/mesh roles, semantic
requirements, ports, coupling direction, convergence measures, fidelity
levels) together with the functions that prepare, launch, parse, and validate
it. One native executable may service several participant types.
"""

from __future__ import annotations

from dataclasses import dataclass

MANIFEST_VERSION = "2"

_VALID_ID = frozenset(
    "abcdefghijklmnopqrstuvwxyz0123456789-"
)


def _check_id(label: str, value: str) -> None:
    if not value or any(character not in _VALID_ID for character in value):
        raise ValueError(f"INVALID_PARTICIPANT_ID:{label}:{value}")


@dataclass(frozen=True, slots=True)
class PortSpec:
    """One typed scalar or field port with units and direction."""

    name: str
    kind: str  # "scalar" | "field"
    data_type: str  # "float" | "int" | "string" | "bool"
    unit: str  # SI unit label or "dimensionless"
    direction: str  # "in" | "out"

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("PORT_NAME_REQUIRED")
        if self.kind not in {"scalar", "field"}:
            raise ValueError(f"INVALID_PORT_KIND:{self.name}")
        if self.data_type not in {"float", "int", "string", "bool"}:
            raise ValueError(f"INVALID_PORT_TYPE:{self.name}")
        if not self.unit.strip():
            raise ValueError(f"PORT_UNIT_REQUIRED:{self.name}")
        if self.direction not in {"in", "out"}:
            raise ValueError(f"INVALID_PORT_DIRECTION:{self.name}")


@dataclass(frozen=True, slots=True)
class ExecutableCapability:
    """The allowlisted executable backing a participant."""

    solver_id: str
    executables: tuple[str, ...]
    execution_mode: str  # "subprocess" | "in-process"
    run_script: str | None = None

    def __post_init__(self) -> None:
        if not self.solver_id.strip():
            raise ValueError("EXECUTABLE_SOLVER_REQUIRED")
        if not self.executables or any(
            not item.strip() for item in self.executables
        ):
            raise ValueError("EXECUTABLE_ALLOWLIST_REQUIRED")
        if self.execution_mode not in {"subprocess", "in-process"}:
            raise ValueError("INVALID_EXECUTION_MODE")
        if self.execution_mode == "in-process" and self.run_script is not None:
            raise ValueError("IN_PROCESS_NEEDS_NO_RUN_SCRIPT")


@dataclass(frozen=True, slots=True)
class ParticipantManifest:
    """Complete declaration of one executable physics participant."""

    participant_id: str
    physics_domain: str
    manifest_version: str
    description: str
    inputs: tuple[PortSpec, ...]
    outputs: tuple[PortSpec, ...]
    geometry_roles: tuple[str, ...]
    mesh_roles: tuple[str, ...]
    semantic_requirements: tuple[str, ...]
    coupling_direction: str  # "none" | "one-way" | "two-way"
    convergence_measures: tuple[str, ...]
    fidelity_levels: tuple[str, ...]
    executable: ExecutableCapability
    prepare_ref: str
    execute_ref: str | None
    parser_ref: str
    validity_ref: str
    artifacts: tuple[str, ...]
    checkpoint: bool
    benchmark_ref: str

    def __post_init__(self) -> None:
        _check_id("participant", self.participant_id)
        if not self.physics_domain.strip():
            raise ValueError("PHYSICS_DOMAIN_REQUIRED")
        if self.manifest_version != MANIFEST_VERSION:
            raise ValueError("STALE_PARTICIPANT_MANIFEST")
        if not self.description.strip():
            raise ValueError("PARTICIPANT_DESCRIPTION_REQUIRED")
        if not self.inputs or not self.outputs:
            raise ValueError("PARTICIPANT_NEEDS_TYPED_IO")
        in_names = {port.name for port in self.inputs if port.direction == "in"}
        out_names = {port.name for port in self.outputs if port.direction == "out"}
        if len(in_names) != len([p for p in self.inputs if p.direction == "in"]):
            raise ValueError("DUPLICATE_INPUT_PORT")
        if len(out_names) != len([p for p in self.outputs if p.direction == "out"]):
            raise ValueError("DUPLICATE_OUTPUT_PORT")
        if self.coupling_direction not in {"none", "one-way", "two-way"}:
            raise ValueError("INVALID_COUPLING_DIRECTION")
        if not self.fidelity_levels:
            raise ValueError("FIDELITY_LEVELS_REQUIRED")
        for ref in (self.prepare_ref, self.parser_ref, self.validity_ref):
            module, _, function = ref.partition(":")
            if not module or not function or "/" in module or "\\" in module:
                raise ValueError(f"INVALID_FUNCTION_REF:{ref}")
        if self.execute_ref is not None:
            module, _, function = self.execute_ref.partition(":")
            if not module or not function or "/" in module or "\\" in module:
                raise ValueError(f"INVALID_FUNCTION_REF:{self.execute_ref}")
        if (self.execute_ref is None) == (
            self.executable.execution_mode == "in-process"
        ):
            raise ValueError("EXECUTE_REF_MUST_MATCH_IN_PROCESS_MODE")
        if not self.artifacts:
            raise ValueError("ARTIFACT_OUTPUTS_REQUIRED")
        if not self.benchmark_ref.strip():
            raise ValueError("BENCHMARK_EVIDENCE_REQUIRED")

    @property
    def scalar_inputs(self) -> tuple[PortSpec, ...]:
        return tuple(port for port in self.inputs if port.kind == "scalar")

    @property
    def field_inputs(self) -> tuple[PortSpec, ...]:
        return tuple(port for port in self.inputs if port.kind == "field")

    @property
    def scalar_outputs(self) -> tuple[PortSpec, ...]:
        return tuple(port for port in self.outputs if port.kind == "scalar")

    @property
    def field_outputs(self) -> tuple[PortSpec, ...]:
        return tuple(port for port in self.outputs if port.kind == "field")


def _scalar(
    name: str, unit: str, direction: str, data_type: str = "float"
) -> PortSpec:
    return PortSpec(name, "scalar", data_type, unit, direction)


def _field(name: str, unit: str, direction: str) -> PortSpec:
    return PortSpec(name, "field", "float", unit, direction)


def _executable(
    solver_id: str,
    executables: tuple[str, ...],
    mode: str = "subprocess",
    run_script: str | None = None,
) -> ExecutableCapability:
    return ExecutableCapability(solver_id, executables, mode, run_script)


def _manifest(
    participant_id: str,
    physics_domain: str,
    description: str,
    inputs: tuple[PortSpec, ...],
    outputs: tuple[PortSpec, ...],
    executable: ExecutableCapability,
    prepare_ref: str,
    parser_ref: str,
    validity_ref: str,
    artifacts: tuple[str, ...],
    *,
    execute_ref: str | None = None,
    geometry_roles: tuple[str, ...] = (),
    mesh_roles: tuple[str, ...] = (),
    semantic_requirements: tuple[str, ...] = (),
    coupling_direction: str = "none",
    convergence_measures: tuple[str, ...] = ("residual",),
    fidelity_levels: tuple[str, ...] = ("baseline",),
    checkpoint: bool = True,
    benchmark_ref: str = "pending",
) -> ParticipantManifest:
    return ParticipantManifest(
        participant_id,
        physics_domain,
        MANIFEST_VERSION,
        description,
        inputs,
        outputs,
        geometry_roles,
        mesh_roles,
        semantic_requirements,
        coupling_direction,
        convergence_measures,
        fidelity_levels,
        executable,
        prepare_ref,
        execute_ref,
        parser_ref,
        validity_ref,
        artifacts,
        checkpoint,
        benchmark_ref,
    )


_FLOW_IO = (
    _scalar("inlet_velocity_m_s", "m/s", "in"),
    _scalar("outlet_pressure_pa", "Pa", "in"),
    _scalar("density_kg_m3", "kg/m3", "in"),
    _scalar("viscosity_pa_s", "Pa.s", "in"),
    _field("velocity", "m/s", "in"),
    _field("pressure", "Pa", "in"),
)
_FLOW_OUT = (
    _scalar("pressure_drop_pa", "Pa", "out"),
    _scalar("continuity_error", "dimensionless", "out"),
    _field("velocity", "m/s", "out"),
    _field("pressure", "Pa", "out"),
)

PARTICIPANT_MANIFESTS: tuple[ParticipantManifest, ...] = (
    _manifest(
        "incompressible-steady-flow",
        "fluid",
        "Generic incompressible steady RANS flow through a ducted domain.",
        _FLOW_IO,
        _FLOW_OUT,
        _executable("openfoam", ("simpleFoam", "pimpleFoam")),
        "openfoam.case:prepare_case_files",
        "openfoam.case:parse_case_result",
        "openfoam.case:validate_case_result",
        ("controlDict", "fvSchemes", "fvSolution", "result.json", "solver.log"),
        geometry_roles=("fluid_zone", "inlet", "outlet", "wall"),
        mesh_roles=("fluid",),
        semantic_requirements=("inlet", "outlet", "wall"),
        convergence_measures=("residual", "continuity"),
        fidelity_levels=("rans-steady",),
        benchmark_ref="pending-native-binary",
    ),
    _manifest(
        "compressible-steady-flow",
        "fluid",
        "Generic compressible steady flow with energy equation.",
        _FLOW_IO + (_scalar("inlet_temperature_k", "K", "in"),),
        _FLOW_OUT + (_scalar("outlet_temperature_k", "K", "out"),),
        _executable("openfoam", ("rhoSimpleFoam", "rhoPimpleFoam")),
        "openfoam.case:prepare_case_files",
        "openfoam.case:parse_case_result",
        "openfoam.case:validate_case_result",
        ("controlDict", "fvSchemes", "fvSolution", "result.json", "solver.log"),
        geometry_roles=("fluid_zone", "inlet", "outlet", "wall"),
        mesh_roles=("fluid",),
        semantic_requirements=("inlet", "outlet", "wall"),
        convergence_measures=("residual", "continuity", "energy"),
        fidelity_levels=("rans-steady-compressible",),
        benchmark_ref="pending-native-binary",
    ),
    _manifest(
        "rotating-flow-mrf",
        "fluid",
        "Generic steady flow with a rotating reference frame zone.",
        _FLOW_IO + (_scalar("rotation_rate_rpm", "rpm", "in"),),
        _FLOW_OUT + (_scalar("torque_n_m", "N.m", "out"),),
        _executable("openfoam", ("simpleFoam", "pimpleFoam")),
        "openfoam.case:prepare_case_files",
        "openfoam.case:parse_case_result",
        "openfoam.case:validate_case_result",
        ("controlDict", "fvSchemes", "fvSolution", "result.json", "solver.log"),
        geometry_roles=("fluid_zone", "rotating_region", "inlet", "outlet", "wall"),
        mesh_roles=("fluid",),
        semantic_requirements=("inlet", "outlet", "wall", "rotating_region"),
        coupling_direction="one-way",
        convergence_measures=("residual", "continuity", "torque"),
        fidelity_levels=("mrf-steady",),
        benchmark_ref="pending-native-binary",
    ),
    _manifest(
        "structural-static",
        "structural",
        "Generic linear static structural analysis of a solid domain.",
        (
            _scalar("youngs_modulus_pa", "Pa", "in"),
            _scalar("poisson_ratio", "dimensionless", "in"),
            _scalar("applied_force_n", "N", "in"),
            _field("fixed_constraint", "dimensionless", "in"),
        ),
        (
            _scalar("max_displacement_m", "m", "out"),
            _scalar("max_von_mises_pa", "Pa", "out"),
            _field("displacement", "m", "out"),
        ),
        _executable("code-aster", ("as_run",)),
        "code_aster.comm:prepare_comm",
        "code_aster.comm:parse_comm_result",
        "code_aster.comm:validate_comm_result",
        ("case.comm", "result.json", "solver.log"),
        geometry_roles=("solid_region",),
        mesh_roles=("solid",),
        semantic_requirements=("mechanical_constraint",),
        convergence_measures=("residual",),
        fidelity_levels=("linear-static",),
        benchmark_ref="pending-native-binary",
    ),
    _manifest(
        "structural-modal",
        "structural",
        "Generic modal analysis, optionally prestressed, of a solid domain.",
        (
            _scalar("youngs_modulus_pa", "Pa", "in"),
            _scalar("density_kg_m3", "kg/m3", "in"),
            _scalar("n_modes", "dimensionless", "in", "int"),
            _scalar("prestress", "dimensionless", "in", "bool"),
            _field("fixed_constraint", "dimensionless", "in"),
        ),
        (
            _scalar("first_frequency_hz", "Hz", "out"),
            _field("mode_shape", "dimensionless", "out"),
        ),
        _executable("code-aster", ("as_run",)),
        "code_aster.comm:prepare_comm",
        "code_aster.comm:parse_comm_result",
        "code_aster.comm:validate_comm_result",
        ("case.comm", "result.json", "solver.log"),
        geometry_roles=("solid_region",),
        mesh_roles=("solid",),
        semantic_requirements=("mechanical_constraint",),
        convergence_measures=("eigen_residual",),
        fidelity_levels=("modal", "prestressed-modal"),
        benchmark_ref="pending-native-binary",
    ),
    _manifest(
        "rotor-campbell",
        "rotordynamics",
        "Generic shaft/disk/bearing rotor Campbell and critical-speed analysis.",
        (
            _scalar("shaft_length_m", "m", "in"),
            _scalar("shaft_diameter_m", "m", "in"),
            _scalar("n_elements", "dimensionless", "in", "int"),
            _scalar("bearing_stiffness_n_m", "N/m", "in"),
            _scalar("max_speed_rpm", "rpm", "in"),
        ),
        (
            _scalar("first_critical_rpm", "rpm", "out"),
            _scalar("second_critical_rpm", "rpm", "out"),
        ),
        _executable("ross", ("python",), run_script="run_ross.py"),
        "ross.rotor:prepare_rotor_case",
        "ross.rotor:parse_rotor_result",
        "ross.rotor:validate_rotor_result",
        ("case.json", "run_ross.py", "result.json", "solver.log"),
        geometry_roles=("shaft",),
        mesh_roles=(),
        semantic_requirements=("shaft",),
        convergence_measures=("eigen_residual",),
        fidelity_levels=("beam-campbell",),
        benchmark_ref="milestone-2:rotor-campbell",
    ),
    _manifest(
        "rotor-modal",
        "rotordynamics",
        "Generic damped modal analysis of a shaft/disk/bearing rotor at speed.",
        (
            _scalar("shaft_length_m", "m", "in"),
            _scalar("shaft_diameter_m", "m", "in"),
            _scalar("n_elements", "dimensionless", "in", "int"),
            _scalar("bearing_stiffness_n_m", "N/m", "in"),
            _scalar("speed_rpm", "rpm", "in"),
        ),
        (
            _scalar("first_whirl_hz", "Hz", "out"),
            _scalar("first_damping_ratio", "dimensionless", "out"),
        ),
        _executable("ross", ("python",), run_script="run_ross.py"),
        "ross.rotor:prepare_rotor_case",
        "ross.rotor:parse_rotor_result",
        "ross.rotor:validate_rotor_result",
        ("case.json", "run_ross.py", "result.json", "solver.log"),
        geometry_roles=("shaft",),
        mesh_roles=(),
        semantic_requirements=("shaft",),
        convergence_measures=("eigen_residual",),
        fidelity_levels=("beam-modal",),
        benchmark_ref="milestone-2:rotor-modal",
    ),
    _manifest(
        "cell-spm-discharge",
        "electrochemical",
        "Generic single-particle-model galvanostatic discharge of one cell type.",
        (
            _scalar("discharge_current_a", "A", "in"),
            _scalar("duration_s", "s", "in"),
            _scalar("n_series", "dimensionless", "in", "int"),
            _scalar("n_parallel", "dimensionless", "in", "int"),
        ),
        (
            _scalar("voltage_start_v", "V", "out"),
            _scalar("voltage_end_v", "V", "out"),
            _scalar("delivered_ah", "A.h", "out"),
            _scalar("soc_end", "dimensionless", "out"),
        ),
        _executable("pybamm", ("python",), run_script="run_pybamm.py"),
        "pybamm.cell:prepare_cell_case",
        "pybamm.cell:parse_cell_result",
        "pybamm.cell:validate_cell_result",
        ("case.json", "run_pybamm.py", "result.json", "solver.log"),
        geometry_roles=(),
        mesh_roles=(),
        semantic_requirements=(),
        convergence_measures=("solver_residual",),
        fidelity_levels=("spm",),
        benchmark_ref="milestone-2:cell-spm",
    ),
    _manifest(
        "cell-spme-discharge",
        "electrochemical",
        "Generic single-particle-with-electrolyte discharge of one cell type.",
        (
            _scalar("discharge_current_a", "A", "in"),
            _scalar("duration_s", "s", "in"),
            _scalar("n_series", "dimensionless", "in", "int"),
            _scalar("n_parallel", "dimensionless", "in", "int"),
        ),
        (
            _scalar("voltage_start_v", "V", "out"),
            _scalar("voltage_end_v", "V", "out"),
            _scalar("delivered_ah", "A.h", "out"),
            _scalar("soc_end", "dimensionless", "out"),
        ),
        _executable("pybamm", ("python",), run_script="run_pybamm.py"),
        "pybamm.cell:prepare_cell_case",
        "pybamm.cell:parse_cell_result",
        "pybamm.cell:validate_cell_result",
        ("case.json", "run_pybamm.py", "result.json", "solver.log"),
        geometry_roles=(),
        mesh_roles=(),
        semantic_requirements=(),
        convergence_measures=("solver_residual",),
        fidelity_levels=("spme",),
        benchmark_ref="milestone-2:cell-spme",
    ),
    _manifest(
        "pack-thevenin-discharge",
        "electrochemical",
        "Generic equivalent-circuit discharge of an arbitrary series/parallel pack.",
        (
            _scalar("discharge_current_a", "A", "in"),
            _scalar("duration_s", "s", "in"),
            _scalar("n_series", "dimensionless", "in", "int"),
            _scalar("n_parallel", "dimensionless", "in", "int"),
        ),
        (
            _scalar("voltage_start_v", "V", "out"),
            _scalar("voltage_end_v", "V", "out"),
            _scalar("delivered_ah", "A.h", "out"),
            _scalar("soc_end", "dimensionless", "out"),
        ),
        _executable("pybamm", ("python",), run_script="run_pybamm.py"),
        "pybamm.cell:prepare_cell_case",
        "pybamm.cell:parse_cell_result",
        "pybamm.cell:validate_cell_result",
        ("case.json", "run_pybamm.py", "result.json", "solver.log"),
        geometry_roles=(),
        mesh_roles=(),
        semantic_requirements=(),
        convergence_measures=("solver_residual",),
        fidelity_levels=("ecm-thevenin",),
        benchmark_ref="milestone-2:pack-ecm",
    ),
    _manifest(
        "thermal-conduction",
        "thermal",
        "Generic steady heat conduction in a solid domain.",
        (
            _scalar("conductivity_w_m_k", "W/m.K", "in"),
            _scalar("heat_load_w", "W", "in"),
            _scalar("ambient_k", "K", "in"),
            _field("fixed_temperature", "K", "in"),
        ),
        (
            _scalar("max_temperature_k", "K", "out"),
            _scalar("min_temperature_k", "K", "out"),
            _field("temperature", "K", "out"),
        ),
        _executable("elmer", ("ElmerSolver",)),
        "elmer.sif:prepare_sif",
        "elmer.sif:parse_sif_result",
        "elmer.sif:validate_sif_result",
        ("case.sif", "result.json", "solver.log"),
        geometry_roles=("solid_region",),
        mesh_roles=("solid",),
        semantic_requirements=("thermal_constraint",),
        convergence_measures=("residual", "energy"),
        fidelity_levels=("steady-conduction",),
        benchmark_ref="pending-native-binary",
    ),
    _manifest(
        "electrostatic-field",
        "electromagnetic",
        "Generic electrostatic potential field in a dielectric domain.",
        (
            _scalar("permittivity", "dimensionless", "in"),
            _scalar("voltage_v", "V", "in"),
            _field("fixed_potential", "V", "in"),
        ),
        (
            _scalar("max_potential_v", "V", "out"),
            _scalar("potential_span_v", "V", "out"),
            _field("potential", "V", "out"),
        ),
        _executable("elmer", ("ElmerSolver",)),
        "elmer.sif:prepare_sif",
        "elmer.sif:parse_sif_result",
        "elmer.sif:validate_sif_result",
        ("case.sif", "result.json", "solver.log"),
        geometry_roles=("solid_region",),
        mesh_roles=("solid",),
        semantic_requirements=("electrical_constraint",),
        convergence_measures=("residual",),
        fidelity_levels=("electrostatic",),
        benchmark_ref="pending-native-binary",
    ),
    _manifest(
        "rotating-electrical-machine",
        "electromagnetic",
        "Generic rotating electrical machine with analytical, map, and native seams.",
        (
            _scalar("bus_voltage_v", "V", "in"),
            _scalar("commanded_speed_rpm", "rpm", "in"),
            _scalar("load_torque_n_m", "N.m", "in"),
            _scalar("winding_temp_k", "K", "in"),
            _scalar("magnet_temp_k", "K", "in"),
            _scalar("machine_parameter_revision", "dimensionless", "in", "string"),
        ),
        (
            _scalar("speed_rpm", "rpm", "out"),
            _scalar("torque_n_m", "N.m", "out"),
            _scalar("current_a", "A", "out"),
            _scalar("electrical_power_w", "W", "out"),
            _scalar("mechanical_power_w", "W", "out"),
            _scalar("copper_loss_w", "W", "out"),
            _scalar("core_loss_w", "W", "out"),
            _scalar("friction_loss_w", "W", "out"),
            _scalar("total_loss_w", "W", "out"),
            _scalar("efficiency", "dimensionless", "out"),
            _scalar("heat_load_winding_w", "W", "out"),
            _scalar("heat_load_core_w", "W", "out"),
            _scalar("heat_load_magnet_w", "W", "out"),
        ),
        _executable("aeroworkbench-electrical", ("python",), mode="in-process"),
        "electrical.machine:prepare_machine_case",
        "electrical.machine:parse_machine_result",
        "electrical.machine:validate_machine_result",
        ("case.json", "result.json"),
        execute_ref="electrical.machine:execute_machine_case",
        semantic_requirements=("winding", "magnet", "core"),
        coupling_direction="two-way",
        convergence_measures=("power_balance", "temperature_fixed_point"),
        fidelity_levels=("analytical", "reduced", "native"),
        benchmark_ref="gen09:rotating-electrical-machine",
    ),
    _manifest(
        "power-electronics-drive",
        "power-electronics",
        "Generic inverter/ESC with conduction loss, switching loss, and heat load.",
        (
            _scalar("dc_bus_voltage_v", "V", "in"),
            _scalar("output_power_w", "W", "in"),
            _scalar("switching_frequency_hz", "Hz", "in"),
            _scalar("modulation_index", "dimensionless", "in"),
            _scalar("case_temp_k", "K", "in"),
            _scalar("device_parameter_revision", "dimensionless", "in", "string"),
        ),
        (
            _scalar("motor_voltage_v", "V", "out"),
            _scalar("output_current_a", "A", "out"),
            _scalar("dc_current_a", "A", "out"),
            _scalar("dc_power_w", "W", "out"),
            _scalar("conduction_loss_w", "W", "out"),
            _scalar("switching_loss_w", "W", "out"),
            _scalar("total_loss_w", "W", "out"),
            _scalar("efficiency", "dimensionless", "out"),
            _scalar("junction_temp_k", "K", "out"),
            _scalar("heat_load_w", "W", "out"),
        ),
        _executable("aeroworkbench-electrical", ("python",), mode="in-process"),
        "electrical.power_electronics:prepare_inverter_case",
        "electrical.power_electronics:parse_inverter_result",
        "electrical.power_electronics:validate_inverter_result",
        ("case.json", "result.json"),
        execute_ref="electrical.power_electronics:execute_inverter_case",
        coupling_direction="two-way",
        convergence_measures=("power_balance", "thermal_fixed_point"),
        fidelity_levels=("analytical",),
        benchmark_ref="gen09:power-electronics-drive",
    ),
    _manifest(
        "coupled-interface-validation",
        "coupled",
        "Generic preCICE interface configuration validation for two participants.",
        (
            _scalar("coupling_dt_s", "s", "in"),
            _scalar("max_iterations", "dimensionless", "in", "int"),
            _scalar("tolerance", "dimensionless", "in"),
        ),
        (
            _scalar("conservation_error", "dimensionless", "out"),
            _scalar("config_digest_ok", "dimensionless", "out", "bool"),
        ),
        _executable("precice", ("precice-config-visualizer",)),
        "precice.validate:prepare_coupling_case",
        "precice.validate:parse_coupling_result",
        "precice.validate:validate_coupling_result",
        ("precice-config.xml", "result.json", "solver.log"),
        geometry_roles=(),
        mesh_roles=(),
        semantic_requirements=("fsi_interface",),
        coupling_direction="two-way",
        convergence_measures=("interface_residual", "conservation"),
        fidelity_levels=("implicit-iqn",),
        benchmark_ref="pending-native-binary",
    ),
    _manifest(
        "domain-mesh",
        "mesh",
        "Generic conforming mesh of a parametric ducted domain via native Gmsh.",
        (
            _scalar("base_size_mm", "mm", "in"),
            _scalar("n_rotating", "dimensionless", "in", "int"),
            _scalar("length_mm", "mm", "in"),
            _scalar("inner_diameter_mm", "mm", "in"),
            _scalar("outer_diameter_mm", "mm", "in"),
            _scalar("zone_length_mm", "mm", "in"),
            _scalar("zone_gap_mm", "mm", "in"),
        ),
        (
            _scalar("element_count", "dimensionless", "out", "int"),
            _scalar("min_sicn", "dimensionless", "out"),
        ),
        _executable("gmsh", ("gmsh",), mode="in-process"),
        "participants.mesh_case:prepare_mesh_case",
        "participants.mesh_case:parse_mesh_result",
        "participants.mesh_case:validate_mesh_result",
        ("case.json", "domain.msh", "result.json"),
        geometry_roles=("fluid_zone", "solid_region"),
        mesh_roles=("fluid", "solid"),
        semantic_requirements=("rotating_region",),
        convergence_measures=("quality",),
        fidelity_levels=("conforming-linear",),
        benchmark_ref="milestone-2:domain-mesh",
        execute_ref="participants.mesh_case:execute_mesh_case",
    ),
    _manifest(
        "cad-interchange",
        "geometry",
        "Generic STEP/BREP interchange through FreeCAD or the OCC fallback.",
        (
            _scalar("n_rotating", "dimensionless", "in", "int"),
            _scalar("source_format", "dimensionless", "in", "string"),
            _scalar("length_mm", "mm", "in"),
            _scalar("inner_diameter_mm", "mm", "in"),
            _scalar("outer_diameter_mm", "mm", "in"),
            _scalar("zone_length_mm", "mm", "in"),
            _scalar("zone_gap_mm", "mm", "in"),
        ),
        (
            _scalar("faces_before", "dimensionless", "out", "int"),
            _scalar("faces_after", "dimensionless", "out", "int"),
        ),
        _executable("freecad", ("FreeCADCmd", "ocp-fallback"), mode="in-process"),
        "participants.cad_case:prepare_cad_case",
        "participants.cad_case:parse_cad_result",
        "participants.cad_case:validate_cad_result",
        ("case.json", "product.step", "result.json"),
        geometry_roles=("solid_region",),
        mesh_roles=(),
        semantic_requirements=(),
        convergence_measures=("topology",),
        fidelity_levels=("brep-roundtrip",),
        benchmark_ref="milestone-2:cad-interchange",
        execute_ref="participants.cad_case:execute_cad_case",
    ),
)

_REGISTRY: dict[str, ParticipantManifest] = {
    manifest.participant_id: manifest for manifest in PARTICIPANT_MANIFESTS
}


def get_participant(participant_id: str) -> ParticipantManifest:
    try:
        return _REGISTRY[participant_id]
    except KeyError:
        raise ValueError(f"UNKNOWN_PARTICIPANT:{participant_id}") from None


def participants_for_solver(solver_id: str) -> tuple[ParticipantManifest, ...]:
    return tuple(
        manifest
        for manifest in PARTICIPANT_MANIFESTS
        if manifest.executable.solver_id == solver_id
    )


def participant_ids() -> tuple[str, ...]:
    return tuple(manifest.participant_id for manifest in PARTICIPANT_MANIFESTS)
