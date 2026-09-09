import type { JobRequest } from "../../packages/solver-contracts/src/contracts.ts";

export interface EngineeringPolicy {
  readonly ownerId: string;
  readonly mutations: boolean;
  readonly destructive: boolean;
  readonly remoteCompute: boolean;
  readonly remoteCostCeilingUsd: number;
}

const parseSwitch = (name: string): boolean => process.env[name] === "1";

export const policyFromEnvironment = (): EngineeringPolicy => {
  const remoteCostCeilingUsd = Number(process.env.AERO_REMOTE_COST_CEILING_USD ?? "0");
  if (!Number.isFinite(remoteCostCeilingUsd) || remoteCostCeilingUsd < 0) throw new Error("INVALID_REMOTE_COST_CEILING");
  return {
    ownerId: process.env.AERO_OWNER_ID?.trim() || "local-operator",
    mutations: parseSwitch("AERO_ALLOW_MUTATIONS"),
    destructive: parseSwitch("AERO_ALLOW_DESTRUCTIVE"),
    remoteCompute: parseSwitch("AERO_ALLOW_REMOTE_COMPUTE"),
    remoteCostCeilingUsd,
  };
};

export const assertIdentifier = (value: unknown, field: string): string => {
  if (typeof value !== "string" || !/^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/.test(value)) throw new Error(`INVALID_${field.toUpperCase()}`);
  return value;
};

export const assertBoundedMemory = (value: unknown): number => {
  if (typeof value !== "number" || !Number.isFinite(value) || value <= 0 || value > 896) throw new Error("INVALID_RSS_RESERVATION");
  return value;
};

export const assertCost = (value: unknown): number => {
  if (typeof value !== "number" || !Number.isFinite(value) || value < 0) throw new Error("INVALID_COST_CEILING");
  return value;
};

export const assertOwnedJob = (job: JobRequest, ownerId: string): void => {
  if (job.ownerId !== ownerId) throw new Error("JOB_NOT_OWNED");
};
