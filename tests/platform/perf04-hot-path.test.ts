// PERF 04: measured hot-path tests for the Node edge.
//
// Bounded, deterministic timing tests. No native solver runs: probes are fake
// async work with a fixed delay, so the assertions measure orchestration
// concurrency and cache warmth, not host or solver speed.
import assert from "node:assert/strict";
import test from "node:test";

import { BASELINE_CHECK_IDS, runDoctor } from "../../scripts/platform/doctor.mjs";
import { CAPABILITY_MANIFESTS, CapabilityProbeCache } from "../../packages/solver-contracts/src/index.ts";

const SOLVER_IDS = [
  "openfoam", "code-aster", "precice", "ross", "pybamm", "elmer",
  "cantera", "pycycle", "cadquery", "gmsh", "openvsp", "freecad",
] as const;

const EXPECTED_ROUTES = [
  "/health", "/v1/native/capabilities", "/v1/native/participants",
  "/v1/native/analyses", "/v1/native/analyses/{job_id}",
  "/v1/native/analyses/{job_id}/events", "/v1/native/analyses/{job_id}/start",
  "/v1/native/analyses/{job_id}/cancel", "/v1/native/results/{job_id}",
  "/v1/native/artifacts/{job_id}", "/v1/native/provenance/{job_id}",
];

const PROBE_DELAY_MS = 25;
const delay = (milliseconds: number) => new Promise((resolve) => setTimeout(resolve, milliseconds));
const okSpawn = (stdout: string) => ({ status: 0, stdout, stderr: "" });

/** Fake env whose every probe takes a fixed delay and tracks peak concurrency. */
const makeTrackedEnv = () => {
  let active = 0;
  let peak = 0;
  const track = async (): Promise<void> => {
    active += 1;
    peak = Math.max(peak, active);
    await delay(PROBE_DELAY_MS);
    active -= 1;
  };
  const env = {
    nodeVersion: "v24.10.0",
    root: "/repo",
    home: "/home/tester",
    jobRootOverride: "",
    now: () => "2026-01-01T00:00:00.000Z",
    spawn: async (cmd: string) => {
      await track();
      if (cmd === "pnpm" || cmd === "pnpm.cmd" || cmd === "corepack") return okSpawn("11.19.0\n");
      if (cmd === "python" || cmd === "python3") return okSpawn("Python 3.12.2\n");
      if (cmd === "uv") return okSpawn("uv 0.9.6\n");
      if (cmd === "uv-api-preflight") {
        return okSpawn(JSON.stringify({ ok: true, version: "0.1.0", routes: EXPECTED_ROUTES, participants: 15 }));
      }
      throw Object.assign(new Error(`unexpected spawn: ${cmd}`), { code: "ENOENT" });
    },
    fsAccess: async () => undefined,
    fsStat: async () => ({ isDirectory: true }),
    apiFilesPresent: async () => true,
    checkPort: async () => ({ occupied: false, detail: "port is free" }),
    sqliteProbe: async () => { await track(); return { ok: true, version: "3.x", detail: "in-memory probe passed" }; },
    solverProbe: async () => { await track(); return { available: true, version: "1.0", detail: "native command responded" }; },
    solverIds: [...SOLVER_IDS],
  };
  return { env, peak: () => peak };
};

test("independent doctor probes run concurrently and report in deterministic order", async () => {
  const { env, peak } = makeTrackedEnv();
  const started = Date.now();
  const report = await runDoctor(env);
  const wallMs = Date.now() - started;
  assert.equal(report.baselineReady, true);
  assert.deepEqual(
    report.checks.map((check) => check.id),
    [...BASELINE_CHECK_IDS, ...SOLVER_IDS.map((id) => `solver:${id}`)],
    "assembled report order must not depend on probe completion order",
  );
  // 17 tracked probes × 25 ms ≈ 425 ms if serial. Concurrency must collapse it.
  assert.ok(peak() >= 8, `expected concurrent probes, observed peak ${peak()}`);
  assert.ok(wallMs < 250, `parallel doctor wall ${wallMs}ms should be far below the serial floor`);
  console.log(JSON.stringify({ "doctor.parallel_wall_ms": wallMs, "doctor.peak_concurrency": peak() }));
});

test("repeated capability queries are warm with no additional native probes", async () => {
  let probes = 0;
  const cache = new CapabilityProbeCache({
    probe: async () => {
      probes += 1;
      await delay(15);
      return { available: true, detail: "native command responded", version: "1.0" };
    },
    environment: {},
    executableIdentity: () => "stable-binary",
  });
  const coldStart = Date.now();
  await cache.detect(CAPABILITY_MANIFESTS);
  const coldMs = Date.now() - coldStart;
  const warmStart = Date.now();
  await cache.detect(CAPABILITY_MANIFESTS);
  const warmMs = Date.now() - warmStart;
  assert.equal(probes, CAPABILITY_MANIFESTS.length, "a warm detect must perform zero extra probes");
  assert.ok(warmMs <= coldMs, `warm ${warmMs}ms must not exceed cold ${coldMs}ms`);
  assert.ok(warmMs < 20, `warm detect ${warmMs}ms should be effectively free`);
  console.log(JSON.stringify({ "capability.cold_ms": coldMs, "capability.warm_ms": warmMs, probes }));
});
