import type { SolverId } from "./contracts.ts";

const manifestExecutables: Readonly<Record<SolverId, readonly string[]>> = Object.freeze({
  openfoam: ["simpleFoam", "pimpleFoam", "rhoSimpleFoam", "rhoPimpleFoam"],
  "code-aster": ["as_run"], precice: ["precice-config-visualizer"], ross: ["ross"], pybamm: ["pybamm"],
  elmer: ["ElmerSolver"], cantera: ["cantera"], pycycle: ["pycycle"], cadquery: ["cadquery"], gmsh: ["gmsh"],
  openvsp: ["vsp"], freecad: ["FreeCADCmd"],
});

const isOpaqueCaseId = (value: string): boolean =>
  /^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/.test(value) && value !== "." && value !== "..";

/** Input accepted by a manifest-specific native command builder. */
export interface SolverLaunchInput {
  /** Opaque relative case identifier, resolved beneath the approved job root. */
  readonly caseDirectory: string;
}

/** Opaque command produced by a trusted manifest builder. */
export interface NativeSolverCommand {
  readonly solverId: SolverId;
  readonly executable: string;
  readonly args: readonly string[];
  readonly __trustedNativeCommand: true;
}

const trustedCommands = new WeakSet<object>();

/** @internal Manifest implementation hook; immutable registry validation prevents arbitrary minting. */
export const createTrustedNativeCommand = (
  solverId: SolverId,
  executable: string,
  args: readonly string[],
): NativeSolverCommand => {
  const allowed = manifestExecutables[solverId] ?? [];
  if (!allowed.includes(executable) || args.length !== 2 || args[0] !== "-case" || typeof args[1] !== "string" || !isOpaqueCaseId(args[1])) {
    throw new Error(`COMMAND_NOT_ALLOWLISTED: ${solverId}`);
  }
  const command: NativeSolverCommand = Object.freeze({
    solverId,
    executable,
    args: Object.freeze([...args]),
    __trustedNativeCommand: true,
  });
  trustedCommands.add(command);
  return command;
};

export const isTrustedNativeCommand = (value: unknown): value is NativeSolverCommand =>
  typeof value === "object" && value !== null && trustedCommands.has(value) &&
  (value as NativeSolverCommand).__trustedNativeCommand === true;
