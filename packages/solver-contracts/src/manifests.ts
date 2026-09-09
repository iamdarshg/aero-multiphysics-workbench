import type { SolverManifest } from "./contracts.ts";

const native = (id: SolverManifest["id"], displayName: string, category: SolverManifest["category"], command: string, allowedExecutables: readonly string[], resultKinds: SolverManifest["resultKinds"]): SolverManifest => ({
  id, displayName, category, versionProbe: { command: [command, "--version"] }, resultKinds,
  allowedExecutables,
  execution: { trustModel: "native-only", checkpoint: true },
});

/** Registry contains only executable, version-probed native integrations. */
export const CAPABILITY_MANIFESTS: readonly SolverManifest[] = [
  native("openfoam", "OpenFOAM", "solver", "foamVersion", ["simpleFoam", "pimpleFoam", "rhoSimpleFoam", "rhoPimpleFoam"], ["fields", "scalars"]),
  native("code-aster", "Code_Aster", "solver", "as_run", ["as_run"], ["fields", "scalars"]),
  native("precice", "preCICE", "coupling", "precice-config-visualizer", ["precice-config-visualizer"], ["coupling", "report"]),
  native("ross", "ROSS", "solver", "ross", ["ross"], ["scalars", "report"]),
  native("pybamm", "PyBaMM", "solver", "pybamm", ["pybamm"], ["scalars", "report"]),
  native("elmer", "Elmer", "solver", "ElmerSolver", ["ElmerSolver"], ["fields", "scalars"]),
  native("cantera", "Cantera", "solver", "cantera", ["cantera"], ["scalars", "report"]),
  native("pycycle", "pyCycle", "solver", "pycycle", ["pycycle"], ["scalars", "report"]),
  native("cadquery", "CadQuery", "geometry", "cadquery", ["cadquery"], ["geometry"]),
  native("gmsh", "Gmsh", "geometry", "gmsh", ["gmsh"], ["mesh", "geometry"]),
  native("openvsp", "OpenVSP", "geometry", "vsp", ["vsp"], ["geometry", "mesh"]),
  native("freecad", "FreeCAD", "geometry", "FreeCADCmd", ["FreeCADCmd"], ["geometry", "mesh"]),
];
