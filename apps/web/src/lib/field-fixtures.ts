// LOCAL FIXTURES — not native solver output.
//
// No native field artifact exists on this host. These manifests exercise the
// typed contract and the honest-state/refusal paths only. Every consumer must
// keep the fixture banner visible; a fixture can never be presented as a
// native solver result.

import type { ComparableResult } from './result-comparison';

/** Deterministic 64-char lowercase-hex digest for fixture lineage only. */
const h = (seed: string): string => seed.repeat(64).slice(0, 64);

export const FIXTURE_BANNER = 'LOCAL FIXTURE — not a native solver result';

export const FIXTURE_SCALAR_FIELD = {
  artifact_id: 'fixture-pressure-surface',
  artifact_sha256: h('a'),
  mesh_sha256: h('b'),
  geometry_sha256: h('c'),
  field_name: 'pressure',
  rank: 'scalar',
  components: ['pressure'],
  units: 'Pa',
  association: 'surface',
  time: { kind: 'time', index: 0, value: 0.5, unit: 's' },
  range: { min: 98000.0, max: 118500.0 },
  region_ids: ['duct-wall', 'rotor-face'],
  bounds: { min: [-0.05, -0.05, 0], max: [0.05, 0.05, 0.09] },
  diagnostics: {
    mesh_quality: { name: 'min-non-orthogonality', value: 28.4, unit: 'deg' },
    conservation: [{ name: 'mass-balance', value: 1.2e-4, unit: '-', passed: true }],
    warnings: ['fixture warning: leading-edge curvature sample'],
    residuals: [1.8e-1, 6.4e-2, 2.1e-2, 8.0e-3, 2.9e-3, 1.8e-3],
  },
  full_artifact: {
    artifact_id: 'fixture-pressure-surface-vtu',
    sha256: h('a'),
    bytes: 24000000,
    mime: 'application/octet-stream',
    format: 'vtu',
  },
  derivatives: [
    {
      artifact_id: 'fixture-pressure-surface-glb',
      sha256: h('d'),
      bytes: 480000,
      mime: 'model/gltf-binary',
      format: 'glb',
      role: 'visualization-decimated',
      source_sha256: h('a'),
      decimation_ratio: 0.05,
    },
  ],
};

export const FIXTURE_VECTOR_DEFORMATION_FIELD = {
  artifact_id: 'fixture-displacement-solid',
  artifact_sha256: h('e'),
  mesh_sha256: h('f'),
  geometry_sha256: h('1'),
  field_name: 'displacement',
  rank: 'vector',
  components: ['u', 'v', 'w'],
  units: 'mm',
  association: 'point',
  time: null,
  range: { min: -0.42, max: 0.87 },
  region_ids: ['mount-bracket'],
  bounds: { min: [-0.02, -0.01, 0], max: [0.02, 0.01, 0.05] },
  full_artifact: {
    artifact_id: 'fixture-displacement-exo',
    sha256: h('e'),
    bytes: 18000000,
    mime: 'application/octet-stream',
    format: 'exo',
  },
  derivatives: [
    {
      artifact_id: 'fixture-displacement-glb',
      sha256: h('2'),
      bytes: 360000,
      mime: 'model/gltf-binary',
      format: 'glb',
      role: 'visualization-decimated',
      source_sha256: h('e'),
      decimation_ratio: 0.02,
    },
  ],
};

export const FIXTURE_FLOW_VECTOR_FIELD = {
  artifact_id: 'fixture-velocity-volume',
  artifact_sha256: h('3'),
  mesh_sha256: h('4'),
  geometry_sha256: null,
  field_name: 'velocity',
  rank: 'vector',
  components: ['Ux', 'Uy', 'Uz'],
  units: 'm/s',
  association: 'cell',
  time: { kind: 'frequency', index: 2, value: 120.0, unit: 'Hz' },
  range: { min: 0.0, max: 42.5 },
  region_ids: ['inlet-flow-domain'],
  bounds: { min: [-0.05, -0.05, 0], max: [0.05, 0.05, 0.09] },
  full_artifact: {
    artifact_id: 'fixture-velocity-openfoam',
    sha256: h('3'),
    bytes: 96000000,
    mime: 'application/octet-stream',
    format: 'openfoam',
  },
  derivatives: [
    {
      artifact_id: 'fixture-velocity-vtp',
      sha256: h('5'),
      bytes: 720000,
      mime: 'application/octet-stream',
      format: 'vtp',
      role: 'visualization-converted',
      source_sha256: h('3'),
      decimation_ratio: null,
    },
  ],
};

/** Partial: no bounded derivative yet, so the UI may export but not view it. */
export const FIXTURE_PARTIAL_FIELD = {
  ...FIXTURE_SCALAR_FIELD,
  artifact_id: 'fixture-temperature-partial',
  artifact_sha256: h('6'),
  field_name: 'temperature',
  units: 'K',
  derivatives: [],
  full_artifact: { ...FIXTURE_SCALAR_FIELD.full_artifact, sha256: h('6'), artifact_id: 'fixture-temperature-vtu' },
};

/** Invalid: derivative claims a different source hash (provenance violation). */
export const FIXTURE_BROKEN_PROVENANCE_FIELD = {
  ...FIXTURE_SCALAR_FIELD,
  artifact_id: 'fixture-broken-provenance',
  artifact_sha256: h('7'),
  derivatives: [
    {
      ...FIXTURE_SCALAR_FIELD.derivatives[0],
      artifact_id: 'fixture-broken-glb',
      source_sha256: h('9'),
    },
  ],
};

/** Rejected: a giant inline numeric array is not a valid control-path manifest. */
export const FIXTURE_GIANT_INLINE_FIELD = {
  ...FIXTURE_SCALAR_FIELD,
  values: Array.from({ length: 50000 }, (_, index) => index),
};

export const FIXTURE_FIELDS: Array<{ key: string; label: string; payload: unknown }> = [
  { key: 'scalar', label: `${FIXTURE_BANNER} · scalar pressure`, payload: FIXTURE_SCALAR_FIELD },
  { key: 'deformation', label: `${FIXTURE_BANNER} · structural displacement`, payload: FIXTURE_VECTOR_DEFORMATION_FIELD },
  { key: 'flow', label: `${FIXTURE_BANNER} · flow velocity`, payload: FIXTURE_FLOW_VECTOR_FIELD },
  { key: 'partial', label: `${FIXTURE_BANNER} · partial temperature`, payload: FIXTURE_PARTIAL_FIELD },
  { key: 'broken', label: `${FIXTURE_BANNER} · broken provenance`, payload: FIXTURE_BROKEN_PROVENANCE_FIELD },
  { key: 'giant', label: `${FIXTURE_BANNER} · rejected inline payload`, payload: FIXTURE_GIANT_INLINE_FIELD },
];

export const FIXTURE_RESULT_A: ComparableResult = {
  jobId: 'fixture-job-a',
  label: 'Fixture native result A',
  source: 'native_solver',
  fidelity: 'medium-fidelity',
  solverIdentity: 'fixture-solver',
  solverVersion: '1.0',
  validity: { passed: true, detail: 'fixture receipt only' },
  units: { pressure_drop: 'Pa', temperature_rise: 'K' },
  scalars: { pressure_drop: 1240.0, temperature_rise: 18.5 },
  meshSha256: h('b'),
  geometrySha256: h('c'),
  artifactSha256: h('a'),
  provenanceId: 'fixture-prov-a',
  interfaceNames: ['fsi-0'],
};

export const FIXTURE_RESULT_B: ComparableResult = {
  ...FIXTURE_RESULT_A,
  jobId: 'fixture-job-b',
  label: 'Fixture native result B',
  fidelity: 'coarse-fidelity',
  solverVersion: '1.1',
  scalars: { pressure_drop: 1195.0, temperature_rise: 17.8 },
  artifactSha256: h('e'),
};

export const FIXTURE_RESULT_ANALYTICAL: ComparableResult = {
  ...FIXTURE_RESULT_A,
  jobId: 'fixture-job-analytical',
  label: 'Fixture analytical sample',
  source: 'analytical',
  fidelity: 'analytical',
  validity: { passed: true, detail: 'demonstration only' },
  solverIdentity: 'analytical-model',
  solverVersion: '',
  provenanceId: null,
  meshSha256: null,
  artifactSha256: null,
};
