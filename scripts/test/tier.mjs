#!/usr/bin/env node
// Tiered test runner (issue #30). Bounded, deterministic, no network by default.
// Usage: node scripts/test/tier.mjs <fast|focused|integration|native-smoke|science|all|list>
// Docs: docs/testing-tiers.md
import { spawn, spawnSync } from "node:child_process";
import { existsSync, readdirSync, readFileSync, rmSync } from "node:fs";
import { fileURLToPath, pathToFileURL } from "node:url";
import { tmpdir } from "node:os";
import { dirname, join, delimiter } from "node:path";

const SCRIPT_DIR = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = join(SCRIPT_DIR, "..", "..");
const IS_WINDOWS = process.platform === "win32";
const PY_ROOT = "../../tests";

export const EXIT = { OK: 0, FAILURE: 1, USAGE: 2, BUDGET: 3 };

export const BUDGETS = {
  fast: 120,
  focused: 300,
  integration: 300,
  "native-smoke": 300,
  science: 900,
  all: 1200,
};

const FAST_PHYSICS_PURE = [
  `${PY_ROOT}/physics/test_aircraft_demo.py`,
  `${PY_ROOT}/physics/test_gas_turbine_demo.py`,
  `${PY_ROOT}/physics/test_scalar_coupling.py`,
  `${PY_ROOT}/physics/test_result_inspection.py`,
  `${PY_ROOT}/physics/test_edf_electrical_dynamic_loop.py`,
  `${PY_ROOT}/physics/test_geometry_semantics_mesh.py`,
  `${PY_ROOT}/physics/test_precice_benchmark.py`,
  `${PY_ROOT}/physics/test_native_benchmarks.py`,
  `${PY_ROOT}/physics/test_participant_lifecycle.py`,
];

const HEAVY_PHYSICS_STEPS = {
  "tests/physics/test_native_execution.py": ["py-native-execution", "py-native-smoke"],
  "tests/physics/test_governed_product_jobs.py": ["py-integration-native"],
  "tests/physics/test_generic_multiphysics_substrate.py": ["py-science-substrate"],
  "tests/physics/test_edf_80mm_three_stage.py": ["py-science-edf"],
  "tests/physics/test_milestone3_orchestration.py": ["py-science-milestone3"],
};

export const STEP_ORDER = [
  "js-web",
  "js-unit-fast",
  "js-unit-all",
  "js-audit",
  "js-platform-fast",
  "js-platform-all",
  "js-smoke",
  "js-stack-live",
  "js-mcp-stdio",
  "js-fast-tests",
  "py-core",
  "py-integration",
  "py-fast-physics",
  "py-fast-tests",
  "py-integration-native",
  "py-native-execution",
  "py-native-smoke",
  "py-science-edf",
  "py-science-substrate",
  "py-science-milestone3",
  "py-all",
];

const allowSync = process.env.AERO_TEST_ALLOW_SYNC === "1";

function listTestFiles(dir, suffix) {
  const abs = join(REPO_ROOT, dir);
  if (!existsSync(abs)) return [];
  return readdirSync(abs)
    .filter((name) => name.endsWith(suffix))
    .sort()
    .map((name) => `${dir}/${name}`);
}

function unitFiles(exclude = []) {
  return listTestFiles("tests/unit", ".test.ts").filter((f) => !exclude.includes(f));
}

function pythonStep(name, { paths = [], keyword, timeoutSeconds, perTestTimeoutSeconds }) {
  const args = ["run"];
  if (!allowSync) args.push("--no-sync");
  args.push("--directory", "services/api", "pytest", "-q", "-c", "pyproject.toml", "--durations=15");
  if (keyword) args.push("-k", keyword);
  if (paths.length) args.push(...paths);
  const env = {};
  if (perTestTimeoutSeconds > 0) {
    args.push("-p", "pytest_hang_guard");
    env.AERO_TEST_TIMEOUT_SECONDS = String(perTestTimeoutSeconds);
    const inherited = process.env.PYTHONPATH ? `${process.env.PYTHONPATH}${delimiter}` : "";
    env.PYTHONPATH = `${inherited}${SCRIPT_DIR}`;
  }
  return { name, command: "uv", args, timeoutSeconds, env };
}

export function makeStep(name) {
  switch (name) {
    case "js-web":
      return { name, command: "pnpm", args: ["--filter", "@aero/web", "test"], timeoutSeconds: 180, env: {} };
    case "js-unit-fast":
      return {
        name,
        command: "node",
        args: [
          "--test",
          "--test-timeout=60000",
          ...unitFiles(["tests/unit/stack-live.test.ts", "tests/unit/requirements-audit.test.ts"]),
        ],
        timeoutSeconds: 120,
        env: {},
      };
    case "js-unit-all":
      return {
        name,
        command: "node",
        args: ["--test", "--test-timeout=120000", ...unitFiles()],
        timeoutSeconds: 300,
        env: {},
      };
    case "js-audit":
      return {
        name,
        command: "node",
        args: ["--test", "--test-timeout=60000", "tests/unit/requirements-audit.test.ts"],
        timeoutSeconds: 120,
        env: {},
      };
    case "js-platform-fast":
      return {
        name,
        command: "node",
        args: [
          "--test",
          "--test-timeout=60000",
          "tests/platform/platform.test.ts",
          "tests/platform/participants.test.ts",
          "tests/platform/doctor.test.ts",
        ],
        timeoutSeconds: 120,
        env: {},
      };
    case "js-platform-all":
      return {
        name,
        command: "node",
        args: ["--test", "--test-timeout=180000", ...listTestFiles("tests/platform", ".test.ts")],
        timeoutSeconds: 300,
        env: {},
      };
    case "js-smoke":
      return {
        name,
        command: "node",
        args: ["--test", "--test-timeout=60000", "tests/smoke/workspace.test.mjs"],
        timeoutSeconds: 60,
        env: {},
      };
    case "js-stack-live":
      return {
        name,
        command: "node",
        args: ["--test", "--test-timeout=120000", "tests/unit/stack-live.test.ts"],
        timeoutSeconds: 180,
        env: {},
      };
    case "js-mcp-stdio":
      return {
        name,
        command: "node",
        args: ["--test", "--test-timeout=180000", "tests/platform/mcp-stdio.test.ts"],
        timeoutSeconds: 240,
        env: {},
      };
    case "js-fast-tests":
      return {
        name,
        command: "node",
        args: ["--test", "--test-timeout=60000", ...listTestFiles("tests/fast", ".test.mjs")],
        timeoutSeconds: 60,
        env: {},
      };
    case "py-core":
      return pythonStep(name, {
        paths: [`${PY_ROOT}/core`],
        timeoutSeconds: 120,
        perTestTimeoutSeconds: 90,
      });
    case "py-integration":
      return pythonStep(name, {
        paths: [`${PY_ROOT}/integration`],
        timeoutSeconds: 120,
        perTestTimeoutSeconds: 90,
      });
    case "py-fast-physics":
      return pythonStep(name, {
        paths: FAST_PHYSICS_PURE,
        timeoutSeconds: 120,
        perTestTimeoutSeconds: 90,
      });
    case "py-fast-tests":
      return pythonStep(name, {
        paths: [`${PY_ROOT}/fast`],
        timeoutSeconds: 60,
        perTestTimeoutSeconds: 60,
      });
    case "py-integration-native":
      return pythonStep(name, {
        paths: [`${PY_ROOT}/physics/test_governed_product_jobs.py`],
        timeoutSeconds: 240,
        perTestTimeoutSeconds: 150,
      });
    case "py-native-execution":
      return pythonStep(name, {
        paths: [`${PY_ROOT}/physics/test_native_execution.py`],
        timeoutSeconds: 240,
        perTestTimeoutSeconds: 150,
      });
    case "py-native-smoke":
      return pythonStep(name, {
        paths: [`${PY_ROOT}/physics/test_native_execution.py`],
        keyword: "benchmark_runs_natively",
        timeoutSeconds: 240,
        perTestTimeoutSeconds: 180,
      });
    case "py-science-edf":
      return pythonStep(name, {
        paths: [`${PY_ROOT}/physics/test_edf_80mm_three_stage.py`],
        timeoutSeconds: 600,
        perTestTimeoutSeconds: 300,
      });
    case "py-science-substrate":
      return pythonStep(name, {
        paths: [`${PY_ROOT}/physics/test_generic_multiphysics_substrate.py`],
        timeoutSeconds: 600,
        perTestTimeoutSeconds: 300,
      });
    case "py-science-milestone3":
      return pythonStep(name, {
        paths: [`${PY_ROOT}/physics/test_milestone3_orchestration.py`],
        timeoutSeconds: 600,
        perTestTimeoutSeconds: 300,
      });
    case "py-all":
      return pythonStep(name, { timeoutSeconds: 900, perTestTimeoutSeconds: 600 });
    default:
      throw new Error(`unknown step: ${name}`);
  }
}

export const TIERS = {
  fast: [
    "js-unit-fast",
    "js-platform-fast",
    "js-web",
    "js-smoke",
    "js-fast-tests",
    "py-core",
    "py-integration",
    "py-fast-physics",
    "py-fast-tests",
  ],
  integration: ["js-stack-live", "js-mcp-stdio", "py-integration-native", "py-native-execution"],
  "native-smoke": ["py-native-smoke"],
  science: ["py-science-edf", "py-science-substrate", "py-science-milestone3"],
  all: ["js-web", "js-unit-all", "js-platform-all", "js-smoke", "js-fast-tests", "py-all"],
};

export function selectSteps(changedPaths) {
  const selected = new Set();
  for (const raw of changedPaths) {
    const p = raw.replace(/\\/g, "/");
    const heavy = HEAVY_PHYSICS_STEPS[p];
    if (heavy) {
      heavy.forEach((s) => selected.add(s));
      continue;
    }
    if (p.startsWith("apps/web/")) selected.add("js-web");
    else if (
      p === "tests/unit/requirements-audit.test.ts" ||
      p.startsWith("scripts/audit-requirements") ||
      p === "docs/requirements-audit.json"
    )
      selected.add("js-audit");
    else if (p.startsWith("tests/unit/")) selected.add("js-unit-fast");
    else if (p.startsWith("tests/smoke/")) selected.add("js-smoke");
    else if (p.startsWith("tests/platform/")) selected.add("js-platform-fast");
    else if (p.startsWith("tests/fast/")) selected.add("js-fast-tests");
    else if (p.startsWith("scripts/platform/")) selected.add("js-unit-fast");
    else if (p.startsWith("scripts/test/tier.mjs")) selected.add("js-fast-tests");
    else if (p.startsWith("packages/solver-contracts/")) selected.add("js-platform-fast");
    else if (p.startsWith("packages/")) selected.add("js-unit-fast");
    else if (p.startsWith("tests/core/")) selected.add("py-core");
    else if (p.startsWith("tests/integration/")) selected.add("py-integration");
    else if (p.startsWith("tests/physics/")) selected.add("py-fast-physics");
    else if (p.startsWith("services/api/")) {
      selected.add("py-core");
      selected.add("py-integration");
      selected.add("py-fast-physics");
    } else if (p.startsWith("solvers/") || /\.py$/.test(p)) selected.add("py-core");
  }
  return STEP_ORDER.filter((name) => selected.has(name));
}

export function parseArgs(argv) {
  const opts = { tier: null, budgetSeconds: null, json: false, paths: null, help: false };
  const rest = [...argv];
  while (rest.length > 0) {
    const arg = rest.shift();
    if (arg === "--help" || arg === "-h") opts.help = true;
    else if (arg === "--json") opts.json = true;
    else if (arg === "--budget-seconds") opts.budgetSeconds = Number(rest.shift());
    else if (arg === "--paths") opts.paths = String(rest.shift() ?? "").split(",").map((s) => s.trim()).filter(Boolean);
    else if (!arg.startsWith("-") && opts.tier === null) opts.tier = arg;
    else throw Object.assign(new Error(`unknown argument: ${arg}`), { usage: true });
  }
  return opts;
}

export function changedPathsFromGit() {
  const set = new Set();
  const probes = [
    ["diff", "--name-only", "HEAD"],
    ["diff", "--name-only", "--cached"],
    ["ls-files", "--others", "--exclude-standard"],
  ];
  for (const args of probes) {
    const res = spawnSync("git", args, { cwd: REPO_ROOT, encoding: "utf8" });
    if (res.status !== 0 || !res.stdout) continue;
    for (const line of res.stdout.split(/\r?\n/)) {
      const p = line.trim();
      if (p) set.add(p.replace(/\\/g, "/"));
    }
  }
  return [...set];
}

function resolveCommand(command) {
  if (command === "node") return process.execPath;
  if (command === "pnpm") return IS_WINDOWS ? "pnpm.cmd" : "pnpm";
  if (command === "uv") return IS_WINDOWS ? "uv.exe" : "uv";
  return command;
}

function killTree(child) {
  if (!child || child.exitCode !== null) return;
  if (IS_WINDOWS) {
    try {
      spawnSync("taskkill", ["/pid", String(child.pid), "/T", "/F"], { stdio: "ignore" });
    } catch {
      // best effort
    }
  } else {
    try {
      process.kill(-child.pid, "SIGKILL");
    } catch {
      // best effort
    }
  }
  try {
    child.kill("SIGKILL");
  } catch {
    // best effort
  }
}

let currentChild = null;
process.on("SIGINT", () => {
  process.stderr.write("\n[tier] interrupted, terminating child tree\n");
  killTree(currentChild);
  process.exit(130);
});

function runStep(step, timeoutMs) {
  return new Promise((resolve) => {
    const command = resolveCommand(step.command);
    const env = { ...process.env, ...step.env };
    const hangLog = step.env.AERO_TEST_TIMEOUT_SECONDS
      ? join(tmpdir(), `aero-hang-guard-${process.pid}-${Date.now()}.log`)
      : null;
    if (hangLog) env.AERO_HANG_GUARD_LOG = hangLog;
    const useShell = step.command === "pnpm" && IS_WINDOWS;
    process.stdout.write(`\n[tier] >> ${step.name} (budget ${Math.round(timeoutMs / 1000)}s)\n`);
    const shellLine = useShell ? [command, ...step.args].join(" ") : null;
    const child = spawn(useShell ? shellLine : command, useShell ? [] : step.args, {
      cwd: REPO_ROOT,
      env,
      stdio: "inherit",
      shell: useShell,
      detached: !IS_WINDOWS,
    });
    currentChild = child;
    let settled = false;
    const reportHangLog = () => {
      if (!hangLog || !existsSync(hangLog)) return;
      try {
        const diagnostics = readFileSync(hangLog, "utf8").trim();
        if (diagnostics) process.stderr.write(`\n[tier] hang-guard diagnostics for ${step.name}:\n${diagnostics}\n`);
      } catch {
        // diagnostics are best effort
      } finally {
        try {
          rmSync(hangLog, { force: true });
        } catch {
          // best effort
        }
      }
    };
    const finish = (status) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      currentChild = null;
      reportHangLog();
      resolve(status);
    };
    const timer = setTimeout(() => {
      process.stderr.write(`\n[tier] TIMEOUT ${step.name} after ${Math.round(timeoutMs / 1000)}s; killing process tree\n`);
      killTree(child);
      finish("timeout");
    }, timeoutMs);
    child.on("error", (error) => {
      process.stderr.write(`[tier] failed to launch ${step.name}: ${error.message}\n`);
      finish(EXIT.FAILURE);
    });
    child.on("exit", (code, signal) => {
      if (signal) return finish("timeout");
      if (code === 42) return finish("timeout");
      finish(code === 0 ? EXIT.OK : EXIT.FAILURE);
    });
  });
}

export async function runTier(tierName, opts = {}) {
  const names = opts.steps ?? TIERS[tierName];
  if (!names) return { code: EXIT.USAGE, reason: `unknown tier: ${tierName}` };
  const budgetSeconds = opts.budgetSeconds ?? BUDGETS[tierName] ?? 300;
  const deadline = Date.now() + budgetSeconds * 1000;
  const timings = [];
  let code = EXIT.OK;
  for (const name of names) {
    const remaining = deadline - Date.now();
    if (remaining <= 0) {
      process.stderr.write(`[tier] budget ${budgetSeconds}s exhausted before ${name}\n`);
      code = EXIT.BUDGET;
      break;
    }
    const step = makeStep(name);
    const timeoutMs = Math.min(step.timeoutSeconds * 1000, remaining);
    const started = Date.now();
    const status = await runStep(step, timeoutMs);
    const seconds = (Date.now() - started) / 1000;
    timings.push({ name, seconds, status });
    if (status === "timeout") {
      code = EXIT.BUDGET;
      break;
    }
    if (status !== EXIT.OK) {
      code = EXIT.FAILURE;
      break;
    }
  }
  const totalSeconds = timings.reduce((a, t) => a + t.seconds, 0);
  const slowest = [...timings].sort((a, b) => b.seconds - a.seconds).slice(0, 8);
  process.stdout.write(`\n[tier] ${tierName}: ${code === EXIT.OK ? "PASS" : code === EXIT.BUDGET ? "TIMEOUT/BUDGET" : "FAIL"} in ${totalSeconds.toFixed(1)}s (budget ${budgetSeconds}s)\n`);
  process.stdout.write("[tier] slowest steps:\n");
  for (const t of slowest) process.stdout.write(`[tier]   ${t.seconds.toFixed(1)}s  ${t.name}  (${t.status})\n`);
  if (opts.json) {
    process.stdout.write(`TIER_SUMMARY ${JSON.stringify({ tier: tierName, code, budgetSeconds, totalSeconds: Number(totalSeconds.toFixed(2)), steps: timings })}\n`);
  }
  return { code, timings, totalSeconds };
}

function printUsage() {
  process.stdout.write(
    [
      "Tiered test runner (issue #30)",
      "",
      "Usage: node scripts/test/tier.mjs <tier> [--budget-seconds N] [--json]",
      "       node scripts/test/tier.mjs focused [--paths a.ts,b/py,path]",
      "       node scripts/test/tier.mjs list",
      "",
      "Tiers:",
      "  fast         unit/contracts + tiny pure-Python tests (target <=120s)",
      "  focused      changed-path selection (bounded, <=300s)",
      "  integration  local API/job/MCP/stack integration (bounded, <=300s)",
      "  native-smoke tiny installed-solver proofs, opt-in (<=300s)",
      "  science      mesh/time-independence + coupled heavy benchmarks (explicit)",
      "  all          CI/release aggregation (not the default edit loop)",
      "",
      "Env: AERO_TEST_ALLOW_SYNC=1 permits uv to sync before running (default: --no-sync, fail closed).",
      "",
    ].join("\n"),
  );
}

async function main() {
  let opts;
  try {
    opts = parseArgs(process.argv.slice(2));
  } catch (error) {
    process.stderr.write(`${error.message}\n\n`);
    printUsage();
    process.exit(EXIT.USAGE);
  }
  if (opts.help) {
    printUsage();
    process.exit(EXIT.OK);
  }
  if (opts.tier === "list") {
    process.stdout.write(Object.keys(TIERS).join("\n") + "\n");
    process.exit(EXIT.OK);
  }
  if (!opts.tier) {
    printUsage();
    process.exit(EXIT.USAGE);
  }
  let steps = null;
  if (opts.tier === "focused") {
    const changed = opts.paths ?? changedPathsFromGit();
    steps = selectSteps(changed);
    if (steps.length === 0) {
      process.stderr.write("[tier] no mapped changes, falling back to fast tier\n");
      steps = TIERS.fast;
    }
    process.stdout.write(`[tier] focused on ${steps.length} step(s): ${steps.join(", ")}\n`);
  } else if (!TIERS[opts.tier]) {
    process.stderr.write(`unknown tier: ${opts.tier}\n\n`);
    printUsage();
    process.exit(EXIT.USAGE);
  }
  const result = await runTier(opts.tier, { ...opts, steps });
  process.exit(result.code);
}

const invokedDirectly = process.argv[1] && pathToFileURL(process.argv[1]).href === import.meta.url;
if (invokedDirectly) {
  main().catch((error) => {
    process.stderr.write(`[tier] internal error: ${error?.stack ?? error}\n`);
    process.exit(EXIT.FAILURE);
  });
}
