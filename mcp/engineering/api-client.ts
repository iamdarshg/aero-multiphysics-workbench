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

/**
 * Bounded read cache for the two slow-moving discovery endpoints (capability
 * and participant manifests). They change at campaign/environment boundaries,
 * not per job, so a short-lived cache removes one HTTP round trip per submit
 * without weakening the policy gate: an unknown participant still fails closed.
 * `0` disables the cache. Explicit invalidation is available via `invalidate()`.
 */
const DEFAULT_READ_CACHE_TTL_MS = (() => {
  const raw = Number(process.env.AERO_MCP_READ_CACHE_MS ?? "");
  return Number.isFinite(raw) && raw >= 0 ? raw : 15_000;
})();

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

export interface HttpEngineeringApiOptions {
  readonly readCacheTtlMs?: number;
  readonly now?: () => number;
}

export interface HttpEngineeringApiCacheStats {
  readonly hits: number;
  readonly misses: number;
  readonly invalidations: number;
}

export class HttpEngineeringApi implements EngineeringApi {
  private readonly baseUrl: string;
  private readonly readCacheTtlMs: number;
  private readonly now: () => number;
  private participantsCache: { atMs: number; value: ParticipantSummary[] } | null = null;
  private capabilitiesCache: { atMs: number; value: Record<string, unknown> } | null = null;
  private participantsInflight: Promise<ParticipantSummary[]> | null = null;
  private capabilitiesInflight: Promise<Record<string, unknown>> | null = null;
  private cacheCounters = { hits: 0, misses: 0, invalidations: 0 };

  constructor(baseUrl: string, options: HttpEngineeringApiOptions = {}) {
    this.baseUrl = baseUrl.replace(/\/$/, "");
    this.readCacheTtlMs = options.readCacheTtlMs ?? DEFAULT_READ_CACHE_TTL_MS;
    if (!Number.isFinite(this.readCacheTtlMs) || this.readCacheTtlMs < 0) throw new Error("INVALID_READ_CACHE_TTL");
    this.now = options.now ?? (() => Date.now());
  }

  /** Drops cached discovery payloads; call after a known environment change. */
  invalidate(): void {
    this.cacheCounters.invalidations += 1;
    this.participantsCache = null;
    this.capabilitiesCache = null;
  }

  cacheStats(): HttpEngineeringApiCacheStats {
    return { ...this.cacheCounters };
  }

  private readCacheFresh(entry: { atMs: number } | null): boolean {
    return this.readCacheTtlMs > 0 && entry !== null && this.now() - entry.atMs < this.readCacheTtlMs;
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
    if (this.readCacheFresh(this.capabilitiesCache)) {
      this.cacheCounters.hits += 1;
      return Promise.resolve((this.capabilitiesCache as { value: Record<string, unknown> }).value);
    }
    if (this.capabilitiesInflight) return this.capabilitiesInflight;
    this.cacheCounters.misses += 1;
    const inflight = this.request<Record<string, unknown>>("GET", "/v1/native/capabilities")
      .then((value) => {
        this.capabilitiesCache = { atMs: this.now(), value };
        return value;
      })
      .finally(() => {
        this.capabilitiesInflight = null;
      });
    this.capabilitiesInflight = inflight;
    return inflight;
  }

  participants(): Promise<ParticipantSummary[]> {
    if (this.readCacheFresh(this.participantsCache)) {
      this.cacheCounters.hits += 1;
      return Promise.resolve((this.participantsCache as { value: ParticipantSummary[] }).value);
    }
    if (this.participantsInflight) return this.participantsInflight;
    this.cacheCounters.misses += 1;
    const inflight = this.request<{ participants?: unknown }>("GET", "/v1/native/participants")
      .then((payload) => {
        const value = Array.isArray(payload.participants)
          ? payload.participants.filter(isRecord).map((entry) => ({
            participantId: typeof entry.participant_id === "string" ? entry.participant_id : "",
            fidelityLevels: Array.isArray(entry.fidelity_levels)
              ? entry.fidelity_levels.filter((level): level is string => typeof level === "string")
              : [],
          }))
          : [];
        this.participantsCache = { atMs: this.now(), value };
        return value;
      })
      .finally(() => {
        this.participantsInflight = null;
      });
    this.participantsInflight = inflight;
    return inflight;
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
