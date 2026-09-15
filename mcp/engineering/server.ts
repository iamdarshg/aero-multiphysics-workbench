import { McpServer } from "@modelcontextprotocol/server";
import { serveStdio } from "@modelcontextprotocol/server/stdio";

import { HttpEngineeringApi } from "./api-client.ts";
import { EngineeringOperations } from "./operations.ts";
import { policyFromEnvironment } from "./policy.ts";
import { registerEngineeringTools } from "./tools.ts";

// The official SDK owns JSON-RPC framing. stdout is reserved for protocol
// messages; diagnostics go to stderr only, and a failed initialization exits
// nonzero with a single-line stderr detail.
try {
  const policy = policyFromEnvironment();
  const operations = new EngineeringOperations(new HttpEngineeringApi(policy.apiBaseUrl), policy);

  const createServer = (): McpServer => {
    const server = new McpServer(
      { name: "aero-engineering", version: "0.1.0" },
      { instructions: "Thin policy-gated client of the product API. Read-only inspection is open; submits are deferred and require mutation approval; cancel requires destructive approval plus job ownership. This server never enables remote compute, raises cost limits, or executes solvers." },
    );
    registerEngineeringTools(server, operations);
    return server;
  };

  await serveStdio(createServer, {
    onerror: (error) => console.error(`MCP_RUNTIME_ERROR:${error instanceof Error ? error.message : "unknown"}`),
  });
} catch (error) {
  console.error(`MCP_STARTUP_FAILED:${error instanceof Error ? error.message : "unknown"}`);
  process.exit(1);
}
