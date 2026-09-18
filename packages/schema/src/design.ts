import type { NormalizedQuantity } from "../../units/src/index.ts";
import { normalizeQuantity } from "../../units/src/index.ts";
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

/** Binding from a design-variable name to a geometry parameter path. */
export interface GeometryParameterBinding {
  readonly variable: string;
  readonly parameterPath: string;
  readonly unit: string;
}

/** Rebuild and permitted topology-change policy for a geometry definition. */
export interface GeometryRebuildPolicy {
  readonly onParameterChange: "rebuild" | "reuse";
  readonly permittedTopologyChange: "preserve" | "remesh" | "any";
}

/** Immutable reference to a geometry definition plus its semantic topology. */
export interface GeometryRef {
  readonly digest: string;
  readonly semanticDigest: string;
  readonly definitionDigest?: string;
  readonly revisionId?: string;
  readonly parameterRevision?: ParameterRevisionRef;
  readonly topologyDigest?: string;
  readonly bindings?: ReadonlyArray<GeometryParameterBinding>;
  readonly rebuildPolicy?: GeometryRebuildPolicy;
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
  designSpace?: DesignSpace;
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
  if (input.geometry.definitionDigest) requireDigest("geometryDefinition", input.geometry.definitionDigest);
  if (input.geometry.topologyDigest) requireDigest("geometryTopology", input.geometry.topologyDigest);
  if (input.geometry.parameterRevision) requireDigest("geometryParameterRevision", input.geometry.parameterRevision.digest);
  for (const binding of input.geometry.bindings ?? []) {
    if (!binding.variable.trim() || !binding.parameterPath.trim() || !binding.unit.trim()) {
      throw new TypeError("geometry bindings need a variable, parameter path, and unit");
    }
  }
  if (input.geometry.rebuildPolicy) {
    const { onParameterChange, permittedTopologyChange } = input.geometry.rebuildPolicy;
    if (onParameterChange !== "rebuild" && onParameterChange !== "reuse") {
      throw new TypeError("unknown geometry rebuild policy");
    }
    if (!["preserve", "remesh", "any"].includes(permittedTopologyChange)) {
      throw new TypeError("unknown geometry topology-change policy");
    }
  }
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
  if (input.designSpace) validateDesignSpace(input.designSpace);
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
    designSpace: input.designSpace,
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
  geometryBindings: Object.freeze(["geometry", "mesh", "analysis", "objectives"]),
  geometryRebuildPolicy: Object.freeze(["geometry", "mesh", "analysis", "optimization"]),
  topologyDigest: Object.freeze(["mesh", "analysis", "interfaces", "objectives"]),
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
  designSpace: Object.freeze(["geometry", "mesh", "analysis", "optimization", "objectives"]),
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

/* --------------------------------------------------------------------------
 * Canonical mixed, conditional, hierarchical design-space contract.
 *
 * A design space is a declarative description of every variable that may be
 * sampled or derived during a generative study. It is intentionally data-only:
 * conditions use a small typed predicate/expression AST, never executable code.
 * ``flattenDesignState`` produces the deterministic, unit-normalized view that
 * OpenMDAO/search drivers consume; ``unflattenDesignState`` reverses it.
 * ------------------------------------------------------------------------ */

export type DesignVariableKind =
  | "continuous"
  | "integer"
  | "discrete"
  | "categorical"
  | "boolean"
  | "vector-profile"
  | "linked"
  | "derived";

export type DesignBindingTarget = "parameter" | "material" | "solver" | "operating-point";

/** Binding of a design variable into downstream participant state. */
export interface DesignVariableBinding {
  readonly target: DesignBindingTarget;
  readonly path: string;
  readonly unit?: string;
}

/** One bounded, named control point of a vector/profile variable. */
export interface ProfileControlPoint {
  readonly id: string;
  readonly lower: number;
  readonly upper: number;
  readonly baseValue: number;
}

/** Safe arithmetic AST; evaluators never execute user-provided code. */
export type DesignExpression =
  | { readonly op: "variable"; readonly variable: string }
  | { readonly op: "constant"; readonly value: number }
  | {
      readonly op: "add" | "subtract" | "multiply" | "divide";
      readonly left: DesignExpression;
      readonly right: DesignExpression;
    };

/** Safe boolean predicate AST used for conditional activation. */
export type DesignPredicate =
  | { readonly op: "equals"; readonly variable: string; readonly value: number | string | boolean }
  | { readonly op: "in"; readonly variable: string; readonly values: ReadonlyArray<number | string | boolean> }
  | {
      readonly op: "lessThan" | "lessOrEqual" | "greaterThan" | "greaterOrEqual";
      readonly variable: string;
      readonly valueSI: number;
    }
  | { readonly op: "all"; readonly clauses: ReadonlyArray<DesignPredicate> }
  | { readonly op: "any"; readonly clauses: ReadonlyArray<DesignPredicate> }
  | { readonly op: "not"; readonly clause: DesignPredicate };

export type DesignDomain =
  | { readonly kind: "continuous"; readonly lower: number; readonly upper: number }
  | { readonly kind: "integer"; readonly lower: number; readonly upper: number; readonly step: number }
  | { readonly kind: "discrete"; readonly values: ReadonlyArray<number> }
  | { readonly kind: "categorical"; readonly values: ReadonlyArray<string> }
  | { readonly kind: "boolean" }
  | {
      readonly kind: "vector-profile";
      readonly controlPoints: ReadonlyArray<ProfileControlPoint>;
      readonly lengthVariable?: string;
    }
  | { readonly kind: "linked"; readonly targetVariable: string; readonly scale?: number; readonly offset?: number }
  | { readonly kind: "derived"; readonly expression: DesignExpression };

export interface DesignVariable {
  readonly id: string;
  readonly name?: string;
  readonly kind: DesignVariableKind;
  readonly unit?: string;
  readonly bindings: ReadonlyArray<DesignVariableBinding>;
  readonly baseValue?: number | string | boolean;
  readonly basePoints?: ReadonlyArray<{ readonly id: string; readonly value: number }>;
  readonly mutationScale?: number;
  readonly activeWhen?: DesignPredicate;
  readonly domain: DesignDomain;
}

/** Selects one implementation branch from a declared set of option members. */
export interface DesignBranch {
  readonly id: string;
  readonly selector: string;
  readonly options: Readonly<Record<string, ReadonlyArray<string>>>;
}

export type PreflightConstraint =
  | { readonly id: string; readonly kind: "mutually-exclusive"; readonly variables: ReadonlyArray<string> }
  | { readonly id: string; readonly kind: "requires"; readonly when: DesignPredicate; readonly require: DesignPredicate }
  | {
      readonly id: string;
      readonly kind: "relation";
      readonly expression: DesignExpression;
      readonly relation: "lessOrEqual" | "greaterOrEqual" | "equal";
      readonly limit: number;
    }
  | { readonly id: string; readonly kind: "count"; readonly countVariable: string; readonly memberVariable: string };

export interface DesignSpace {
  readonly id: string;
  readonly variables: ReadonlyArray<DesignVariable>;
  readonly branches?: ReadonlyArray<DesignBranch>;
  readonly constraints?: ReadonlyArray<PreflightConstraint>;
}

export type DesignStateValue =
  | { readonly kind: "number"; readonly value: number; readonly unit: string }
  | { readonly kind: "dimensionless"; readonly value: number }
  | { readonly kind: "categorical"; readonly value: string }
  | { readonly kind: "boolean"; readonly value: boolean }
  | {
      readonly kind: "vector-profile";
      readonly points: ReadonlyArray<{ readonly id: string; readonly value: number; readonly unit?: string }>;
    };

export type DesignState = Readonly<Record<string, DesignStateValue>>;

export interface FlatProfilePoint {
  readonly id: string;
  readonly valueSI: number;
  readonly rawValue: number;
  readonly unit?: string;
}

export interface FlatDesignEntry {
  readonly id: string;
  readonly kind: DesignVariableKind;
  readonly active: boolean;
  readonly provided: boolean;
  readonly lineage: ReadonlyArray<string>;
  readonly unit?: string;
  readonly bindings: ReadonlyArray<DesignVariableBinding>;
  readonly value?: number | string | boolean;
  readonly valueSI?: number;
  readonly points?: ReadonlyArray<FlatProfilePoint>;
}

export interface FlatDesignState {
  readonly spaceId: string;
  readonly order: ReadonlyArray<string>;
  readonly entries: ReadonlyArray<FlatDesignEntry>;
  readonly inactive: ReadonlyArray<string>;
}

const VARIABLE_KINDS: ReadonlySet<string> = new Set([
  "continuous",
  "integer",
  "discrete",
  "categorical",
  "boolean",
  "vector-profile",
  "linked",
  "derived",
]);
const BINDING_TARGETS: ReadonlySet<string> = new Set(["parameter", "material", "solver", "operating-point"]);
const NUMERIC_KINDS: ReadonlySet<string> = new Set(["continuous", "integer", "discrete"]);

function designIndex(space: DesignSpace): Map<string, DesignVariable> {
  return new Map(space.variables.map((variable) => [variable.id, variable]));
}

function requireFinite(label: string, value: number): void {
  if (!Number.isFinite(value)) throw new TypeError(`${label} must be finite`);
}

function validateBindings(variable: DesignVariable): void {
  if (!variable.bindings.length) throw new RangeError(`VARIABLE_NEEDS_BINDING:${variable.id}`);
  for (const binding of variable.bindings) {
    if (!BINDING_TARGETS.has(binding.target)) throw new TypeError(`UNKNOWN_BINDING_TARGET:${variable.id}`);
    if (!binding.path.trim()) throw new TypeError(`BINDING_PATH_REQUIRED:${variable.id}`);
    if (binding.unit !== undefined && !binding.unit.trim()) throw new TypeError(`BINDING_UNIT_EMPTY:${variable.id}`);
  }
}

function validateControlPoints(variable: DesignVariable, domain: Extract<DesignDomain, { kind: "vector-profile" }>): void {
  if (!domain.controlPoints.length) throw new RangeError(`PROFILE_NEEDS_CONTROL_POINTS:${variable.id}`);
  const seen = new Set<string>();
  for (const point of domain.controlPoints) {
    if (!point.id.trim()) throw new TypeError(`PROFILE_POINT_ID_REQUIRED:${variable.id}`);
    if (seen.has(point.id)) throw new RangeError(`DUPLICATE_PROFILE_POINT:${variable.id}:${point.id}`);
    seen.add(point.id);
    requireFinite(`profile:${variable.id}:${point.id}`, point.lower);
    requireFinite(`profile:${variable.id}:${point.id}`, point.upper);
    requireFinite(`profile:${variable.id}:${point.id}`, point.baseValue);
    if (point.lower > point.upper) throw new RangeError(`PROFILE_BOUNDS_INVALID:${variable.id}:${point.id}`);
    if (point.baseValue < point.lower || point.baseValue > point.upper) {
      throw new RangeError(`PROFILE_BASE_OUT_OF_BOUNDS:${variable.id}:${point.id}`);
    }
  }
}

function validatePredicate(predicate: DesignPredicate, index: Map<string, DesignVariable>): void {
  if (predicate.op === "all" || predicate.op === "any") {
    for (const clause of predicate.clauses) validatePredicate(clause, index);
    return;
  }
  if (predicate.op === "not") {
    validatePredicate(predicate.clause, index);
    return;
  }
  const variable = index.get(predicate.variable);
  if (!variable) throw new RangeError(`PREDICATE_UNKNOWN_VARIABLE:${predicate.variable}`);
  if (predicate.op === "equals" || predicate.op === "in") {
    if (variable.kind !== "categorical" && variable.kind !== "boolean") {
      throw new TypeError(`EQUALITY_NEEDS_CATEGORICAL_OR_BOOLEAN:${predicate.variable}`);
    }
    const values = predicate.op === "equals" ? [predicate.value] : predicate.values;
    if (predicate.op === "in" && values.length === 0) throw new RangeError(`PREDICATE_IN_NEEDS_VALUES:${predicate.variable}`);
    for (const value of values) {
      if (variable.kind === "boolean" && typeof value !== "boolean") {
        throw new TypeError(`BOOLEAN_PREDICATE_VALUE_REQUIRED:${predicate.variable}`);
      }
      if (variable.kind === "categorical" && typeof value !== "string") {
        throw new TypeError(`CATEGORICAL_PREDICATE_VALUE_REQUIRED:${predicate.variable}`);
      }
      if (variable.kind === "categorical" && !(variable.domain as Extract<DesignDomain, { kind: "categorical" }>).values.includes(value as string)) {
        throw new RangeError(`PREDICATE_VALUE_NOT_IN_DOMAIN:${predicate.variable}:${String(value)}`);
      }
    }
    return;
  }
  if (predicate.op === "lessThan" || predicate.op === "lessOrEqual" || predicate.op === "greaterThan" || predicate.op === "greaterOrEqual") {
    if (!NUMERIC_KINDS.has(variable.kind)) throw new TypeError(`COMPARISON_NEEDS_NUMERIC:${predicate.variable}`);
    requireFinite(`predicate:${predicate.variable}`, predicate.valueSI);
    return;
  }
  throw new TypeError("UNKNOWN_PREDICATE_OP");
}

function validateExpression(expression: DesignExpression, index: Map<string, DesignVariable>): void {
  if (expression.op === "variable") {
    const variable = index.get(expression.variable);
    if (!variable) throw new RangeError(`EXPRESSION_UNKNOWN_VARIABLE:${expression.variable}`);
    if (!NUMERIC_KINDS.has(variable.kind) && variable.kind !== "linked" && variable.kind !== "derived") {
      throw new TypeError(`EXPRESSION_NEEDS_NUMERIC:${expression.variable}`);
    }
    return;
  }
  if (expression.op === "constant") {
    requireFinite("expression constant", expression.value);
    return;
  }
  validateExpression(expression.left, index);
  validateExpression(expression.right, index);
  if (expression.op === "divide" && expression.right.op === "constant" && expression.right.value === 0) {
    throw new RangeError("EXPRESSION_DIVISION_BY_ZERO");
  }
}

function expressionVariables(expression: DesignExpression): ReadonlyArray<string> {
  if (expression.op === "variable") return [expression.variable];
  if (expression.op === "constant") return [];
  return [...expressionVariables(expression.left), ...expressionVariables(expression.right)];
}

function validateVariable(variable: DesignVariable, index: Map<string, DesignVariable>): void {
  if (!variable.id.trim()) throw new TypeError("VARIABLE_ID_REQUIRED");
  if (!VARIABLE_KINDS.has(variable.kind)) throw new TypeError(`UNKNOWN_VARIABLE_KIND:${variable.id}`);
  if (variable.domain.kind !== variable.kind) throw new TypeError(`DOMAIN_KIND_MISMATCH:${variable.id}`);
  if (variable.unit !== undefined) {
    if (!variable.unit.trim()) throw new TypeError(`VARIABLE_UNIT_EMPTY:${variable.id}`);
    if (variable.kind === "categorical" || variable.kind === "boolean") {
      throw new TypeError(`NON_NUMERIC_VARIABLE_HAS_UNIT:${variable.id}`);
    }
    try {
      normalizeQuantity(0, variable.unit);
    } catch {
      throw new TypeError(`UNSUPPORTED_UNIT:${variable.id}:${variable.unit}`);
    }
  }
  validateBindings(variable);
  if (variable.mutationScale !== undefined) {
    requireFinite(`mutationScale:${variable.id}`, variable.mutationScale);
    if (variable.mutationScale <= 0) throw new RangeError(`MUTATION_SCALE_MUST_BE_POSITIVE:${variable.id}`);
  }
  const domain = variable.domain;
  switch (domain.kind) {
    case "continuous":
      requireFinite(variable.id, domain.lower);
      requireFinite(variable.id, domain.upper);
      if (!(domain.lower < domain.upper)) throw new RangeError(`INVALID_CONTINUOUS_BOUNDS:${variable.id}`);
      break;
    case "integer":
      requireFinite(variable.id, domain.lower);
      requireFinite(variable.id, domain.upper);
      requireFinite(variable.id, domain.step);
      if (!(domain.lower <= domain.upper)) throw new RangeError(`INVALID_INTEGER_BOUNDS:${variable.id}`);
      if (!Number.isInteger(domain.lower) || !Number.isInteger(domain.upper) || !Number.isInteger(domain.step)) {
        throw new TypeError(`INTEGER_BOUNDS_NOT_INTEGRAL:${variable.id}`);
      }
      if (domain.step <= 0) throw new RangeError(`INTEGER_STEP_MUST_BE_POSITIVE:${variable.id}`);
      break;
    case "discrete": {
      if (!domain.values.length) throw new RangeError(`DISCRETE_NEEDS_VALUES:${variable.id}`);
      const unique = new Set(domain.values);
      if (unique.size !== domain.values.length) throw new RangeError(`DISCRETE_VALUES_DUPLICATE:${variable.id}`);
      for (const value of domain.values) requireFinite(`discrete:${variable.id}`, value);
      break;
    }
    case "categorical": {
      if (!domain.values.length) throw new RangeError(`CATEGORICAL_NEEDS_VALUES:${variable.id}`);
      if (domain.values.some((value) => !value.trim())) throw new TypeError(`CATEGORICAL_VALUE_EMPTY:${variable.id}`);
      if (new Set(domain.values).size !== domain.values.length) throw new RangeError(`CATEGORICAL_VALUES_DUPLICATE:${variable.id}`);
      break;
    }
    case "boolean":
      break;
    case "vector-profile": {
      validateControlPoints(variable, domain);
      if (domain.lengthVariable !== undefined) {
        const lengthVariable = index.get(domain.lengthVariable);
        if (!lengthVariable) throw new RangeError(`PROFILE_LENGTH_UNKNOWN_VARIABLE:${variable.id}`);
        if (lengthVariable.kind !== "integer") throw new TypeError(`PROFILE_LENGTH_NEEDS_INTEGER:${variable.id}`);
      }
      break;
    }
    case "linked": {
      const target = index.get(domain.targetVariable);
      if (!target) throw new RangeError(`LINKED_UNKNOWN_TARGET:${variable.id}`);
      if (!NUMERIC_KINDS.has(target.kind)) throw new TypeError(`LINKED_TARGET_NEEDS_NUMERIC:${variable.id}`);
      if (domain.targetVariable === variable.id) throw new RangeError(`LINKED_SELF_REFERENCE:${variable.id}`);
      if (domain.scale !== undefined) requireFinite(`linked:${variable.id}`, domain.scale);
      if (domain.offset !== undefined) requireFinite(`linked:${variable.id}`, domain.offset);
      break;
    }
    case "derived":
      validateExpression(domain.expression, index);
      break;
    default:
      throw new TypeError(`UNKNOWN_VARIABLE_KIND:${variable.id}`);
  }
  if (variable.activeWhen) validatePredicate(variable.activeWhen, index);
}

function validateBranch(branch: DesignBranch, index: Map<string, DesignVariable>): void {
  if (!branch.id.trim()) throw new TypeError("BRANCH_ID_REQUIRED");
  const selector = index.get(branch.selector);
  if (!selector) throw new RangeError(`BRANCH_UNKNOWN_SELECTOR:${branch.id}`);
  if (selector.kind !== "categorical") throw new TypeError(`BRANCH_SELECTOR_NEEDS_CATEGORICAL:${branch.id}`);
  const selectorValues = (selector.domain as Extract<DesignDomain, { kind: "categorical" }>).values;
  for (const [option, members] of Object.entries(branch.options)) {
    if (!selectorValues.includes(option)) throw new RangeError(`BRANCH_OPTION_NOT_IN_DOMAIN:${branch.id}:${option}`);
    for (const member of members) {
      if (!index.has(member)) throw new RangeError(`BRANCH_UNKNOWN_MEMBER:${branch.id}:${member}`);
    }
  }
}

function validateConstraint(constraint: PreflightConstraint, index: Map<string, DesignVariable>): void {
  if (!constraint.id.trim()) throw new TypeError("CONSTRAINT_ID_REQUIRED");
  if (constraint.kind === "mutually-exclusive") {
    if (constraint.variables.length < 2) throw new RangeError(`MUTEX_NEEDS_TWO_VARIABLES:${constraint.id}`);
    for (const id of constraint.variables) {
      const variable = index.get(id);
      if (!variable) throw new RangeError(`CONSTRAINT_UNKNOWN_VARIABLE:${constraint.id}:${id}`);
      if (variable.kind !== "boolean") throw new TypeError(`MUTEX_NEEDS_BOOLEAN:${constraint.id}:${id}`);
    }
    return;
  }
  if (constraint.kind === "requires") {
    validatePredicate(constraint.when, index);
    validatePredicate(constraint.require, index);
    return;
  }
  if (constraint.kind === "relation") {
    validateExpression(constraint.expression, index);
    requireFinite(`relation:${constraint.id}`, constraint.limit);
    return;
  }
  if (constraint.kind === "count") {
    const countVariable = index.get(constraint.countVariable);
    if (!countVariable) throw new RangeError(`CONSTRAINT_UNKNOWN_VARIABLE:${constraint.id}`);
    if (countVariable.kind !== "integer") throw new TypeError(`COUNT_NEEDS_INTEGER:${constraint.id}`);
    const memberVariable = index.get(constraint.memberVariable);
    if (!memberVariable) throw new RangeError(`CONSTRAINT_UNKNOWN_VARIABLE:${constraint.id}`);
    if (memberVariable.kind !== "vector-profile") throw new TypeError(`COUNT_NEEDS_PROFILE_MEMBER:${constraint.id}`);
    return;
  }
  throw new TypeError(`UNKNOWN_CONSTRAINT_KIND:${(constraint as { kind: string }).kind}`);
}

function dependencyEdges(space: DesignSpace, index: Map<string, DesignVariable>): Map<string, ReadonlyArray<string>> {
  const edges = new Map<string, ReadonlyArray<string>>();
  for (const variable of space.variables) {
    const domain = variable.domain;
    if (domain.kind === "linked") edges.set(variable.id, [domain.targetVariable]);
    else if (domain.kind === "derived") edges.set(variable.id, expressionVariables(domain.expression).filter((id) => index.has(id)));
    else if (domain.kind === "vector-profile" && domain.lengthVariable) edges.set(variable.id, [domain.lengthVariable]);
    else edges.set(variable.id, []);
  }
  return edges;
}

function validateAcyclic(space: DesignSpace, index: Map<string, DesignVariable>): void {
  const edges = dependencyEdges(space, index);
  const state = new Map<string, "visiting" | "done">();
  const visit = (id: string): void => {
    const current = state.get(id);
    if (current === "done") return;
    if (current === "visiting") throw new RangeError(`DESIGN_SPACE_CYCLE:${id}`);
    state.set(id, "visiting");
    for (const next of edges.get(id) ?? []) visit(next);
    state.set(id, "done");
  };
  for (const id of edges.keys()) visit(id);
}

/** Validate a design space, failing closed on any structural inconsistency. */
export function validateDesignSpace(space: DesignSpace): void {
  if (!space.id.trim()) throw new TypeError("DESIGN_SPACE_ID_REQUIRED");
  if (!space.variables.length) throw new RangeError("DESIGN_SPACE_NEEDS_VARIABLES");
  const index = designIndex(space);
  if (index.size !== space.variables.length) throw new RangeError("DESIGN_SPACE_DUPLICATE_VARIABLE");
  for (const variable of space.variables) validateVariable(variable, index);
  for (const branch of space.branches ?? []) validateBranch(branch, index);
  for (const constraint of space.constraints ?? []) validateConstraint(constraint, index);
  validateAcyclic(space, index);
}

function rawScalar(variable: DesignVariable, state: DesignState): number | string | boolean | undefined {
  const entry = state[variable.id];
  if (!entry) return undefined;
  if (entry.kind === "number" || entry.kind === "dimensionless") {
    if (!NUMERIC_KINDS.has(variable.kind)) throw new TypeError(`STATE_KIND_MISMATCH:${variable.id}`);
    return entry.value;
  }
  if (entry.kind === "categorical") return entry.value;
  if (entry.kind === "boolean") return entry.value;
  return undefined;
}

function providedEntry(variable: DesignVariable, state: DesignState): boolean {
  return state[variable.id] !== undefined;
}

function toSI(id: string, value: number, unit: string | undefined): number {
  if (unit === undefined) {
    requireFinite(id, value);
    return Object.is(value, -0) ? 0 : value;
  }
  return normalizeQuantity(value, unit).valueSI;
}

interface Resolved {
  readonly raw: number | string | boolean;
  readonly valueSI?: number;
  readonly unit?: string;
}

function resolveValue(
  variable: DesignVariable,
  index: Map<string, DesignVariable>,
  state: DesignState,
  visiting: Set<string>,
): Resolved {
  if (visiting.has(variable.id)) throw new RangeError(`DESIGN_SPACE_CYCLE:${variable.id}`);
  visiting.add(variable.id);
  try {
    const entry = state[variable.id];
    if (entry) {
      if (entry.kind === "number") return { raw: entry.value, valueSI: toSI(variable.id, entry.value, entry.unit), unit: variable.unit };
      if (entry.kind === "dimensionless") return { raw: entry.value, valueSI: toSI(variable.id, entry.value, undefined) };
      if (entry.kind === "categorical") return { raw: entry.value };
      if (entry.kind === "boolean") return { raw: entry.value };
      throw new TypeError(`STATE_KIND_MISMATCH:${variable.id}`);
    }
    const domain = variable.domain;
    if (domain.kind === "linked") {
      const target = index.get(domain.targetVariable);
      if (!target) throw new RangeError(`LINKED_UNKNOWN_TARGET:${variable.id}`);
      const resolved = resolveValue(target, index, state, visiting);
      if (typeof resolved.valueSI !== "number") throw new TypeError(`LINKED_TARGET_NOT_NUMERIC:${variable.id}`);
      const value = resolved.valueSI * (domain.scale ?? 1) + (domain.offset ?? 0);
      return { raw: value, valueSI: Object.is(value, -0) ? 0 : value, unit: resolved.unit };
    }
    if (domain.kind === "derived") {
      const value = evaluateExpression(domain.expression, index, state, visiting);
      return { raw: value, valueSI: value, unit: variable.unit };
    }
    if (variable.baseValue !== undefined) {
      if (typeof variable.baseValue === "number") {
        return { raw: variable.baseValue, valueSI: toSI(variable.id, variable.baseValue, variable.unit), unit: variable.unit };
      }
      return { raw: variable.baseValue };
    }
    throw new RangeError(`MISSING_VARIABLE_VALUE:${variable.id}`);
  } finally {
    visiting.delete(variable.id);
  }
}

function evaluateExpression(
  expression: DesignExpression,
  index: Map<string, DesignVariable>,
  state: DesignState,
  visiting: Set<string>,
): number {
  if (expression.op === "constant") return expression.value;
  if (expression.op === "variable") {
    const variable = index.get(expression.variable);
    if (!variable) throw new RangeError(`EXPRESSION_UNKNOWN_VARIABLE:${expression.variable}`);
    const resolved = resolveValue(variable, index, state, visiting);
    if (typeof resolved.valueSI !== "number") throw new TypeError(`EXPRESSION_NEEDS_NUMERIC:${expression.variable}`);
    return resolved.valueSI;
  }
  const left = evaluateExpression(expression.left, index, state, visiting);
  const right = evaluateExpression(expression.right, index, state, visiting);
  switch (expression.op) {
    case "add":
      return left + right;
    case "subtract":
      return left - right;
    case "multiply":
      return left * right;
    case "divide":
      if (right === 0) throw new RangeError("EXPRESSION_DIVISION_BY_ZERO");
      return left / right;
    default:
      throw new TypeError("UNKNOWN_EXPRESSION_OP");
  }
}

function evaluatePredicate(
  predicate: DesignPredicate,
  index: Map<string, DesignVariable>,
  state: DesignState,
  depth = 0,
): boolean {
  if (depth > 64) throw new RangeError("PREDICATE_DEPTH_EXCEEDED");
  if (predicate.op === "all") return predicate.clauses.every((clause) => evaluatePredicate(clause, index, state, depth + 1));
  if (predicate.op === "any") return predicate.clauses.some((clause) => evaluatePredicate(clause, index, state, depth + 1));
  if (predicate.op === "not") return !evaluatePredicate(predicate.clause, index, state, depth + 1);
  const variable = index.get(predicate.variable);
  if (!variable) throw new RangeError(`PREDICATE_UNKNOWN_VARIABLE:${predicate.variable}`);
  if (predicate.op === "equals" || predicate.op === "in") {
    const resolved = resolveValue(variable, index, state, new Set());
    const values = predicate.op === "equals" ? [predicate.value] : predicate.values;
    return values.some((value) => resolved.raw === value);
  }
  const resolved = resolveValue(variable, index, state, new Set());
  if (typeof resolved.valueSI !== "number") throw new TypeError(`COMPARISON_NEEDS_NUMERIC:${predicate.variable}`);
  switch (predicate.op) {
    case "lessThan":
      return resolved.valueSI < predicate.valueSI;
    case "lessOrEqual":
      return resolved.valueSI <= predicate.valueSI;
    case "greaterThan":
      return resolved.valueSI > predicate.valueSI;
    case "greaterOrEqual":
      return resolved.valueSI >= predicate.valueSI;
    default:
      throw new TypeError("UNKNOWN_PREDICATE_OP");
  }
}

function branchMembership(space: DesignSpace): Map<string, ReadonlyArray<DesignBranch>> {
  const membership = new Map<string, DesignBranch[]>();
  for (const branch of space.branches ?? []) {
    for (const members of Object.values(branch.options)) {
      for (const member of members) {
        const list = membership.get(member) ?? [];
        list.push(branch);
        membership.set(member, list);
      }
    }
  }
  return membership;
}

function branchAllows(
  variableId: string,
  branches: ReadonlyArray<DesignBranch>,
  index: Map<string, DesignVariable>,
  state: DesignState,
): boolean {
  for (const branch of branches) {
    const selector = index.get(branch.selector);
    if (!selector) throw new RangeError(`BRANCH_UNKNOWN_SELECTOR:${branch.id}`);
    const resolved = resolveValue(selector, index, state, new Set());
    const selected = branch.options[String(resolved.raw)] ?? [];
    if (!selected.includes(variableId)) return false;
  }
  return true;
}

/** Determine which variables are active; inactive ones are preserved as lineage. */
export function activeVariableIds(space: DesignSpace, state: DesignState): ReadonlyArray<string> {
  const index = designIndex(space);
  const membership = branchMembership(space);
  const memo = new Map<string, boolean>();
  const isActive = (id: string, visiting: Set<string>): boolean => {
    const remembered = memo.get(id);
    if (remembered !== undefined) return remembered;
    if (visiting.has(id)) throw new RangeError(`DESIGN_SPACE_ACTIVATION_CYCLE:${id}`);
    visiting.add(id);
    const variable = index.get(id);
    if (!variable) throw new RangeError(`UNKNOWN_VARIABLE:${id}`);
    let active = branchAllows(id, membership.get(id) ?? [], index, state);
    if (active && variable.activeWhen) active = evaluatePredicate(variable.activeWhen, index, state);
    const domain = variable.domain;
    if (active && domain.kind === "linked") active = isActive(domain.targetVariable, visiting);
    if (active && domain.kind === "derived") {
      active = expressionVariables(domain.expression).every((dependency) => isActive(dependency, visiting));
    }
    if (active && domain.kind === "vector-profile" && domain.lengthVariable) {
      active = isActive(domain.lengthVariable, visiting);
    }
    visiting.delete(id);
    memo.set(id, active);
    return active;
  };
  return Object.freeze(space.variables.filter((variable) => isActive(variable.id, new Set())).map((variable) => variable.id));
}

function profilePointSIBounds(variable: DesignVariable, point: ProfileControlPoint): { lower: number; upper: number } {
  return { lower: toSI(variable.id, point.lower, variable.unit), upper: toSI(variable.id, point.upper, variable.unit) };
}

function effectiveProfileLength(
  variable: DesignVariable,
  index: Map<string, DesignVariable>,
  state: DesignState,
): number {
  const domain = variable.domain as Extract<DesignDomain, { kind: "vector-profile" }>;
  if (!domain.lengthVariable) return domain.controlPoints.length;
  const lengthVariable = index.get(domain.lengthVariable);
  if (!lengthVariable) throw new RangeError(`PROFILE_LENGTH_UNKNOWN_VARIABLE:${variable.id}`);
  const resolved = resolveValue(lengthVariable, index, state, new Set());
  if (typeof resolved.raw !== "number") throw new TypeError(`PROFILE_LENGTH_NEEDS_INTEGER:${variable.id}`);
  return Math.trunc(resolved.raw);
}

function domainViolations(
  variable: DesignVariable,
  index: Map<string, DesignVariable>,
  state: DesignState,
): string[] {
  const violations: string[] = [];
  const domain = variable.domain;
  switch (domain.kind) {
    case "continuous": {
      const resolved = resolveValue(variable, index, state, new Set());
      const value = resolved.valueSI;
      if (typeof value !== "number") return [`${variable.id}:VALUE_NOT_NUMERIC`];
      const lower = toSI(variable.id, domain.lower, variable.unit);
      const upper = toSI(variable.id, domain.upper, variable.unit);
      if (value < lower || value > upper) violations.push(`${variable.id}:OUT_OF_BOUNDS`);
      break;
    }
    case "integer": {
      const resolved = resolveValue(variable, index, state, new Set());
      const value = resolved.valueSI;
      if (typeof value !== "number" || !Number.isInteger(resolved.raw)) return [`${variable.id}:VALUE_NOT_INTEGER`];
      const lower = toSI(variable.id, domain.lower, variable.unit);
      const upper = toSI(variable.id, domain.upper, variable.unit);
      if (value < lower || value > upper) violations.push(`${variable.id}:OUT_OF_BOUNDS`);
      break;
    }
    case "discrete": {
      const resolved = resolveValue(variable, index, state, new Set());
      if (typeof resolved.valueSI !== "number") return [`${variable.id}:VALUE_NOT_NUMERIC`];
      const allowed = domain.values.map((value) => toSI(variable.id, value, variable.unit));
      if (!allowed.some((value) => value === resolved.valueSI)) violations.push(`${variable.id}:NOT_A_DISCRETE_VALUE`);
      break;
    }
    case "categorical": {
      const raw = resolveValue(variable, index, state, new Set()).raw;
      if (typeof raw !== "string") violations.push(`${variable.id}:VALUE_NOT_CATEGORICAL`);
      else if (!domain.values.includes(raw)) violations.push(`${variable.id}:NOT_A_CATEGORICAL_VALUE`);
      break;
    }
    case "boolean":
      if (typeof resolveValue(variable, index, state, new Set()).raw !== "boolean") violations.push(`${variable.id}:VALUE_NOT_BOOLEAN`);
      break;
    case "vector-profile": {
      const length = effectiveProfileLength(variable, index, state);
      if (length < 1 || length > domain.controlPoints.length) violations.push(`${variable.id}:PROFILE_LENGTH_OUT_OF_RANGE`);
      const entry = state[variable.id];
      if (entry && entry.kind !== "vector-profile") violations.push(`${variable.id}:STATE_KIND_MISMATCH`);
      const points = entry?.kind === "vector-profile" ? entry.points : undefined;
      if (points) {
        for (const point of points) {
          const control = domain.controlPoints.find((item) => item.id === point.id);
          if (!control) {
            violations.push(`${variable.id}:UNKNOWN_PROFILE_POINT:${point.id}`);
            continue;
          }
          const unit = point.unit ?? variable.unit;
          const value = toSI(variable.id, point.value, unit);
          const bounds = profilePointSIBounds(variable, control);
          if (value < bounds.lower || value > bounds.upper) violations.push(`${variable.id}:PROFILE_POINT_OUT_OF_BOUNDS:${point.id}`);
        }
      }
      break;
    }
    case "linked":
    case "derived":
      try {
        resolveValue(variable, index, state, new Set());
      } catch {
        violations.push(`${variable.id}:UNRESOLVED`);
      }
      break;
    default:
      violations.push(`${variable.id}:UNKNOWN_KIND`);
  }
  return violations;
}

function constraintViolations(space: DesignSpace, index: Map<string, DesignVariable>, state: DesignState): string[] {
  const violations: string[] = [];
  for (const constraint of space.constraints ?? []) {
    if (constraint.kind === "mutually-exclusive") {
      const truths = constraint.variables.filter((id) => {
        const variable = index.get(id);
        return variable ? resolveValue(variable, index, state, new Set()).raw === true : false;
      });
      if (truths.length > 1) violations.push(`${constraint.id}:MUTUALLY_EXCLUSIVE_VIOLATION`);
    } else if (constraint.kind === "requires") {
      if (evaluatePredicate(constraint.when, index, state) && !evaluatePredicate(constraint.require, index, state)) {
        violations.push(`${constraint.id}:REQUIRED_CONDITION_UNMET`);
      }
    } else if (constraint.kind === "relation") {
      const value = evaluateExpression(constraint.expression, index, state, new Set());
      if (constraint.relation === "lessOrEqual" && value > constraint.limit) violations.push(`${constraint.id}:RELATION_VIOLATION`);
      if (constraint.relation === "greaterOrEqual" && value < constraint.limit) violations.push(`${constraint.id}:RELATION_VIOLATION`);
      if (constraint.relation === "equal" && Math.abs(value - constraint.limit) > 1e-9) violations.push(`${constraint.id}:RELATION_VIOLATION`);
    } else if (constraint.kind === "count") {
      const member = index.get(constraint.memberVariable);
      const count = resolveValue(index.get(constraint.countVariable) as DesignVariable, index, state, new Set()).raw;
      if (member && typeof count === "number") {
        const entry = state[member.id];
        const provided = entry?.kind === "vector-profile" && entry.points ? entry.points.length : undefined;
        const actual = provided ?? effectiveProfileLength(member, index, state);
        if (actual !== Math.trunc(count)) violations.push(`${constraint.id}:COUNT_MISMATCH`);
      }
    }
  }
  return violations;
}

/** Cheap structural checks evaluated before any physics. */
export function preflightDesignState(space: DesignSpace, state: DesignState): ReadonlyArray<string> {
  const index = designIndex(space);
  for (const id of Object.keys(state)) {
    if (!index.has(id)) throw new RangeError(`STATE_UNKNOWN_VARIABLE:${id}`);
  }
  const active = new Set(activeVariableIds(space, state));
  const violations: string[] = [];
  for (const variable of space.variables) {
    if (!active.has(variable.id)) continue;
    const computed = variable.kind === "linked" || variable.kind === "derived" || variable.kind === "vector-profile";
    if (!providedEntry(variable, state) && variable.baseValue === undefined && !computed) {
      violations.push(`${variable.id}:MISSING_VALUE`);
      continue;
    }
    violations.push(...domainViolations(variable, index, state));
  }
  violations.push(...constraintViolations(space, index, state));
  return Object.freeze(violations);
}

/** Deterministic unit-normalized view consumed by search/optimization code. */
export function flattenDesignState(space: DesignSpace, state: DesignState): FlatDesignState {
  validateDesignSpace(space);
  const violations = preflightDesignState(space, state);
  if (violations.length) throw new RangeError(`DESIGN_SPACE_PREFLIGHT_FAILED:${violations.join("; ")}`);
  const index = designIndex(space);
  const active = new Set(activeVariableIds(space, state));
  const entries: FlatDesignEntry[] = [];
  for (const variable of space.variables) {
    const isActive = active.has(variable.id);
    const lineage = isActive ? [] : [variable.id];
    const base: Omit<FlatDesignEntry, "kind" | "active" | "provided" | "lineage" | "bindings"> = { id: variable.id, unit: variable.unit };
    const bindings = variable.bindings;
    if (!isActive) {
      entries.push({ ...base, kind: variable.kind, active: false, provided: providedEntry(variable, state), lineage, bindings });
      continue;
    }
    const provided = providedEntry(variable, state);
    if (variable.kind === "vector-profile") {
      const domain = variable.domain as Extract<DesignDomain, { kind: "vector-profile" }>;
      const length = effectiveProfileLength(variable, index, state);
      const entry = state[variable.id];
      const statePoints = entry?.kind === "vector-profile" ? entry.points : undefined;
      const points: FlatProfilePoint[] = [];
      for (let position = 0; position < length; position += 1) {
        const control = domain.controlPoints[position];
        const statePoint = statePoints?.find((item) => item.id === control.id);
        const rawValue = statePoint ? statePoint.value : control.baseValue;
        const unit = statePoint?.unit ?? variable.unit;
        points.push({ id: control.id, valueSI: toSI(variable.id, rawValue, unit), rawValue, ...(unit !== undefined ? { unit } : {}) });
      }
      entries.push({ ...base, kind: variable.kind, active: true, provided, lineage, bindings, points });
      continue;
    }
    const resolved = resolveValue(variable, index, state, new Set());
    const entry: FlatDesignEntry = { ...base, kind: variable.kind, active: true, provided, lineage, bindings };
    if (typeof resolved.raw === "number" && (NUMERIC_KINDS.has(variable.kind) || variable.kind === "linked" || variable.kind === "derived")) {
      entries.push({ ...entry, value: resolved.raw, valueSI: resolved.valueSI });
    } else {
      entries.push({ ...entry, value: resolved.raw });
    }
  }
  return Object.freeze({
    spaceId: space.id,
    order: Object.freeze(entries.filter((entry) => entry.active).map((entry) => entry.id)),
    entries: Object.freeze(entries),
    inactive: Object.freeze(entries.filter((entry) => !entry.active).map((entry) => entry.id)),
  });
}

/** Reverse a flattened view back into hierarchical design state. */
export function unflattenDesignState(space: DesignSpace, flat: FlatDesignState): DesignState {
  const index = designIndex(space);
  const result: Record<string, DesignStateValue> = {};
  for (const entry of flat.entries) {
    if (!entry.provided) continue;
    if (entry.kind === "linked" || entry.kind === "derived") continue;
    const variable = index.get(entry.id);
    if (!variable) throw new RangeError(`UNKNOWN_VARIABLE:${entry.id}`);
    if (entry.kind === "vector-profile") {
      result[entry.id] = {
        kind: "vector-profile",
        points: (entry.points ?? []).map((point) => ({
          id: point.id,
          value: point.rawValue,
          ...(point.unit !== undefined ? { unit: point.unit } : {}),
        })),
      };
      continue;
    }
    if (entry.kind === "categorical") {
      result[entry.id] = { kind: "categorical", value: String(entry.value) };
    } else if (entry.kind === "boolean") {
      result[entry.id] = { kind: "boolean", value: Boolean(entry.value) };
    } else if (entry.unit !== undefined) {
      result[entry.id] = { kind: "number", value: Number(entry.value), unit: entry.unit };
    } else {
      result[entry.id] = { kind: "dimensionless", value: Number(entry.value) };
    }
  }
  return result;
}

/** Stable hash of the active evaluation view; key order and unit choice do not matter. */
export function candidateHash(flat: FlatDesignState): string {
  const byId = new Map(flat.entries.map((entry) => [entry.id, entry]));
  const variables = flat.order.map((id) => {
    const entry = byId.get(id);
    if (!entry) throw new RangeError(`UNKNOWN_VARIABLE:${id}`);
    const payload: Record<string, unknown> = { id: entry.id, kind: entry.kind };
    if (entry.unit !== undefined) payload.unit = entry.unit;
    if (entry.valueSI !== undefined) payload.valueSI = entry.valueSI;
    if ((entry.kind === "categorical" || entry.kind === "boolean") && entry.value !== undefined) {
      payload.value = entry.value;
    }
    if (entry.points !== undefined) payload.points = entry.points.map((point) => ({ id: point.id, valueSI: point.valueSI }));
    return payload;
  });
  return contentDigest({ space: flat.spaceId, variables });
}
