import assert from "node:assert/strict";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import { parseMode, resolveServiceCommand } from "../../infra/docker/platform-entrypoint.mjs";

test("platform entrypoint accepts exactly one service mode", () => {
  assert.equal(parseMode(["api"]).mode, "api");
  assert.equal(parseMode(["web"]).mode, "web");
  assert.equal(parseMode(["mcp"]).mode, "mcp");
  assert.equal(parseMode(["--help"]).help, true);
  assert.throws(() => parseMode([]), /ENTRYPOINT_USAGE/);
  assert.throws(() => parseMode(["api", "web"]), /ENTRYPOINT_USAGE/);
  assert.throws(() => parseMode(["solver"]), /ENTRYPOINT_USAGE/);
});

test("platform entrypoint resolves loopback-safe service commands", () => {
  const jobRoot = mkdtempSync(join(tmpdir(), "aero-entrypoint-"));
  const api = resolveServiceCommand({
    mode: "api",
    root: "/workbench",
    env: { AEROWORKBENCH_JOB_ROOT: jobRoot },
  });
  assert.deepEqual(api.argv.slice(0, 2), ["-m", "uvicorn"]);
  assert.ok(api.argv.includes("0.0.0.0"));
  assert.equal(api.extraEnv.AEROWORKBENCH_JOB_ROOT, jobRoot);

  const web = resolveServiceCommand({ mode: "web", root: "/workbench", env: {} });
  assert.ok(web.argv[0].endsWith(join("next", "dist", "bin", "next")));
  assert.deepEqual(web.argv.slice(1, 2), ["start"]);

  const mcp = resolveServiceCommand({
    mode: "mcp",
    root: "/workbench",
    env: { AERO_API_BASE_URL: "http://api:8000" },
  });
  assert.ok(mcp.argv[0].endsWith(join("mcp", "engineering", "server.ts")));

  assert.throws(
    () => resolveServiceCommand({ mode: "mcp", root: "/workbench", env: {} }),
    /AERO_API_BASE_URL/,
  );
  assert.throws(
    () => resolveServiceCommand({ mode: "api", root: "/workbench", env: { AERO_API_PORT: "huge" } }),
    /ENTRYPOINT_USAGE/,
  );
});
