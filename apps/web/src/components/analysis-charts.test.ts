import { describe, expect, it } from 'vitest';
import { canInitializeChart } from './analysis-charts';

describe('analysis chart activation policy', () => {
  it('requires explicit activation, viewport visibility, and a laid-out target', () => {
    expect(canInitializeChart(false, true, 500, 135)).toBe(false);
    expect(canInitializeChart(true, false, 500, 135)).toBe(false);
    expect(canInitializeChart(true, true, 0, 135)).toBe(false);
    expect(canInitializeChart(true, true, 500, 0)).toBe(false);
    expect(canInitializeChart(true, true, 500, 135)).toBe(true);
  });
});
