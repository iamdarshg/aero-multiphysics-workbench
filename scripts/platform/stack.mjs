// One-command local product stack: API + web UI, with optional MCP.
//
// Process orchestration and health management only. This module never changes
// UI behavior or solver physics, never launches a solver executable, and never
// uses Docker on the default path (infra/docker/compose.local.yml remains a
// manifest-only non-default intent).
//
// Product-service mapping after issue #2 (real API job lifecycle):
// - `api`: uvicorn serving services/api. The governed single-worker native job
//   lifecycle (NativeJobManager) runs in-process inside the API, so there is no
//   separate scheduler/worker service to orchestrate. The worker readiness gate
//   is a live GET of /v1/native/capabilities: the job path answers without any
//   solver being started.
// - `web`: the Next.js UI (dev server for `dev`, `next start` for `start`).
// - `mcp`: the stdio engineering server, only with --with-mcp / AERO_WITH_MCP.
//   Readiness is a real JSON-RPC `initialize` handshake, never spawn success.
//
// "Ready" is reported only after loopback gates actually respond. Shutdown
// terminates project-owned children in reverse dependency order (mcp, web,
// api) with a bounded grace period, then force-kills the observed process
// tree. Only PIDs observed under a service root are ever signalled.
import { spawn } from "node:child_process";
import { constants } from "node:fs";
import { access } from "node:fs/promises";
import { createConnection } from "node:net";
import { createRequire } from "node:module";
import { createInterface } from "node:readline";
import { delimiter, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { readProcessTreePids } from "../../packages/solver-contracts/src/scheduler.ts";

export const STACK_SCHEMA = 1;

/** Startup order; shutdown always runs this list in reverse. */
export const STARTUP_ORDER = Object.freeze(["api", "web", "mcp"]);

export const EXIT = Object.freeze({ OK: 0, FAILURE: 1, USAGE: 2, INTERRUPTED: 130 });

export const DEFAULTS = Object.freeze({
  host: "127.0.0.1",
  apiPort: 8000,
  webPort: 3000,
  readyTimeoutMs: 120_000,
  stopGraceMs: 5_000,
  mcpHandshakeMs: 15_000,
  pollMs: 250,
});

const PORT_LABELS = Object.freeze({ apiPort: "local API", webPort: "web UI" });

const stackError = (code, detail) => new Error(`${code}:${detail}`);

/** Parse CLI args. Throws STACK_USAGE on anything unrecognized. */
export const parseArgs = (argv) => {
  const args = [...argv];
  let mode = null;
  let withMcp = false;
  let readyTimeoutMs = null;
  let stopGraceMs = null;
  for (let index = 0; index < args.length; index += 1) {
    const arg = args[index];
    if (arg === "dev" || arg === "start") {
      if (mode) throw stackError("STACK_USAGE", `duplicate mode: ${arg}`);
      mode = arg;
    } else if (arg === "--with-mcp") {
      withMcp = true;
    } else if (arg === "--ready-timeout-ms") {
      readyTimeoutMs = args[index + 1];
      index += 1;
    } else if (arg === "--stop-grace-ms") {
      stopGraceMs = args[index + 1];
      index += 1;
    } else if (arg === "--help" || arg === "-h") {
      return { mode: null, withMcp: false, readyTimeoutMs: null, stopGraceMs: null, help: true };
    } else if (arg === "--docker") {
      throw stackError("STACK_USAGE",
        "--docker is not a default local path; the compose file is manifest-only intent (see infra/docker/compose.local.yml)");
    } else {
      throw stackError("STACK_USAGE", `unknown argument: ${arg} (usage: stack.mjs [dev|start] [--with-mcp])`);
    }
  }
  if (!mode) throw stackError("STACK_USAGE", "missing mode: expected `dev` or `start`");
  return { mode, withMcp, readyTimeoutMs, stopGraceMs, help: false };
};

const parsePort = (raw, envName, fallback) => {
  if (raw === undefined || raw === null || raw === "") return fallback;
  const port = Number(raw);
  if (!Number.isInteger(port) || port < 1 || port > 65535) {
    throw stackError("STACK_USAGE", `invalid ${envName}=${JSON.stringify(raw)}: expected an integer port 1-65535`);
  }
  return port;
};

const parsePositiveMs = (raw, name, fallback) => {
  if (raw === undefined || raw === null || raw === "") return fallback;
  const value = Number(raw);
  if (!Number.isFinite(value) || value <= 0) {
    throw stackError("STACK_USAGE", `invalid ${name}=${JSON.stringify(raw)}: expected a positive millisecond budget`);
  }
  return Math.floor(value);
};

const parseCommandOverride = (raw, envName) => {
  if (!raw) return null;
  let parsed;
  try {
    parsed = JSON.parse(raw);
  } catch {
    throw stackError("STACK_USAGE", `invalid ${envName}: expected a JSON argv array, e.g. ["node","-e","..."]`);
  }
  if (!Array.isArray(parsed) || parsed.length === 0 || parsed.some((part) => typeof part !== "string" || !part)) {
    throw stackError("STACK_USAGE", `invalid ${envName}: expected a non-empty JSON array of command strings`);
  }
  return [...parsed];
};

/**
 * Resolve the full stack configuration. Ports come from explicit env
 * overrides or the existing defaults; a port is never chosen at random so the
 * UI/API contract stays predictable.
 */
export const resolveConfig = ({ argv, env = {}, root, nextBin = "<next-bin>" }) => {
  const parsed = parseArgs(argv);
  const apiPort = parsePort(env.AERO_API_PORT, "AERO_API_PORT", DEFAULTS.apiPort);
  const webPort = parsePort(env.AERO_WEB_PORT, "AERO_WEB_PORT", DEFAULTS.webPort);
  const host = env.AERO_STACK_HOST?.trim() ? env.AERO_STACK_HOST.trim() : DEFAULTS.host;
  const readyTimeoutMs = parsePositiveMs(
    parsed.readyTimeoutMs ?? env.AERO_STACK_READY_TIMEOUT_MS, "AERO_STACK_READY_TIMEOUT_MS", DEFAULTS.readyTimeoutMs);
  const stopGraceMs = parsePositiveMs(
    parsed.stopGraceMs ?? env.AERO_STACK_STOP_GRACE_MS, "AERO_STACK_STOP_GRACE_MS", DEFAULTS.stopGraceMs);
  const mcpHandshakeMs = parsePositiveMs(
    env.AERO_STACK_MCP_HANDSHAKE_MS, "AERO_STACK_MCP_HANDSHAKE_MS", DEFAULTS.mcpHandshakeMs);
  const withMcp = parsed.withMcp || env.AERO_WITH_MCP === "1";
  const apiDir = join(root, "services", "api");
  const apiBase = `http://${host}:${apiPort}`;
  const apiCommand = parseCommandOverride(env.AERO_STACK_API_COMMAND, "AERO_STACK_API_COMMAND") ?? [
    "uv", "run", "--directory", apiDir,
    "uvicorn", "aeroworkbench_api.main:app",
    "--host", host, "--port", String(apiPort),
    ...(parsed.mode === "dev" ? ["--reload"] : []),
  ];
  const webCommand = parseCommandOverride(env.AERO_STACK_WEB_COMMAND, "AERO_STACK_WEB_COMMAND") ?? [
    process.execPath, nextBin, parsed.mode === "dev" ? "dev" : "start",
    "--port", String(webPort), "--hostname", host,
  ];
  const mcpCommand = parseCommandOverride(env.AERO_STACK_MCP_COMMAND, "AERO_STACK_MCP_COMMAND") ?? [
    process.execPath, join(root, "mcp", "engineering", "server.ts"),
  ];
  return {
    schema: STACK_SCHEMA,
    mode: parsed.mode,
    help: parsed.help,
    withMcp,
    root,
    host,
    apiPort,
    webPort,
    apiBase,
    webBase: `http://${host}:${webPort}`,
    apiHealthUrl: `${apiBase}/health`,
    apiCapabilitiesUrl: `${apiBase}/v1/native/capabilities`,
    readyTimeoutMs,
    stopGraceMs,
    mcpHandshakeMs,
    pollMs: DEFAULTS.pollMs,
    apiCommand,
    webCommand,
    mcpCommand,
    /** Extra env for the API child (PYTHONPATH); set by main, honoured by startStack. */
    apiExtraEnv: null,
  };
};

/** Resolve the Next.js CLI shell-free so `dev:all` never needs pnpm on PATH. */
export const resolveNextBin = (root) => {
  const requireFromWeb = createRequire(join(root, "apps", "web", "package.json"));
  return requireFromWeb.resolve("next/dist/bin/next");
};

/**
 * Rebuild the API import path from the repo's own pytest path config
 * (services/api/pyproject.toml `pythonpath`). Mirrors doctor.mjs so the
 * orchestrated `uvicorn` imports exactly what the repo's tests import.
 * Returns null when the config is unreadable; callers then fail honestly at
 * the health gate instead of guessing.
 */
export const resolveApiPythonPath = async ({ root, pathDelimiter = delimiter, readText }) => {
  const apiDir = join(root, "services", "api");
  let text;
  try {
    text = await (readText ?? ((path) => import("node:fs/promises").then((fs) => fs.readFile(path, "utf8"))))(join(apiDir, "pyproject.toml"));
  } catch {
    return null;
  }
  const match = /pythonpath\s*=\s*\[(.*?)\]/s.exec(text);
  if (!match) return null;
  const entries = [...match[1].matchAll(/"([^"]+)"/g)].map((entry) => entry[1]);
  if (entries.length === 0) return null;
  return entries.map((entry) => resolve(apiDir, entry)).join(pathDelimiter);
};

const portConflictMessage = (port, label, detail) => {
  const envName = label === PORT_LABELS.apiPort ? "AERO_API_PORT" : "AERO_WEB_PORT";
  return `port ${port} (${label}) is occupied: ${detail}. ` +
    `Stop the process holding port ${port} or set ${envName} to a free port.`;
};

/**
 * Wait until `probe` reports `{ ok: true }`, the child dies, or the deadline
 * passes. Never treats spawn success as readiness.
 */
const waitForGate = async ({ service, gate, url, child, deadline, config, deps, probe }) => {
  for (;;) {
    if (child.isExited()) {
      const tail = child.lastLines().slice(-5).join(" | ");
      throw stackError(`STACK_STARTUP_FAILED:${service}`,
        `${service} exited (code ${child.exitCodeValue() ?? "unknown"}) before the ${gate} gate passed${tail ? `; last output: ${tail}` : ""}. ` +
        `Previously started services were stopped.`);
    }
    let outcome = null;
    try {
      outcome = await probe();
    } catch {
      outcome = null;
    }
    if (outcome?.ok) return outcome;
    if (deps.now() >= deadline) {
      throw stackError(`STACK_START_TIMEOUT:${service}`,
        `timed out waiting for ${service} ${gate} at ${url} after ${config.readyTimeoutMs}ms. ` +
        `Check the [${service}] log lines above; previously started services were stopped.`);
    }
    await deps.sleep(config.pollMs);
  }
};

const waitForHttpOk = (service, gate, url, child, deadline, config, deps) =>
  waitForGate({
    service, gate, url, child, deadline, config, deps,
    probe: async () => {
      const response = await deps.httpGet(url);
      return response && response.status >= 200 && response.status < 300 ? { ok: true } : null;
    },
  });

const waitForTcpOk = (service, gate, url, child, deadline, config, deps) =>
  waitForGate({
    service, gate, url, child, deadline, config, deps,
    probe: async () => {
      const probe = await deps.tcpProbe(config.host, config.webPort);
      return probe?.occupied ? { ok: true } : null;
    },
  });

/** Real MCP `initialize` handshake over the child's stdio pipes. */
const waitForMcpHandshake = async (child, deadline, config, deps) => {
  const request = {
    jsonrpc: "2.0",
    id: "stack-probe",
    method: "initialize",
    params: {
      protocolVersion: "2025-06-18",
      capabilities: {},
      clientInfo: { name: "aero-stack", version: "0.1.0" },
    },
  };
  const done = new Promise((resolveHandshake, rejectHandshake) => {
    const unsubscribe = child.onStdoutLine((line) => {
      let message;
      try {
        message = JSON.parse(line);
      } catch {
        return;
      }
      if (message?.id !== "stack-probe") return;
      unsubscribe();
      if (message?.error) {
        rejectHandshake(stackError("STACK_STARTUP_FAILED:mcp",
          `MCP server answered the initialize handshake with an error: ${JSON.stringify(message.error).slice(0, 300)}. ` +
          `Previously started services were stopped.`));
        return;
      }
      resolveHandshake(message?.result ?? {});
    });
    child.sendStdin(`${JSON.stringify(request)}\n`);
  });
  const timeout = (async () => {
    while (deps.now() < deadline) {
      if (child.isExited()) {
        throw stackError("STACK_STARTUP_FAILED:mcp",
          `mcp exited (code ${child.exitCodeValue() ?? "unknown"}) before the initialize handshake completed. ` +
          `Previously started services were stopped.`);
      }
      await deps.sleep(config.pollMs);
    }
    throw stackError("STACK_START_TIMEOUT:mcp",
      `timed out waiting for the MCP initialize handshake after ${config.mcpHandshakeMs}ms. ` +
      `Previously started services were stopped.`);
  })();
  const result = await Promise.race([done, timeout]);
  try {
    child.sendStdin(`${JSON.stringify({ jsonrpc: "2.0", method: "notifications/initialized" })}\n`);
  } catch {
    // Fire-and-forget: the handshake already proved the server is alive.
  }
  return result;
};

/**
 * Start every requested service, in dependency order, behind readiness gates.
 * On any failure the already-started services are stopped in reverse order
 * before the error propagates, so a half-started stack never lingers.
 */
export const startStack = async (config, deps) => {
  const started = [];
  const deadlineFor = () => deps.now() + config.readyTimeoutMs;
  try {
    if (config.mode === "start") {
      try {
        await deps.fsAccess(join(config.root, "apps", "web", ".next", "BUILD_ID"));
      } catch {
        throw stackError("STACK_STARTUP_FAILED:web",
          "web production build output is missing (apps/web/.next/BUILD_ID not found). " +
          "Run `pnpm --filter @aero/web build` first, or use `dev` mode for the developer stack.");
      }
    }
    for (const [port, key] of [[config.apiPort, "apiPort"], [config.webPort, "webPort"]]) {
      const probe = await deps.tcpProbe(config.host, port);
      if (probe?.occupied) throw stackError("STACK_PORT_CONFLICT", portConflictMessage(port, PORT_LABELS[key], probe.detail ?? "listener detected"));
    }
    deps.log(`starting local stack (mode=${config.mode} services=${["api", "web", ...(config.withMcp ? ["mcp"] : [])].join(",")})`);

    const api = deps.spawnService("api", config.apiCommand, { cwd: config.root, extraEnv: config.apiExtraEnv ?? undefined });
    started.push({ name: "api", child: api });
    deps.log(`[api] spawned pid ${api.pid ?? "(unknown)"}; waiting for ${config.apiHealthUrl}`);
    await waitForHttpOk("api", "health", config.apiHealthUrl, api, deadlineFor(), config, deps);
    deps.log("[api] health gate passed");
    await waitForHttpOk("api", "worker /v1/native/capabilities", config.apiCapabilitiesUrl, api, deadlineFor(), config, deps);
    deps.log("[api] worker gate passed (single-worker job lifecycle answers; no solver started)");

    const webEnv = { NEXT_PUBLIC_API_BASE_URL: config.apiBase };
    const web = deps.spawnService("web", config.webCommand, { cwd: join(config.root, "apps", "web"), extraEnv: webEnv });
    started.push({ name: "web", child: web });
    deps.log(`[web] spawned pid ${web.pid ?? "(unknown)"}; waiting for ${config.webBase} to accept connections`);
    await waitForTcpOk("web", "port-accept", config.webBase, web, deadlineFor(), config, deps);
    deps.log("[web] port gate passed");

    if (config.withMcp) {
      const mcp = deps.spawnService("mcp", config.mcpCommand, { cwd: config.root, stdio: true });
      started.push({ name: "mcp", child: mcp });
      deps.log(`[mcp] spawned pid ${mcp.pid ?? "(unknown)"}; waiting for the initialize handshake`);
      const handshake = await waitForMcpHandshake(mcp, deps.now() + config.mcpHandshakeMs, config, deps);
      const version = handshake?.protocolVersion ? ` (protocol ${handshake.protocolVersion})` : "";
      deps.log(`[mcp] handshake gate passed${version}`);
    }

    deps.log(`stack ready: api=${config.apiBase} worker=in-process(api) web=${config.webBase}${config.withMcp ? " mcp=stdio" : ""}`);
    return { config, services: started };
  } catch (error) {
    await stopStack({ config, services: started }, deps);
    throw error;
  }
};

/** Stop services in reverse dependency order with a bounded grace period. */
export const stopStack = async (handle, deps) => {
  const results = [];
  for (const service of [...handle.services].reverse()) {
    const { name, child } = service;
    if (child.isExited()) {
      results.push({ service: name, stopped: true, detail: "already exited" });
      continue;
    }
    try {
      child.kill("SIGTERM");
    } catch {
      // Fall through to the tree sweep below.
    }
    const graceUntil = deps.now() + handle.config.stopGraceMs;
    while (!child.isExited() && deps.now() < graceUntil) {
      await deps.sleep(Math.min(handle.config.pollMs, 100));
    }
    if (child.isExited()) {
      deps.log(`[${name}] stopped gracefully`);
      results.push({ service: name, stopped: true, detail: "graceful" });
      continue;
    }
    let observed = child.pid ? [child.pid] : [];
    try {
      if (child.pid) observed = [...await deps.readTreePids(child.pid)];
    } catch {
      // Fall back to the root PID: only ever project-owned PIDs are signalled.
    }
    await deps.forceKill(child.pid, observed);
    const verifyUntil = deps.now() + 2000;
    let gone = child.isExited();
    while (!gone && deps.now() < verifyUntil) {
      await deps.sleep(50);
      gone = child.isExited();
    }
    deps.log(`[${name}] force-stopped ${observed.length} observed process(es)${gone ? "" : " (unverified; see log)"}`);
    results.push({ service: name, stopped: gone, detail: gone ? `force-killed ${observed.length} process(es)` : "force-kill unverified" });
  }
  return results;
};

// ---------------------------------------------------------------------------
// Real host bindings (default path: loopback only, no shell, no Docker).
// ---------------------------------------------------------------------------

const tcpProbePort = (host, port) => new Promise((resolveProbe) => {
  let settled = false;
  const finish = (result) => { if (!settled) { settled = true; resolveProbe(result); } };
  const socket = createConnection({ host, port }, () => {
    socket.destroy();
    finish({ occupied: true, detail: "a listener accepted a loopback connection" });
  });
  socket.setTimeout(1000);
  socket.once("timeout", () => { socket.destroy(); finish({ occupied: false, detail: "port is free" }); });
  socket.once("error", (error) => {
    socket.destroy();
    if (error?.code === "ECONNREFUSED") finish({ occupied: false, detail: "port is free" });
    else finish({ occupied: false, detail: `no listener detected (${error?.code ?? error?.message ?? "unknown"})` });
  });
});

const httpGetReal = async (url) => {
  const response = await fetch(url, { signal: AbortSignal.timeout(3000) });
  return { status: response.status };
};

const runTreeKill = (rootPid, pids) => new Promise((resolveKill) => {
  if (!rootPid) { resolveKill(); return; }
  if (process.platform === "win32") {
    // taskkill /T covers the whole descendant tree from the project-owned root.
    const killer = spawn("taskkill.exe", ["/PID", String(rootPid), "/T", "/F"],
      { shell: false, windowsHide: true, stdio: "ignore" });
    killer.once("error", () => resolveKill());
    killer.once("close", () => resolveKill());
    return;
  }
  try {
    process.kill(-rootPid, "SIGKILL");
  } catch {
    // Best effort; per-PID sweep follows.
  }
  for (const pid of pids) {
    try {
      process.kill(pid, "SIGKILL");
    } catch {
      // A PID can exit between observation and signalling; that is success.
    }
  }
  resolveKill();
});

const wrapChild = (name, child, log) => {
  const lines = [];
  const lineHandlers = new Set();
  const emitLine = (chunk, isStderr) => {
    for (const raw of String(chunk).split(/\r?\n/)) {
      if (!raw) continue;
      const framed = `[${name}] ${raw}`;
      lines.push(framed);
      if (lines.length > 50) lines.shift();
      (isStderr ? console.error : console.log)(framed);
      if (!isStderr) for (const handler of lineHandlers) handler(raw);
    }
  };
  if (child.stdout) {
    const reader = createInterface({ input: child.stdout });
    reader.on("line", (line) => emitLine(line, false));
  }
  if (child.stderr) child.stderr.on("data", (chunk) => emitLine(chunk, true));
  log(`[${name}] $ ${name === "mcp" ? "(stdio)" : ""}${child.spawnargs?.slice(1).join(" ") ?? ""}`.trim());
  return {
    name,
    pid: child.pid,
    kill: (signal) => {
      try {
        return child.kill(process.platform === "win32" ? undefined : (signal ?? "SIGTERM"));
      } catch {
        return false;
      }
    },
    isExited: () => child.exitCode !== null || child.signalCode !== null,
    exitCodeValue: () => child.exitCode,
    lastLines: () => [...lines],
    sendStdin: (data) => child.stdin?.write(data),
    onStdoutLine: (callback) => { lineHandlers.add(callback); return () => lineHandlers.delete(callback); },
    waitExit: () => new Promise((resolveExit) => {
      if (child.exitCode !== null || child.signalCode !== null) { resolveExit(child.exitCode); return; }
      child.once("exit", (code) => resolveExit(code));
    }),
  };
};

const realDeps = (log) => ({
  now: () => Date.now(),
  sleep: (ms) => new Promise((resolveSleep) => setTimeout(resolveSleep, ms)),
  log,
  fsAccess: (path) => access(path, constants.F_OK),
  readTreePids: readProcessTreePids,
  forceKill: runTreeKill,
  httpGet: httpGetReal,
  tcpProbe: tcpProbePort,
  spawnService: (name, cmd, options = {}) => {
    const child = spawn(cmd[0], cmd.slice(1), {
      cwd: options.cwd,
      env: { ...process.env, ...(options.extraEnv ?? {}) },
      shell: false,
      windowsHide: true,
      detached: process.platform !== "win32",
      stdio: name === "mcp" ? ["pipe", "pipe", "pipe"] : ["ignore", "pipe", "pipe"],
    });
    // Observable owned PID: the release E2E and operators use this to account
    // for the CLI's children when the CLI itself exits abruptly.
    log(`[${name}] spawned pid ${child.pid}`);
    return wrapChild(name, child, log);
  },
});

const printUsage = () => {
  console.log("Usage: node scripts/platform/stack.mjs [dev|start] [--with-mcp] [--ready-timeout-ms N] [--stop-grace-ms N]");
  console.log("");
  console.log("Starts the usable local product stack (API + worker path + UI) with readiness");
  console.log("gates and clean shutdown. No solvers are launched; Docker is never required.");
  console.log("");
  console.log("  dev         developer stack (API --reload, Next dev server)");
  console.log("  start       production-ish stack (API, Next start; needs apps/web build first)");
  console.log("  --with-mcp  also start the stdio MCP engineering server (default: omitted)");
  console.log("");
  console.log("Env overrides: AERO_API_PORT (8000), AERO_WEB_PORT (3000),");
  console.log("  AERO_STACK_READY_TIMEOUT_MS, AERO_STACK_STOP_GRACE_MS, AERO_WITH_MCP=1.");
};

const translateExit = (error) => {
  const message = error?.message ?? String(error);
  if (message.startsWith("STACK_USAGE") || message.startsWith("STACK_PORT_CONFLICT")) return EXIT.USAGE;
  return EXIT.FAILURE;
};

const main = async () => {
  const rawArgs = process.argv.slice(2);
  if (rawArgs.includes("--help") || rawArgs.includes("-h")) {
    printUsage();
    return;
  }
  const root = resolve(fileURLToPath(new URL(".", import.meta.url)), "..", "..");
  let config;
  try {
    config = resolveConfig({ argv: rawArgs, env: process.env, root, nextBin: resolveNextBin(root) });
    // The API imports the workspace packages through the repo's own pytest
    // path config; without it uvicorn cannot import aeroworkbench_core.
    const apiPath = await resolveApiPythonPath({ root });
    if (apiPath) {
      config.apiExtraEnv = {
        PYTHONPATH: process.env.PYTHONPATH ? `${apiPath}${delimiter}${process.env.PYTHONPATH}` : apiPath,
      };
    }
  } catch (error) {
    console.error(`[stack] ${error.message}`);
    if (String(error.message).startsWith("STACK_USAGE")) printUsage();
    process.exitCode = translateExit(error);
    return;
  }
  const deps = realDeps((line) => console.log(`[stack] ${line}`));
  // Best-effort synchronous sweep for abrupt (but handled) exits. Only
  // project-owned roots recorded here are ever signalled.
  const ownedRoots = [];
  const handle = { config, services: [] };
  const shutdown = async (reason, code) => {
    if (handle.shuttingDown) return;
    handle.shuttingDown = true;
    console.log(`[stack] ${reason}; stopping ${handle.services.length} service(s) in reverse order`);
    await stopStack(handle, deps);
    process.exitCode = code;
    process.exit(code);
  };
  process.once("SIGINT", () => shutdown("interrupted (Ctrl-C)", EXIT.INTERRUPTED));
  process.once("SIGTERM", () => shutdown("parent termination requested", EXIT.INTERRUPTED));
  process.on("exit", () => {
    for (const pid of ownedRoots) {
      if (!Number.isInteger(pid)) continue;
      try {
        if (process.platform === "win32") {
          spawn("taskkill.exe", ["/PID", String(pid), "/T", "/F"],
            { shell: false, windowsHide: true, stdio: "ignore" });
        } else {
          process.kill(-pid, "SIGKILL");
        }
      } catch {
        // Best effort only; the ordered stopStack above is authoritative.
      }
    }
  });
  try {
    const started = await startStack(config, deps);
    handle.services = started.services;
    for (const service of handle.services) {
      if (service.child.pid) ownedRoots.push(service.child.pid);
    }
  } catch (error) {
    console.error(`[stack] ${error.message}`);
    process.exitCode = translateExit(error);
    return;
  }
  // After ready: any unexpected child exit shuts the stack down cleanly.
  const watchers = handle.services.map((service) => service.child.waitExit().then(() => service));
  while (!handle.shuttingDown) {
    const exited = await Promise.race(watchers);
    if (handle.shuttingDown) break;
    await shutdown(
      `${exited.name} exited unexpectedly (code ${exited.child.exitCodeValue() ?? "unknown"})`,
      EXIT.FAILURE,
    );
    break;
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
