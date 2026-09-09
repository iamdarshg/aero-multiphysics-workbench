import { createHash } from "node:crypto";
import { readFileSync, existsSync, realpathSync } from "node:fs";
import { dirname, isAbsolute, relative, resolve, posix } from "node:path";
import { fileURLToPath } from "node:url";
import { execFileSync } from "node:child_process";

export const REQUIRED_SECTION_IDS = Array.from({ length: 86 }, (_, id) => `section:${id}`);
export const REQUIRED_STOPPING_IDS = Array.from({ length: 44 }, (_, index) => `stopping:${index + 1}`);
export const ALLOWED_STATUSES = new Set(["PASS", "PARTIAL", "FAIL", "BLOCKED"]);
export const ALLOWED_EVIDENCE_KINDS = new Set(["file", "test", "command", "artifact", "receipt"]);
export const SOURCE_BINDING = Object.freeze({
  briefId: "authoritative-user-brief-v1",
  sha256: "53fd123b59eb65cfe72e3967c7d07e5d3fe169b18be8f0b61a8a061c8c0f9d9a",
  lineCount: 2895
});
const SECTION_TITLES = Object.freeze(["PROJECT PURPOSE","CORE PHILOSOPHY","USE THE FOLLOWING MAIN TECHNOLOGY ARCHITECTURE","FIELD COUPLING","COUPLING MUST BE STRONG BY DEFAULT","GLOBAL PHYSICAL CONVERGENCE MANAGER","RESONANCE MUST BE INSIDE THE PHYSICS LOOP","EDF SYSTEM — FULL FIRST IMPLEMENTATION","CFD BACKEND","STRUCTURAL BACKEND","THERMAL","ELECTRIC MOTOR — THREE FIDELITY LEVELS","ESC MODEL","BATTERY MODEL","AIRCRAFT PURPOSE","OPERATING ENVELOPE","WHOLE-AIRCRAFT COUPLING","GEOMETRY SYSTEM","SEMANTIC GEOMETRY","PARAMETRIC GEOMETRY","MESHING","CACHE EVERYTHING SAFE TO CACHE","WARM STARTS","MESH MORPHING AND LOCAL REMESH","DESIGN VARIANTS","COMPLETE PROVENANCE","USER INTERFACE","MAIN LAYOUT","VISUALIZATION","LIVE SOLVER VIEW","AI ENGINEERING INTERFACE","MCP CAPABILITIES","CHATGPT MUST BE ABLE TO SUPERVISE LIVE SIMULATIONS","USER-ONLY CLOUD COMPUTE SWITCH","CLOUD COMPUTE","USER COST LIMITS","CLOUD CHECKPOINTING","LOCAL MODE","GAS TURBINE SYSTEM","COMPRESSOR DESIGN","TURBINE DESIGN","COMBUSTOR","THERMOACOUSTICS","COMPLETE ENGINE COUPLING","FREECAD INTEROPERABILITY","EXTENSIBILITY","MATERIAL DATABASE","COMPOSITES","OPTIMIZATION","ADAPTIVE FIDELITY","PHYSICS BENCHMARKING","MESH INDEPENDENCE","TIME-STEP INDEPENDENCE","POWER/ENERGY BALANCE DASHBOARD","RESULT QUALITY SCORE","ERROR RECOVERY","APPLICATION INFRASTRUCTURE","DATABASE","STORAGE FORMATS","API","CI/CD","CONTAINERS","DEPLOYMENT","COMPLETE EDF DEMO","COMPLETE AIRCRAFT DEMO","COMPLETE GAS-TURBINE DEMO","UI POLISH","EXPLAINABILITY","ENGINEERING AI UX","NO PREMATURE STOPPING","PARALLEL EXECUTION","USE AUTONOMOUS CODE REVIEW","TEST EVERYTHING BEFORE DECLARING DONE","DO NOT FAKE RESULTS","DON'T SUBSTITUTE PLACEHOLDERS FOR REQUIRED FEATURES","EXTERNAL DOCUMENTATION","SOURCE CONTROL","AUTOMATED ENVIRONMENT BOOTSTRAP","ONE-COMMAND DEVELOPMENT START","ONE-COMMAND DEMOS","SOLVER CAPABILITY DETECTOR","DOCUMENTATION","FINAL COMPLETION TEST","STOPPING CONDITION","FINAL RESPONSE","BEGIN NOW"]);
const SECTION_LINES = Object.freeze([93,132,234,282,322,382,500,584,621,658,684,711,790,813,873,915,946,975,1013,1047,1073,1106,1132,1156,1190,1231,1295,1313,1334,1403,1430,1453,1526,1560,1589,1615,1632,1649,1668,1698,1735,1758,1788,1807,1835,1860,1889,1913,1931,1952,1991,2050,2068,2082,2113,2130,2165,2236,2260,2277,2291,2310,2332,2351,2397,2420,2448,2473,2494,2512,2533,2581,2599,2618,2632,2652,2664,2680,2696,2708,2722,2742,2770,2792,2847,2874]);
const STOPPING_TITLES = Object.freeze(["the repository exists and is clean","the application runs","the browser UI works","CAD works","geometry import works","FreeCAD pathway works","OpenMDAO coupling works","preCICE coupling works","real CFD works","real structural analysis works","thermal coupling works","EDF works","motor model works","6S PyBaMM works","high-fidelity EM works","ROSS works","modal/resonance detection works","dynamic escalation works","full-aircraft workflow works","operating-envelope workflow works","compressor workflow works","combustor workflow works","turbine workflow works","gas-turbine coupling works","visualization works","variants work","provenance works","caching works","warm starts work","mesh morphing/local remesh works","MCP works","AI can supervise simulations","GCP compute works","remote-compute user-only switch works","cloud cost controls work","checkpoint/restart works","EDF demo passes","aircraft demo passes","gas-turbine demo passes","physics benchmarks pass","documentation is complete","automated tests pass","deployment is live and usable","the final requirement audit contains no incomplete mandatory requirement"]);
const STOPPING_LINES = Object.freeze([2796,2797,2798,2799,2800,2801,2802,2803,2804,2805,2806,2807,2808,2809,2810,2811,2812,2813,2814,2815,2816,2817,2818,2819,2820,2821,2822,2823,2824,2825,2826,2827,2828,2829,2830,2831,2832,2833,2834,2835,2836,2837,2838,2839]);
const UTC_ISO = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{3})?Z$/;
const SHA256 = /^[a-f0-9]{64}$/i;
const GIT_SHA1 = /^[a-f0-9]{40}$/i;
const TRUSTED_RECEIPT_COMMANDS = new Set(["pnpm test && pnpm typecheck && pnpm lint"]);
const STATUS_SEMANTICS = "PASS requires linked, existing, digest-checked, verified evidence; PARTIAL means a verified subset exists; FAIL means an attempted check failed; BLOCKED means required capability or prerequisite is unavailable.";

export function expectedRequirement(id) {
  if (id.startsWith("section:")) {
    const number = Number(id.slice("section:".length));
    if (Number.isInteger(number) && number >= 0 && number < SECTION_TITLES.length) {
      return { title: SECTION_TITLES[number], section: number, lineStart: SECTION_LINES[number], lineEnd: number + 1 < SECTION_LINES.length ? SECTION_LINES[number + 1] - 1 : 2895 };
    }
  }
  if (id.startsWith("stopping:")) {
    const number = Number(id.slice("stopping:".length));
    if (Number.isInteger(number) && number >= 1 && number <= STOPPING_TITLES.length) {
      return { title: STOPPING_TITLES[number - 1], section: 83, lineStart: STOPPING_LINES[number - 1], lineEnd: STOPPING_LINES[number - 1] };
    }
  }
  return null;
}

function expectedIds(prefix) {
  return prefix === "section" ? REQUIRED_SECTION_IDS : REQUIRED_STOPPING_IDS;
}

function sha256File(filePath) {
  return createHash("sha256").update(readFileSync(filePath)).digest("hex");
}

function normalizedRepoPath(rawPath, repoRoot, label, errors) {
  if (typeof rawPath !== "string" || rawPath.trim() === "" || rawPath !== rawPath.trim() || rawPath.includes("\\") || rawPath.includes("\0") || rawPath.startsWith("/") || /^[A-Za-z]:[\\/]/.test(rawPath)) {
    errors.push(`${label} path must be a trimmed repo-relative POSIX path`);
    return null;
  }
  const normalized = posix.normalize(rawPath);
  if (normalized === "." || normalized.startsWith("../") || normalized === ".." || normalized.includes("/../")) {
    errors.push(`${label} path escapes the repository`);
    return null;
  }
  const absolute = resolve(repoRoot, ...normalized.split("/"));
  const relativePath = relative(repoRoot, absolute).replaceAll("\\", "/");
  if (relativePath === ".." || relativePath.startsWith("../") || isAbsolute(relativePath) || relativePath !== normalized) {
    errors.push(`${label} path is not normalized or is outside the repository`);
    return null;
  }
  if (!existsSync(absolute)) errors.push(`${label} evidence path does not exist: ${normalized}`);
  else {
    const realRepoRoot = realpathSync(repoRoot);
    const realEvidencePath = realpathSync(absolute);
    const realRelativePath = relative(realRepoRoot, realEvidencePath).replaceAll("\\", "/");
    if (realRelativePath === ".." || realRelativePath.startsWith("../") || isAbsolute(realRelativePath)) {
      errors.push(`${label} real path escapes the repository`);
      return null;
    }
  }
  return { normalized, absolute };
}

function validateTimestamp(value, label, errors, required = false) {
  if (value === null && !required) return;
  if (typeof value !== "string" || !UTC_ISO.test(value) || Number.isNaN(Date.parse(value))) {
    errors.push(`${label} must be an exact UTC ISO-8601 timestamp`);
    return;
  }
  if (Date.parse(value) > Date.now() + 60_000) errors.push(`${label} cannot be in the future`);
}

function sha256Text(value) {
  return createHash("sha256").update(value).digest("hex");
}

function readReceipt(pathInfo, repoRoot, label, errors, receiptCache) {
  if (receiptCache.has(pathInfo.absolute)) return receiptCache.get(pathInfo.absolute);
  let receipt;
  try {
    receipt = JSON.parse(readFileSync(pathInfo.absolute, "utf8"));
  } catch (error) {
    errors.push(`${label} is not valid receipt JSON: ${error instanceof Error ? error.message : String(error)}`);
    receiptCache.set(pathInfo.absolute, null);
    return null;
  }
  if (receipt.schemaVersion !== 2) errors.push(`${label} receipt schemaVersion must be 2`);
  if (typeof receipt.receiptId !== "string" || receipt.receiptId.trim() === "") errors.push(`${label} receiptId is missing`);
  validateTimestamp(receipt.generatedAt, `${label} generatedAt`, errors, true);
  if (!TRUSTED_RECEIPT_COMMANDS.has(receipt.command)) errors.push(`${label} receipt command is not trusted`);
  if (!Number.isInteger(receipt.exitCode)) errors.push(`${label} receipt exitCode must be an integer`);
  if (typeof receipt.stdout !== "string" || !SHA256.test(receipt.stdoutSha256 ?? "") || sha256Text(receipt.stdout ?? "") !== String(receipt.stdoutSha256).toLowerCase()) {
    errors.push(`${label} receipt stdout digest does not match`);
  }
  if (typeof receipt.stderr !== "string" || !SHA256.test(receipt.stderrSha256 ?? "") || sha256Text(receipt.stderr ?? "") !== String(receipt.stderrSha256).toLowerCase()) {
    errors.push(`${label} receipt stderr digest does not match`);
  }
  if (!GIT_SHA1.test(receipt.repositoryCommit ?? "") || !GIT_SHA1.test(receipt.sourceTreeSha256 ?? "")) {
    errors.push(`${label} receipt requires full repositoryCommit and sourceTreeSha256 git object ids`);
  } else {
    try {
      const commit = execFileSync("git", ["rev-parse", `${receipt.repositoryCommit}^{commit}`], { cwd: repoRoot, encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] }).trim();
      const tree = execFileSync("git", ["rev-parse", `${receipt.repositoryCommit}^{tree}`], { cwd: repoRoot, encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] }).trim();
      execFileSync("git", ["merge-base", "--is-ancestor", commit, "HEAD"], { cwd: repoRoot, stdio: "ignore" });
      if (commit.toLowerCase() !== receipt.repositoryCommit.toLowerCase()) errors.push(`${label} repositoryCommit is not canonical`);
      if (tree.toLowerCase() !== receipt.sourceTreeSha256.toLowerCase()) errors.push(`${label} source tree does not match repositoryCommit`);
    } catch {
      errors.push(`${label} repositoryCommit is unavailable or not an ancestor of HEAD`);
    }
  }
  if (!Array.isArray(receipt.observations)) errors.push(`${label} receipt observations must be an array`);
  receiptCache.set(pathInfo.absolute, receipt);
  return receipt;
}

function validateEvidence(ref, id, status, repoRoot, errors, receiptCache) {
  const label = `${id} evidence`;
  if (!ref || typeof ref !== "object") {
    errors.push(`${label} must be an object`);
    return false;
  }
  if (!ALLOWED_EVIDENCE_KINDS.has(ref.kind)) errors.push(`${label} has invalid kind ${String(ref.kind)}`);
  const pathInfo = normalizedRepoPath(ref.path, repoRoot, label, errors);
  if (!pathInfo) return false;
  if (typeof ref.detail !== "string" || ref.detail.trim() === "") errors.push(`${label} detail must be non-empty`);
  if (typeof ref.sha256 !== "string" || !SHA256.test(ref.sha256)) {
    errors.push(`${label} requires a SHA-256 digest`);
  } else if (existsSync(pathInfo.absolute) && sha256File(pathInfo.absolute).toLowerCase() !== ref.sha256.toLowerCase()) {
    errors.push(`${label} SHA-256 does not match the referenced file`);
  }
  if (ref.kind === "command" || ref.kind === "test") {
    if (typeof ref.command !== "string" || ref.command.trim() === "") errors.push(`${label} requires an immutable command receipt`);
    if (!Number.isInteger(ref.exitCode)) errors.push(`${label} requires an integer exitCode`);
  }
  if ("verified" in ref || "supportsPass" in ref) errors.push(`${label} must not contain mutable verified/supportsPass assertions`);
  if (ref.kind !== "receipt") return false;
  if (typeof ref.receiptId !== "string" || ref.receiptId.trim() === "") errors.push(`${label} requires receiptId`);
  if (!GIT_SHA1.test(ref.receiptCommit ?? "")) {
    errors.push(`${label} requires a full receiptCommit git object id`);
  } else {
    const commitCacheKey = `commit:${ref.receiptCommit}:${pathInfo.normalized}:${ref.sha256}`;
    if (!receiptCache.has(commitCacheKey)) {
      let commitError = null;
      try {
        const commit = execFileSync("git", ["rev-parse", `${ref.receiptCommit}^{commit}`], { cwd: repoRoot, encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] }).trim();
        execFileSync("git", ["merge-base", "--is-ancestor", commit, "HEAD"], { cwd: repoRoot, stdio: "ignore" });
        const committedReceipt = execFileSync("git", ["show", `${commit}:${pathInfo.normalized}`], { cwd: repoRoot, stdio: ["ignore", "pipe", "ignore"] });
        const committedDigest = createHash("sha256").update(committedReceipt).digest("hex");
        if (commit.toLowerCase() !== ref.receiptCommit.toLowerCase()) commitError = "receiptCommit is not canonical";
        else if (committedDigest !== ref.sha256.toLowerCase()) commitError = "receipt digest does not match the committed receipt";
      } catch {
        commitError = "receiptCommit is unavailable, not an ancestor, or does not contain the receipt";
      }
      receiptCache.set(commitCacheKey, commitError);
    }
    const commitError = receiptCache.get(commitCacheKey);
    if (commitError) errors.push(`${label} ${commitError}`);
  }
  if (ref.observationId !== id) errors.push(`${label} observationId must equal ${id}`);
  const receipt = readReceipt(pathInfo, repoRoot, label, errors, receiptCache);
  if (!receipt) return false;
  if (ref.receiptId !== receipt.receiptId) errors.push(`${label} receiptId does not match the receipt`);
  if ("command" in ref || "exitCode" in ref) errors.push(`${label} command and exitCode must be derived from the receipt`);
  const observations = receipt.observations?.filter((observation) => observation?.id === ref.observationId) ?? [];
  if (observations.length !== 1) {
    errors.push(`${label} receipt must contain exactly one matching observation`);
    return false;
  }
  const observation = observations[0];
  if (observation.status !== status) errors.push(`${label} receipt observation status does not match ${status}`);
  if (!Array.isArray(observation.basis) || observation.basis.length === 0 || typeof observation.observation !== "string" || observation.observation.trim() === "") {
    errors.push(`${label} receipt observation requires non-empty basis and explanation`);
  }
  return observation.status === "PASS" && receipt.exitCode === 0 && TRUSTED_RECEIPT_COMMANDS.has(receipt.command);
}

function validateSource(document, errors) {
  if (!document.source || typeof document.source !== "object") {
    errors.push("source binding is required");
    return;
  }
  for (const key of ["briefId", "sha256", "lineCount", "sectionsRange", "stoppingConditionsRange"]) {
    if (!(key in document.source)) errors.push(`source.${key} is required`);
  }
  if (document.source.briefId !== SOURCE_BINDING.briefId) errors.push("source briefId does not match the canonical portable identifier");
  if (String(document.source.sha256).toLowerCase() !== SOURCE_BINDING.sha256) errors.push("source SHA-256 does not match the authoritative brief");
  if (document.source.lineCount !== SOURCE_BINDING.lineCount) errors.push("source lineCount does not match the authoritative brief");
  if (document.source.sectionsRange !== "0-85") errors.push("source sectionsRange must be 0-85");
  if (document.source.stoppingConditionsRange !== "1-44") errors.push("source stoppingConditionsRange must be 1-44");
}

function validateEntries(entries, prefix, document, repoRoot, errors) {
  if (!Array.isArray(entries)) {
    errors.push(`${prefix} must be an array`);
    return;
  }
  const expected = new Set(expectedIds(prefix));
  const seen = new Set();
  const receiptCache = new Map();
  for (const entry of entries) {
    if (!entry || typeof entry !== "object") {
      errors.push(`${prefix} contains a non-object entry`);
      continue;
    }
    const id = entry.id;
    const canonical = typeof id === "string" ? expectedRequirement(id) : null;
    if (typeof id !== "string" || !expected.has(id)) errors.push(`${prefix} contains unexpected id ${String(id)}`);
    else if (seen.has(id)) errors.push(`${prefix} contains duplicate id ${id}`);
    else seen.add(id);
    if (!canonical) {
      errors.push(`${id ?? prefix} has no canonical source mapping`);
      continue;
    }
    if (entry.title !== canonical.title) errors.push(`${id} title does not match the authoritative brief`);
    if (!ALLOWED_STATUSES.has(entry.status)) errors.push(`${id} has invalid status ${String(entry.status)}`);
    if (typeof entry.statusExplanation !== "string" || entry.statusExplanation.trim() === "") errors.push(`${id} requires a truthful statusExplanation`);
    const ref = entry.sourceRef;
    if (!ref || ref.briefId !== SOURCE_BINDING.briefId || ref.section !== canonical.section || ref.lineStart !== canonical.lineStart || ref.lineEnd !== canonical.lineEnd) errors.push(`${id} sourceRef does not match the authoritative brief span`);
    let receiptSupportsPass = false;
    if (!Array.isArray(entry.evidence) || entry.evidence.length === 0) errors.push(`${id} must contain non-empty evidence`);
    else for (const evidence of entry.evidence) receiptSupportsPass = validateEvidence(evidence, id, entry.status, repoRoot, errors, receiptCache) || receiptSupportsPass;
    if (!("lastVerifiedAt" in entry)) errors.push(`${id} lastVerifiedAt must be explicit (ISO string or null)`);
    if (entry.lastVerifiedAt !== null && entry.lastVerifiedAt !== undefined) validateTimestamp(entry.lastVerifiedAt, `${id} lastVerifiedAt`, errors);
    if (entry.status === "PASS") {
      validateTimestamp(entry.lastVerifiedAt, `${id} lastVerifiedAt`, errors, true);
      if (!receiptSupportsPass) errors.push(`${id} PASS requires a matching trusted receipt observation with a successful exit`);
    }
  }
  for (const id of expected) if (!seen.has(id)) errors.push(`${prefix} is missing ${id}`);
}

export function validateAuditDocument(document, options = {}) {
  const errors = [];
  const repoRoot = resolve(options.repoRoot ?? process.cwd());
  if (!document || typeof document !== "object") return ["document must be an object"];
  if (document.schemaVersion !== 1) errors.push("schemaVersion must be 1");
  if (document.statusSemantics !== STATUS_SEMANTICS) errors.push("statusSemantics must document PASS/PARTIAL/FAIL/BLOCKED semantics");
  validateSource(document, errors);
  validateEntries(document.sections, "section", document, repoRoot, errors);
  validateEntries(document.stoppingConditions, "stopping", document, repoRoot, errors);
  return errors;
}

export function summarizeAudit(document, options = {}) {
  const entries = [...(document?.sections ?? []), ...(document?.stoppingConditions ?? [])];
  const counts = { PASS: 0, PARTIAL: 0, FAIL: 0, BLOCKED: 0 };
  for (const entry of entries) if (entry?.status in counts) counts[entry.status] += 1;
  const errors = validateAuditDocument(document, options);
  return {
    schemaVersion: 1,
    statusSemantics: STATUS_SEMANTICS,
    total: entries.length,
    counts,
    mandatoryComplete: errors.length === 0 && counts.PARTIAL === 0 && counts.FAIL === 0 && counts.BLOCKED === 0,
    errors
  };
}

export function loadAudit(file = resolve(process.cwd(), "docs/requirements-audit.json")) {
  return JSON.parse(readFileSync(file, "utf8"));
}

function findRepoRoot(file) {
  let candidate = dirname(resolve(file));
  while (true) {
    if (existsSync(resolve(candidate, "package.json"))) return candidate;
    const parent = dirname(candidate);
    if (parent === candidate) return dirname(resolve(file));
    candidate = parent;
  }
}

if (process.argv[1] && resolve(process.argv[1]) === resolve(fileURLToPath(import.meta.url))) {
  const file = process.argv[2] ? resolve(process.argv[2]) : resolve(process.cwd(), "docs/requirements-audit.json");
  let summary;
  try {
    summary = summarizeAudit(loadAudit(file), { repoRoot: findRepoRoot(file) });
  } catch (error) {
    summary = { schemaVersion: 1, statusSemantics: STATUS_SEMANTICS, total: 0, counts: { PASS: 0, PARTIAL: 0, FAIL: 0, BLOCKED: 0 }, mandatoryComplete: false, errors: [error instanceof Error ? error.message : String(error)] };
  }
  process.stdout.write(`${JSON.stringify(summary)}\n`);
  process.exitCode = summary.mandatoryComplete ? 0 : 1;
}
