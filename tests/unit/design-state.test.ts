import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { describe, it } from "node:test";

import { createDesignRevision, createVariantRevision } from "../../packages/schema/src/design.ts";
import { normalizeQuantity } from "../../packages/units/src/index.ts";
import { ContentAddressedCache, createContentKey } from "../../packages/cache/src/content-addressed.ts";
import { ProvenanceLedger } from "../../packages/provenance/src/ledger.ts";

const digest = (character: string) => character.repeat(64);

function baseRevision(clearance: ReturnType<typeof normalizeQuantity>) {
  return createDesignRevision({
    designId: "edf-70",
    revisionId: "rev-a",
    parentRevisionHash: null,
    parameters: { tipClearance: clearance },
    geometry: { digest: digest("a"), semanticDigest: digest("b") },
    materials: { digest: digest("c") },
    solverPolicy: {
      solver: "analytical-edf",
      version: "1.0.0",
      settings: { tolerance: 0.000001, iterations: 80 },
    },
  });
}

describe("canonical design state", () => {
  it("normalizes equivalent dimensions before hashing", () => {
    const millimetres = baseRevision(normalizeQuantity(70, "mm"));
    const metres = baseRevision(normalizeQuantity(0.07, "m"));

    assert.equal(millimetres.parameters.tipClearance.valueSI, 0.07);
    assert.equal(millimetres.parameters.tipClearance.dimension, "length");
    assert.equal(millimetres.contentHash, metres.contentHash);
    assert.match(millimetres.contentHash, /^[a-f0-9]{64}$/);
  });

  it("rejects unknown units and non-finite quantities", () => {
    assert.throws(() => normalizeQuantity(1, "furlong"), /unsupported unit/i);
    assert.throws(() => normalizeQuantity(Number.NaN, "m"), /finite/i);
  });

  it("creates an immutable parent-linked variant without mutating its parent", () => {
    const parent = baseRevision(normalizeQuantity(0.7, "mm"));
    const variant = createVariantRevision(parent, {
      revisionId: "rev-b",
      parameterChanges: { tipClearance: normalizeQuantity(0.8, "mm") },
      author: "engineer",
      reason: "clearance study",
      createdAt: "2026-09-09T18:00:00.000Z",
    });

    assert.equal(parent.parameters.tipClearance.valueSI, 0.0007);
    assert.equal(variant.parameters.tipClearance.valueSI, 0.0008);
    assert.equal(variant.parentRevisionHash, parent.contentHash);
    assert.notEqual(variant.contentHash, parent.contentHash);
    assert.throws(() => Object.assign(parent.parameters, { tipClearance: normalizeQuantity(1, "mm") }), TypeError);
  });

  it("changes a node key when semantic, material, solver, or upstream content changes", () => {
    const common = {
      nodeType: "edf.performance",
      geometryHash: digest("a"),
      semanticHash: digest("b"),
      materialHash: digest("c"),
      upstreamKeys: [digest("d")],
      solver: { id: "analytical-edf", version: "1.0.0" },
      settings: { tolerance: 0.000001 },
    };
    const baseline = createContentKey(common);

    assert.notEqual(createContentKey({ ...common, semanticHash: digest("e") }), baseline);
    assert.notEqual(createContentKey({ ...common, materialHash: digest("e") }), baseline);
    assert.notEqual(createContentKey({ ...common, solver: { ...common.solver, version: "1.0.1" } }), baseline);
    assert.notEqual(createContentKey({ ...common, upstreamKeys: [digest("e")] }), baseline);
  });

  it("produces the same content key in a fresh process", () => {
    const moduleUrl = new URL("../../packages/cache/src/content-addressed.ts", import.meta.url).href;
    const script = `import { createContentKey } from ${JSON.stringify(moduleUrl)};
      const d = (c) => c.repeat(64);
      process.stdout.write(createContentKey({nodeType:"edf.performance",geometryHash:d("a"),semanticHash:d("b"),materialHash:d("c"),upstreamKeys:[d("d")],solver:{id:"analytical-edf",version:"1.0.0"},settings:{tolerance:0.000001}}));`;
    const child = spawnSync(process.execPath, ["--experimental-strip-types", "--input-type=module", "--eval", script], { encoding: "utf8" });
    const local = createContentKey({
      nodeType: "edf.performance",
      geometryHash: digest("a"),
      semanticHash: digest("b"),
      materialHash: digest("c"),
      upstreamKeys: [digest("d")],
      solver: { id: "analytical-edf", version: "1.0.0" },
      settings: { tolerance: 0.000001 },
    });

    assert.equal(child.status, 0, child.stderr);
    assert.equal(child.stdout, local);
  });
});

describe("cache and provenance contracts", () => {
  it("keeps content-addressed entries immutable", () => {
    const cache = new ContentAddressedCache<{ artifactDigest: string }>();
    const key = digest("1");
    cache.put(key, { artifactDigest: digest("2") });

    assert.deepEqual(cache.get(key), { artifactDigest: digest("2") });
    const copy = cache.get(key);
    assert.ok(copy);
    copy.artifactDigest = digest("4");
    assert.deepEqual(cache.get(key), { artifactDigest: digest("2") });
    assert.throws(() => cache.put(key, { artifactDigest: digest("3") }), /immutable/i);
  });

  it("chains append-only provenance and permits external engineering artifact formats", () => {
    const ledger = new ProvenanceLedger();
    const first = ledger.append({
      eventType: "design.created",
      subjectHash: digest("a"),
      actor: "engineer",
      occurredAt: "2026-09-09T18:00:00.000Z",
      artifacts: [{ format: "step", uri: "artifacts/edf.step", sha256: digest("b"), bytes: 128 }],
      details: { fidelity: "analytical" },
    });
    const second = ledger.append({
      eventType: "result.published",
      subjectHash: digest("c"),
      actor: "worker:local",
      occurredAt: "2026-09-09T18:01:00.000Z",
      artifacts: [
        { format: "parquet", uri: "artifacts/points.parquet", sha256: digest("d"), bytes: 256 },
        { format: "vtk", uri: "artifacts/field.vtu", sha256: digest("e"), bytes: 512 },
        { format: "gltf", uri: "artifacts/view.glb", sha256: digest("f"), bytes: 1024 },
        { format: "brep", uri: "artifacts/body.brep", sha256: digest("1"), bytes: 2048 },
        { format: "hdf5", uri: "artifacts/state.h5", sha256: digest("2"), bytes: 4096 },
        { format: "zarr", uri: "artifacts/state.zarr", sha256: digest("3"), bytes: 8192 },
      ],
      details: { eligible: false },
    });

    assert.equal(first.sequence, 1);
    assert.equal(second.sequence, 2);
    assert.equal(second.previousEventHash, first.eventHash);
    assert.match(second.eventHash, /^[a-f0-9]{64}$/);
    assert.deepEqual(ledger.list().map((event) => event.eventHash), [first.eventHash, second.eventHash]);
    assert.throws(() => Array.prototype.pop.call(ledger.list()), TypeError);
    assert.throws(() => Object.assign(first, { actor: "rewritten" }), TypeError);
    assert.throws(
      () => ledger.append({ ...second, sequence: undefined, eventHash: undefined, previousEventHash: undefined, artifacts: [{ format: "csv", uri: "x.csv", sha256: digest("4"), bytes: 1 }] } as never),
      /artifact format/i,
    );
  });
});
