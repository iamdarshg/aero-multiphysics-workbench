import type { SolverId } from "./contracts.ts";

/** Input accepted by a manifest-specific native command builder. */
export interface SolverLaunchInput {
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

/** @internal Manifest implementation hook; callers must use buildSolverCommand. */
export const createTrustedNativeCommand = (
  solverId: SolverId,
  executable: string,
  args: readonly string[],
): NativeSolverCommand => {
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
