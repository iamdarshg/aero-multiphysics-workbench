import { LocalScheduler } from "./scheduler.ts";
import type { ScheduledJob } from "./contracts.ts";

export type McpOperation = "design.inspect" | "design.delete" | "simulation.launch" | "result.inspect";
export interface McpPermissions { readonly destructive?: boolean; }

/** In-process MCP operation facade; transport binding is intentionally external and opt-in. */
export class McpEngineeringServer {
  private readonly scheduler: LocalScheduler;
  private readonly permissions: McpPermissions;
  constructor(scheduler: LocalScheduler, permissions: McpPermissions = {}) {
    this.scheduler = scheduler;
    this.permissions = permissions;
  }

  async call(operation: McpOperation, input: Record<string, unknown>): Promise<Record<string, unknown> | ScheduledJob> {
    if (operation === "design.delete") {
      if (!this.permissions.destructive) throw new Error("DESTRUCTIVE_OPERATION_NOT_AUTHORIZED");
      return { deleted: true, designId: String(input.designId ?? "") };
    }
    if (operation === "simulation.launch") {
      return this.scheduler.submit({
        id: String(input.id ?? ""), requestedMemoryMiB: Number(input.requestedMemoryMiB),
        remote: input.remote === true, costCeilingUsd: Number(input.costCeilingUsd),
      });
    }
    if (operation === "design.inspect" || operation === "result.inspect") return { operation, source: "metadata-only", found: false };
    throw new Error("UNKNOWN_MCP_OPERATION");
  }
}
