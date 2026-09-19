'use client';

import { useCallback, useRef, useState } from 'react';
import {
  classifyFieldCollection,
  type FieldInspectionState,
} from '../lib/field-manifest';
import { loadFieldInspectionState } from '../lib/field-client';
import {
  buildFieldRenderPlan,
  fieldProjectionSummary,
  type FieldRenderPlan,
  type FieldViewKind,
} from '../lib/field-projection';
import {
  FIXTURE_BANNER,
  FIXTURE_FIELDS,
  FIXTURE_RESULT_B,
} from '../lib/field-fixtures';
import {
  comparableFromEnvelope,
  compareResults,
  comparisonResolutionNote,
  sourceKindLabel,
  type ComparableResult,
  type EnvelopeLike,
  type ResultComparison,
} from '../lib/result-comparison';
import { shortHash } from './result-inspector';
import { loadFieldViewer } from './lazy-field-viewer';

export const fieldStateBadge = (state: FieldInspectionState): string => {
  switch (state.status) {
    case 'loaded':
      return 'LOADED';
    case 'partial':
      return 'PARTIAL';
    case 'error':
      return 'ERROR';
    default:
      return 'UNAVAILABLE';
  }
};

export const fieldStateTone = (state: FieldInspectionState): 'good' | 'watch' | 'blocked' => {
  if (state.status === 'loaded') return 'good';
  if (state.status === 'partial') return 'watch';
  return 'blocked';
};

export const fieldStateMessage = (state: FieldInspectionState): string => {
  switch (state.status) {
    case 'loaded':
      return 'Provenance-linked field manifest published; bounded derivative available for interactive viewing.';
    case 'partial':
      return `Partial manifest — missing ${state.missing.join(', ')}. Export only until the bounded derivative is published.`;
    case 'error':
      return `Field manifest rejected: ${state.reason}. Nothing is loaded.`;
    default:
      return `No field manifest is published (${state.reason}); nothing is loaded.`;
  }
};

const trustRow = (label: string, value: string, title?: string) => (
  <div key={label}>
    <dt>{label}</dt>
    <dd title={title}>{value}</dd>
  </div>
);

export interface FieldInspectorProps {
  jobId: string;
  envelope?: EnvelopeLike | null;
}

export default function FieldInspector({ jobId, envelope }: FieldInspectorProps) {
  const [inspection, setInspection] = useState<FieldInspectionState | null>(null);
  const [fixtureLabel, setFixtureLabel] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [view, setView] = useState<FieldViewKind | undefined>(undefined);
  const [viewer, setViewer] = useState<'idle' | 'loading' | 'ready' | 'error'>('idle');
  const requestToken = useRef(0);

  const apply = useCallback((state: FieldInspectionState, label: string | null) => {
    setInspection(state);
    setFixtureLabel(label);
    setView(undefined);
    setViewer('idle');
  }, []);

  // Cancel stale requests: a newer inspection invalidates any in-flight read.
  const inspectLive = useCallback(async () => {
    const token = (requestToken.current += 1);
    setBusy(true);
    try {
      const state = await loadFieldInspectionState(jobId);
      if (requestToken.current !== token) return;
      apply(state, null);
    } finally {
      if (requestToken.current === token) setBusy(false);
    }
  }, [apply, jobId]);

  const inspectFixture = useCallback(
    (key: string) => {
      requestToken.current += 1;
      setBusy(false);
      const entry = FIXTURE_FIELDS.find((fixture) => fixture.key === key);
      if (!entry) return;
      apply(classifyFieldCollection(entry.payload), entry.label);
    },
    [apply],
  );

  const plan: FieldRenderPlan | null =
    inspection === null ? null : buildFieldRenderPlan(inspection, view ? { view } : {});
  const manifest = plan?.manifest ?? null;
  const diagnostics = manifest?.diagnostics ?? null;
  const hasDiagnostics =
    diagnostics !== null &&
    Boolean(
      diagnostics.meshQuality ||
      diagnostics.conservation.length > 0 ||
      diagnostics.warnings.length > 0 ||
      diagnostics.residuals.length > 0,
    );

  const activateViewer = useCallback(async () => {
    setViewer('loading');
    try {
      await loadFieldViewer();
      setViewer('ready');
    } catch {
      setViewer('error');
    }
  }, []);

  const comparison: ResultComparison | null =
    envelope && inspection !== null && plan?.manifest
      ? (() => {
          const a: ComparableResult = comparableFromEnvelope(jobId, 'Published native result', envelope, {
            meshSha256: plan.manifest.meshSha256,
            geometrySha256: plan.manifest.geometrySha256,
            artifactSha256: plan.manifest.fullArtifact.sha256,
          });
          return compareResults(a, FIXTURE_RESULT_B);
        })()
      : null;

  return (
    <section aria-label="Native field inspection" className="field-inspection">
      <span className="muted-label">NATIVE FIELD INSPECTION</span>
      {fixtureLabel ? <p className="field-fixture-banner" role="note">{fixtureLabel}</p> : null}
      <div className="field-actions">
        <button type="button" className="chart-action" onClick={() => void inspectLive()} disabled={busy}>
          {busy ? 'Reading published fields…' : 'Inspect published fields'}
        </button>
        <label>
          <span className="muted-label">LABELED FIXTURE</span>
          <select
            aria-label="Load a labeled local fixture"
            value=""
            onChange={(event) => { if (event.target.value) inspectFixture(event.target.value); }}
          >
            <option value="">Select fixture…</option>
            {FIXTURE_FIELDS.map((fixture) => (
              <option key={fixture.key} value={fixture.key}>{fixture.label}</option>
            ))}
          </select>
        </label>
      </div>

      {inspection === null ? (
        <p className="field-note">No field inspected yet. Nothing is loaded until the backend publishes a compact manifest.</p>
      ) : (
        <>
          <div className={`quality-row field-state`}>
            <i className={fieldStateTone(inspection)} />
            <span>
              {fieldStateBadge(inspection)}
              <small>{fieldStateMessage(inspection)}</small>
            </span>
          </div>
          <p className="field-honesty">Displayed data is a projection of backend metadata; it is never a new solver result.</p>

          {plan?.manifest ? (
            <dl className="capability-list field-trust">
              {trustRow('Source', sourceKindLabel('native_solver'))}
              {envelope ? trustRow('Fidelity', envelope.fidelity || 'unspecified') : null}
              {envelope ? trustRow('Solver', `${envelope.solverIdentity} ${envelope.solverVersion}`.trim() || 'unspecified') : null}
              {envelope ? trustRow('Validity', envelope.validity.passed ? `passed${envelope.validity.detail ? ` — ${envelope.validity.detail}` : ''}` : `not passed — ${envelope.validity.detail || 'see quality gates'}`) : null}
              {trustRow('Field / rank / association', `${plan.manifest.fieldName} · ${plan.manifest.rank} · ${plan.manifest.association}`)}
              {trustRow('Units', plan.manifest.units || 'unspecified')}
              {trustRow('Mesh hash', shortHash(plan.manifest.meshSha256), plan.manifest.meshSha256)}
              {trustRow('Full artifact', `${plan.manifest.fullArtifact.format} · sha256 ${shortHash(plan.manifest.fullArtifact.sha256)}`, plan.manifest.fullArtifact.sha256)}
              {trustRow('Display resolution', plan.status === 'ready' ? plan.resolution : 'not renderable')}
              {plan.manifest.range ? trustRow('Range', `${plan.manifest.range.min} … ${plan.manifest.range.max} ${plan.manifest.units}`.trim()) : null}
              {plan.manifest.time ? trustRow('Time / frequency', `${plan.manifest.time.kind} ${plan.manifest.time.index} · ${plan.manifest.time.value} ${plan.manifest.time.unit}`) : null}
              {plan.manifest.regionIds.length > 0 ? trustRow('Semantic regions', plan.manifest.regionIds.join(', ')) : null}
            </dl>
          ) : null}

          {hasDiagnostics && diagnostics ? (
            <div className="field-diagnostics">
              <span className="muted-label">DIAGNOSTICS (backend-reported)</span>
              <dl className="capability-list">
                {diagnostics.meshQuality
                  ? trustRow('Mesh quality', `${diagnostics.meshQuality.name} · ${diagnostics.meshQuality.value} ${diagnostics.meshQuality.unit}`.trim())
                  : null}
                {diagnostics.conservation.map((entry) => trustRow(
                  `Conservation · ${entry.name}`,
                  `${entry.value} ${entry.unit} (${entry.passed ? 'passed' : 'failed'})`,
                ))}
                {diagnostics.residuals.length > 0
                  ? trustRow('Residual samples', diagnostics.residuals.slice(-8).map((value) => value.toExponential(1)).join(', '))
                  : null}
                {diagnostics.warnings.length > 0
                  ? trustRow('Warnings', diagnostics.warnings.join('; '))
                  : null}
              </dl>
            </div>
          ) : null}

          {plan?.status === 'ready' ? (
            <>
              <div className="field-views" role="group" aria-label="Field views">
                {plan.views.map((option) => (
                  <button
                    key={option.kind}
                    type="button"
                    className={plan.view === option.kind ? 'active' : ''}
                    aria-pressed={plan.view === option.kind}
                    title={option.detail}
                    onClick={() => setView(option.kind)}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
              <p className="field-note">{fieldProjectionSummary(plan)}</p>
              <p className="field-lineage">
                Provenance: <b>{plan.renderArtifact?.artifactId}</b> (sha256 {plan.renderArtifact ? shortHash(plan.renderArtifact.sha256) : '—'})
                → full <b>{plan.sourceArtifact?.artifactId}</b> (sha256 {plan.sourceArtifact ? shortHash(plan.sourceArtifact.sha256) : '—'}).
              </p>
              {viewer === 'idle' ? (
                <button type="button" className="chart-action" onClick={() => void activateViewer()}>
                  Load 3D field viewer (lazy)
                </button>
              ) : null}
              {viewer === 'loading' ? <p className="field-note" role="status">Lazy-loading the field renderer…</p> : null}
              {viewer === 'ready' ? <p className="field-note" role="status">Field renderer loaded lazily. No native field bytes are served on this host, so nothing is drawn.</p> : null}
              {viewer === 'error' ? <p className="field-note field-error" role="alert">Field renderer unavailable; metadata remains inspectable.</p> : null}
            </>
          ) : plan ? (
            <p className="field-note field-error" role="alert">Interactive view refused: {plan.reason}.</p>
          ) : null}
        </>
      )}

      {comparison ? <ResultComparisonPanel comparison={comparison} /> : null}
    </section>
  );
}

export interface ResultComparisonPanelProps {
  comparison: ResultComparison;
}

export const ResultComparisonPanel = ({ comparison }: ResultComparisonPanelProps) => (
  <div className="result-comparison" aria-label="Result comparison">
    <span className="muted-label">RESULT A/B COMPARISON</span>
    <p className="field-fixture-banner" role="note">Comparator: local fixture B — {FIXTURE_BANNER}</p>
    <div className="comparison-grid">
      {(['a', 'b'] as const).map((side) => (
        <dl key={side} className="capability-list comparison-side">
          {trustRow('Source', comparison.trust[side].source)}
          {trustRow('Fidelity', comparison.trust[side].fidelity)}
          {trustRow('Solver', comparison.trust[side].solver)}
          {trustRow('Validity', comparison.trust[side].validity)}
          {trustRow('Units', comparison.trust[side].units)}
          {trustRow('Design / mesh', comparison.trust[side].designMeshHash)}
          {trustRow('Resolution', comparison.trust[side].resolution)}
        </dl>
      ))}
    </div>
    <p className="field-note">{comparisonResolutionNote(comparison)}</p>
    <p className="field-lineage">
      Field difference: {comparison.fieldDifference.allowed ? comparison.fieldDifference.mode : 'refused'} — {comparison.fieldDifference.reason}.
    </p>
    <div className="capability-list comparison-qoi">
      {comparison.qois.map((row) => (
        <div key={row.name}>
          <span>{row.name} <small>{row.unit}</small></span>
          <b className={row.status === 'comparable' ? '' : 'danger-text'}>
            {row.status === 'comparable'
              ? `${row.a} → ${row.b} (Δ ${row.delta})`
              : `${row.a ?? '—'} / ${row.b ?? '—'} · ${row.reason}`}
          </b>
        </div>
      ))}
    </div>
  </div>
);
