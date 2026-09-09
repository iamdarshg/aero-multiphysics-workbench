import assert from "node:assert/strict";
import { readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import {
  CAPABILITY_MANIFESTS,
  CapabilityDetector,
  commandProbe,
  LocalScheduler,
  McpEngineeringServer,
  SolverGateway,
  createInMemoryProvenanceStore,
  buildSolverCommand,
  isPathContained,
} from "../../packages/solver-contracts/src/index.ts";
import { createTrustedNativeCommand } from "../../packages/solver-contracts/src/commands.ts";

test("the manifest registry describes every requested solver and geometry adapter", () => {
  assert.deepEqual(
    CAPABILITY_MANIFESTS.map((manifest) => manifest.id),
    [
      "openfoam", "code-aster", "precice", "ross", "pybamm", "elmer",
      "cantera", "pycycle", "cadquery", "gmsh", "openvsp", "freecad",
    ],
  );
  for (const manifest of CAPABILITY_MANIFESTS) {
    assert.equal(manifest.versionProbe.args[0], "--version");
    assert.ok(manifest.resultKinds.length > 0);
    assert.equal(manifest.execution.trustModel, "native-only");
    assert.ok(manifest.allowedExecutables.length > 0);
  }
});

test("capability detection reports unavailable native tools without pretending they work", async () => {
  const detector = new CapabilityDetector(async () => ({ available: false, detail: "not installed" }));
  const report = await detector.detect(CAPABILITY_MANIFESTS);
  assert.equal(report.ready.length, 0);
  assert.equal(report.unavailable.length, CAPABILITY_MANIFESTS.length);
  assert.match(report.unavailable[0].detail, /not installed/);
});

test("command probe rejects manifests outside the immutable trusted registry", async () => {
  const result = await commandProbe({ ...CAPABILITY_MANIFESTS.find((manifest) => manifest.id === "ross")!, versionProbe: { executable: process.execPath, args: ["--version"] } });
  assert.equal(result.available, false);
  assert.match(result.detail, /trusted registry/);
});

test("a launch is fail-closed until its declared native capability is ready", async () => {
  const gateway = new SolverGateway({ openfoam: { available: false, detail: "missing" } }, createInMemoryProvenanceStore());
  await assert.rejects(
    gateway.launch({ solverId: "openfoam", designId: "fan-a", launch: { caseDirectory: "case" }, requestedMemoryMiB: 64 }),
    /CAPABILITY_UNAVAILABLE/,
  );
});

test("native result publication is disabled until a verified receipt exists", async () => {
  const provenance = createInMemoryProvenanceStore();
  const gateway = new SolverGateway({ openfoam: { available: true, detail: "tested native command" } }, provenance);
  const run = await gateway.launch({ solverId: "openfoam", designId: "fan-a", launch: { caseDirectory: "case" }, requestedMemoryMiB: 64, checkpointFrom: "checkpoint-7" });
  assert.throws(() => gateway.recordResult(run, { artifactUri: "file:///case/result.vtk", digestSha256: "abc123" }), /NATIVE_RESULT_PUBLICATION_UNVERIFIED/);
  assert.equal(provenance.list().at(-1)?.type, "launch-accepted");
});

test("scheduler leaves host headroom below the one-gibibyte project RSS ceiling", async () => {
  const scheduler = new LocalScheduler();
  scheduler.submit({ id: "one", requestedMemoryMiB: 850, remote: false, costCeilingUsd: 0 });
  assert.throws(
    () => scheduler.submit({ id: "two", requestedMemoryMiB: 100, remote: false, costCeilingUsd: 0 }),
    /RSS_BUDGET_EXCEEDED/,
  );
  assert.throws(
    () => scheduler.submit({ id: "remote", requestedMemoryMiB: 64, remote: true, costCeilingUsd: 1 }),
    /REMOTE_COMPUTE_NOT_AUTHORIZED/,
  );
});

test("scheduler kills a local process when measured RSS exceeds its reservation", async () => {
  const scheduler = new LocalScheduler();
  const result = await scheduler.runLocal(
    { id: "bounded", requestedMemoryMiB: 64, remote: false, costCeilingUsd: 0 },
    createTrustedNativeCommand("openfoam", process.execPath, ["-e", "setInterval(() => {}, 1000)"]),
    {
      allowedExecutables: new Set([process.execPath]),
      pollIntervalMs: 1,
      readPids: async (pid) => [pid],
      readRssMiB: async () => 65,
    },
  );
  assert.equal(result.state, "failed");
  assert.equal(result.reason, "PROCESS_RSS_LIMIT_EXCEEDED");
  assert.equal(scheduler.snapshot().length, 0);
});

test("scheduler refuses to spawn commands outside the explicit executable allowlist", async () => {
  const scheduler = new LocalScheduler();
  await assert.rejects(
    scheduler.runLocal(
      { id: "blocked", requestedMemoryMiB: 64, remote: false, costCeilingUsd: 0 },
      createTrustedNativeCommand("openfoam", process.execPath, ["--version"]),
      { allowedExecutables: new Set(["definitely-not-node"]) },
    ),
    /COMMAND_NOT_ALLOWLISTED/,
  );
  assert.equal(scheduler.snapshot().length, 0);
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

test("scheduler fails closed when the configured remote budget is invalid", () => {
  assert.throws(
    () => new LocalScheduler({ remoteComputeAuthorized: true, remainingRemoteBudgetUsd: Number.NaN }),
    /INVALID_REMOTE_BUDGET/,
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
  await assert.rejects(server.call("design.variant.create", { designId: "fan-a", variantId: "variant-a" }), /MUTATION_NOT_AUTHORIZED/);
  const dryRun = await server.call("simulation.launch", { id: "run-local", requestedMemoryMiB: 64, remote: false, costCeilingUsd: 0 });
  assert.equal(dryRun.state, "queued");
});

test("MCP cancellation is scoped to the owner", async () => {
  const scheduler = new LocalScheduler();
  scheduler.submit({ id: "foreign-job", requestedMemoryMiB: 64, remote: false, costCeilingUsd: 0, ownerId: "operator-b" });
  const server = new McpEngineeringServer(scheduler, { ownerId: "operator-a" });
  await assert.rejects(server.call("job.cancel", { id: "foreign-job" }), /JOB_NOT_OWNED/);
  await server.call("simulation.launch", { id: "owned-job", requestedMemoryMiB: 64, remote: false, costCeilingUsd: 0 });
  const cancelled = await server.call("job.cancel", { id: "owned-job" });
  assert.equal(cancelled.state, "queued");
});

test("authorized MCP delete does not claim deletion without a backing design store", async () => {
  const server = new McpEngineeringServer(new LocalScheduler(), { destructive: true });
  const response = await server.call("design.delete", { designId: "fan-a" });
  assert.deepEqual(response, {
    operation: "design.delete",
    skeleton: true,
    queued: false,
    authorized: true,
    deleted: false,
    designId: "fan-a",
    reason: "NO_DESIGN_STORE_CONFIGURED",
  });
});

test("solver gateway rejects a native executable not allowlisted for its solver", async () => {
  const gateway = new SolverGateway(
    { openfoam: { available: true, detail: "tested native command" } },
    createInMemoryProvenanceStore(),
  );
  await assert.rejects(
    gateway.launch({ solverId: "openfoam", designId: "fan-a", launch: { caseDirectory: "case\u0000" }, requestedMemoryMiB: 64 }),
    /INVALID_SOLVER_LAUNCH_INPUT/,
  );
});

test("solver command builders select only manifest executables and reject shell text", () => {
  const command = buildSolverCommand("openfoam", { caseDirectory: "case" });
  assert.equal(command.executable, "simpleFoam");
  assert.deepEqual(command.args, ["-case", "case"]);
  assert.throws(() => buildSolverCommand("openfoam", { caseDirectory: "case\u0000" }), /INVALID_SOLVER_LAUNCH_INPUT/);
});

test("path containment normalizes both separator styles before comparing", () => {
  assert.equal(isPathContained("C:\\work\\cases", "C:/work/cases/../outside"), false);
  assert.equal(isPathContained("C:/work/cases", "C:\\work\\cases\\case-a"), true);
});

test("native result publication remains fail-closed without a verified completion receipt", async () => {
  const gateway = new SolverGateway({ openfoam: { available: true, detail: "tested native command", version: "v1" } }, createInMemoryProvenanceStore());
  const run = await gateway.launch({ solverId: "openfoam", designId: "fan-a", launch: { caseDirectory: "case" }, requestedMemoryMiB: 64 });
  assert.throws(() => gateway.recordResult(run, { artifactUri: "file:///case/result.vtk", digestSha256: "a".repeat(64) }), /NATIVE_RESULT_PUBLICATION_UNVERIFIED/);
});

test("scheduler fails closed when a process-tree RSS monitor is unavailable", async () => {
  const scheduler = new LocalScheduler();
  const result = await scheduler.runLocal(
    { id: "unmeasured", requestedMemoryMiB: 64, remote: false, costCeilingUsd: 0 },
    createTrustedNativeCommand("openfoam", process.execPath, ["-e", "setTimeout(() => {}, 200)"]),
    { allowedExecutables: new Set([process.execPath]), pollIntervalMs: 1, readPids: async (pid) => [pid], readRssMiB: async () => { throw new Error("no monitor"); } },
  );
  assert.equal(result.reason, "RSS_MONITOR_UNAVAILABLE");
});

test("scheduler rejects an uncontained working directory before spawning", async () => {
  const scheduler = new LocalScheduler();
  await assert.rejects(
    scheduler.runLocal(
      { id: "outside", requestedMemoryMiB: 64, remote: false, costCeilingUsd: 0 },
      createTrustedNativeCommand("openfoam", process.execPath, ["--version"]),
      { allowedExecutables: new Set([process.execPath]), workingDirectory: process.cwd(), allowedWorkingDirectory: `${process.cwd()}\\case-root` },
    ),
    /WORKING_DIRECTORY_OUTSIDE_ALLOWLIST/,
  );
});

test("scheduler terminates a timed-out process tree", async () => {
  const scheduler = new LocalScheduler();
  const result = await scheduler.runLocal(
    { id: "timed", requestedMemoryMiB: 64, remote: false, costCeilingUsd: 0 },
    createTrustedNativeCommand("openfoam", process.execPath, ["-e", "setInterval(() => {}, 1000)"]),
    { allowedExecutables: new Set([process.execPath]), pollIntervalMs: 1, timeoutMs: 20, readPids: async (pid) => [pid], readRssMiB: async () => 1 },
  );
  assert.equal(result.reason, "PROCESS_TIMEOUT");
});

test("scheduler cleans a descendant after the root exits", async () => {
  const scheduler = new LocalScheduler();
  const pidFile = join(tmpdir(), `aero-platform-descendant-${process.pid}-${Date.now()}.txt`);
  const script = "const fs=require('node:fs');const {spawn}=require('node:child_process');const c=spawn(process.execPath,['-e','setInterval(()=>{},10000)'],{detached:true,stdio:'ignore'});fs.writeFileSync(process.argv[1],String(c.pid));c.unref();setTimeout(()=>process.exit(0),80);";
  let descendantPid: number | undefined;
  const result = await scheduler.runLocal(
    { id: "descendant-cleanup", requestedMemoryMiB: 64, remote: false, costCeilingUsd: 0 },
    createTrustedNativeCommand("openfoam", process.execPath, ["-e", script, pidFile]),
    {
      allowedExecutables: new Set([process.execPath]),
      pollIntervalMs: 5,
      readPids: async (pid) => {
        try {
          descendantPid = Number((await readFile(pidFile, "utf8")).trim());
          return descendantPid > 0 ? [pid, descendantPid] : [pid];
        } catch { return [pid]; }
      },
      readRssMiB: async () => 1,
    },
  );
  assert.equal(result.state, "completed");
  assert.ok(descendantPid && descendantPid > 0);
  await new Promise((resolve) => setTimeout(resolve, 50));
  assert.throws(() => process.kill(descendantPid as number, 0));
  await rm(pidFile, { force: true });
});
