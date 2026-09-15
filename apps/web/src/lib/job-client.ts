// One typed API client for the workbench backend.
//
// Every component talks to the API through this module. Raw `fetch()` calls
// must not be scattered through components.

export type ResultSourceLabel = 'analytical' | 'benchmark' | 'native_solver';

export type JobState =
  | 'QUEUED'
  | 'PREPARING'
  | 'RUNNING'
  | 'PARSING'
  | 'VALIDATING'
  | 'COMPLETED'
  | 'FAILED'
  | 'CANCELLED';

export interface HealthReport {
  status: string;
  analyticalModels: string[];
  nativeSolvers: Record<string, unknown>;
}

export interface WorkbenchStateReport {
  defaultCouplingStrength: number;
  availableResultSources: string[];
}

export interface CapabilityEntry {
  participantId: string;
  solverId: string;
  executable: string;
  version: string | null;
  detail: string;
}

export interface CapabilityReport {
  ready: CapabilityEntry[];
  unavailable: CapabilityEntry[];
}

export interface ParticipantSummary {
  participantId: string;
  physicsDomain: string;
  solverId: string;
  executionMode: string;
  fidelityLevels: string[];
  couplingDirection: string;
  benchmarkRef: string;
}

export interface ParticipantReport {
  manifestVersion: string;
  participants: ParticipantSummary[];
}

export interface SubmitJobRequest {
  participantId: string;
  inputs: Record<string, unknown>;
  designId: string;
  analysis?: string;
  fidelity?: string;
  deferred?: boolean;
}

export interface SubmittedJob {
  jobId: string;
  state: JobState;
  participantId: string;
}

export interface JobStatus {
  jobId: string;
  participantId: string;
  designId: string;
  ownerId: string | null;
  revisionId: string | null;
  analysis: string | null;
  fidelity: string;
  state: JobState;
  errorCode: string | null;
  errorDetail: string | null;
  runId: string | null;
  resultId: string | null;
  provenanceId: string | null;
  inputHash: string | null;
}

export interface JobEvent {
  sequence: number;
  state: JobState;
  at: string;
  detail: string;
}

export interface CancelledJob {
  jobId: string;
  state: string;
}

export interface ResultEnvelopeSummary {
  source: 'native_solver';
  fidelity: string;
  solverIdentity: string;
  solverVersion: string;
  runId: string;
  provenanceId: string;
  inputHash: string;
  validity: { passed: boolean; detail: string };
  warnings: string[];
  scalars: Record<string, number>;
  units: Record<string, string>;
  artifacts: Array<{ name: string; sha256: string; bytes: number }>;
}

export interface ArtifactMetadata {
  id: string;
  name: string;
  displayName: string;
  mime: string;
  category: string;
  bytes: number;
  sha256: string;
  solverId: string;
  runId: string | null;
  provenanceId: string | null;
  downloadUrl: string;
}

export interface ResultManifestArtifact {
  name: string;
  sha256: string;
  bytes: number;
}

export interface ResultManifest {
  jobId: string;
  designId: string;
  revisionId: string | null;
  resultId: string | null;
  runId: string | null;
  provenanceId: string | null;
  source: string;
  fidelity: string;
  validity: { passed: boolean; detail: string };
  solverIdentity: string;
  solverVersion: string;
  inputHash: string | null;
  artifacts: ResultManifestArtifact[];
}

export interface JobProvenance {
  jobId: string;
  events: Array<Record<string, unknown>>;
}

export interface SubscribeOptions {
  pollIntervalMs?: number;
  signal?: AbortSignal;
  onEvent?: (event: JobEvent, events: JobEvent[]) => void;
}

export class JobApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(message: string, status: number, code: string) {
    super(message);
    this.name = 'JobApiError';
    this.status = status;
    this.code = code;
  }
}

const DEFAULT_API_BASE = 'http://localhost:8000';
const REQUEST_TIMEOUT_MS = 5000;
const SUBSCRIBE_POLL_MS = 750;

export const apiBaseUrl = (): string => {
  const configured = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
  return (configured || DEFAULT_API_BASE).replace(/\/$/, '');
};

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null;

const asString = (value: unknown, fallback = ''): string =>
  typeof value === 'string' ? value : fallback;

const asNullableString = (value: unknown): string | null =>
  typeof value === 'string' ? value : null;

const failFromPayload = (status: number, payload: unknown, fallback: string): never => {
  if (isRecord(payload) && isRecord(payload.detail)) {
    const code = asString(payload.detail.code, fallback);
    const message = asString(payload.detail.message, code);
    throw new JobApiError(message, status, code);
  }
  if (isRecord(payload) && typeof payload.detail === 'string' && payload.detail) {
    throw new JobApiError(payload.detail, status, fallback);
  }
  throw new JobApiError(`${fallback}: HTTP ${status}`, status, fallback);
};

const requestJson = async <T>(
  path: string,
  init: RequestInit,
  timeoutMs = REQUEST_TIMEOUT_MS,
): Promise<T> => {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`${apiBaseUrl()}${path}`, {
      ...init,
      headers: { accept: 'application/json', ...(init.headers ?? {}) },
      signal: controller.signal,
    });
    const payload: unknown = await response.json().catch(() => null);
    if (!response.ok) failFromPayload(response.status, payload, 'API_REQUEST_FAILED');
    return payload as T;
  } catch (error) {
    if (error instanceof JobApiError) throw error;
    throw new JobApiError(
      error instanceof Error ? error.message : 'API request failed',
      0,
      'API_UNREACHABLE',
    );
  } finally {
    clearTimeout(timeout);
  }
};

const getJson = <T>(path: string): Promise<T> =>
  requestJson<T>(path, { method: 'GET' });

const postJson = <T>(path: string, body?: unknown): Promise<T> =>
  requestJson<T>(path, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  });

interface HealthPayload {
  status: string;
  analytical_models?: unknown;
  native_solvers?: unknown;
}

export const getHealth = async (): Promise<HealthReport> => {
  const payload = await getJson<HealthPayload>('/health');
  const analyticalModels = Array.isArray(payload.analytical_models)
    ? payload.analytical_models.filter((entry): entry is string => typeof entry === 'string')
    : [];
  const nativeSolvers =
    isRecord(payload.native_solvers) && !Array.isArray(payload.native_solvers)
      ? (payload.native_solvers as Record<string, unknown>)
      : {};
  return { status: asString(payload.status, 'unknown'), analyticalModels, nativeSolvers };
};

interface WorkbenchStatePayload {
  default_coupling_strength?: unknown;
  available_result_sources?: unknown;
}

export const getWorkbenchState = async (): Promise<WorkbenchStateReport> => {
  const payload = await getJson<WorkbenchStatePayload>('/api/v1/workbench/state');
  const sources = Array.isArray(payload.available_result_sources)
    ? payload.available_result_sources.filter((entry): entry is string => typeof entry === 'string')
    : [];
  const strength =
    typeof payload.default_coupling_strength === 'number' ? payload.default_coupling_strength : 0.9;
  return { defaultCouplingStrength: strength, availableResultSources: sources };
};

interface CapabilityEntryPayload {
  participant_id?: unknown;
  solver_id?: unknown;
  executable?: unknown;
  version?: unknown;
  detail?: unknown;
}

const toCapabilityEntry = (payload: CapabilityEntryPayload): CapabilityEntry => ({
  participantId: asString(payload.participant_id, 'unknown'),
  solverId: asString(payload.solver_id, 'unknown'),
  executable: asString(payload.executable, 'unknown'),
  version: typeof payload.version === 'string' ? payload.version : null,
  detail: asString(payload.detail, ''),
});

export const getCapabilities = async (): Promise<CapabilityReport> => {
  const payload = await getJson<{ ready?: unknown; unavailable?: unknown }>('/v1/native/capabilities');
  const ready = Array.isArray(payload.ready)
    ? payload.ready.filter(isRecord).map((entry) => toCapabilityEntry(entry as CapabilityEntryPayload))
    : [];
  const unavailable = Array.isArray(payload.unavailable)
    ? payload.unavailable.filter(isRecord).map((entry) => toCapabilityEntry(entry as CapabilityEntryPayload))
    : [];
  return { ready, unavailable };
};

export const getParticipants = async (): Promise<ParticipantReport> => {
  const payload = await getJson<{ manifest_version?: unknown; participants?: unknown }>(
    '/v1/native/participants',
  );
  const participants = Array.isArray(payload.participants)
    ? payload.participants.filter(isRecord).map((entry) => {
        const record = entry as Record<string, unknown>;
        const fidelityLevels = Array.isArray(record.fidelity_levels)
          ? record.fidelity_levels.filter((level): level is string => typeof level === 'string')
          : [];
        return {
          participantId: asString(record.participant_id, 'unknown'),
          physicsDomain: asString(record.physics_domain, ''),
          solverId: asString(record.solver_id, ''),
          executionMode: asString(record.execution_mode, ''),
          fidelityLevels,
          couplingDirection: asString(record.coupling_direction, ''),
          benchmarkRef: asString(record.benchmark_ref, ''),
        };
      })
    : [];
  return { manifestVersion: asString(payload.manifest_version, ''), participants };
};

export const submitJob = async (request: SubmitJobRequest): Promise<SubmittedJob> => {
  const payload = await postJson<Record<string, unknown>>('/v1/native/analyses', {
    participant_id: request.participantId,
    inputs: request.inputs,
    design_id: request.designId,
    ...(request.analysis === undefined ? {} : { analysis: request.analysis }),
    ...(request.fidelity === undefined ? {} : { fidelity: request.fidelity }),
    deferred: request.deferred ?? true,
  });
  return {
    jobId: asString(payload.job_id),
    state: asString(payload.state, 'QUEUED') as JobState,
    participantId: asString(payload.participant_id, request.participantId),
  };
};

export const getJob = async (jobId: string): Promise<JobStatus> => {
  const payload = await getJson<Record<string, unknown>>(
    `/v1/native/analyses/${encodeURIComponent(jobId)}`,
  );
  return {
    jobId: asString(payload.job_id, jobId),
    participantId: asString(payload.participant_id),
    designId: asString(payload.design_id),
    ownerId: asNullableString(payload.owner_id),
    revisionId: asNullableString(payload.revision_id),
    analysis: asNullableString(payload.analysis),
    fidelity: asString(payload.fidelity),
    state: asString(payload.state, 'QUEUED') as JobState,
    errorCode: asNullableString(payload.error_code),
    errorDetail: asNullableString(payload.error_detail),
    runId: asNullableString(payload.run_id),
    resultId: asNullableString(payload.result_id),
    provenanceId: asNullableString(payload.provenance_id),
    inputHash: asNullableString(payload.input_hash),
  };
};

const toJobEvent = (payload: unknown): JobEvent | null => {
  if (!isRecord(payload)) return null;
  const sequence = payload.sequence;
  if (typeof sequence !== 'number') return null;
  return {
    sequence,
    state: asString(payload.state, 'QUEUED') as JobState,
    at: asString(payload.at),
    detail: asString(payload.detail),
  };
};

export const parseSseBody = (body: string): JobEvent[] => {
  const events: JobEvent[] = [];
  for (const line of body.split('\n')) {
    const trimmed = line.trim();
    if (!trimmed.startsWith('data:')) continue;
    try {
      const event = toJobEvent(JSON.parse(trimmed.slice('data:'.length).trim()) as unknown);
      if (event) events.push(event);
    } catch {
      // Ignore malformed SSE data lines; JSON polling remains the source of truth.
    }
  }
  return events.sort((a, b) => a.sequence - b.sequence);
};

export const getJobEvents = async (jobId: string): Promise<JobEvent[]> => {
  const payload = await getJson<{ events?: unknown }>(
    `/v1/native/analyses/${encodeURIComponent(jobId)}/events`,
  );
  if (!Array.isArray(payload.events)) return [];
  return payload.events
    .map(toJobEvent)
    .filter((event): event is JobEvent => event !== null)
    .sort((a, b) => a.sequence - b.sequence);
};

const TERMINAL_JOB_STATES: ReadonlySet<string> = new Set(['COMPLETED', 'FAILED', 'CANCELLED']);

const delay = (ms: number, signal?: AbortSignal): Promise<void> =>
  new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(new JobApiError('Subscription aborted', 0, 'SUBSCRIPTION_ABORTED'));
      return;
    }
    const timer = setTimeout(() => {
      signal?.removeEventListener('abort', onAbort);
      resolve();
    }, ms);
    const onAbort = (): void => {
      clearTimeout(timer);
      reject(new JobApiError('Subscription aborted', 0, 'SUBSCRIPTION_ABORTED'));
    };
    signal?.addEventListener('abort', onAbort, { once: true });
  });

/** Poll the persisted backend event stream; progress comes only from real events. */
export const subscribeJobEvents = async (
  jobId: string,
  options: SubscribeOptions = {},
): Promise<JobEvent[]> => {
  const pollIntervalMs = options.pollIntervalMs ?? SUBSCRIBE_POLL_MS;
  const seen = new Map<number, JobEvent>();
  for (;;) {
    if (options.signal?.aborted) {
      throw new JobApiError('Subscription aborted', 0, 'SUBSCRIPTION_ABORTED');
    }
    const events = await getJobEvents(jobId);
    const fresh = events.filter((event) => !seen.has(event.sequence));
    for (const event of fresh) {
      seen.set(event.sequence, event);
      options.onEvent?.(event, [...seen.values()].sort((a, b) => a.sequence - b.sequence));
    }
    const latest = [...seen.values()].sort((a, b) => a.sequence - b.sequence).at(-1);
    if (latest && TERMINAL_JOB_STATES.has(latest.state)) {
      return [...seen.values()].sort((a, b) => a.sequence - b.sequence);
    }
    await delay(pollIntervalMs, options.signal);
  }
};

export const startJob = async (jobId: string): Promise<{ jobId: string; state: string }> => {
  const payload = await postJson<Record<string, unknown>>(
    `/v1/native/analyses/${encodeURIComponent(jobId)}/start`,
  );
  return { jobId: asString(payload.job_id, jobId), state: asString(payload.state) };
};

export const cancelJob = async (jobId: string): Promise<CancelledJob> => {
  const payload = await postJson<Record<string, unknown>>(
    `/v1/native/analyses/${encodeURIComponent(jobId)}/cancel`,
  );
  return { jobId: asString(payload.job_id, jobId), state: asString(payload.state) };
};

export const getJobResult = async (jobId: string): Promise<ResultEnvelopeSummary> => {
  const payload = await getJson<Record<string, unknown>>(
    `/v1/native/results/${encodeURIComponent(jobId)}`,
  );
  const scalars: Record<string, number> = {};
  if (isRecord(payload.scalars)) {
    for (const [key, value] of Object.entries(payload.scalars)) {
      if (typeof value === 'number' && Number.isFinite(value)) scalars[key] = value;
    }
  }
  const units: Record<string, string> = {};
  if (isRecord(payload.units)) {
    for (const [key, value] of Object.entries(payload.units)) {
      if (typeof value === 'string') units[key] = value;
    }
  }
  const warnings = Array.isArray(payload.warnings)
    ? payload.warnings.filter((entry): entry is string => typeof entry === 'string')
    : [];
  const validity = isRecord(payload.validity) ? payload.validity : {};
  const artifacts: Array<{ name: string; sha256: string; bytes: number }> = [];
  if (Array.isArray(payload.artifacts)) {
    for (const entry of payload.artifacts) {
      if (!isRecord(entry)) continue;
      const name = asString(entry.name);
      const sha256 = asString(entry.sha256);
      if (!name || !sha256 || typeof entry.bytes !== 'number') continue;
      artifacts.push({ name, sha256, bytes: entry.bytes });
    }
  }
  return {
    source: 'native_solver',
    fidelity: asString(payload.fidelity),
    solverIdentity: asString(payload.solver_identity),
    solverVersion: asString(payload.solver_version),
    runId: asString(payload.run_id),
    provenanceId: asString(payload.provenance_id),
    inputHash: asString(payload.input_hash),
    validity: {
      passed: validity.passed === true,
      detail: asString(validity.detail),
    },
    warnings,
    scalars,
    units,
    artifacts,
  };
};

export const getJobProvenance = async (jobId: string): Promise<JobProvenance> => {
  const payload = await getJson<{ job_id?: unknown; events?: unknown }>(
    `/v1/native/provenance/${encodeURIComponent(jobId)}`,
  );
  const events = Array.isArray(payload.events) ? payload.events.filter(isRecord) : [];
  return { jobId: asString(payload.job_id, jobId), events };
};

const toArtifactMetadata = (payload: unknown): ArtifactMetadata | null => {
  if (!isRecord(payload)) return null;
  const id = asString(payload.id);
  const name = asString(payload.name);
  if (!id || !name) return null;
  const sha256 = asString(payload.sha256);
  if (!/^[0-9a-f]{64}$/.test(sha256)) return null;
  return {
    id,
    name,
    displayName: asString(payload.display_name, name),
    mime: asString(payload.mime, 'application/octet-stream'),
    category: asString(payload.category, 'other'),
    bytes: typeof payload.bytes === 'number' ? payload.bytes : 0,
    sha256,
    solverId: asString(payload.solver_id),
    runId: asNullableString(payload.run_id),
    provenanceId: asNullableString(payload.provenance_id),
    downloadUrl: asString(payload.download_url),
  };
};

/** Read-only metadata for artifacts registered to a completed result. */
export const getJobArtifacts = async (jobId: string): Promise<ArtifactMetadata[]> => {
  const payload = await getJson<{ artifacts?: unknown }>(
    `/v1/native/artifacts/${encodeURIComponent(jobId)}`,
  );
  if (!Array.isArray(payload.artifacts)) return [];
  return payload.artifacts
    .map(toArtifactMetadata)
    .filter((entry): entry is ArtifactMetadata => entry !== null);
};

/** Absolute download URL for one registered artifact id (metadata-resolved only). */
export const artifactFileUrl = (downloadUrl: string): string =>
  `${apiBaseUrl()}${downloadUrl.startsWith('/') ? downloadUrl : `/${downloadUrl}`}`;

/** Absolute URL for the small machine-readable result manifest export. */
export const resultManifestUrl = (jobId: string): string =>
  `${apiBaseUrl()}/v1/native/results/${encodeURIComponent(jobId)}/manifest`;

/** Fetch one registered artifact as a Blob for preview; never invents bytes. */
export const downloadJobArtifact = async (jobId: string, artifactId: string): Promise<Blob> => {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    const response = await fetch(
      `${apiBaseUrl()}/v1/native/artifacts/${encodeURIComponent(jobId)}/${encodeURIComponent(artifactId)}`,
      { headers: { accept: '*/*' }, signal: controller.signal },
    );
    if (!response.ok) {
      const payload: unknown = await response.json().catch(() => null);
      failFromPayload(response.status, payload, 'ARTIFACT_DOWNLOAD_FAILED');
    }
    return await response.blob();
  } catch (error) {
    if (error instanceof JobApiError) throw error;
    throw new JobApiError(
      error instanceof Error ? error.message : 'Artifact download failed',
      0,
      'API_UNREACHABLE',
    );
  } finally {
    clearTimeout(timeout);
  }
};

const toManifestArtifact = (payload: unknown): ResultManifestArtifact | null => {
  if (!isRecord(payload)) return null;
  const name = asString(payload.name);
  const sha256 = asString(payload.sha256);
  if (!name || !/^[0-9a-f]{64}$/.test(sha256) || typeof payload.bytes !== 'number') return null;
  return { name, sha256, bytes: payload.bytes };
};

/** Small machine-readable manifest: lineage and hashes, never bundled outputs. */
export const getResultManifest = async (jobId: string): Promise<ResultManifest> => {
  const payload = await getJson<Record<string, unknown>>(
    `/v1/native/results/${encodeURIComponent(jobId)}/manifest`,
  );
  const validity = isRecord(payload.validity) ? payload.validity : {};
  const artifacts = Array.isArray(payload.artifacts)
    ? payload.artifacts
        .map(toManifestArtifact)
        .filter((entry): entry is ResultManifestArtifact => entry !== null)
    : [];
  return {
    jobId: asString(payload.job_id, jobId),
    designId: asString(payload.design_id),
    revisionId: asNullableString(payload.revision_id),
    resultId: asNullableString(payload.result_id),
    runId: asNullableString(payload.run_id),
    provenanceId: asNullableString(payload.provenance_id),
    source: asString(payload.source),
    fidelity: asString(payload.fidelity),
    validity: { passed: validity.passed === true, detail: asString(validity.detail) },
    solverIdentity: asString(payload.solver_identity),
    solverVersion: asString(payload.solver_version),
    inputHash: asNullableString(payload.input_hash),
    artifacts,
  };
};
