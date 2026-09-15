import type { McpServer } from "@modelcontextprotocol/server";
import { z } from "zod";

import { ApiError } from "./api-client.ts";
import { isSafeInputValue } from "./policy.ts";
import { type EngineeringOperations, type EngineeringToolName } from "./operations.ts";

const success = (value: Record<string, unknown>) => ({
  content: [{ type: "text" as const, text: JSON.stringify(value) }],
  structuredContent: value,
});

const invoke = async (
  tool: EngineeringToolName,
  operations: EngineeringOperations,
  input: Record<string, unknown>,
) => {
  try {
    return success(await operations.call(tool, input));
  } catch (error) {
    // API errors surface their stable product code first so callers and
    // tests can match on codes like RESULT_NOT_PUBLISHED or JOB_NOT_FOUND.
    const text =
      error instanceof ApiError
        ? `${error.code}: ${error.message}`
        : error instanceof Error
          ? error.message
          : "UNKNOWN_ERROR";
    return {
      content: [{ type: "text" as const, text }],
      isError: true as const,
    };
  }
};

const safeToken = (field: string) =>
  z
    .string()
    .min(1)
    .max(128)
    .regex(/^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/, `${field} must be a bounded product identifier`)
    .refine((value) => !value.includes(".."), `${field} must not contain parent traversal`);

const boundedInputs = z
  .record(
    z.string().min(1).max(64).regex(/^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$/),
    z.union([
      z.string().max(256).refine((value) => isSafeInputValue(value), "input value must not carry paths or command text"),
      z.number().finite(),
      z.boolean(),
    ]),
  )
  .refine((value) => Object.keys(value).length <= 32, "at most 32 input entries");

const submitFields = {
  participantId: safeToken("participantId").describe("Allowlisted participant id, validated live against the product API"),
  analysis: safeToken("analysis").optional().describe("Optional analysis label from API-supported fields"),
  fidelity: safeToken("fidelity").optional().describe("Optional fidelity level, validated against the participant manifest"),
  inputs: boundedInputs.optional().describe("Bounded scalar input map; no paths, commands, or nested objects"),
  requestedMemoryMib: z.number().positive().max(896).optional().describe("Optional local RSS reservation in MiB"),
};

/**
 * Register only the seven product-facing tools. There is deliberately no
 * shell, path, fetch, or raw-solver tool: every operation goes through the
 * public product API with strict schemas and independent policy gates.
 */
export const registerEngineeringTools = (server: McpServer, operations: EngineeringOperations): void => {
  server.registerTool(
    "capabilities.inspect",
    {
      description: "Read-only: solver capabilities and participant manifests from the product API, plus the MCP policy gates in force.",
      inputSchema: z.object({}).strict(),
    },
    () => invoke("capabilities.inspect", operations, {}),
  );

  server.registerTool(
    "design.inspect",
    {
      description: "Read-only: design/revision metadata anchored to a governed job record via the product API. Takes a job id, never a filesystem path.",
      inputSchema: z.object({ jobId: safeToken("jobId") }).strict(),
    },
    (input) => invoke("design.inspect", operations, input),
  );

  server.registerTool(
    "job.inspect",
    {
      description: "Read-only: governed job state (state, error codes, run/result/provenance ids) via the product API.",
      inputSchema: z.object({ jobId: safeToken("jobId") }).strict(),
    },
    (input) => invoke("job.inspect", operations, input),
  );

  server.registerTool(
    "result.inspect",
    {
      description: "Read-only: trusted result envelope, result manifest, and provenance for a job via the product API. Unpublished results fail honestly.",
      inputSchema: z.object({ jobId: safeToken("jobId") }).strict(),
    },
    (input) => invoke("result.inspect", operations, input),
  );

  server.registerTool(
    "design.variant.create",
    {
      description: "Mutation-gated: queue a validated design variant as a deferred governed job using API-supported fields only. Requires AERO_ALLOW_MUTATIONS=1. Never starts execution.",
      inputSchema: z
        .object({
          designId: safeToken("designId"),
          variantRevisionId: safeToken("variantRevisionId"),
          ...submitFields,
        })
        .strict(),
    },
    (input) => invoke("design.variant.create", operations, input),
  );

  server.registerTool(
    "analysis.submit",
    {
      description: "Mutation-gated: submit an allowed analysis as a deferred governed job using API-supported fields only. Requires AERO_ALLOW_MUTATIONS=1. Never starts execution; a human starts it via the UI/API.",
      inputSchema: z
        .object({
          designId: safeToken("designId").optional(),
          revisionId: safeToken("revisionId").optional(),
          ...submitFields,
        })
        .strict(),
    },
    (input) => invoke("analysis.submit", operations, input),
  );

  server.registerTool(
    "job.cancel",
    {
      description: "Destructive and ownership-gated: cancel a job owned by the configured operator via the product API. Requires AERO_ALLOW_DESTRUCTIVE=1 and owner match.",
      inputSchema: z.object({ jobId: safeToken("jobId") }).strict(),
    },
    (input) => invoke("job.cancel", operations, input),
  );
};
