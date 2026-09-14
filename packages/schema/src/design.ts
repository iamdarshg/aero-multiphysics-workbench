import type { NormalizedQuantity } from "../../units/src/index.ts";
import { contentDigest } from "../../cache/src/content-addressed.ts";

const SHA256 = /^[a-f0-9]{64}$/;

function deepFreeze<T>(value: T): Readonly<T> {
  if (value && typeof value === "object" && !Object.isFrozen(value)) {
    for (const child of Object.values(value as Record<string, unknown>)) deepFreeze(child);
    Object.freeze(value);
  }
  return value;
}

function requireDigest(label: string, digest: string): void {
  if (!SHA256.test(digest)) throw new TypeError(`${label} must be a SHA-256 digest`);
}

/** Immutable reference to a parameter set revision (units live on the set). */
export interface ParameterRevisionRef {
  readonly digest: string;
  readonly count: number;
}

/** Immutable reference to a geometry definition plus its semantic topology. */
export interface GeometryRef {
  readonly digest: string;
  readonly semanticDigest: string;
  readonly definitionDigest?: string;
  readonly revisionId?: string;
}

/** One region's binding to an immutable material revision. */
export interface MaterialRegionBinding {
  readonly region: string;
  readonly materialIdentity: string;
  readonly materialDigest: string;
  readonly orientationFrame?: string;
}

/** Immutable reference to material revisions plus region bindings. */
export interface MaterialsRef {
  readonly digest: string;
  readonly bindings?: ReadonlyArray<MaterialRegionBinding>;
}

/** One operating point: named condition with unit-bearing values. */
export interface OperatingPoint {
  readonly name: string;
  readonly values: Readonly<Record<string, NormalizedQuantity>>;
}

/** One design objective with an optional weight. */
export interface ObjectiveDefinition {
  readonly name: string;
  readonly target: "maximize" | "minimize" | "match";
  readonly weight?: number;
  readonly unit?: string;
}

/** One design constraint with a bound. */
export interface ConstraintDefinition {
  readonly name: string;
  readonly bound: "upper" | "lower" | "equality";
  readonly limitSI: number;
  readonly unit: string;
}

/** Solver settings for one participant (never one global blob). */
export interface ParticipantSolverSettings {
  readonly participant: string;
  readonly solver: string;
  readonly version: string;
  readonly settings: Readonly<Record<string, unknown>>;
}

/** Field/scalar coupling configuration between participants. */
export interface CouplingSettings {
  readonly strength: number;
  readonly pairs: ReadonlyArray<{
    readonly from: string;
    readonly to: string;
    readonly quantities: ReadonlyArray<string>;
  }>;
  readonly policy: Readonly<Record<string, unknown>>;
}

/** Motion/frame definition: rotating or stationary reference frames. */
export interface MotionFrame {
  readonly name: string;
  readonly kind: "rotating" | "stationary";
  readonly axis: Readonly<[number, number, number]>;
  readonly rateSI?: number;
}

/** Interface declaration between two solver domains. */
export interface DomainInterface {
  readonly name: string;
  readonly domainA: string;
  readonly domainB: string;
  readonly kind: string;
}

export interface DesignRevision {
  designId: string;
  revisionId: string;
  parentRevisionHash: string | null;
  parameters: Readonly<Record<string, NormalizedQuantity>>;
  parameterRevision?: ParameterRevisionRef;
  geometry: GeometryRef;
  semanticsDigest?: string;
  materials: MaterialsRef;
  operatingPoints?: ReadonlyArray<OperatingPoint>;
  objectives?: ReadonlyArray<ObjectiveDefinition>;
  constraints?: ReadonlyArray<ConstraintDefinition>;
  solverPolicy: Readonly<{ solver: string; version: string; settings: Readonly<Record<string, unknown>> }>;
  participantSolvers?: ReadonlyArray<ParticipantSolverSettings>;
  coupling?: CouplingSettings;
  computePolicy?: Readonly<Record<string, unknown>>;
  fidelityPolicy?: Readonly<Record<string, unknown>>;
  motionFrames?: ReadonlyArray<MotionFrame>;
  interfaces?: ReadonlyArray<DomainInterface>;
  parentVariant?: Readonly<{ designId: string; revisionHash: string }>;
  contentHash: string;
  changeRecord?: Readonly<{ author: string; reason: string; createdAt: string }>;
}

function normalizedParameters(
  parameters: Readonly<Record<string, NormalizedQuantity>>,
): Record<string, unknown> {
  return Object.fromEntries(
    Object.entries(parameters).map(([name, quantity]) => [name, {
      valueSI: quantity.valueSI,
      dimension: quantity.dimension,
      canonicalUnit: quantity.canonicalUnit,
    }]),
  );
}

export function createDesignRevision(input: Omit<DesignRevision, "contentHash">): Readonly<DesignRevision> {
  if (!input.designId.trim() || !input.revisionId.trim()) throw new TypeError("design and revision ids must be non-empty");
  for (const [name, digest] of Object.entries({
    geometry: input.geometry.digest,
    semantics: input.geometry.semanticDigest,
    materials: input.materials.digest,
  })) {
    requireDigest(name, digest);
  }
  if (input.parameterRevision) requireDigest("parameterRevision", input.parameterRevision.digest);
  if (input.semanticsDigest) requireDigest("semantics", input.semanticsDigest);
  for (const binding of input.materials.bindings ?? []) {
    requireDigest(`material:${binding.region}`, binding.materialDigest);
    if (!binding.region.trim() || !binding.materialIdentity.includes("@")) {
      throw new TypeError("material bindings need a region and an id@revision identity");
    }
  }
  if (input.coupling && !(input.coupling.strength >= 0 && input.coupling.strength <= 1)) {
    throw new TypeError("coupling strength must be within 0..1");
  }
  const parameters = Object.fromEntries(
    Object.entries(input.parameters).map(([name, quantity]) => [name, { ...quantity }]),
  );
  const physicalContent = {
    parameters: normalizedParameters(parameters),
    parameterRevision: input.parameterRevision,
    geometry: input.geometry,
    semanticsDigest: input.semanticsDigest,
    materials: input.materials,
    operatingPoints: (input.operatingPoints ?? []).map((point) => ({
      name: point.name,
      values: normalizedParameters(point.values),
    })),
    objectives: input.objectives,
    constraints: input.constraints,
    solverPolicy: input.solverPolicy,
    participantSolvers: input.participantSolvers,
    coupling: input.coupling,
    computePolicy: input.computePolicy,
    fidelityPolicy: input.fidelityPolicy,
    motionFrames: input.motionFrames,
    interfaces: input.interfaces,
    parentVariant: input.parentVariant,
  };
  return deepFreeze({
    ...structuredClone(input),
    parameters,
    contentHash: contentDigest(physicalContent),
  }) as Readonly<DesignRevision>;
}

export function createVariantRevision(
  parent: DesignRevision,
  change: {
    revisionId: string;
    parameterChanges: Record<string, NormalizedQuantity>;
    author: string;
    reason: string;
    createdAt: string;
  },
): Readonly<DesignRevision> {
  if (!change.author.trim() || !change.reason.trim() || Number.isNaN(Date.parse(change.createdAt))) {
    throw new TypeError("variant changes require an author, reason, and ISO timestamp");
  }
  for (const [name, quantity] of Object.entries(change.parameterChanges)) {
    const current = parent.parameters[name];
    if (!current) throw new RangeError(`unknown parameter: ${name}`);
    if (current.dimension !== quantity.dimension) throw new TypeError(`parameter ${name} cannot change dimension`);
  }
  const { contentHash: _parentHash, ...rest } = parent;
  void _parentHash;
  return createDesignRevision({
    ...structuredClone(rest),
    revisionId: change.revisionId,
    parentRevisionHash: parent.contentHash,
    parentVariant: { designId: parent.designId, revisionHash: parent.contentHash },
    parameters: { ...parent.parameters, ...change.parameterChanges },
    changeRecord: { author: change.author, reason: change.reason, createdAt: change.createdAt },
  });
}

/**
 * Map a changed design section to the downstream computation node families it
 * invalidates. Every material/geometry/semantics/operating-point/solver/
 * coupling change must invalidate its affected descendants; unknown sections
 * fail closed by invalidating everything.
 */
export const CHANGE_IMPACT: Readonly<Record<string, ReadonlyArray<string>>> = Object.freeze({
  parameters: Object.freeze(["geometry", "mesh", "analysis", "objectives"]),
  parameterRevision: Object.freeze(["geometry", "mesh", "analysis", "objectives"]),
  geometry: Object.freeze(["geometry", "mesh", "analysis", "interfaces", "objectives"]),
  semantics: Object.freeze(["mesh", "analysis", "interfaces", "objectives"]),
  materials: Object.freeze(["mesh", "structural", "thermal", "electromagnetic", "objectives"]),
  operatingPoints: Object.freeze(["analysis", "objectives"]),
  objectives: Object.freeze(["optimization"]),
  constraints: Object.freeze(["optimization", "validation"]),
  solverPolicy: Object.freeze(["analysis"]),
  participantSolvers: Object.freeze(["analysis"]),
  coupling: Object.freeze(["coupled-analysis", "convergence"]),
  computePolicy: Object.freeze(["scheduling"]),
  fidelityPolicy: Object.freeze(["analysis", "optimization"]),
  motionFrames: Object.freeze(["mesh", "analysis", "interfaces"]),
  interfaces: Object.freeze(["coupled-analysis", "mesh"]),
});

export function invalidatedNodes(changedSections: ReadonlyArray<string>): ReadonlyArray<string> {
  const invalidated = new Set<string>();
  for (const section of changedSections) {
    const impact = CHANGE_IMPACT[section];
    if (!impact) {
      return Object.freeze(["all"]);
    }
    for (const node of impact) invalidated.add(node);
  }
  return Object.freeze([...invalidated].sort());
}
