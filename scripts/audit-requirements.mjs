import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

export const REQUIRED_SECTION_IDS = Array.from({ length: 86 }, (_, id) => `section:${id}`);
export const REQUIRED_STOPPING_IDS = Array.from({ length: 44 }, (_, index) => `stopping:${index + 1}`);
export const ALLOWED_STATUSES = new Set(["PASS", "PARTIAL", "FAIL", "BLOCKED"]);

function expectedIds(prefix) {
  return prefix === "section" ? REQUIRED_SECTION_IDS : REQUIRED_STOPPING_IDS;
}

function validateEntries(entries, prefix, errors) {
  if (!Array.isArray(entries)) {
    errors.push(`${prefix} must be an array`);
    return;
  }

  const expected = new Set(expectedIds(prefix));
  const seen = new Set();
  for (const entry of entries) {
    if (!entry || typeof entry !== "object") {
      errors.push(`${prefix} contains a non-object entry`);
      continue;
    }
    const id = entry.id;
    if (typeof id !== "string" || !expected.has(id)) {
      errors.push(`${prefix} contains unexpected id ${String(id)}`);
    } else if (seen.has(id)) {
      errors.push(`${prefix} contains duplicate id ${id}`);
    } else {
      seen.add(id);
    }
    if (typeof entry.title !== "string" || entry.title.trim() === "") {
      errors.push(`${id ?? prefix} has an empty title`);
    }
    if (!ALLOWED_STATUSES.has(entry.status)) {
      errors.push(`${id ?? prefix} has invalid status ${String(entry.status)}`);
    }
    if (!Array.isArray(entry.evidence) || entry.evidence.length === 0) {
      errors.push(`${id ?? prefix} must contain non-empty evidence`);
    } else {
      for (const ref of entry.evidence) {
        if (!ref || typeof ref !== "object" || typeof ref.path !== "string" || ref.path.trim() === "" || typeof ref.detail !== "string" || ref.detail.trim() === "") {
          errors.push(`${id ?? prefix} contains an incomplete evidence reference`);
        }
      }
    }
    if (entry.status === "PASS" && (typeof entry.lastVerifiedAt !== "string" || Number.isNaN(Date.parse(entry.lastVerifiedAt)))) {
      errors.push(`${id ?? prefix} PASS entries require a valid lastVerifiedAt`);
    }
    if (entry.lastVerifiedAt !== null && typeof entry.lastVerifiedAt !== "string") {
      errors.push(`${id ?? prefix} lastVerifiedAt must be an ISO string or null`);
    }
  }
  for (const id of expected) {
    if (!seen.has(id)) errors.push(`${prefix} is missing ${id}`);
  }
}

export function validateAuditDocument(document) {
  const errors = [];
  if (!document || typeof document !== "object") return ["document must be an object"];
  if (document.schemaVersion !== 1) errors.push("schemaVersion must be 1");
  validateEntries(document.sections, "section", errors);
  validateEntries(document.stoppingConditions, "stopping", errors);
  return errors;
}

export function summarizeAudit(document) {
  const entries = [...(document.sections ?? []), ...(document.stoppingConditions ?? [])];
  const counts = { PASS: 0, PARTIAL: 0, FAIL: 0, BLOCKED: 0 };
  for (const entry of entries) if (entry?.status in counts) counts[entry.status] += 1;
  const errors = validateAuditDocument(document);
  return {
    schemaVersion: 1,
    total: entries.length,
    counts,
    mandatoryComplete: errors.length === 0 && counts.PARTIAL === 0 && counts.FAIL === 0 && counts.BLOCKED === 0,
    errors,
  };
}

export function loadAudit(file = resolve(process.cwd(), "docs/requirements-audit.json")) {
  return JSON.parse(readFileSync(file, "utf8"));
}

if (process.argv[1] && resolve(process.argv[1]) === resolve(fileURLToPath(import.meta.url))) {
  const file = process.argv[2] ? resolve(process.argv[2]) : resolve(process.cwd(), "docs/requirements-audit.json");
  let summary;
  try {
    summary = summarizeAudit(loadAudit(file));
  } catch (error) {
    summary = { schemaVersion: 1, total: 0, counts: { PASS: 0, PARTIAL: 0, FAIL: 0, BLOCKED: 0 }, mandatoryComplete: false, errors: [error instanceof Error ? error.message : String(error)] };
  }
  process.stdout.write(`${JSON.stringify(summary)}\n`);
  process.exitCode = summary.mandatoryComplete ? 0 : 1;
}
