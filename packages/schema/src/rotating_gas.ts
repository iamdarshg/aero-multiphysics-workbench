/**
 * Canonical rotating-gas-machine architecture: gas path, stations, rows, shafts.
 *
 * This is the TypeScript mirror of
 * `packages/turbomachinery/aeroworkbench_turbomachinery/`. The canonical
 * serialization and `architectureHash` are byte-for-byte identical to the Python
 * `canonical_architecture` / `architecture_hash`, which is the cross-language
 * contract proven by the shared fixtures.
 *
 * Topology changes are projected onto the existing design-section vocabulary
 * (`topologyDigest`, `geometry`, `motionFrames`, `materials`, `operatingPoints`,
 * `parameters`) so the existing `invalidatedNodes` table invalidates
 * geometry/mesh/analysis/interfaces/optimization descendants without a parallel
 * framework.
 */

import { contentDigest } from "../../cache/src/content-addressed.ts";
import { invalidatedNodes } from "./design.ts";

export const SCHEMA_VERSION = 1;

export const FLOW_NODE_KINDS = [
  "ambient",
  "inlet",
  "intake",
  "duct",
  "plenum",
  "mixer",
  "splitter",
  "rotor_row",
  "stator_row",
  "diffuser",
  "compressor_stage",
  "fan_stage",
  "turbine_stage",
  "expander_stage",
  "combustor",
  "heat_addition",
  "heat_exchanger",
  "recuperator",
  "intercooler",
  "nozzle",
  "exhaust",
  "bleed_extract",
  "cooling_inject",
  "bypass_split",
  "core_split",
  "bypass_merge",
  "core_merge",
] as const;
export const MECHANICAL_NODE_KINDS = ["shaft_spool", "mechanical_load"] as const;
export const ELECTRICAL_NODE_KINDS = ["motor_coupling", "generator_coupling"] as const;
export const NODE_KINDS = [...FLOW_NODE_KINDS, ...MECHANICAL_NODE_KINDS, ...ELECTRICAL_NODE_KINDS] as const;
export const FLOW_EDGE_KINDS = ["flow", "bleed", "cooling", "bypass", "core"] as const;
export const COUPLING_EDGE_KINDS = ["mechanical", "electrical"] as const;
export const EDGE_KINDS = [...FLOW_EDGE_KINDS, ...COUPLING_EDGE_KINDS] as const;

export const ROW_ROLES = ["work_adding", "work_extracting", "turning_only", "diffuser_guide"] as const;
export const ROW_FRAMES = ["rotating", "stationary"] as const;
export const FLOW_FAMILIES = ["axial", "radial", "mixed"] as const;
export const SHAFT_KINDS = ["single", "common", "free_power"] as const;
export const COUPLING_KINDS = [
  "common_shaft",
  "geared",
  "electric_motor",
  "electric_generator",
  "mechanical_load",
] as const;

export type FlowNodeKind = (typeof FLOW_NODE_KINDS)[number];
export type MechanicalNodeKind = (typeof MECHANICAL_NODE_KINDS)[number];
export type ElectricalNodeKind = (typeof ELECTRICAL_NODE_KINDS)[number];
export type NodeKind = (typeof NODE_KINDS)[number];
export type EdgeKind = (typeof EDGE_KINDS)[number];
export type RowRole = (typeof ROW_ROLES)[number];
export type RowFrame = (typeof ROW_FRAMES)[number];
export type FlowFamily = (typeof FLOW_FAMILIES)[number];
export type ShaftKind = (typeof SHAFT_KINDS)[number];
export type CouplingKind = (typeof COUPLING_KINDS)[number];

export interface Quantity {
  readonly valueSI: number;
  readonly dimension: string;
}

export interface WorkingFluid {
  readonly identity: string;
  readonly composition: Readonly<Record<string, number>>;
}

export interface AnnulusGeometryRef {
  readonly area: Quantity | null;
  readonly radius: Quantity | null;
  readonly hubRadius: Quantity | null;
  readonly tipRadius: Quantity | null;
  readonly geometryRef: string | null;
}

export interface StationState {
  readonly massFlow: Quantity | null;
  readonly totalPressure: Quantity | null;
  readonly staticPressure: Quantity | null;
  readonly totalTemperature: Quantity | null;
  readonly staticTemperature: Quantity | null;
  readonly density: Quantity | null;
  readonly velocity: Quantity | null;
  readonly mach: Quantity | null;
  readonly tangentialVelocity: Quantity | null;
  readonly swirlAngle: Quantity | null;
  readonly fluid: WorkingFluid | null;
  readonly annulus: AnnulusGeometryRef | null;
}

export interface Station {
  readonly id: string;
  readonly name: string | null;
  readonly state: StationState;
}

export interface GasPathNode {
  readonly id: string;
  readonly kind: NodeKind;
  readonly label: string | null;
}

export interface GasPathEdge {
  readonly from: string;
  readonly to: string;
  readonly kind: EdgeKind;
  readonly station: string | null;
}

export interface BladeClearance {
  readonly tipClearance: Quantity | null;
  readonly endwallState: string | null;
  readonly shroudState: string | null;
}

export interface BladeRow {
  readonly id: string;
  readonly node: string;
  readonly role: RowRole;
  readonly frame: RowFrame;
  readonly shaft: string | null;
  readonly stationIn: string;
  readonly stationOut: string;
  readonly rowCount: number;
  readonly periodicity: number;
  readonly family: FlowFamily;
  readonly geometryRef: string | null;
  readonly clearance: BladeClearance;
  readonly materialRef: string | null;
  readonly thermalRef: string | null;
}

export interface SpeedBound {
  readonly kind: "speed" | "torque";
  readonly value: Quantity;
}

export interface ShaftCoupling {
  readonly id: string;
  readonly kind: CouplingKind;
  readonly targetShaft: string | null;
  readonly targetNode: string | null;
  readonly ratio: number | null;
  readonly efficiency: number | null;
}

export interface Shaft {
  readonly id: string;
  readonly kind: ShaftKind;
  readonly members: readonly string[];
  readonly speed: SpeedBound | null;
  readonly mechanicalLossFraction: number;
  readonly couplings: readonly ShaftCoupling[];
}

export interface RotatingGasArchitecture {
  readonly schemaVersion: number;
  readonly architectureId: string;
  readonly defaultFluid: WorkingFluid | null;
  readonly nodes: readonly GasPathNode[];
  readonly edges: readonly GasPathEdge[];
  readonly stations: readonly Station[];
  readonly rows: readonly BladeRow[];
  readonly shafts: readonly Shaft[];
}

const ROLE_ALLOWED_NODE_KINDS: Readonly<Record<RowRole, readonly string[]>> = Object.freeze({
  work_adding: ["rotor_row", "compressor_stage", "fan_stage"],
  work_extracting: ["rotor_row", "turbine_stage", "expander_stage"],
  turning_only: ["stator_row"],
  diffuser_guide: ["stator_row", "diffuser"],
});

const COUPLING_TARGET_NODE_KIND: Readonly<Record<string, string>> = Object.freeze({
  electric_motor: "motor_coupling",
  electric_generator: "generator_coupling",
  mechanical_load: "mechanical_load",
});

// unit label -> [dimension, scale to SI, offset to SI]: si = value * scale + offset
const UNIT_TABLE: Readonly<Record<string, readonly [string, number, number]>> = Object.freeze({
  dimensionless: ["dimensionless", 1, 0],
  "kg/s": ["mass_flow", 1, 0],
  "kg/h": ["mass_flow", 1 / 3600, 0],
  Pa: ["pressure", 1, 0],
  kPa: ["pressure", 1e3, 0],
  MPa: ["pressure", 1e6, 0],
  bar: ["pressure", 1e5, 0],
  K: ["temperature", 1, 0],
  degC: ["temperature", 1, 273.15],
  "kg/m3": ["density", 1, 0],
  "m/s": ["velocity", 1, 0],
  m: ["length", 1, 0],
  mm: ["length", 1e-3, 0],
  m2: ["area", 1, 0],
  cm2: ["area", 1e-4, 0],
  W: ["power", 1, 0],
  kW: ["power", 1e3, 0],
  MW: ["power", 1e6, 0],
  "N.m": ["torque", 1, 0],
  rpm: ["rotational_speed", 1 / 60, 0],
  "rev/s": ["rotational_speed", 1, 0],
  "rad/s": ["rotational_speed", 1 / (2 * Math.PI), 0],
  deg: ["angle", Math.PI / 180, 0],
  rad: ["angle", 1, 0],
  s: ["time", 1, 0],
});

function canonicalNumber(value: number): number {
  if (!Number.isFinite(value)) throw new TypeError("NONFINITE_CANONICAL_VALUE");
  return Object.is(value, -0) ? 0 : value;
}

function asObject(value: unknown, label: string): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new TypeError(`EXPECTED_OBJECT:${label}`);
  }
  return value as Record<string, unknown>;
}

function asArray(value: unknown, label: string): unknown[] {
  if (!Array.isArray(value)) throw new TypeError(`EXPECTED_ARRAY:${label}`);
  return value;
}

function requireString(value: unknown, label: string): string {
  if (typeof value !== "string" || value.trim() === "") {
    throw new TypeError(`EXPECTED_NONEMPTY_STRING:${label}`);
  }
  return value;
}

function optionalString(value: unknown, label: string): string | null {
  if (value === null || value === undefined) return null;
  if (typeof value !== "string") throw new TypeError(`EXPECTED_STRING:${label}`);
  return value;
}

function requireNumber(value: unknown, label: string): number {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    throw new TypeError(`EXPECTED_NUMBER:${label}`);
  }
  return value;
}

function optionalNumber(value: unknown, label: string): number | null {
  if (value === null || value === undefined) return null;
  return requireNumber(value, label);
}

function requireInteger(value: unknown, label: string, fallback: number): number {
  if (value === null || value === undefined) return fallback;
  if (typeof value !== "number" || !Number.isInteger(value)) {
    throw new TypeError(`EXPECTED_INTEGER:${label}`);
  }
  return value;
}

function requireEnum<T extends string>(value: unknown, allowed: readonly T[], label: string): T {
  const text = requireString(value, label);
  if (!(allowed as readonly string[]).includes(text)) {
    throw new RangeError(`UNKNOWN_${label}:${text}`);
  }
  return text as T;
}

function parseQuantity(value: unknown, label: string, dimension?: string): Quantity | null {
  if (value === null || value === undefined) return null;
  const item = asObject(value, label);
  if ("value" in item && "unit" in item) {
    const raw = requireNumber(item.value, label);
    const unit = requireString(item.unit, `${label}.unit`);
    const definition = UNIT_TABLE[unit];
    if (!definition) throw new RangeError(`UNKNOWN_UNIT:${unit}`);
    if (dimension !== undefined && definition[0] !== dimension) {
      throw new TypeError(`QUANTITY_DIMENSION_MISMATCH:${label}:${definition[0]}:${dimension}`);
    }
    return { valueSI: canonicalNumber(raw * definition[1] + definition[2]), dimension: definition[0] };
  }
  if ("valueSI" in item && "dimension" in item) {
    const raw = requireNumber(item.valueSI, label);
    const canonicalDimension = requireString(item.dimension, `${label}.dimension`);
    if (dimension !== undefined && canonicalDimension !== dimension) {
      throw new TypeError(`QUANTITY_DIMENSION_MISMATCH:${label}:${canonicalDimension}:${dimension}`);
    }
    return { valueSI: canonicalNumber(raw), dimension: canonicalDimension };
  }
  throw new TypeError(`QUANTITY_NEEDS_VALUE_AND_UNIT:${label}`);
}

function parseFluid(value: unknown, label: string): WorkingFluid | null {
  if (value === null || value === undefined) return null;
  const item = asObject(value, label);
  const compositionSource = item.composition === undefined || item.composition === null
    ? {}
    : asObject(item.composition, `${label}.composition`);
  const composition: Record<string, number> = {};
  const species: string[] = [];
  for (const [name, fraction] of Object.entries(compositionSource)) {
    const numeric = requireNumber(fraction, `${label}.composition.${name}`);
    if (numeric < 0 || numeric > 1) throw new TypeError(`INVALID_MASS_FRACTION:${name}`);
    composition[name] = numeric;
    species.push(name);
  }
  if (species.length > 0) {
    const total = species.reduce((sum, name) => sum + composition[name], 0);
    if (Math.abs(total - 1) > 1e-6) throw new TypeError("MASS_FRACTIONS_MUST_SUM_TO_ONE");
  }
  return { identity: requireString(item.identity, `${label}.identity`), composition };
}

function parseAnnulus(value: unknown, label: string): AnnulusGeometryRef | null {
  if (value === null || value === undefined) return null;
  const item = asObject(value, label);
  const annulus: AnnulusGeometryRef = {
    area: parseQuantity(item.area, `${label}.area`, "area"),
    radius: parseQuantity(item.radius, `${label}.radius`, "length"),
    hubRadius: parseQuantity(item.hubRadius, `${label}.hubRadius`, "length"),
    tipRadius: parseQuantity(item.tipRadius, `${label}.tipRadius`, "length"),
    geometryRef: optionalString(item.geometryRef, `${label}.geometryRef`),
  };
  if (annulus.hubRadius && annulus.tipRadius && annulus.hubRadius.valueSI >= annulus.tipRadius.valueSI) {
    throw new TypeError("HUB_RADIUS_MUST_BE_SMALLER_THAN_TIP_RADIUS");
  }
  return annulus;
}

function parseState(value: unknown, label: string): StationState {
  const item = asObject(value, label);
  return {
    massFlow: parseQuantity(item.massFlow, `${label}.massFlow`, "mass_flow"),
    totalPressure: parseQuantity(item.totalPressure, `${label}.totalPressure`, "pressure"),
    staticPressure: parseQuantity(item.staticPressure, `${label}.staticPressure`, "pressure"),
    totalTemperature: parseQuantity(item.totalTemperature, `${label}.totalTemperature`, "temperature"),
    staticTemperature: parseQuantity(item.staticTemperature, `${label}.staticTemperature`, "temperature"),
    density: parseQuantity(item.density, `${label}.density`, "density"),
    velocity: parseQuantity(item.velocity, `${label}.velocity`, "velocity"),
    mach: parseQuantity(item.mach, `${label}.mach`, "dimensionless"),
    tangentialVelocity: parseQuantity(item.tangentialVelocity, `${label}.tangentialVelocity`, "velocity"),
    swirlAngle: parseQuantity(item.swirlAngle, `${label}.swirlAngle`, "angle"),
    fluid: parseFluid(item.fluid, `${label}.fluid`),
    annulus: parseAnnulus(item.annulus, `${label}.annulus`),
  };
}

function parseStation(value: unknown, label: string): Station {
  const item = asObject(value, label);
  const state = item.state === undefined || item.state === null ? {} : item.state;
  return {
    id: requireString(item.id, `${label}.id`),
    name: optionalString(item.name, `${label}.name`),
    state: parseState(state, `${label}.state`),
  };
}

function parseNode(value: unknown, label: string): GasPathNode {
  const item = asObject(value, label);
  return {
    id: requireString(item.id, `${label}.id`),
    kind: requireEnum(item.kind, NODE_KINDS, `${label}.kind`) as NodeKind,
    label: optionalString(item.label, `${label}.label`),
  };
}

function parseEdge(value: unknown, label: string): GasPathEdge {
  const item = asObject(value, label);
  return {
    from: requireString(item.from, `${label}.from`),
    to: requireString(item.to, `${label}.to`),
    kind: requireEnum(item.kind, EDGE_KINDS, `${label}.kind`) as EdgeKind,
    station: optionalString(item.station, `${label}.station`),
  };
}

function parseClearance(value: unknown, label: string): BladeClearance {
  if (value === null || value === undefined) {
    return { tipClearance: null, endwallState: null, shroudState: null };
  }
  const item = asObject(value, label);
  return {
    tipClearance: parseQuantity(item.tipClearance, `${label}.tipClearance`, "length"),
    endwallState: optionalString(item.endwallState, `${label}.endwallState`),
    shroudState: optionalString(item.shroudState, `${label}.shroudState`),
  };
}

function parseRow(value: unknown, label: string): BladeRow {
  const item = asObject(value, label);
  const row: BladeRow = {
    id: requireString(item.id, `${label}.id`),
    node: requireString(item.node, `${label}.node`),
    role: requireEnum(item.role, ROW_ROLES, `${label}.role`) as RowRole,
    frame: requireEnum(item.frame, ROW_FRAMES, `${label}.frame`) as RowFrame,
    shaft: optionalString(item.shaft, `${label}.shaft`),
    stationIn: requireString(item.stationIn, `${label}.stationIn`),
    stationOut: requireString(item.stationOut, `${label}.stationOut`),
    rowCount: requireInteger(item.rowCount, `${label}.rowCount`, 1),
    periodicity: requireInteger(item.periodicity, `${label}.periodicity`, 1),
    family: item.family === undefined ? "axial" : (requireEnum(item.family, FLOW_FAMILIES, `${label}.family`) as FlowFamily),
    geometryRef: optionalString(item.geometryRef, `${label}.geometryRef`),
    clearance: parseClearance(item.clearance, `${label}.clearance`),
    materialRef: optionalString(item.materialRef, `${label}.materialRef`),
    thermalRef: optionalString(item.thermalRef, `${label}.thermalRef`),
  };
  if (row.rowCount < 1 || row.periodicity < 1) {
    throw new TypeError(`INVALID_ROW_COUNT_OR_PERIODICITY:${row.id}`);
  }
  if (row.frame === "rotating" && !row.shaft) throw new TypeError(`ROTATING_ROW_NEEDS_SHAFT:${row.id}`);
  if (row.frame === "stationary" && row.shaft) throw new TypeError(`STATIONARY_ROW_HAS_SHAFT:${row.id}`);
  if ((row.role === "work_adding" || row.role === "work_extracting") && row.frame !== "rotating") {
    throw new TypeError(`WORK_ROW_MUST_ROTATE:${row.id}`);
  }
  if (row.role === "diffuser_guide" && row.frame !== "stationary") {
    throw new TypeError(`DIFFUSER_GUIDE_MUST_BE_STATIONARY:${row.id}`);
  }
  return row;
}

function parseSpeed(value: unknown, label: string): SpeedBound | null {
  if (value === null || value === undefined) return null;
  const item = asObject(value, label);
  const kind = requireEnum(item.kind, ["speed", "torque"] as const, `${label}.kind`);
  const quantity = parseQuantity(
    item.value,
    `${label}.value`,
    kind === "speed" ? "rotational_speed" : "torque",
  );
  if (!quantity) throw new TypeError(`SPEED_BOUND_NEEDS_VALUE:${label}`);
  return { kind, value: quantity };
}

function parseCoupling(value: unknown, label: string): ShaftCoupling {
  const item = asObject(value, label);
  const kind = requireEnum(item.kind, COUPLING_KINDS, `${label}.kind`) as CouplingKind;
  const coupling: ShaftCoupling = {
    id: requireString(item.id, `${label}.id`),
    kind,
    targetShaft: optionalString(item.targetShaft, `${label}.targetShaft`),
    targetNode: optionalString(item.targetNode, `${label}.targetNode`),
    ratio: optionalNumber(item.ratio, `${label}.ratio`),
    efficiency: optionalNumber(item.efficiency, `${label}.efficiency`),
  };
  if (kind === "common_shaft" || kind === "geared") {
    if (!coupling.targetShaft) throw new TypeError(`COUPLING_NEEDS_TARGET_SHAFT:${coupling.id}`);
    if (coupling.targetNode) throw new TypeError(`SHAFT_COUPLING_HAS_NODE_TARGET:${coupling.id}`);
    if (kind === "geared" && (coupling.ratio === null || coupling.ratio <= 0)) {
      throw new TypeError(`GEARED_COUPLING_NEEDS_POSITIVE_RATIO:${coupling.id}`);
    }
    if (kind === "common_shaft" && coupling.ratio !== null) {
      throw new TypeError(`COMMON_SHAFT_COUPLING_HAS_RATIO:${coupling.id}`);
    }
  } else {
    if (!coupling.targetNode) throw new TypeError(`COUPLING_NEEDS_TARGET_NODE:${coupling.id}`);
    if (coupling.targetShaft) throw new TypeError(`MACHINE_COUPLING_HAS_SHAFT_TARGET:${coupling.id}`);
  }
  if (coupling.ratio !== null && coupling.ratio <= 0) throw new TypeError(`INVALID_COUPLING_RATIO:${coupling.id}`);
  if (coupling.efficiency !== null && !(coupling.efficiency > 0 && coupling.efficiency <= 1)) {
    throw new TypeError(`INVALID_COUPLING_EFFICIENCY:${coupling.id}`);
  }
  return coupling;
}

function parseShaft(value: unknown, label: string): Shaft {
  const item = asObject(value, label);
  const members = asArray(item.members ?? [], `${label}.members`).map((member, index) =>
    requireString(member, `${label}.members[${index}]`),
  );
  const couplings = asArray(item.couplings ?? [], `${label}.couplings`).map((coupling, index) =>
    parseCoupling(coupling, `${label}.couplings[${index}]`),
  );
  const shaft: Shaft = {
    id: requireString(item.id, `${label}.id`),
    kind: requireEnum(item.kind, SHAFT_KINDS, `${label}.kind`) as ShaftKind,
    members,
    speed: parseSpeed(item.speed, `${label}.speed`),
    mechanicalLossFraction: optionalNumber(item.mechanicalLossFraction, `${label}.mechanicalLossFraction`) ?? 0,
    couplings,
  };
  if (new Set(shaft.members).size !== shaft.members.length) {
    throw new TypeError(`DUPLICATE_SHAFT_MEMBER:${shaft.id}`);
  }
  if (!(shaft.mechanicalLossFraction >= 0 && shaft.mechanicalLossFraction < 1)) {
    throw new TypeError(`INVALID_MECHANICAL_LOSS_FRACTION:${shaft.id}`);
  }
  const couplingIds = shaft.couplings.map((coupling) => coupling.id);
  if (new Set(couplingIds).size !== couplingIds.length) throw new TypeError(`DUPLICATE_COUPLING:${shaft.id}`);
  return shaft;
}

function validateArchitecture(architecture: RotatingGasArchitecture): void {
  const nodeById = new Map(architecture.nodes.map((node) => [node.id, node]));
  const stationIds = new Set(architecture.stations.map((station) => station.id));
  const shaftById = new Map(architecture.shafts.map((shaft) => [shaft.id, shaft]));

  const unique = (ids: readonly string[], label: string): void => {
    if (new Set(ids).size !== ids.length) throw new TypeError(`DUPLICATE_${label}`);
  };
  unique(architecture.nodes.map((node) => node.id), "NODE");
  unique(architecture.stations.map((station) => station.id), "STATION");
  unique(architecture.rows.map((row) => row.id), "ROW");
  unique(architecture.shafts.map((shaft) => shaft.id), "SHAFT");
  const edgeKeys = architecture.edges.map((edge) => `${edge.from}|${edge.to}|${edge.kind}|${edge.station ?? ""}`);
  if (new Set(edgeKeys).size !== edgeKeys.length) throw new TypeError("DUPLICATE_EDGE");

  for (const edge of architecture.edges) {
    for (const endpoint of [edge.from, edge.to]) {
      if (!nodeById.has(endpoint)) throw new TypeError(`EDGE_ENDPOINT_UNKNOWN:${endpoint}`);
    }
    if (edge.station !== null && !stationIds.has(edge.station)) {
      throw new TypeError(`EDGE_STATION_UNKNOWN:${edge.station}`);
    }
  }

  const rowShaftBinding = new Map<string, string>();
  for (const row of architecture.rows) {
    const node = nodeById.get(row.node);
    if (!node) throw new TypeError(`ROW_NODE_UNKNOWN:${row.id}`);
    if (!ROLE_ALLOWED_NODE_KINDS[row.role].includes(node.kind)) {
      throw new TypeError(`ROW_ROLE_NODE_MISMATCH:${row.id}:${node.kind}`);
    }
    for (const stationId of [row.stationIn, row.stationOut]) {
      if (!stationIds.has(stationId)) throw new TypeError(`ROW_STATION_UNKNOWN:${row.id}:${stationId}`);
    }
    if (row.shaft !== null) {
      if (!shaftById.has(row.shaft)) throw new TypeError(`ROW_SHAFT_UNKNOWN:${row.id}:${row.shaft}`);
      if (rowShaftBinding.has(row.id)) throw new TypeError(`ROW_BOUND_TO_MULTIPLE_SHAFTS:${row.id}`);
      rowShaftBinding.set(row.id, row.shaft);
    }
  }

  for (const shaft of architecture.shafts) {
    for (const member of shaft.members) {
      if (!rowShaftBinding.has(member)) throw new TypeError(`SHAFT_MEMBER_UNKNOWN:${shaft.id}:${member}`);
      if (rowShaftBinding.get(member) !== shaft.id) throw new TypeError(`SHAFT_MEMBER_BOUND_ELSEWHERE:${shaft.id}:${member}`);
    }
    for (const coupling of shaft.couplings) {
      if (coupling.targetShaft !== null) {
        if (!shaftById.has(coupling.targetShaft)) {
          throw new TypeError(`COUPLING_TARGET_SHAFT_UNKNOWN:${shaft.id}:${coupling.id}`);
        }
        if (coupling.targetShaft === shaft.id) throw new TypeError(`COUPLING_SELF_REFERENCE:${shaft.id}:${coupling.id}`);
      }
      if (coupling.targetNode !== null) {
        const target = nodeById.get(coupling.targetNode);
        if (!target) throw new TypeError(`COUPLING_TARGET_NODE_UNKNOWN:${shaft.id}:${coupling.id}`);
        const expected = COUPLING_TARGET_NODE_KIND[coupling.kind];
        if (expected !== undefined && target.kind !== expected) {
          throw new TypeError(`COUPLING_TARGET_NODE_KIND:${coupling.id}:${target.kind}`);
        }
      }
    }
  }

  const flowNodes = new Set(architecture.nodes.filter((node) => (FLOW_NODE_KINDS as readonly string[]).includes(node.kind)).map((node) => node.id));
  const flowEdges = architecture.edges.filter((edge) => (FLOW_EDGE_KINDS as readonly string[]).includes(edge.kind));
  const adjacency = new Map<string, string[]>();
  const undirected = new Map<string, Set<string>>();
  for (const nodeId of flowNodes) {
    adjacency.set(nodeId, []);
    undirected.set(nodeId, new Set());
  }
  for (const edge of flowEdges) {
    if (!flowNodes.has(edge.from) || !flowNodes.has(edge.to)) {
      throw new TypeError(`FLOW_EDGE_NEEDS_FLOW_NODES:${edge.from}->${edge.to}`);
    }
    adjacency.get(edge.from)?.push(edge.to);
    undirected.get(edge.from)?.add(edge.to);
    undirected.get(edge.to)?.add(edge.from);
  }
  const state = new Map<string, "visiting" | "done">();
  const visit = (nodeId: string): void => {
    const current = state.get(nodeId);
    if (current === "done") return;
    if (current === "visiting") throw new TypeError(`FLOW_CYCLE:${nodeId}`);
    state.set(nodeId, "visiting");
    for (const downstream of adjacency.get(nodeId) ?? []) visit(downstream);
    state.set(nodeId, "done");
  };
  for (const nodeId of flowNodes) visit(nodeId);
  if (flowNodes.size > 0) {
    const start = [...flowNodes].sort()[0];
    const seen = new Set([start]);
    const frontier = [start];
    while (frontier.length > 0) {
      const current = frontier.pop() as string;
      for (const neighbour of undirected.get(current) ?? []) {
        if (!seen.has(neighbour)) {
          seen.add(neighbour);
          frontier.push(neighbour);
        }
      }
    }
    if (seen.size !== flowNodes.size) throw new TypeError("FLOW_GRAPH_DISCONNECTED");
  }
}

/** Parse and validate a raw architecture document into the canonical model. */
export function parseArchitecture(payload: unknown): RotatingGasArchitecture {
  const document = asObject(payload, "architecture");
  const architecture: RotatingGasArchitecture = {
    schemaVersion:
      document.schemaVersion === undefined || document.schemaVersion === null
        ? SCHEMA_VERSION
        : requireInteger(document.schemaVersion, "schemaVersion", SCHEMA_VERSION),
    architectureId: requireString(document.architectureId, "architectureId"),
    defaultFluid: parseFluid(document.defaultFluid, "defaultFluid"),
    nodes: asArray(document.nodes ?? [], "nodes").map((node, index) => parseNode(node, `nodes[${index}]`)),
    edges: asArray(document.edges ?? [], "edges").map((edge, index) => parseEdge(edge, `edges[${index}]`)),
    stations: asArray(document.stations ?? [], "stations").map((station, index) => parseStation(station, `stations[${index}]`)),
    rows: asArray(document.rows ?? [], "rows").map((row, index) => parseRow(row, `rows[${index}]`)),
    shafts: asArray(document.shafts ?? [], "shafts").map((shaft, index) => parseShaft(shaft, `shafts[${index}]`)),
  };
  if (architecture.schemaVersion !== SCHEMA_VERSION) {
    throw new RangeError(`SCHEMA_VERSION_UNSUPPORTED:${architecture.schemaVersion}`);
  }
  if (architecture.nodes.length === 0) throw new TypeError("NODES_REQUIRED");
  validateArchitecture(architecture);
  return architecture;
}

function sorted<T>(items: readonly T[], key: (item: T) => string): T[] {
  return [...items].sort((left, right) => (key(left) < key(right) ? -1 : key(left) > key(right) ? 1 : 0));
}

function quantityOrNull(quantity: Quantity | null): Record<string, unknown> | null {
  return quantity === null ? null : { valueSI: canonicalNumber(quantity.valueSI), dimension: quantity.dimension };
}

function canonicalState(state: StationState): Record<string, unknown> {
  return {
    massFlow: quantityOrNull(state.massFlow),
    totalPressure: quantityOrNull(state.totalPressure),
    staticPressure: quantityOrNull(state.staticPressure),
    totalTemperature: quantityOrNull(state.totalTemperature),
    staticTemperature: quantityOrNull(state.staticTemperature),
    density: quantityOrNull(state.density),
    velocity: quantityOrNull(state.velocity),
    mach: quantityOrNull(state.mach),
    tangentialVelocity: quantityOrNull(state.tangentialVelocity),
    swirlAngle: quantityOrNull(state.swirlAngle),
    fluid: state.fluid === null ? null : { identity: state.fluid.identity, composition: { ...state.fluid.composition } },
    annulus:
      state.annulus === null
        ? null
        : {
            area: quantityOrNull(state.annulus.area),
            radius: quantityOrNull(state.annulus.radius),
            hubRadius: quantityOrNull(state.annulus.hubRadius),
            tipRadius: quantityOrNull(state.annulus.tipRadius),
            geometryRef: state.annulus.geometryRef,
          },
  };
}

/** Canonical, deterministic payload identical to the Python `canonical_payload`. */
export function canonicalArchitecture(architecture: RotatingGasArchitecture): Record<string, unknown> {
  return {
    schemaVersion: architecture.schemaVersion,
    architectureId: architecture.architectureId,
    defaultFluid:
      architecture.defaultFluid === null
        ? null
        : { identity: architecture.defaultFluid.identity, composition: { ...architecture.defaultFluid.composition } },
    nodes: sorted(architecture.nodes, (node) => node.id).map((node) => ({
      id: node.id,
      kind: node.kind,
      label: node.label,
    })),
    edges: sorted(
      architecture.edges,
      (edge) => `${edge.from}|${edge.to}|${edge.kind}|${edge.station ?? ""}`,
    ).map((edge) => ({ from: edge.from, to: edge.to, kind: edge.kind, station: edge.station })),
    stations: sorted(architecture.stations, (station) => station.id).map((station) => ({
      id: station.id,
      name: station.name,
      state: canonicalState(station.state),
    })),
    rows: sorted(architecture.rows, (row) => row.id).map((row) => ({
      id: row.id,
      node: row.node,
      role: row.role,
      frame: row.frame,
      shaft: row.shaft,
      stationIn: row.stationIn,
      stationOut: row.stationOut,
      rowCount: row.rowCount,
      periodicity: row.periodicity,
      family: row.family,
      geometryRef: row.geometryRef,
      clearance: {
        tipClearance: quantityOrNull(row.clearance.tipClearance),
        endwallState: row.clearance.endwallState,
        shroudState: row.clearance.shroudState,
      },
      materialRef: row.materialRef,
      thermalRef: row.thermalRef,
    })),
    shafts: sorted(architecture.shafts, (shaft) => shaft.id).map((shaft) => ({
      id: shaft.id,
      kind: shaft.kind,
      members: [...shaft.members].sort(),
      speed: shaft.speed === null ? null : { kind: shaft.speed.kind, value: quantityOrNull(shaft.speed.value) },
      mechanicalLossFraction: canonicalNumber(shaft.mechanicalLossFraction),
      couplings: sorted(shaft.couplings, (coupling) => coupling.id).map((coupling) => ({
        id: coupling.id,
        kind: coupling.kind,
        targetShaft: coupling.targetShaft,
        targetNode: coupling.targetNode,
        ratio: coupling.ratio,
        efficiency: coupling.efficiency,
      })),
    })),
  };
}

export function architectureDigest(architecture: RotatingGasArchitecture): string {
  return contentDigest(canonicalArchitecture(architecture));
}

/** Deterministic SHA-256 content hash of a raw architecture document. */
export function architectureHash(payload: unknown): string {
  return architectureDigest(parseArchitecture(payload));
}

/** Structural topology view used for design-space invalidation. */
export function topologyPayload(architecture: RotatingGasArchitecture): Record<string, unknown> {
  return {
    schemaVersion: architecture.schemaVersion,
    nodes: sorted(architecture.nodes, (node) => node.id).map((node) => ({ id: node.id, kind: node.kind })),
    edges: sorted(
      architecture.edges,
      (edge) => `${edge.from}|${edge.to}|${edge.kind}|${edge.station ?? ""}`,
    ).map((edge) => ({ from: edge.from, to: edge.to, kind: edge.kind, station: edge.station })),
    stations: sorted(architecture.stations, (station) => station.id).map((station) => station.id),
    rows: sorted(architecture.rows, (row) => row.id).map((row) => ({
      id: row.id,
      node: row.node,
      role: row.role,
      frame: row.frame,
      shaft: row.shaft,
      stationIn: row.stationIn,
      stationOut: row.stationOut,
      rowCount: row.rowCount,
      periodicity: row.periodicity,
      family: row.family,
      geometryRef: row.geometryRef,
      materialRef: row.materialRef,
      thermalRef: row.thermalRef,
    })),
    shafts: sorted(architecture.shafts, (shaft) => shaft.id).map((shaft) => ({
      id: shaft.id,
      kind: shaft.kind,
      members: [...shaft.members].sort(),
      speedKind: shaft.speed === null ? null : shaft.speed.kind,
      couplings: sorted(shaft.couplings, (coupling) => coupling.id).map((coupling) => ({
        id: coupling.id,
        kind: coupling.kind,
        targetShaft: coupling.targetShaft,
        targetNode: coupling.targetNode,
      })),
    })),
  };
}

export function topologyDigest(architecture: RotatingGasArchitecture): string {
  return contentDigest(topologyPayload(architecture));
}

function digestEqual(left: unknown, right: unknown): boolean {
  return contentDigest(left) === contentDigest(right);
}

/**
 * Classify an architecture delta onto the existing design-section vocabulary.
 * Feed the result to `invalidatedNodes` (re-exported here as
 * `rotatingGasInvalidatedNodes`) to invalidate geometry/mesh/analysis/optimization
 * descendants.
 */
export function topologyChangeSections(
  before: RotatingGasArchitecture,
  after: RotatingGasArchitecture,
): readonly string[] {
  const sections = new Set<string>();
  const b = topologyPayload(before);
  const a = topologyPayload(after);
  const graph = (payload: Record<string, unknown>): unknown => ({ nodes: payload.nodes, edges: payload.edges });
  if (!digestEqual(graph(b), graph(a))) sections.add("topologyDigest");
  if (!digestEqual(b.stations, a.stations)) sections.add("topologyDigest");
  const rowStructure = (rows: readonly BladeRow[]): unknown =>
    rows.map((row) => [row.id, row.node, row.role, row.frame, row.shaft, row.stationIn, row.stationOut, row.family]);
  if (!digestEqual(rowStructure(before.rows), rowStructure(after.rows))) sections.add("topologyDigest");
  const geometry = (architecture: RotatingGasArchitecture): unknown => ({
    rows: architecture.rows.map((row) => [row.id, row.rowCount, row.periodicity, row.geometryRef]),
    annuli: architecture.stations.map((station) => [station.id, canonicalState(station.state).annulus]),
  });
  if (!digestEqual(geometry(before), geometry(after))) sections.add("geometry");
  const motion = (architecture: RotatingGasArchitecture): unknown => ({
    rows: architecture.rows.map((row) => [row.id, row.frame, row.shaft]),
    shafts: architecture.shafts.map((shaft) => [shaft.id, shaft.kind, [...shaft.members].sort()]),
  });
  if (!digestEqual(motion(before), motion(after))) sections.add("motionFrames");
  const material = (architecture: RotatingGasArchitecture): unknown =>
    architecture.rows.map((row) => [row.id, row.materialRef, row.thermalRef]);
  if (!digestEqual(material(before), material(after))) sections.add("materials");
  const stationValues = (architecture: RotatingGasArchitecture): unknown =>
    architecture.stations.map((station) => [station.id, canonicalState(station.state)]);
  if (!digestEqual(stationValues(before), stationValues(after))) sections.add("operatingPoints");
  const parametric = (architecture: RotatingGasArchitecture): unknown => ({
    rows: architecture.rows.map((row) => [row.id, row.clearance]),
    shafts: architecture.shafts.map((shaft) => [
      shaft.id,
      shaft.mechanicalLossFraction,
      shaft.speed,
      shaft.couplings.map((coupling) => [coupling.id, coupling.ratio, coupling.efficiency]),
    ]),
  });
  if (!digestEqual(parametric(before), parametric(after))) sections.add("parameters");
  return [...sections].sort();
}

/** Apply the existing design invalidation table to rotating-gas change sections. */
export function rotatingGasInvalidatedNodes(changedSections: readonly string[]): readonly string[] {
  return invalidatedNodes(changedSections);
}
