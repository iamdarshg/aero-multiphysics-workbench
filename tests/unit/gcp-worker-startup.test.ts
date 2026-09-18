import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import test from "node:test";

// Regression guard for issue #11: the GCP worker installs the Python stack
// into an explicit 3.12 venv, but every proof must use that same interpreter —
// never system `python3` (3.10 on Ubuntu 22.04).
const scriptPath = fileURLToPath(
  new URL("../../infra/gcp/solver-worker-startup.sh", import.meta.url),
);
const script = readFileSync(scriptPath, "utf8");
const lines = script.split("\n");

test("worker script pins one explicit python interpreter", () => {
  assert.match(script, /^PY=\/opt\/solvers-py312\/bin\/python$/m);
  assert.match(script, /python3\.12 -m venv \/opt\/solvers-py312/);
  assert.match(script, /"\$PY" -m pip install/);
});

test("worker script smoke-asserts 3.12 + imports before proofs", () => {
  const assertIndex = lines.findIndex((line) =>
    line.includes("assert sys.version_info[:2] >= (3, 12)"),
  );
  assert.ok(assertIndex > -1, "missing version assertion");
  assert.match(lines[assertIndex], /import openmdao, ross, pybamm, cantera/);
  const smokeIndex = lines.findIndex((line) => line.includes("PY_OK=0"));
  const firstProofIndex = lines.findIndex((line) =>
    line.includes("--- D1: openmdao paraboloid ---"),
  );
  assert.ok(smokeIndex > -1 && firstProofIndex > smokeIndex);
  // The smoke gate must wrap D1-D4 (an else + fi pair after the block).
  assert.match(script, /if \[ "\$PY_OK" = 1 \]; then[\s\S]*?--- D4:[\s\S]*?\nelse\n[\s\S]*?\nfi/);
});

test("no proof falls back to bare system python3", () => {
  const proofStart = lines.findIndex((line) => line.includes("--- B2: interpreter smoke"));
  assert.ok(proofStart > -1);
  const offenders = lines
    .slice(proofStart)
    .filter((line) => /^\s*python3\s/.test(line));
  assert.deepEqual(offenders, [], `proofs must use "$PY", found: ${offenders.join(" | ")}`);
});
