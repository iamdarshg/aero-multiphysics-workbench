import assert from "node:assert/strict";
import test from "node:test";

import {
  CAPABILITY_MANIFESTS,
  CapabilityDetector,
  commandProbe,
  LocalScheduler,
  McpEngineeringServer,
  SolverGateway,
  createInMemoryProvenanceStore,
} from "../../packages/solver-contracts/src/index.ts";

test("the manifest registry describes every requested solver and geometry adapter", () => {
  assert.deepEqual(
    CAPABILITY_MANIFESTS.map((manifest) => manifest.id),
    [
      "openfoam", "code-aster", "precice", "ross", "pybamm", "elmer",
      "cantera", "pycycle", "cadquery", "gmsh", "openvsp", "freecad",
    ],
  );
  for (const manifest of CAPABILITY_MANIFESTS) {
    assert.ok(manifest.versionProbe.command.length > 0);
    assert.ok(manifest.resultKinds.length > 0);
    assert.equal(manifest.execution.trustModel, "native-only");
  }
});

test("capability detection reports unavailable native tools without pretending they work", async () => {
  const detector = new CapabilityDetector(async () => ({ available: false, detail: "not installed" }));
  const report = await detector.detect(CAPABILITY_MANIFESTS);
  assert.equal(report.ready.length, 0);
  assert.equal(report.unavailable.length, CAPABILITY_MANIFESTS.length);
  assert.match(report.unavailable[0].detail, /not installed/);
});

test("command probe has a bounded no-shell execution path and records a version", async () => {
  const result = await commandProbe({
    id: "ross", displayName: "probe", category: "solver",
    versionProbe: { command: [process.execPath, "--version"] }, resultKinds: ["report"],
    execution: { trustModel: "native-only", checkpoint: true },
  });
  assert.equal(result.available, true);
  assert.match(result.version ?? "", /^v\d+/);
});

test("a launch is fail-closed until its declared native capability is ready", async () => {
  const gateway = new SolverGateway({ openfoam: { available: false, detail: "missing" } }, createInMemoryProvenanceStore());
  await assert.rejects(
    gateway.launch({ solverId: "openfoam", designId: "fan-a", command: ["simpleFoam"], requestedMemoryMiB: 64 }),
    /CAPABILITY_UNAVAILABLE/,
  );
});

test("a native result cannot be published without an accepted run and provenance", async () => {
  const provenance = createInMemoryProvenanceStore();
  const gateway = new SolverGateway({ openfoam: { available: true, detail: "tested native command" } }, provenance);
  const run = await gateway.launch({ solverId: "openfoam", designId: "fan-a", command: ["simpleFoam"], requestedMemoryMiB: 64, checkpointFrom: "checkpoint-7" });
  const result = gateway.recordResult(run, { artifactUri: "file:///case/result.vtk", digestSha256: "abc123" });
  assert.equal(result.source, "native-solver");
  assert.equal(result.checkpointFrom, "checkpoint-7");
  assert.equal(provenance.list().at(-1)?.type, "result-recorded");
});

test("scheduler enforces aggregate one-gibibyte reservations and refuses remote jobs by default", async () => {
  const scheduler = new LocalScheduler();
  scheduler.submit({ id: "one", requestedMemoryMiB: 700, remote: false, costCeilingUsd: 0 });
  assert.throws(
    () => scheduler.submit({ id: "two", requestedMemoryMiB: 400, remote: false, costCeilingUsd: 0 }),
    /RSS_BUDGET_EXCEEDED/,
  );
  assert.throws(
    () => scheduler.submit({ id: "remote", requestedMemoryMiB: 64, remote: true, costCeilingUsd: 1 }),
    /REMOTE_COMPUTE_NOT_AUTHORIZED/,
  );
});

test("scheduler accepts remote work only with explicit authorization and a non-negative user cost ceiling", () => {
  const scheduler = new LocalScheduler({ remoteComputeAuthorized: true, remainingRemoteBudgetUsd: 3 });
  const job = scheduler.submit({ id: "remote", requestedMemoryMiB: 64, remote: true, costCeilingUsd: 2 });
  assert.equal(job.state, "queued");
  assert.throws(
    () => scheduler.submit({ id: "over-budget", requestedMemoryMiB: 64, remote: true, costCeilingUsd: 2 }),
    /REMOTE_COST_BUDGET_EXCEEDED/,
  );
});

test("MCP operations gate destructive mutations and remote compute independently", async () => {
  const server = new McpEngineeringServer(new LocalScheduler());
  await assert.rejects(
    server.call("design.delete", { designId: "fan-a" }),
    /DESTRUCTIVE_OPERATION_NOT_AUTHORIZED/,
  );
  await assert.rejects(
    server.call("simulation.launch", { id: "run-a", requestedMemoryMiB: 64, remote: true, costCeilingUsd: 1 }),
    /REMOTE_COMPUTE_NOT_AUTHORIZED/,
  );
  const dryRun = await server.call("simulation.launch", { id: "run-local", requestedMemoryMiB: 64, remote: false, costCeilingUsd: 0 });
  assert.equal(dryRun.state, "queued");
});
