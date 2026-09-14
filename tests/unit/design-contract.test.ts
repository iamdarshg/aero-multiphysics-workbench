import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { createDesignRevision, invalidatedNodes } from "../../packages/schema/src/design.ts";
import { normalizeQuantity } from "../../packages/units/src/index.ts";

const digest = (character: string) => character.repeat(64);

function fullRevision() {
  return createDesignRevision({
    designId: "generic-duct",
    revisionId: "rev-a",
    parentRevisionHash: null,
    parameters: { clearance: normalizeQuantity(0.7, "mm") },
    parameterRevision: { digest: digest("f"), count: 1 },
    geometry: { digest: digest("a"), semanticDigest: digest("b"), definitionDigest: digest("e") },
    semanticsDigest: digest("b"),
    materials: {
      digest: digest("c"),
      bindings: [
        { region: "duct", materialIdentity: "alloy@r1", materialDigest: digest("c") },
        { region: "shaft", materialIdentity: "steel@r1", materialDigest: digest("d") },
      ],
    },
    operatingPoints: [{ name: "cruise", values: { rpm: normalizeQuantity(1000, "mm") } }],
    objectives: [{ name: "thrust", target: "maximize", weight: 1 }],
    constraints: [{ name: "max-stress", bound: "upper", limitSI: 2e8, unit: "Pa" }],
    solverPolicy: { solver: "generic", version: "1.0.0", settings: {} },
    participantSolvers: [
      { participant: "fluid", solver: "generic-cfd", version: "1.0.0", settings: {} },
      { participant: "structure", solver: "generic-fem", version: "1.0.0", settings: {} },
    ],
    coupling: { strength: 0.9, pairs: [{ from: "fluid", to: "structure", quantities: ["pressure"] }], policy: {} },
    computePolicy: { backend: "local" },
    fidelityPolicy: { default: "screening" },
    motionFrames: [{ name: "rotor-0", kind: "rotating", axis: [0, 0, 1], rateSI: 100 }],
    interfaces: [{ name: "fsi-0", domainA: "fluid", domainB: "structure", kind: "fsi" }],
  });
}

describe("full physical design contract", () => {
  it("hashes every contract section and invalidates on each change", () => {
    const baseline = fullRevision();
    assert.match(baseline.contentHash, /^[a-f0-9]{64}$/);

    const materialChange = createDesignRevision({
      ...structuredClone({ ...baseline, contentHash: undefined }),
      revisionId: "rev-b",
      materials: { digest: digest("9"), bindings: baseline.materials.bindings },
    } as never);
    assert.notEqual(materialChange.contentHash, baseline.contentHash);

    const couplingChange = createDesignRevision({
      ...structuredClone({ ...baseline, contentHash: undefined }),
      revisionId: "rev-c",
      coupling: { strength: 0.5, pairs: [], policy: {} },
    } as never);
    assert.notEqual(couplingChange.contentHash, baseline.contentHash);
  });

  it("rejects bad digests, bad coupling strength, and bad bindings", () => {
    const baseline = fullRevision();
    const clone = () => structuredClone({ ...baseline, contentHash: undefined }) as never;
    assert.throws(() => createDesignRevision({ ...clone(), revisionId: "x", geometry: { digest: "nope", semanticDigest: digest("b") } } as never), /geometry/);
    assert.throws(() => createDesignRevision({ ...clone(), revisionId: "x", coupling: { strength: 2, pairs: [], policy: {} } } as never), /coupling strength/);
    assert.throws(() => createDesignRevision({
      ...clone(),
      revisionId: "x",
      materials: { digest: digest("c"), bindings: [{ region: "", materialIdentity: "x", materialDigest: digest("c") }] },
    } as never), /region/);
  });

  it("maps every mandated change kind to downstream nodes", () => {
    for (const section of ["materials", "geometry", "semantics", "operatingPoints", "participantSolvers", "coupling"]) {
      const nodes = invalidatedNodes([section]);
      assert.ok(nodes.length > 0, section);
    }
    assert.ok(invalidatedNodes(["materials"]).includes("structural"));
    assert.ok(invalidatedNodes(["geometry"]).includes("mesh"));
    assert.ok(invalidatedNodes(["coupling"]).includes("coupled-analysis"));
    assert.deepEqual(invalidatedNodes(["nope"]), ["all"]);
  });
});
