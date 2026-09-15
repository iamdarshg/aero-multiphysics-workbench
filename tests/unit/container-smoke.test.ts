import assert from "node:assert/strict";
import { join } from "node:path";
import test from "node:test";

import { parseArgs, resolveConfig } from "../../scripts/platform/container-smoke.mjs";

test("container smoke arg parsing has deterministic defaults", () => {
  const defaults = parseArgs([]);
  assert.equal(defaults.image, "aero-platform:ci");
  assert.equal(defaults.apiPort, 8000);
  assert.equal(defaults.webPort, 3000);
  assert.equal(defaults.help, false);

  const custom = parseArgs(["--image", "aero-platform:pr-1", "--api-port", "18000"]);
  assert.equal(custom.image, "aero-platform:pr-1");
  assert.equal(custom.apiPort, 18000);

  assert.throws(() => parseArgs(["--api-port", "huge"]), /SMOKE_USAGE/);
  assert.throws(() => parseArgs(["--bogus-flag"]), /SMOKE_USAGE/);
  assert.deepEqual(parseArgs(["--help"]).help, true);
});

test("container smoke config resolves compose intent and the API base", () => {
  const config = resolveConfig({ argv: [], env: {}, root: "/repo" });
  assert.equal(config.apiBase, "http://127.0.0.1:8000");
  assert.equal(config.composeFile, join("/repo", "infra", "docker", "compose.local.yml"));
  assert.equal(config.dockerfile, join("/repo", "infra", "docker", "Dockerfile.platform"));
  assert.ok(config.buildTimeoutMs >= 60_000);
  assert.ok(config.healthTimeoutMs >= 60_000);
});
