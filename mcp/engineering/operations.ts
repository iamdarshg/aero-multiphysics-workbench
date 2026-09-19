/**
 * Policy-gated product operations for the engineering MCP server.
 *
 * Every operation calls the public product API through {@link EngineeringApi}
 * — the same paths a human or the workbench UI uses. This module never
 * imports scheduler internals and never invokes solver adapters directly.
 */

import type { EngineeringApi } from "./api-client.ts";
import {
  type EngineeringPolicy,
  assertOwnedJobStatus,
  assertSafeToken,
  isSafeInputValue,
  isSafeToken,
  rejectCostEscalation,
  rejectRemoteEscalation,
} from "./policy.ts";

export const TOOL_NAMES = [
  "capabilities.inspect",
  "design.inspect",
  "job.inspect",
  "result.inspect",
  "design.variant.create",
  "analysis.submit",
  "job.cancel",
] as const;

export type EngineeringToolName = (typeof TOOL_NAMES)[number];

export const isToolName = (value: unknown): value is EngineeringToolName =>
  typeof value === "string" && (TOOL_NAMES as readonly string[]).includes(value);

const asString = (value: unknown): string | null => (typeof value === "string" ? value : null);

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

// Thin-edge bounds: MCP passes compact identity/status/artifact refs, never an
// unbounded engineering payload. The Python engine stays the owner of the
// scientific arrays; the edge caps what it forwards over the protocol.
const MAX_RESULT_ARTIFACTS = 256;
const MAX_RESULT_SCALARS = 256;
const MAX_PROVENANCE_EVENTS = 200;
const MAX_WARNINGS = 64;

const asArray = (value: unknown): readonly unknown[] => (Array.isArray(value) ? value : []);

const compactNumberMap = (value: unknown): Record<string, number> => {
  if (!isRecord(value)) return {};
  const bounded: Record<string, number> = {};
  let count = 0;
  for (const [key, entry] of Object.entries(value)) {
    if (count >= MAX_RESULT_SCALARS) break;
    if (typeof entry === "number" && Number.isFinite(entry)) { bounded[key] = entry; count += 1; }
  }
  return bounded;
};

const compactStringMap = (value: unknown): Record<string, string> => {
  if (!isRecord(value)) return {};
  const bounded: Record<string, string> = {};
  let count = 0;
  for (const [key, entry] of Object.entries(value)) {
    if (count >= MAX_RESULT_SCALARS) break;
    if (typeof entry === "string") { bounded[key] = entry; count += 1; }
  }
  return bounded;
};

/** Artifact references only (name/digest/bytes) — never artifact contents. */
const compactArtifactRefs = (value: unknown): readonly Record<string, unknown>[] =>
  asArray(value)
    .slice(0, MAX_RESULT_ARTIFACTS)
    .filter(isRecord)
    .map((entry) => ({
      name: asString(entry.name) ?? asString(entry.file),
      sha256: asString(entry.sha256),
      bytes: typeof entry.bytes === "number" && Number.isInteger(entry.bytes) ? entry.bytes : null,
    }));

const compactValidity = (value: unknown): Record<string, unknown> => {
  if (!isRecord(value)) return { passed: false };
  const detail = asString(value.detail);
  return detail === null ? { passed: value.passed === true } : { passed: value.passed === true, detail };
};

const compactResult = (result: Record<string, unknown>): Record<string, unknown> => ({
  source: asString(result.source),
  fidelity: asString(result.fidelity),
  solverIdentity: asString(result.solver_identity) ?? asString(result.solverIdentity),
  solverVersion: asString(result.solver_version) ?? asString(result.solverVersion),
  runId: asString(result.run_id) ?? asString(result.runId),
  resultId: asString(result.result_id) ?? asString(result.resultId),
  provenanceId: asString(result.provenance_id) ?? asString(result.provenanceId),
  inputHash: asString(result.input_hash) ?? asString(result.inputHash),
  validity: compactValidity(result.validity),
  warnings: asArray(result.warnings).filter((warning): warning is string => typeof warning === "string").slice(0, MAX_WARNINGS),
  scalars: compactNumberMap(result.scalars),
  units: compactStringMap(result.units),
  artifacts: compactArtifactRefs(result.artifacts),
});

const compactResultManifest = (manifest: Record<string, unknown>): Record<string, unknown> => ({
  jobId: asString(manifest.job_id) ?? asString(manifest.jobId),
  designId: asString(manifest.design_id) ?? asString(manifest.designId),
  revisionId: asString(manifest.revision_id) ?? asString(manifest.revisionId),
  resultId: asString(manifest.result_id) ?? asString(manifest.resultId),
  runId: asString(manifest.run_id) ?? asString(manifest.runId),
  provenanceId: asString(manifest.provenance_id) ?? asString(manifest.provenanceId),
  source: asString(manifest.source),
  fidelity: asString(manifest.fidelity),
  solverIdentity: asString(manifest.solver_identity) ?? asString(manifest.solverIdentity),
  solverVersion: asString(manifest.solver_version) ?? asString(manifest.solverVersion),
  inputHash: asString(manifest.input_hash) ?? asString(manifest.inputHash),
  validity: compactValidity(manifest.validity),
  artifacts: compactArtifactRefs(manifest.artifacts),
});

const compactProvenance = (provenance: Record<string, unknown>): Record<string, unknown> => ({
  jobId: asString(provenance.job_id) ?? asString(provenance.jobId),
  events: asArray(provenance.events)
    .slice(0, MAX_PROVENANCE_EVENTS)
    .filter(isRecord)
    .map((event) => ({
      id: asString(event.id),
      at: asString(event.at),
      type: asString(event.type),
      detail: asString(event.detail),
    })),
});

const mapStatus = (status: Record<string, unknown>): Record<string, unknown> => ({
  jobId: asString(status.job_id),
  participantId: asString(status.participant_id),
  designId: asString(status.design_id),
  ownerId: asString(status.owner_id),
  revisionId: asString(status.revision_id),
  analysis: asString(status.analysis),
  fidelity: asString(status.fidelity),
  state: asString(status.state),
  errorCode: asString(status.error_code),
  errorDetail: asString(status.error_detail),
  runId: asString(status.run_id),
  resultId: asString(status.result_id),
  provenanceId: asString(status.provenance_id),
  inputHash: asString(status.input_hash),
  source: "product-api",
});

export class EngineeringOperations {
  private readonly api: EngineeringApi;
  private readonly policy: EngineeringPolicy;
  constructor(api: EngineeringApi, policy: EngineeringPolicy) {
    this.api = api;
    this.policy = policy;
  }

  async call(tool: EngineeringToolName, input: Record<string, unknown>): Promise<Record<string, unknown>> {
    switch (tool) {
      case "capabilities.inspect": return this.capabilitiesInspect();
      case "design.inspect": return this.designInspect(input);
      case "job.inspect": return this.jobInspect(input);
      case "result.inspect": return this.resultInspect(input);
      case "design.variant.create": return this.variantCreate(input);
      case "analysis.submit": return this.analysisSubmit(input);
      case "job.cancel": return this.jobCancel(input);
      default: throw new Error("UNKNOWN_MCP_OPERATION");
    }
  }

  private assertMutations(): void {
    if (!this.policy.mutations) throw new Error("MUTATION_NOT_AUTHORIZED");
  }

  private assertDestructive(): void {
    if (!this.policy.destructive) throw new Error("DESTRUCTIVE_OPERATION_NOT_AUTHORIZED");
  }

  private async capabilitiesInspect(): Promise<Record<string, unknown>> {
    const [capabilities, participants] = await Promise.all([
      this.api.capabilities(),
      this.api.participants(),
    ]);
    return {
      source: "product-api",
      capabilities,
      participants,
      policy: {
        ownerId: this.policy.ownerId,
        mutations: this.policy.mutations,
        destructive: this.policy.destructive,
        remoteCompute: this.policy.remoteCompute,
        remoteCostCeilingUsd: this.policy.remoteCostCeilingUsd,
        deferredSubmitsOnly: true,
      },
    };
  }

  private async designInspect(input: Record<string, unknown>): Promise<Record<string, unknown>> {
    const jobId = assertSafeToken(input.jobId, "jobId");
    const status = await this.api.jobStatus(jobId);
    return {
      jobId,
      designId: asString(status.design_id),
      revisionId: asString(status.revision_id),
      inputHash: asString(status.input_hash),
      participantId: asString(status.participant_id),
      analysis: asString(status.analysis),
      fidelity: asString(status.fidelity),
      // No separate design store exists; design/revision metadata is anchored
      // to the governed job record, read through the same path the UI uses.
      designStore: "job-anchored",
      source: "product-api",
    };
  }

  private async jobInspect(input: Record<string, unknown>): Promise<Record<string, unknown>> {
    const jobId = assertSafeToken(input.jobId, "jobId");
    return mapStatus(await this.api.jobStatus(jobId));
  }

  private async resultInspect(input: Record<string, unknown>): Promise<Record<string, unknown>> {
    const jobId = assertSafeToken(input.jobId, "jobId");
    const [result, manifest, provenance] = await Promise.all([
      this.api.jobResult(jobId),
      this.api.jobResultManifest(jobId),
      this.api.jobProvenance(jobId),
    ]);
    return {
      jobId,
      source: "product-api",
      result: compactResult(result),
      manifest: compactResultManifest(manifest),
      provenance: compactProvenance(provenance),
    };
  }

  private async variantCreate(input: Record<string, unknown>): Promise<Record<string, unknown>> {
    this.assertMutations();
    rejectRemoteEscalation(input);
    rejectCostEscalation(input);
    const designId = assertSafeToken(input.designId, "designId");
    const variantRevisionId = assertSafeToken(input.variantRevisionId, "variantRevisionId");
    return this.submitGoverned({ ...input, designId, revisionId: variantRevisionId });
  }

  private async analysisSubmit(input: Record<string, unknown>): Promise<Record<string, unknown>> {
    this.assertMutations();
    rejectRemoteEscalation(input);
    rejectCostEscalation(input);
    const designId = input.designId === undefined ? "generic-design" : assertSafeToken(input.designId, "designId");
    const revisionId = input.revisionId === undefined ? undefined : assertSafeToken(input.revisionId, "revisionId");
    return this.submitGoverned({ ...input, designId, revisionId });
  }

  /**
   * Submit through API-supported fields only, always deferred: MCP queues a
   * governed job but never starts execution itself, so it cannot trigger
   * cost-bearing compute by itself.
   */
  private async submitGoverned(input: Record<string, unknown>): Promise<Record<string, unknown>> {
    const participantId = assertSafeToken(input.participantId, "participantId");
    const analysis = input.analysis === undefined ? undefined : assertSafeToken(input.analysis, "analysis");
    const fidelity = input.fidelity === undefined ? undefined : assertSafeToken(input.fidelity, "fidelity");
    const inputs = this.assertBoundedInputs(input.inputs);
    const requestedMemoryMib = this.assertBoundedMemory(input.requestedMemoryMib);
    await this.assertSupportedTarget(participantId, fidelity);
    const status = await this.api.submitAnalysis({
      participantId,
      inputs,
      designId: String(input.designId),
      ownerId: this.policy.ownerId,
      ...(input.revisionId === undefined ? {} : { revisionId: String(input.revisionId) }),
      ...(analysis === undefined ? {} : { analysis }),
      ...(fidelity === undefined ? {} : { fidelity }),
      ...(requestedMemoryMib === undefined ? {} : { requestedMemoryMib }),
    });
    return {
      jobId: asString(status.job_id),
      state: asString(status.state),
      participantId,
      designId: asString(status.design_id),
      revisionId: asString(status.revision_id),
      analysis: asString(status.analysis),
      fidelity: asString(status.fidelity),
      deferred: true,
      source: "product-api",
    };
  }

  private async jobCancel(input: Record<string, unknown>): Promise<Record<string, unknown>> {
    this.assertDestructive();
    rejectRemoteEscalation(input);
    rejectCostEscalation(input);
    const jobId = assertSafeToken(input.jobId ?? input.id, "jobId");
    assertOwnedJobStatus(await this.api.jobStatus(jobId), this.policy.ownerId);
    const cancelled = await this.api.cancelJob(jobId);
    return { jobId, state: asString(cancelled.state), source: "product-api" };
  }

  /** Participant/fidelity allowlist is read live from the product API. */
  private async assertSupportedTarget(participantId: string, fidelity: string | undefined): Promise<void> {
    const participants = await this.api.participants();
    const manifest = participants.find((entry) => entry.participantId === participantId);
    if (!manifest) throw new Error("UNKNOWN_PARTICIPANT");
    if (fidelity !== undefined && !manifest.fidelityLevels.includes(fidelity)) {
      throw new Error(`UNSUPPORTED_ANALYSIS:allowed=${manifest.fidelityLevels.join(",")}`);
    }
  }

  private assertBoundedInputs(value: unknown): Record<string, string | number | boolean> {
    if (value === undefined) return {};
    if (typeof value !== "object" || value === null || Array.isArray(value)) throw new Error("INVALID_JOB_INPUTS");
    const entries = Object.entries(value);
    if (entries.length > 32) throw new Error("INVALID_JOB_INPUTS");
    const bounded: Record<string, string | number | boolean> = {};
    for (const [key, entry] of entries) {
      if (!isSafeToken(key) || key.length > 64 || !isSafeInputValue(entry)) throw new Error("INVALID_JOB_INPUTS");
      bounded[key] = entry as string | number | boolean;
    }
    return bounded;
  }

  private assertBoundedMemory(value: unknown): number | undefined {
    if (value === undefined) return undefined;
    if (typeof value !== "number" || !Number.isFinite(value) || value <= 0 || value > 896) {
      throw new Error("INVALID_RSS_RESERVATION");
    }
    return value;
  }
}
