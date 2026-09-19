import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  FIELD_MANIFEST_MAX_BYTES,
  MAX_RESIDUAL_SAMPLES,
  classifyFieldCollection,
  findInlineFieldPayload,
  parseFieldManifest,
  pickVisualizationDerivative,
} from './field-manifest';
import { buildFieldRenderPlan, supportedFieldViews } from './field-projection';
import {
  FIXTURE_BROKEN_PROVENANCE_FIELD,
  FIXTURE_FLOW_VECTOR_FIELD,
  FIXTURE_GIANT_INLINE_FIELD,
  FIXTURE_PARTIAL_FIELD,
  FIXTURE_RESULT_A,
  FIXTURE_RESULT_ANALYTICAL,
  FIXTURE_RESULT_B,
  FIXTURE_SCALAR_FIELD,
  FIXTURE_VECTOR_DEFORMATION_FIELD,
} from './field-fixtures';
import { compareResults, normalizeUnit, validityClass } from './result-comparison';
import { loadFieldInspectionState } from './field-client';
import { fieldStateBadge, fieldStateMessage, fieldStateTone } from '../components/field-inspector';

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('compact field manifest', () => {
  it('classifies a scalar field render manifest as loaded with provenance links', () => {
    const state = classifyFieldCollection(FIXTURE_SCALAR_FIELD);
    expect(state.status).toBe('loaded');
    if (state.status !== 'loaded') return;
    expect(state.manifest.rank).toBe('scalar');
    expect(state.manifest.association).toBe('surface');
    expect(state.manifest.components).toEqual(['pressure']);
    expect(state.manifest.units).toBe('Pa');
    expect(state.manifest.regionIds).toEqual(['duct-wall', 'rotor-face']);
    const derivative = pickVisualizationDerivative(state.manifest);
    expect(derivative?.sourceSha256).toBe(state.manifest.artifactSha256);
  });

  it('keeps vector and deformation metadata for structural fields', () => {
    const state = classifyFieldCollection(FIXTURE_VECTOR_DEFORMATION_FIELD);
    expect(state.status).toBe('loaded');
    if (state.status !== 'loaded') return;
    expect(state.manifest.rank).toBe('vector');
    expect(state.manifest.components).toEqual(['u', 'v', 'w']);
    const views = supportedFieldViews(state.manifest).map((view) => view.kind);
    expect(views).toContain('glyphs');
    expect(views).toContain('deformation');
    const plan = buildFieldRenderPlan(state, { view: 'deformation' });
    expect(plan.status).toBe('ready');
    expect(plan.deformation).toBe(true);
  });

  it('decimated artifact retains the full native artifact source hash', () => {
    const state = classifyFieldCollection(FIXTURE_SCALAR_FIELD);
    const plan = buildFieldRenderPlan(state, { view: 'contour' });
    expect(plan.status).toBe('ready');
    expect(plan.resolution).toBe('decimated');
    expect(plan.renderArtifact?.sourceSha256).toBe(plan.manifest?.artifactSha256);
    expect(plan.renderArtifact?.artifactId).not.toBe(plan.sourceArtifact?.artifactId);
    expect(plan.trust?.resolution).toBe('decimated');
    expect(plan.trust?.displayDerivative).toBe(true);
  });

  it('does not offer or apply deformation to a non-structural field', () => {
    const state = classifyFieldCollection(FIXTURE_FLOW_VECTOR_FIELD);
    expect(state.status).toBe('loaded');
    if (state.status !== 'loaded') return;
    const views = supportedFieldViews(state.manifest).map((view) => view.kind);
    expect(views).not.toContain('deformation');
    const plan = buildFieldRenderPlan(state, { deformation: true });
    expect(plan.status).toBe('refused');
    expect(plan.reason).toBe('deformation-overlay-requires-structural-field');
  });

  it('refuses a view that the field does not support instead of substituting', () => {
    const state = classifyFieldCollection(FIXTURE_FLOW_VECTOR_FIELD);
    const plan = buildFieldRenderPlan(state, { view: 'contour' });
    expect(plan.status).toBe('refused');
    expect(plan.reason).toBe('view-not-supported-for-field');
  });
});

describe('honest field states', () => {
  it('reports partial manifests without masquerading as loaded', () => {
    const state = classifyFieldCollection(FIXTURE_PARTIAL_FIELD);
    expect(state.status).toBe('partial');
    if (state.status !== 'partial') return;
    expect(state.missing).toContain('visualization-derivative');
    const plan = buildFieldRenderPlan(state);
    expect(plan.status).toBe('refused');
    expect(plan.reason).toBe('no-provenance-linked-visualization-derivative');
    expect(fieldStateBadge(state)).toBe('PARTIAL');
    expect(fieldStateTone(state)).toBe('watch');
    expect(fieldStateMessage(state)).toContain('Export only');
  });

  it('fails closed on a derivative with mismatched provenance', () => {
    const state = classifyFieldCollection(FIXTURE_BROKEN_PROVENANCE_FIELD);
    expect(state.status).toBe('error');
    if (state.status !== 'error') return;
    expect(state.reason).toBe('derivative-provenance-mismatch');
    expect(fieldStateTone(state)).toBe('blocked');
  });

  it('reports an absent field endpoint as unavailable', () => {
    const state = classifyFieldCollection(null);
    expect(state.status).toBe('unavailable');
    expect(fieldStateBadge(state)).toBe('UNAVAILABLE');
    expect(fieldStateMessage(state)).not.toContain('loaded;');
  });

  it('marks parse failures as errors, never loaded', () => {
    const state = classifyFieldCollection({ artifact_id: 'x', rank: 'scalar' });
    expect(state.status).toBe('error');
    expect(fieldStateBadge(state)).toBe('ERROR');
  });
});

describe('bounded control path', () => {
  it('rejects a large inline numeric array (giant API JSON)', () => {
    const payload = { ...FIXTURE_SCALAR_FIELD, coordinates: Array.from({ length: 64 }, (_, index) => index) };
    expect(findInlineFieldPayload(payload)).toBe('inline-coordinates');
    const parsed = parseFieldManifest(payload);
    expect(parsed.ok).toBe(false);
  });

  it('rejects an oversized manifest before it enters the control path', () => {
    const parsed = parseFieldManifest(FIXTURE_GIANT_INLINE_FIELD);
    expect(parsed.ok).toBe(false);
    const serialized = JSON.stringify(FIXTURE_GIANT_INLINE_FIELD);
    expect(serialized.length).toBeGreaterThan(FIELD_MANIFEST_MAX_BYTES);
  });

  it('never emits raw arrays in the render plan', () => {
    const state = classifyFieldCollection(FIXTURE_SCALAR_FIELD);
    const plan = buildFieldRenderPlan(state);
    const serialized = JSON.stringify(plan);
    expect(serialized).not.toMatch(/\bvalues\b/);
    expect(serialized.length).toBeLessThan(FIELD_MANIFEST_MAX_BYTES);
  });

  it('requests the compact /fields endpoint and fails closed on 404', async () => {
    const calls: string[] = [];
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      calls.push(String(input));
      return new Response(JSON.stringify({ detail: { code: 'RESULT_FIELDS_UNAVAILABLE' } }), {
        status: 404,
        headers: { 'content-type': 'application/json' },
      });
    }));
    const state = await loadFieldInspectionState('job-123');
    expect(calls[0]).toContain('/v1/native/results/job-123/fields');
    expect(state.status).toBe('unavailable');
  });
});

describe('time/frequency selection and diagnostics', () => {
  it('applies a supplied time selection and refuses mismatches', () => {
    const scalar = classifyFieldCollection(FIXTURE_SCALAR_FIELD);
    const ok = buildFieldRenderPlan(scalar, { view: 'contour', time: { kind: 'time', index: 0 } });
    expect(ok.status).toBe('ready');
    expect(ok.time?.index).toBe(0);

    const wrongKind = buildFieldRenderPlan(scalar, { time: { kind: 'frequency', index: 0 } });
    expect(wrongKind.status).toBe('refused');
    expect(wrongKind.reason).toBe('time-selection-kind-mismatch');

    const wrongIndex = buildFieldRenderPlan(scalar, { time: { kind: 'time', index: 3 } });
    expect(wrongIndex.reason).toBe('time-index-out-of-range');

    const none = buildFieldRenderPlan(classifyFieldCollection(FIXTURE_VECTOR_DEFORMATION_FIELD), {
      time: { kind: 'time', index: 0 },
    });
    expect(none.reason).toBe('time-or-frequency-not-supplied');
  });

  it('carries bounded diagnostics and rejects an unbounded residual history', () => {
    const state = classifyFieldCollection(FIXTURE_SCALAR_FIELD);
    expect(state.status).toBe('loaded');
    if (state.status !== 'loaded') return;
    expect(state.manifest.diagnostics.meshQuality?.name).toBe('min-non-orthogonality');
    expect(state.manifest.diagnostics.conservation[0]?.passed).toBe(true);
    expect(state.manifest.diagnostics.residuals.length).toBeGreaterThan(0);

    const oversized = {
      ...FIXTURE_SCALAR_FIELD,
      diagnostics: { residuals: Array.from({ length: MAX_RESIDUAL_SAMPLES + 1 }, () => 1) },
    };
    const parsed = parseFieldManifest(oversized);
    expect(parsed.ok).toBe(false);
    if (!parsed.ok) expect(parsed.reason).toBe('residual-history-too-large');
  });
});

describe('trustworthy result comparison', () => {
  it('computes deltas only for comparable QoIs (matching units and evidence)', () => {
    const comparison = compareResults(FIXTURE_RESULT_A, FIXTURE_RESULT_B);
    const drop = comparison.qois.find((row) => row.name === 'pressure_drop');
    expect(drop?.status).toBe('comparable');
    expect(drop?.delta).toBeCloseTo(-45.0);
    expect(comparison.fieldDifference.mode).toBe('direct');
    expect(comparison.comparable).toBe(true);
  });

  it('blocks a scalar difference on unit mismatch and withholds the delta', () => {
    const mismatched = { ...FIXTURE_RESULT_B, units: { ...FIXTURE_RESULT_B.units, pressure_drop: 'kPa' } };
    const comparison = compareResults(FIXTURE_RESULT_A, mismatched);
    const drop = comparison.qois.find((row) => row.name === 'pressure_drop');
    expect(drop?.status).toBe('unit-mismatch');
    expect(drop?.delta).toBeNull();
    expect(normalizeUnit('m / s')).toBe('m/s');
  });

  it('requires mapping or refuses when meshes are incompatible', () => {
    const mapped = {
      ...FIXTURE_RESULT_B,
      meshSha256: '9'.repeat(64),
      interfaceNames: ['fsi-0'],
    };
    const mapping = compareResults(FIXTURE_RESULT_A, mapped);
    expect(mapping.fieldDifference.allowed).toBe(true);
    expect(mapping.fieldDifference.mode).toBe('mapping-required');

    const noInterface = compareResults(FIXTURE_RESULT_A, { ...mapped, interfaceNames: [] });
    expect(noInterface.fieldDifference.allowed).toBe(false);
    expect(noInterface.fieldDifference.mode).toBe('refused');
    expect(noInterface.refusals).toContain('non-conforming meshes with no shared interface; subtraction is invalid');
  });

  it('never relabels analytical as native and never subtracts across classes', () => {
    const comparison = compareResults(FIXTURE_RESULT_A, FIXTURE_RESULT_ANALYTICAL);
    expect(comparison.trust.a.source).toContain('Native solver');
    expect(comparison.trust.b.source).toContain('Analytical model');
    expect(comparison.qois.every((row) => row.status === 'not-comparable')).toBe(true);
    expect(comparison.qois.every((row) => row.delta === null)).toBe(true);
    expect(comparison.fieldDifference.allowed).toBe(false);
  });

  it('refuses comparison across incompatible validity', () => {
    const invalid = {
      ...FIXTURE_RESULT_B,
      validity: { passed: false, detail: 'quality gate failed' },
    };
    const comparison = compareResults(FIXTURE_RESULT_A, invalid);
    expect(validityClass(FIXTURE_RESULT_A.validity)).toBe('passed');
    expect(validityClass(invalid.validity)).toBe('failed');
    expect(comparison.qois.every((row) => row.delta === null)).toBe(true);
    expect(comparison.fieldDifference.allowed).toBe(false);
  });
});
