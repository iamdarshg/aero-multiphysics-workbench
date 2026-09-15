import type { JobRequest } from "../../packages/solver-contracts/src/contracts.ts";

export interface EngineeringPolicy {
  readonly ownerId: string;
  readonly mutations: boolean;
  readonly destructive: boolean;
  readonly remoteCompute: boolean;
  readonly remoteCostCeilingUsd: number;
  readonly apiBaseUrl: string;
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
    apiBaseUrl: resolveApiBaseUrl(),
  };
};

/**
 * The MCP server is a thin client of the local product API only. It must
 * never reach a remote/cloud endpoint on its own, so only loopback http(s)
 * targets are accepted here.
 */
export const resolveApiBaseUrl = (): string => {
  const raw = process.env.AERO_API_BASE_URL?.trim() || "http://localhost:8000";
  let parsed: URL;
  try {
    parsed = new URL(raw);
  } catch {
    throw new Error(`INVALID_API_BASE_URL:${raw.slice(0, 80)}`);
  }
  if ((parsed.protocol !== "http:" && parsed.protocol !== "https:") || !parsed.hostname) {
    throw new Error(`INVALID_API_BASE_URL:${raw.slice(0, 80)}`);
  }
  const host = parsed.hostname.toLowerCase();
  if (host !== "localhost" && host !== "127.0.0.1" && host !== "::1") {
    throw new Error(`INVALID_API_BASE_URL:${raw.slice(0, 80)}`);
  }
  return `${parsed.protocol}//${parsed.host}`;
};

/**
 * Bounded identifier predicate shared by every MCP tool schema. It admits
 * only opaque product ids (letters, digits, and . _ : -) and therefore
 * rejects absolute paths, parent traversal, shell metacharacters, command
 * separators, and whitespace by construction.
 */
export const isSafeToken = (value: unknown): value is string => {
  if (typeof value !== "string" || value.length < 1 || value.length > 128) return false;
  if (!/^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/.test(value)) return false;
  if (value.includes("..")) return false;
  return true;
};

export const assertSafeToken = (value: unknown, field: string): string => {
  if (!isSafeToken(value)) throw new Error(`UNSAFE_${field.toUpperCase()}`);
  return value;
};

/**
 * String values inside bounded input maps use the same token discipline plus
 * an explicit command/path probe so a hostile payload is rejected with a
 * stable code even if a schema is widened later.
 */
export const isSafeInputValue = (value: unknown): boolean => {
  if (typeof value === "number") return Number.isFinite(value);
  if (typeof value === "boolean") return true;
  if (typeof value !== "string" || value.length > 256) return false;
  if (value.includes("..") || /[\\/;|&$`'"!*?<>#(){}\[\]\n\r\u0000]/.test(value)) return false;
  return true;
};

/**
 * Structural remote-compute gate: no MCP tool accepts a remote flag, so any
 * present remote-like field is an escalation attempt and is rejected rather
 * than forwarded. MCP can never enable remote compute by itself.
 */
export const rejectRemoteEscalation = (input: Record<string, unknown>): void => {
  if ("remote" in input || "remoteCompute" in input || "allowRemote" in input) {
    throw new Error("REMOTE_COMPUTE_NOT_AUTHORIZED");
  }
};

/**
 * Structural cost gate: no MCP tool accepts a cost ceiling, so any present
 * cost-like field is an escalation attempt and is rejected rather than
 * forwarded. MCP can never raise cost limits by itself.
 */
export const rejectCostEscalation = (input: Record<string, unknown>): void => {
  if ("costCeilingUsd" in input || "costCeiling" in input || "budgetUsd" in input) {
    throw new Error("REMOTE_COST_BUDGET_EXCEEDED");
  }
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

/**
 * Ownership gate for API-backed cancellation. The API status payload carries
 * the recorded owner; a missing, empty, or mismatched owner fails closed so
 * MCP can only cancel jobs owned by its configured operator.
 */
export const assertOwnedJobStatus = (status: Record<string, unknown>, ownerId: string): void => {
  if (typeof status.owner_id !== "string" || status.owner_id.length === 0 || status.owner_id !== ownerId) {
    throw new Error("JOB_NOT_OWNED");
  }
};
