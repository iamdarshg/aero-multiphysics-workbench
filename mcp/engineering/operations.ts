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
    return { jobId, source: "product-api", result, manifest, provenance };
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
