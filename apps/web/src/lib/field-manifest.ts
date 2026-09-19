// Compact, generic field-manifest projection for the workbench UI.
//
// A manifest is metadata plus provenance links. Giant raw arrays (coordinates,
// connectivity, per-node values) are never part of this control path: any
// inline numeric payload large enough to be field data is rejected so it can
// never masquerade as an inspectable native field.

export const FIELD_MANIFEST_MAX_BYTES = 64 * 1024;
export const MAX_INLINE_NUMERIC_VALUES = 8;
export const MAX_RESIDUAL_SAMPLES = 256;

export type FieldRank = 'scalar' | 'vector' | 'tensor';
export type FieldAssociation = 'point' | 'cell' | 'surface';
export type FieldArtifactRole =
  | 'native-full'
  | 'visualization-converted'
  | 'visualization-decimated';
export type FieldResolution = 'full' | 'converted' | 'decimated';

export interface FieldRange {
  min: number;
  max: number;
  span: number;
}

export interface FieldTimeSelection {
  kind: 'time' | 'frequency';
  index: number;
  value: number;
  unit: string;
}

export type FieldVector3 = readonly [number, number, number];

export interface FieldBounds {
  min: FieldVector3;
  max: FieldVector3;
}

export interface FieldArtifactRef {
  artifactId: string;
  sha256: string;
  bytes: number;
  mime: string;
  format: string;
  role: FieldArtifactRole;
  sourceSha256: string | null;
  decimationRatio: number | null;
}

export interface FieldConservationEntry {
  name: string;
  value: number;
  unit: string;
  passed: boolean;
}

export interface FieldDiagnostics {
  meshQuality: { name: string; value: number; unit: string } | null;
  conservation: FieldConservationEntry[];
  warnings: string[];
  residuals: number[];
}

export interface FieldManifest {
  artifactId: string;
  artifactSha256: string;
  meshSha256: string;
  geometrySha256: string | null;
  fieldName: string;
  rank: FieldRank;
  components: string[];
  units: string;
  association: FieldAssociation;
  time: FieldTimeSelection | null;
  range: FieldRange | null;
  regionIds: string[];
  bounds: FieldBounds | null;
  diagnostics: FieldDiagnostics;
  fullArtifact: FieldArtifactRef;
  derivatives: FieldArtifactRef[];
}

export interface FieldTrustLabels {
  source: 'native_solver';
  artifactId: string;
  artifactSha256: string;
  meshSha256: string;
  geometrySha256: string | null;
  units: string;
  resolution: FieldResolution;
  displayDerivative: boolean;
  provenanceLinked: boolean;
  fieldName: string;
  rank: FieldRank;
  association: FieldAssociation;
}

export type FieldInspectionState =
  | { status: 'unavailable'; reason: string }
  | { status: 'error'; reason: string }
  | { status: 'partial'; manifest: FieldManifest; missing: string[] }
  | { status: 'loaded'; manifest: FieldManifest };

export type FieldParseResult =
  | { ok: true; manifest: FieldManifest }
  | { ok: false; reason: string };

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value);

const asString = (value: unknown): string | null =>
  typeof value === 'string' && value.trim().length > 0 ? value : null;

const asFinite = (value: unknown): number | null =>
  typeof value === 'number' && Number.isFinite(value) ? value : null;

const isSha256 = (value: string): boolean => /^[a-f0-9]{64}$/i.test(value);

const toVector3 = (value: unknown): FieldVector3 | null => {
  if (!Array.isArray(value) || value.length !== 3) return null;
  const tuple = value.map((entry) => (typeof entry === 'number' && Number.isFinite(entry) ? entry : null));
  if (tuple.some((entry) => entry === null)) return null;
  return tuple as unknown as FieldVector3;
};

const parseTime = (raw: unknown): FieldTimeSelection | null | 'invalid' => {
  if (raw === null || raw === undefined) return null;
  if (!isRecord(raw)) return 'invalid';
  if (raw.kind !== 'time' && raw.kind !== 'frequency') return 'invalid';
  const index = asFinite(raw.index);
  const value = asFinite(raw.value);
  const unit = asString(raw.unit);
  if (index === null || value === null || unit === null || !Number.isInteger(index) || index < 0) {
    return 'invalid';
  }
  return { kind: raw.kind, index, value, unit };
};

const parseRange = (raw: unknown): FieldRange | null | 'invalid' => {
  if (raw === null || raw === undefined) return null;
  if (!isRecord(raw)) return 'invalid';
  const min = asFinite(raw.min);
  const max = asFinite(raw.max);
  if (min === null || max === null || max < min) return 'invalid';
  return { min, max, span: max - min };
};

const parseBounds = (raw: unknown): FieldBounds | null | 'invalid' => {
  if (raw === null || raw === undefined) return null;
  if (!isRecord(raw)) return 'invalid';
  const min = toVector3(raw.min);
  const max = toVector3(raw.max);
  if (!min || !max) return 'invalid';
  return { min, max };
};

const EMPTY_DIAGNOSTICS: FieldDiagnostics = {
  meshQuality: null,
  conservation: [],
  warnings: [],
  residuals: [],
};

const parseDiagnostics = (raw: unknown): FieldDiagnostics | string => {
  if (raw === null || raw === undefined) return EMPTY_DIAGNOSTICS;
  if (!isRecord(raw)) return 'invalid-field-diagnostics';
  let meshQuality: FieldDiagnostics['meshQuality'] = null;
  if (raw.mesh_quality !== null && raw.mesh_quality !== undefined) {
    if (!isRecord(raw.mesh_quality)) return 'invalid-field-diagnostics';
    const name = asString(raw.mesh_quality.name);
    const value = asFinite(raw.mesh_quality.value);
    if (!name || value === null) return 'invalid-field-diagnostics';
    meshQuality = { name, value, unit: asString(raw.mesh_quality.unit) ?? '' };
  }
  const conservation: FieldConservationEntry[] = [];
  if (raw.conservation !== null && raw.conservation !== undefined) {
    if (!Array.isArray(raw.conservation)) return 'invalid-field-diagnostics';
    for (const entry of raw.conservation) {
      if (!isRecord(entry)) return 'invalid-field-diagnostics';
      const name = asString(entry.name);
      const value = asFinite(entry.value);
      if (!name || value === null || typeof entry.passed !== 'boolean') return 'invalid-field-diagnostics';
      conservation.push({ name, value, unit: asString(entry.unit) ?? '', passed: entry.passed });
    }
  }
  const warnings = Array.isArray(raw.warnings)
    ? raw.warnings.filter((entry): entry is string => typeof entry === 'string')
    : [];
  if (Array.isArray(raw.warnings) && warnings.length !== raw.warnings.length) return 'invalid-field-diagnostics';
  const residuals = Array.isArray(raw.residuals)
    ? raw.residuals.filter((entry): entry is number => typeof entry === 'number' && Number.isFinite(entry))
    : [];
  if (Array.isArray(raw.residuals) && residuals.length !== raw.residuals.length) return 'invalid-field-diagnostics';
  if (residuals.length > MAX_RESIDUAL_SAMPLES) return 'residual-history-too-large';
  return { meshQuality, conservation, warnings, residuals };
};

const parseArtifactRef = (raw: unknown, role: FieldArtifactRole | null): FieldArtifactRef | null => {
  if (!isRecord(raw)) return null;
  const artifactId = asString(raw.artifact_id);
  const sha256 = asString(raw.sha256);
  if (!artifactId || !sha256 || !isSha256(sha256)) return null;
  const resolvedRole = role ?? (asString(raw.role) as FieldArtifactRole | null);
  if (
    resolvedRole !== 'native-full' &&
    resolvedRole !== 'visualization-converted' &&
    resolvedRole !== 'visualization-decimated'
  ) {
    return null;
  }
  const bytes = asFinite(raw.bytes);
  const sourceSha = asString(raw.source_sha256);
  const ratio = asFinite(raw.decimation_ratio);
  return {
    artifactId,
    sha256,
    bytes: bytes !== null && bytes >= 0 ? bytes : 0,
    mime: asString(raw.mime) ?? 'application/octet-stream',
    format: asString(raw.format) ?? 'unknown',
    role: resolvedRole,
    sourceSha256: sourceSha && isSha256(sourceSha) ? sourceSha : null,
    decimationRatio: ratio !== null && ratio > 0 && ratio <= 1 ? ratio : null,
  };
};

/** Find any inline numeric array that is large enough to be actual field data. */
export const findInlineFieldPayload = (raw: unknown, depth = 0): string | null => {
  if (depth > 6) return null;
  if (Array.isArray(raw)) {
    const numeric = raw.filter((entry) => typeof entry === 'number').length;
    if (numeric > MAX_INLINE_NUMERIC_VALUES) return 'inline-numeric-array';
    for (const entry of raw) {
      const found = findInlineFieldPayload(entry, depth + 1);
      if (found) return found;
    }
    return null;
  }
  if (!isRecord(raw)) return null;
  for (const [key, value] of Object.entries(raw)) {
    if (Array.isArray(value) && /^residuals$/i.test(key)) {
      // Bounded convergence histories are legitimate diagnostics, not field data.
      if (value.filter((entry) => typeof entry === 'number').length > MAX_RESIDUAL_SAMPLES) {
        return 'residual-history-too-large';
      }
      continue;
    }
    if (
      Array.isArray(value) &&
      /^(values?|data|coordinates|points|connectivity|indices|normals)$/i.test(key) &&
      value.some((entry) => typeof entry === 'number')
    ) {
      return `inline-${key}`;
    }
    const found = findInlineFieldPayload(value, depth + 1);
    if (found) return found;
  }
  return null;
};

export const parseFieldManifest = (raw: unknown): FieldParseResult => {
  if (!isRecord(raw)) return { ok: false, reason: 'manifest-not-an-object' };
  const serialized = (() => {
    try {
      return JSON.stringify(raw);
    } catch {
      return null;
    }
  })();
  if (serialized === null) return { ok: false, reason: 'manifest-not-serializable' };
  if (serialized.length > FIELD_MANIFEST_MAX_BYTES) {
    return { ok: false, reason: 'manifest-too-large-for-control-path' };
  }
  const inline = findInlineFieldPayload(raw);
  if (inline) return { ok: false, reason: inline };

  const artifactId = asString(raw.artifact_id);
  const artifactSha256 = asString(raw.artifact_sha256);
  const meshSha256 = asString(raw.mesh_sha256);
  const fieldName = asString(raw.field_name);
  const rank = raw.rank;
  const association = raw.association;
  const units = asString(raw.units);
  if (!artifactId || !fieldName) return { ok: false, reason: 'missing-field-identity' };
  if (!artifactSha256 || !isSha256(artifactSha256)) return { ok: false, reason: 'missing-artifact-hash' };
  if (!meshSha256 || !isSha256(meshSha256)) return { ok: false, reason: 'missing-mesh-hash' };
  if (rank !== 'scalar' && rank !== 'vector' && rank !== 'tensor') {
    return { ok: false, reason: 'unknown-field-rank' };
  }
  if (association !== 'point' && association !== 'cell' && association !== 'surface') {
    return { ok: false, reason: 'unknown-field-association' };
  }
  if (!Array.isArray(raw.components) || raw.components.length === 0) {
    return { ok: false, reason: 'missing-field-components' };
  }
  const components = raw.components.filter((entry): entry is string => typeof entry === 'string' && entry.length > 0);
  if (components.length !== raw.components.length) return { ok: false, reason: 'invalid-field-components' };

  const geometryRaw = raw.geometry_sha256;
  const geometrySha256 = geometryRaw === null || geometryRaw === undefined ? null : asString(geometryRaw);
  if (geometryRaw !== null && geometryRaw !== undefined && (!geometrySha256 || !isSha256(geometrySha256))) {
    return { ok: false, reason: 'invalid-geometry-hash' };
  }

  const time = parseTime(raw.time);
  if (time === 'invalid') return { ok: false, reason: 'invalid-time-selection' };
  const range = parseRange(raw.range);
  if (range === 'invalid') return { ok: false, reason: 'invalid-field-range' };
  const bounds = parseBounds(raw.bounds);
  if (bounds === 'invalid') return { ok: false, reason: 'invalid-field-bounds' };
  const diagnostics = parseDiagnostics(raw.diagnostics);
  if (typeof diagnostics === 'string') return { ok: false, reason: diagnostics };

  const fullArtifact = parseArtifactRef(raw.full_artifact, 'native-full');
  if (!fullArtifact) return { ok: false, reason: 'missing-full-artifact' };

  const derivatives: FieldArtifactRef[] = [];
  if (raw.derivatives !== undefined && raw.derivatives !== null) {
    if (!Array.isArray(raw.derivatives)) return { ok: false, reason: 'invalid-derivatives' };
    for (const entry of raw.derivatives) {
      const ref = parseArtifactRef(entry, null);
      if (!ref || ref.role === 'native-full') return { ok: false, reason: 'invalid-derivative' };
      derivatives.push(ref);
    }
  }

  const regionIds = Array.isArray(raw.region_ids)
    ? raw.region_ids.filter((entry): entry is string => typeof entry === 'string' && entry.length > 0)
    : [];
  if (Array.isArray(raw.region_ids) && regionIds.length !== raw.region_ids.length) {
    return { ok: false, reason: 'invalid-region-ids' };
  }

  return {
    ok: true,
    manifest: {
      artifactId,
      artifactSha256,
      meshSha256,
      geometrySha256,
      fieldName,
      rank,
      components,
      units: units ?? '',
      association,
      time,
      range,
      regionIds,
      bounds,
      diagnostics,
      fullArtifact,
      derivatives,
    },
  };
};

export const expectedComponentCounts = (rank: FieldRank): readonly number[] =>
  rank === 'scalar' ? [1] : rank === 'vector' ? [2, 3] : [4, 6, 9];

const derivativeProvenanceViolation = (manifest: FieldManifest): boolean =>
  manifest.derivatives.some(
    (derivative) => derivative.sourceSha256 !== manifest.artifactSha256,
  );

/**
 * Classify one manifest honestly. Missing provenance or missing visualization
 * derivative downgrades to partial; a derivative that points at a different
 * source than its parent is a provenance violation and fails closed.
 */
export const classifyFieldManifest = (raw: unknown): FieldInspectionState => {
  const parsed = parseFieldManifest(raw);
  if (!parsed.ok) {
    if (parsed.reason.includes('inline')) return { status: 'error', reason: parsed.reason };
    return { status: 'error', reason: parsed.reason };
  }
  const manifest = parsed.manifest;
  if (derivativeProvenanceViolation(manifest)) {
    return { status: 'error', reason: 'derivative-provenance-mismatch' };
  }
  const missing: string[] = [];
  if (!manifest.range) missing.push('range');
  if (manifest.regionIds.length === 0) missing.push('semantic-regions');
  if (!expectedComponentCounts(manifest.rank).includes(manifest.components.length)) {
    missing.push('components');
  }
  if (manifest.derivatives.length === 0) missing.push('visualization-derivative');
  if (missing.length === 0) return { status: 'loaded', manifest };
  return { status: 'partial', manifest, missing };
};

export const classifyFieldCollection = (raw: unknown): FieldInspectionState => {
  if (raw === null || raw === undefined) {
    return { status: 'unavailable', reason: 'no-field-manifests-published' };
  }
  if (isRecord(raw) && !Array.isArray(raw.fields) && typeof raw.artifact_id === 'string') {
    return classifyFieldManifest(raw);
  }
  const list = Array.isArray(raw)
    ? raw
    : isRecord(raw) && Array.isArray(raw.fields)
      ? raw.fields
      : null;
  if (!list) return { status: 'error', reason: 'field-manifest-not-a-list' };
  if (list.length === 0) return { status: 'unavailable', reason: 'no-field-manifests-published' };
  return classifyFieldManifest(list[0]);
};

export const pickVisualizationDerivative = (
  manifest: FieldManifest,
  preferDecimated = true,
): FieldArtifactRef | null => {
  const usable = manifest.derivatives.filter(
    (derivative) => derivative.sourceSha256 === manifest.artifactSha256,
  );
  if (usable.length === 0) return null;
  const decimated = usable.filter((entry) => entry.role === 'visualization-decimated');
  const converted = usable.filter((entry) => entry.role === 'visualization-converted');
  const ordered = preferDecimated ? [...decimated, ...converted] : [...converted, ...decimated];
  return ordered[0] ?? null;
};

export const fieldResolutionFor = (ref: FieldArtifactRef | null): FieldResolution => {
  if (!ref) return 'full';
  if (ref.role === 'visualization-decimated' || (ref.decimationRatio !== null && ref.decimationRatio < 1)) {
    return 'decimated';
  }
  if (ref.role === 'visualization-converted') return 'converted';
  return 'full';
};

export const fieldTrustLabels = (
  manifest: FieldManifest,
  resolution: FieldResolution,
): FieldTrustLabels => ({
  source: 'native_solver',
  artifactId: manifest.artifactId,
  artifactSha256: manifest.artifactSha256,
  meshSha256: manifest.meshSha256,
  geometrySha256: manifest.geometrySha256,
  units: manifest.units,
  resolution,
  displayDerivative: resolution !== 'full',
  provenanceLinked: true,
  fieldName: manifest.fieldName,
  rank: manifest.rank,
  association: manifest.association,
});

export const isStructuralField = (manifest: FieldManifest): boolean => {
  if (manifest.rank !== 'vector') return false;
  if (/disp|deform|deflection/i.test(manifest.fieldName)) return true;
  const names = new Set(manifest.components.map((entry) => entry.toLowerCase()));
  return names.has('u') && names.has('v') && names.has('w');
};

export const isFlowField = (manifest: FieldManifest): boolean =>
  manifest.rank === 'vector' && /veloc|flow|flux/i.test(manifest.fieldName);
