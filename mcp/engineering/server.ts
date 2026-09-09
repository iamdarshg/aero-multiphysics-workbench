import { McpServer } from "@modelcontextprotocol/server";
import { serveStdio } from "@modelcontextprotocol/server/stdio";

import { McpEngineeringServer } from "../../packages/solver-contracts/src/index.ts";
import { LocalScheduler } from "../../packages/solver-contracts/src/scheduler.ts";
import { policyFromEnvironment } from "./policy.ts";
import { registerEngineeringTools } from "./tools.ts";

const policy = policyFromEnvironment();
const operationServer = new McpEngineeringServer(
  new LocalScheduler({
    remoteComputeAuthorized: policy.remoteCompute,
    remainingRemoteBudgetUsd: policy.remoteCostCeilingUsd,
  }),
  {
    mutations: policy.mutations,
    destructive: policy.destructive,
    remoteCompute: policy.remoteCompute,
    remoteCostCeilingUsd: policy.remoteCostCeilingUsd,
    ownerId: policy.ownerId,
  },
);

const createServer = (): McpServer => {
  const server = new McpServer(
    { name: "aero-engineering", version: "0.1.0" },
    { instructions: "Typed metadata and bounded reservations only. Remote, destructive, and cost-bearing work remains deny-by-default." },
  );
  registerEngineeringTools(server, operationServer);
  return server;
};

// The official SDK owns JSON-RPC framing. stdout is reserved for protocol
// messages; diagnostics are emitted by the SDK callback to stderr.
await serveStdio(createServer, { onerror: (error) => console.error(error.message) });
