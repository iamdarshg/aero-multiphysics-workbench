import { describe, expect, it } from 'vitest';
import { getDemoProfile, getDockPanel, getViewModeStatus, qualityGateEvidence, updateCouplingStrength } from './workbench-state';

describe('workbench demo profiles', () => {
  it('uses serious engineering coupling by default for the EDF profile', () => {
    expect(getDemoProfile('edf').couplingStrength).toBe(0.9);
  });

  it('keeps coupling strength in the available 0–1 range', () => {
    expect(updateCouplingStrength(0.9, 1.8)).toBe(1);
    expect(updateCouplingStrength(0.9, -0.2)).toBe(0);
  });

  it('labels demonstration values as analytical sample data', () => {
    const profile = getDemoProfile('gas-turbine');
    expect(profile.evidenceLabel).toBe('Analytical sample state — not a native solver run');
    expect(profile.evidence.source).toBe('analytical model');
    expect(profile.evidence.fidelity).toBe('analytical');
    expect(profile.evidence.nativeExecution).toBe('not performed');
    expect(profile.evidence.validity).toBe('demonstration only');
  });

  it('fails closed when field assets or native analyses are unavailable', () => {
    expect(getViewModeStatus('fields').available).toBe(false);
    expect(getViewModeStatus('fields').detail).toContain('No field asset');
    expect(getDockPanel('energy').source).toBe('Analytical model');
    expect(getDockPanel('energy').fidelity).toBe('analytical');
    expect(getDockPanel('energy').validity).toBe('sample state only');
    expect(getDockPanel('logs').source).toBe('Capability registry');
  });

  it('keeps quality-gate evidence labels explicit', () => {
    expect(qualityGateEvidence.energy).toBe('Analytical · screening/sample only');
    expect(qualityGateEvidence.resonance).toBe('Analytical · screening/sample only');
    expect(qualityGateEvidence.native).toBe('Declarative capability state');
  });
});
