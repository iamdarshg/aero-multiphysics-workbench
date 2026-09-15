import assert from "node:assert/strict";
import { spawn, type ChildProcess } from "node:child_process";
import { createServer, type IncomingMessage, type Server, type ServerResponse } from "node:http";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { Client } from "@modelcontextprotocol/client";
import { StdioClientTransport } from "@modelcontextprotocol/client/stdio";

const EXPECTED_TOOLS = [
  "analysis.submit",
  "capabilities.inspect",
  "design.inspect",
  "design.variant.create",
  "job.cancel",
  "job.inspect",
  "result.inspect",
];

interface StubJob {
  job_id: string;
  participant_id: string;
  design_id: string;
  owner_id: string | null;
  revision_id: string | null;
  analysis: string | null;
  fidelity: string;
  state: string;
  error_code: string | null;
  error_detail: string | null;
  run_id: string | null;
  result_id: string | null;
  provenance_id: string | null;
  input_hash: string | null;
}

const PARTICIPANT_ID = "stub-flow";

const stubState = () => {
  let counter = 0;
  const jobs = new Map<string, StubJob>();
  const seed = (job: StubJob): void => {
    jobs.set(job.job_id, job);
  };
  seed({
    job_id: "foreign-job-1",
    participant_id: PARTICIPANT_ID,
    design_id: "foreign-design",
    owner_id: "someone-else",
    revision_id: null,
    analysis: "baseline-run",
    fidelity: "baseline",
    state: "QUEUED",
    error_code: null,
    error_detail: null,
    run_id: null,
    result_id: null,
    provenance_id: "prov-foreign",
    input_hash: "0".repeat(64),
  });
  seed({
    job_id: "done-job-1",
    participant_id: PARTICIPANT_ID,
    design_id: "done-design",
    owner_id: "test-owner",
    revision_id: "rev-3",
    analysis: "baseline-run",
    fidelity: "baseline",
    state: "COMPLETED",
    error_code: null,
    error_detail: null,
    run_id: "run-done-1",
    result_id: "result-done-1",
    provenance_id: "prov-done-1",
    input_hash: "1".repeat(64),
  });
  return {
    jobs,
    nextId: (): string => {
      counter += 1;
      return `stub-job-${counter}`;
    },
  };
};

type StubStore = ReturnType<typeof stubState>;

const readJsonBody = (request: IncomingMessage): Promise<Record<string, unknown>> =>
  new Promise((resolve, reject) => {
    let text = "";
    request.on("data", (chunk: Buffer) => {
      text += chunk.toString();
    });
    request.on("end", () => {
      if (!text) {
        resolve({});
        return;
      }
      try {
        const parsed: unknown = JSON.parse(text);
        resolve(typeof parsed === "object" && parsed !== null ? (parsed as Record<string, unknown>) : {});
      } catch (error) {
        reject(error);
      }
    });
    request.on("error", reject);
  });

const sendJson = (response: ServerResponse, status: number, payload: unknown): void => {
  response.writeHead(status, { "content-type": "application/json" });
  response.end(JSON.stringify(payload));
};

/** Minimal in-process double of the public product API paths the MCP server uses. */
const startStubApi = async (store: StubStore): Promise<{ server: Server; baseUrl: string }> =>
  new Promise((resolve) => {
    const server = createServer((request: IncomingMessage, response: ServerResponse) => {
      void (async () => {
        const url = new URL(request.url ?? "/", "http://127.0.0.1");
        const method = request.method ?? "GET";
        if (method === "GET" && url.pathname === "/v1/native/capabilities") {
          sendJson(response, 200, {
            ready: [
              {
                participant_id: PARTICIPANT_ID,
                solver_id: "stub-solver",
                executable: "stub-solver",
                version: "0.0-test",
                detail: "stub capability for MCP E2E",
              },
            ],
            unavailable: [],
          });
          return;
        }
        if (method === "GET" && url.pathname === "/v1/native/participants") {
          sendJson(response, 200, {
            manifest_version: "2",
            participants: [
              {
                participant_id: PARTICIPANT_ID,
                physics_domain: "stub",
                solver_id: "stub-solver",
                execution_mode: "subprocess",
                fidelity_levels: ["baseline"],
                coupling_direction: "none",
                benchmark_ref: "stub-ref",
              },
            ],
          });
          return;
        }
        if (method === "POST" && url.pathname === "/v1/native/analyses") {
          const body = await readJsonBody(request);
          if (body.participant_id !== PARTICIPANT_ID) {
            sendJson(response, 404, { detail: { code: "UNKNOWN_PARTICIPANT" } });
            return;
          }
          const job: StubJob = {
            job_id: store.nextId(),
            participant_id: PARTICIPANT_ID,
            design_id: typeof body.design_id === "string" ? body.design_id : "generic-design",
            owner_id: typeof body.owner_id === "string" ? body.owner_id : null,
            revision_id: typeof body.revision_id === "string" ? body.revision_id : null,
            analysis: typeof body.analysis === "string" ? body.analysis : null,
            fidelity: typeof body.fidelity === "string" ? body.fidelity : "baseline",
            state: "QUEUED",
            error_code: null,
            error_detail: null,
            run_id: null,
            result_id: null,
            provenance_id: null,
            input_hash: "2".repeat(64),
          };
          store.jobs.set(job.job_id, job);
          sendJson(response, 202, { job_id: job.job_id, ...job });
          return;
        }
        const analysisMatch = /^\/v1\/native\/analyses\/([^/]+)(\/cancel)?$/.exec(url.pathname);
        if (analysisMatch) {
          const job = store.jobs.get(decodeURIComponent(analysisMatch[1]));
          if (!job) {
            sendJson(response, 404, { detail: { code: "JOB_NOT_FOUND" } });
            return;
          }
          if (method === "GET" && !analysisMatch[2]) {
            sendJson(response, 200, job);
            return;
          }
          if (method === "POST" && analysisMatch[2] === "/cancel") {
            job.state = "CANCELLED";
            sendJson(response, 200, { job_id: job.job_id, state: job.state });
            return;
          }
        }
        const resultMatch = /^\/v1\/native\/results\/([^/]+)(\/manifest)?$/.exec(url.pathname);
        if (method === "GET" && resultMatch) {
          const job = store.jobs.get(decodeURIComponent(resultMatch[1]));
          if (!job) {
            sendJson(response, 404, { detail: { code: "JOB_NOT_FOUND" } });
            return;
          }
          if (job.state !== "COMPLETED") {
            sendJson(response, 404, { detail: { code: "RESULT_NOT_PUBLISHED", message: "no trusted result" } });
            return;
          }
          if (resultMatch[2] === "/manifest") {
            sendJson(response, 200, {
              job_id: job.job_id,
              design_id: job.design_id,
              revision_id: job.revision_id,
              result_id: job.result_id,
              run_id: job.run_id,
              provenance_id: job.provenance_id,
              source: "native_solver",
              fidelity: job.fidelity,
              validity: { passed: true, detail: "stub valid" },
              solver_identity: "stub-solver",
              solver_version: "0.0-test",
              input_hash: job.input_hash,
              artifacts: [],
            });
            return;
          }
          sendJson(response, 200, {
            source: "native_solver",
            fidelity: job.fidelity,
            solver_identity: "stub-solver",
            solver_version: "0.0-test",
            run_id: job.run_id,
            provenance_id: job.provenance_id,
            input_hash: job.input_hash,
            validity: { passed: true, detail: "stub valid" },
            warnings: [],
            scalars: { residual: 0.001 },
            units: { residual: "dimensionless" },
            artifacts: [],
          });
          return;
        }
        const provenanceMatch = /^\/v1\/native\/provenance\/([^/]+)$/.exec(url.pathname);
        if (method === "GET" && provenanceMatch) {
          const job = store.jobs.get(decodeURIComponent(provenanceMatch[1]));
          if (!job) {
            sendJson(response, 404, { detail: { code: "JOB_NOT_FOUND" } });
            return;
          }
          sendJson(response, 200, { job_id: job.job_id, events: [] });
          return;
        }
        sendJson(response, 404, { detail: { code: "STUB_ROUTE_NOT_FOUND" } });
      })().catch(() => {
        if (!response.headersSent) sendJson(response, 500, { detail: { code: "STUB_FAILURE" } });
      });
    });
    server.listen(0, "127.0.0.1", () => {
      const address = server.address();
      const port = typeof address === "object" && address ? address.port : 0;
      resolve({ server, baseUrl: `http://127.0.0.1:${port}` });
    });
  });

const closeServer = (server: Server): Promise<void> =>
  new Promise((resolve) => {
    server.close(() => resolve());
  });

const connectClient = async (repoRoot: string, env: Record<string, string>): Promise<{ client: Client; transport: StdioClientTransport }> => {
  const client = new Client({ name: "mcp-e2e-test", version: "1.0.0" });
  const transport = new StdioClientTransport({
    command: process.execPath,
    args: ["mcp/engineering/server.ts"],
    cwd: repoRoot,
    stderr: "pipe",
    env,
  });
  assert.ok(transport.stderr, "the official transport must keep diagnostics off the protocol stream");
  await client.connect(transport);
  return { client, transport };
};

/** Accept either a tool-level isError result or a thrown validation error. */
const expectRejected = async (attempt: Promise<Record<string, unknown>>, pattern: RegExp): Promise<void> => {
  try {
    const result = (await attempt) as { isError?: boolean; content?: unknown };
    assert.equal(result.isError, true, `expected isError result matching ${pattern}`);
    assert.match(JSON.stringify(result.content ?? result), pattern);
  } catch (error) {
    if (error instanceof assert.AssertionError) throw error;
    assert.match(error instanceof Error ? error.message : String(error), pattern);
  }
};

test(
  "engineering MCP exposes the small API-backed tool set over real stdio",
  { timeout: 60_000 },
  async () => {
    const repoRoot = fileURLToPath(new URL("../../", import.meta.url));
    const store = stubState();
    const { server, baseUrl } = await startStubApi(store);
    const { client } = await connectClient(repoRoot, {
      AERO_API_BASE_URL: baseUrl,
      AERO_OWNER_ID: "test-owner",
      AERO_ALLOW_MUTATIONS: "1",
      AERO_ALLOW_DESTRUCTIVE: "1",
      AERO_ALLOW_REMOTE_COMPUTE: "0",
      AERO_REMOTE_COST_CEILING_USD: "0",
    });
    try {
      const listed = await client.listTools();
      assert.deepEqual(listed.tools.map((tool) => tool.name).sort(), EXPECTED_TOOLS);

      const capabilities = await client.callTool({ name: "capabilities.inspect", arguments: {} });
      assert.equal(capabilities.isError, undefined);
      assert.match(JSON.stringify(capabilities.structuredContent), /stub-flow/);

      const submitted = await client.callTool({
        name: "analysis.submit",
        arguments: { participantId: PARTICIPANT_ID, designId: "e2e-design", inputs: { inlet_velocity_m_s: 10 } },
      });
      assert.equal(submitted.isError, undefined);
      const submittedContent = submitted.structuredContent as { jobId: string; state: string };
      assert.match(submittedContent.jobId, /^stub-job-/);
      assert.equal(submittedContent.state, "QUEUED");

      const inspected = await client.callTool({
        name: "job.inspect",
        arguments: { jobId: submittedContent.jobId },
      });
      assert.equal(inspected.isError, undefined);
      assert.match(JSON.stringify(inspected.structuredContent), /QUEUED/);

      const design = await client.callTool({
        name: "design.inspect",
        arguments: { jobId: submittedContent.jobId },
      });
      assert.equal(design.isError, undefined);
      assert.match(JSON.stringify(design.structuredContent), /e2e-design/);

      const variant = await client.callTool({
        name: "design.variant.create",
        arguments: {
          designId: "e2e-design",
          variantRevisionId: "rev-e2e-2",
          participantId: PARTICIPANT_ID,
          inputs: { inlet_velocity_m_s: 12 },
        },
      });
      assert.equal(variant.isError, undefined);
      assert.match(JSON.stringify(variant.structuredContent), /rev-e2e-2/);

      const unpublished = await client.callTool({
        name: "result.inspect",
        arguments: { jobId: submittedContent.jobId },
      });
      assert.equal(unpublished.isError, true);
      assert.match(JSON.stringify(unpublished.content), /RESULT_NOT_PUBLISHED/);

      const published = await client.callTool({ name: "result.inspect", arguments: { jobId: "done-job-1" } });
      assert.equal(published.isError, undefined);
      assert.match(JSON.stringify(published.structuredContent), /stub-solver/);

      const cancelled = await client.callTool({ name: "job.cancel", arguments: { jobId: submittedContent.jobId } });
      assert.equal(cancelled.isError, undefined);
      assert.match(JSON.stringify(cancelled.structuredContent), /CANCELLED/);

      const foreignStateBefore = store.jobs.get("foreign-job-1")?.state;
      await expectRejected(
        client.callTool({ name: "job.cancel", arguments: { jobId: "foreign-job-1" } }) as Promise<Record<string, unknown>>,
        /JOB_NOT_OWNED/,
      );
      assert.equal(store.jobs.get("foreign-job-1")?.state, foreignStateBefore);

      // Bounded schemas: traversal, absolute paths, command text, unknown ids/fields.
      await expectRejected(
        client.callTool({ name: "design.inspect", arguments: { jobId: "../../etc/passwd" } }) as Promise<Record<string, unknown>>,
        /UNSAFE_|Invalid|validation/i,
      );
      await expectRejected(
        client.callTool({ name: "job.cancel", arguments: { jobId: "/absolute/path" } }) as Promise<Record<string, unknown>>,
        /UNSAFE_|Invalid|validation/i,
      );
      await expectRejected(
        client.callTool({
          name: "analysis.submit",
          arguments: { participantId: "stub-flow; rm -rf /", inputs: {} },
        }) as Promise<Record<string, unknown>>,
        /UNSAFE_|Invalid|validation/i,
      );
      await expectRejected(
        client.callTool({
          name: "analysis.submit",
          arguments: { participantId: "no-such-participant", inputs: {} },
        }) as Promise<Record<string, unknown>>,
        /UNKNOWN_PARTICIPANT/,
      );
      await expectRejected(
        client.callTool({
          name: "analysis.submit",
          arguments: { participantId: PARTICIPANT_ID, inputs: {}, extraField: true },
        }) as Promise<Record<string, unknown>>,
        /nrecognized|UNSAFE|validation/i,
      );
    } finally {
      await client.close();
      await closeServer(server);
    }
  },
);

test("engineering MCP denies mutations and destructive cancel without explicit flags", { timeout: 60_000 }, async () => {
  const repoRoot = fileURLToPath(new URL("../../", import.meta.url));
  const store = stubState();
  const { server, baseUrl } = await startStubApi(store);
  const { client } = await connectClient(repoRoot, {
    AERO_API_BASE_URL: baseUrl,
    AERO_OWNER_ID: "test-owner",
    AERO_ALLOW_MUTATIONS: "0",
    AERO_ALLOW_DESTRUCTIVE: "0",
    AERO_ALLOW_REMOTE_COMPUTE: "0",
    AERO_REMOTE_COST_CEILING_USD: "0",
  });
  try {
    await expectRejected(
      client.callTool({
        name: "analysis.submit",
        arguments: { participantId: PARTICIPANT_ID, inputs: {} },
      }) as Promise<Record<string, unknown>>,
      /MUTATION_NOT_AUTHORIZED/,
    );
    await expectRejected(
      client.callTool({ name: "job.cancel", arguments: { jobId: "done-job-1" } }) as Promise<Record<string, unknown>>,
      /DESTRUCTIVE_OPERATION_NOT_AUTHORIZED/,
    );
    const readOnly = await client.callTool({ name: "job.inspect", arguments: { jobId: "done-job-1" } });
    assert.equal(readOnly.isError, undefined);
  } finally {
    await client.close();
    await closeServer(server);
  }
});

test("engineering MCP stdout carries protocol frames only", { timeout: 30_000 }, async () => {
  const repoRoot = fileURLToPath(new URL("../../", import.meta.url));
  const child: ChildProcess = spawn(process.execPath, ["mcp/engineering/server.ts"], {
    cwd: repoRoot,
    stdio: ["pipe", "pipe", "pipe"],
    env: { ...process.env, AERO_API_BASE_URL: "http://127.0.0.1:9", AERO_REMOTE_COST_CEILING_USD: "0" },
  });
  let stdout = "";
  let settled = false;
  try {
    child.stdout?.on("data", (chunk: Buffer) => {
      stdout += chunk.toString();
    });
    const frame = {
      jsonrpc: "2.0",
      id: 1,
      method: "initialize",
      params: { protocolVersion: "2025-06-18", capabilities: {}, clientInfo: { name: "raw-stdout-probe", version: "0" } },
    };
    child.stdin?.write(`${JSON.stringify(frame)}\n`);
    await new Promise((resolve) => setTimeout(resolve, 4000));
    const lines = stdout.split("\n").map((line) => line.trim()).filter((line) => line.length > 0);
    assert.ok(lines.length > 0, "expected at least one protocol frame on stdout");
    let sawResponse = false;
    for (const line of lines) {
      const parsed: unknown = JSON.parse(line);
      assert.equal(typeof parsed, "object");
      assert.equal((parsed as { jsonrpc: string }).jsonrpc, "2.0");
      if ((parsed as { id?: number }).id === 1) sawResponse = true;
    }
    assert.equal(sawResponse, true, `expected the initialize response on stdout, got: ${stdout.slice(0, 500)}`);
  } finally {
    if (!settled) {
      settled = true;
      child.kill("SIGKILL");
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
});

test("engineering MCP startup failure exits nonzero with stderr detail", { timeout: 30_000 }, async () => {
  const repoRoot = fileURLToPath(new URL("../../", import.meta.url));
  const child: ChildProcess = spawn(process.execPath, ["mcp/engineering/server.ts"], {
    cwd: repoRoot,
    stdio: ["ignore", "pipe", "pipe"],
    env: { ...process.env, AERO_REMOTE_COST_CEILING_USD: "not-a-number" },
  });
  let stderr = "";
  child.stderr?.on("data", (chunk: Buffer) => {
    stderr += chunk.toString();
  });
  const exitCode: number | null = await new Promise((resolve) => {
    const timer = setTimeout(() => {
      child.kill("SIGKILL");
      resolve(null);
    }, 15000);
    child.on("exit", (code) => {
      clearTimeout(timer);
      resolve(code);
    });
  });
  assert.ok(exitCode !== null && exitCode !== 0, `expected a nonzero exit, got ${exitCode}`);
  assert.match(stderr, /INVALID_REMOTE_COST_CEILING/);
});
