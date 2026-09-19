// Browser-friendly projection of a native field manifest onto supported views.
//
// This module contains no numerical science: it only decides which bounded,
// provenance-linked visualization derivative the UI may request. Every ready
// plan points at both the full native artifact (authority) and the converted /
// decimated derivative actually rendered.

import {
  fieldResolutionFor,
  fieldTrustLabels,
  isFlowField,
  isStructuralField,
  type FieldBounds,
  type FieldInspectionState,
  type FieldManifest,
  type FieldResolution,
  type FieldTimeSelection,
  type FieldTrustLabels,
  type FieldVector3,
} from './field-manifest';

export type FieldViewKind =
  | 'contour'
  | 'glyphs'
  | 'streamlines'
  | 'wireframe'
  | 'section'
  | 'deformation';

export interface FieldViewOption {
  kind: FieldViewKind;
  label: string;
  detail: string;
}

export interface FieldSectionPlane {
  normal: FieldVector3;
  offset: number;
}

export interface FieldViewOptions {
  view?: FieldViewKind;
  componentIndex?: number;
  deformation?: boolean;
  section?: FieldSectionPlane | null;
  time?: { kind: 'time' | 'frequency'; index: number } | null;
  preferDecimated?: boolean;
}

export interface FieldRenderPlan {
  status: 'ready' | 'refused';
  reason: string;
  view: FieldViewKind | null;
  views: FieldViewOption[];
  resolution: FieldResolution;
  manifest: FieldManifest | null;
  /** Bounded derivative actually rendered; never a raw native array. */
  renderArtifact: FieldManifest['derivatives'][number] | null;
  /** Full native artifact; lineage authority for the derivative. */
  sourceArtifact: FieldManifest['fullArtifact'] | null;
  componentIndex: number | null;
  deformation: boolean;
  section: FieldSectionPlane | null;
  time: FieldTimeSelection | null;
  trust: FieldTrustLabels | null;
}

const REFUSED = (reason: string): FieldRenderPlan => ({
  status: 'refused',
  reason,
  view: null,
  views: [],
  resolution: 'full',
  manifest: null,
  renderArtifact: null,
  sourceArtifact: null,
  componentIndex: null,
  deformation: false,
  section: null,
  time: null,
  trust: null,
});

export const supportedFieldViews = (manifest: FieldManifest): FieldViewOption[] => {
  const views: FieldViewOption[] = [
    { kind: 'wireframe', label: 'Mesh', detail: 'Bounded mesh/wireframe derivative.' },
  ];
  if (manifest.rank === 'scalar') {
    views.unshift({ kind: 'contour', label: 'Contour', detail: 'Scalar contour over the associated entities.' });
  }
  if (manifest.rank === 'vector') {
    views.push({ kind: 'glyphs', label: 'Glyphs', detail: 'Vector glyphs on the bounded derivative.' });
    if (isFlowField(manifest)) {
      views.push({ kind: 'streamlines', label: 'Streamlines', detail: 'Flow streamlines from the bounded derivative.' });
    }
  }
  if (manifest.bounds) {
    views.push({ kind: 'section', label: 'Section', detail: 'Clipping/section plane within the reported bounds.' });
  }
  if (isStructuralField(manifest)) {
    views.push({ kind: 'deformation', label: 'Deformation', detail: 'Displacement overlay for structural fields.' });
  }
  return views;
};

const defaultView = (views: FieldViewOption[]): FieldViewKind | null =>
  views[0]?.kind ?? null;

const resolveTime = (
  manifest: FieldManifest,
  requested: FieldViewOptions['time'],
): { time: FieldTimeSelection | null; reason: string } => {
  if (!requested) return { time: manifest.time, reason: '' };
  if (!manifest.time) return { time: null, reason: 'time-or-frequency-not-supplied' };
  if (requested.kind !== manifest.time.kind) return { time: null, reason: 'time-selection-kind-mismatch' };
  if (requested.index !== manifest.time.index) {
    return { time: null, reason: 'time-index-out-of-range' };
  }
  return { time: manifest.time, reason: '' };
};

/**
 * Build a bounded render plan. Fails closed unless a derivative whose source
 * hash matches the full native artifact is available for the requested view.
 */
export const buildFieldRenderPlan = (
  state: FieldInspectionState,
  options: FieldViewOptions = {},
): FieldRenderPlan => {
  if (state.status === 'unavailable') return REFUSED(state.reason || 'field-unavailable');
  if (state.status === 'error') return REFUSED(state.reason || 'field-manifest-error');
  const manifest = state.manifest;
  const views = supportedFieldViews(manifest);
  const requested = options.view;
  if (requested && !views.some((entry) => entry.kind === requested)) {
    return REFUSED('view-not-supported-for-field');
  }
  const view = requested ?? defaultView(views);
  if (!view) return REFUSED('no-supported-field-view');

  const derivative = manifest.derivatives.find(
    (entry) =>
      entry.sourceSha256 === manifest.artifactSha256 &&
      (options.preferDecimated === false
        ? entry.role === 'visualization-converted'
        : true),
  ) ?? manifest.derivatives.find((entry) => entry.sourceSha256 === manifest.artifactSha256);
  if (!derivative) return REFUSED('no-provenance-linked-visualization-derivative');

  const time = resolveTime(manifest, options.time);
  if (time.reason) return REFUSED(time.reason);

  const componentCount = manifest.components.length;
  let componentIndex: number | null = null;
  if (view === 'contour' || view === 'glyphs' || view === 'streamlines') {
    componentIndex = options.componentIndex ?? 0;
    if (!Number.isInteger(componentIndex) || componentIndex < 0 || componentIndex >= componentCount) {
      return REFUSED('component-index-out-of-range');
    }
  }

  const deformation = options.deformation === true || view === 'deformation';
  if (deformation && !isStructuralField(manifest)) {
    return REFUSED('deformation-overlay-requires-structural-field');
  }

  let section: FieldSectionPlane | null = null;
  if (view === 'section' || options.section) {
    if (!manifest.bounds) return REFUSED('section-plane-requires-bounds');
    const requestedSection = options.section ?? { normal: [1, 0, 0] as FieldVector3, offset: 0 };
    section = requestedSection;
  }

  const resolution = fieldResolutionFor(derivative);
  return {
    status: 'ready',
    reason: '',
    view,
    views,
    resolution,
    manifest,
    renderArtifact: derivative,
    sourceArtifact: manifest.fullArtifact,
    componentIndex,
    deformation,
    section,
    time: time.time,
    trust: fieldTrustLabels(manifest, resolution),
  };
};

export const fieldProjectionSummary = (plan: FieldRenderPlan): string => {
  if (plan.status === 'refused') return `Refused: ${plan.reason}`;
  const parts = [
    plan.manifest?.fieldName ?? 'field',
    plan.view ?? 'view',
    plan.resolution === 'full' ? 'full-resolution' : `${plan.resolution} visualization derivative`,
  ];
  if (plan.time) parts.push(`${plan.time.kind} ${plan.time.index} = ${plan.time.value} ${plan.time.unit}`);
  return parts.join(' · ');
};

export const fieldBoundsForSection = (manifest: FieldManifest): FieldBounds | null => manifest.bounds;
