import { LocalScheduler } from "./scheduler.ts";
import type { ScheduledJob } from "./contracts.ts";

export type McpOperation =
  | "design.inspect" | "design.variant.create" | "design.delete"
  | "simulation.launch" | "job.cancel" | "result.inspect" | "provenance.list";

export interface McpPermissions {
  readonly mutations?: boolean;
  readonly destructive?: boolean;
  readonly remoteCompute?: boolean;
  readonly remoteCostCeilingUsd?: number;
  readonly ownerId?: string;
}

/** Typed, policy-only operation facade used by the official MCP transport. */
export class McpEngineeringServer {
  private readonly scheduler: LocalScheduler;
  private readonly permissions: McpPermissions;
  constructor(scheduler: LocalScheduler, permissions: McpPermissions = {}) {
    this.scheduler = scheduler;
    this.permissions = permissions;
  }

  async call(operation: McpOperation, input: Record<string, unknown>): Promise<Record<string, unknown> | ScheduledJob | readonly ScheduledJob[]> {
    const ownerId = this.permissions.ownerId ?? "local-operator";
    if (operation === "design.delete") {
      if (!this.permissions.destructive) throw new Error("DESTRUCTIVE_OPERATION_NOT_AUTHORIZED");
      return { authorized: true, deleted: false, designId: String(input.designId ?? ""), reason: "NO_DESIGN_STORE_CONFIGURED" };
    }
    if (operation === "design.variant.create") {
      if (!this.permissions.mutations) throw new Error("MUTATION_NOT_AUTHORIZED");
      const designId = String(input.designId ?? "");
      const variantId = String(input.variantId ?? "");
      if (!designId || !variantId) throw new Error("INVALID_VARIANT_REQUEST");
      return { created: false, designId, variantId, reason: "NO_DESIGN_STORE_CONFIGURED" };
    }
    if (operation === "simulation.launch") {
      const id = String(input.id ?? "");
      const requestedMemoryMiB = Number(input.requestedMemoryMiB);
      const costCeilingUsd = Number(input.costCeilingUsd ?? 0);
      const remote = input.remote === true;
      if (remote && !this.permissions.remoteCompute) throw new Error("REMOTE_COMPUTE_NOT_AUTHORIZED");
      if (remote && costCeilingUsd > (this.permissions.remoteCostCeilingUsd ?? 0)) throw new Error("REMOTE_COST_BUDGET_EXCEEDED");
      return this.scheduler.submit({ id, requestedMemoryMiB, remote, costCeilingUsd, ownerId });
    }
    if (operation === "job.cancel") {
      return this.scheduler.cancel(String(input.id ?? ""), ownerId);
    }
    if (operation === "design.inspect" || operation === "result.inspect") return { operation, source: "metadata-only", found: false };
    if (operation === "provenance.list") return { source: "metadata-only", events: [] };
    throw new Error("UNKNOWN_MCP_OPERATION");
  }
}
