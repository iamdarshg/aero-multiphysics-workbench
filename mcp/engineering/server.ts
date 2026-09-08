import readline from "node:readline";
import { LocalScheduler, McpEngineeringServer } from "../../packages/solver-contracts/src/index.ts";

/** User-started JSON-lines MCP bridge. It is intentionally not a daemon and defaults to deny. */
const destructive = process.env.AERO_ALLOW_DESTRUCTIVE === "1";
const remote = process.env.AERO_ALLOW_REMOTE_COMPUTE === "1";
const remoteBudget = Number(process.env.AERO_REMOTE_COST_CEILING_USD ?? "0");
const server = new McpEngineeringServer(
  new LocalScheduler({ remoteComputeAuthorized: remote, remainingRemoteBudgetUsd: remoteBudget }),
  { destructive },
);

const input = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });
for await (const line of input) {
  try {
    const request = JSON.parse(line) as { id?: string | number; operation: "design.inspect" | "design.delete" | "simulation.launch" | "result.inspect"; input?: Record<string, unknown> };
    const result = await server.call(request.operation, request.input ?? {});
    process.stdout.write(`${JSON.stringify({ id: request.id ?? null, ok: true, result })}\n`);
  } catch (error) {
    process.stdout.write(`${JSON.stringify({ ok: false, error: error instanceof Error ? error.message : "UNKNOWN_ERROR" })}\n`);
  }
}
