import assert from "node:assert/strict";
import { createServer } from "node:http";
import type { AddressInfo } from "node:net";
import test from "node:test";

import {
  E2E_JOB_TIMEOUT_MS_DEFAULT,
  E2E_OVERALL_TIMEOUT_MS_DEFAULT,
  E2E_READY_TIMEOUT_MS_DEFAULT,
  NATIVE_SMOKE_CANDIDATES,
  TERMINAL_STATES,
  UI_MARKER,
  boundedDeadline,
  buildSummary,
  captureOwnedPids,
  checkUiMarker,
  fetchEvents,
  fetchResultBundle,
  liveDescendants,
  parseArgs,
  pickNativeCandidate,
  pidFromSpawnLine,
  pollJobState,
  resolveConfig,
  submitJob,
} from "../../scripts/platform/product-e2e.mjs";

test("release E2E arg parsing has bounded defaults and rejects misuse", () => {
  const defaults = parseArgs([]);
  assert.equal(defaults.apiPort, 18233);
  assert.equal(defaults.webPort, 13233);
  assert.equal(defaults.readyTimeoutMs, E2E_READY_TIMEOUT_MS_DEFAULT);
  assert.equal(defaults.jobTimeoutMs, E2E_JOB_TIMEOUT_MS_DEFAULT);
  assert.equal(defaults.overallTimeoutMs, E2E_OVERALL_TIMEOUT_MS_DEFAULT);
  assert.equal(defaults.nativeSmoke, false);
  assert.equal(defaults.help, false);

  const custom = parseArgs([
    "--api-port", "18234",
    "--web-port", "13234",
    "--overall-timeout-ms", "300000",
    "--native-smoke",
  ]);
  assert.equal(custom.apiPort, 18234);
  assert.equal(custom.webPort, 13234);
  assert.equal(custom.overallTimeoutMs, 300000);
  assert.equal(custom.nativeSmoke, true);

  assert.throws(() => parseArgs(["--api-port", "huge"]), /E2E_USAGE/);
  assert.throws(() => parseArgs(["--bogus"]), /E2E_USAGE/);
  assert.throws(() => parseArgs(["--api-port"]), /E2E_USAGE/);
  assert.throws(() => parseArgs(["--overall-timeout-ms", "0"]), /E2E_USAGE/);
  assert.throws(() => parseArgs(["--job-timeout-ms", "nope"]), /E2E_USAGE/);
  assert.deepEqual(parseArgs(["--help"]).help, true);
});

test("release E2E config honors environment overrides and isolates state", () => {
  const config = resolveConfig({
    argv: [],
    env: {
      AERO_E2E_API_PORT: "18300",
      AERO_E2E_WEB_PORT: "13300",
      AEROWORKBENCH_JOB_ROOT: "/tmp/e2e-jobs",
      AERO_E2E_SUMMARY_DIR: "/tmp/e2e-summary",
    },
    root: "/repo",
  });
  assert.equal(config.apiPort, 18300);
  assert.equal(config.webPort, 13300);
  assert.equal(config.apiBase, "http://127.0.0.1:18300");
  assert.equal(config.webBase, "http://127.0.0.1:13300");
  assert.equal(config.jobRoot, "/tmp/e2e-jobs");
  assert.equal(config.summaryDir, "/tmp/e2e-summary");
  assert.equal(config.overallTimeoutMs, E2E_OVERALL_TIMEOUT_MS_DEFAULT);

  const isolated = resolveConfig({ argv: [], env: {}, root: "/repo" });
  assert.match(isolated.jobRoot, /aero-e2e-jobs/);
  assert.match(isolated.summaryDir, /aero-e2e-summary/);
  assert.notEqual(isolated.jobRoot, isolated.summaryDir);
});

test("phase deadlines never outlive the overall release-smoke budget", () => {
  assert.equal(boundedDeadline(1_000, 500), 500);
  assert.equal(boundedDeadline(400, 500), 400);
  assert.equal(boundedDeadline(500, 500), 500);
});

test("release E2E tracks the tiny deterministic participant and terminal states", () => {
  assert.deepEqual([...TERMINAL_STATES].sort(), ["CANCELLED", "COMPLETED", "FAILED"]);
  assert.equal(UI_MARKER, "Aero Workbench");
});

test("native smoke candidate picker is capability-gated and honest", () => {
  assert.ok(NATIVE_SMOKE_CANDIDATES.length >= 2);
  for (const candidate of NATIVE_SMOKE_CANDIDATES) {
    assert.match(candidate.participantId, /^[a-z0-9][a-z0-9-]*$/);
    assert.ok(candidate.inputs && typeof candidate.inputs === "object");
  }
  const picked = pickNativeCandidate({
    ready: [{ participant_id: "rotor-campbell" }, { participant_id: "cell-spm-discharge" }],
    unavailable: [],
  });
  assert.equal(picked?.participantId, "cell-spm-discharge");

  const skipped = pickNativeCandidate({ ready: [], unavailable: [] });
  assert.equal(skipped, null);
});

test("UI marker check requires the served workbench title", () => {
  assert.equal(checkUiMarker("<html><head><title>Aero Workbench</title></head></html>"), true);
  assert.equal(checkUiMarker("<html><body>router error</body></html>"), false);
  assert.equal(checkUiMarker(""), false);
});

test("owned PIDs are parsed from stack service spawn lines only", () => {
  assert.deepEqual(pidFromSpawnLine("[stack] [api] spawned pid 1234; waiting for health"), { service: "api", pid: 1234 });
  assert.deepEqual(pidFromSpawnLine("[web] spawned pid 5678"), { service: "web", pid: 5678 });
  assert.equal(pidFromSpawnLine("[stack] stack ready: api=http://127.0.0.1:18233"), null);
  assert.equal(pidFromSpawnLine(""), null);
});

test("owned PID capture unions spawn lines with the real process tree", async () => {
  // No tree-walkable root: falls back to the parsed spawn lines only.
  const fromLines = await captureOwnedPids(NaN, new Map([["api", 111], ["web", 222]]));
  assert.deepEqual(fromLines.sort((a, b) => a - b), [111, 222]);

  // A live root contributes itself and its descendants; invalid entries dropped.
  const owned = await captureOwnedPids(process.pid, new Map([["web", 0], ["api", -3]]));
  assert.ok(owned.includes(process.pid));
  assert.ok(owned.every((pid) => Number.isInteger(pid) && pid > 0));
});

test("live descendants exclude the CLI root and report only living PIDs", () => {
  const dead = 2_147_483_600; // far above any real PID on this host
  const owned = [process.pid, dead, 0, -1];
  const live = liveDescendants(owned, process.pid);
  assert.ok(!live.includes(process.pid), "root is not an orphan");
  assert.ok(!live.includes(dead), "dead PID is not an orphan");
  assert.deepEqual(live, []);
});

test("release summary carries the machine-readable release gate fields", () => {
  const summary = buildSummary({
    commitSha: "abc123",
    jobId: "job-1",
    source: "native_solver",
    fidelity: "beam-campbell",
    nativeSmoke: { status: "SKIPPED", reason: "no verified native solver capability ready" },
    shutdown: { clean: true, stopped: ["api", "web"], orphans: [] },
  });
  assert.equal(summary.tool, "aero-product-e2e");
  assert.equal(summary.jobId, "job-1");
  assert.equal(summary.source, "native_solver");
  assert.equal(summary.nativeSmoke.status, "SKIPPED");
  assert.deepEqual(summary.shutdown.orphans, []);
});

const startStubApi = (): Promise<{ close: () => Promise<void>; base: string }> =>
  new Promise((resolve) => {
    let polls = 0;
    const server = createServer((request, response) => {
      const send = (status: number, payload: unknown): void => {
        response.writeHead(status, { "content-type": "application/json" });
        response.end(JSON.stringify(payload));
      };
      const url = new URL(request.url ?? "/", "http://127.0.0.1");
      if (request.method === "POST" && url.pathname === "/v1/native/analyses") {
        send(202, { job_id: "e2e-job-1" });
        return;
      }
      if (url.pathname === "/v1/native/analyses/e2e-job-1") {
        polls += 1;
        send(200, {
          job_id: "e2e-job-1",
          state: polls < 2 ? "RUNNING" : "COMPLETED",
          run_id: "run-1",
          result_id: "a".repeat(64),
          provenance_id: "prov-1",
        });
        return;
      }
      if (url.pathname === "/v1/native/analyses/e2e-job-1/events") {
        send(200, {
          job_id: "e2e-job-1",
          events: [
            { sequence: 1, state: "QUEUED", at: "2026-09-15T00:00:00.000Z" },
            { sequence: 2, state: "COMPLETED", at: "2026-09-15T00:00:01.000Z" },
          ],
        });
        return;
      }
      if (url.pathname === "/v1/native/results/e2e-job-1") {
        send(200, { source: "native_solver", fidelity: "beam-campbell", run_id: "run-1", provenance_id: "prov-1" });
        return;
      }
      if (url.pathname === "/v1/native/results/e2e-job-1/manifest") {
        send(200, { job_id: "e2e-job-1", result_id: "a".repeat(64), source: "native_solver", fidelity: "beam-campbell" });
        return;
      }
      if (url.pathname === "/v1/native/provenance/e2e-job-1") {
        send(200, { job_id: "e2e-job-1", events: [{ event_type: "native.launch-accepted" }, { event_type: "native.result-recorded" }] });
        return;
      }
      send(404, { detail: { code: "JOB_NOT_FOUND" } });
    });
    server.listen(0, "127.0.0.1", () => {
      const port = (server.address() as AddressInfo).port;
      resolve({
        base: `http://127.0.0.1:${port}`,
        close: () => new Promise((done) => server.close(() => done())),
      });
    });
  });

test("API phase helpers drive submit, lifecycle, events, and result bundle", { timeout: 30_000 }, async () => {
  const stub = await startStubApi();
  try {
    const jobId = await submitJob(stub.base, { participant_id: "rotor-campbell", inputs: {} });
    assert.equal(jobId, "e2e-job-1");
    const final = await pollJobState(stub.base, jobId, { deadlineMs: Date.now() + 10_000, pollMs: 10 });
    assert.equal(final.state, "COMPLETED");
    const events = await fetchEvents(stub.base, jobId);
    assert.equal(events.length, 2);
    assert.deepEqual(events.map((event) => event.sequence), [1, 2]);
    const bundle = await fetchResultBundle(stub.base, jobId);
    assert.equal(bundle.results.payload.source, "native_solver");
    assert.equal(bundle.manifest.payload.result_id, "a".repeat(64));
    assert.equal(bundle.provenance.payload.events.length, 2);
  } finally {
    await stub.close();
  }
});
