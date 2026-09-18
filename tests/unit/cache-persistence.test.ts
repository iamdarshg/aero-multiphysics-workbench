import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, readdirSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { after, describe, it } from "node:test";

import { createContentKey } from "../../packages/cache/src/content-addressed.ts";
import {
  CacheImmutabilityError,
  CacheIntegrityError,
  CacheReuseError,
  PersistentContentAddressedCache,
  type CacheEntryInput,
} from "../../packages/cache/src/persistent-cache.ts";

const digest = (character: string) => character.repeat(64);
const roots: string[] = [];

function tempRoot(): string {
  const root = mkdtempSync(join(tmpdir(), "aero-cache-"));
  roots.push(root);
  return root;
}

function meta(overrides: Partial<CacheEntryInput> = {}): CacheEntryInput {
  return { nodeType: "edf.performance", family: "analysis", ...overrides };
}

after(() => {
  for (const root of roots) rmSync(root, { recursive: true, force: true });
});

describe("persistent content-addressed cache", () => {
  it("misses, hits, and survives a process restart", async () => {
    const root = tempRoot();
    const key = digest("1");
    const first = new PersistentContentAddressedCache<{ value: number }>({ root });
    let computations = 0;
    const compute = () => {
      computations += 1;
      return { value: 7 };
    };

    const cold = Date.now();
    const coldValue = await first.getOrCompute(key, meta(), compute);
    const coldMs = Date.now() - cold;
    const warm = Date.now();
    const warmValue = await first.getOrCompute(key, meta(), compute);
    const warmMs = Date.now() - warm;
    assert.deepEqual(coldValue, { value: 7 });
    assert.deepEqual(warmValue, { value: 7 });
    assert.equal(computations, 1, "second request must be served from cache");

    const restarted = new PersistentContentAddressedCache<{ value: number }>({ root });
    const resumed = await restarted.getOrCompute(key, meta(), compute);
    assert.deepEqual(resumed, { value: 7 });
    assert.equal(computations, 1, "restart must not recompute reusable work");
    console.log(`[cache-persistence] cold=${coldMs}ms warm=${warmMs}ms restart=hit`);
  });

  it("coalesces one hundred concurrent candidates into a single computation", async () => {
    const root = tempRoot();
    const key = digest("2");
    const cache = new PersistentContentAddressedCache<{ value: number }>({ root });
    let computations = 0;
    const compute = () => {
      computations += 1;
      return new Promise<{ value: number }>((resolve) => {
        setTimeout(() => resolve({ value: computations }), 25);
      });
    };
    const started = Date.now();
    const results = await Promise.all(
      Array.from({ length: 100 }, () => cache.getOrCompute(key, meta({ family: "mesh" }), compute)),
    );
    const elapsedMs = Date.now() - started;
    assert.equal(computations, 1, "in-flight duplicate work must coalesce");
    assert.equal(new Set(results.map((item) => item.value)).size, 1);
    assert.equal(cache.keys().length, 1);
    console.log(`[cache-persistence] coalesced 100 requests into 1 task in ${elapsedMs}ms`);
  });

  it("fails closed on a corrupted or tampered entry instead of hitting", () => {
    const root = tempRoot();
    const key = digest("3");
    const cache = new PersistentContentAddressedCache<{ value: number }>({ root });
    cache.put(key, { value: 1 }, meta());

    const file = join(root, "values", `${key}.json`);
    const record = JSON.parse(readFileSync(file, "utf8")) as { value: { value: number } };
    record.value = { value: 999 };
    writeFileSync(file, JSON.stringify(record), "utf8");

    assert.throws(() => cache.get(key), (error: unknown) => {
      assert.ok(error instanceof CacheIntegrityError);
      assert.equal(error.key, key);
      assert.match(error.message, /digest verification/);
      return true;
    });
  });

  it("rejects overwriting a key with different content", () => {
    const root = tempRoot();
    const key = digest("4");
    const cache = new PersistentContentAddressedCache<{ value: number }>({ root });
    cache.put(key, { value: 1 }, meta());
    cache.put(key, { value: 1 }, meta());
    assert.throws(() => cache.put(key, { value: 2 }, meta()), CacheImmutabilityError);
  });

  it("writes atomically without leaving partial files", () => {
    const root = tempRoot();
    const cache = new PersistentContentAddressedCache<{ value: number }>({ root });
    for (let index = 0; index < 5; index += 1) {
      cache.put(digest(index.toString(16)), { value: index }, meta());
    }
    const files = readdirSync(join(root, "values"));
    assert.equal(files.filter((name) => name.endsWith(".tmp")).length, 0);
    assert.equal(files.filter((name) => name.endsWith(".json")).length, 5);
  });

  it("keeps eviction bounded while pinned results survive", () => {
    const root = tempRoot();
    const cache = new PersistentContentAddressedCache<unknown>({ root, maxBytes: 8192 });
    const keyFor = (index: number) => index.toString(16).padStart(64, "0");
    const pinnedKey = digest("a");
    cache.put(pinnedKey, { payload: "pin" }, meta({ pinned: true }));
    for (let index = 0; index < 24; index += 1) {
      cache.put(keyFor(index), { payload: "x".repeat(1024) }, meta());
    }
    assert.ok(cache.sizeBytes <= 8192, `cache must stay bounded, saw ${cache.sizeBytes}`);
    assert.deepEqual(cache.get(pinnedKey), { payload: "pin" });
    assert.ok(cache.keys().length < 25, "size pressure must evict unpinned entries");
    assert.equal(cache.get(keyFor(0)), undefined, "least-recently-used unpinned entry is evicted");
  });

  it("invalidates a changed upstream and only its descendants", () => {
    const root = tempRoot();
    const cache = new PersistentContentAddressedCache<{ value: number }>({ root });
    const upstream = digest("b");
    const child = digest("c");
    const unrelated = digest("d");
    cache.put(upstream, { value: 1 }, meta({ nodeType: "geometry", family: "geometry" }));
    cache.put(child, { value: 2 }, meta({ nodeType: "mesh", family: "mesh", upstreamKeys: [upstream] }));
    cache.put(unrelated, { value: 3 }, meta({ nodeType: "post", family: "post" }));

    const dropped = cache.invalidate(upstream);
    assert.deepEqual(dropped, [upstream, child].sort());
    assert.equal(cache.get(upstream), undefined);
    assert.equal(cache.get(child), undefined);
    assert.deepEqual(cache.get(unrelated), { value: 3 });
  });

  it("requires matching solver, policy, source, and artifacts for trusted reuse", () => {
    const root = tempRoot();
    const key = digest("e");
    const cache = new PersistentContentAddressedCache<{ source: string }>({ root });
    const artifact = { uri: "artifacts/result.json", sha256: digest("f"), bytes: 12 };
    cache.put(key, { source: "native_solver" }, meta({
      nodeType: "rotor-campbell",
      family: "analysis",
      solver: { id: "ross", version: "2.3.0" },
      source: "native_solver",
      validityPolicyVersion: "policy-v1",
      artifacts: [artifact],
    }));

    const request = {
      solverId: "ross",
      solverVersion: "2.3.0",
      validityPolicyVersion: "policy-v1",
      source: "native_solver",
      resolveArtifact: () => digest("f"),
    };
    assert.deepEqual(cache.reuseIfTrusted(key, request).value, { source: "native_solver" });
    assert.throws(
      () => cache.reuseIfTrusted(key, { ...request, solverVersion: "2.4.0" }),
      (error: unknown) => error instanceof CacheReuseError && error.reason === "SOLVER_IDENTITY_MISMATCH",
    );
    assert.throws(
      () => cache.reuseIfTrusted(key, { ...request, validityPolicyVersion: "policy-v2" }),
      (error: unknown) => error instanceof CacheReuseError && error.reason === "VALIDITY_POLICY_MISMATCH",
    );
    assert.throws(
      () => cache.reuseIfTrusted(key, { ...request, source: "analytical" }),
      (error: unknown) => error instanceof CacheReuseError && error.reason === "SOURCE_MISMATCH",
    );
    assert.throws(
      () => cache.reuseIfTrusted(key, { ...request, resolveArtifact: () => digest("0") }),
      (error: unknown) => error instanceof CacheReuseError && error.reason === "ARTIFACT_DIGEST_MISMATCH",
    );
    assert.throws(
      () => cache.reuseIfTrusted(key, { ...request, resolveArtifact: () => undefined }),
      (error: unknown) => error instanceof CacheReuseError && error.reason === "ARTIFACT_MISSING",
    );
  });
});

describe("canonical cache key covers every reuse axis", () => {
  it("changes the key for mesh, fidelity, policy, participant, inputs, solver, and settings", () => {
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
    assert.equal(createContentKey({ ...common }), baseline, "absent optional axes must not perturb the key");
    assert.notEqual(createContentKey({ ...common, meshHash: digest("e") }), baseline);
    assert.notEqual(createContentKey({ ...common, inputDigest: digest("e") }), baseline);
    assert.notEqual(createContentKey({ ...common, fidelity: "high" }), baseline);
    assert.notEqual(createContentKey({ ...common, participant: "rotor-campbell" }), baseline);
    assert.notEqual(createContentKey({ ...common, validityPolicyVersion: "policy-v2" }), baseline);
    assert.notEqual(
      createContentKey({ ...common, solver: { id: "analytical-edf", version: "1.0.1" } }),
      baseline,
    );
    assert.notEqual(createContentKey({ ...common, settings: { tolerance: 0.001 } }), baseline);
    assert.notEqual(createContentKey({ ...common, semanticHash: digest("e") }), baseline);
  });
});
