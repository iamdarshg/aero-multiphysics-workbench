import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, it } from "node:test";

import {
  architectureDigest,
  architectureHash,
  canonicalArchitecture,
  parseArchitecture,
  rotatingGasInvalidatedNodes,
  topologyChangeSections,
  topologyDigest,
  type RotatingGasArchitecture,
} from "../../packages/schema/src/rotating_gas.ts";

const fixtureDirectory = fileURLToPath(new URL("../turbo/fixtures/", import.meta.url));
const expectedHashes = JSON.parse(
  readFileSync(fileURLToPath(new URL("../turbo/expected_hashes.json", import.meta.url)), "utf8"),
) as Record<string, string>;

const fixtureNames = readdirSync(fixtureDirectory)
  .filter((name) => name.endsWith(".json"))
  .sort();

function loadFixture(name: string): Record<string, unknown> {
  return JSON.parse(readFileSync(`${fixtureDirectory}${name}`, "utf8")) as Record<string, unknown>;
}

function loadArchitecture(name: string): RotatingGasArchitecture {
  return parseArchitecture(loadFixture(name));
}

describe("TURBO 01 rotating-gas architecture", () => {
  it("parses and validates every acceptance fixture", () => {
    assert.equal(fixtureNames.length, 6);
    for (const name of fixtureNames) {
      const architecture = loadArchitecture(name);
      assert.ok(architecture.architectureId.startsWith("turbo01-"));
    }
  });

  it("matches the shared Python architecture hashes", () => {
    for (const name of fixtureNames) {
      const architecture = loadArchitecture(name);
      assert.equal(architectureHash(architecture), expectedHashes[architecture.architectureId], name);
      assert.equal(architectureDigest(architecture), expectedHashes[architecture.architectureId], name);
    }
  });

  it("round-trips canonically without changing identity", () => {
    for (const name of fixtureNames) {
      const architecture = loadArchitecture(name);
      const canonical = canonicalArchitecture(architecture);
      const rebuilt = parseArchitecture(canonical);
      assert.deepEqual(canonicalArchitecture(rebuilt), canonical, name);
      assert.equal(architectureDigest(rebuilt), architectureDigest(architecture), name);
      assert.equal(topologyDigest(rebuilt), topologyDigest(architecture), name);
    }
  });

  it("hashes independently of array and key order", () => {
    for (const name of fixtureNames) {
      const payload = loadFixture(name);
      const reordered = {
        shafts: (payload.shafts as unknown[]).slice().reverse(),
        rows: (payload.rows as unknown[]).slice().reverse(),
        stations: (payload.stations as unknown[]).slice().reverse(),
        edges: (payload.edges as unknown[]).slice().reverse(),
        nodes: (payload.nodes as unknown[]).slice().reverse(),
        defaultFluid: payload.defaultFluid,
        architectureId: payload.architectureId,
        schemaVersion: payload.schemaVersion,
      };
      assert.equal(architectureHash(reordered), architectureHash(payload), name);
    }
  });

  it("keeps the topology digest stable across station value changes", () => {
    const architecture = loadArchitecture("single_ducted_fan.json");
    const changed = loadFixture("single_ducted_fan.json");
    const stations = changed.stations as Record<string, unknown>[];
    (stations[1].state as Record<string, unknown>).totalPressure = { value: 92000, unit: "Pa" };
    assert.equal(topologyDigest(parseArchitecture(changed)), topologyDigest(architecture));
    assert.notEqual(architectureHash(changed), architectureHash(architecture));
  });

  it("projects topology changes onto the existing invalidation table", () => {
    const architecture = loadArchitecture("single_ducted_fan.json");
    const valueChange = loadFixture("single_ducted_fan.json");
    const stations = valueChange.stations as Record<string, unknown>[];
    (stations[1].state as Record<string, unknown>).totalPressure = { value: 92000, unit: "Pa" };
    assert.deepEqual(topologyChangeSections(architecture, parseArchitecture(valueChange)), ["operatingPoints"]);

    const structural = loadFixture("single_ducted_fan.json");
    (structural.nodes as unknown[]).push({ id: "diffuser", kind: "diffuser" });
    (structural.edges as unknown[]).push({ from: "fan", to: "diffuser", kind: "flow", station: "2" });
    (structural.edges as unknown[]).push({ from: "diffuser", to: "nozzle", kind: "flow", station: "2" });
    const sections = topologyChangeSections(architecture, parseArchitecture(structural));
    assert.ok(sections.includes("topologyDigest"));
    const invalidated = rotatingGasInvalidatedNodes(sections);
    assert.ok(invalidated.includes("mesh"));
    assert.ok(invalidated.includes("analysis"));
  });

  it("fails closed on structural inconsistencies", () => {
    const payload = loadFixture("single_ducted_fan.json");
    (payload.rows as Record<string, unknown>[])[0].shaft = null;
    assert.throws(() => parseArchitecture(payload), /ROTATING_ROW_NEEDS_SHAFT/);

    const badUnit = loadFixture("single_ducted_fan.json");
    ((badUnit.stations as Record<string, Record<string, Record<string, unknown>>>[])[1].state).totalPressure = {
      value: 1,
      unit: "furlongs",
    };
    assert.throws(() => parseArchitecture(badUnit), /UNKNOWN_UNIT/);

    const badDimension = loadFixture("single_ducted_fan.json");
    ((badDimension.stations as Record<string, Record<string, Record<string, unknown>>>[])[1].state).massFlow = {
      value: 1,
      unit: "Pa",
    };
    assert.throws(() => parseArchitecture(badDimension), /QUANTITY_DIMENSION_MISMATCH/);
  });
});
