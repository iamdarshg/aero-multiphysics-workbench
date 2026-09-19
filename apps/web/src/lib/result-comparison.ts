// Provenance- and unit-aware comparison of two result candidates.
//
// Comparison is a pure projection over already-published receipts. Nothing is
// recomputed and no analytical result is ever relabelled as native (or vice
// versa). Scalar differences are only produced for comparable QoIs, and field
// difference is refused unless mesh/interface/unit provenance allows it.

export type ComparisonSourceKind = 'analytical' | 'benchmark' | 'native_solver' | 'unknown';

export interface ComparableValidity {
  passed: boolean;
  detail: string;
}

export interface ComparableResult {
  jobId: string;
  label: string;
  source: ComparisonSourceKind;
  fidelity: string;
  solverIdentity: string;
  solverVersion: string;
  validity: ComparableValidity | null;
  units: Record<string, string>;
  scalars: Record<string, number>;
  meshSha256: string | null;
  geometrySha256: string | null;
  artifactSha256: string | null;
  provenanceId: string | null;
  interfaceNames: string[];
  /** True when the numbers shown are a visualization derivative, not the native field. */
  derivedVisualization?: boolean;
}

export type QoIComparability =
  | 'comparable'
  | 'unit-mismatch'
  | 'missing'
  | 'not-comparable';

export interface QoIComparison {
  name: string;
  a: number | null;
  b: number | null;
  delta: number | null;
  unit: string;
  status: QoIComparability;
  reason: string;
}

export type FieldDifferenceMode = 'direct' | 'mapping-required' | 'refused';

export interface FieldDifferenceDecision {
  allowed: boolean;
  mode: FieldDifferenceMode;
  reason: string;
}

export interface ResultTrustLabels {
  source: string;
  fidelity: string;
  solver: string;
  units: string;
  validity: string;
  designMeshHash: string;
  resolution: string;
}

export interface ResultComparison {
  comparable: boolean;
  reason: string;
  trust: { a: ResultTrustLabels; b: ResultTrustLabels };
  refusals: string[];
  qois: QoIComparison[];
  fieldDifference: FieldDifferenceDecision;
}

export const sourceKindLabel = (source: ComparisonSourceKind): string => {
  if (source === 'native_solver') return 'Native solver · evidence-gated';
  if (source === 'analytical') return 'Analytical model · sample only';
  if (source === 'benchmark') return 'Benchmark reference · not this design';
  return 'Unclassified source';
};

export const normalizeUnit = (unit: string | undefined | null): string =>
  (unit ?? '').trim().toLowerCase().replace(/\s+/g, '').replace(/·/g, '*');

export const validityClass = (validity: ComparableValidity | null): 'passed' | 'failed' | 'unknown' => {
  if (!validity) return 'unknown';
  return validity.passed ? 'passed' : 'failed';
};

const trustLabelsFor = (result: ComparableResult): ResultTrustLabels => ({
  source: sourceKindLabel(result.source),
  fidelity: result.fidelity || 'unspecified',
  solver: [result.solverIdentity, result.solverVersion].filter(Boolean).join(' ') || 'unspecified',
  units: Object.values(result.units).map(normalizeUnit).filter(Boolean).join(', ') || 'units unspecified',
  validity: result.validity
    ? `${result.validity.passed ? 'passed' : 'not passed'}${result.validity.detail ? ` — ${result.validity.detail}` : ''}`
    : 'validity not reported',
  designMeshHash: result.meshSha256 ? `mesh ${result.meshSha256.slice(0, 12)}` : 'mesh hash missing',
  resolution: result.derivedVisualization ? 'visualization derivative (decimated/derived)' : 'full native artifact',
});

const comparableQoIs = (a: ComparableResult, b: ComparableResult): QoIComparison[] => {
  const names = [...new Set([...Object.keys(a.scalars), ...Object.keys(b.scalars)])].sort();
  const sameEvidenceClass = a.source === b.source;
  const sameValidity = validityClass(a.validity) === validityClass(b.validity);
  const rows: QoIComparison[] = [];
  for (const name of names) {
    const unitA = a.units[name];
    const unitB = b.units[name];
    const valueA = typeof a.scalars[name] === 'number' && Number.isFinite(a.scalars[name]) ? a.scalars[name] : null;
    const valueB = typeof b.scalars[name] === 'number' && Number.isFinite(b.scalars[name]) ? b.scalars[name] : null;
    if (valueA === null || valueB === null) {
      rows.push({ name, a: valueA, b: valueB, delta: null, unit: unitA ?? unitB ?? '', status: 'missing', reason: 'QoI missing on one side' });
      continue;
    }
    if (!sameEvidenceClass) {
      rows.push({ name, a: valueA, b: valueB, delta: null, unit: unitA ?? '', status: 'not-comparable', reason: 'mixed evidence classes are never subtracted' });
      continue;
    }
    if (!sameValidity) {
      rows.push({ name, a: valueA, b: valueB, delta: null, unit: unitA ?? '', status: 'not-comparable', reason: 'validity classes differ' });
      continue;
    }
    const normalizedA = normalizeUnit(unitA);
    const normalizedB = normalizeUnit(unitB);
    if (!normalizedA || !normalizedB || normalizedA !== normalizedB) {
      rows.push({ name, a: valueA, b: valueB, delta: null, unit: unitA ?? unitB ?? '', status: 'unit-mismatch', reason: 'units differ; difference withheld' });
      continue;
    }
    rows.push({ name, a: valueA, b: valueB, delta: valueB - valueA, unit: unitA ?? '', status: 'comparable', reason: '' });
  }
  return rows;
};

const decideFieldDifference = (a: ComparableResult, b: ComparableResult): FieldDifferenceDecision => {
  if (a.source !== 'native_solver' || b.source !== 'native_solver') {
    return { allowed: false, mode: 'refused', reason: 'field difference requires two native solver results' };
  }
  if (validityClass(a.validity) !== 'passed' || validityClass(b.validity) !== 'passed') {
    return { allowed: false, mode: 'refused', reason: 'field difference requires valid results on both sides' };
  }
  if (!a.artifactSha256 || !b.artifactSha256) {
    return { allowed: false, mode: 'refused', reason: 'artifact hashes missing; lineage cannot be verified' };
  }
  if (a.geometrySha256 && b.geometrySha256 && a.geometrySha256 !== b.geometrySha256) {
    return { allowed: false, mode: 'refused', reason: 'geometry hashes differ' };
  }
  if (!a.meshSha256 || !b.meshSha256) {
    return { allowed: false, mode: 'refused', reason: 'mesh hashes missing; mapping cannot be validated' };
  }
  if (a.meshSha256 === b.meshSha256) {
    return { allowed: true, mode: 'direct', reason: 'identical mesh hash; node-wise difference is valid' };
  }
  const sharedInterfaces = a.interfaceNames.filter((name) => b.interfaceNames.includes(name));
  if (sharedInterfaces.length > 0) {
    return {
      allowed: true,
      mode: 'mapping-required',
      reason: `non-conforming meshes; explicit mapping required over shared interface(s): ${sharedInterfaces.join(', ')}`,
    };
  }
  return { allowed: false, mode: 'refused', reason: 'non-conforming meshes with no shared interface; subtraction is invalid' };
};

export interface EnvelopeLike {
  source: string;
  fidelity: string;
  solverIdentity: string;
  solverVersion: string;
  runId: string;
  provenanceId: string;
  inputHash: string;
  validity: { passed: boolean; detail: string };
  scalars: Record<string, number>;
  units: Record<string, string>;
}

export const comparableFromEnvelope = (
  jobId: string,
  label: string,
  envelope: EnvelopeLike,
  lineage: Partial<Pick<ComparableResult, 'meshSha256' | 'geometrySha256' | 'artifactSha256' | 'interfaceNames' | 'derivedVisualization'>> = {},
): ComparableResult => ({
  jobId,
  label,
  source:
    envelope.source === 'native_solver'
      ? 'native_solver'
      : envelope.source === 'analytical model' || envelope.source === 'analytical'
        ? 'analytical'
        : 'unknown',
  fidelity: envelope.fidelity,
  solverIdentity: envelope.solverIdentity,
  solverVersion: envelope.solverVersion,
  validity: { passed: envelope.validity.passed, detail: envelope.validity.detail },
  units: { ...envelope.units },
  scalars: { ...envelope.scalars },
  meshSha256: lineage.meshSha256 ?? null,
  geometrySha256: lineage.geometrySha256 ?? null,
  artifactSha256: lineage.artifactSha256 ?? null,
  provenanceId: envelope.provenanceId,
  interfaceNames: lineage.interfaceNames ?? [],
  derivedVisualization: lineage.derivedVisualization ?? false,
});

export const compareResults = (a: ComparableResult, b: ComparableResult): ResultComparison => {
  const refusals: string[] = [];
  if (a.source === 'unknown' || b.source === 'unknown') {
    refusals.push('unclassified source; comparison withheld');
  }
  const fieldDifference = decideFieldDifference(a, b);
  if (!fieldDifference.allowed) refusals.push(fieldDifference.reason);
  return {
    comparable: refusals.length === 0,
    reason: refusals[0] ?? 'comparable within reported units and provenance',
    trust: { a: trustLabelsFor(a), b: trustLabelsFor(b) },
    refusals,
    qois: comparableQoIs(a, b),
    fieldDifference,
  };
};

export const comparisonResolutionNote = (comparison: ResultComparison): string => {
  if (!comparison.comparable) return `Not comparable: ${comparison.reason}`;
  if (comparison.fieldDifference.mode === 'mapping-required') return comparison.fieldDifference.reason;
  return 'Direct comparison; both sides share units, validity class, and evidence source.';
};
