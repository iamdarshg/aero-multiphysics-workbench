import assert from "node:assert/strict";
import { createServer } from "node:http";
import type { AddressInfo } from "node:net";
import test from "node:test";

import {
  JOB_TIMEOUT_MS_DEFAULT,
  POLL_MS_DEFAULT,
  READY_TIMEOUT_MS_DEFAULT,
  SMOKE_INPUTS,
  SMOKE_PARTICIPANT,
  TERMINAL_STATES,
  parseArgs,
  resolveConfig,
  runProductJob,
} from "../../scripts/platform/product-smoke.mjs";

test("product smoke targets the tiny deterministic rotor-campbell participant", () => {
  assert.equal(SMOKE_PARTICIPANT, "rotor-campbell");
  assert.deepEqual(Object.keys(SMOKE_INPUTS).sort(), [
    "analysis",
    "bearing_damping_n_s_m",
    "bearing_stiffness_n_m",
    "max_speed_rpm",
    "n_elements",
    "shaft_diameter_m",
    "shaft_length_m",
  ]);
  assert.deepEqual([...TERMINAL_STATES].sort(), ["CANCELLED", "COMPLETED", "FAILED"]);
});

test("product smoke arg parsing has bounded defaults and rejects misuse", () => {
  const defaults = parseArgs([]);
  assert.equal(defaults.port, 8123);
  assert.equal(defaults.participantId, "rotor-campbell");
  assert.equal(defaults.readyTimeoutMs, READY_TIMEOUT_MS_DEFAULT);
  assert.equal(defaults.jobTimeoutMs, JOB_TIMEOUT_MS_DEFAULT);
  assert.equal(defaults.help, false);

  const custom = parseArgs(["--port", "8234", "--participant", "rotor-campbell"]);
  assert.equal(custom.port, 8234);

  assert.throws(() => parseArgs(["--port", "not-a-port"]), /SMOKE_USAGE/);
  assert.throws(() => parseArgs(["--bogus"]), /SMOKE_USAGE/);
  assert.throws(() => parseArgs(["--port"]), /SMOKE_USAGE/);
  assert.deepEqual(parseArgs(["--help"]).help, true);
});

test("product smoke config honors environment overrides", () => {
  const config = resolveConfig({
    argv: [],
    env: { AERO_SMOKE_PORT: "8321", AEROWORKBENCH_JOB_ROOT: "/tmp/smoke-jobs" },
    root: "/repo",
  });
  assert.equal(config.port, 8321);
  assert.equal(config.apiBase, "http://127.0.0.1:8321");
  assert.equal(config.jobRoot, "/tmp/smoke-jobs");
  assert.equal(config.pollMs, POLL_MS_DEFAULT);
});

const startStubApi = (behavior: "happy" | "failed" | "not-ready"): Promise<{ close: () => Promise<void>; base: string }> =>
  new Promise((resolve) => {
    let polls = 0;
    const server = createServer((request, response) => {
      const send = (status: number, payload: unknown): void => {
        response.writeHead(status, { "content-type": "application/json" });
        response.end(JSON.stringify(payload));
      };
      const url = new URL(request.url ?? "/", "http://127.0.0.1");
      if (url.pathname === "/v1/native/participants") {
        send(200, { manifest_version: "2", participants: [{ participant_id: "rotor-campbell" }] });
        return;
      }
      if (url.pathname === "/v1/native/capabilities") {
        send(200, behavior === "not-ready"
          ? { ready: [], unavailable: [{ participant_id: "rotor-campbell" }] }
          : { ready: [{ participant_id: "rotor-campbell" }], unavailable: [] });
        return;
      }
      if (request.method === "POST" && url.pathname === "/v1/native/analyses") {
        send(202, { job_id: "smoke-job-1" });
        return;
      }
      if (url.pathname === "/v1/native/analyses/smoke-job-1") {
        polls += 1;
        send(200, {
          job_id: "smoke-job-1",
          state: behavior === "failed" ? "FAILED" : polls < 2 ? "RUNNING" : "COMPLETED",
          error_code: behavior === "failed" ? "QUALITY_GATE_FAILED" : null,
          error_detail: behavior === "failed" ? "injected" : null,
        });
        return;
      }
      if (url.pathname === "/v1/native/results/smoke-job-1") {
        send(200, { source: "native_solver", fidelity: "beam-campbell" });
        return;
      }
      if (url.pathname === "/v1/native/provenance/smoke-job-1") {
        send(200, { job_id: "smoke-job-1", events: [{ sequence: 1, state: "COMPLETED" }] });
        return;
      }
      send(404, { detail: "stub" });
    });
    server.listen(0, "127.0.0.1", () => {
      const port = (server.address() as AddressInfo).port;
      resolve({
        base: `http://127.0.0.1:${port}`,
        close: () => new Promise((done) => server.close(() => done())),
      });
    });
  });

test("product job flow verifies terminal source metadata over the API path", { timeout: 30_000 }, async () => {
  const stub = await startStubApi("happy");
  try {
    const summary = await runProductJob(stub.base, {
      participantId: "rotor-campbell",
      inputs: { ...SMOKE_INPUTS },
      jobTimeoutMs: 10_000,
      pollMs: 10,
    });
    assert.equal(summary.jobId, "smoke-job-1");
    assert.equal(summary.state, "COMPLETED");
    assert.equal(summary.source, "native_solver");
    assert.equal(summary.fidelity, "beam-campbell");
    assert.equal(summary.provenanceEvents, 1);
  } finally {
    await stub.close();
  }
});

test("product job flow fails closed on FAILED jobs and missing capability", { timeout: 30_000 }, async () => {
  const failed = await startStubApi("failed");
  try {
    await assert.rejects(
      runProductJob(failed.base, { participantId: "rotor-campbell", inputs: {}, jobTimeoutMs: 10_000, pollMs: 10 }),
      /SMOKE_JOB_FAILED/,
    );
  } finally {
    await failed.close();
  }
  const notReady = await startStubApi("not-ready");
  try {
    await assert.rejects(
      runProductJob(notReady.base, { participantId: "rotor-campbell", inputs: {}, jobTimeoutMs: 10_000, pollMs: 10 }),
      /SMOKE_CAPABILITY_NOT_READY/,
    );
  } finally {
    await notReady.close();
  }
});
