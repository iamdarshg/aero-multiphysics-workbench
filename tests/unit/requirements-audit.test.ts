import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { readFileSync } from "node:fs";
import { summarizeAudit, validateAuditDocument } from "../../scripts/audit-requirements.mjs";

const audit = JSON.parse(readFileSync(new URL("../../docs/requirements-audit.json", import.meta.url), "utf8"));

describe("requirements audit contract", () => {
  it("contains every section and stopping condition exactly once", () => {
    assert.deepEqual(validateAuditDocument(audit), []);
    assert.equal(audit.sections.length, 86);
    assert.equal(audit.stoppingConditions.length, 44);
  });

  it("rejects a duplicate or missing requirement id", () => {
    const duplicate = structuredClone(audit);
    duplicate.sections[1].id = duplicate.sections[0].id;
    const duplicateErrors = validateAuditDocument(duplicate);
    assert.ok(duplicateErrors.some((error: string) => error.includes("duplicate id")));
    assert.ok(duplicateErrors.some((error: string) => error.includes("missing section:1")));
  });

  it("rejects an entry with empty evidence", () => {
    const missingEvidence = structuredClone(audit);
    missingEvidence.stoppingConditions[0].evidence = [];
    const errors = validateAuditDocument(missingEvidence);
    assert.ok(errors.some((error: string) => error.includes("stopping:1 must contain non-empty evidence")));
  });

  it("keeps the final gate closed while mandatory work is incomplete", () => {
    const summary = summarizeAudit(audit);
    assert.equal(summary.total, 130);
    assert.equal(summary.mandatoryComplete, false);
    assert.ok(summary.counts.PARTIAL + summary.counts.FAIL + summary.counts.BLOCKED > 0);
  });
});
