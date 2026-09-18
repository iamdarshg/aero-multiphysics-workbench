// Bounded performance smoke harness and regression-budget gate.
//
// One fast entry point (documented as `pnpm perf:smoke`; the package.json
// script entry is owned by the integrator since this workstream only owns
// scripts/perf, benchmarks, tests/perf, and docs/performance-baselines.md).
//
// It measures the Node/control-plane hot paths (content-addressed cache,
// canonical digest, doctor probes, optional product-stack cold start), runs
// the Python half as a bounded child (scripts/perf/perf_suite.py), merges both
// into one machine-readable report, and checks committed regression budgets.
//
// Honest measurement rules: environment is always recorded, a benchmark that
// cannot run is reported as skipped with an explicit reason, and the suite is
// bounded by --budget-ms (default 60_000).
import { createHash } from "node:crypto";
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { createServer } from "node:net";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { monitorEventLoopDelay } from "node:perf_hooks";

import { ContentAddressedCache, contentDigest } from "../../packages/cache/src/content-addressed.ts";
import { runDoctor, defaultEnv } from "../platform/doctor.mjs";

const SCHEMA_VERSION = 1;
const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(HERE, "..", "..");
const PYTHON_SUITE = join(HERE, "perf_suite.py");
const BUDGETS_PATH = join(ROOT, "benchmarks", "perf", "budgets.json");
const REPORTS_DIR = join(ROOT, "benchmarks", "perf", "reports");

const nowMs = () => Number(process.hrtime.bigint()) / 1e6;

function emptyMetric(id, group, unit = "ms", notes = "") {
  return {
    id, group, status: "skipped", available: false, cold: false, unit, iterations: 0,
    median: null, p95: null, min: null, max: null, totalMs: null, perItemMs: null,
    itemsPerSecond: null, mibPerSecond: null, items: null, bytes: null,
    reason: null, notes, stages: null,
  };
}

const skipped = (id, group, reason, notes = "") => ({ ...emptyMetric(id, group, "ms", notes), reason });
const failedMetric = (id, group, reason) => ({ ...emptyMetric(id, group), status: "failed", reason });

function percentile(ordered, fraction) {
  if (ordered.length === 0) throw new Error("EMPTY_SAMPLE");
  if (ordered.length === 1) return ordered[0];
  const rank = fraction * (ordered.length - 1);
  const low = Math.floor(rank);
  const high = Math.ceil(rank);
  if (low === high) return ordered[low];
  return ordered[low] + (ordered[high] - ordered[low]) * (rank - low);
}

function latency(id, group, samplesMs, { iterations, cold = false, notes = "", stages = null } = {}) {
  const ordered = [...samplesMs].sort((a, b) => a - b);
  return {
    ...emptyMetric(id, group, "ms", notes),
    status: "measured", available: true, cold,
    iterations: iterations ?? ordered.length,
    median: round(percentile(ordered, 0.5)), p95: round(percentile(ordered, 0.95)),
    min: round(ordered[0]), max: round(ordered[ordered.length - 1]),
    totalMs: round(ordered.reduce((total, value) => total + value, 0)), stages,
  };
}

function throughput(id, group, { totalMs, items, bytes = null, iterations = null, notes = "", stages = null }) {
  const metric = emptyMetric(id, group, "ms", notes);
  const perItem = items ? totalMs / items : null;
  const perSecond = totalMs > 0 && items ? items / (totalMs / 1000) : null;
  const mibPerSecond = bytes !== null && totalMs > 0 ? (bytes / (1024 * 1024)) / (totalMs / 1000) : null;
  return {
    ...metric, status: "measured", available: true,
    iterations: iterations ?? Math.trunc(items ?? 0),
    totalMs: round(totalMs),
    perItemMs: perItem === null ? null : round(perItem),
    itemsPerSecond: perSecond === null ? null : round(perSecond, 3),
    mibPerSecond: mibPerSecond === null ? null : round(mibPerSecond, 3),
    items, bytes, stages,
  };
}

const round = (value, digits = 6) => (value === null || value === undefined ? null : Number(value.toFixed(digits)));

// ---------------------------------------------------------------------------
// Node microbenchmarks
// ---------------------------------------------------------------------------

async function measureNodeContentLookup() {
  const id = "node.content_lookup";
  try {
    const cache = new ContentAddressedCache();
    const entries = 200;
    const lookups = 40_000;
    const keys = [];
    for (let index = 0; index < entries; index += 1) {
      const key = createHash("sha256").update(`perf-${index}`).digest("hex");
      keys.push(key);
      cache.put(key, { index, unit: "dimensionless" });
    }
    const samples = [];
    for (let index = 0; index < lookups; index += 1) {
      const key = keys[index % entries];
      const start = nowMs();
      cache.get(key);
      samples.push(nowMs() - start);
    }
    return latency(id, "node", samples, {
      iterations: lookups,
      notes: `${entries} populated entries; each sample is one ContentAddressedCache.get (structuredClone), matching the Python metric`,
    });
  } catch (error) {
    return failedMetric(id, "node", `${error?.name ?? "Error"}:${error?.message ?? error}`);
  }
}

async function measureNodeCanonicalDigest() {
  const id = "node.canonical_digest";
  try {
    const payload = {
      node: "n12", kind: "analytical", solver: ["perf", "1"],
      settings: { index: 12, tolerance: 1e-6, enabled: true },
      base: { geometry: createHash("sha256").update("geometry").digest("hex") },
      upstream: [createHash("sha256").update("upstream").digest("hex")],
    };
    const iterations = 5_000;
    const samples = [];
    for (let index = 0; index < iterations; index += 1) {
      const start = nowMs();
      contentDigest(payload);
      samples.push(nowMs() - start);
    }
    return latency(id, "node", samples, {
      iterations,
      notes: "contentDigest over a representative DAG node key payload (canonicalJson + sha256)",
    });
  } catch (error) {
    return failedMetric(id, "node", `${error?.name ?? "Error"}:${error?.message ?? error}`);
  }
}

function timeoutReject(ms, label) {
  return new Promise((_, reject) => setTimeout(() => reject(new Error(`TIMEOUT:${label}`)), ms));
}

const raceTimeout = (promise, ms, label) => Promise.race([promise, timeoutReject(ms, label)]);

async function measureDoctor() {
  const id = "node.doctor_total";
  const perProbe = {};
  const timed = (label, fn) => async (...args) => {
    const start = nowMs();
    try {
      return await fn(...args);
    } finally {
      perProbe[label] = (perProbe[label] ?? 0) + (nowMs() - start);
    }
  };
  try {
    const base = defaultEnv();
    const env = {
      ...base,
      spawn: timed("spawn", (cmd, args) => raceTimeout(base.spawn(cmd, args), 8_000, `spawn:${cmd}`)),
      fsAccess: timed("fsAccess", base.fsAccess),
      fsStat: timed("fsStat", base.fsStat),
      apiFilesPresent: timed("apiFilesPresent", base.apiFilesPresent),
      checkPort: timed("checkPort", base.checkPort),
      sqliteProbe: timed("sqliteProbe", base.sqliteProbe),
      solverProbe: timed("solverProbe", base.solverProbe),
    };
    const start = nowMs();
    let report;
    try {
      report = await raceTimeout(runDoctor(env), 25_000, "doctor");
    } catch (error) {
      const stages = Object.fromEntries(Object.entries(perProbe).map(([key, value]) => [key, round(value)]));
      const metric = failedMetric(id, "node", `doctor did not finish within 25s: ${error?.message ?? error}`);
      metric.totalMs = round(nowMs() - start);
      metric.stages = stages;
      return metric;
    }
    const total = nowMs() - start;
    const metric = latency(id, "node", [total], {
      iterations: 1,
      notes: `full pnpm doctor run (${report.checks.length} checks, baseline ${report.baseline}); per-probe timings in stages`,
      stages: Object.fromEntries(Object.entries(perProbe).map(([key, value]) => [key, round(value)])),
    });
    metric.totalMs = round(total);
    metric.detail = {
      baseline: report.baseline,
      solversReady: report.solvers?.ready?.length ?? 0,
      solversUnavailable: report.solvers?.unavailable?.length ?? 0,
    };
    return metric;
  } catch (error) {
    return failedMetric(id, "node", `${error?.name ?? "Error"}:${error?.message ?? error}`);
  }
}

// ---------------------------------------------------------------------------
// optional product stack cold start
// ---------------------------------------------------------------------------

function killTree(pid) {
  if (!pid) return Promise.resolve();
  if (process.platform !== "win32") {
    try { process.kill(-pid, "SIGKILL"); } catch { /* not a group */ }
    return Promise.resolve();
  }
  return new Promise((resolveKill) => {
    const killer = spawn("taskkill.exe", ["/PID", String(pid), "/T", "/F"], { shell: false, windowsHide: true, stdio: "ignore" });
    killer.once("error", () => resolveKill());
    killer.once("close", () => resolveKill());
  });
}

function freePort() {
  return new Promise((resolvePort, rejectPort) => {
    const server = createServer();
    server.once("error", rejectPort);
    server.listen(0, "127.0.0.1", () => {
      const address = server.address();
      const port = typeof address === "object" && address ? address.port : 0;
      server.close(() => resolvePort(port));
    });
  });
}

async function measureStackColdStart(budgetMs) {
  const id = "stack.cold_start_ready";
  const buildId = join(ROOT, "apps", "web", ".next", "BUILD_ID");
  if (!existsSync(buildId)) {
    return skipped(id, "node", "apps/web production build missing (apps/web/.next/BUILD_ID); run pnpm --filter @aero/web build");
  }
  const timeoutMs = Math.max(5_000, Math.min(budgetMs, 40_000));
  // Use free ports so a concurrently running local stack never turns this into
  // a false failure; the cold-start cost measured is the same.
  const [apiPort, webPort] = await Promise.all([freePort(), freePort()]);
  const env = { ...process.env, AERO_API_PORT: String(apiPort), AERO_WEB_PORT: String(webPort) };
  const child = spawn(process.execPath, [join(ROOT, "scripts", "platform", "stack.mjs"), "start", "--ready-timeout-ms", String(timeoutMs - 2_000)], {
    cwd: ROOT, env, stdio: ["ignore", "pipe", "pipe"], shell: false, windowsHide: true,
  });
  const lines = [];
  const start = nowMs();
  let ready = null;
  let earlyExit = null;
  const outcome = await new Promise((resolveOutcome) => {
    const timer = setTimeout(() => resolveOutcome("timeout"), timeoutMs);
    const observe = (chunk) => {
      for (const raw of chunk.toString().split(/\r?\n/)) {
        if (!raw) continue;
        lines.push(raw);
        if (lines.length > 80) lines.shift();
        if (!ready && /stack ready:/.test(raw)) { ready = nowMs() - start; clearTimeout(timer); resolveOutcome("ready"); }
      }
    };
    child.stdout?.on("data", observe);
    child.stderr?.on("data", observe);
    child.once("exit", (code) => { if (!ready) { earlyExit = code; clearTimeout(timer); resolveOutcome("exit"); } });
    child.once("error", (error) => { earlyExit = error?.message ?? String(error); clearTimeout(timer); resolveOutcome("exit"); });
  });
  await killTree(child.pid);
  const tail = lines.slice(-4).join(" | ").slice(0, 400);
  if (outcome === "ready") {
    return latency(id, "node", [ready], {
      iterations: 1, cold: true,
      notes: "node scripts/platform/stack.mjs start; measured spawn to the 'stack ready' line, then the tree was terminated",
    });
  }
  return skipped(id, "node", outcome === "timeout" ? `stack did not become ready within ${timeoutMs}ms` : `stack exited early (code ${earlyExit})`, tail);
}

// ---------------------------------------------------------------------------
// python half + budgets + report
// ---------------------------------------------------------------------------

function runCommand(command, args, { timeoutMs, cwd = ROOT } = {}) {
  return new Promise((resolveRun) => {
    const child = spawn(command, args, { cwd, env: process.env, shell: false, windowsHide: true, stdio: ["ignore", "pipe", "pipe"] });
    let stdout = "";
    let stderr = "";
    let settled = false;
    const finish = (result) => { if (!settled) { settled = true; clearTimeout(timer); resolveRun(result); } };
    const timer = setTimeout(() => {
      killTree(child.pid).finally(() => finish({ code: null, stdout, stderr, timedOut: true }));
    }, timeoutMs);
    child.stdout?.on("data", (chunk) => { stdout += chunk.toString(); });
    child.stderr?.on("data", (chunk) => { stderr += chunk.toString(); });
    child.once("error", (error) => finish({ code: null, stdout, stderr: `${stderr}${error?.message ?? error}`, timedOut: false }));
    child.once("close", (code) => finish({ code, stdout, stderr, timedOut: false }));
  });
}

async function runPythonSuite(deadlineMs) {
  const tempDir = await mkdir(join(tmpdir(), "perf-smoke"), { recursive: true }).then(() => join(tmpdir(), "perf-smoke"));
  const jsonPath = join(tempDir, `python-${Date.now()}.json`);
  const result = await runCommand(
    "uv",
    ["run", "--no-sync", "--directory", join(ROOT, "services", "api"), "python", PYTHON_SUITE, "--json", jsonPath, "--deadline-ms", String(deadlineMs)],
    { timeoutMs: deadlineMs + 5_000 },
  );
  if (result.timedOut) {
    return { error: `python perf suite exceeded ${deadlineMs}ms`, stdout: result.stdout.slice(-400), stderr: result.stderr.slice(-400) };
  }
  if (!existsSync(jsonPath)) {
    return { error: `python perf suite produced no report (exit ${result.code})`, stdout: result.stdout.slice(-400), stderr: result.stderr.slice(-400) };
  }
  try {
    const report = JSON.parse(await readFile(jsonPath, "utf8"));
    return { report };
  } catch (error) {
    return { error: `python perf report unreadable: ${error?.message ?? error}` };
  }
}

const METRIC_EXTRACTORS = {
  median_ms: (benchmark) => benchmark.median,
  p95_ms: (benchmark) => benchmark.p95,
  total_ms: (benchmark) => benchmark.totalMs ?? benchmark.median,
  per_item_ms: (benchmark) => benchmark.perItemMs,
  items_per_second: (benchmark) => benchmark.itemsPerSecond,
  mib_per_second: (benchmark) => benchmark.mibPerSecond,
};

function checkBudgets(benchmarks, budgets) {
  const byId = new Map(benchmarks.map((benchmark) => [benchmark.id, benchmark]));
  return budgets.map((budget) => {
    const benchmark = byId.get(budget.id);
    const extractor = METRIC_EXTRACTORS[budget.metric];
    const observed = benchmark && extractor ? extractor(benchmark) : null;
    if (!benchmark || benchmark.status !== "measured" || observed === null || observed === undefined) {
      return { ...budget, observed: null, pass: null, status: benchmark ? benchmark.status : "missing" };
    }
    const pass = budget.direction === "min" ? observed >= budget.limit : observed <= budget.limit;
    return { ...budget, observed: round(observed), pass, status: "measured" };
  });
}

function exitCodeFor(budgets, benchmarks, failOnBudget) {
  if (!failOnBudget) return 0;
  if (benchmarks.some((benchmark) => benchmark.status === "failed")) return 1;
  return budgets.some((budget) => budget.pass === false) ? 1 : 0;
}

async function gitState() {
  const head = await runCommand("git", ["rev-parse", "HEAD"], { timeoutMs: 10_000 });
  const status = await runCommand("git", ["status", "--porcelain"], { timeoutMs: 10_000 });
  return { commit: head.stdout.trim() || null, dirty: Boolean(status.stdout.trim()) };
}

function parseArgs(argv) {
  const options = { budgetMs: 60_000, failOnBudget: false, jsonPath: null, noStack: false, cpuProfile: false };
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === "--budget-ms") { options.budgetMs = Number(argv[++index]); }
    else if (arg === "--fail-on-budget") { options.failOnBudget = true; }
    else if (arg === "--json") { options.jsonPath = argv[++index]; }
    else if (arg === "--no-stack") { options.noStack = true; }
    else if (arg === "--cpu-prof") { options.cpuProfile = true; }
    else if (arg === "--help" || arg === "-h") { options.help = true; }
    else { throw new Error(`unknown argument: ${arg}`); }
  }
  return options;
}

function printUsage() {
  console.log("Usage: node scripts/perf/perf-smoke.mjs [--json out.json] [--budget-ms 60000]");
  console.log("       [--fail-on-budget] [--no-stack] [--cpu-prof]");
  console.log("Bounded engineering-hot-path benchmark suite. Skips missing capabilities with a reason.");
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  if (options.help) { printUsage(); return 0; }
  const overallStart = nowMs();
  const deadline = overallStart + options.budgetMs;
  const remaining = () => Math.max(0, deadline - nowMs());
  const eventLoop = options.cpuProfile || process.env.AERO_PERF_PROFILE === "1" ? monitorEventLoopDelay({ resolution: 10 }) : null;
  eventLoop?.enable();

  const benchmarks = [];
  benchmarks.push(await measureNodeContentLookup());
  benchmarks.push(await measureNodeCanonicalDigest());
  benchmarks.push(await measureDoctor());
  if (eventLoop) {
    benchmarks.push(latency("node.event_loop_delay", "node", [eventLoop.mean / 1e6, eventLoop.max / 1e6], {
      iterations: 2, notes: "opt-in event-loop delay profile (mean, max) in ms",
    }));
  }

  const pythonBudget = Math.max(5_000, remaining() - 5_000);
  const python = await runPythonSuite(pythonBudget);
  if (python.report) {
    benchmarks.push(...python.report.benchmarks);
    benchmarks.push(latency("python.suite_wall", "python", [python.report.summary.wallMs ?? 0], {
      iterations: 1, notes: "wall time of the Python perf suite process (excludes Node benchmarks)",
    }));
  } else {
    benchmarks.push(failedMetric("python.suite", "python", python.error));
  }

  if (!options.noStack && remaining() > 12_000) {
    benchmarks.push(await measureStackColdStart(remaining() - 2_000));
  } else if (!options.noStack) {
    benchmarks.push(skipped("stack.cold_start_ready", "node", "suite budget exhausted before the product-stack cold start"));
  }

  const budgets = JSON.parse(await readFile(BUDGETS_PATH, "utf8")).budgets;
  const budgetResults = checkBudgets(benchmarks, budgets);
  const git = await gitState();

  const report = {
    schemaVersion: SCHEMA_VERSION,
    tool: "aero-perf-smoke",
    generatedAt: new Date().toISOString(),
    commit: git.commit,
    dirty: git.dirty,
    budgetMs: options.budgetMs,
    wallMs: round(nowMs() - overallStart),
    environment: {
      platform: process.platform, arch: process.arch, release: (await import("node:os")).release(),
      node: process.version, cpus: (await import("node:os")).cpus().length,
      totalMemoryMiB: round((await import("node:os")).totalmem() / (1024 * 1024), 1),
      python: python.report?.environment?.pythonVersion ?? null,
      uv: python.report?.environment?.uvVersion ?? null,
    },
    benchmarks,
    budgets: budgetResults,
    summary: {
      measured: benchmarks.filter((benchmark) => benchmark.status === "measured").length,
      skipped: benchmarks.filter((benchmark) => benchmark.status === "skipped").length,
      failed: benchmarks.filter((benchmark) => benchmark.status === "failed").length,
      budgetFailures: budgetResults.filter((budget) => budget.pass === false).length,
    },
  };
  eventLoop?.disable();

  await mkdir(REPORTS_DIR, { recursive: true });
  const jsonPath = options.jsonPath ?? join(REPORTS_DIR, `perf-smoke-${new Date().toISOString().replace(/[:.]/g, "-")}.json`);
  await writeFile(jsonPath, `${JSON.stringify(report, null, 2)}\n`, "utf8");
  printSummary(report, jsonPath);
  return exitCodeFor(budgetResults, benchmarks, options.failOnBudget);
}

function printSummary(report, jsonPath) {
  console.log(`[perf:smoke] ${JSON.stringify(report.summary)} wall=${report.wallMs}ms budget=${report.budgetMs}ms`);
  for (const benchmark of report.benchmarks) {
    if (benchmark.status === "measured") {
      const extra = benchmark.itemsPerSecond ? ` ${benchmark.itemsPerSecond}/s` : benchmark.mibPerSecond ? ` ${benchmark.mibPerSecond}MiB/s` : "";
      console.log(`  measured ${benchmark.id}: median=${benchmark.median}ms p95=${benchmark.p95}ms${extra}`);
    } else {
      console.log(`  ${benchmark.status} ${benchmark.id}: ${benchmark.reason}`);
    }
  }
  const failures = report.budgets.filter((budget) => budget.pass === false);
  if (failures.length > 0) {
    console.log(`  budget failures: ${failures.map((budget) => `${budget.id}=${budget.observed}${budget.direction === "min" ? ">=" : "<="}${budget.limit}`).join(", ")}`);
  }
  console.log(`[perf:smoke] report: ${jsonPath}`);
}

main()
  .then((code) => { process.exitCode = code; })
  .catch((error) => { console.error(`[perf:smoke] ${error?.stack ?? error}`); process.exitCode = 1; });
