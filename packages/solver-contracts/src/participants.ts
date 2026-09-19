import type { SolverId } from "./contracts.ts";
import type { CheckpointMode } from "./executors.ts";

/** One typed scalar or field port with units and direction. */
export interface ParticipantPort {
  readonly name: string;
  readonly kind: "scalar" | "field";
  readonly dataType: "float" | "int" | "string" | "boolean";
  readonly unit: string;
  readonly direction: "in" | "out";
}

/**
 * The architecture's per-physics-role declaration. A ParticipantManifest is
 * not a SolverManifest: one native executable may service several
 * participant types, and the manifest chooses the executable, never the
 * caller. Function hooks are registry-relative references, never commands.
 */
export interface ParticipantManifest {
  readonly participantId: string;
  readonly physicsDomain: string;
  readonly manifestVersion: "2";
  readonly description: string;
  readonly inputs: readonly ParticipantPort[];
  readonly outputs: readonly ParticipantPort[];
  readonly geometryRoles: readonly string[];
  readonly meshRoles: readonly string[];
  readonly semanticRequirements: readonly string[];
  readonly couplingDirection: "none" | "one-way" | "two-way";
  readonly convergenceMeasures: readonly string[];
  readonly fidelityLevels: readonly string[];
  readonly solverId: SolverId;
  readonly executionMode: "subprocess" | "in-process";
  readonly prepareRef: string;
  readonly parserRef: string;
  readonly validityRef: string;
  readonly artifactOutputs: readonly string[];
  readonly checkpoint: boolean;
  /** Explicit checkpoint behavior: unsupported | periodic | solver-window | time-step | external. */
  readonly checkpointPolicy: CheckpointMode;
  readonly benchmarkRef: string;
}

const scalar = (name: string, unit: string, direction: "in" | "out"): ParticipantPort =>
  ({ name, kind: "scalar", dataType: "float", unit, direction });

const field = (name: string, unit: string, direction: "in" | "out"): ParticipantPort =>
  ({ name, kind: "field", dataType: "float", unit, direction });

const manifest = (
  participantId: string,
  physicsDomain: string,
  description: string,
  solverId: SolverId,
  executionMode: "subprocess" | "in-process",
  refs: readonly [string, string, string],
  artifactOutputs: readonly string[],
  fidelityLevels: readonly string[],
  benchmarkRef: string,
  inputs: readonly ParticipantPort[],
  outputs: readonly ParticipantPort[],
): ParticipantManifest => Object.freeze({
  participantId,
  physicsDomain,
  manifestVersion: "2" as const,
  description,
  inputs: Object.freeze([...inputs]),
  outputs: Object.freeze([...outputs]),
  geometryRoles: Object.freeze([]),
  meshRoles: Object.freeze([]),
  semanticRequirements: Object.freeze([]),
  couplingDirection: "none" as const,
  convergenceMeasures: Object.freeze(["residual"]),
  fidelityLevels: Object.freeze([...fidelityLevels]),
  solverId,
  executionMode,
  prepareRef: refs[0],
  parserRef: refs[1],
  validityRef: refs[2],
  artifactOutputs: Object.freeze([...artifactOutputs]),
  checkpoint: true,
  checkpointPolicy: "periodic" as const,
  benchmarkRef,
});

const FLOW_IN: readonly ParticipantPort[] = [
  scalar("inlet_velocity_m_s", "m/s", "in"),
  scalar("outlet_pressure_pa", "Pa", "in"),
  scalar("density_kg_m3", "kg/m3", "in"),
  scalar("viscosity_pa_s", "Pa.s", "in"),
];
const FLOW_OUT: readonly ParticipantPort[] = [
  scalar("pressure_drop_pa", "Pa", "out"),
  scalar("continuity_error", "dimensionless", "out"),
];
const CELL_IO: readonly ParticipantPort[] = [
  scalar("discharge_current_a", "A", "in"),
  scalar("duration_s", "s", "in"),
  scalar("n_series", "dimensionless", "in"),
  scalar("n_parallel", "dimensionless", "in"),
];
const CELL_OUT: readonly ParticipantPort[] = [
  scalar("voltage_start_v", "V", "out"),
  scalar("voltage_end_v", "V", "out"),
  scalar("delivered_ah", "A.h", "out"),
  scalar("soc_end", "dimensionless", "out"),
];

/** Every executable physics role; mirrors the Python participant registry. */
export const PARTICIPANT_MANIFESTS: readonly ParticipantManifest[] = Object.freeze([
  manifest("incompressible-steady-flow", "fluid", "Generic incompressible steady RANS flow.", "openfoam", "subprocess",
    ["openfoam.case:prepare_case_files", "openfoam.case:parse_case_result", "openfoam.case:validate_case_result"],
    ["controlDict", "result.json", "solver.log"], ["rans-steady"], "pending-native-binary", FLOW_IN, FLOW_OUT),
  manifest("compressible-steady-flow", "fluid", "Generic compressible steady flow.", "openfoam", "subprocess",
    ["openfoam.case:prepare_case_files", "openfoam.case:parse_case_result", "openfoam.case:validate_case_result"],
    ["controlDict", "result.json", "solver.log"], ["rans-steady-compressible"], "pending-native-binary", FLOW_IN, FLOW_OUT),
  manifest("rotating-flow-mrf", "fluid", "Generic steady flow with a rotating frame zone.", "openfoam", "subprocess",
    ["openfoam.case:prepare_case_files", "openfoam.case:parse_case_result", "openfoam.case:validate_case_result"],
    ["controlDict", "result.json", "solver.log"], ["mrf-steady"], "pending-native-binary", FLOW_IN, FLOW_OUT),
  manifest("structural-static", "structural", "Generic linear static analysis.", "code-aster", "subprocess",
    ["code_aster.comm:prepare_comm", "code_aster.comm:parse_comm_result", "code_aster.comm:validate_comm_result"],
    ["case.comm", "result.json", "solver.log"], ["linear-static"], "pending-native-binary",
    [scalar("youngs_modulus_pa", "Pa", "in"), scalar("applied_force_n", "N", "in")],
    [scalar("max_displacement_m", "m", "out"), scalar("max_von_mises_pa", "Pa", "out")]),
  manifest("structural-modal", "structural", "Generic modal analysis, optionally prestressed.", "code-aster", "subprocess",
    ["code_aster.comm:prepare_comm", "code_aster.comm:parse_comm_result", "code_aster.comm:validate_comm_result"],
    ["case.comm", "result.json", "solver.log"], ["modal", "prestressed-modal"], "pending-native-binary",
    [scalar("youngs_modulus_pa", "Pa", "in"), scalar("density_kg_m3", "kg/m3", "in")],
    [scalar("first_frequency_hz", "Hz", "out"), field("mode_shape", "dimensionless", "out")]),
  manifest("rotor-campbell", "rotordynamics", "Generic rotor Campbell and critical speeds.", "ross", "subprocess",
    ["ross.rotor:prepare_rotor_case", "ross.rotor:parse_rotor_result", "ross.rotor:validate_rotor_result"],
    ["case.json", "run_ross.py", "result.json", "solver.log"], ["beam-campbell"], "milestone-2:rotor-campbell",
    [scalar("shaft_length_m", "m", "in"), scalar("shaft_diameter_m", "m", "in"), scalar("max_speed_rpm", "rpm", "in")],
    [scalar("first_critical_rpm", "rpm", "out"), scalar("second_critical_rpm", "rpm", "out")]),
  manifest("rotor-modal", "rotordynamics", "Generic damped rotor modal analysis.", "ross", "subprocess",
    ["ross.rotor:prepare_rotor_case", "ross.rotor:parse_rotor_result", "ross.rotor:validate_rotor_result"],
    ["case.json", "run_ross.py", "result.json", "solver.log"], ["beam-modal"], "milestone-2:rotor-modal",
    [scalar("shaft_length_m", "m", "in"), scalar("speed_rpm", "rpm", "in")],
    [scalar("first_whirl_hz", "Hz", "out"), scalar("first_damping_ratio", "dimensionless", "out")]),
  manifest("cell-spm-discharge", "electrochemical", "Generic SPM cell discharge.", "pybamm", "subprocess",
    ["pybamm.cell:prepare_cell_case", "pybamm.cell:parse_cell_result", "pybamm.cell:validate_cell_result"],
    ["case.json", "run_pybamm.py", "result.json", "solver.log"], ["spm"], "milestone-2:cell-spm", CELL_IO, CELL_OUT),
  manifest("cell-spme-discharge", "electrochemical", "Generic SPMe cell discharge.", "pybamm", "subprocess",
    ["pybamm.cell:prepare_cell_case", "pybamm.cell:parse_cell_result", "pybamm.cell:validate_cell_result"],
    ["case.json", "run_pybamm.py", "result.json", "solver.log"], ["spme"], "milestone-2:cell-spme", CELL_IO, CELL_OUT),
  manifest("pack-thevenin-discharge", "electrochemical", "Generic Thevenin pack discharge.", "pybamm", "subprocess",
    ["pybamm.cell:prepare_cell_case", "pybamm.cell:parse_cell_result", "pybamm.cell:validate_cell_result"],
    ["case.json", "run_pybamm.py", "result.json", "solver.log"], ["ecm-thevenin"], "milestone-2:pack-ecm", CELL_IO, CELL_OUT),
  manifest("thermal-conduction", "thermal", "Generic steady heat conduction.", "elmer", "subprocess",
    ["elmer.sif:prepare_sif", "elmer.sif:parse_sif_result", "elmer.sif:validate_sif_result"],
    ["case.sif", "result.json", "solver.log"], ["steady-conduction"], "pending-native-binary",
    [scalar("conductivity_w_m_k", "W/m.K", "in"), scalar("heat_load_w", "W", "in")],
    [scalar("max_temperature_k", "K", "out"), scalar("min_temperature_k", "K", "out")]),
  manifest("electrostatic-field", "electromagnetic", "Generic electrostatic potential field.", "elmer", "subprocess",
    ["elmer.sif:prepare_sif", "elmer.sif:parse_sif_result", "elmer.sif:validate_sif_result"],
    ["case.sif", "result.json", "solver.log"], ["electrostatic"], "pending-native-binary",
    [scalar("permittivity", "dimensionless", "in"), scalar("voltage_v", "V", "in")],
    [scalar("max_potential_v", "V", "out"), scalar("potential_span_v", "V", "out")]),
  manifest("coupled-interface-validation", "coupled", "Generic preCICE interface validation.", "precice", "subprocess",
    ["precice.validate:prepare_coupling_case", "precice.validate:parse_coupling_result", "precice.validate:validate_coupling_result"],
    ["precice-config.xml", "result.json", "solver.log"], ["implicit-iqn"], "pending-native-binary",
    [scalar("coupling_dt_s", "s", "in"), scalar("tolerance", "dimensionless", "in")],
    [scalar("conservation_error", "dimensionless", "out")]),
  manifest("domain-mesh", "mesh", "Generic conforming mesh via native Gmsh.", "gmsh", "in-process",
    ["participants.mesh_case:prepare_mesh_case", "participants.mesh_case:parse_mesh_result", "participants.mesh_case:validate_mesh_result"],
    ["case.json", "domain.msh", "result.json"], ["conforming-linear"], "milestone-2:domain-mesh",
    [scalar("base_size_mm", "mm", "in")],
    [scalar("element_count", "dimensionless", "out"), scalar("min_sicn", "dimensionless", "out")]),
  manifest("cad-interchange", "geometry", "Generic STEP/BREP interchange.", "freecad", "in-process",
    ["participants.cad_case:prepare_cad_case", "participants.cad_case:parse_cad_result", "participants.cad_case:validate_cad_result"],
    ["case.json", "product.step", "result.json"], ["brep-roundtrip"], "milestone-2:cad-interchange",
    [scalar("n_rotating", "dimensionless", "in")],
    [scalar("faces_before", "dimensionless", "out"), scalar("faces_after", "dimensionless", "out")]),
]);

export const findParticipant = (participantId: string): ParticipantManifest => {
  const found = PARTICIPANT_MANIFESTS.find((manifest) => manifest.participantId === participantId);
  if (!found) throw new Error(`UNKNOWN_PARTICIPANT:${participantId}`);
  return found;
};

export const participantsForSolver = (solverId: SolverId): readonly ParticipantManifest[] =>
  PARTICIPANT_MANIFESTS.filter((manifest) => manifest.solverId === solverId);
