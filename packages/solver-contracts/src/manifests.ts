import type { SolverManifest } from "./contracts.ts";

const native = (id: SolverManifest["id"], displayName: string, category: SolverManifest["category"], command: string, resultKinds: SolverManifest["resultKinds"]): SolverManifest => ({
  id, displayName, category, versionProbe: { command: [command, "--version"] }, resultKinds,
  execution: { trustModel: "native-only", checkpoint: true },
});

/** Registry contains only executable, version-probed native integrations. */
export const CAPABILITY_MANIFESTS: readonly SolverManifest[] = [
  native("openfoam", "OpenFOAM", "solver", "foamVersion", ["fields", "scalars"]),
  native("code-aster", "Code_Aster", "solver", "as_run", ["fields", "scalars"]),
  native("precice", "preCICE", "coupling", "precice-config-visualizer", ["coupling", "report"]),
  native("ross", "ROSS", "solver", "ross", ["scalars", "report"]),
  native("pybamm", "PyBaMM", "solver", "pybamm", ["scalars", "report"]),
  native("elmer", "Elmer", "solver", "ElmerSolver", ["fields", "scalars"]),
  native("cantera", "Cantera", "solver", "cantera", ["scalars", "report"]),
  native("pycycle", "pyCycle", "solver", "pycycle", ["scalars", "report"]),
  native("cadquery", "CadQuery", "geometry", "cadquery", ["geometry"]),
  native("gmsh", "Gmsh", "geometry", "gmsh", ["mesh", "geometry"]),
  native("openvsp", "OpenVSP", "geometry", "vsp", ["geometry", "mesh"]),
  native("freecad", "FreeCAD", "geometry", "FreeCADCmd", ["geometry", "mesh"]),
];
