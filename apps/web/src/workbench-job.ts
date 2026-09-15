// Native job domain helpers for the workbench UI.
//
// Pure functions only: allowlist validation, submit payloads, event merging,
// backend-derived progress, and honest source/state labels. No timers, no
// fetch, no invented solver output.

import type { JobEvent, JobState, SubmitJobRequest } from './lib/job-client';

export type { JobEvent, JobState };

export interface AllowedAnalysis {
  participantId: string;
  label: string;
  analysis: string;
  fidelity: string;
  designId: string;
  inputs: Record<string, unknown>;
}

/** Small allowlist of analyses the existing UI may submit, with valid canned inputs. */
export const ALLOWED_ANALYSES: AllowedAnalysis[] = [
  {
    participantId: 'rotor-campbell',
    label: 'Rotor Campbell (beam)',
    analysis: 'campbell',
    fidelity: 'beam-campbell',
    designId: 'edf-90-rotor',
    inputs: {
      analysis: 'campbell',
      shaft_length_m: 1.5,
      shaft_diameter_m: 0.05,
      n_elements: 4,
      bearing_stiffness_n_m: 1e8,
      bearing_damping_n_s_m: 1000.0,
      max_speed_rpm: 12000.0,
    },
  },
  {
    participantId: 'cell-spm-discharge',
    label: 'Cell SPM discharge',
    analysis: 'discharge',
    fidelity: 'spm',
    designId: 'battery-pack',
    inputs: {
      model: 'spm',
      parameter_set: 'Chen2020',
      discharge_current_a: 1.0,
      duration_s: 60.0,
      n_series: 1,
      n_parallel: 1,
    },
  },
  {
    participantId: 'domain-mesh',
    label: 'Duct domain mesh',
    analysis: 'mesh',
    fidelity: 'conforming-linear',
    designId: 'edf-90-duct',
    inputs: {
      n_rotating: 1,
      base_size_mm: 2.0,
      length_mm: 90.0,
      inner_diameter_mm: 70.0,
      outer_diameter_mm: 90.0,
      zone_length_mm: 20.0,
      zone_gap_mm: 2.0,
    },
  },
];

const TERMINAL_JOB_STATES: ReadonlySet<JobState> = new Set(['COMPLETED', 'FAILED', 'CANCELLED']);

/** Canonical backend execution chain; progress is a position on this chain. */
export const JOB_STATE_CHAIN: ReadonlyArray<JobState> = [
  'QUEUED',
  'PREPARING',
  'RUNNING',
  'PARSING',
  'VALIDATING',
  'COMPLETED',
];

export const isAllowedParticipant = (participantId: string): boolean =>
  ALLOWED_ANALYSES.some((analysis) => analysis.participantId === participantId);

export const allowedAnalysisFor = (participantId: string): AllowedAnalysis | null =>
  ALLOWED_ANALYSES.find((analysis) => analysis.participantId === participantId) ?? null;

/** Validate the selected analysis and build the submit payload; null means rejected. */
export const buildSubmitPayload = (participantId: string, designId: string): SubmitJobRequest | null => {
  const allowed = allowedAnalysisFor(participantId);
  if (!allowed) return null;
  const trimmedDesign = designId.trim();
  if (!trimmedDesign) return null;
  return {
    participantId: allowed.participantId,
    inputs: { ...allowed.inputs },
    designId: trimmedDesign,
    analysis: allowed.analysis,
    fidelity: allowed.fidelity,
    deferred: false,
  };
};

export const isTerminalJobState = (state: JobState): boolean => TERMINAL_JOB_STATES.has(state);

export const isCancellableJobState = (state: JobState): boolean => !TERMINAL_JOB_STATES.has(state);

/** Merge freshly polled backend events with local state, ordered and deduplicated. */
export const applyJobEvents = (previous: JobEvent[], incoming: JobEvent[]): JobEvent[] => {
  const merged = new Map<number, JobEvent>();
  for (const event of [...previous, ...incoming]) merged.set(event.sequence, event);
  return [...merged.values()].sort((a, b) => a.sequence - b.sequence);
};

const chainIndex = (state: JobState): number => JOB_STATE_CHAIN.indexOf(state);

/**
 * Progress derived exclusively from backend events: position of the latest
 * on-chain event on the canonical chain. FAILED/CANCELLED hold the progress
 * of the last productive event; unknown states contribute nothing.
 */
export const jobProgressPercent = (events: JobEvent[]): number => {
  let furthest = -1;
  for (const event of events) {
    const index = chainIndex(event.state);
    if (index > furthest) furthest = index;
  }
  if (furthest <= 0) return 0;
  return Math.round((furthest / (JOB_STATE_CHAIN.length - 1)) * 100);
};

export const latestJobState = (events: JobEvent[]): JobState | null =>
  events.length > 0 ? events[events.length - 1]?.state ?? null : null;

const JOB_STATE_LABELS: Record<JobState, string> = {
  QUEUED: 'Queued — awaiting the native worker',
  PREPARING: 'Preparing — validating inputs and capability',
  RUNNING: 'Running — native solver executing',
  PARSING: 'Parsing — reading solver output',
  VALIDATING: 'Validating — checking quality gates',
  COMPLETED: 'Completed — native result published',
  FAILED: 'Failed — no result published',
  CANCELLED: 'Cancelled — no result published',
};

export const formatJobState = (state: JobState): string => JOB_STATE_LABELS[state];

export type ResultSourceKind = 'analytical model' | 'native_solver' | string;

/** Preserve exact analytical-vs-native wording; never blur the two. */
export const sourceDisplayLabel = (source: ResultSourceKind): string => {
  if (source === 'native_solver') return 'Native solver · evidence-gated';
  if (source === 'analytical model') return 'Analytical model · sample only';
  return `${source} · unclassified source`;
};

export interface ScalarRow {
  name: string;
  value: number;
}

/** Scalar rows from a completed envelope; empty stays empty, never zero-filled. */
export const summarizeResultScalars = (scalars: Record<string, unknown>): ScalarRow[] => {
  const rows: ScalarRow[] = [];
  for (const [name, value] of Object.entries(scalars)) {
    if (typeof value === 'number' && Number.isFinite(value)) rows.push({ name, value });
  }
  return rows.sort((a, b) => (a.name < b.name ? -1 : a.name > b.name ? 1 : 0));
};

export type JobEmptyKind =
  | 'api-unreachable'
  | 'capability-unavailable'
  | 'queued'
  | 'running'
  | 'failed'
  | 'cancelled'
  | 'completed-invalid'
  | 'completed';

const JOB_EMPTY_MESSAGES: Record<JobEmptyKind, string> = {
  'api-unreachable': 'API unreachable — start the local stack. No job was submitted.',
  'capability-unavailable': 'Native capability unavailable — no solver was launched.',
  queued: 'Job queued — awaiting the native worker. No solver output yet.',
  running: 'Native solver executing — progress follows backend events only.',
  failed: 'Failed — no result published. See the backend reason; nothing here is engineering data.',
  cancelled: 'Cancelled — the job record is preserved and no result was published.',
  'completed-invalid': 'Completed with invalid or partial quality — values are withheld, not zeroed.',
  completed: 'Completed — native result published with provenance.',
};

export const jobEmptyMessage = (kind: JobEmptyKind): string => JOB_EMPTY_MESSAGES[kind];
