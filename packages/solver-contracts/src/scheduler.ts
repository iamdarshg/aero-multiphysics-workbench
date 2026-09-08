import type { JobRequest, ScheduledJob } from "./contracts.ts";

export interface SchedulerPolicy {
  readonly aggregateRssMiB?: number;
  readonly remoteComputeAuthorized?: boolean;
  readonly remainingRemoteBudgetUsd?: number;
}

/** Reservation scheduler: it neither starts processes nor calls a remote provider. */
export class LocalScheduler {
  private readonly jobs = new Map<string, ScheduledJob>();
  private readonly aggregateRssMiB: number;
  private readonly remoteComputeAuthorized: boolean;
  private remoteBudget: number;

  constructor(policy: SchedulerPolicy = {}) {
    this.aggregateRssMiB = policy.aggregateRssMiB ?? 1024;
    this.remoteComputeAuthorized = policy.remoteComputeAuthorized ?? false;
    this.remoteBudget = policy.remainingRemoteBudgetUsd ?? 0;
  }

  submit(request: JobRequest): ScheduledJob {
    if (!Number.isFinite(request.requestedMemoryMiB) || request.requestedMemoryMiB <= 0) throw new Error("INVALID_RSS_RESERVATION");
    if (!Number.isFinite(request.costCeilingUsd) || request.costCeilingUsd < 0) throw new Error("INVALID_COST_CEILING");
    if (this.jobs.has(request.id)) throw new Error("DUPLICATE_JOB_ID");
    if (request.remote && !this.remoteComputeAuthorized) throw new Error("REMOTE_COMPUTE_NOT_AUTHORIZED");
    if (request.remote && request.costCeilingUsd > this.remoteBudget) throw new Error("REMOTE_COST_BUDGET_EXCEEDED");
    const committed = [...this.jobs.values()].reduce((total, job) => total + job.requestedMemoryMiB, 0);
    if (committed + request.requestedMemoryMiB > this.aggregateRssMiB) throw new Error("RSS_BUDGET_EXCEEDED");
    if (request.remote) this.remoteBudget -= request.costCeilingUsd;
    const job = { ...request, state: "queued" as const };
    this.jobs.set(job.id, job);
    return job;
  }

  snapshot(): readonly ScheduledJob[] { return [...this.jobs.values()]; }
}
