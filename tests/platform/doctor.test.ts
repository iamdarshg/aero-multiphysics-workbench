import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

import {
  BASELINE_CHECK_IDS,
  CHECK_STATES,
  exitCodeFor,
  formatHuman,
  runDoctor,
  type DoctorEnv,
  type DoctorReport,
} from "../../scripts/platform/doctor.mjs";

const root = resolve(fileURLToPath(new URL("../..", import.meta.url)));

type SpawnCall = { cmd: string; args: readonly string[] };
type FsCall = { op: string; path: string };

const SOLVER_IDS = [
  "openfoam", "code-aster", "precice", "ross", "pybamm", "elmer",
  "cantera", "pycycle", "cadquery", "gmsh", "openvsp", "freecad",
] as const;

interface FakeWorld {
  env: DoctorEnv;
  spawns: SpawnCall[];
  fsCalls: FsCall[];
}

const okSpawn = (stdout: string) => ({ status: 0, stdout, stderr: "" });

/** Healthy fake: every baseline dependency present, every solver probed ready. */
const makeHealthyWorld = (): FakeWorld => {
  const spawns: SpawnCall[] = [];
  const fsCalls: FsCall[] = [];
  const env: DoctorEnv = {
    nodeVersion: "v24.10.0",
    root: "/repo",
    home: "/home/tester",
    jobRootOverride: "",
    now: () => "2026-09-14T00:00:00.000Z",
    spawn: async (cmd: string, args: readonly string[]) => {
      spawns.push({ cmd, args });
      if (cmd === "pnpm") return okSpawn("11.12.1\n");
      if (cmd === "python") return okSpawn("Python 3.12.2\n");
      if (cmd === "uv") return okSpawn("uv 0.8.0\n");
      if (cmd === "uv-api-preflight") {
        return okSpawn(JSON.stringify({
          ok: true,
          version: "0.1.0",
          routes: [
            "/health", "/api/v1/workbench/state",
            "/v1/native/capabilities", "/v1/native/participants",
            "/v1/native/analyses", "/v1/native/analyses/{job_id}",
            "/v1/native/analyses/{job_id}/events", "/v1/native/analyses/{job_id}/start",
            "/v1/native/analyses/{job_id}/cancel", "/v1/native/results/{job_id}",
            "/v1/native/artifacts/{job_id}", "/v1/native/provenance/{job_id}",
          ],
          participants: 15,
        }));
      }
      throw new Error(`unexpected spawn: ${cmd}`);
    },
    fsAccess: async (path: string) => { fsCalls.push({ op: "access", path }); },
    fsStat: async (path: string) => { fsCalls.push({ op: "stat", path }); return { isDirectory: true }; },
    apiFilesPresent: async () => true,
    checkPort: async () => ({ occupied: false, detail: "port is free" }),
    sqliteProbe: async () => ({ ok: true, version: "3.x", detail: "in-memory read-write probe passed" }),
    solverProbe: async (id: string) => ({ available: true, version: `${id}-test-1.0`, detail: "native command responded" }),
    solverIds: [...SOLVER_IDS],
  };
  return { env, spawns, fsCalls };
};

const checkById = (report: DoctorReport, id: string) =>
  report.checks.find((check) => check.id === id)!;

test("healthy mocked environment reports baseline ready with exit 0", async () => {
  const { env } = makeHealthyWorld();
  const report = await runDoctor(env);
  assert.equal(report.tool, "aero-doctor");
  assert.equal(report.baselineReady, true);
  assert.equal(report.baseline, "ready");
  assert.equal(exitCodeFor(report), 0);
  for (const id of BASELINE_CHECK_IDS) {
    assert.equal(checkById(report, id).state, "ready", `${id} should be ready`);
  }
  assert.equal(report.solvers.total, 12);
  assert.equal(report.solvers.ready.length, 12);
});

test("missing Node reports a blocking failure", async () => {
  const { env } = makeHealthyWorld();
  env.nodeVersion = "v18.19.0";
  const report = await runDoctor(env);
  assert.equal(checkById(report, "node").state, "failed");
  assert.equal(report.baselineReady, false);
  assert.equal(exitCodeFor(report), 1);
});

test("pnpm resolves through the Windows .cmd shim without a shell", async () => {
  const { env } = makeHealthyWorld();
  env.platform = "win32";
  env.spawn = async (cmd: string, args: readonly string[]) => {
    if (cmd === "pnpm.cmd") return okSpawn("11.19.0\n");
    throw Object.assign(new Error(`unexpected spawn: ${cmd}`), { code: "ENOENT" });
  };
  const report = await runDoctor(env);
  assert.equal(checkById(report, "pnpm").state, "ready");
  assert.equal(checkById(report, "pnpm").version, "11.19.0");
});

test("tool versions report dotted numbers, not banner prefixes", async () => {
  const { env } = makeHealthyWorld();
  env.spawn = async (cmd: string, args: readonly string[]) => {
    if (cmd === "uv") return okSpawn("uv 0.9.6 (dc984d2d2 2025-11-11)\n");
    return makeHealthyWorld().env.spawn(cmd, args);
  };
  const report = await runDoctor(env);
  assert.equal(checkById(report, "uv").version, "0.9.6");
});

test("missing Python reports a blocking failure", async () => {
  const { env } = makeHealthyWorld();
  env.spawn = async (cmd: string, args: readonly string[]) => {
    if (cmd === "python") throw Object.assign(new Error("spawn python ENOENT"), { code: "ENOENT" });
    if (cmd === "python3") throw Object.assign(new Error("spawn python3 ENOENT"), { code: "ENOENT" });
    return makeHealthyWorld().env.spawn(cmd, args);
  };
  const report = await runDoctor(env);
  assert.equal(checkById(report, "python").state, "failed");
  assert.match(checkById(report, "python").detail, /not found|unavailable/i);
  assert.equal(report.baselineReady, false);
  assert.equal(exitCodeFor(report), 1);
});

test("missing uv reports a blocking failure", async () => {
  const { env } = makeHealthyWorld();
  const inner = env.spawn;
  env.spawn = async (cmd: string, args: readonly string[]) => {
    if (cmd === "uv") throw Object.assign(new Error("spawn uv ENOENT"), { code: "ENOENT" });
    return inner(cmd, args);
  };
  const report = await runDoctor(env);
  assert.equal(checkById(report, "uv").state, "failed");
  assert.equal(report.baselineReady, false);
  assert.equal(exitCodeFor(report), 1);
});

test("missing optional solver is unavailable but baseline still exits 0", async () => {
  const { env } = makeHealthyWorld();
  env.solverProbe = async (id: string) =>
    id === "openfoam"
      ? { available: false, detail: "command not found" }
      : { available: true, version: "9.9", detail: "native command responded" };
  const report = await runDoctor(env);
  const openfoam = checkById(report, "solver:openfoam");
  assert.ok(openfoam.state === "unavailable" || openfoam.state === "warning");
  assert.equal(openfoam.version, null);
  assert.equal(report.baselineReady, true);
  assert.equal(exitCodeFor(report), 0);
  assert.deepEqual(report.solvers.unavailable, ["openfoam"]);
});

test("version probe failure is reported honestly without an invented version", async () => {
  const { env } = makeHealthyWorld();
  env.solverProbe = async () => ({ available: false, detail: "command exited 1" });
  const report = await runDoctor(env);
  for (const id of SOLVER_IDS) {
    const check = checkById(report, `solver:${id}`);
    assert.equal(check.version, null, `${id} must not invent a version`);
    assert.match(check.detail, /exited 1/);
  }
  assert.equal(report.baselineReady, true);
});

test("JSON report schema is deterministic", async () => {
  const first = await runDoctor(makeHealthyWorld().env);
  const second = await runDoctor(makeHealthyWorld().env);
  const strip = (report: DoctorReport) => ({ ...report, checkedAt: "STABLE" });
  assert.deepEqual(strip(first), strip(second));
  assert.deepEqual(
    first.checks.map((check) => check.id),
    [...BASELINE_CHECK_IDS, ...SOLVER_IDS.map((id) => `solver:${id}`)],
  );
  for (const check of first.checks) {
    assert.deepEqual(Object.keys(check).sort(), ["detail", "id", "remediation", "state", "tier", "version"]);
    assert.ok((CHECK_STATES as readonly string[]).includes(check.state));
    assert.ok(check.tier === "baseline" || check.tier === "optional");
  }
  assert.equal(first.schema, 1);
});

test("doctor performs no installs or destructive actions", async () => {
  const { env, spawns, fsCalls } = makeHealthyWorld();
  await runDoctor(env);
  assert.ok(spawns.length > 0, "expected probes to run");
  for (const call of spawns) {
    const text = `${call.cmd} ${call.args.join(" ")}`.toLowerCase();
    assert.ok(!text.includes("install"), `must not install: ${text}`);
    assert.ok(!text.includes("micromamba"), `must not touch solver setup: ${text}`);
    assert.ok(!/(^|\s)--sync(\s|$)/.test(`${text} `), `must not sync deps: ${text}`);
  }
  const writeOps = fsCalls.filter((call) => !["access", "stat"].includes(call.op));
  assert.deepEqual(writeOps, []);
});

test("human output renders a table plus remediation hints", async () => {
  const { env } = makeHealthyWorld();
  env.solverProbe = async (id: string) =>
    id === "gmsh" ? { available: false, detail: "command not found" } : { available: true, version: "1.0", detail: "ok" };
  const report = await runDoctor(env);
  const human = formatHuman(report);
  assert.match(human, /CHECK.*STATE.*DETAIL/);
  assert.match(human, /solver:gmsh/);
  assert.match(human, /pnpm setup:solvers/);
  assert.match(human, /Baseline: READY/);
});

test("occupied ports are reported as warnings without blocking the baseline", async () => {
  const { env } = makeHealthyWorld();
  env.checkPort = async (port: number) =>
    port === 8000 ? { occupied: true, detail: "port 8000 is occupied" } : { occupied: false, detail: "port is free" };
  const report = await runDoctor(env);
  assert.equal(checkById(report, "port-8000").state, "warning");
  assert.equal(report.baselineReady, true);
  assert.equal(exitCodeFor(report), 0);
});

test("real CLI emits stable JSON and a consistent exit code", () => {
  const script = join(root, "scripts", "platform", "doctor.mjs");
  const result = spawnSync(process.execPath, [script, "--json"], { encoding: "utf8", timeout: 180_000 });
  assert.ok(result.stdout.trim().length > 0, `expected JSON on stdout, stderr: ${result.stderr}`);
  const report = JSON.parse(result.stdout) as DoctorReport;
  assert.equal(report.tool, "aero-doctor");
  assert.ok(Array.isArray(report.checks) && report.checks.length === BASELINE_CHECK_IDS.length + 12);
  assert.equal(result.status, report.baselineReady ? 0 : 1);
});
