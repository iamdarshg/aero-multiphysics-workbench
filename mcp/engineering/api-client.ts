/**
 * Thin typed client of the public product API — the same paths a human or
 * the workbench UI uses. The MCP server never imports scheduler internals
 * or solver adapters; every operational tool goes through this client.
 */

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  constructor(message: string, status: number, code: string) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
  }
}

export interface ParticipantSummary {
  readonly participantId: string;
  readonly fidelityLevels: readonly string[];
}

export interface SubmitAnalysisInput {
  readonly participantId: string;
  readonly inputs: Record<string, string | number | boolean>;
  readonly designId: string;
  readonly ownerId: string;
  readonly revisionId?: string;
  readonly analysis?: string;
  readonly fidelity?: string;
  readonly requestedMemoryMib?: number;
}

/** Port implemented by the HTTP client below; fakes can implement it in tests. */
export interface EngineeringApi {
  capabilities(): Promise<Record<string, unknown>>;
  participants(): Promise<ParticipantSummary[]>;
  submitAnalysis(input: SubmitAnalysisInput): Promise<Record<string, unknown>>;
  jobStatus(jobId: string): Promise<Record<string, unknown>>;
  cancelJob(jobId: string): Promise<Record<string, unknown>>;
  jobResult(jobId: string): Promise<Record<string, unknown>>;
  jobResultManifest(jobId: string): Promise<Record<string, unknown>>;
  jobProvenance(jobId: string): Promise<Record<string, unknown>>;
}

const REQUEST_TIMEOUT_MS = 5000;

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

const errorFromPayload = (status: number, payload: unknown, fallback: string): ApiError => {
  if (isRecord(payload) && isRecord(payload.detail)) {
    const code = typeof payload.detail.code === "string" ? payload.detail.code : fallback;
    const message = typeof payload.detail.message === "string" ? payload.detail.message : code;
    return new ApiError(message, status, code);
  }
  if (isRecord(payload) && typeof payload.detail === "string" && payload.detail) {
    return new ApiError(payload.detail, status, fallback);
  }
  return new ApiError(`${fallback}: HTTP ${status}`, status, fallback);
};

export class HttpEngineeringApi implements EngineeringApi {
  private readonly baseUrl: string;
  constructor(baseUrl: string) {
    this.baseUrl = baseUrl.replace(/\/$/, "");
  }

  private async request<T>(method: string, path: string, body?: unknown): Promise<T> {
    let response: Response;
    try {
      response = await fetch(`${this.baseUrl}${path}`, {
        method,
        headers: { accept: "application/json", "content-type": "application/json" },
        body: body === undefined ? undefined : JSON.stringify(body),
        signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
      });
    } catch (error) {
      throw new ApiError(
        error instanceof Error ? error.message : "API request failed",
        0,
        "API_NOT_REACHABLE",
      );
    }
    const payload: unknown = await response.json().catch(() => null);
    if (!response.ok) throw errorFromPayload(response.status, payload, "API_REQUEST_FAILED");
    return payload as T;
  }

  capabilities(): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>("GET", "/v1/native/capabilities");
  }

  async participants(): Promise<ParticipantSummary[]> {
    const payload = await this.request<{ participants?: unknown }>("GET", "/v1/native/participants");
    if (!Array.isArray(payload.participants)) return [];
    return payload.participants.filter(isRecord).map((entry) => ({
      participantId: typeof entry.participant_id === "string" ? entry.participant_id : "",
      fidelityLevels: Array.isArray(entry.fidelity_levels)
        ? entry.fidelity_levels.filter((level): level is string => typeof level === "string")
        : [],
    }));
  }

  submitAnalysis(input: SubmitAnalysisInput): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>("POST", "/v1/native/analyses", {
      participant_id: input.participantId,
      inputs: input.inputs,
      design_id: input.designId,
      owner_id: input.ownerId,
      deferred: true,
      ...(input.revisionId === undefined ? {} : { revision_id: input.revisionId }),
      ...(input.analysis === undefined ? {} : { analysis: input.analysis }),
      ...(input.fidelity === undefined ? {} : { fidelity: input.fidelity }),
      ...(input.requestedMemoryMib === undefined ? {} : { requested_memory_mib: input.requestedMemoryMib }),
    });
  }

  jobStatus(jobId: string): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>("GET", `/v1/native/analyses/${encodeURIComponent(jobId)}`);
  }

  cancelJob(jobId: string): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>("POST", `/v1/native/analyses/${encodeURIComponent(jobId)}/cancel`, {});
  }

  jobResult(jobId: string): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>("GET", `/v1/native/results/${encodeURIComponent(jobId)}`);
  }

  jobResultManifest(jobId: string): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>("GET", `/v1/native/results/${encodeURIComponent(jobId)}/manifest`);
  }

  jobProvenance(jobId: string): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>("GET", `/v1/native/provenance/${encodeURIComponent(jobId)}`);
  }
}
