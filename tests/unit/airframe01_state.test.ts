import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, it } from "node:test";

import {
  canonicalVehicleState,
  parseVehicleState,
  rotationBetween,
  topologyChangeSections,
  vehicleStateDigest,
  vehicleStateHash,
  vehicleStateInvalidatedNodes,
  type FlyingVehicleState,
} from "../../packages/schema/src/vehicle_state.ts";

const fixtureDirectory = fileURLToPath(new URL("../airframe/state/", import.meta.url));
const expectedHashes = JSON.parse(
  readFileSync(`${fixtureDirectory}expected_hashes.json`, "utf8"),
) as Record<string, string>;

function loadFixture(name: string): Record<string, unknown> {
  return JSON.parse(readFileSync(`${fixtureDirectory}${name}`, "utf8")) as Record<string, unknown>;
}

function loadState(name: string): FlyingVehicleState {
  return parseVehicleState(loadFixture(name));
}

function deepClone(value: Record<string, unknown>): Record<string, unknown> {
  return JSON.parse(JSON.stringify(value)) as Record<string, unknown>;
}

describe("AIRFRAME 01 canonical flying-vehicle state", () => {
  it("matches the shared Python vehicle-state hashes", () => {
    for (const name of ["minimal_vehicle_state.json", "equivalent_units_vehicle_state.json"]) {
      const state = loadState(name);
      assert.equal(vehicleStateHash(loadFixture(name)), expectedHashes[state.vehicleId], name);
      assert.equal(vehicleStateDigest(state), expectedHashes[state.vehicleId], name);
    }
  });

  it("hashes identically for equivalent unit representations", () => {
    assert.equal(
      vehicleStateHash(loadFixture("minimal_vehicle_state.json")),
      vehicleStateHash(loadFixture("equivalent_units_vehicle_state.json")),
    );
  });

  it("round-trips canonically without changing identity", () => {
    for (const name of ["minimal_vehicle_state.json", "equivalent_units_vehicle_state.json"]) {
      const state = loadState(name);
      const canonical = canonicalVehicleState(state);
      const rebuilt = parseVehicleState(canonical);
      assert.deepEqual(canonicalVehicleState(rebuilt), canonical, name);
      assert.equal(vehicleStateDigest(rebuilt), vehicleStateDigest(state), name);
    }
  });

  it("hashes independently of array and key order", () => {
    const payload = loadFixture("minimal_vehicle_state.json");
    const reordered = {
      loads: payload.loads,
      controls: payload.controls,
      flight: payload.flight,
      massProperties: payload.massProperties,
      frames: (payload.frames as unknown[]).slice().reverse(),
      reference: payload.reference,
      architectureType: payload.architectureType,
      vehicleId: payload.vehicleId,
      schemaVersion: payload.schemaVersion,
    };
    assert.equal(vehicleStateHash(reordered), vehicleStateHash(payload));
  });

  it("keeps frame transforms deterministic and orthonormal", () => {
    const state = loadState("minimal_vehicle_state.json");
    const bodiedFromNed = rotationBetween(state.frames, "ned", "body");
    const inverse = rotationBetween(state.frames, "body", "ned");
    const product = bodiedFromNed.map((row, row_index) =>
      row.map((_, col) => row.reduce((sum, value, k) => sum + value * inverse[k][col], 0)),
    );
    for (let row = 0; row < 3; row += 1) {
      for (let col = 0; col < 3; col += 1) {
        assert.ok(Math.abs(product[row][col] - (row === col ? 1 : 0)) < 1e-12);
      }
    }
  });

  it("projects state changes onto the existing invalidation table", () => {
    const before = loadState("minimal_vehicle_state.json");
    const changed = deepClone(loadFixture("minimal_vehicle_state.json"));
    ((changed.reference as Record<string, Record<string, number>>).span).value = 0.7;
    assert.deepEqual(topologyChangeSections(before, parseVehicleState(changed)), ["geometry"]);
    const invalidated = vehicleStateInvalidatedNodes(["geometry"]);
    assert.ok(invalidated.includes("mesh"));
    assert.ok(invalidated.includes("analysis"));

    const motion = deepClone(loadFixture("minimal_vehicle_state.json"));
    ((motion.flight as Record<string, Record<string, Record<string, Record<string, number>>>>).attitude.angles).yaw.value = 20;
    assert.deepEqual(topologyChangeSections(before, parseVehicleState(motion)), ["motionFrames"]);
  });

  it("fails closed on mixed conventions, unknown frames, and bad units", () => {
    const mismatch = deepClone(loadFixture("minimal_vehicle_state.json"));
    ((mismatch.flight as Record<string, Record<string, unknown>>).attitude).convention = "alpha_beta";
    assert.throws(() => parseVehicleState(mismatch), /FRAME_CONVENTION_MISMATCH|ATTITUDE_CONVENTION/);

    const undeclared = deepClone(loadFixture("minimal_vehicle_state.json"));
    ((undeclared.flight as Record<string, Record<string, unknown>>).velocity).frame = "geodetic";
    assert.throws(() => parseVehicleState(undeclared), /UNKNOWN_FRAME/);

    const badParent = deepClone(loadFixture("minimal_vehicle_state.json"));
    for (const frame of badParent.frames as Record<string, unknown>[]) {
      if (frame.id === "wind") frame.parent = "ned";
    }
    assert.throws(() => parseVehicleState(badParent), /FRAME_PARENT_KIND_MISMATCH/);

    const badUnit = deepClone(loadFixture("minimal_vehicle_state.json"));
    ((badUnit.massProperties as Record<string, Record<string, string>>).mass).unit = "furlongs";
    assert.throws(() => parseVehicleState(badUnit), /UNKNOWN_UNIT/);

    const badDimension = deepClone(loadFixture("minimal_vehicle_state.json"));
    const flight = (badDimension.flight as Record<string, Record<string, Record<string, string>>>).flight;
    flight.altitude.unit = "N";
    assert.throws(() => parseVehicleState(badDimension), /QUANTITY_DIMENSION_MISMATCH/);
  });
});
