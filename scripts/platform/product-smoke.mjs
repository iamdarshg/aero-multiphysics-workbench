// Product smoke test: one real API job to a terminal verified result.
//
// Spawns the genuine services/api FastAPI app (uvicorn) on loopback with an
// isolated job root, submits the tiny deterministic `rotor-campbell`
// participant (ross library, seconds-scale), polls the governed lifecycle to
// a terminal state, and verifies the published envelope carries
// `source: "native_solver"` plus persisted provenance events. Any deviation
// fails closed with a SMOKE_* code; success is never synthesized.
//
// Usage: node scripts/platform/product-smoke.mjs [--port N] [--participant ID]
//   [--ready-timeout-ms N] [--job-timeout-ms N]
import { spawn } from "node:child_process";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { delimiter, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { resolveApiPythonPath } from "./stack.mjs";

export const SMOKE_SCHEMA = 1;

/** Tiny deterministic participant: ross Campbell analysis, seconds-scale. */
export const SMOKE_PARTICIPANT = "rotor-campbell";

/** Minimal valid rotor-campbell inputs (mirrors the governed product tests). */
export const SMOKE_INPUTS = Object.freeze({
  analysis: "campbell",
  shaft_length_m: 1.5,
  shaft_diameter_m: 0.05,
  n_elements: 4,
  bearing_stiffness_n_m: 1e8,
  bearing_damping_n_s_m: 1000.0,
  max_speed_rpm: 12000.0,
});

export const TERMINAL_STATES = Object.freeze(["COMPLETED", "FAILED", "CANCELLED"]);

export const READY_TIMEOUT_MS_DEFAULT = 180_000;
export const JOB_TIMEOUT_MS_DEFAULT = 600_000;
export const POLL_MS_DEFAULT = 1_000;
export const STOP_GRACE_MS = 10_000;

const smokeError = (code, detail) => new Error(`${code}:${detail}`);

export const parseArgs = (argv) => {
  const parsed = {
    port: 8123,
    participantId: SMOKE_PARTICIPANT,
    readyTimeoutMs: READY_TIMEOUT_MS_DEFAULT,
    jobTimeoutMs: JOB_TIMEOUT_MS_DEFAULT,
    help: false,
  };
  const args = [...argv];
  for (let index = 0; index < args.length; index += 1) {
    const arg = args[index];
    if (arg === "--help" || arg === "-h") return { ...parsed, help: true };
    if (arg === "--port" || arg === "--ready-timeout-ms" || arg === "--job-timeout-ms" || arg === "--participant") {
      const raw = args[index + 1];
      if (raw === undefined) throw smokeError("SMOKE_USAGE", `missing value for ${arg}`);
      index += 1;
      if (arg === "--participant") {
        if (!/^[a-z0-9][a-z0-9-]*$/.test(raw)) throw smokeError("SMOKE_USAGE", `invalid --participant ${JSON.stringify(raw)}`);
        parsed.participantId = raw;
      } else {
        const value = Number(raw);
        if (!Number.isInteger(value) || value <= 0) throw smokeError("SMOKE_USAGE", `invalid ${arg}=${JSON.stringify(raw)}`);
        if (arg === "--port") parsed.port = value;
        else if (arg === "--ready-timeout-ms") parsed.readyTimeoutMs = value;
        else parsed.jobTimeoutMs = value;
      }
    } else {
      throw smokeError("SMOKE_USAGE", `unknown argument: ${arg}`);
    }
  }
  return parsed;
};

export const resolveConfig = ({ argv, env = {}, root }) => {
  const parsed = parseArgs(argv);
  const port = env.AERO_SMOKE_PORT?.trim() ? Number(env.AERO_SMOKE_PORT) : parsed.port;
  if (!Number.isInteger(port) || port < 1 || port > 65535) {
    throw smokeError("SMOKE_USAGE", `invalid AERO_SMOKE_PORT=${JSON.stringify(env.AERO_SMOKE_PORT)}`);
  }
  return {
    schema: SMOKE_SCHEMA,
    help: parsed.help,
    port,
    participantId: parsed.participantId,
    readyTimeoutMs: parsed.readyTimeoutMs,
    jobTimeoutMs: parsed.jobTimeoutMs,
    pollMs: POLL_MS_DEFAULT,
    root,
    apiBase: `http://127.0.0.1:${port}`,
    apiDir: join(root, "services", "api"),
    jobRoot: env.AEROWORKBENCH_JOB_ROOT?.trim()
      ? env.AEROWORKBENCH_JOB_ROOT.trim()
      : mkdtempSync(join(tmpdir(), "aero-smoke-")),
  };
};

const sleep = (ms) => new Promise((resolveSleep) => setTimeout(resolveSleep, ms));

const apiJson = async (method, url, body) => {
  const response = await fetch(url, {
    method,
    headers: body ? { "content-type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
    signal: AbortSignal.timeout(30_000),
  });
  let payload = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }
  return { status: response.status, payload };
};

/** Wait until GET url returns 2xx or the deadline passes. */
export const waitForHealth = async ({ url, deadlineMs, pollMs, now = () => Date.now() }) => {
  for (;;) {
    try {
      const response = await fetch(url, { signal: AbortSignal.timeout(5_000) });
      if (response.status >= 200 && response.status < 300) return;
    } catch {
      // Server still warming; keep polling until the deadline.
    }
    if (now() >= deadlineMs) {
      throw smokeError("SMOKE_STARTUP_TIMEOUT", `API health at ${url} never turned ready`);
    }
    await sleep(pollMs);
  }
};

/**
 * Submit one product job through the real API routes and verify the
 * terminal envelope. Throws SMOKE_* on any deviation; never synthesizes
 * success. Shared by the local smoke and the container smoke.
 */
export const runProductJob = async (apiBase, { participantId, inputs, jobTimeoutMs, pollMs }) => {
  const startedAt = Date.now();
  const participants = await apiJson("GET", `${apiBase}/v1/native/participants`);
  const known = (participants.payload?.participants ?? []).some(
    (entry) => entry?.participant_id === participantId,
  );
  if (!known) throw smokeError("SMOKE_PARTICIPANT_MISSING", `${participantId} is not in the API participant manifest`);

  const capabilities = await apiJson("GET", `${apiBase}/v1/native/capabilities`);
  const ready = (capabilities.payload?.ready ?? []).some(
    (entry) => entry?.participant_id === participantId,
  );
  if (!ready) {
    throw smokeError("SMOKE_CAPABILITY_NOT_READY",
      `${participantId} is not ready; refusing to fake a native result`);
  }

  const submitted = await apiJson("POST", `${apiBase}/v1/native/analyses`, {
    participant_id: participantId,
    inputs,
  });
  if (submitted.status !== 202 || !submitted.payload?.job_id) {
    throw smokeError("SMOKE_SUBMIT_FAILED",
      `submit returned ${submitted.status}: ${JSON.stringify(submitted.payload).slice(0, 300)}`);
  }
  const jobId = submitted.payload.job_id;

  const deadline = Date.now() + jobTimeoutMs;
  let status = await apiJson("GET", `${apiBase}/v1/native/analyses/${jobId}`);
  while (!TERMINAL_STATES.includes(status.payload?.state)) {
    if (Date.now() >= deadline) throw smokeError("SMOKE_JOB_TIMEOUT", `job ${jobId} stuck in ${status.payload?.state}`);
    await sleep(pollMs);
    status = await apiJson("GET", `${apiBase}/v1/native/analyses/${jobId}`);
  }
  if (status.payload?.state !== "COMPLETED") {
    throw smokeError("SMOKE_JOB_FAILED",
      `job ${jobId} ended ${status.payload?.state} (${status.payload?.error_code ?? "no code"}: ${(status.payload?.error_detail ?? "").slice(0, 200)})`);
  }

  const envelope = await apiJson("GET", `${apiBase}/v1/native/results/${jobId}`);
  if (envelope.status !== 200 || envelope.payload?.source !== "native_solver") {
    throw smokeError("SMOKE_RESULT_UNVERIFIED",
      `job ${jobId} has no native_solver envelope: ${JSON.stringify(envelope.payload).slice(0, 300)}`);
  }
  const provenance = await apiJson("GET", `${apiBase}/v1/native/provenance/${jobId}`);
  const events = provenance.payload?.events ?? [];
  if (!Array.isArray(events) || events.length === 0) {
    throw smokeError("SMOKE_RESULT_UNVERIFIED", `job ${jobId} published no provenance events`);
  }
  return {
    jobId,
    state: status.payload.state,
    source: envelope.payload.source,
    fidelity: envelope.payload.fidelity ?? null,
    provenanceEvents: events.length,
    elapsedMs: Date.now() - startedAt,
  };
};

const stopChild = async (child) => {
  if (child.exitCode !== null || child.signalCode !== null) return;
  child.kill("SIGTERM");
  const deadline = Date.now() + STOP_GRACE_MS;
  while ((child.exitCode === null && child.signalCode === null) && Date.now() < deadline) {
    await sleep(100);
  }
  if (child.exitCode === null && child.signalCode === null) child.kill("SIGKILL");
};

const printUsage = () => {
  console.log("Usage: node scripts/platform/product-smoke.mjs [--port N] [--participant ID] [--ready-timeout-ms N] [--job-timeout-ms N]");
  console.log("");
  console.log("Runs one tiny deterministic product job (default: rotor-campbell) through");
  console.log("the real API lifecycle on an isolated job root and verifies the terminal");
  console.log("native_solver envelope plus provenance. Fails closed; never fakes results.");
};

const main = async () => {
  const root = resolve(fileURLToPath(new URL(".", import.meta.url)), "..", "..");
  let config;
  try {
    config = resolveConfig({ argv: process.argv.slice(2), env: process.env, root });
  } catch (error) {
    console.error(`[product-smoke] ${error.message}`);
    printUsage();
    process.exitCode = 2;
    return;
  }
  if (config.help) {
    printUsage();
    return;
  }
  const lines = [];
  const child = spawn("uv",
    ["run", "--directory", config.apiDir, "uvicorn", "aeroworkbench_api.main:app",
      "--host", "127.0.0.1", "--port", String(config.port)],
    {
      cwd: root,
      shell: false,
      windowsHide: true,
      stdio: ["ignore", "pipe", "pipe"],
      env: {
        ...process.env,
        AEROWORKBENCH_JOB_ROOT: config.jobRoot,
        ...(await resolveApiPythonPath({ root }).then((apiPath) => (apiPath
          ? { PYTHONPATH: process.env.PYTHONPATH ? `${apiPath}${delimiter}${process.env.PYTHONPATH}` : apiPath }
          : {}))),
      },
    });
  child.stdout?.on("data", (chunk) => {
    for (const line of String(chunk).split(/\r?\n/)) {
      if (!line) continue;
      lines.push(line);
      if (lines.length > 50) lines.shift();
    }
  });
  child.stderr?.on("data", (chunk) => {
    for (const line of String(chunk).split(/\r?\n/)) {
      if (!line) continue;
      lines.push(line);
      if (lines.length > 50) lines.shift();
    }
  });
  const childFailedEarly = new Promise((resolveEarly) => {
    child.once("exit", (code) => resolveEarly(code));
  });
  try {
    const healthRace = await Promise.race([
      waitForHealth({
        url: `${config.apiBase}/health`,
        deadlineMs: Date.now() + config.readyTimeoutMs,
        pollMs: config.pollMs,
      }).then(() => "ready"),
      childFailedEarly.then(() => "exited"),
    ]);
    if (healthRace === "exited") {
      throw smokeError("SMOKE_STARTUP_FAILED",
        `API exited before health passed; tail: ${lines.slice(-5).join(" | ").slice(0, 500)}`);
    }
    const summary = await runProductJob(config.apiBase, {
      participantId: config.participantId,
      inputs: { ...SMOKE_INPUTS },
      jobTimeoutMs: config.jobTimeoutMs,
      pollMs: config.pollMs,
    });
    console.log(JSON.stringify({
      tool: "aero-product-smoke",
      schema: SMOKE_SCHEMA,
      participant: config.participantId,
      apiBase: config.apiBase,
      ...summary,
    }, null, 2));
  } catch (error) {
    console.error(`[product-smoke] ${error.message}`);
    if (lines.length > 0) console.error(`[product-smoke] api tail: ${lines.slice(-5).join(" | ").slice(0, 500)}`);
    process.exitCode = 1;
  } finally {
    await stopChild(child);
  }
};

const invokedDirectly = (() => {
  try {
    return resolve(process.argv[1] ?? "") === fileURLToPath(import.meta.url);
  } catch { return false; }
})();

if (invokedDirectly) await main();
