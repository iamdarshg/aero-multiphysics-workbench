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

const evidence = (overrides: Partial<NativeResultEvidence> = {}): NativeResultEvidence => ({
  capabilityState: "ready",
  capabilityDetail: "probe ok",
  solverName: "ross",
  solverVersion: "2.3.0",
  inputHash: "a".repeat(64),
  runId: "run-1",
  processState: "completed",
  exitCode: 0,
  executionMode: "subprocess",
  stdoutSha256: "b".repeat(64),
  stderrSha256: "c".repeat(64),
  parserName: "ross.rotor:parse_rotor_result",
  outputFiles: [{ name: "result.json", sha256: "d".repeat(64), bytes: 10 }],
  participantId: "rotor-campbell",
  manifestVersion: "2",
  validityPassed: true,
  fidelity: "beam-campbell",
  scalars: { first_critical_rpm: 2691.0 },
  units: { first_critical_rpm: "rpm" },
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
  const envelope = gateway.recordResult(
    { ...run, runId: "run-1" },
    { artifactUri: "file:///case/result.json", digestSha256: "d".repeat(64) },
    evidence({ runId: "run-1" }),
  );
  assert.equal(envelope.source, "native_solver");
  assert.equal(envelope.fidelity, "beam-campbell");
  assert.equal(envelope.inputHash, "a".repeat(64));
  assert.equal(provenance.list().at(-1)?.type, "result-recorded");
});

test("recordResult fails closed on every evidence gap", async () => {
  const gateway = new SolverGateway({ ross: { available: true, detail: "tested" } }, createInMemoryProvenanceStore());
  const run = await gateway.launch({ solverId: "ross", designId: "rotor-a", launch: { caseDirectory: "case" }, requestedMemoryMiB: 64 });
  const record = { ...run, runId: "run-1" };
  const artifact = { artifactUri: "file:///case/result.json", digestSha256: "d".repeat(64) };
  assert.throws(() => gateway.recordResult(record, artifact), /NATIVE_RESULT_PUBLICATION_UNVERIFIED/);
  assert.throws(() => gateway.recordResult(record, artifact, evidence({ runId: "other" })), /RESULT_INVALID/);
  assert.throws(() => gateway.recordResult(record, artifact, evidence({ validityPassed: false })), /RESULT_INVALID/);
  assert.throws(() => gateway.recordResult(record, artifact, evidence({ inputHash: "xyz" })), /RESULT_INVALID/);
  assert.throws(() => gateway.recordResult(record, artifact, evidence({ stdoutSha256: undefined })), /RESULT_INVALID/);
  assert.throws(
    () => gateway.recordResult(record, artifact, evidence({ participantId: "no-such-participant" })),
    /UNKNOWN_PARTICIPANT/,
  );
});
