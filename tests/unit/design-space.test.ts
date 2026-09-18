import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  activeVariableIds,
  candidateHash,
  createDesignRevision,
  flattenDesignState,
  preflightDesignState,
  unflattenDesignState,
  validateDesignSpace,
  type DesignSpace,
  type DesignState,
} from "../../packages/schema/src/design.ts";

/**
 * Canonical JSON shared with tests/physics/test_gen02_design_space.py. The two
 * layers must parse this identical document and agree on candidateHash.
 */
export const CROSS_LANGUAGE_FIXTURE = String.raw`{
  "id": "gen02-crosslang",
  "variables": [
    { "id": "thickness", "name": "Wall thickness", "kind": "continuous", "unit": "mm",
      "bindings": [{ "target": "parameter", "path": "shell.thickness", "unit": "mm" }],
      "baseValue": 2.0, "mutationScale": 0.25,
      "domain": { "kind": "continuous", "lower": 0.5, "upper": 10.0 } },
    { "id": "segments", "kind": "integer",
      "bindings": [{ "target": "parameter", "path": "ring.segments" }],
      "baseValue": 3,
      "domain": { "kind": "integer", "lower": 1, "upper": 6, "step": 1 } },
    { "id": "taper", "kind": "discrete",
      "bindings": [{ "target": "parameter", "path": "blade.taper" }],
      "baseValue": 1.0,
      "domain": { "kind": "discrete", "values": [0.5, 1.0, 1.5] } },
    { "id": "material", "kind": "categorical",
      "bindings": [{ "target": "material", "path": "region.hot" }],
      "baseValue": "alloy",
      "domain": { "kind": "categorical", "values": ["alloy", "steel"] } },
    { "id": "hollow", "kind": "boolean",
      "bindings": [{ "target": "parameter", "path": "shell.hollow" }],
      "baseValue": false, "domain": { "kind": "boolean" } },
    { "id": "ribbed", "kind": "boolean",
      "bindings": [{ "target": "parameter", "path": "shell.ribbed" }],
      "baseValue": false, "domain": { "kind": "boolean" } },
    { "id": "profile", "kind": "vector-profile", "unit": "mm",
      "bindings": [{ "target": "parameter", "path": "airfoil.camber" }],
      "domain": { "kind": "vector-profile", "lengthVariable": "segments",
        "controlPoints": [
          { "id": "p0", "lower": 0, "upper": 5, "baseValue": 1 },
          { "id": "p1", "lower": 0, "upper": 5, "baseValue": 2 },
          { "id": "p2", "lower": 0, "upper": 5, "baseValue": 3 },
          { "id": "p3", "lower": 0, "upper": 5, "baseValue": 4 },
          { "id": "p4", "lower": 0, "upper": 5, "baseValue": 3 },
          { "id": "p5", "lower": 0, "upper": 5, "baseValue": 2 }
        ] } },
    { "id": "wallOuter", "kind": "linked", "unit": "mm",
      "bindings": [{ "target": "parameter", "path": "shell.outer" }],
      "domain": { "kind": "linked", "targetVariable": "thickness", "scale": 2.0 } },
    { "id": "area", "kind": "derived", "unit": "mm",
      "bindings": [{ "target": "parameter", "path": "shell.area" }],
      "domain": { "kind": "derived", "expression": { "op": "multiply",
        "left": { "op": "variable", "variable": "thickness" },
        "right": { "op": "constant", "value": 4 } } } },
    { "id": "slotWidth", "kind": "continuous", "unit": "mm",
      "bindings": [{ "target": "solver", "path": "mesh.slot", "unit": "mm" }],
      "baseValue": 1.0,
      "activeWhen": { "op": "equals", "variable": "material", "value": "alloy" },
      "domain": { "kind": "continuous", "lower": 0.0, "upper": 3.0 } }
  ],
  "branches": [
    { "id": "material-branch", "selector": "material",
      "options": { "alloy": ["slotWidth"], "steel": [] } }
  ],
  "constraints": [
    { "id": "shell-mutex", "kind": "mutually-exclusive", "variables": ["hollow", "ribbed"] },
    { "id": "steel-requires-ribbed", "kind": "requires",
      "when": { "op": "equals", "variable": "material", "value": "steel" },
      "require": { "op": "equals", "variable": "ribbed", "value": true } },
    { "id": "length-check", "kind": "count", "countVariable": "segments", "memberVariable": "profile" },
    { "id": "thin-limit", "kind": "relation",
      "expression": { "op": "variable", "variable": "thickness" },
      "relation": "lessOrEqual", "limit": 0.008 }
  ]
}`;

const CROSS_LANGUAGE_STATE = String.raw`{
  "thickness": { "kind": "number", "value": 2.0, "unit": "mm" },
  "segments": { "kind": "dimensionless", "value": 3 },
  "taper": { "kind": "dimensionless", "value": 1.0 },
  "material": { "kind": "categorical", "value": "alloy" },
  "hollow": { "kind": "boolean", "value": true },
  "ribbed": { "kind": "boolean", "value": false },
  "profile": { "kind": "vector-profile", "points": [
    { "id": "p0", "value": 1.0, "unit": "mm" },
    { "id": "p1", "value": 2.0, "unit": "mm" },
    { "id": "p2", "value": 3.0, "unit": "mm" }
  ] }
}`;

const CROSS_LANGUAGE_HASH = "38cf9ebbe8335edf812c7424f4ca1dfd7075c316e07495912750ff3d1259aa77";

function fixture(): DesignSpace {
  return JSON.parse(CROSS_LANGUAGE_FIXTURE) as DesignSpace;
}

function baseState(): DesignState {
  return JSON.parse(CROSS_LANGUAGE_STATE) as DesignState;
}

function withState(overrides: DesignState): DesignState {
  return { ...baseState(), ...overrides };
}

describe("GEN 02 design-space validation", () => {
  it("accepts the canonical mixed/hierarchical fixture", () => {
    assert.doesNotThrow(() => validateDesignSpace(fixture()));
  });

  it("fails closed on duplicate variables, unknown kinds, and cycles", () => {
    const duplicate = fixture();
    (duplicate.variables as unknown[]).push(structuredClone(duplicate.variables[0]));
    assert.throws(() => validateDesignSpace(duplicate), /DUPLICATE_VARIABLE/);

    const badKind = structuredClone(fixture()) as unknown as { variables: { kind: string }[] };
    badKind.variables[0].kind = "quantum";
    assert.throws(() => validateDesignSpace(badKind as never), /DOMAIN_KIND_MISMATCH|UNKNOWN_VARIABLE_KIND/);

    const cyclic = structuredClone(fixture()) as unknown as {
      variables: { id: string; kind: string; domain: unknown }[];
    };
    const area = cyclic.variables.find((variable) => variable.id === "area")!;
    area.kind = "derived";
    area.domain = { kind: "derived", expression: { op: "variable", variable: "wallOuter" } };
    const wallOuter = cyclic.variables.find((variable) => variable.id === "wallOuter")!;
    wallOuter.kind = "derived";
    wallOuter.domain = { kind: "derived", expression: { op: "variable", variable: "area" } };
    assert.throws(() => validateDesignSpace(cyclic as never), /DESIGN_SPACE_CYCLE/);
  });

  it("rejects profile points beyond their bounds and non-integer length variables", () => {
    const outOfBounds = withState({
      profile: { kind: "vector-profile", points: [{ id: "p0", value: 99, unit: "mm" }] },
    });
    assert.throws(() => flattenDesignState(fixture(), outOfBounds), /PREFLIGHT_FAILED/);

    const badLength = structuredClone(fixture()) as unknown as {
      variables: { id: string; domain: { lengthVariable?: string } }[];
    };
    badLength.variables.find((variable) => variable.id === "profile")!.domain.lengthVariable = "thickness";
    assert.throws(() => validateDesignSpace(badLength as never), /PROFILE_LENGTH_NEEDS_INTEGER/);
  });
});

describe("GEN 02 flatten / unflatten", () => {
  it("round-trips every variable kind losslessly", () => {
    const space = fixture();
    const flat = flattenDesignState(space, baseState());
    const rebuilt = unflattenDesignState(space, flat);
    const flatAgain = flattenDesignState(space, rebuilt);

    assert.deepEqual(flatAgain, flat);
    for (const kind of ["continuous", "integer", "discrete", "categorical", "boolean", "vector-profile", "linked", "derived"]) {
      assert.ok(flat.entries.some((entry) => entry.kind === kind), kind);
    }
  });

  it("normalizes unit-bearing values and bounds before evaluation", () => {
    const space = fixture();
    const millimetres = flattenDesignState(space, withState({ thickness: { kind: "number", value: 2.0, unit: "mm" } }));
    const metres = flattenDesignState(space, withState({ thickness: { kind: "number", value: 0.002, unit: "m" } }));

    const entry = (flat: ReturnType<typeof flattenDesignState>) => flat.entries.find((item) => item.id === "thickness")!;
    assert.equal(entry(millimetres).valueSI, 0.002);
    assert.equal(entry(metres).valueSI, 0.002);
    assert.equal(candidateHash(millimetres), candidateHash(metres));

    assert.throws(
      () => flattenDesignState(space, withState({ thickness: { kind: "number", value: 20, unit: "mm" } })),
      /PREFLIGHT_FAILED/,
    );
  });

  it("activates and deactivates conditional variables deterministically", () => {
    const space = fixture();
    const alloy = flattenDesignState(space, baseState());
    const steelState = withState({
      material: { kind: "categorical", value: "steel" },
      ribbed: { kind: "boolean", value: true },
      hollow: { kind: "boolean", value: false },
    });
    const steel = flattenDesignState(space, steelState);

    assert.ok(alloy.order.includes("slotWidth"));
    assert.ok(activeVariableIds(space, baseState()).includes("slotWidth"));
    assert.ok(steel.inactive.includes("slotWidth"));
    assert.ok(!steel.order.includes("slotWidth"));
    assert.ok(!activeVariableIds(space, steelState).includes("slotWidth"));
  });

  it("rebuilds vector profiles from their controlled length", () => {
    const space = fixture();
    const shortened = flattenDesignState(space, withState({
      segments: { kind: "dimensionless", value: 2 },
      profile: { kind: "vector-profile", points: [
        { id: "p0", value: 1.0, unit: "mm" },
        { id: "p1", value: 2.0, unit: "mm" },
      ] },
    }));
    const profile = shortened.entries.find((entry) => entry.id === "profile")!;

    assert.equal(profile.points?.length, 2);
    assert.deepEqual(profile.points?.map((point) => point.id), ["p0", "p1"]);
    assert.deepEqual(unflattenDesignState(space, shortened).profile, {
      kind: "vector-profile",
      points: [
        { id: "p0", value: 1, unit: "mm" },
        { id: "p1", value: 2, unit: "mm" },
      ],
    });
  });

  it("does not sample linked or derived variables independently", () => {
    const flat = flattenDesignState(fixture(), baseState());
    const linked = flat.entries.find((entry) => entry.id === "wallOuter")!;
    const derived = flat.entries.find((entry) => entry.id === "area")!;

    assert.equal(linked.valueSI, 0.004);
    assert.equal(derived.valueSI, 0.008);
    const rebuilt = unflattenDesignState(fixture(), flat);
    assert.equal(rebuilt.wallOuter, undefined);
    assert.equal(rebuilt.area, undefined);
  });
});

describe("GEN 02 preflight and hashing", () => {
  it("rejects invalid categorical choices and compatibility violations", () => {
    const space = fixture();
    assert.throws(
      () => flattenDesignState(space, withState({ material: { kind: "categorical", value: "titanium" } })),
      /PREFLIGHT_FAILED/,
    );
    assert.throws(
      () => flattenDesignState(space, withState({ material: { kind: "categorical", value: "steel" } })),
      /PREFLIGHT_FAILED/,
    );
  });

  it("rejects mutually exclusive and algebraic violations without physics", () => {
    const space = fixture();
    assert.throws(
      () => flattenDesignState(space, withState({
        hollow: { kind: "boolean", value: true },
        ribbed: { kind: "boolean", value: true },
      })),
      /MUTUALLY_EXCLUSIVE_VIOLATION/,
    );
    assert.throws(
      () => flattenDesignState(space, withState({ thickness: { kind: "number", value: 9, unit: "mm" } })),
      /thin-limit:RELATION_VIOLATION/,
    );
    assert.throws(
      () => flattenDesignState(space, withState({ segments: { kind: "dimensionless", value: 2 } })),
      /length-check:COUNT_MISMATCH/,
    );
  });

  it("hashes stably regardless of JSON key ordering", () => {
    const space = fixture();
    const first = baseState();
    const reordered = JSON.parse(
      `{"ribbed":{"kind":"boolean","value":false},"material":{"kind":"categorical","value":"alloy"},"thickness":{"kind":"number","unit":"mm","value":2.0},"segments":{"kind":"dimensionless","value":3},"taper":{"kind":"dimensionless","value":1.0},"hollow":{"kind":"boolean","value":true},"profile":{"points":[{"value":1.0,"id":"p0","unit":"mm"},{"value":2.0,"id":"p1","unit":"mm"},{"value":3.0,"id":"p2","unit":"mm"}],"kind":"vector-profile"}}`,
    ) as DesignState;

    assert.equal(candidateHash(flattenDesignState(space, first)), candidateHash(flattenDesignState(space, reordered)));
  });

  it("matches the Python candidate hash for the shared fixture", () => {
    const flat = flattenDesignState(fixture(), baseState());
    assert.equal(candidateHash(flat), CROSS_LANGUAGE_HASH);
  });
});

describe("GEN 02 conditional rules and binding targets", () => {
  const branchSpace = (): DesignSpace => ({
    id: "branch-only",
    variables: [
      {
        id: "mode",
        kind: "categorical",
        bindings: [{ target: "solver", path: "mode" }],
        baseValue: "a",
        domain: { kind: "categorical", values: ["a", "b"] },
      },
      {
        id: "x",
        kind: "continuous",
        unit: "mm",
        bindings: [{ target: "parameter", path: "x" }],
        baseValue: 1,
        domain: { kind: "continuous", lower: 0, upper: 2 },
      },
      {
        id: "y",
        kind: "continuous",
        unit: "mm",
        bindings: [{ target: "material", path: "y" }],
        baseValue: 1,
        domain: { kind: "continuous", lower: 0, upper: 2 },
      },
    ],
    branches: [{ id: "impl", selector: "mode", options: { a: ["x"], b: ["y"] } }],
  });

  it("activates branch members without an explicit activeWhen", () => {
    const space = branchSpace();
    const optionA = flattenDesignState(space, { mode: { kind: "categorical", value: "a" } });
    const optionB = flattenDesignState(space, { mode: { kind: "categorical", value: "b" } });

    assert.deepEqual(optionA.order, ["mode", "x"]);
    assert.deepEqual(optionA.inactive, ["y"]);
    assert.deepEqual(optionB.order, ["mode", "y"]);
    assert.deepEqual(optionB.inactive, ["x"]);
  });

  it("accepts parameter, material, and solver binding targets and rejects others", () => {
    assert.doesNotThrow(() => validateDesignSpace(branchSpace()));
    const invalid = structuredClone(branchSpace()) as unknown as {
      variables: { bindings: { target: string }[] }[];
    };
    invalid.variables[0].bindings[0].target = "telemetry";
    assert.throws(() => validateDesignSpace(invalid as never), /UNKNOWN_BINDING_TARGET/);
  });
});

describe("GEN 02 design revision integration", () => {
  const digest = (character: string) => character.repeat(64);

  function revision(space?: DesignSpace) {
    return createDesignRevision({
      designId: "gen02",
      revisionId: "rev-a",
      parentRevisionHash: null,
      parameters: {},
      geometry: { digest: digest("a"), semanticDigest: digest("b") },
      materials: { digest: digest("c") },
      solverPolicy: { solver: "generic", version: "1.0.0", settings: {} },
      ...(space ? { designSpace: space } : {}),
    });
  }

  it("changes the revision hash when the design space definition changes", () => {
    const baseline = revision(fixture());
    const same = revision(fixture());
    assert.equal(baseline.contentHash, same.contentHash);

    const changed = structuredClone(fixture()) as unknown as { variables: { domain: { upper?: number } }[] };
    changed.variables[0].domain.upper = 12.0;
    assert.notEqual(revision(changed as never).contentHash, baseline.contentHash);
  });

  it("still loads legacy revisions without a design space", () => {
    const legacy = revision();
    assert.equal(legacy.designSpace, undefined);
    assert.match(legacy.contentHash, /^[a-f0-9]{64}$/);
    assert.doesNotThrow(() => preflightDesignState(fixture(), baseState()));
  });
});
