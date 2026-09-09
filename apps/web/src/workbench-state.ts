export type DemoId = 'edf' | 'aircraft' | 'gas-turbine';
export type ViewMode = 'flow' | 'structure' | 'thermal' | 'fields';
export type DockTab = 'convergence' | 'energy' | 'resonance' | 'timeline' | 'warnings' | 'logs';

export interface SampleEvidence {
  source: 'analytical model';
  fidelity: 'analytical';
  validity: 'demonstration only';
  nativeExecution: 'not performed';
}

const analyticalSampleEvidence: SampleEvidence = {
  source: 'analytical model',
  fidelity: 'analytical',
  validity: 'demonstration only',
  nativeExecution: 'not performed',
};

export interface DemoProfile {
  id: DemoId;
  title: string;
  subtitle: string;
  couplingStrength: number;
  evidenceLabel: 'Analytical sample state — not a native solver run';
  evidence: SampleEvidence;
  activeNode: string;
  geometry: 'EDF' | 'Aircraft' | 'Turbine';
  progress: number;
}

const profiles: Record<DemoId, DemoProfile> = {
  edf: {
    id: 'edf',
    title: 'EDF-90 / Coupled inlet study',
    subtitle: '90 mm ducted-fan demonstrator',
    couplingStrength: 0.9,
    evidenceLabel: 'Analytical sample state — not a native solver run',
    evidence: analyticalSampleEvidence,
    activeNode: 'Rotor & duct assembly',
    geometry: 'EDF',
    progress: 68,
  },
  aircraft: {
    id: 'aircraft',
    title: 'Asterion / Flight envelope',
    subtitle: 'Aerobatic aircraft demonstrator',
    couplingStrength: 0.9,
    evidenceLabel: 'Analytical sample state — not a native solver run',
    evidence: analyticalSampleEvidence,
    activeNode: 'Wing carry-through',
    geometry: 'Aircraft',
    progress: 41,
  },
  'gas-turbine': {
    id: 'gas-turbine',
    title: 'GT-01 / Core matching',
    subtitle: 'Single-spool gas turbine demonstrator',
    couplingStrength: 0.9,
    evidenceLabel: 'Analytical sample state — not a native solver run',
    evidence: analyticalSampleEvidence,
    activeNode: 'Compressor map',
    geometry: 'Turbine',
    progress: 53,
  },
};

export const getDemoProfile = (id: DemoId): DemoProfile => profiles[id];

export const updateCouplingStrength = (_current: number, proposed: number): number =>
  Math.max(0, Math.min(1, Number.isFinite(proposed) ? proposed : 0));

export const qualityGateEvidence = {
  energy: 'Analytical · screening/sample only',
  resonance: 'Analytical · screening/sample only',
  native: 'Declarative capability state',
} as const;

export const shouldRestoreProvenanceFocus = (provenanceOpen: boolean, wasOpen: boolean): boolean =>
  !provenanceOpen && wasOpen;

const viewModes: Record<ViewMode, { label: string; field: string; available: boolean; detail: string }> = {
  flow: { label: 'Flow', field: 'Pressure coefficient', available: true, detail: 'Analytical surface-pressure estimate' },
  structure: { label: 'Structure', field: 'Displacement envelope', available: true, detail: 'Analytical beam-response estimate' },
  thermal: { label: 'Thermal', field: 'Component temperature', available: true, detail: 'Lumped thermal-network estimate' },
  fields: { label: 'Fields', field: 'No asset loaded', available: false, detail: 'No field asset is attached; the optional VTK viewer remains unloaded.' },
};

const dockPanels: Record<DockTab, { eyebrow: string; value: string; detail: string; source: string; fidelity: string; validity: string }> = {
  convergence: { eyebrow: 'GLOBAL RESIDUAL', value: '1.8e−3', detail: 'Seven-iteration sample convergence trace', source: 'Analytical model', fidelity: 'analytical', validity: 'sample state only' },
  energy: { eyebrow: 'ENERGY BALANCE', value: '0.8%', detail: 'Estimated imbalance across the coupled sample state', source: 'Analytical model', fidelity: 'analytical', validity: 'sample state only' },
  resonance: { eyebrow: 'RESONANCE MARGIN', value: '1.21×', detail: 'Screening ratio to the nearest analytical mode', source: 'Analytical model', fidelity: 'analytical', validity: 'screening only' },
  timeline: { eyebrow: 'STATE HISTORY', value: '07', detail: 'Current baseline follows six retained sample revisions', source: 'Local sample state', fidelity: 'demonstration', validity: 'sample state only' },
  warnings: { eyebrow: 'REVIEW QUEUE', value: '2', detail: 'One mesh warning and one unavailable native capability', source: 'Quality-gate checks', fidelity: 'declarative', validity: 'not solver evidence' },
  logs: { eyebrow: 'CAPABILITY LOG', value: '4', detail: 'Declared adapters checked; three native solvers unavailable', source: 'Capability registry', fidelity: 'declarative', validity: 'not solver evidence' },
};

export const getViewModeStatus = (mode: ViewMode) => viewModes[mode];
export const getDockPanel = (tab: DockTab) => dockPanels[tab];
