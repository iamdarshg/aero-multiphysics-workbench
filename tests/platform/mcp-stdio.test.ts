import assert from "node:assert/strict";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { Client } from "@modelcontextprotocol/client";
import { StdioClientTransport } from "@modelcontextprotocol/client/stdio";

test("engineering server completes an MCP stdio handshake and exposes only allowlisted tools", async () => {
  const repoRoot = fileURLToPath(new URL("../../", import.meta.url));
  const client = new Client({ name: "platform-integration-test", version: "1.0.0" });
  const transport = new StdioClientTransport({
    command: process.execPath,
    args: ["mcp/engineering/server.ts"],
    cwd: repoRoot,
    stderr: "pipe",
    env: {
      AERO_ALLOW_DESTRUCTIVE: "0",
      AERO_ALLOW_REMOTE_COMPUTE: "0",
      AERO_REMOTE_COST_CEILING_USD: "0",
    },
  });
  assert.ok(transport.stderr, "the official transport must keep diagnostics off the protocol stream");

  try {
    await client.connect(transport);
    const listed = await client.listTools();
    assert.deepEqual(
      listed.tools.map((tool) => tool.name).sort(),
      ["design.delete", "design.inspect", "design.variant.create", "job.cancel", "provenance.list", "result.inspect", "simulation.launch"],
    );

    const inspect = await client.callTool({ name: "design.inspect", arguments: { designId: "fan-a" } });
    assert.equal(inspect.isError, undefined);
    assert.deepEqual(inspect.structuredContent, {
      operation: "design.inspect",
      source: "metadata-only",
      found: false,
    });

    const denied = await client.callTool({ name: "design.delete", arguments: { designId: "fan-a" } });
    assert.equal(denied.isError, true);
    assert.match(JSON.stringify(denied.content), /DESTRUCTIVE_OPERATION_NOT_AUTHORIZED/);

    const queued = await client.callTool({ name: "simulation.launch", arguments: { id: "stdio-job", requestedMemoryMiB: 64, remote: false, costCeilingUsd: 0 } });
    assert.equal(queued.isError, undefined);
    const cancelled = await client.callTool({ name: "job.cancel", arguments: { id: "stdio-job" } });
    assert.equal(cancelled.isError, undefined);
  } finally {
    await client.close();
  }
});
