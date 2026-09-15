import assert from "node:assert/strict";
import test from "node:test";

import {
  assertOwnedJobStatus,
  assertSafeToken,
  isSafeToken,
  policyFromEnvironment,
  rejectCostEscalation,
  rejectRemoteEscalation,
  resolveApiBaseUrl,
} from "../../mcp/engineering/policy.ts";

const withEnv = (values: Record<string, string | undefined>, run: () => void): void => {
  const saved = new Map<string, string | undefined>();
  for (const [key, value] of Object.entries(values)) {
    saved.set(key, process.env[key]);
    if (value === undefined) delete process.env[key];
    else process.env[key] = value;
  }
  try {
    run();
  } finally {
    for (const [key, value] of saved) {
      if (value === undefined) delete process.env[key];
      else process.env[key] = value;
    }
  }
};

test("safe tokens accept bounded identifiers and reject paths/commands/traversal", () => {
  for (const good of ["fan-a", "job_01", "rev:7", "a", "X".repeat(128)]) {
    assert.equal(isSafeToken(good), true, good);
    assert.equal(assertSafeToken(good, "jobId"), good);
  }
  for (const bad of [
    "",
    "../escape",
    "a/b",
    "a\\b",
    "/absolute",
    "C:\\win",
    "job; rm -rf",
    "x|y",
    "a&b",
    "$HOME",
    "`id`",
    "a\nb",
    "a..b",
    " spaced",
    "x".repeat(129),
    42,
    null,
    undefined,
  ]) {
    assert.equal(isSafeToken(bad), false, JSON.stringify(bad));
    assert.throws(() => assertSafeToken(bad, "jobId"), /UNSAFE_/);
  }
});

test("remote and cost escalation are rejected even when policy allows remote", () => {
  withEnv({ AERO_ALLOW_REMOTE_COMPUTE: "1", AERO_REMOTE_COST_CEILING_USD: "5" }, () => {
    const policy = policyFromEnvironment();
    assert.equal(policy.remoteCompute, true);
    // The MCP layer must never forward remote execution or a cost ceiling itself.
    assert.throws(() => rejectRemoteEscalation({ remote: true }), /REMOTE_COMPUTE_NOT_AUTHORIZED/);
    assert.throws(() => rejectRemoteEscalation({ remote: false }), /REMOTE_COMPUTE_NOT_AUTHORIZED/);
    assert.throws(() => rejectCostEscalation({ costCeilingUsd: 1 }), /REMOTE_COST_BUDGET_EXCEEDED/);
    assert.throws(() => rejectCostEscalation({ costCeilingUsd: 0 }), /REMOTE_COST_BUDGET_EXCEEDED/);
    rejectRemoteEscalation({});
    rejectCostEscalation({});
  });
});

test("ownership check fails closed on mismatch, missing, or empty owner", () => {
  assert.throws(() => assertOwnedJobStatus({ owner_id: "operator-b" }, "operator-a"), /JOB_NOT_OWNED/);
  assert.throws(() => assertOwnedJobStatus({ owner_id: null }, "operator-a"), /JOB_NOT_OWNED/);
  assert.throws(() => assertOwnedJobStatus({}, "operator-a"), /JOB_NOT_OWNED/);
  assert.throws(() => assertOwnedJobStatus({ owner_id: "" }, "operator-a"), /JOB_NOT_OWNED/);
  assertOwnedJobStatus({ owner_id: "operator-a" }, "operator-a");
});

test("API base URL resolution rejects non-local and non-http targets", () => {
  withEnv({ AERO_API_BASE_URL: undefined }, () => {
    assert.equal(resolveApiBaseUrl(), "http://localhost:8000");
  });
  withEnv({ AERO_API_BASE_URL: "http://127.0.0.1:9000/" }, () => {
    assert.equal(resolveApiBaseUrl(), "http://127.0.0.1:9000");
  });
  for (const bad of ["https://example.com", "http://example.com", "ftp://localhost/x", "not-a-url"]) {
    withEnv({ AERO_API_BASE_URL: bad }, () => {
      assert.throws(() => resolveApiBaseUrl(), /INVALID_API_BASE_URL/, bad);
    });
  }
  withEnv({ AERO_API_BASE_URL: "" }, () => {
    assert.equal(resolveApiBaseUrl(), "http://localhost:8000");
  });
});

test("policy startup fails closed on an invalid remote cost ceiling", () => {
  withEnv({ AERO_REMOTE_COST_CEILING_USD: "-1" }, () => {
    assert.throws(() => policyFromEnvironment(), /INVALID_REMOTE_COST_CEILING/);
  });
  withEnv({ AERO_REMOTE_COST_CEILING_USD: "abc" }, () => {
    assert.throws(() => policyFromEnvironment(), /INVALID_REMOTE_COST_CEILING/);
  });
});
