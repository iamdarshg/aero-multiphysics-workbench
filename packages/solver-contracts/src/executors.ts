/**
 * Provider-neutral governed executor + checkpoint contracts (INFRA-FIX 03/04).
 *
 * The scheduler routes an approved job local or remote through one logical
 * lifecycle; only the transport differs. Participant code never sees cloud
 * details. Remote work is impossible unless a user-owned policy enables it,
 * and the policy limits are immutable for the lifetime of a session.
 */

export type CheckpointMode =
  | "unsupported"
  | "periodic"
  | "solver-window"
  | "time-step"
  | "external";

export type ExecutorKind = "local" | "remote";

export interface RemoteLimits {
  readonly maxVcpu: number;
  readonly maxMemoryMiB: number;
  readonly maxConcurrency: number;
  readonly maxWallTimeS: number;
  readonly maxJobCostUsd: number;
  readonly maxSessionCostUsd: number;
  readonly maxProjectCostUsd: number;
  readonly allowedRegions: readonly string[];
  readonly allowedProjects: readonly string[];
  readonly allowedImageDigests: readonly string[];
}

export interface RemoteComputePolicy {
  readonly enabled: boolean;
  readonly limits: RemoteLimits;
}

export interface RemoteResourceRequest {
  readonly vcpu: number;
  readonly memoryMiB: number;
  readonly wallTimeS: number;
  readonly machineType: string;
}

export interface ExecutionPlan {
  readonly jobId: string;
  readonly participantId: string;
  readonly solverId: string;
  readonly solverVersion: string;
  readonly executionMode: "subprocess" | "in-process" | "remote";
  readonly caseId: string;
  readonly inputHash: string;
  readonly artifacts: readonly string[];
  readonly resource?: RemoteResourceRequest;
  readonly imageDigest?: string;
  readonly region?: string;
  readonly project?: string;
  readonly checkpointId?: string;
  readonly resumeOf?: string;
  readonly attempt: number;
}

export interface ArtifactDigest {
  readonly name: string;
  readonly sha256: string;
  readonly bytes: number;
}

export type ExecutionState = "completed" | "failed" | "cancelled" | "preempted";

export interface ExecutionReceipt {
  readonly state: ExecutionState;
  readonly executionMode: "subprocess" | "in-process" | "remote";
  readonly exitCode: number | null;
  readonly reason?: string;
  readonly stdoutSha256?: string;
  readonly stderrSha256?: string;
  readonly artifacts: readonly ArtifactDigest[];
  readonly inputHash?: string;
  readonly solverIdentity?: string;
  readonly imageDigest?: string;
  readonly estimatedCostUsd: number;
  readonly actualCostUsd?: number;
  readonly preempted: boolean;
  readonly interruptionReason?: string;
  readonly checkpointId?: string;
  readonly evidenceVerified: boolean;
}

export interface CheckpointArtifact {
  readonly name: string;
  readonly sha256: string;
  readonly bytes: number;
}

export interface CheckpointReceipt {
  readonly checkpointId: string;
  readonly jobId: string;
  readonly runId: string;
  readonly participantId: string;
  readonly solverId: string;
  readonly solverVersion: string;
  readonly inputHash: string;
  readonly geometryHash?: string;
  readonly meshHash?: string;
  readonly sequence: number;
  readonly createdAt: string;
  readonly artifacts: readonly CheckpointArtifact[];
  readonly imageDigest?: string;
  readonly resumeOf?: string;
}

/** The single transport contract behind the scheduler. */
export interface RemoteExecutor {
  readonly name: string;
  submit(plan: ExecutionPlan): string;
  poll(ref: string): ExecutionState | "running";
  cancel(ref: string): void;
  fetchStdout(ref: string): Promise<Uint8Array>;
  fetchStderr(ref: string): Promise<Uint8Array>;
  fetchArtifacts(ref: string): Promise<ReadonlyMap<string, Uint8Array>>;
  terminalReceipt(ref: string): ExecutionReceipt;
}

/**
 * Fail-closed authorization. A disabled or unpriced remote request is refused
 * with a stable code; it never falls back to local execution.
 */
export const requireRemoteAuthorized = (policy: RemoteComputePolicy): void => {
  if (!policy.enabled) throw new Error("REMOTE_COMPUTE_NOT_AUTHORIZED");
};

export const assertWithinRemoteLimits = (
  policy: RemoteComputePolicy,
  request: RemoteResourceRequest,
): void => {
  if (request.vcpu > policy.limits.maxVcpu) throw new Error("REMOTE_COMPUTE_NOT_AUTHORIZED");
  if (request.memoryMiB > policy.limits.maxMemoryMiB) {
    throw new Error("REMOTE_COMPUTE_NOT_AUTHORIZED");
  }
  if (request.wallTimeS > policy.limits.maxWallTimeS) {
    throw new Error("REMOTE_COMPUTE_NOT_AUTHORIZED");
  }
};

export type RetryClass =
  | "infrastructure-transient"
  | "solver-divergence"
  | "invalid-input"
  | "user-cancellation"
  | "budget-exhaustion";

export interface RetryPolicy {
  readonly maxAttempts: number;
  readonly autoResumeClasses: readonly RetryClass[];
}

export const mayAutoResume = (
  policy: RetryPolicy,
  retryClass: RetryClass,
  attempt: number,
): boolean =>
  attempt < policy.maxAttempts && policy.autoResumeClasses.includes(retryClass);
