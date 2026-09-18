// Release smoke: one bounded end-to-end pass over the actual public product path.
//
// Steps (all against loopback, all bounded, fail-closed with E2E_* codes):
//   1. isolated temp job root + summary dir
//   2. product doctor in machine-readable mode (`doctor.mjs --json`)
//   3. start the local stack with the USER's command (`stack.mjs start`) in background
//   4. readiness wait (API /health + worker capabilities, web serving) <= ~120s
//   5. capabilities + participant manifest over the public API
//   6. submit one tiny deterministic rotor-campbell analysis (non-deferred)
//   7. observe the real job lifecycle (status poll + persisted events + SSE) to terminal
//   8. result metadata: source/fidelity/provenance + manifest ids
//   9. artifact list, hash-verified download, and export of one registered artifact
//  10. one read-only MCP call (capabilities.inspect + job.inspect) vs the live API
//  11. UI root via plain HTTP GET (status + marker) and API-backed workbench state
//  12. shutdown through the stack's own shutdown path (terminate the CLI whose
//      exit sweep stops owned services in reverse order)
//  13. verify no owned children remain (stack CLI, api, web, MCP); owned-only
//      fallback kill, then fail closed if anything owned survives.
//
// Opt-in `--native-smoke` runs one tiny native benchmark (cell-spm-discharge or
// rotor-modal, whichever capability is ready) through the same job/result path.
// Without the flag, or without a ready capability, it reports SKIPPED with a
// reason and never substitutes analytical output.
//
// Trust-boundary assertions (analytical!=native, unknown artifacts unfetchable,
// arbitrary command/path rejected, cancelled jobs expose no trusted success)
// run against the live stack and fail the gate on any deviation.
//
// This module never touches Docker, never scans or kills foreign processes,
// and never writes inside the repository (summary goes to an isolated temp dir
// or $AERO_E2E_SUMMARY_DIR for CI artifact upload).
import { spawn, spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdtempSync, mkdirSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { readProcessTreePids } from "../../packages/solver-contracts/src/scheduler.ts";
import { SMOKE_INPUTS, SMOKE_PARTICIPANT } from "./product-smoke.mjs";

export const E2E_SCHEMA = 1;

/** Tiny deterministic analysis for the mandatory path (ross, seconds-scale). */
export const E2E_PARTICIPANT = SMOKE_PARTICIPANT;
export const E2E_INPUTS = SMOKE_INPUTS;

export const TERMINAL_STATES = Object.freeze(["COMPLETED", "FAILED", "CANCELLED"]);

/** Served-workbench marker: <title> from apps/web/src/app/layout.tsx metadata. */
export const UI_MARKER = "Aero Workbench";

export const E2E_READY_TIMEOUT_MS_DEFAULT = 120_000;
export const E2E_JOB_TIMEOUT_MS_DEFAULT = 240_000;
export const E2E_OVERALL_TIMEOUT_MS_DEFAULT = 240_000;
export const E2E_POLL_MS_DEFAULT = 1_000;
export const E2E_FETCH_TIMEOUT_MS = 30_000;
export const E2E_UI_TIMEOUT_MS = 15_000;
export const E2E_STOP_TIMEOUT_MS = 15_000;
export const E2E_ORPHAN_GRACE_MS = 10_000;

/**
 * Opt-in native benchmark candidates in preference order, each with minimal
 * valid inputs. The gate picks the first whose capability is ready and
 * reports SKIPPED with reason when none is.
 */
export const NATIVE_SMOKE_CANDIDATES = Object.freeze([
  Object.freeze({
    participantId: "cell-spm-discharge",
    inputs: Object.freeze({
      model: "spm",
      parameter_set: "Chen2020",
      discharge_current_a: 1.0,
      duration_s: 60.0,
      n_series: 1,
      n_parallel: 1,
    }),
  }),
  Object.freeze({
    participantId: "rotor-modal",
    inputs: Object.freeze({
      shaft_length_m: 1.5,
      shaft_diameter_m: 0.05,
      n_elements: 4,
      bearing_stiffness_n_m: 1e8,
      speed_rpm: 6000.0,
    }),
  }),
]);

const e2eError = (code, detail) => new Error(`${code}:${detail}`);

/** Earliest deadline: a phase never outlives the overall release-smoke budget. */
export const boundedDeadline = (phaseDeadline, overallDeadline) => Math.min(phaseDeadline, overallDeadline);

export const parseArgs = (argv) => {
  const parsed = {
    apiPort: 18233,
    webPort: 13233,
    readyTimeoutMs: E2E_READY_TIMEOUT_MS_DEFAULT,
    jobTimeoutMs: E2E_JOB_TIMEOUT_MS_DEFAULT,
    overallTimeoutMs: E2E_OVERALL_TIMEOUT_MS_DEFAULT,
    summaryDir: null,
    nativeSmoke: false,
    help: false,
  };
  const args = [...argv];
  for (let index = 0; index < args.length; index += 1) {
    const arg = args[index];
    if (arg === "--help" || arg === "-h") return { ...parsed, help: true };
    if (arg === "--native-smoke") {
      parsed.nativeSmoke = true;
      continue;
    }
    if (arg === "--api-port" || arg === "--web-port" || arg === "--ready-timeout-ms" ||
        arg === "--job-timeout-ms" || arg === "--overall-timeout-ms" || arg === "--summary-dir") {
      const raw = args[index + 1];
      if (raw === undefined) throw e2eError("E2E_USAGE", `missing value for ${arg}`);
      index += 1;
      if (arg === "--summary-dir") {
        if (!raw.trim()) throw e2eError("E2E_USAGE", "invalid --summary-dir: expected a non-empty path");
        parsed.summaryDir = raw;
        continue;
      }
      const isPort = arg === "--api-port" || arg === "--web-port";
      const value = Number(raw);
      const valid = isPort
        ? Number.isInteger(value) && value >= 1 && value <= 65535
        : Number.isInteger(value) && value > 0;
      if (!valid) throw e2eError("E2E_USAGE", `invalid ${arg}=${JSON.stringify(raw)}`);
      if (arg === "--api-port") parsed.apiPort = value;
      else if (arg === "--web-port") parsed.webPort = value;
      else if (arg === "--ready-timeout-ms") parsed.readyTimeoutMs = value;
      else if (arg === "--job-timeout-ms") parsed.jobTimeoutMs = value;
      else parsed.overallTimeoutMs = value;
      continue;
    }
    throw e2eError("E2E_USAGE", `unknown argument: ${arg}`);
  }
  return parsed;
};

const parsePortEnv = (raw, name, fallback) => {
  if (raw === undefined || raw === null || raw === "") return fallback;
  const port = Number(raw);
  if (!Number.isInteger(port) || port < 1 || port > 65535) {
    throw e2eError("E2E_USAGE", `invalid ${name}=${JSON.stringify(raw)}: expected an integer port 1-65535`);
  }
  return port;
};

export const resolveConfig = ({ argv, env = {}, root }) => {
  const parsed = parseArgs(argv);
  const apiPort = parsePortEnv(env.AERO_E2E_API_PORT, "AERO_E2E_API_PORT", parsed.apiPort);
  const webPort = parsePortEnv(env.AERO_E2E_WEB_PORT, "AERO_E2E_WEB_PORT", parsed.webPort);
  const jobRoot = env.AEROWORKBENCH_JOB_ROOT?.trim()
    ? env.AEROWORKBENCH_JOB_ROOT.trim()
    : mkdtempSync(join(tmpdir(), "aero-e2e-jobs-"));
  const summaryDir = parsed.summaryDir
    ?? (env.AERO_E2E_SUMMARY_DIR?.trim() ? env.AERO_E2E_SUMMARY_DIR.trim() : mkdtempSync(join(tmpdir(), "aero-e2e-summary-")));
  mkdirSync(summaryDir, { recursive: true });
  return {
    schema: E2E_SCHEMA,
    help: parsed.help,
    apiPort,
    webPort,
    readyTimeoutMs: parsed.readyTimeoutMs,
    jobTimeoutMs: parsed.jobTimeoutMs,
    overallTimeoutMs: parsed.overallTimeoutMs,
    pollMs: E2E_POLL_MS_DEFAULT,
    nativeSmoke: parsed.nativeSmoke,
    root,
    apiBase: `http://127.0.0.1:${apiPort}`,
    webBase: `http://127.0.0.1:${webPort}`,
    jobRoot,
    summaryDir,
    summaryPath: join(summaryDir, "product-e2e-summary.json"),
  };
};

/** First ready opt-in native candidate, or null when none is available. */
export const pickNativeCandidate = (capabilities) => {
  const ready = capabilities?.ready ?? [];
  for (const candidate of NATIVE_SMOKE_CANDIDATES) {
    if (ready.some((entry) => entry?.participant_id === candidate.participantId)) return candidate;
  }
  return null;
};

export const checkUiMarker = (html) =>
  typeof html === "string" && html.length > 0 && html.includes(UI_MARKER);

/** Parse `[api] spawned pid 123` style lines from the stack CLI output. */
export const pidFromSpawnLine = (line) => {
  const match = /\[(api|web|mcp)\] spawned pid (\d+)/.exec(line ?? "");
  if (!match) return null;
  return { service: match[1], pid: Number(match[2]) };
};

export const buildSummary = (fields = {}) => ({
  tool: "aero-product-e2e",
  schema: E2E_SCHEMA,
  decidedAt: new Date().toISOString(),
  commitSha: fields.commitSha ?? null,
  platform: fields.platform ?? `${process.platform}-${process.arch}`,
  nodeVersion: fields.nodeVersion ?? process.version,
  apiBase: fields.apiBase ?? null,
  webBase: fields.webBase ?? null,
  doctor: fields.doctor ?? null,
  jobId: fields.jobId ?? null,
  resultId: fields.resultId ?? null,
  source: fields.source ?? null,
  fidelity: fields.fidelity ?? null,
  artifactDigests: fields.artifactDigests ?? [],
  trustChecks: fields.trustChecks ?? [],
  mcp: fields.mcp ?? null,
  ui: fields.ui ?? null,
  apiState: fields.apiState ?? null,
  nativeSmoke: fields.nativeSmoke ?? { status: "SKIPPED", reason: "--native-smoke not passed" },
  shutdown: fields.shutdown ?? { clean: false, stopped: [], orphans: [] },
  error: fields.error ?? null,
});

// ---------------------------------------------------------------------------
// Public-API phase helpers (each fetch carries an explicit timeout).
// ---------------------------------------------------------------------------

const apiJson = async (method, url, body, timeoutMs = E2E_FETCH_TIMEOUT_MS) => {
  const response = await fetch(url, {
    method,
    headers: body ? { "content-type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
    signal: AbortSignal.timeout(timeoutMs),
  });
  let payload = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }
  return { status: response.status, payload };
};

export const submitJob = async (apiBase, body) => {
  const submitted = await apiJson("POST", `${apiBase}/v1/native/analyses`, body);
  if (submitted.status !== 202 || typeof submitted.payload?.job_id !== "string") {
    throw e2eError("E2E_SUBMIT_FAILED",
      `submit returned ${submitted.status}: ${JSON.stringify(submitted.payload).slice(0, 300)}`);
  }
  return submitted.payload.job_id;
};

export const pollJobState = async (apiBase, jobId, { deadlineMs, pollMs, now = () => Date.now() }) => {
  for (;;) {
    const status = await apiJson("GET", `${apiBase}/v1/native/analyses/${jobId}`);
    if (status.status !== 200) {
      throw e2eError("E2E_STATUS_FAILED", `status for ${jobId} returned ${status.status}`);
    }
    if (TERMINAL_STATES.includes(status.payload?.state)) return status.payload;
    if (now() >= deadlineMs) {
      throw e2eError("E2E_JOB_TIMEOUT", `job ${jobId} stuck in ${status.payload?.state}`);
    }
    await new Promise((resolveSleep) => setTimeout(resolveSleep, pollMs));
  }
};

export const fetchEvents = async (apiBase, jobId) => {
  const events = await apiJson("GET", `${apiBase}/v1/native/analyses/${jobId}/events`);
  if (events.status !== 200 || !Array.isArray(events.payload?.events)) {
    throw e2eError("E2E_EVENTS_FAILED", `events for ${jobId} returned ${events.status}`);
  }
  return events.payload.events;
};

export const fetchResultBundle = async (apiBase, jobId) => {
  const [results, manifest, provenance] = await Promise.all([
    apiJson("GET", `${apiBase}/v1/native/results/${jobId}`),
    apiJson("GET", `${apiBase}/v1/native/results/${jobId}/manifest`),
    apiJson("GET", `${apiBase}/v1/native/provenance/${jobId}`),
  ]);
  return { results, manifest, provenance };
};

// ---------------------------------------------------------------------------
// Orchestration.
// ---------------------------------------------------------------------------

const sleep = (ms) => new Promise((resolveSleep) => setTimeout(resolveSleep, ms));

const runWithTimeout = async (label, code, promise, timeoutMs, onTimeout) => {
  let timer = null;
  try {
    const outcome = await Promise.race([
      promise,
      new Promise((_, reject) => {
        timer = setTimeout(() => {
          try {
            onTimeout?.();
          } catch {
            // Best effort only; the timeout error below decides.
          }
          reject(e2eError(code, `${label} exceeded ${timeoutMs}ms`));
        }, timeoutMs);
      }),
    ]);
    return outcome;
  } finally {
    if (timer) clearTimeout(timer);
  }
};

const commitSha = () => {
  try {
    const out = spawnSync("git", ["rev-parse", "HEAD"], { encoding: "utf8", timeout: 15_000 });
    const sha = String(out.stdout ?? "").trim();
    return /^[a-f0-9]{40}$/.test(sha) ? sha : "unknown";
  } catch {
    return "unknown";
  }
};

const runDoctor = async (root, timeoutMs = 100_000) => {
  const child = spawn(process.execPath, [join(root, "scripts", "platform", "doctor.mjs"), "--json"], {
    shell: false,
    windowsHide: true,
    stdio: ["ignore", "pipe", "pipe"],
  });
  let stdout = "";
  let stderr = "";
  child.stdout?.on("data", (chunk) => { stdout += String(chunk); });
  child.stderr?.on("data", (chunk) => { stderr += String(chunk); });
  const exit = await runWithTimeout("E2E_DOCTOR_TIMEOUT", "doctor --json", new Promise((resolveExit) => {
    child.once("error", () => resolveExit("error"));
    child.once("exit", (code) => resolveExit(code));
  }), Math.max(1, timeoutMs), () => { try { child.kill("SIGKILL"); } catch { /* bounded */ } });
  let report = null;
  try {
    report = JSON.parse(stdout.trim().slice(stdout.indexOf("{")));
  } catch {
    report = null;
  }
  if (report?.tool !== "aero-doctor") {
    throw e2eError("E2E_DOCTOR_FAILED", `doctor produced no machine-readable report${stderr ? `: ${stderr.slice(0, 200)}` : ""}`);
  }
  if (!report.baselineReady) {
    const blocked = (report.checks ?? []).filter((check) => check.tier === "baseline" && check.state === "failed").map((check) => check.id);
    throw e2eError("E2E_DOCTOR_BLOCKED", `product baseline is blocked: ${blocked.join(", ") || "see doctor report"}`);
  }
  return { exit, report };
};

const startStackCli = ({ root, config }) => {
  const child = spawn(process.execPath, [join(root, "scripts", "platform", "stack.mjs"), "start"], {
    cwd: root,
    shell: false,
    windowsHide: true,
    stdio: ["ignore", "pipe", "pipe"],
    env: {
      ...process.env,
      AERO_API_PORT: String(config.apiPort),
      AERO_WEB_PORT: String(config.webPort),
      AEROWORKBENCH_JOB_ROOT: config.jobRoot,
      AERO_STACK_READY_TIMEOUT_MS: String(Math.max(config.readyTimeoutMs - 10_000, 30_000)),
    },
  });
  const lines = [];
  const spawned = new Map();
  const collect = (chunk) => {
    for (const raw of String(chunk).split(/\r?\n/)) {
      if (!raw) continue;
      lines.push(raw);
      if (lines.length > 200) lines.shift();
      const hit = pidFromSpawnLine(raw);
      if (hit && !spawned.has(hit.service)) spawned.set(hit.service, hit.pid);
      process.stdout.write(`[e2e:stack] ${raw}\n`);
    }
  };
  child.stdout?.on("data", collect);
  child.stderr?.on("data", collect);
  return { child, lines, spawned };
};

const childExited = (child) => child.exitCode !== null || child.signalCode !== null;

const waitForStackReady = async ({ apiBase, webBase, handle, deadlineMs, pollMs }) => {
  let apiOk = false;
  let workerOk = false;
  let webOk = false;
  for (;;) {
    if (childExited(handle.child)) {
      throw e2eError("E2E_STACK_EXITED",
        `stack CLI exited (code ${handle.child.exitCode ?? "unknown"}) before readiness; tail: ${handle.lines.slice(-5).join(" | ").slice(0, 500)}`);
    }
    try {
      const health = await apiJson("GET", `${apiBase}/health`, undefined, 5_000);
      apiOk = apiOk || (health.status >= 200 && health.status < 300);
    } catch { /* warming */ }
    try {
      const caps = await apiJson("GET", `${apiBase}/v1/native/capabilities`, undefined, 5_000);
      workerOk = workerOk || caps.status === 200;
    } catch { /* warming */ }
    try {
      const web = await fetch(webBase, { signal: AbortSignal.timeout(5_000) });
      await web.arrayBuffer().catch(() => null);
      webOk = webOk || web.status < 500;
    } catch { /* warming */ }
    if (apiOk && workerOk && webOk) return;
    if (Date.now() >= deadlineMs) {
      throw e2eError("E2E_STACK_TIMEOUT",
        `stack not ready (api=${apiOk} worker=${workerOk} web=${webOk}); tail: ${handle.lines.slice(-5).join(" | ").slice(0, 500)}`);
    }
    await sleep(pollMs);
  }
};

const pidAlive = (pid) => {
  try {
    process.kill(pid, 0);
    return true;
  } catch {
    return false;
  }
};

/**
 * Owned process IDs for the stack: the CLI root plus everything the OS reports
 * as its descendants, unioned with any `[service] spawned pid N` lines the CLI
 * printed. The tree walk is authoritative because the CLI's own children are
 * what survive an abrupt CLI exit and must be accounted for.
 */
export const captureOwnedPids = async (rootPid, spawned) => {
  const owned = new Set();
  const fromLines = spawned instanceof Map ? [...spawned.values()] : Array.isArray(spawned) ? spawned : [];
  for (const pid of fromLines) if (Number.isInteger(pid) && pid > 0) owned.add(pid);
  if (Number.isInteger(rootPid) && rootPid > 0) {
    owned.add(rootPid);
    try {
      for (const pid of await readProcessTreePids(rootPid)) owned.add(pid);
    } catch {
      // Tree walk is best-effort; the CLI root is still tracked.
    }
  }
  return [...owned];
};

/** Descendant PIDs (owned minus the CLI root) still alive. */
export const liveDescendants = (owned, rootPid) =>
  owned.filter((pid) => Number.isInteger(pid) && pid > 0 && pid !== rootPid && pidAlive(pid));

const stopStackCli = async (handle, { mcpPid }) => {
  const stopped = [];
  const rootPid = handle.child.pid;
  const owned = await captureOwnedPids(rootPid, handle.spawned);
  if (Number.isInteger(mcpPid)) owned.push(mcpPid);

  // Windows cannot deliver a catchable termination signal to the CLI, so an
  // abrupt `child.kill()` would orphan the CLI's own services (this was the
  // pre-existing leak). `taskkill /T` terminates the whole owned tree from the
  // project-owned root; POSIX keeps the graceful SIGTERM path.
  if (process.platform === "win32") {
    try {
      spawnSync("taskkill.exe", ["/PID", String(rootPid), "/T", "/F"], { stdio: "ignore", timeout: E2E_STOP_TIMEOUT_MS });
    } catch { /* fall through to per-PID sweep */ }
  } else {
    try {
      handle.child.kill("SIGTERM");
    } catch { /* already gone */ }
  }
  const exitDeadline = Date.now() + E2E_STOP_TIMEOUT_MS;
  while (!childExited(handle.child) && Date.now() < exitDeadline) await sleep(100);
  const stackGone = childExited(handle.child);
  stopped.push(`stack-cli:${stackGone ? "exited" : "kill-sent"}`);

  let orphans = liveDescendants(owned, rootPid);
  if (orphans.length > 0) {
    await sleep(2_000);
    orphans = liveDescendants(owned, rootPid);
  }
  // `fallback` means the primary shutdown path left descendants behind and a
  // per-PID sweep was required; the Windows tree kill itself is primary.
  let fallback = false;
  if (orphans.length > 0) {
    fallback = true;
    for (const pid of orphans) {
      try {
        if (process.platform === "win32") {
          spawnSync("taskkill.exe", ["/PID", String(pid), "/T", "/F"], { stdio: "ignore", timeout: 10_000 });
        } else {
          process.kill(pid, "SIGKILL");
        }
      } catch { /* re-polled below */ }
    }
    const verifyUntil = Date.now() + E2E_ORPHAN_GRACE_MS;
    while (liveDescendants(owned, rootPid).length > 0 && Date.now() < verifyUntil) await sleep(200);
    orphans = liveDescendants(owned, rootPid);
  }
  return {
    stopped,
    orphans,
    ownedCount: owned.length - (Number.isInteger(mcpPid) ? 1 : 0),
    clean: stackGone && orphans.length === 0,
    fallback,
  };
};

/**
 * One read-only MCP call against the live API over raw stdio JSON-RPC (the
 * same framing the #7 stdio E2E uses, without SDK client machinery so the
 * E2E owns the server PID end to end). Returns the owned PID for the orphan
 * check; the caller always terminates it.
 */
const mcpPhase = async ({ root, apiBase, jobId }) => {
  const child = spawn(process.execPath, [join(root, "mcp", "engineering", "server.ts")], {
    cwd: root,
    shell: false,
    windowsHide: true,
    stdio: ["pipe", "pipe", "pipe"],
    env: {
      ...process.env,
      AERO_API_BASE_URL: apiBase,
      AERO_OWNER_ID: "e2e-release",
      AERO_ALLOW_MUTATIONS: "0",
      AERO_ALLOW_DESTRUCTIVE: "0",
      AERO_ALLOW_REMOTE_COMPUTE: "0",
      AERO_REMOTE_COST_CEILING_USD: "0",
    },
  });
  const mcpPid = child.pid ?? null;
  const lines = [];
  child.stdout?.on("data", (chunk) => {
    for (const raw of String(chunk).split(/\r?\n/)) {
      if (raw.trim()) lines.push(raw.trim());
    }
  });
  child.stderr?.on("data", () => { /* diagnostics stay off the protocol stream */ });
  const send = (frame) => child.stdin?.write(`${JSON.stringify(frame)}\n`);
  const waitForId = async (id, deadlineMs) => {
    for (;;) {
      const hit = lines.map((line) => {
        try {
          return JSON.parse(line);
        } catch {
          return null;
        }
      }).find((message) => message?.id === id);
      if (hit) {
        if (hit.error) throw e2eError("E2E_MCP_FAILED", `MCP call ${id} answered with error: ${JSON.stringify(hit.error).slice(0, 200)}`);
        return hit.result;
      }
      if (childExited(child)) throw e2eError("E2E_MCP_FAILED", `MCP server exited before answering ${id}`);
      if (Date.now() >= deadlineMs) throw e2eError("E2E_MCP_FAILED", `MCP call ${id} timed out`);
      await sleep(50);
    }
  };
  try {
    send({
      jsonrpc: "2.0", id: "e2e-init", method: "initialize",
      params: {
        protocolVersion: "2025-06-18", capabilities: {},
        clientInfo: { name: "product-e2e", version: "0.1.0" },
      },
    });
    await waitForId("e2e-init", Date.now() + E2E_FETCH_TIMEOUT_MS);
    send({ jsonrpc: "2.0", method: "notifications/initialized" });
    send({
      jsonrpc: "2.0", id: "e2e-caps", method: "tools/call",
      params: { name: "capabilities.inspect", arguments: {} },
    });
    const caps = await waitForId("e2e-caps", Date.now() + E2E_FETCH_TIMEOUT_MS);
    if (caps?.isError) throw e2eError("E2E_MCP_FAILED", "capabilities.inspect returned isError");
    if (!JSON.stringify(caps).includes("rotor-campbell")) {
      throw e2eError("E2E_MCP_FAILED", "capabilities.inspect did not reflect the live API participants");
    }
    send({
      jsonrpc: "2.0", id: "e2e-job", method: "tools/call",
      params: { name: "job.inspect", arguments: { jobId } },
    });
    const inspected = await waitForId("e2e-job", Date.now() + E2E_FETCH_TIMEOUT_MS);
    if (inspected?.isError) throw e2eError("E2E_MCP_FAILED", "job.inspect returned isError");
    if (!JSON.stringify(inspected).includes("COMPLETED")) {
      throw e2eError("E2E_MCP_FAILED", "job.inspect did not reflect the terminal COMPLETED state");
    }
    return { tools: ["capabilities.inspect", "job.inspect"], ok: true, mcpPid };
  } finally {
    try {
      child.stdin?.end();
    } catch { /* bounded */ }
    const exitDeadline = Date.now() + 10_000;
    while (!childExited(child) && Date.now() < exitDeadline) await sleep(100);
    if (!childExited(child)) {
      try {
        child.kill("SIGKILL");
      } catch { /* orphan check decides */ }
    }
  }
};

const printUsage = () => {
  console.log("Usage: node scripts/platform/product-e2e.mjs [--api-port N] [--web-port N]");
  console.log("  [--ready-timeout-ms N] [--job-timeout-ms N] [--overall-timeout-ms N] [--summary-dir PATH] [--native-smoke]");
  console.log("");
  console.log("Bounded release smoke over the real product path: isolated dirs, doctor,");
  console.log("`stack.mjs start`, readiness, capabilities, one tiny rotor-campbell job to");
  console.log("a verified native_solver envelope, artifact export, one read-only MCP call,");
  console.log("UI root + API-backed state, trust assertions, shutdown, orphan check.");
};

const main = async () => {
  const root = resolve(fileURLToPath(new URL(".", import.meta.url)), "..", "..");
  let config;
  try {
    config = resolveConfig({ argv: process.argv.slice(2), env: process.env, root });
  } catch (error) {
    console.error(`[product-e2e] ${error.message}`);
    printUsage();
    process.exitCode = 2;
    return;
  }
  if (config.help) {
    printUsage();
    return;
  }
  const sha = commitSha();
  const summary = { commitSha: sha };
  const overallDeadline = Date.now() + config.overallTimeoutMs;
  const ensureBudget = (label) => {
    if (Date.now() >= overallDeadline) {
      throw e2eError("E2E_OVERALL_TIMEOUT",
        `${label} exceeded the ${config.overallTimeoutMs}ms release-smoke budget`);
    }
  };
  let handle = null;
  let shut = false;
  const shutdownOnce = async (mcpPid) => {
    if (shut) return { stopped: [], orphans: [], clean: false, fallback: false };
    shut = true;
    if (!handle) return { stopped: [], orphans: [], clean: true, fallback: false };
    return stopStackCli(handle, { mcpPid });
  };
  let mcpPid = null;
  let failure = null;
  try {
    console.log(`[product-e2e] isolated job root: ${config.jobRoot}`);
    ensureBudget("doctor");
    const doctor = await runDoctor(root, boundedDeadline(100_000, overallDeadline - Date.now()));
    summary.doctor = {
      baselineReady: doctor.report.baselineReady,
      checks: doctor.report.checks.length,
      solversReady: doctor.report.solvers.ready,
      solversUnavailable: doctor.report.solvers.unavailable,
    };
    console.log(`[product-e2e] doctor baseline ready (${summary.doctor.checks} checks)`);

    ensureBudget("stack startup");
    handle = startStackCli({ root, config });
    console.log(`[product-e2e] stack CLI pid ${handle.child.pid}; waiting for readiness`);
    await waitForStackReady({
      apiBase: config.apiBase,
      webBase: config.webBase,
      handle,
      deadlineMs: boundedDeadline(Date.now() + config.readyTimeoutMs, overallDeadline),
      pollMs: config.pollMs,
    });
    console.log("[product-e2e] stack ready");

    ensureBudget("capabilities");
    const capabilities = await apiJson("GET", `${config.apiBase}/v1/native/capabilities`);
    if (capabilities.status !== 200) throw e2eError("E2E_CAPABILITIES_FAILED", `capabilities returned ${capabilities.status}`);
    const readyIds = (capabilities.payload?.ready ?? []).map((entry) => entry?.participant_id);
    if (!readyIds.includes(E2E_PARTICIPANT)) {
      throw e2eError("E2E_CAPABILITY_NOT_READY",
        `${E2E_PARTICIPANT} is not ready (ready=[${readyIds.join(", ")}]); refusing to fake a result`);
    }
    const participants = await apiJson("GET", `${config.apiBase}/v1/native/participants`);
    const known = (participants.payload?.participants ?? []).some((entry) => entry?.participant_id === E2E_PARTICIPANT);
    if (!known) throw e2eError("E2E_PARTICIPANT_MISSING", `${E2E_PARTICIPANT} is not in the participant manifest`);

    ensureBudget("job submission");
    const jobId = await submitJob(config.apiBase, { participant_id: E2E_PARTICIPANT, inputs: { ...E2E_INPUTS } });
    console.log(`[product-e2e] submitted ${jobId}`);
    const final = await pollJobState(config.apiBase, jobId, {
      deadlineMs: boundedDeadline(Date.now() + config.jobTimeoutMs, overallDeadline),
      pollMs: config.pollMs,
    });
    if (final.state !== "COMPLETED") {
      throw e2eError("E2E_JOB_FAILED",
        `job ${jobId} ended ${final.state} (${final.error_code ?? "no code"}: ${(final.error_detail ?? "").slice(0, 200)})`);
    }
    const events = await fetchEvents(config.apiBase, jobId);
    const sequences = events.map((event) => event.sequence);
    if (events.length < 2 || sequences.some((s) => !Number.isInteger(s)) ||
        sequences.some((s, i) => i > 0 && s <= sequences[i - 1])) {
      throw e2eError("E2E_EVENTS_FAILED", `job ${jobId} has no well-ordered persisted event stream`);
    }
    if (events[0]?.state !== "QUEUED" || events[events.length - 1]?.state !== "COMPLETED") {
      throw e2eError("E2E_EVENTS_FAILED", `job ${jobId} event stream does not span QUEUED..COMPLETED`);
    }
    const sse = await fetch(`${config.apiBase}/v1/native/analyses/${jobId}/events`, {
      headers: { accept: "text/event-stream" },
      signal: AbortSignal.timeout(E2E_FETCH_TIMEOUT_MS),
    });
    const sseText = await sse.text();
    if (!sse.headers.get("content-type")?.startsWith("text/event-stream") || !sseText.includes("event: progress")) {
      throw e2eError("E2E_EVENTS_FAILED", `job ${jobId} SSE replay is not backed by persisted transitions`);
    }

    const bundle = await fetchResultBundle(config.apiBase, jobId);
    if (bundle.results.status !== 200 || bundle.results.payload?.source !== "native_solver") {
      throw e2eError("E2E_RESULT_UNVERIFIED",
        `job ${jobId} has no native_solver envelope: ${JSON.stringify(bundle.results.payload).slice(0, 300)}`);
    }
    if (bundle.results.payload?.fidelity !== "beam-campbell") {
      throw e2eError("E2E_RESULT_UNVERIFIED", `job ${jobId} fidelity is not beam-campbell`);
    }
    const manifest = bundle.manifest.status === 200 ? bundle.manifest.payload : null;
    if (!manifest || !/^[a-f0-9]{64}$/.test(manifest.result_id ?? "")) {
      throw e2eError("E2E_RESULT_UNVERIFIED", `job ${jobId} manifest carries no 64-hex result id`);
    }
    if (final.run_id && bundle.results.payload?.run_id !== final.run_id) {
      throw e2eError("E2E_RESULT_UNVERIFIED", `job ${jobId} envelope run id does not match job status`);
    }
    const provenance = bundle.provenance.status === 200 ? bundle.provenance.payload : null;
    const eventTypes = (provenance?.events ?? []).map((event) => event.event_type ?? event.state);
    if (!Array.isArray(provenance?.events) || provenance.events.length === 0 ||
        !eventTypes.includes("native.launch-accepted") || !eventTypes.includes("native.result-recorded")) {
      throw e2eError("E2E_RESULT_UNVERIFIED", `job ${jobId} published no launch/result provenance pair`);
    }
    summary.jobId = jobId;
    summary.resultId = manifest.result_id;
    summary.source = bundle.results.payload.source;
    summary.fidelity = bundle.results.payload.fidelity;

    const artifacts = await apiJson("GET", `${config.apiBase}/v1/native/artifacts/${jobId}`);
    const entries = artifacts.payload?.artifacts ?? [];
    if (artifacts.status !== 200 || entries.length === 0) {
      throw e2eError("E2E_ARTIFACT_MISSING", `job ${jobId} registered no fetchable artifacts`);
    }
    const first = entries[0];
    const download = await fetch(
      `${config.apiBase}/v1/native/artifacts/${jobId}/${encodeURIComponent(first.name)}`,
      { signal: AbortSignal.timeout(E2E_FETCH_TIMEOUT_MS) });
    const bytes = Buffer.from(await download.arrayBuffer());
    if (download.status !== 200 || bytes.length === 0) {
      throw e2eError("E2E_ARTIFACT_MISSING", `artifact ${first.name} of job ${jobId} is not downloadable`);
    }
    const digest = createHash("sha256").update(bytes).digest("hex");
    if (first.sha256 && first.sha256 !== digest) {
      throw e2eError("E2E_ARTIFACT_MISSING", `artifact ${first.name} digest mismatch (ledger vs bytes)`);
    }
    const exportPath = join(config.summaryDir, `export-${first.name}`);
    writeFileSync(exportPath, bytes);
    summary.artifactDigests = [{ name: first.name, sha256: digest, bytes: bytes.length, exportPath }];

    const workbench = await apiJson("GET", `${config.apiBase}/api/v1/workbench/state`);
    if (workbench.status !== 200 ||
        !Array.isArray(workbench.payload?.available_result_sources) ||
        !workbench.payload.available_result_sources.includes("native_solver")) {
      throw e2eError("E2E_API_STATE_FAILED", "API-backed workbench state did not load");
    }
    summary.apiState = { ok: true, sources: workbench.payload.available_result_sources };

    ensureBudget("trust boundaries");
    const trustChecks = [];
    const demos = await apiJson("POST", `${config.apiBase}/v1/demos/edf`, {});
    if (demos.status !== 200 || demos.payload?.result_type !== "analytical" || demos.payload?.native_solver_executed !== false) {
      throw e2eError("E2E_TRUST_FAILED", "analytical demo path is not honestly labelled (analytical!=native)");
    }
    trustChecks.push({ name: "analytical-cannot-claim-native", ok: true });

    const unknownArtifact = await fetch(
      `${config.apiBase}/v1/native/artifacts/${jobId}/e2e-no-such-artifact.json`,
      { signal: AbortSignal.timeout(E2E_FETCH_TIMEOUT_MS) });
    await unknownArtifact.arrayBuffer().catch(() => null);
    const unknownResult = await apiJson("GET", `${config.apiBase}/v1/native/results/${"0".repeat(32)}`);
    if (unknownArtifact.status !== 404 || unknownResult.status !== 404) {
      throw e2eError("E2E_TRUST_FAILED", "unknown artifact/result ids must be unfetchable (404)");
    }
    trustChecks.push({ name: "unknown-artifact-unfetchable", ok: true });

    const shellShaped = await apiJson("POST", `${config.apiBase}/v1/native/analyses`, {
      participant_id: E2E_PARTICIPANT, inputs: { ...E2E_INPUTS }, executable: "rm -rf /",
    });
    const unknownParticipant = await apiJson("POST", `${config.apiBase}/v1/native/analyses`, {
      participant_id: "no-such-participant", inputs: {},
    });
    const bogusFidelity = await apiJson("POST", `${config.apiBase}/v1/native/analyses`, {
      participant_id: E2E_PARTICIPANT, inputs: { ...E2E_INPUTS }, fidelity: "bogus-level",
    });
    if (shellShaped.status !== 422 || unknownParticipant.status !== 404 || bogusFidelity.status !== 422) {
      throw e2eError("E2E_TRUST_FAILED",
        `arbitrary command/path/participant/fidelity must be rejected (got ${shellShaped.status}/${unknownParticipant.status}/${bogusFidelity.status})`);
    }
    trustChecks.push({ name: "arbitrary-command-path-rejected", ok: true });

    const deferredId = await submitJob(config.apiBase, {
      participant_id: "cell-spm-discharge",
      inputs: { ...(NATIVE_SMOKE_CANDIDATES[0].inputs) },
      deferred: true,
    });
    const cancelled = await apiJson("POST", `${config.apiBase}/v1/native/analyses/${deferredId}/cancel`);
    if (cancelled.payload?.state !== "CANCELLED") {
      throw e2eError("E2E_TRUST_FAILED", `deferred job ${deferredId} could not be cancelled`);
    }
    const cancelledResult = await apiJson("GET", `${config.apiBase}/v1/native/results/${deferredId}`);
    if (cancelledResult.status !== 404 || cancelledResult.payload?.detail?.code !== "RESULT_NOT_PUBLISHED") {
      throw e2eError("E2E_TRUST_FAILED", "cancelled job must expose no trusted successful result");
    }
    trustChecks.push({ name: "cancelled-job-exposes-no-trusted-success", ok: true });
    summary.trustChecks = trustChecks;

    ensureBudget("MCP call");
    const mcp = await mcpPhase({ root, apiBase: config.apiBase, jobId });
    mcpPid = mcp.mcpPid;
    summary.mcp = { tools: mcp.tools, ok: mcp.ok };
    console.log("[product-e2e] read-only MCP call against the live API passed");

    ensureBudget("UI root");
    const uiResponse = await fetch(config.webBase, { signal: AbortSignal.timeout(E2E_UI_TIMEOUT_MS) });
    const uiHtml = await uiResponse.text();
    if (uiResponse.status !== 200 || !checkUiMarker(uiHtml)) {
      throw e2eError("E2E_UI_FAILED",
        `UI root returned ${uiResponse.status} without the workbench marker`);
    }
    summary.ui = { status: uiResponse.status, markerFound: true };
    console.log("[product-e2e] UI root + API-backed state load passed");

    if (!config.nativeSmoke) {
      summary.nativeSmoke = { status: "SKIPPED", reason: "--native-smoke not passed" };
    } else {
      const candidate = pickNativeCandidate(capabilities.payload);
      if (!candidate) {
        summary.nativeSmoke = {
          status: "SKIPPED",
          reason: `no verified native solver capability ready (ready=[${readyIds.join(", ")}])`,
        };
      } else {
        const nativeId = await submitJob(config.apiBase, {
          participant_id: candidate.participantId, inputs: { ...candidate.inputs },
        });
        const nativeFinal = await pollJobState(config.apiBase, nativeId, {
          deadlineMs: boundedDeadline(Date.now() + config.jobTimeoutMs, overallDeadline),
          pollMs: config.pollMs,
        });
        const nativeEnvelope = await apiJson("GET", `${config.apiBase}/v1/native/results/${nativeId}`);
        if (nativeFinal.state !== "COMPLETED" || nativeEnvelope.payload?.source !== "native_solver") {
          throw e2eError("E2E_NATIVE_FAILED",
            `native smoke job ${nativeId} ended ${nativeFinal.state} without a native_solver envelope`);
        }
        summary.nativeSmoke = {
          status: "PASSED",
          participantId: candidate.participantId,
          jobId: nativeId,
          source: nativeEnvelope.payload.source,
          fidelity: nativeEnvelope.payload.fidelity ?? null,
        };
      }
    }
    console.log(`[product-e2e] native smoke: ${summary.nativeSmoke.status}${summary.nativeSmoke.reason ? ` (${summary.nativeSmoke.reason})` : ""}`);
  } catch (error) {
    failure = error;
  } finally {
    const shutdown = await shutdownOnce(mcpPid);
    summary.shutdown = shutdown;
    summary.apiBase = config.apiBase;
    summary.webBase = config.webBase;
    if (failure) summary.error = String(failure.message ?? failure);
    writeFileSync(config.summaryPath, `${JSON.stringify(summary, null, 2)}\n`);
    console.log(JSON.stringify(summary, null, 2));
    console.log(`[product-e2e] summary: ${config.summaryPath}`);
    if (shutdown.orphans.length > 0) {
      console.error(`[product-e2e] E2E_ORPHANED_CHILDREN: owned PIDs still alive: ${shutdown.orphans.join(", ")}`);
      process.exitCode = 1;
    } else if (failure) {
      console.error(`[product-e2e] ${failure.message}`);
      process.exitCode = 1;
    }
  }
};

const invokedDirectly = (() => {
  try {
    return resolve(process.argv[1] ?? "") === fileURLToPath(import.meta.url);
  } catch {
    return false;
  }
})();

if (invokedDirectly) await main();
