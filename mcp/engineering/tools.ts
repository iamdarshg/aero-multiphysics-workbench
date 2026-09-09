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
    description: "Inspect design metadata without reading arbitrary paths.",
    inputSchema: z.object({ designId: z.string().min(1).max(128) }),
  }, (input) => invoke("design.inspect", operationServer, input));

  server.registerTool("design.variant.create", {
    description: "Request a variant through the governed design store.",
    inputSchema: z.object({ designId: z.string().min(1).max(128), variantId: z.string().min(1).max(128) }),
  }, (input) => invoke("design.variant.create", operationServer, input));

  server.registerTool("result.inspect", {
    description: "Inspect result metadata without reading arbitrary artifact paths.",
    inputSchema: z.object({ resultId: z.string().min(1).max(128) }),
  }, (input) => invoke("result.inspect", operationServer, input));

  server.registerTool("provenance.list", {
    description: "Retrieve provenance metadata for the current owner.",
    inputSchema: z.object({ designId: z.string().min(1).max(128).optional() }),
  }, (input) => invoke("provenance.list", operationServer, input));

  server.registerTool("simulation.launch", {
    description: "Request a bounded simulation reservation. Does not execute a solver.",
    inputSchema: z.object({
      id: z.string().min(1).max(128),
      requestedMemoryMiB: z.number().positive().max(896),
      remote: z.boolean().default(false),
      costCeilingUsd: z.number().nonnegative().default(0),
    }),
  }, (input) => invoke("simulation.launch", operationServer, input));

  server.registerTool("job.cancel", {
    description: "Cancel a queued job owned by the current operator.",
    inputSchema: z.object({ id: z.string().min(1).max(128) }),
  }, (input) => invoke("job.cancel", operationServer, input));

  server.registerTool("design.delete", {
    description: "Delete a design only when the interactive operator explicitly enabled destructive access.",
    inputSchema: z.object({ designId: z.string().min(1).max(128) }),
  }, (input) => invoke("design.delete", operationServer, input));
};

