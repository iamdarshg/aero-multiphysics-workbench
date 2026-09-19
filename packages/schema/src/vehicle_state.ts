/**
 * Canonical flying-vehicle state: frames, mass properties, unit-safe flight quantities.
 *
 * This is the TypeScript mirror of
 * `packages/airframe/aeroworkbench_airframe/`. The canonical serialization and
 * `vehicleStateHash` are byte-for-byte identical to the Python
 * `canonical_vehicle_state` / `vehicle_state_hash`, which is the cross-language
 * contract proven by the shared fixtures under `tests/airframe/state`.
 *
 * Topology changes are projected onto the existing design-section vocabulary
 * (`invalidatedNodes`) so the existing invalidation table handles vehicle-state
 * changes without a parallel framework.
 */

import { contentDigest } from "../../cache/src/content-addressed.ts";
import { invalidatedNodes } from "./design.ts";

export const SCHEMA_VERSION = 1;

export const FRAME_KINDS = ["inertial", "ecef", "ned", "body", "wind"] as const;
export const SIGN_CONVENTIONS = [
  "body_axes_aerodynamic",
  "stability_axes_aerodynamic",
  "structural_body_axes",
] as const;

export type FrameKind = (typeof FRAME_KINDS)[number];
export type SignConvention = (typeof SIGN_CONVENTIONS)[number];

export interface Quantity {
  readonly valueSI: number;
  readonly dimension: string;
}

export interface Vec3 {
  readonly x: number;
  readonly y: number;
  readonly z: number;
  readonly dimension: string;
  readonly frame: string;
}

export interface Frame {
  readonly id: string;
  readonly kind: FrameKind;
  readonly parent: string | null;
  readonly convention: string | null;
  readonly parameters: Readonly<Record<string, Quantity>>;
}

export interface InertiaTensor {
  readonly ixx: Quantity;
  readonly iyy: Quantity;
  readonly izz: Quantity;
  readonly ixy: Quantity;
  readonly ixz: Quantity;
  readonly iyz: Quantity;
  readonly dimension: "moment_of_inertia";
  readonly frame: string;
}

export interface Attitude {
  readonly fromFrame: string;
  readonly toFrame: string;
  readonly convention: string;
  readonly angles: Readonly<Record<string, Quantity>> | null;
  readonly quaternion: readonly number[] | null;
}

export interface FlyingVehicleState {
  readonly schemaVersion: number;
  readonly vehicleId: string;
  readonly architectureType: string;
  readonly reference: {
    readonly frame: string;
    readonly area: Quantity | null;
    readonly span: Quantity | null;
    readonly chord: Quantity | null;
    readonly aerodynamicReferencePoint: Vec3 | null;
  };
  readonly frames: readonly Frame[];
  readonly massProperties: {
    readonly mass: Quantity;
    readonly cg: Vec3;
    readonly inertia: InertiaTensor;
  };
  readonly flight: {
    readonly position: Vec3;
    readonly attitude: Attitude;
    readonly velocity: Vec3;
    readonly angularRates: Vec3;
    readonly flight: Record<string, unknown>;
    readonly atmosphere: Record<string, unknown>;
  };
  readonly controls: Record<string, unknown>;
  readonly loads: Record<string, unknown> | null;
}

const FRAME_PARENT_KIND: Readonly<Record<string, string | null>> = Object.freeze({
  inertial: null,
  ecef: "inertial",
  ned: "ecef",
  body: "ned",
  wind: "body",
});

const FRAME_CONVENTIONS: Readonly<Record<string, readonly string[]>> = Object.freeze({
  inertial: [],
  ecef: [],
  ned: ["geodetic"],
  body: ["euler_321", "quaternion"],
  wind: ["alpha_beta"],
});

const CONVENTION_PARAMETERS: Readonly<Record<string, readonly (readonly [string, string])[]>> =
  Object.freeze({
    euler_321: [["yaw", "angle"], ["pitch", "angle"], ["roll", "angle"]],
    quaternion: [["qw", "dimensionless"], ["qx", "dimensionless"], ["qy", "dimensionless"], ["qz", "dimensionless"]],
    alpha_beta: [["alpha", "angle"], ["beta", "angle"]],
    geodetic: [["latitude", "angle"], ["longitude", "angle"]],
  });

// unit label -> [dimension, scale to SI, offset to SI]: si = value * scale + offset
const UNIT_TABLE: Readonly<Record<string, readonly [string, number, number]>> = Object.freeze({
  dimensionless: ["dimensionless", 1, 0],
  kg: ["mass", 1, 0],
  g: ["mass", 1e-3, 0],
  mg: ["mass", 1e-6, 0],
  lbm: ["mass", 0.45359237, 0],
  slug: ["mass", 14.59390294, 0],
  m: ["length", 1, 0],
  cm: ["length", 1e-2, 0],
  mm: ["length", 1e-3, 0],
  in: ["length", 0.0254, 0],
  ft: ["length", 0.3048, 0],
  km: ["length", 1e3, 0],
  m2: ["area", 1, 0],
  cm2: ["area", 1e-4, 0],
  mm2: ["area", 1e-6, 0],
  ft2: ["area", 0.09290304, 0],
  s: ["time", 1, 0],
  min: ["time", 60, 0],
  h: ["time", 3600, 0],
  "m/s": ["velocity", 1, 0],
  "cm/s": ["velocity", 1e-2, 0],
  "km/h": ["velocity", 1000 / 3600, 0],
  kt: ["velocity", 1852 / 3600, 0],
  "ft/s": ["velocity", 0.3048, 0],
  mph: ["velocity", 0.44704, 0],
  "m/s2": ["acceleration", 1, 0],
  g0: ["acceleration", 9.80665, 0],
  "ft/s2": ["acceleration", 0.3048, 0],
  N: ["force", 1, 0],
  kN: ["force", 1e3, 0],
  lbf: ["force", 4.4482216152605, 0],
  kgf: ["force", 9.80665, 0],
  "N.m": ["moment", 1, 0],
  "kN.m": ["moment", 1e3, 0],
  "lbf.ft": ["moment", 1.3558179483314004, 0],
  "kg.m2": ["moment_of_inertia", 1, 0],
  "g.m2": ["moment_of_inertia", 1e-3, 0],
  Pa: ["pressure", 1, 0],
  hPa: ["pressure", 100, 0],
  kPa: ["pressure", 1e3, 0],
  MPa: ["pressure", 1e6, 0],
  bar: ["pressure", 1e5, 0],
  atm: ["pressure", 101325, 0],
  psi: ["pressure", 6894.757293168361, 0],
  K: ["temperature", 1, 0],
  degC: ["temperature", 1, 273.15],
  "kg/m3": ["density", 1, 0],
  "g/cm3": ["density", 1e3, 0],
  rad: ["angle", 1, 0],
  deg: ["angle", Math.PI / 180, 0],
  "rad/s": ["angular_rate", 1, 0],
  "deg/s": ["angular_rate", Math.PI / 180, 0],
  rpm: ["rotational_speed", 1 / 60, 0],
  "rev/s": ["rotational_speed", 1, 0],
  "kg/s": ["mass_flow", 1, 0],
  "kg/h": ["mass_flow", 1 / 3600, 0],
  "lbm/s": ["mass_flow", 0.45359237, 0],
  "J/(kg.K)": ["specific_gas_constant", 1, 0],
  "kJ/(kg.K)": ["specific_gas_constant", 1e3, 0],
  W: ["power", 1, 0],
  kW: ["power", 1e3, 0],
  hp: ["power", 745.6998715822702, 0],
});

const SI_UNIT_FOR_DIMENSION: Readonly<Record<string, string>> = Object.freeze({
  dimensionless: "dimensionless",
  mass: "kg",
  length: "m",
  area: "m2",
  time: "s",
  velocity: "m/s",
  acceleration: "m/s2",
  force: "N",
  moment: "N.m",
  moment_of_inertia: "kg.m2",
  pressure: "Pa",
  temperature: "K",
  density: "kg/m3",
  angle: "rad",
  angular_rate: "rad/s",
  rotational_speed: "rev/s",
  mass_flow: "kg/s",
  specific_gas_constant: "J/(kg.K)",
  power: "W",
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
  if ("unit" in item) {
    const raw = requireNumber(item.value, label);
    const unit = requireString(item.unit, `${label}.unit`);
    const definition = UNIT_TABLE[unit];
    if (!definition) throw new RangeError(`UNKNOWN_UNIT:${unit}`);
    if (dimension !== undefined && definition[0] !== dimension) {
      throw new TypeError(`QUANTITY_DIMENSION_MISMATCH:${label}:${definition[0]}:${dimension}`);
    }
    return { valueSI: canonicalNumber(raw * definition[1] + definition[2]), dimension: definition[0] };
  }
  if ("valueSI" in item) {
    const raw = requireNumber(item.valueSI, label);
    const declared = requireString(item.dimension, `${label}.dimension`);
    if (dimension !== undefined && declared !== dimension) {
      throw new TypeError(`QUANTITY_DIMENSION_MISMATCH:${label}:${declared}:${dimension}`);
    }
    return { valueSI: canonicalNumber(raw), dimension: declared };
  }
  throw new TypeError(`QUANTITY_NEEDS_VALUE_AND_UNIT:${label}`);
}

function parseVec3(value: unknown, label: string, dimension?: string): Vec3 | null {
  if (value === null || value === undefined) return null;
  const item = asObject(value, label);
  const frame = requireString(item.frame, `${label}.frame`);
  if ("unit" in item) {
    const unit = requireString(item.unit, `${label}.unit`);
    const definition = UNIT_TABLE[unit];
    if (!definition) throw new RangeError(`UNKNOWN_UNIT:${unit}`);
    if (dimension !== undefined && definition[0] !== dimension) {
      throw new TypeError(`QUANTITY_DIMENSION_MISMATCH:${label}:${definition[0]}:${dimension}`);
    }
    const convert = (component: unknown, axis: string): number =>
      canonicalNumber(requireNumber(component, `${label}.${axis}`) * definition[1] + definition[2]);
    return {
      x: convert(item.x, "x"),
      y: convert(item.y, "y"),
      z: convert(item.z, "z"),
      dimension: definition[0],
      frame,
    };
  }
  const declared = requireString(item.dimension, `${label}.dimension`);
  if (dimension !== undefined && declared !== dimension) {
    throw new TypeError(`QUANTITY_DIMENSION_MISMATCH:${label}:${declared}:${dimension}`);
  }
  return {
    x: canonicalNumber(requireNumber(item.x, `${label}.x`)),
    y: canonicalNumber(requireNumber(item.y, `${label}.y`)),
    z: canonicalNumber(requireNumber(item.z, `${label}.z`)),
    dimension: declared,
    frame,
  };
}

function parseNamedQuantities(value: unknown, label: string, dimension: string): Record<string, Quantity> {
  if (value === null || value === undefined) return {};
  const item = asObject(value, label);
  const result: Record<string, Quantity> = {};
  for (const [name, raw] of Object.entries(item)) {
    const quantity = parseQuantity(raw, `${label}.${name}`, dimension);
    if (!quantity) throw new TypeError(`QUANTITY_REQUIRED:${label}.${name}`);
    result[name] = quantity;
  }
  return result;
}

function parseFrames(value: unknown): Frame[] {
  return asArray(value ?? [], "frames").map((raw, index) => {
    const label = `frames[${index}]`;
    const item = asObject(raw, label);
    const id = requireString(item.id, `${label}.id`);
    const kind = requireEnum(item.kind, FRAME_KINDS, `${label}.kind`);
    const parent = optionalString(item.parent, `${label}.parent`);
    if (parent !== FRAME_PARENT_KIND[kind]) {
      throw new TypeError(`FRAME_PARENT_KIND_MISMATCH:${id}:${parent}`);
    }
    const convention = optionalString(item.convention, `${label}.convention`);
    const allowed = FRAME_CONVENTIONS[kind];
    if (allowed.length > 0) {
      if (convention === null || !allowed.includes(convention)) {
        throw new TypeError(`FRAME_CONVENTION_REQUIRED:${id}`);
      }
    } else if (convention !== null) {
      throw new TypeError(`FRAME_CONVENTION_NOT_ALLOWED:${id}`);
    }
    const rawParameters = item.parameters === undefined || item.parameters === null ? {} : asObject(item.parameters, `${label}.parameters`);
    let parameters: Record<string, Quantity> = {};
    if (convention !== null) {
      const expected = CONVENTION_PARAMETERS[convention];
      const expectedNames = expected.map(([name]) => name).sort();
      const names = Object.keys(rawParameters).sort();
      if (names.length !== expectedNames.length || names.some((name, position) => name !== expectedNames[position])) {
        throw new TypeError(`FRAME_PARAMETERS_INCOMPLETE:${id}`);
      }
      for (const [name, dimension] of expected) {
        const quantity = parseQuantity(rawParameters[name], `${label}.parameters.${name}`, dimension);
        if (!quantity) throw new TypeError(`FRAME_PARAMETER_MISSING:${id}:${name}`);
        parameters[name] = quantity;
      }
    } else if (Object.keys(rawParameters).length > 0) {
      throw new TypeError(`FRAME_PARAMETERS_NOT_ALLOWED:${id}`);
    }
    return { id, kind, parent, convention, parameters };
  });
}

function frameIndex(frames: readonly Frame[]): Map<string, Frame> {
  if (frames.length === 0) throw new TypeError("FRAMES_REQUIRED");
  const index = new Map<string, Frame>();
  for (const frame of frames) {
    if (index.has(frame.id)) throw new TypeError(`DUPLICATE_FRAME_ID:${frame.id}`);
    index.set(frame.id, frame);
  }
  for (const frame of frames) {
    if (frame.parent !== null && !index.has(frame.parent)) {
      throw new TypeError(`FRAME_PARENT_UNKNOWN:${frame.id}:${frame.parent}`);
    }
  }
  for (const frame of frames) {
    const seen = new Set<string>([frame.id]);
    let cursor = frame.parent;
    while (cursor !== null) {
      if (seen.has(cursor)) throw new TypeError(`FRAME_CYCLE:${frame.id}`);
      seen.add(cursor);
      cursor = index.get(cursor)?.parent ?? null;
    }
  }
  return index;
}

type Mat3 = readonly [readonly [number, number, number], readonly [number, number, number], readonly [number, number, number]];
const IDENTITY: Mat3 = [[1, 0, 0], [0, 1, 0], [0, 0, 1]];

function matmul(left: Mat3, right: Mat3): Mat3 {
  const entry = (row: number, col: number): number =>
    left[row][0] * right[0][col] + left[row][1] * right[1][col] + left[row][2] * right[2][col];
  return [
    [entry(0, 0), entry(0, 1), entry(0, 2)],
    [entry(1, 0), entry(1, 1), entry(1, 2)],
    [entry(2, 0), entry(2, 1), entry(2, 2)],
  ];
}

function transpose(matrix: Mat3): Mat3 {
  return [
    [matrix[0][0], matrix[1][0], matrix[2][0]],
    [matrix[0][1], matrix[1][1], matrix[2][1]],
    [matrix[0][2], matrix[1][2], matrix[2][2]],
  ];
}

function frameParameter(frame: Frame, name: string): number {
  const quantity = frame.parameters[name];
  if (!quantity) throw new TypeError(`FRAME_PARAMETER_MISSING:${frame.id}:${name}`);
  return quantity.valueSI;
}

function frameRotation(frame: Frame): Mat3 {
  if (frame.convention === null) return IDENTITY;
  if (frame.convention === "euler_321") {
    const yaw = frameParameter(frame, "yaw");
    const pitch = frameParameter(frame, "pitch");
    const roll = frameParameter(frame, "roll");
    const cy = Math.cos(yaw), sy = Math.sin(yaw);
    const cp = Math.cos(pitch), sp = Math.sin(pitch);
    const cr = Math.cos(roll), sr = Math.sin(roll);
    return matmul(
      [
        [1, 0, 0],
        [0, cr, -sr],
        [0, sr, cr],
      ],
      matmul(
        [
          [cp, 0, sp],
          [0, 1, 0],
          [-sp, 0, cp],
        ],
        [
          [cy, -sy, 0],
          [sy, cy, 0],
          [0, 0, 1],
        ],
      ),
    );
  }
  if (frame.convention === "quaternion") {
    const w = frameParameter(frame, "qw");
    const x = frameParameter(frame, "qx");
    const y = frameParameter(frame, "qy");
    const z = frameParameter(frame, "qz");
    return [
      [1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
      [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
      [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)],
    ];
  }
  if (frame.convention === "alpha_beta") {
    const alpha = frameParameter(frame, "alpha");
    const beta = frameParameter(frame, "beta");
    const ca = Math.cos(alpha), sa = Math.sin(alpha);
    const cb = Math.cos(beta), sb = Math.sin(beta);
    return [
      [ca * cb, sb, sa * cb],
      [-ca * sb, cb, -sa * sb],
      [-sa, 0, ca],
    ];
  }
  if (frame.convention === "geodetic") {
    const latitude = frameParameter(frame, "latitude");
    const longitude = frameParameter(frame, "longitude");
    const sp = Math.sin(latitude), cp = Math.cos(latitude);
    const sl = Math.sin(longitude), cl = Math.cos(longitude);
    return [
      [-sp * cl, -sp * sl, cp],
      [-sl, cl, 0],
      [-cp * cl, -cp * sl, -sp],
    ];
  }
  throw new RangeError(`UNKNOWN_FRAME_CONVENTION:${frame.convention}`);
}

function rotationToRoot(index: Map<string, Frame>, frameId: string): Mat3 {
  if (!index.has(frameId)) throw new TypeError(`UNKNOWN_FRAME:${frameId}`);
  let result = IDENTITY;
  let cursor: string | null = frameId;
  while (cursor !== null) {
    const frame = index.get(cursor);
    if (!frame) throw new TypeError(`UNKNOWN_FRAME:${cursor}`);
    result = matmul(transpose(frameRotation(frame)), result);
    cursor = frame.parent;
  }
  return result;
}

/** Deterministic rotation between two declared frames: ``v_to = R @ v_from``. */
export function rotationBetween(frames: readonly Frame[], fromId: string, toId: string): Mat3 {
  const index = frameIndex(frames);
  return matmul(transpose(rotationToRoot(index, toId)), rotationToRoot(index, fromId));
}

function parseAttitude(value: unknown): Attitude {
  const item = asObject(value, "flight.attitude");
  const convention = requireString(item.convention, "flight.attitude.convention");
  const fromFrame = requireString(item.fromFrame, "flight.attitude.fromFrame");
  const toFrame = requireString(item.toFrame, "flight.attitude.toFrame");
  if (fromFrame === toFrame) throw new TypeError("ATTITUDE_FRAMES_MUST_DIFFER");
  let angles: Record<string, Quantity> | null = null;
  let quaternion: number[] | null = null;
  if (convention === "euler_321") {
    const rawAngles = item.angles === undefined || item.angles === null ? {} : asObject(item.angles, "flight.attitude.angles");
    const required = ["yaw", "pitch", "roll"];
    if (Object.keys(rawAngles).sort().join("|") !== [...required].sort().join("|")) {
      throw new TypeError("ATTITUDE_EULER_ANGLES_INCOMPLETE");
    }
    angles = {};
    for (const name of required) {
      const quantity = parseQuantity(rawAngles[name], `flight.attitude.angles.${name}`, "angle");
      if (!quantity) throw new TypeError(`ATTITUDE_ANGLE_REQUIRED:${name}`);
      angles[name] = quantity;
    }
  } else if (convention === "quaternion") {
    const raw = asArray(item.quaternion ?? [], "flight.attitude.quaternion");
    if (raw.length !== 4) throw new TypeError("ATTITUDE_QUATERNION_REQUIRED");
    const components = raw.map((component, indexValue) => requireNumber(component, `flight.attitude.quaternion[${indexValue}]`));
    const norm = Math.sqrt(components.reduce((sum, component) => sum + component * component, 0));
    if (Math.abs(norm - 1) > 1e-9) throw new TypeError("QUATERNION_NOT_UNIT");
    quaternion = components;
  } else {
    throw new TypeError(`UNKNOWN_ATTITUDE_CONVENTION:${convention}`);
  }
  return { fromFrame, toFrame, convention, angles, quaternion };
}

function parseInertiaQuantity(item: Record<string, unknown>, key: string): Quantity {
  const raw = item[key];
  if (typeof raw === "object" && raw !== null) {
    const quantity = parseQuantity(raw, `massProperties.inertia.${key}`, "moment_of_inertia");
    if (!quantity) throw new TypeError(`INERTIA_COMPONENT_REQUIRED:${key}`);
    return quantity;
  }
  return { valueSI: canonicalNumber(requireNumber(raw, `massProperties.inertia.${key}`)), dimension: "moment_of_inertia" };
}

function parseFlightQuantities(value: unknown): Record<string, unknown> {
  const item = asObject(value, "flight.flight");
  const airspeed = item.airspeed === undefined || item.airspeed === null ? {} : asObject(item.airspeed, "flight.flight.airspeed");
  return {
    altitude: parseQuantity(item.altitude, "flight.flight.altitude", "length"),
    airspeed: {
      calibrated: parseQuantity(airspeed.calibrated, "flight.flight.airspeed.calibrated", "velocity"),
      equivalent: parseQuantity(airspeed.equivalent, "flight.flight.airspeed.equivalent", "velocity"),
      true: parseQuantity(airspeed.true, "flight.flight.airspeed.true", "velocity"),
    },
    mach: parseQuantity(item.mach, "flight.flight.mach", "dimensionless"),
    dynamicPressure: parseQuantity(item.dynamicPressure, "flight.flight.dynamicPressure", "pressure"),
    angleOfAttack: parseQuantity(item.angleOfAttack, "flight.flight.angleOfAttack", "angle"),
    sideslip: parseQuantity(item.sideslip, "flight.flight.sideslip", "angle"),
    loadFactor: parseQuantity(item.loadFactor, "flight.flight.loadFactor", "dimensionless"),
    reynolds: parseQuantity(item.reynolds, "flight.flight.reynolds", "dimensionless"),
  };
}

function parseAtmosphere(value: unknown): Record<string, unknown> {
  const item = asObject(value, "flight.atmosphere");
  return {
    model: requireString(item.model, "flight.atmosphere.model"),
    referenceAltitude: parseQuantity(item.referenceAltitude, "flight.atmosphere.referenceAltitude", "length"),
    density: parseQuantity(item.density, "flight.atmosphere.density", "density"),
    temperature: parseQuantity(item.temperature, "flight.atmosphere.temperature", "temperature"),
    pressure: parseQuantity(item.pressure, "flight.atmosphere.pressure", "pressure"),
    speedOfSound: parseQuantity(item.speedOfSound, "flight.atmosphere.speedOfSound", "velocity"),
    gasConstant: parseQuantity(item.gasConstant, "flight.atmosphere.gasConstant", "specific_gas_constant"),
    gravity: parseQuantity(item.gravity, "flight.atmosphere.gravity", "acceleration"),
  };
}

function parseControls(value: unknown): Record<string, unknown> {
  const item = value === undefined || value === null ? {} : asObject(value, "controls");
  const throttle = parseQuantity(item.throttle, "controls.throttle", "dimensionless");
  if (throttle && (throttle.valueSI < 0 || throttle.valueSI > 1)) {
    throw new RangeError("THROTTLE_OUT_OF_RANGE");
  }
  return {
    surfaceDeflections: parseNamedQuantities(item.surfaceDeflections, "controls.surfaceDeflections", "angle"),
    throttle,
    rpm: parseQuantity(item.rpm, "controls.rpm", "rotational_speed"),
    collective: parseQuantity(item.collective, "controls.collective", "angle"),
    cyclic: parseNamedQuantities(item.cyclic, "controls.cyclic", "angle"),
    tilt: parseNamedQuantities(item.tilt, "controls.tilt", "angle"),
  };
}

function parseLoads(value: unknown): Record<string, unknown> | null {
  if (value === null || value === undefined) return null;
  const item = asObject(value, "loads");
  const force = parseVec3(item.force, "loads.force", "force");
  const moment = parseVec3(item.moment, "loads.moment", "moment");
  const referencePoint = parseVec3(item.referencePoint, "loads.referencePoint", "length");
  if (!force || !moment || !referencePoint) throw new TypeError("LOADS_VECTORS_REQUIRED");
  return {
    force,
    moment,
    referencePoint,
    axesFrame: requireString(item.axesFrame, "loads.axesFrame"),
    signConvention: requireEnum(item.signConvention, SIGN_CONVENTIONS, "signConvention"),
  };
}

function requireFrame(index: Map<string, Frame>, frameId: string, label: string): void {
  if (!index.has(frameId)) throw new TypeError(`UNKNOWN_FRAME:${label}:${frameId}`);
}

function vec3Frame(vector: Vec3): string {
  return vector.frame;
}

/** Parse and validate a raw vehicle-state document into the canonical model. */
export function parseVehicleState(payload: unknown): FlyingVehicleState {
  const document = asObject(payload, "vehicleState");
  const frames = parseFrames(document.frames);
  const index = frameIndex(frames);
  const referenceItem = asObject(document.reference, "reference");
  const referenceFrame = requireString(referenceItem.frame, "reference.frame");
  requireFrame(index, referenceFrame, "reference");
  const aerodynamicReferencePoint = parseVec3(referenceItem.aerodynamicReferencePoint, "reference.aerodynamicReferencePoint", "length");
  if (aerodynamicReferencePoint) requireFrame(index, aerodynamicReferencePoint.frame, "referencePoint");

  const massItem = asObject(document.massProperties, "massProperties");
  const mass = parseQuantity(massItem.mass, "massProperties.mass", "mass");
  if (!mass || mass.valueSI <= 0) throw new RangeError("NONPOSITIVE_MASS");
  const cg = parseVec3(massItem.cg, "massProperties.cg", "length");
  requireFrame(index, vec3Frame(cg as Vec3), "cg");
  const inertiaItem = asObject(massItem.inertia, "massProperties.inertia");
  const inertia: InertiaTensor = {
    ixx: parseInertiaQuantity(inertiaItem, "ixx"),
    iyy: parseInertiaQuantity(inertiaItem, "iyy"),
    izz: parseInertiaQuantity(inertiaItem, "izz"),
    ixy: parseInertiaQuantity(inertiaItem, "ixy"),
    ixz: parseInertiaQuantity(inertiaItem, "ixz"),
    iyz: parseInertiaQuantity(inertiaItem, "iyz"),
    dimension: "moment_of_inertia",
    frame: requireString(inertiaItem.frame, "massProperties.inertia.frame"),
  };
  requireFrame(index, inertia.frame, "inertia");

  const flightItem = asObject(document.flight, "flight");
  const position = parseVec3(flightItem.position, "flight.position", "length");
  const velocity = parseVec3(flightItem.velocity, "flight.velocity", "velocity");
  const angularRates = parseVec3(flightItem.angularRates, "flight.angularRates", "angular_rate");
  if (!position || !velocity || !angularRates) throw new TypeError("FLIGHT_VECTORS_REQUIRED");
  requireFrame(index, position.frame, "position");
  requireFrame(index, velocity.frame, "velocity");
  requireFrame(index, angularRates.frame, "angularRates");
  const attitude = parseAttitude(flightItem.attitude);
  requireFrame(index, attitude.fromFrame, "attitude.fromFrame");
  requireFrame(index, attitude.toFrame, "attitude.toFrame");
  const target = index.get(attitude.toFrame);
  if (target && target.convention !== null && attitude.convention !== target.convention) {
    throw new TypeError(`FRAME_CONVENTION_MISMATCH:${attitude.toFrame}:${attitude.convention}:${target.convention}`);
  }
  if (target && !FRAME_CONVENTIONS[target.kind].includes(attitude.convention)) {
    throw new TypeError(`ATTITUDE_CONVENTION_NOT_ALLOWED:${attitude.toFrame}:${attitude.convention}`);
  }

  const loads = parseLoads(document.loads);
  if (loads) {
    const force = loads.force as Vec3;
    const moment = loads.moment as Vec3;
    const loadPoint = loads.referencePoint as Vec3;
    requireFrame(index, force.frame, "loads.force");
    requireFrame(index, moment.frame, "loads.moment");
    requireFrame(index, loadPoint.frame, "loads.referencePoint");
    requireFrame(index, loads.axesFrame as string, "loads.axesFrame");
  }

  const version = document.schemaVersion;
  if (version !== undefined && version !== null && version !== SCHEMA_VERSION) {
    throw new RangeError(`SCHEMA_VERSION_UNSUPPORTED:${String(version)}`);
  }

  return {
    schemaVersion: SCHEMA_VERSION,
    vehicleId: requireString(document.vehicleId, "vehicleId"),
    architectureType: requireString(document.architectureType, "architectureType"),
    reference: {
      frame: referenceFrame,
      area: parseQuantity(referenceItem.area, "reference.area", "area"),
      span: parseQuantity(referenceItem.span, "reference.span", "length"),
      chord: parseQuantity(referenceItem.chord, "reference.chord", "length"),
      aerodynamicReferencePoint,
    },
    frames,
    massProperties: { mass, cg: cg as Vec3, inertia },
    flight: {
      position,
      attitude,
      velocity,
      angularRates,
      flight: parseFlightQuantities(flightItem.flight),
      atmosphere: parseAtmosphere(flightItem.atmosphere),
    },
    controls: parseControls(document.controls),
    loads,
  };
}

function sortedFrames(frames: readonly Frame[]): Frame[] {
  return [...frames].sort((left, right) => (left.id < right.id ? -1 : left.id > right.id ? 1 : 0));
}

/** Canonical, deterministic payload identical to the Python `canonical_payload`. */
export function canonicalVehicleState(state: FlyingVehicleState): Record<string, unknown> {
  return {
    schemaVersion: state.schemaVersion,
    vehicleId: state.vehicleId,
    architectureType: state.architectureType,
    reference: state.reference,
    frames: sortedFrames(state.frames).map((frame) => ({
      id: frame.id,
      kind: frame.kind,
      parent: frame.parent,
      convention: frame.convention,
      parameters: frame.parameters,
    })),
    massProperties: state.massProperties,
    flight: state.flight,
    controls: state.controls,
    loads: state.loads,
  };
}

export function vehicleStateDigest(state: FlyingVehicleState): string {
  return contentDigest(canonicalVehicleState(state));
}

/** Deterministic SHA-256 content hash of a raw vehicle-state document. */
export function vehicleStateHash(payload: unknown): string {
  return vehicleStateDigest(parseVehicleState(payload));
}

/** Classify a vehicle-state change onto the existing design-section vocabulary. */
export function topologyChangeSections(before: FlyingVehicleState, after: FlyingVehicleState): readonly string[] {
  const sections = new Set<string>();
  if (JSON.stringify(before.reference) !== JSON.stringify(after.reference)) sections.add("geometry");
  const motion = (state: FlyingVehicleState): unknown => [state.frames, state.flight.position, state.flight.attitude, state.flight.velocity, state.flight.angularRates];
  if (JSON.stringify(motion(before)) !== JSON.stringify(motion(after))) sections.add("motionFrames");
  if (JSON.stringify(before.massProperties) !== JSON.stringify(after.massProperties)) sections.add("parameters");
  if (JSON.stringify(before.controls) !== JSON.stringify(after.controls)) sections.add("parameters");
  const operating = (state: FlyingVehicleState): unknown => [state.flight.flight, state.flight.atmosphere, state.loads];
  if (JSON.stringify(operating(before)) !== JSON.stringify(operating(after))) sections.add("operatingPoints");
  return [...sections].sort();
}

/** Apply the existing design invalidation table to vehicle-state change sections. */
export function vehicleStateInvalidatedNodes(changedSections: readonly string[]): readonly string[] {
  return invalidatedNodes(changedSections);
}
