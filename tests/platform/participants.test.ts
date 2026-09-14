import assert from "node:assert/strict";
import test from "node:test";

import {
  PARTICIPANT_MANIFESTS,
  SolverGateway,
  createInMemoryProvenanceStore,
  findParticipant,
  participantsForSolver,
} from "../../packages/solver-contracts/src/index.ts";
import type { NativeResultEvidence } from "../../packages/solver-contracts/src/index.ts";

// Synthetic fixtures only: repeated-hex digests stand in for real artifact
// hashes so the validator's structural checks can be exercised without
// claiming any fabricated solver output. Real bounded native benchmarks
// (ROSS/PyBaMM/Gmsh) publish through the Python lifecycle path.
const JOB_ROOT = "C:/work/cases/case-a";

const evidence = (overrides: Partial<NativeResultEvidence> = {}): NativeResultEvidence => ({
  capabilityState: "ready",
  capabilityDetail: "probe ok",
  solverId: "ross",
  solverName: "ross",
  solverVersion: "2.3.0",
  inputHash: "a".repeat(64),
  runId: "run-1",
  processState: "completed",
  exitCode: 0,
  peakRssMiB: 64,
  executionMode: "subprocess",
  stdoutSha256: "b".repeat(64),
  stderrSha256: "c".repeat(64),
  parserName: "ross.rotor:parse_rotor_result",
  parserStatus: "ok",
  jobRoot: JOB_ROOT,
  outputFiles: [
    { name: "case.json", sha256: "e".repeat(64), bytes: 12 },
    { name: "run_ross.py", sha256: "f".repeat(64), bytes: 14 },
    { name: "result.json", sha256: "d".repeat(64), bytes: 10 },
    { name: "solver.log", sha256: "0".repeat(64), bytes: 8 },
  ],
  participantId: "rotor-campbell",
  manifestVersion: "2",
  validityPassed: true,
  fidelity: "beam-campbell",
  scalars: { first_critical_rpm: 2691.0 },
  units: { first_critical_rpm: "rpm" },
  warnings: [],
  ...overrides,
});

const artifact = (overrides: { artifactUri?: string; digestSha256?: string } = {}) => ({
  artifactUri: `file://${JOB_ROOT}/result.json`,
  digestSha256: "d".repeat(64),
  ...overrides,
});

test("participant manifests are distinct from solver manifests", () => {
  const ids = PARTICIPANT_MANIFESTS.map((manifest) => manifest.participantId);
  assert.equal(new Set(ids).size, ids.length);
  assert.ok(ids.length >= 14);
  for (const manifest of PARTICIPANT_MANIFESTS) {
    assert.equal(manifest.manifestVersion, "2");
    assert.ok(manifest.inputs.length > 0);
    assert.ok(manifest.outputs.length > 0);
    assert.ok(manifest.fidelityLevels.length > 0);
    assert.ok(manifest.prepareRef.includes(":"));
    assert.ok(!manifest.participantId.includes("edf"));
  }
});

test("one native executable services several participant types", () => {
  assert.equal(participantsForSolver("openfoam").length, 3);
  assert.equal(participantsForSolver("ross").length, 2);
  assert.equal(participantsForSolver("pybamm").length, 3);
  assert.equal(participantsForSolver("elmer").length, 2);
  assert.throws(() => findParticipant("rm -rf"), /UNKNOWN_PARTICIPANT/);
});

test("recordResult publishes a canonical envelope only with full evidence", async () => {
  const provenance = createInMemoryProvenanceStore();
  const gateway = new SolverGateway({ ross: { available: true, detail: "tested" } }, provenance);
  const run = await gateway.launch({ solverId: "ross", designId: "rotor-a", launch: { caseDirectory: "case" }, requestedMemoryMiB: 64 });
  const before = provenance.list().filter((event) => event.type === "result-recorded").length;
  const envelope = gateway.recordResult(
    { ...run, runId: "run-1" },
    artifact(),
    evidence({ runId: "run-1" }),
  );
  assert.equal(envelope.source, "native_solver");
  assert.equal(envelope.fidelity, "beam-campbell");
  assert.equal(envelope.inputHash, "a".repeat(64));
  assert.equal(envelope.solverIdentity, "ross");
  assert.equal(envelope.solverVersion, "2.3.0");
  assert.equal(envelope.runId, "run-1");
  assert.ok(envelope.provenanceId.length > 0);
  assert.ok("resultId" in envelope && typeof (envelope as { resultId?: unknown }).resultId === "string");
  assert.ok(envelope.artifacts.some((file) => file.name === "result.json" && file.sha256 === "d".repeat(64)));
  const recorded = provenance.list().filter((event) => event.type === "result-recorded");
  assert.equal(recorded.length, before + 1);
  assert.equal(provenance.list().at(-1)?.type, "result-recorded");
});

test("recordResult fails closed on every evidence gap", async () => {
  const gateway = new SolverGateway({ ross: { available: true, detail: "tested" } }, createInMemoryProvenanceStore());
  const run = await gateway.launch({ solverId: "ross", designId: "rotor-a", launch: { caseDirectory: "case" }, requestedMemoryMiB: 64 });
  const record = { ...run, runId: "run-1" };
  assert.throws(() => gateway.recordResult(record, artifact()), /NATIVE_RESULT_PUBLICATION_UNVERIFIED/);
  assert.throws(() => gateway.recordResult(record, artifact(), evidence({ runId: "other" })), /RESULT_INVALID/);
  assert.throws(() => gateway.recordResult(record, artifact(), evidence({ validityPassed: false })), /RESULT_INVALID/);
  assert.throws(() => gateway.recordResult(record, artifact(), evidence({ inputHash: "xyz" })), /RESULT_INVALID/);
  assert.throws(() => gateway.recordResult(record, artifact(), evidence({ stdoutSha256: undefined })), /RESULT_INVALID/);
  assert.throws(
    () => gateway.recordResult(record, artifact(), evidence({ participantId: "no-such-participant" })),
    /UNKNOWN_PARTICIPANT/,
  );
});

test("recordResult rejects a run that was never accepted", async () => {
  const gateway = new SolverGateway({ ross: { available: true, detail: "tested" } }, createInMemoryProvenanceStore());
  const run = await gateway.launch({ solverId: "ross", designId: "rotor-a", launch: { caseDirectory: "case" }, requestedMemoryMiB: 64 });
  assert.throws(
    () => gateway.recordResult({ ...run, runId: "run-1", state: "failed" }, artifact(), evidence({ runId: "run-1" })),
    /RESULT_INVALID:run not accepted/,
  );
});

test("recordResult rejects publication while the capability is unverified", async () => {
  const gateway = new SolverGateway({ ross: { available: false, detail: "missing" } }, createInMemoryProvenanceStore());
  const healthy = new SolverGateway({ ross: { available: true, detail: "tested" } }, createInMemoryProvenanceStore());
  const run = await healthy.launch({ solverId: "ross", designId: "rotor-a", launch: { caseDirectory: "case" }, requestedMemoryMiB: 64 });
  const record = { ...run, runId: "run-1" };
  assert.throws(() => gateway.recordResult(record, artifact(), evidence({ runId: "run-1" })), /CAPABILITY_UNAVAILABLE/);
  assert.throws(
    () => healthy.recordResult(record, artifact(), evidence({ runId: "run-1", capabilityState: "unavailable" })),
    /RESULT_INVALID:capability not verified/,
  );
});

test("recordResult rejects a missing expected artifact", async () => {
  const gateway = new SolverGateway({ ross: { available: true, detail: "tested" } }, createInMemoryProvenanceStore());
  const run = await gateway.launch({ solverId: "ross", designId: "rotor-a", launch: { caseDirectory: "case" }, requestedMemoryMiB: 64 });
  const record = { ...run, runId: "run-1" };
  const withoutResult = evidence({ runId: "run-1" }).outputFiles.filter((file) => file.name !== "result.json");
  assert.throws(
    () => gateway.recordResult(record, artifact(), evidence({ runId: "run-1", outputFiles: withoutResult })),
    /RESULT_INVALID:missing expected artifact/,
  );
});

test("recordResult rejects a failed parser", async () => {
  const gateway = new SolverGateway({ ross: { available: true, detail: "tested" } }, createInMemoryProvenanceStore());
  const run = await gateway.launch({ solverId: "ross", designId: "rotor-a", launch: { caseDirectory: "case" }, requestedMemoryMiB: 64 });
  const record = { ...run, runId: "run-1" };
  assert.throws(
    () => gateway.recordResult(record, artifact(), evidence({ runId: "run-1", parserStatus: "failed" })),
    /RESULT_INVALID:parser failed/,
  );
  assert.throws(
    () => gateway.recordResult(record, artifact(), evidence({ runId: "run-1", parserName: "" })),
    /RESULT_INVALID:parser missing/,
  );
});

test("recordResult rejects a nonzero exit", async () => {
  const gateway = new SolverGateway({ ross: { available: true, detail: "tested" } }, createInMemoryProvenanceStore());
  const run = await gateway.launch({ solverId: "ross", designId: "rotor-a", launch: { caseDirectory: "case" }, requestedMemoryMiB: 64 });
  const record = { ...run, runId: "run-1" };
  assert.throws(
    () => gateway.recordResult(record, artifact(), evidence({ runId: "run-1", exitCode: 1 })),
    /PROCESS_EXIT_NONZERO/,
  );
});

test("recordResult rejects timeout and cancellation", async () => {
  const gateway = new SolverGateway({ ross: { available: true, detail: "tested" } }, createInMemoryProvenanceStore());
  const run = await gateway.launch({ solverId: "ross", designId: "rotor-a", launch: { caseDirectory: "case" }, requestedMemoryMiB: 64 });
  const record = { ...run, runId: "run-1" };
  assert.throws(
    () => gateway.recordResult(record, artifact(), evidence({ runId: "run-1", processState: "timeout" })),
    /PROCESS_TIMEOUT/,
  );
  assert.throws(
    () => gateway.recordResult(record, artifact(), evidence({ runId: "run-1", processState: "cancelled" })),
    /PROCESS_CANCELLED/,
  );
});

test("recordResult rejects a digest mismatch", async () => {
  const gateway = new SolverGateway({ ross: { available: true, detail: "tested" } }, createInMemoryProvenanceStore());
  const run = await gateway.launch({ solverId: "ross", designId: "rotor-a", launch: { caseDirectory: "case" }, requestedMemoryMiB: 64 });
  const record = { ...run, runId: "run-1" };
  assert.throws(
    () => gateway.recordResult(record, artifact({ digestSha256: "9".repeat(64) }), evidence({ runId: "run-1" })),
    /RESULT_INVALID:artifact digest mismatch/,
  );
  assert.throws(
    () => gateway.recordResult(record, artifact({ digestSha256: "xyz" }), evidence({ runId: "run-1" })),
    /RESULT_INVALID:artifact digest must be SHA-256/,
  );
});

test("recordResult rejects an artifact outside the job root", async () => {
  const gateway = new SolverGateway({ ross: { available: true, detail: "tested" } }, createInMemoryProvenanceStore());
  const run = await gateway.launch({ solverId: "ross", designId: "rotor-a", launch: { caseDirectory: "case" }, requestedMemoryMiB: 64 });
  const record = { ...run, runId: "run-1" };
  assert.throws(
    () => gateway.recordResult(
      record,
      artifact(),
      evidence({
        runId: "run-1",
        outputFiles: [{ name: "../outside.json", sha256: "d".repeat(64), bytes: 10 }],
      }),
    ),
    /RESULT_INVALID:artifact escapes job directory/,
  );
  assert.throws(
    () => gateway.recordResult(
      record,
      artifact({ artifactUri: `file://${JOB_ROOT}/../outside/result.json` }),
      evidence({ runId: "run-1" }),
    ),
    /RESULT_INVALID:artifact escapes job directory/,
  );
});

test("recordResult rejects a solver identity mismatch", async () => {
  const gateway = new SolverGateway(
    { ross: { available: true, detail: "tested" }, pybamm: { available: true, detail: "tested" } },
    createInMemoryProvenanceStore(),
  );
  const run = await gateway.launch({ solverId: "ross", designId: "rotor-a", launch: { caseDirectory: "case" }, requestedMemoryMiB: 64 });
  const record = { ...run, runId: "run-1" };
  assert.throws(
    () => gateway.recordResult(record, artifact(), evidence({ runId: "run-1", solverId: "pybamm", solverName: "pybamm" })),
    /RESULT_INVALID:solver identity mismatch/,
  );
  assert.throws(
    () => gateway.recordResult(record, artifact(), evidence({ runId: "run-1", solverVersion: "" })),
    /RESULT_INVALID:missing solver identity/,
  );
});

test("failed publication appends no provenance event", async () => {
  const provenance = createInMemoryProvenanceStore();
  const gateway = new SolverGateway({ ross: { available: true, detail: "tested" } }, provenance);
  const run = await gateway.launch({ solverId: "ross", designId: "rotor-a", launch: { caseDirectory: "case" }, requestedMemoryMiB: 64 });
  const record = { ...run, runId: "run-1" };
  const before = provenance.list().length;
  assert.throws(
    () => gateway.recordResult(record, artifact(), evidence({ runId: "run-1", parserStatus: "failed" })),
    /RESULT_INVALID/,
  );
  assert.equal(provenance.list().length, before);
});
