// Tiered Node perf regression tests (run with: node --test tests/perf/*.test.mjs).
//
// Bounded deterministic microbenchmarks plus committed-budget contract checks.
// The heavy, environment-sensitive cold-start measurements live in the
// perf-smoke harness, not here, so this file stays fast and non-flaky.
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

import { ContentAddressedCache, contentDigest } from "../../packages/cache/src/content-addressed.ts";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..");
const BUDGETS_PATH = join(ROOT, "benchmarks", "perf", "budgets.json");
const KNOWN_METRICS = new Set([
  "median_ms", "p95_ms", "total_ms", "per_item_ms", "items_per_second", "mib_per_second",
]);

const nowMs = () => Number(process.hrtime.bigint()) / 1e6;

function percentile(sorted, fraction) {
  if (sorted.length === 1) return sorted[0];
  const rank = fraction * (sorted.length - 1);
  const low = Math.floor(rank);
  const high = Math.ceil(rank);
  if (low === high) return sorted[low];
  return sorted[low] + (sorted[high] - sorted[low]) * (rank - low);
}

test("budget manifest is well formed", async () => {
  const manifest = JSON.parse(await readFile(BUDGETS_PATH, "utf8"));
  assert.equal(manifest.schemaVersion, 1);
  assert.ok(manifest.policy.trim().length > 0);
  assert.ok(Array.isArray(manifest.budgets) && manifest.budgets.length > 0);
  const ids = manifest.budgets.map((entry) => entry.id);
  assert.equal(new Set(ids).size, ids.length, "budget ids must be unique");
  for (const entry of manifest.budgets) {
    assert.ok(entry.id && entry.id.trim(), JSON.stringify(entry));
    assert.ok(KNOWN_METRICS.has(entry.metric), JSON.stringify(entry));
    assert.ok(entry.direction === "max" || entry.direction === "min", JSON.stringify(entry));
    assert.ok(Number.isFinite(entry.limit) && entry.limit > 0, JSON.stringify(entry));
    assert.ok(entry.rationale && entry.rationale.trim(), JSON.stringify(entry));
  }
});

test("content-addressed cache lookup is bounded", () => {
  const cache = new ContentAddressedCache();
  const entries = 64;
  const lookups = 4_000;
  const keys = [];
  for (let index = 0; index < entries; index += 1) {
    const key = createHash("sha256").update(`t-${index}`).digest("hex");
    keys.push(key);
    cache.put(key, { index });
  }
  const samples = [];
  for (let index = 0; index < lookups; index += 1) {
    const start = nowMs();
    cache.get(keys[index % entries]);
    samples.push(nowMs() - start);
  }
  const p95 = percentile([...samples].sort((a, b) => a - b), 0.95);
  assert.ok(p95 < 50, `p95 lookup ${p95}ms exceeded the 50ms hang guard`);
});

test("canonical digest is bounded and deterministic", () => {
  const payload = { node: "n1", settings: { index: 1, tolerance: 1e-6 }, upstream: ["a".repeat(64)] };
  const first = contentDigest(payload);
  assert.match(first, /^[0-9a-f]{64}$/);
  const samples = [];
  for (let index = 0; index < 2_000; index += 1) {
    const start = nowMs();
    contentDigest(payload);
    samples.push(nowMs() - start);
  }
  assert.equal(contentDigest(payload), first);
  const p95 = percentile([...samples].sort((a, b) => a - b), 0.95);
  assert.ok(p95 < 50, `p95 digest ${p95}ms exceeded the 50ms hang guard`);
});
