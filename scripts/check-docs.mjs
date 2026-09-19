// Anti-staleness guard for documentation and the requirements audit.
//
// This check is deliberately explicit and deterministic: it verifies versioned
// capability facts against the code that implements them, verifies the audit's
// evidence digests, and rejects known stale prose in the owned docs. It does
// NOT attempt natural-language theorem proving. Native solvers, network, cloud
// and Docker are never required, so it is safe for the fast/reporting CI path.
import { existsSync, readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { loadAudit, validateAuditDocument } from "./audit-requirements.mjs";

export const OWNED_DOCS = [
  "README.md",
  "docs/architecture.md",
  "docs/platform-operations.md",
  "AGENTS.md",
];

const MARKER = /<!--\s*capability:\s*([A-Za-z0-9_]+)\s*=\s*([^\s>]+)\s*-->/g;

// High-value capability facts whose documented wording must match code.
export const REQUIRED_FACT_KEYS = [
  "authoritativeExecutionOwner",
  "schedulingMode",
  "resultPublication",
  "cachePersistence",
  "mcpServer",
  "remoteCompute",
  "containers",
  "nativeSolvers",
  "storage",
];

// Phrases that were true before GEN/PERF/product work landed and must not
// reappear in the owned docs while the corresponding capability is active.
const STALE_PHRASES = {
  "README.md": [
    "single-worker native job",
    "Local native execution is single-worker",
  ],
  "docs/architecture.md": ["Native solver jobs run one at a time"],
  "docs/platform-operations.md": [
    "Result publication is currently disabled",
    "only cancels queued reservations",
    "returns skeleton metadata",
    "governed single-worker native job lifecycle",
  ],
  "AGENTS.md": ["single-worker execution"],
};

const MCP_TOOLS = [
  "capabilities.inspect",
  "design.inspect",
  "job.inspect",
  "result.inspect",
  "design.variant.create",
  "analysis.submit",
  "job.cancel",
];

const defaultRoot = () => resolve(dirname(fileURLToPath(import.meta.url)), "..");

const readDoc = (repoRoot, relative) => {
  const absolute = resolve(repoRoot, relative);
  if (!existsSync(absolute)) return null;
  return readFileSync(absolute, "utf8");
};

const parseMarkers = (text) => {
  const found = new Map();
  for (const match of text.matchAll(MARKER)) found.set(match[1], match[2]);
  return found;
};

const flattenFacts = (facts) => {
  const flat = new Map();
  for (const [key, value] of Object.entries(facts ?? {})) {
    if (key === "schemaVersion" || key === "updatedAt") continue;
    if (typeof value === "string") flat.set(key, value);
  }
  return flat;
};

const checkCodeFacts = (repoRoot, facts, errors) => {
  const read = (relative) => {
    const text = readDoc(repoRoot, relative);
    if (text === null) errors.push(`code marker file is missing: ${relative}`);
    return text ?? "";
  };

  if (facts.get("schedulingMode") === "resource-aware-concurrent") {
    const lifecycle = read("solvers/participants/lifecycle.py");
    if (!/class ResourceScheduler/.test(lifecycle)) {
      errors.push("schedulingMode=resource-aware-concurrent but ResourceScheduler is absent from lifecycle.py");
    }
    const concurrency = [...lifecycle.matchAll(/max_concurrency=(\d+)/g)].map((match) => Number(match[1]));
    if (!concurrency.some((value) => value > 1)) {
      errors.push("schedulingMode fact claims concurrency but no solver policy allows more than one active job");
    }
  }

  if (facts.get("resultPublication") === "evidence-gated-publish-active") {
    const lifecycle = read("solvers/participants/lifecycle.py");
    if (!lifecycle.includes("publish_result(") || !lifecycle.includes("def _publish")) {
      errors.push("resultPublication fact claims active publication but the evidence-gated publish path is absent");
    }
  }

  if (facts.get("mcpServer") === "stdio-public-product-api") {
    const operations = read("mcp/engineering/operations.ts");
    if (!operations.includes("product-api")) {
      errors.push("mcpServer fact claims API backing but operations.ts does not reference the product API");
    }
    for (const tool of MCP_TOOLS) {
      if (!operations.includes(tool)) errors.push(`mcpServer fact is missing the documented tool ${tool}`);
    }
  }

  if (facts.get("nativeSolvers") === "capability-gated-fail-closed") {
    const capabilities = read("scripts/platform/capabilities.mjs");
    if (!capabilities.includes("CAPABILITY_MANIFESTS")) {
      errors.push("nativeSolvers fact claims capability gating but capabilities.mjs does not use the manifest registry");
    }
  }

  if (facts.get("containers") === "manifests-ci-build-smoke") {
    const smoke = read("scripts/platform/container-smoke.mjs");
    for (const token of ["SMOKE_NO_DAEMON", "docker", "build"]) {
      if (!smoke.includes(token)) errors.push(`containers fact is missing the container-smoke marker ${token}`);
    }
  }

  if (facts.get("cachePersistence") === "persistent-content-addressed") {
    if (!existsSync(resolve(repoRoot, "packages/cache/src/persistent-cache.ts"))) {
      errors.push("cachePersistence fact claims a persistent cache but persistent-cache.ts is missing");
    }
    const store = read("services/api/aeroworkbench_api/repositories/cache_store.py");
    if (!store.includes("reuse_if_trusted")) {
      errors.push("cachePersistence fact claims trusted reuse but cache_store.py lacks reuse_if_trusted");
    }
  }

  if (facts.get("authoritativeExecutionOwner") === "services-api-governed-inprocess-native-jobs") {
    const stack = read("scripts/platform/stack.mjs");
    const routes = read("services/api/aeroworkbench_api/native_jobs.py");
    if (!stack.includes("v1/native") || !routes.includes("/v1/native")) {
      errors.push("authoritativeExecutionOwner fact is not backed by the in-process API native job routes");
    }
  }

  if (facts.get("remoteCompute") === "disabled-by-default-user-only") {
    const policy = read("mcp/engineering/policy.ts");
    if (!policy.includes("AERO_ALLOW_REMOTE_COMPUTE") || !policy.includes("rejectRemoteEscalation")) {
      errors.push("remoteCompute fact is not backed by the MCP remote-escalation gate");
    }
  }
};

const checkReadmeCommands = (repoRoot, errors) => {
  const readme = readDoc(repoRoot, "README.md");
  if (readme === null) {
    errors.push("README.md is missing");
    return;
  }
  const pkgPath = resolve(repoRoot, "package.json");
  if (!existsSync(pkgPath)) {
    errors.push("package.json is missing");
    return;
  }
  const scripts = Object.keys(JSON.parse(readFileSync(pkgPath, "utf8")).scripts ?? {});
  const pnpmSubcommands = new Set([
    "install", "exec", "dlx", "run", "add", "remove", "config", "store", "approve-builds",
    "init", "create", "audit", "outdated", "list", "ls", "view", "info", "publish", "pack",
    "prune", "rebuild", "fetch", "deploy", "why", "ping", "login", "logout", "whoami", "link", "unlink",
  ]);
  const pattern = /pnpm\s+(?:run\s+)?([A-Za-z0-9@:][A-Za-z0-9:@/_.-]*)/g;
  for (const match of readme.matchAll(pattern)) {
    const token = match[1];
    if (token.startsWith("-") || token.startsWith("@") || token.includes("/")) continue;
    if (pnpmSubcommands.has(token)) continue;
    if (!scripts.includes(token)) errors.push(`README references unknown pnpm script: ${token}`);
  }
  const pathPattern = /`((?:scripts|docs|infra|tests|services|apps|packages|mcp)\/[A-Za-z0-9_.\-/]+)`/g;
  for (const match of readme.matchAll(pathPattern)) {
    if (!existsSync(resolve(repoRoot, match[1]))) errors.push(`README references missing local path: ${match[1]}`);
  }
};

/**
 * Pure marker/stale-phrase check. `facts` is a flat string map and `docs` maps
 * an owned relative path to its text. Exposed so tests can prove the known
 * stale-contradiction classes fail without mutating the real checkout.
 */
export function checkDocumentMarkerConsistency(factsInput, docs) {
  const errors = [];
  const facts = new Map(Object.entries(factsInput ?? {}));
  const declared = new Map();
  for (const [relative, text] of Object.entries(docs ?? {})) {
    for (const [key, value] of parseMarkers(text)) {
      if (!declared.has(key)) declared.set(key, []);
      declared.get(key).push({ relative, value });
    }
    for (const phrase of STALE_PHRASES[relative] ?? []) {
      if (text.includes(phrase)) errors.push(`${relative} contains stale phrase: "${phrase}"`);
    }
  }
  for (const [key, value] of facts) {
    const declarations = declared.get(key);
    if (!declarations || declarations.length === 0) {
      errors.push(`no owned document declares capability marker ${key}`);
      continue;
    }
    for (const declaration of declarations) {
      if (declaration.value !== value) {
        errors.push(`${declaration.relative} marker ${key}=${declaration.value} disagrees with capabilityFacts (${value})`);
      }
    }
  }
  for (const key of declared.keys()) {
    if (!facts.has(key)) errors.push(`owned document declares unknown capability marker ${key}`);
  }
  return errors;
}

export function runDocConsistencyChecks(options = {}) {
  const repoRoot = resolve(options.repoRoot ?? defaultRoot());
  const errors = [];
  const auditPath = resolve(repoRoot, "docs/requirements-audit.json");
  let document;
  try {
    document = loadAudit(auditPath);
  } catch (error) {
    return [`docs/requirements-audit.json is unreadable: ${error instanceof Error ? error.message : String(error)}`];
  }

  errors.push(...validateAuditDocument(document, { repoRoot }));

  const facts = flattenFacts(document.capabilityFacts);
  for (const key of REQUIRED_FACT_KEYS) {
    if (!facts.has(key)) errors.push(`capabilityFacts.${key} is required`);
  }

  const docs = {};
  for (const relative of OWNED_DOCS) {
    const text = readDoc(repoRoot, relative);
    if (text === null) {
      errors.push(`owned document is missing: ${relative}`);
      continue;
    }
    docs[relative] = text;
  }

  errors.push(
    ...checkDocumentMarkerConsistency(
      Object.fromEntries([...facts].filter(([key]) => REQUIRED_FACT_KEYS.includes(key))),
      docs,
    ),
  );

  checkCodeFacts(repoRoot, facts, errors);
  checkReadmeCommands(repoRoot, errors);
  return errors;
}

if (process.argv[1] && resolve(process.argv[1]) === resolve(fileURLToPath(import.meta.url))) {
  const errors = runDocConsistencyChecks();
  if (errors.length === 0) {
    process.stdout.write("doc-consistency: OK\n");
  } else {
    process.stdout.write(`doc-consistency: ${errors.length} problem(s)\n`);
    for (const error of errors) process.stdout.write(`  - ${error}\n`);
    process.exitCode = 1;
  }
}
