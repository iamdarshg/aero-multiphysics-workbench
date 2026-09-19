// PERF 04: Node edge hot-path contracts.
//
// Evidence-only unit tests for the new hot-path mechanisms: the native
// capability/version probe cache (manifest/env/executable invalidation) and the
// MCP read cache/single-flight for slow-moving discovery endpoints. No solver
// is launched, no network leaves loopback, and every probe is an injected fake.
import assert from "node:assert/strict";
import { createServer, type Server } from "node:http";
import test from "node:test";

import {
  CAPABILITY_MANIFESTS,
  CapabilityProbeCache,
  describeManifest,
} from "../../packages/solver-contracts/src/index.ts";
import type { SolverManifest } from "../../packages/solver-contracts/src/index.ts";
import { HttpEngineeringApi } from "../../mcp/engineering/api-client.ts";
import { EngineeringOperations } from "../../mcp/engineering/operations.ts";
import type { EngineeringPolicy } from "../../mcp/engineering/policy.ts";

const MANIFEST = CAPABILITY_MANIFESTS[0] as SolverManifest;

const countingProbe = (counter: { probes: number }) => async () => {
  counter.probes += 1;
  return { available: true, detail: "probe ok", version: "1.0.0" };
};

const closeServer = (server: Server): Promise<void> => new Promise((resolve) => server.close(() => resolve()));

const listen = (server: Server, handler: (request: import("node:http").IncomingMessage, response: import("node:http").ServerResponse) => void): Promise<string> =>
  new Promise((resolve) => {
    server.on("request", handler);
    server.listen(0, "127.0.0.1", () => {
      const address = server.address();
      const port = typeof address === "object" && address ? address.port : 0;
      resolve(`http://127.0.0.1:${port}`);
    });
  });

test("a repeated capability query performs exactly one probe", async () => {
  const counter = { probes: 0 };
  const cache = new CapabilityProbeCache({
    probe: countingProbe(counter),
    environment: {},
    executableIdentity: () => "stable-binary",
  });
  const first = await cache.capability(MANIFEST);
  const second = await cache.capability(MANIFEST);
  assert.equal(counter.probes, 1, "a warm query must not spawn a second probe");
  assert.equal(first.version, "1.0.0");
  assert.equal(second.version, "1.0.0");
  assert.deepEqual(cache.stats(), { hits: 1, misses: 1, probes: 1, invalidations: 0, entries: 1 });
});

test("concurrent detection is single-flighted and order-stable", async () => {
  const counter = { probes: 0 };
  const cache = new CapabilityProbeCache({
    probe: async () => { counter.probes += 1; await new Promise((resolve) => setTimeout(resolve, 5)); return { available: true, detail: "ok" }; },
    environment: {},
    executableIdentity: () => "stable-binary",
  });
  const [first, second] = await Promise.all([
    cache.detect(CAPABILITY_MANIFESTS),
    cache.detect(CAPABILITY_MANIFESTS),
  ]);
  assert.equal(counter.probes, CAPABILITY_MANIFESTS.length, "each manifest must be probed exactly once");
  assert.deepEqual(first.ready.map((entry) => entry.id), CAPABILITY_MANIFESTS.map((manifest) => manifest.id));
  assert.deepEqual(second.unavailable, []);
});

test("a manifest edit invalidates a cached probe without a process spawn", async () => {
  const counter = { probes: 0 };
  const cache = new CapabilityProbeCache({
    probe: countingProbe(counter),
    environment: {},
    executableIdentity: () => "stable-binary",
  });
  await cache.capability(MANIFEST);
  const edited: SolverManifest = { ...MANIFEST, allowedExecutables: ["a-different-binary"] };
  await cache.capability(edited);
  assert.equal(counter.probes, 2);
});

test("an environment change invalidates a cached probe", async () => {
  const counter = { probes: 0 };
  const environment: Record<string, string | undefined> = { PATH: "/bin/one" };
  const cache = new CapabilityProbeCache({ probe: countingProbe(counter), environment, executableIdentity: () => "stable" });
  await cache.capability(MANIFEST);
  environment.PATH = "/bin/two";
  await cache.capability(MANIFEST);
  assert.equal(counter.probes, 2);
});

test("an in-place executable change invalidates a cached probe", async () => {
  const counter = { probes: 0 };
  let identity = "solver|100|1000";
  const cache = new CapabilityProbeCache({
    probe: countingProbe(counter),
    environment: {},
    executableIdentity: () => identity,
    executableTtlMs: 0,
  });
  await cache.capability(MANIFEST);
  identity = "solver|200|2000";
  await cache.capability(MANIFEST);
  assert.equal(counter.probes, 2);
});

test("ttl expiry and explicit invalidation both re-probe", async () => {
  const counter = { probes: 0 };
  let clock = 0;
  const cache = new CapabilityProbeCache({
    probe: countingProbe(counter),
    environment: {},
    executableIdentity: () => "stable",
    executableTtlMs: 0,
    ttlMs: 1_000,
    now: () => clock,
  });
  await cache.capability(MANIFEST);
  clock = 500;
  await cache.capability(MANIFEST);
  assert.equal(counter.probes, 1, "within TTL the entry stays warm");
  clock = 1_001;
  await cache.capability(MANIFEST);
  assert.equal(counter.probes, 2, "past TTL the entry is refreshed");
  cache.invalidate(MANIFEST.id);
  await cache.capability(MANIFEST);
  assert.equal(counter.probes, 3, "explicit invalidation refreshes immediately");
});

test("manifest fingerprint is stable and field-sensitive", () => {
  assert.equal(describeManifest(MANIFEST), describeManifest(MANIFEST));
  assert.notEqual(describeManifest(MANIFEST), describeManifest({ ...MANIFEST, allowedExecutables: ["other"] }));
  assert.notEqual(describeManifest(MANIFEST), describeManifest({ ...MANIFEST, category: "geometry" }));
});

test("MCP read cache removes repeated discovery round-trips and dedupes in-flight reads", async () => {
  let participantRequests = 0;
  let capabilityRequests = 0;
  const server = createServer();
  const baseUrl = await listen(server, (request, response) => {
    const url = new URL(request.url ?? "/", "http://127.0.0.1");
    response.writeHead(200, { "content-type": "application/json" });
    if (url.pathname === "/v1/native/participants") {
      participantRequests += 1;
      response.end(JSON.stringify({ participants: [{ participant_id: "rotor-campbell", fidelity_levels: ["beam"] }] }));
      return;
    }
    if (url.pathname === "/v1/native/capabilities") {
      capabilityRequests += 1;
      response.end(JSON.stringify({ ready: [], unavailable: [] }));
      return;
    }
    response.end(JSON.stringify({}));
  });
  const api = new HttpEngineeringApi(baseUrl, { readCacheTtlMs: 60_000, now: () => 0 });
  try {
    const [first, second] = await Promise.all([api.participants(), api.participants()]);
    assert.deepEqual(first, second);
    await api.participants();
    assert.equal(participantRequests, 1, "two concurrent + one sequential read must share one request");
    await api.capabilities();
    await api.capabilities();
    assert.equal(capabilityRequests, 1);
    assert.equal(api.cacheStats().hits, 2, "one sequential participants hit + one cached capabilities hit");
    api.invalidate();
    await api.participants();
    assert.equal(participantRequests, 2, "invalidation forces the next read to refetch");
    assert.equal(api.cacheStats().invalidations, 1);
  } finally {
    await closeServer(server);
  }
});

test("a failed discovery read is never cached", async () => {
  let requests = 0;
  const server = createServer();
  const baseUrl = await listen(server, (request, response) => {
    requests += 1;
    if (requests === 1) {
      response.writeHead(503, { "content-type": "application/json" });
      response.end(JSON.stringify({ detail: "temporarily unavailable" }));
      return;
    }
    response.writeHead(200, { "content-type": "application/json" });
    response.end(JSON.stringify({ participants: [{ participant_id: "rotor-campbell", fidelity_levels: ["beam"] }] }));
  });
  const api = new HttpEngineeringApi(baseUrl, { readCacheTtlMs: 60_000, now: () => 0 });
  try {
    await assert.rejects(api.participants(), /API_REQUEST_FAILED|temporarily unavailable/);
    const value = await api.participants();
    assert.equal(value.length, 1);
    assert.equal(requests, 2, "an error must not populate the cache");
  } finally {
    await closeServer(server);
  }
});

test("result.inspect forwards bounded artifact refs and scalars, never unbounded arrays", async () => {
  const bigArtifacts = Array.from({ length: 1_000 }, (_, index) => ({ name: `field-${index}.vtk`, sha256: "a".repeat(64), bytes: index + 1 }));
  const bigScalars = Object.fromEntries(Array.from({ length: 1_000 }, (_, index) => [`s${index}`, index]));
  const unused = async () => ({});
  const fakeApi = {
    capabilities: unused,
    participants: async () => [{ participantId: "rotor-campbell", fidelityLevels: ["beam"] }],
    submitAnalysis: unused,
    jobStatus: unused,
    cancelJob: unused,
    jobResult: async () => ({ source: "native_solver", solver_identity: "ross", solver_version: "2.3.0", run_id: "run-1", provenance_id: "prov-1", input_hash: "b".repeat(64), validity: { passed: true, detail: "ok" }, warnings: ["w"], scalars: bigScalars, units: { s0: "rpm" }, artifacts: bigArtifacts }),
    jobResultManifest: async () => ({ job_id: "job-1", solver_identity: "ross", solver_version: "2.3.0", artifacts: bigArtifacts }),
    jobProvenance: async () => ({ job_id: "job-1", events: Array.from({ length: 1_000 }, (_, index) => ({ id: `e${index}`, at: "2026-01-01T00:00:00Z", type: "result-recorded", detail: "d" })) }),
  };
  const policy: EngineeringPolicy = {
    ownerId: "test-owner",
    mutations: false,
    destructive: false,
    remoteCompute: false,
    remoteCostCeilingUsd: 0,
    apiBaseUrl: "http://127.0.0.1:9",
  };
  const operations = new EngineeringOperations(fakeApi, policy);
  const response = await operations.call("result.inspect", { jobId: "job-1" });
  const result = response.result as { artifacts: readonly unknown[]; scalars: Record<string, number>; solverIdentity: string };
  const manifest = response.manifest as { artifacts: readonly unknown[]; solverIdentity: string };
  const provenance = response.provenance as { events: readonly unknown[] };
  assert.equal(result.solverIdentity, "ross");
  assert.equal(manifest.solverIdentity, "ross");
  assert.ok(result.artifacts.length <= 256);
  assert.ok(Object.keys(result.scalars).length <= 256);
  assert.ok(manifest.artifacts.length <= 256);
  assert.ok(provenance.events.length <= 200);
});
