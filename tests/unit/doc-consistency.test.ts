import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

import {
  checkDocumentMarkerConsistency,
  runDocConsistencyChecks,
} from "../../scripts/check-docs.mjs";

const repoRoot = fileURLToPath(new URL("../..", import.meta.url));

describe("documentation and audit anti-staleness guard", () => {
  it("passes every doc, audit and code consistency check on the real repository", () => {
    assert.deepEqual(runDocConsistencyChecks({ repoRoot }), []);
  });

  it("fails when a documented capability marker contradicts the machine-readable facts", () => {
    const errors = checkDocumentMarkerConsistency(
      { schedulingMode: "resource-aware-concurrent" },
      { "README.md": "<!-- capability: schedulingMode=single-worker -->" },
    );
    assert.ok(errors.some((error: string) => error.includes("disagrees with capabilityFacts")));
  });

  it("fails when a required capability fact is not rendered anywhere", () => {
    const errors = checkDocumentMarkerConsistency(
      { schedulingMode: "resource-aware-concurrent", resultPublication: "evidence-gated-publish-active" },
      { "README.md": "<!-- capability: schedulingMode=resource-aware-concurrent -->" },
    );
    assert.ok(errors.some((error: string) => error.includes("no owned document declares capability marker resultPublication")));
  });

  it("fails when an owned document reintroduces a known stale phrase", () => {
    const errors = checkDocumentMarkerConsistency(
      {},
      { "docs/architecture.md": "Native solver jobs run one at a time locally" },
    );
    assert.ok(errors.some((error: string) => error.includes("contains stale phrase")));
  });

  it("runs as a bounded CLI check that exits 0 on the real repository", () => {
    const script = fileURLToPath(new URL("../../scripts/check-docs.mjs", import.meta.url));
    const result = spawnSync(process.execPath, [script], {
      cwd: repoRoot,
      encoding: "utf8",
      timeout: 60_000,
    });
    assert.equal(result.status, 0, `${result.stdout}${result.stderr}`);
    assert.match(String(result.stdout), /doc-consistency: OK/);
  });
});
