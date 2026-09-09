import type { McpServer } from "@modelcontextprotocol/server";
import { z } from "zod";
import type { McpEngineeringServer, McpOperation } from "../../packages/solver-contracts/src/mcp.ts";

const success = (value: Record<string, unknown> | readonly unknown[]) => ({
  content: [{ type: "text" as const, text: JSON.stringify(value) }],
  structuredContent: value,
});

const invoke = async (operation: McpOperation, operationServer: McpEngineeringServer, input: Record<string, unknown>) => {
  try {
    return success(await operationServer.call(operation, input));
  } catch (error) {
    return {
      content: [{ type: "text" as const, text: error instanceof Error ? error.message : "UNKNOWN_ERROR" }],
      isError: true as const,
    };
  }
};

/** Register only typed, bounded operations; there is deliberately no shell/path tool. */
export const registerEngineeringTools = (server: McpServer, operationServer: McpEngineeringServer): void => {
  server.registerTool("design.inspect", {
    description: "Skeleton metadata inspection only; no design store is connected and no arbitrary paths are read.",
    inputSchema: z.object({ designId: z.string().min(1).max(128) }),
  }, (input) => invoke("design.inspect", operationServer, input));

  server.registerTool("design.variant.create", {
    description: "Skeleton variant request only; queued metadata response until a governed design store is connected.",
    inputSchema: z.object({ designId: z.string().min(1).max(128), variantId: z.string().min(1).max(128) }),
  }, (input) => invoke("design.variant.create", operationServer, input));

  server.registerTool("result.inspect", {
    description: "Skeleton result metadata inspection only; no result store or native artifact reader is connected.",
    inputSchema: z.object({ resultId: z.string().min(1).max(128) }),
  }, (input) => invoke("result.inspect", operationServer, input));

  server.registerTool("provenance.list", {
    description: "Skeleton provenance listing only; returns queued/empty metadata until a provenance store is connected.",
    inputSchema: z.object({ designId: z.string().min(1).max(128).optional() }),
  }, (input) => invoke("provenance.list", operationServer, input));

  server.registerTool("simulation.launch", {
    description: "Queued reservation skeleton only; does not execute a solver or claim Task 4/5 completion.",
    inputSchema: z.object({
      id: z.string().min(1).max(128),
      requestedMemoryMiB: z.number().positive().max(896),
      remote: z.boolean().default(false),
      costCeilingUsd: z.number().nonnegative().default(0),
    }),
  }, (input) => invoke("simulation.launch", operationServer, input));

  server.registerTool("job.cancel", {
    description: "Cancel a queued reservation only; no running native process is connected to this operation.",
    inputSchema: z.object({ id: z.string().min(1).max(128) }),
  }, (input) => invoke("job.cancel", operationServer, input));

  server.registerTool("design.delete", {
    description: "Skeleton destructive request only; no design store is connected, so deletion remains a fail-closed no-op.",
    inputSchema: z.object({ designId: z.string().min(1).max(128) }),
  }, (input) => invoke("design.delete", operationServer, input));
};
