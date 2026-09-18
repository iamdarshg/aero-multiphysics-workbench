import assert from "node:assert/strict";
import test from "node:test";

import {
  BUDGETS,
  EXIT,
  STEP_ORDER,
  TIERS,
  makeStep,
  parseArgs,
  selectSteps,
} from "../../scripts/test/tier.mjs";

test("parseArgs accepts a tier, budget override and change set", () => {
  const opts = parseArgs(["fast", "--budget-seconds", "90", "--json"]);
  assert.equal(opts.tier, "fast");
  assert.equal(opts.budgetSeconds, 90);
  assert.equal(opts.json, true);

  const focused = parseArgs(["focused", "--paths", "apps/web/x.ts, packages/schema/y.ts"]);
  assert.deepEqual(focused.paths, ["apps/web/x.ts", "packages/schema/y.ts"]);
});

test("parseArgs rejects unknown flags and exposes usage errors", () => {
  assert.throws(() => parseArgs(["--nope"]), /unknown argument/);
});

test("every declared tier maps to real, ordered steps", () => {
  for (const [tier, steps] of Object.entries(TIERS)) {
    assert.ok(steps.length > 0, `${tier} has no steps`);
    for (const name of steps) {
      assert.ok(STEP_ORDER.includes(name), `${tier} references unknown step ${name}`);
      const step = makeStep(name);
      assert.ok(step.timeoutSeconds > 0, `${name} has no timeout`);
    }
    assert.ok(BUDGETS[tier] > 0, `${tier} has no budget`);
  }
});

test("fast tier stays inside its two minute budget and bounds each step", () => {
  const steps = TIERS.fast.map(makeStep);
  assert.ok(BUDGETS.fast <= 120, "fast budget must be <=120s");
  assert.ok(steps.every((step) => step.timeoutSeconds > 0));
  assert.ok(
    steps.reduce((total, step) => total + step.timeoutSeconds, 0) >= BUDGETS.fast,
    "fast steps should be individually bounded",
  );
});

test("python steps fail closed with --no-sync and only arm the watchdog when asked", () => {
  const core = makeStep("py-core");
  assert.equal(core.command, "uv");
  assert.ok(core.args.includes("--no-sync"));
  assert.ok(core.args.includes("-p") && core.args.includes("pytest_hang_guard"));
  assert.equal(core.env.AERO_TEST_TIMEOUT_SECONDS, "90");

  const all = makeStep("py-all");
  assert.ok(all.args.includes("-p"));
  assert.equal(all.env.AERO_TEST_TIMEOUT_SECONDS, "600");
});

test("focused selection routes changed paths to the owning tiers", () => {
  assert.deepEqual(selectSteps(["apps/web/src/app.tsx"]), ["js-web"]);
  assert.deepEqual(selectSteps(["tests/core/test_api.py"]), ["py-core"]);
  assert.deepEqual(selectSteps(["tests/integration/test_sqlite_roundtrip.py"]), ["py-integration"]);
  assert.deepEqual(selectSteps(["services/api/pyproject.toml"]), [
    "py-core",
    "py-integration",
    "py-fast-physics",
  ]);
  assert.deepEqual(selectSteps(["packages/solver-contracts/src/index.ts"]), ["js-platform-fast"]);
});

test("focused selection escalates heavy physics files to explicit tiers", () => {
  assert.deepEqual(selectSteps(["tests/physics/test_edf_80mm_three_stage.py"]), ["py-science-edf"]);
  assert.deepEqual(selectSteps(["tests/physics/test_native_execution.py"]), [
    "py-native-execution",
    "py-native-smoke",
  ]);
  assert.deepEqual(selectSteps(["tests/physics/test_participant_lifecycle.py"]), ["py-fast-physics"]);
});

test("focused selection routes audit changes to the audit contract step", () => {
  assert.deepEqual(selectSteps(["tests/unit/requirements-audit.test.ts"]), ["js-audit"]);
  assert.deepEqual(selectSteps(["scripts/audit-requirements.mjs"]), ["js-audit"]);
  assert.deepEqual(selectSteps(["docs/requirements-audit.json"]), ["js-audit"]);
});

test("unknown paths select nothing so the caller can fall back to fast", () => {
  assert.deepEqual(selectSteps(["docs/testing-tiers.md"]), []);
});

test("fast tier excludes release-only byte-pinned and process-spawning contracts", () => {
  const fast = makeStep("js-unit-fast");
  assert.ok(!fast.args.some((arg) => arg.includes("requirements-audit")), "audit gate must stay out of the fast loop");
  assert.ok(!fast.args.some((arg) => arg.includes("stack-live")), "stack-live must stay out of the fast loop");
  assert.ok(makeStep("js-unit-all").args.some((arg) => arg.includes("requirements-audit")));
});

test("legacy full test gate is preserved in the all tier", () => {
  assert.ok(TIERS.all.includes("py-all"));
  assert.ok(TIERS.all.includes("js-unit-all"));
  assert.ok(TIERS.all.includes("js-platform-all"));
  assert.equal(EXIT.BUDGET, 3);
});
