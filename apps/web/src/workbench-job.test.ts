import { describe, expect, it } from 'vitest';
import {
  ALLOWED_ANALYSES,
  applyJobEvents,
  buildSubmitPayload,
  formatJobState,
  isAllowedParticipant,
  isCancellableJobState,
  isTerminalJobState,
  jobEmptyMessage,
  jobProgressPercent,
  sourceDisplayLabel,
  summarizeResultScalars,
} from './workbench-job';

describe('workbench native job wiring', () => {
  it('declares a small allowlist of submittable analyses with valid fidelities', () => {
    expect(ALLOWED_ANALYSES.length).toBeGreaterThan(0);
    for (const analysis of ALLOWED_ANALYSES) {
      expect(analysis.participantId).toBeTruthy();
      expect(analysis.fidelity).toBeTruthy();
      expect(typeof analysis.inputs).toBe('object');
    }
    expect(isAllowedParticipant('rotor-campbell')).toBe(true);
    expect(isAllowedParticipant('bogus-participant')).toBe(false);
  });

  it('builds a submit payload only for allowed analyses', () => {
    const payload = buildSubmitPayload('rotor-campbell', 'edf-90');
    expect(payload?.participantId).toBe('rotor-campbell');
    expect(payload?.designId).toBe('edf-90');
    expect(payload?.fidelity).toBe('beam-campbell');
    expect(buildSubmitPayload('bogus-participant', 'edf-90')).toBeNull();
  });

  it('keeps terminal job state exact and cancellable state honest', () => {
    expect(isTerminalJobState('COMPLETED')).toBe(true);
    expect(isTerminalJobState('FAILED')).toBe(true);
    expect(isTerminalJobState('CANCELLED')).toBe(true);
    expect(isTerminalJobState('RUNNING')).toBe(false);
    expect(isCancellableJobState('QUEUED')).toBe(true);
    expect(isCancellableJobState('RUNNING')).toBe(true);
    expect(isCancellableJobState('COMPLETED')).toBe(false);
    expect(isCancellableJobState('FAILED')).toBe(false);
    expect(isCancellableJobState('CANCELLED')).toBe(false);
  });

  it('merges backend events in sequence without inventing progress', () => {
    const first = applyJobEvents([], [
      { sequence: 1, state: 'QUEUED', at: 't0', detail: '' },
      { sequence: 2, state: 'PREPARING', at: 't1', detail: '' },
    ]);
    expect(first.map((event) => event.state)).toEqual(['QUEUED', 'PREPARING']);
    const second = applyJobEvents(first, [
      { sequence: 1, state: 'QUEUED', at: 't0', detail: '' },
      { sequence: 2, state: 'PREPARING', at: 't1', detail: '' },
      { sequence: 3, state: 'RUNNING', at: 't2', detail: '' },
    ]);
    expect(second.map((event) => event.state)).toEqual(['QUEUED', 'PREPARING', 'RUNNING']);
    expect(second).toHaveLength(3);
  });

  it('derives progress only from backend events, never from timers', () => {
    expect(jobProgressPercent([])).toBe(0);
    expect(jobProgressPercent([{ sequence: 1, state: 'QUEUED', at: 't0', detail: '' }])).toBe(0);
    const running = jobProgressPercent([
      { sequence: 1, state: 'QUEUED', at: 't0', detail: '' },
      { sequence: 2, state: 'PREPARING', at: 't1', detail: '' },
      { sequence: 3, state: 'RUNNING', at: 't2', detail: '' },
    ]);
    expect(running).toBeGreaterThan(0);
    expect(running).toBeLessThan(100);
    const completed = jobProgressPercent([
      { sequence: 1, state: 'QUEUED', at: 't0', detail: '' },
      { sequence: 2, state: 'PREPARING', at: 't1', detail: '' },
      { sequence: 3, state: 'RUNNING', at: 't2', detail: '' },
      { sequence: 4, state: 'PARSING', at: 't3', detail: '' },
      { sequence: 5, state: 'VALIDATING', at: 't4', detail: '' },
      { sequence: 6, state: 'COMPLETED', at: 't5', detail: '' },
    ]);
    expect(completed).toBe(100);
  });

  it('labels analytical and native sources distinctly', () => {
    expect(sourceDisplayLabel('analytical model')).toContain('Analytical');
    expect(sourceDisplayLabel('native_solver')).toContain('Native solver');
    expect(sourceDisplayLabel('analytical model')).not.toContain('Native solver');
    expect(sourceDisplayLabel('native_solver')).not.toContain('Analytical');
  });

  it('names every job state for the existing timeline UI', () => {
    expect(formatJobState('QUEUED')).toBeTruthy();
    expect(formatJobState('RUNNING')).toBeTruthy();
    expect(formatJobState('FAILED')).toContain('Failed');
    expect(formatJobState('CANCELLED')).toContain('Cancelled');
    expect(formatJobState('COMPLETED')).toContain('Completed');
  });

  it('summarizes completed scalars without zero-valued invention', () => {
    expect(summarizeResultScalars({})).toEqual([]);
    const rows = summarizeResultScalars({ first_critical_rpm: 9000, note: 'x' });
    expect(rows).toEqual([{ name: 'first_critical_rpm', value: 9000 }]);
  });

  it('describes failure and empty states honestly', () => {
    expect(jobEmptyMessage('api-unreachable')).toContain('API');
    expect(jobEmptyMessage('capability-unavailable')).toContain('unavailable');
    expect(jobEmptyMessage('failed')).toContain('Failed');
    expect(jobEmptyMessage('cancelled')).toContain('Cancelled');
    expect(jobEmptyMessage('completed-invalid')).toContain('invalid');
    expect(jobEmptyMessage('queued')).toBeTruthy();
    expect(jobEmptyMessage('running')).toBeTruthy();
    expect(jobEmptyMessage('completed')).toBeTruthy();
    for (const kind of ['api-unreachable', 'failed', 'cancelled', 'completed-invalid'] as const) {
      expect(jobEmptyMessage(kind)).not.toMatch(/\b0(\.0+)?\b.*(result|engineering)/i);
    }
  });
});
