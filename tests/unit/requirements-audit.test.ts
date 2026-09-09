import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { summarizeAudit, validateAuditDocument } from "../../scripts/audit-requirements.mjs";

const audit = JSON.parse(readFileSync(new URL("../../docs/requirements-audit.json", import.meta.url), "utf8"));
const repoRoot = fileURLToPath(new URL("../..", import.meta.url));

describe("requirements audit contract", () => {
  it("contains every section and stopping condition exactly once", () => {
    assert.deepEqual(validateAuditDocument(audit, { repoRoot }), []);
    assert.equal(audit.sections.length, 86);
    assert.equal(audit.stoppingConditions.length, 44);
  });

  it("rejects a duplicate or missing requirement id", () => {
    const duplicate = structuredClone(audit);
    duplicate.sections[1].id = duplicate.sections[0].id;
    const duplicateErrors = validateAuditDocument(duplicate, { repoRoot });
    assert.ok(duplicateErrors.some((error: string) => error.includes("duplicate id")));
    assert.ok(duplicateErrors.some((error: string) => error.includes("missing section:1")));
  });

  it("rejects an entry with empty evidence", () => {
    const missingEvidence = structuredClone(audit);
    missingEvidence.stoppingConditions[0].evidence = [];
    const errors = validateAuditDocument(missingEvidence, { repoRoot });
    assert.ok(errors.some((error: string) => error.includes("stopping:1 must contain non-empty evidence")));
  });

  it("keeps the final gate closed while mandatory work is incomplete", () => {
    const summary = summarizeAudit(audit, { repoRoot });
    assert.equal(summary.total, 130);
    assert.equal(summary.mandatoryComplete, false);
    assert.ok(summary.counts.PARTIAL + summary.counts.FAIL + summary.counts.BLOCKED > 0);
  });

  it("rejects nonexistent and outside-repository evidence paths", () => {
    const mutated = structuredClone(audit);
    mutated.sections[0].evidence[0].path = "docs/does-not-exist.json";
    mutated.sections[1].evidence[0].path = "../../outside.json";
    const errors = validateAuditDocument(mutated, { repoRoot });
    assert.ok(errors.some((error: string) => error.includes("does not exist")));
    assert.ok(errors.some((error: string) => error.includes("escapes the repository")));
  });

  it("rejects a bogus evidence kind and a title altered from the brief", () => {
    const mutated = structuredClone(audit);
    mutated.sections[0].evidence[0].kind = "telemetry";
    mutated.sections[1].title = "invented title";
    const errors = validateAuditDocument(mutated, { repoRoot });
    assert.ok(errors.some((error: string) => error.includes("invalid kind")));
    assert.ok(errors.some((error: string) => error.includes("title does not match")));
  });

  it("rejects future and non-ISO verification timestamps", () => {
    const future = structuredClone(audit);
    future.sections[0].lastVerifiedAt = "2999-01-01T00:00:00.000Z";
    const futureErrors = validateAuditDocument(future, { repoRoot });
    assert.ok(futureErrors.some((error: string) => error.includes("cannot be in the future")));

    const malformed = structuredClone(audit);
    malformed.sections[0].lastVerifiedAt = "2026/09/09 12:00:00";
    const malformedErrors = validateAuditDocument(malformed, { repoRoot });
    assert.ok(malformedErrors.some((error: string) => error.includes("exact UTC ISO-8601")));
  });

  it("rejects a fabricated all-PASS document", () => {
    const fabricated = structuredClone(audit);
    for (const entry of [...fabricated.sections, ...fabricated.stoppingConditions]) {
      entry.status = "PASS";
      entry.lastVerifiedAt = "2020-01-01T00:00:00.000Z";
    }
    const summary = summarizeAudit(fabricated, { repoRoot });
    assert.equal(summary.mandatoryComplete, false);
    assert.ok(summary.errors.some((error: string) => error.includes("receipt observation status does not match PASS")));
    assert.ok(summary.errors.some((error: string) => error.includes("matching trusted receipt observation")));
  });

  it("cannot promote mutable evidence flags or a fabricated command to PASS", () => {
    const fabricated = structuredClone(audit);
    const entry = fabricated.sections[0];
    entry.status = "PASS";
    entry.lastVerifiedAt = "2020-01-01T00:00:00.000Z";
    entry.evidence[0].verified = true;
    entry.evidence[0].supportsPass = true;
    entry.evidence[0].command = "echo definitely-complete";
    entry.evidence[0].exitCode = 0;
    const errors = validateAuditDocument(fabricated, { repoRoot });
    assert.ok(errors.some((error: string) => error.includes("must not contain mutable verified/supportsPass assertions")));
    assert.ok(errors.some((error: string) => error.includes("command and exitCode must be derived from the receipt")));
    assert.ok(errors.some((error: string) => error.includes("receipt observation status does not match PASS")));
  });

  it("binds every evidence reference to its own receipt observation", () => {
    const mutated = structuredClone(audit);
    mutated.sections[0].evidence[0].observationId = "section:1";
    const errors = validateAuditDocument(mutated, { repoRoot });
    assert.ok(errors.some((error: string) => error.includes("observationId must equal section:0")));
  });

  it("rejects a changed authoritative brief digest", () => {
    const mutated = structuredClone(audit);
    mutated.source.sha256 = "0".repeat(64);
    const errors = validateAuditDocument(mutated, { repoRoot });
    assert.ok(errors.some((error: string) => error.includes("source SHA-256")));
  });
});
