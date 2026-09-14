// Product doctor: deterministic readiness + capability report.
// Diagnostics only. This command never installs, downloads, writes, starts,
// or stops anything: every check is a version probe, filesystem read/access,
// loopback port probe, in-memory SQLite probe, or read-only API import probe.
import { spawn } from "node:child_process";
import { access, readFile, stat } from "node:fs/promises";
import { constants } from "node:fs";
import { homedir } from "node:os";
import { createConnection } from "node:net";
import { delimiter, dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import {
  CAPABILITY_MANIFESTS,
  commandProbe,
} from "../../packages/solver-contracts/src/index.ts";

export const DOCTOR_SCHEMA = 1;

/** All per-check states. Baseline failures block; optional solvers never block. */
export const CHECK_STATES = Object.freeze(["ready", "unavailable", "warning", "failed"]);

/** Baseline check ids in stable report order. Solver checks follow in manifest order. */
export const BASELINE_CHECK_IDS = Object.freeze([
  "node",
  "pnpm",
  "python",
  "uv",
  "workspace-deps",
  "data-dir",
  "sqlite",
  "port-3000",
  "port-8000",
  "api-preflight",
]);

/** Product API + UI ports. Probes report occupancy; they never bind or kill. */
export const REQUIRED_PORTS = Object.freeze([
  { port: 3000, label: "web UI" },
  { port: 8000, label: "local API" },
]);

/**
 * Native job-lifecycle routes created by the governed product backend.
 * The API preflight reports these honestly: a missing route is a failure,
 * never papered over.
 */
export const EXPECTED_NATIVE_ROUTES = Object.freeze([
  "/v1/native/capabilities",
  "/v1/native/participants",
  "/v1/native/analyses",
  "/v1/native/analyses/{job_id}",
  "/v1/native/analyses/{job_id}/events",
  "/v1/native/analyses/{job_id}/start",
  "/v1/native/analyses/{job_id}/cancel",
  "/v1/native/results/{job_id}",
  "/v1/native/artifacts/{job_id}",
  "/v1/native/provenance/{job_id}",
]);

const SETUP_SOLVERS_HINT = "Run `pnpm setup:solvers` (see docs/solver-verification.md)";

const ready = (id, tier, version, detail) => ({
  id, tier, state: "ready", version: version ?? null, detail, remediation: null,
});

const notReady = (id, tier, state, detail, remediation, version = null) => ({
  id, tier, state, version, detail, remediation: remediation ?? null,
});

const parseDotted = (text) => {
  const match = /(\d+)\.(\d+)\.(\d+)/.exec(text ?? "");
  if (!match) return null;
  return { major: Number(match[1]), minor: Number(match[2]), patch: Number(match[3]) };
};

const spawnTimeout = (cmd, args, timeoutMs, opts = {}) => new Promise((resolve, reject) => {
  const child = spawn(cmd, [...args], {
    shell: false, windowsHide: true, stdio: ["ignore", "pipe", "pipe"], ...opts,
  });
  let stdout = "";
  let stderr = "";
  const timer = setTimeout(() => {
    child.kill();
    reject(Object.assign(new Error(`spawn ${cmd} timed out`), { code: "ETIMEDOUT" }));
  }, timeoutMs);
  child.stdout.on("data", (chunk) => { stdout += chunk.toString(); });
  child.stderr.on("data", (chunk) => { stderr += chunk.toString(); });
  child.once("error", (error) => { clearTimeout(timer); reject(error); });
  child.once("close", (code) => {
    clearTimeout(timer);
    resolve({ status: code ?? 1, stdout, stderr });
  });
});

const PREFLIGHT_PY = [
  "import json",
  "from aeroworkbench_api.main import ANALYTICAL_MODELS, create_app",
  "from participants.manifest import PARTICIPANT_MANIFESTS",
  "app = create_app()",
  "paths = set()",
  "for r in app.routes:",
  "  p = getattr(r, 'path', None)",
  "  if p: paths.add(p)",
  "  inner = getattr(r, 'original_router', None)",
  "  if inner is not None:",
  "    [paths.add(s.path) for s in inner.routes if getattr(s, 'path', None)]",
  "print(json.dumps({",
  "  'ok': True,",
  "  'version': app.version,",
  "  'routes': sorted(paths),",
  "  'analytical_models': list(ANALYTICAL_MODELS),",
  "  'participants': len(PARTICIPANT_MANIFESTS),",
  "}))",
].join("\n");

const checkNode = (env) => {
  const raw = env.nodeVersion ?? "";
  const parsed = /^v(\d+)\./.exec(raw);
  const major = parsed ? Number(parsed[1]) : Number.NaN;
  if (!Number.isInteger(major) || major < 24) {
    return notReady("node", "baseline", "failed",
      `unsupported Node.js ${raw || "(unknown)"}; product baseline requires Node.js 24`,
      "Install Node.js 24 (see README Quickstart)", raw || null);
  }
  return ready("node", "baseline", raw, `Node.js ${raw} meets the baseline`);
};

const checkPnpm = async (env) => {
  // Bare `pnpm` is a .ps1 shim on Windows, which cannot be spawned without a
  // shell; pnpm.cmd (or corepack) covers every platform without one.
  const candidates = env.platform === "win32" || process.platform === "win32" || !env.platform
    ? [["pnpm.cmd", ["--version"]], ["pnpm", ["--version"]], ["corepack", ["pnpm", "--version"]]]
    : [["pnpm", ["--version"]], ["corepack", ["pnpm", "--version"]]];
  let lastError = null;
  for (const attempt of candidates) {
    try {
      const result = await env.spawn(attempt[0], attempt[1]);
      const combined = `${result.stdout}${result.stderr}`.trim();
      const parsed = parseDotted(combined);
      const version = parsed ? `${parsed.major}.${parsed.minor}.${parsed.patch}` : null;
      if (result.status === 0 && parsed && parsed.major >= 10) {
        return ready("pnpm", "baseline", version, `pnpm ${version} available`);
      }
      return notReady("pnpm", "baseline", "failed",
        `pnpm probe reported ${JSON.stringify(combined || "(empty)")}; repo pins pnpm 11 (package.json packageManager)`,
        "Run `corepack enable` then `corepack pnpm install` (see README Quickstart)", version);
    } catch (error) {
      lastError = error;
    }
  }
  return notReady("pnpm", "baseline", "failed",
    `pnpm is not on PATH (${lastError?.code ?? lastError?.message ?? "unavailable"})`,
    "Run `corepack enable` then `corepack pnpm install` (see README Quickstart)");
};

const checkPython = async (env) => {
  let lastError = null;
  for (const cmd of ["python", "python3"]) {
    try {
      const result = await env.spawn(cmd, ["--version"]);
      const combined = `${result.stdout}${result.stderr}`.trim();
      const parsed = parseDotted(combined);
      const version = parsed ? `${parsed.major}.${parsed.minor}.${parsed.patch}` : null;
      if (result.status === 0 && parsed && parsed.major === 3 && parsed.minor === 12) {
        return ready("python", "baseline", version, `Python ${version} meets services/api (requires-python >=3.12,<3.13)`);
      }
      return notReady("python", "baseline", "failed",
        `Python probe reported ${JSON.stringify(combined || "(empty)")}; services/api requires Python 3.12`,
        "Install Python 3.12 (see README Quickstart)", version);
    } catch (error) {
      lastError = error;
      if (error?.code !== "ENOENT") {
        return notReady("python", "baseline", "failed",
          `Python probe failed: ${error?.message ?? error}`,
          "Install Python 3.12 (see README Quickstart)");
      }
    }
  }
  return notReady("python", "baseline", "failed",
    `Python 3.12 not found (${lastError?.code ?? "unavailable"})`,
    "Install Python 3.12 (see README Quickstart)");
};

const checkUv = async (env) => {
  try {
    const result = await env.spawn("uv", ["--version"]);
    const combined = `${result.stdout}${result.stderr}`.trim();
    const parsed = parseDotted(combined);
    const version = parsed ? `${parsed.major}.${parsed.minor}.${parsed.patch}` : null;
    if (result.status === 0 && version) return ready("uv", "baseline", version, `uv ${version} available for services/api`);
    return notReady("uv", "baseline", "failed", "uv probe did not report a version",
      "Install uv (https://docs.astral.sh/uv/getting-started/installation/) — required for services/api", version);
  } catch (error) {
    return notReady("uv", "baseline", "failed",
      `uv not found (${error?.code ?? error?.message ?? error})`,
      "Install uv (https://docs.astral.sh/uv/getting-started/installation/) — required for services/api");
  }
};

const checkWorkspaceDeps = async (env) => {
  try {
    const info = await env.fsStat(join(env.root, "node_modules"));
    if (info.isDirectory) return ready("workspace-deps", "baseline", null, "workspace dependencies are installed");
  } catch { /* missing below */ }
  return notReady("workspace-deps", "baseline", "failed",
    "node_modules is missing; workspace packages cannot be resolved",
    "Run `corepack pnpm install` from the repo root (see README Quickstart)");
};

const resolveJobRoot = (env) => {
  const override = (env.jobRootOverride ?? "").trim();
  if (override) return override;
  return join(env.home, ".aeroworkbench", "native-jobs");
};

const checkDataDir = async (env) => {
  const dir = resolveJobRoot(env);
  try {
    await env.fsAccess(dir);
    return ready("data-dir", "baseline", null, `local job directory is writable: ${dir}`);
  } catch (error) {
    if (error?.code === "ENOENT") {
      return notReady("data-dir", "baseline", "warning",
        `job directory does not exist yet and will be created on first native job submit: ${dir}`, null);
    }
    return notReady("data-dir", "baseline", "failed",
      `job directory is not writable: ${dir} (${error?.code ?? error?.message ?? error})`,
      `Make ${dir} writable or set AEROWORKBENCH_JOB_ROOT to a writable directory`);
  }
};

const checkPort = async (env, port, label) => {
  const id = `port-${port}`;
  try {
    const probe = await env.checkPort(port);
    if (!probe.occupied) return ready(id, "baseline", null, `port ${port} (${label}) is free`);
    return notReady(id, "baseline", "warning",
      `port ${port} (${label}) is occupied: ${probe.detail}`,
      `Stop the process holding port ${port} or start the service on another port`);
  } catch (error) {
    return notReady(id, "baseline", "warning",
      `port ${port} (${label}) probe was inconclusive: ${error?.message ?? error}`,
      `Retry \`pnpm doctor\`; if the port is in use, stop its holder or use another port`);
  }
};

const checkApiPreflight = async (env) => {
  if (!(await env.apiFilesPresent())) {
    return notReady("api-preflight", "baseline", "failed",
      "services/api sources are missing (aeroworkbench_api/main.py or pyproject.toml)",
      "Restore services/api from version control");
  }
  let result;
  try {
    result = await env.spawn("uv-api-preflight", []);
  } catch (error) {
    return notReady("api-preflight", "baseline", "failed",
      `API preflight could not run (${error?.code ?? error?.message ?? error})`,
      "From the repo root run `uv run --directory services/api python -c \"import aeroworkbench_api.main\"` (first run syncs the API venv)");
  }
  if (result.status !== 0) {
    const detail = `${result.stdout}${result.stderr}`.trim().split(/\r?\n/).at(-1)?.slice(0, 200) || `exit ${result.status}`;
    return notReady("api-preflight", "baseline", "failed",
      `API import probe failed: ${detail}`,
      "From the repo root run `uv run --directory services/api python -c \"import aeroworkbench_api.main\"`, then start with `uv run --directory services/api uvicorn aeroworkbench_api.main:app --port 8000` (see README Run locally)");
  }
  let payload;
  try {
    payload = JSON.parse(result.stdout);
  } catch {
    return notReady("api-preflight", "baseline", "failed",
      "API import probe returned non-JSON output",
      "From the repo root run `uv run --directory services/api python -c \"import aeroworkbench_api.main\"` (see README Run locally)");
  }
  if (!payload?.ok) {
    return notReady("api-preflight", "baseline", "failed",
      `API import probe reported failure: ${JSON.stringify(payload).slice(0, 200)}`,
      "From the repo root run `uv run --directory services/api python -c \"import aeroworkbench_api.main\"` (see README Run locally)");
  }
  const routes = Array.isArray(payload.routes) ? payload.routes : [];
  const missing = EXPECTED_NATIVE_ROUTES.filter((route) => !routes.includes(route));
  if (missing.length > 0) {
    return notReady("api-preflight", "baseline", "failed",
      `API imports but is missing governed native routes: ${missing.join(", ")}`,
      "Restore services/api from version control", payload.version ?? null);
  }
  const models = Array.isArray(payload.analytical_models) ? payload.analytical_models.length : 0;
  return ready("api-preflight", "baseline", payload.version ?? null,
    `API imports; ${routes.length} routes incl. governed native submit/status/events/start/cancel/results/artifacts/provenance, ${payload.participants ?? 0} participant types, ${models} analytical models`);
};

const checkSolver = async (env, id) => {
  const manifest = CAPABILITY_MANIFESTS.find((candidate) => candidate.id === id);
  const display = manifest?.displayName ?? id;
  let probe;
  try {
    probe = await env.solverProbe(id);
  } catch (error) {
    return notReady(`solver:${id}`, "optional", "unavailable",
      `${display} probe errored honestly: ${error?.message ?? error}`, SETUP_SOLVERS_HINT);
  }
  if (probe?.available) {
    return ready(`solver:${id}`, "optional", probe.version ?? null,
      `${display} responded to its trusted --version probe${probe.version ? "" : " (no version string)"}`);
  }
  return notReady(`solver:${id}`, "optional", "unavailable",
    `${display} unavailable: ${probe?.detail ?? "no detail reported"}`, SETUP_SOLVERS_HINT);
};

/**
 * Runs every check without mutating the machine and returns a stable report.
 * The optional `env` parameter injects doubles for tests; defaults probe the
 * real host in read-only ways only.
 */
export const runDoctor = async (env = defaultEnv()) => {
  const checks = [
    checkNode(env),
    await checkPnpm(env),
    await checkPython(env),
    await checkUv(env),
    await checkWorkspaceDeps(env),
    await checkDataDir(env),
    await (async () => {
      try {
        const probe = await env.sqliteProbe();
        return probe.ok
          ? ready("sqlite", "baseline", probe.version ?? null, probe.detail)
          : notReady("sqlite", "baseline", "failed", probe.detail,
            "SQLite is required for local artifact storage; repair the Node.js install (node:sqlite) or Python 3.12 (sqlite3)");
      } catch (error) {
        return notReady("sqlite", "baseline", "failed",
          `SQLite probe failed: ${error?.message ?? error}`,
          "SQLite is required for local artifact storage; repair the Node.js install (node:sqlite) or Python 3.12 (sqlite3)");
      }
    })(),
    ...(await Promise.all(REQUIRED_PORTS.map(({ port, label }) => checkPort(env, port, label)))),
    await checkApiPreflight(env),
  ];
  for (const id of env.solverIds) checks.push(await checkSolver(env, id));
  const baselineReady = checks.every((check) => check.tier !== "baseline" || check.state === "ready" || check.state === "warning");
  const optional = checks.filter((check) => check.tier === "optional");
  return {
    tool: "aero-doctor",
    schema: DOCTOR_SCHEMA,
    checkedAt: env.now(),
    baseline: baselineReady ? "ready" : "blocked",
    baselineReady,
    checks,
    solvers: {
      total: optional.length,
      ready: optional.filter((check) => check.state === "ready").map((check) => check.id.replace(/^solver:/, "")),
      unavailable: optional.filter((check) => check.state !== "ready").map((check) => check.id.replace(/^solver:/, "")),
    },
  };
};

/** Nonzero only when baseline-blocking checks fail; optional solvers never block. */
export const exitCodeFor = (report) => (report.baselineReady ? 0 : 1);

export const formatHuman = (report) => {
  const rows = [["CHECK", "TIER", "STATE", "VERSION", "DETAIL"]];
  for (const check of report.checks) {
    rows.push([check.id, check.tier, check.state, check.version ?? "-", check.detail]);
  }
  const widths = rows[0].map((_, col) => Math.max(...rows.map((row) => row[col].length)));
  const lines = rows.map((row, index) => {
    const line = row.map((cell, col) => cell.padEnd(widths[col])).join("  ").trimEnd();
    if (index === 0) return `${line}\n${widths.map((width) => "-".repeat(width)).join("  ")}`;
    return line;
  });
  const needsHelp = report.checks.filter((check) => check.state !== "ready" && check.remediation);
  if (needsHelp.length > 0) {
    lines.push("", "Remediation:");
    for (const check of needsHelp) lines.push(`  [${check.id}] ${check.remediation}`);
  }
  const optionalNote = report.solvers.unavailable.length > 0
    ? ` — optional solvers unavailable: ${report.solvers.unavailable.join(", ")}`
    : " — all optional solvers ready";
  lines.push("", `Baseline: ${report.baselineReady ? "READY" : "BLOCKED"}${optionalNote}`);
  return lines.join("\n");
};

/** Trusted registry probe: resolves the immutable manifest by id, never a caller copy. */
const trustedSolverProbe = async (id) => {
  const trusted = CAPABILITY_MANIFESTS.find((candidate) => candidate.id === id);
  if (!trusted) return { available: false, detail: "not in the trusted manifest registry" };
  const capability = await commandProbe(trusted);
  return { available: capability.available, version: capability.version, detail: capability.detail };
};

const defaultCheckPort = (port) => new Promise((resolve) => {
  let settled = false;
  const finish = (result) => { if (!settled) { settled = true; resolve(result); } };
  const socket = createConnection({ host: "127.0.0.1", port }, () => {
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

const defaultSqliteProbe = async () => {
  try {
    const { DatabaseSync } = await import("node:sqlite");
    const db = new DatabaseSync(":memory:");
    try {
      db.exec("CREATE TABLE doctor_probe(id INTEGER PRIMARY KEY, v TEXT)");
      db.prepare("INSERT INTO doctor_probe(v) VALUES (?)").run("ok");
      const row = db.prepare("SELECT v FROM doctor_probe").get();
      if (row?.v !== "ok") return { ok: false, detail: "in-memory SQLite roundtrip returned no row" };
      return { ok: true, version: process.versions.sqlite ?? null, detail: "in-memory read-write probe via node:sqlite passed" };
    } finally {
      db.close();
    }
  } catch { /* fall through to the Python probe */ }
  const result = await spawnTimeout("python",
    ["-c", "import sqlite3; c=sqlite3.connect(':memory:'); c.execute('CREATE TABLE t(v TEXT)'); c.execute(\"INSERT INTO t VALUES ('ok')\"); assert c.execute('SELECT v FROM t').fetchone()[0]=='ok'; print('ok')"],
    30_000);
  if (result.status === 0 && result.stdout.trim() === "ok") {
    return { ok: true, version: null, detail: "in-memory read-write probe via Python sqlite3 passed" };
  }
  return { ok: false, detail: `SQLite probe failed: ${`${result.stdout}${result.stderr}`.trim().slice(0, 160) || `exit ${result.status}`}` };
};

/** Read-only: mirrors the repo's own API path config (services/api interpreter path). */
const apiPythonPath = async (apiDir) => {
  try {
    const text = await readFile(join(apiDir, "pyproject.toml"), "utf8");
    const match = /pythonpath\s*=\s*\[(.*?)\]/s.exec(text);
    if (!match) return null;
    const entries = [...match[1].matchAll(/"([^"]+)"/g)].map((entry) => entry[1]);
    if (entries.length === 0) return null;
    return entries.map((entry) => resolve(apiDir, entry)).join(delimiter);
  } catch { return null; }
};

/** Read-only host bindings. No installs, downloads, writes, or server control. */
export const defaultEnv = (overrides = {}) => {
  const root = overrides.root ?? resolve(fileURLToPath(new URL(".", import.meta.url)), "..", "..");
  const apiDir = join(root, "services", "api");
  return {
    nodeVersion: process.version,
    root,
    home: homedir(),
    jobRootOverride: process.env.AEROWORKBENCH_JOB_ROOT ?? "",
    now: () => new Date().toISOString(),
    spawn: async (cmd, args) => {
      if (cmd === "uv-api-preflight") {
        // --no-sync: never install or modify the venv; PYTHONPATH reuses the
        // repo's own pytest path config so the probe matches how the repo
        // itself imports the API. Nothing is written anywhere.
        const pythonPath = await apiPythonPath(apiDir);
        return spawnTimeout("uv",
          ["run", "--no-sync", "--directory", apiDir, "python", "-c", PREFLIGHT_PY], 90_000,
          pythonPath ? { env: { ...process.env, PYTHONPATH: pythonPath } } : undefined);
      }
      if (process.platform === "win32" && (cmd === "pnpm" || cmd === "pnpm.cmd" || cmd === "corepack")) {
        // .cmd/.ps1 shims cannot be spawned without a shell (EINVAL), and a
        // PATH search can hit repo-local shims. Run the Node-bundled
        // corepack entry directly instead. All args here are fixed probe
        // constants; no user input flows into any shell.
        try {
          const pnpmJs = join(dirname(process.execPath), "node_modules", "corepack", "dist", "pnpm.js");
          await access(pnpmJs);
          const realArgs = cmd === "corepack" ? args.filter((arg) => arg !== "pnpm") : args;
          return await spawnTimeout(process.execPath, [pnpmJs, ...realArgs], 15_000);
        } catch { /* fall through to the PATH-based attempt below */ }
      }
      if (cmd === "python" || cmd === "python3") return spawnTimeout(cmd, args, 15_000);
      return spawnTimeout(cmd, args, 15_000);
    },
    fsAccess: (path) => access(path, constants.W_OK),
    fsStat: (path) => stat(path),
    apiFilesPresent: async () => {
      try {
        await access(join(apiDir, "aeroworkbench_api", "main.py"));
        await access(join(apiDir, "pyproject.toml"));
        return true;
      } catch { return false; }
    },
    checkPort: defaultCheckPort,
    sqliteProbe: defaultSqliteProbe,
    solverProbe: trustedSolverProbe,
    solverIds: CAPABILITY_MANIFESTS.map((manifest) => manifest.id),
    ...overrides,
  };
};

const printUsage = () => {
  console.log("Usage: node scripts/platform/doctor.mjs [--json]");
  console.log("Diagnostics only: reports readiness without installing or changing anything.");
};

const main = async () => {
  const args = process.argv.slice(2);
  if (args.includes("--help") || args.includes("-h")) { printUsage(); return; }
  if (args.some((arg) => arg !== "--json")) {
    console.error(`unknown argument: ${args.find((arg) => arg !== "--json")}`);
    printUsage();
    process.exitCode = 2;
    return;
  }
  try {
    const report = await runDoctor();
    // JSON is always emitted before any nonzero exit.
    console.log(args.includes("--json") ? JSON.stringify(report, null, 2) : formatHuman(report));
    process.exitCode = exitCodeFor(report);
  } catch (error) {
    console.log(JSON.stringify({
      tool: "aero-doctor",
      schema: DOCTOR_SCHEMA,
      checkedAt: new Date().toISOString(),
      baseline: "blocked",
      baselineReady: false,
      checks: [],
      solvers: { total: 0, ready: [], unavailable: [] },
      error: error?.message ?? String(error),
    }, null, 2));
    process.exitCode = 1;
  }
};

const invokedDirectly = (() => {
  try {
    return resolve(process.argv[1] ?? "") === fileURLToPath(import.meta.url);
  } catch { return false; }
})();

if (invokedDirectly) await main();
