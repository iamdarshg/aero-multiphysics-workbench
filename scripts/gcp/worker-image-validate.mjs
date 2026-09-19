// Static validator for the pinned native-solver worker images (issue #43).
//
// This host has no Docker daemon, so image builds are documented but not run.
// Everything that can be proven without a daemon is proven here:
//   - base images are immutable digests (never `:latest`);
//   - pins.json is internally consistent and has no floating versions;
//   - every Dockerfile carries the required solver install surface, a
//     non-root user, and an allowlisted ENTRYPOINT;
//   - the capability-manifest schema and a representative sample are valid.
//
// Run: node scripts/gcp/worker-image-validate.mjs
import { readFileSync, existsSync } from "node:fs";
import { join } from "node:path";

export const DIGEST_RE = /^sha256:[0-9a-f]{64}$/;
export const REQUIRED_SOLVER_IDS = Object.freeze([
  "openfoam",
  "code-aster",
  "elmer",
  "precice",
]);

export class WorkerImageError extends Error {
  constructor(code) {
    super(code);
    this.name = "WorkerImageError";
  }
}

const fail = (code) => {
  throw new WorkerImageError(code);
};

export const readJson = (path) => JSON.parse(readFileSync(path, "utf8"));

export const parseDockerfileFromLines = (text) => {
  const froms = [];
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trim();
    if (!line || line.startsWith("#")) continue;
    const match = /^FROM\s+(\S+)(?:\s+AS\s+(\S+))?$/i.exec(line);
    if (match) froms.push({ image: match[1], stage: match[2] ?? null });
  }
  return froms;
};

const hasFloatingTag = (ref) => /:latest(\s|$)/.test(ref) || /(^|[:/])latest(@|$)/.test(ref);

export const validateNoFloating = (label, text) => {
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trim();
    if (!line || line.startsWith("#")) continue;
    if (hasFloatingTag(line)) fail(`${label}:FLOATING_LATEST:${line}`);
  }
};

export const validatePins = (pins) => {
  if (pins.schemaVersion !== 1) fail("pins:SCHEMA_VERSION");
  if (!/^3\.12/.test(String(pins.pythonVersion))) fail("pins:PYTHON_VERSION");

  const base = pins.baseImages ?? {};
  for (const name of ["participants-python", "native-solvers"]) {
    const image = base[name];
    if (!image) fail(`pins:MISSING_BASE:${name}`);
    if (!DIGEST_RE.test(image.digest)) fail(`pins:BASE_NOT_DIGEST:${name}`);
    if (hasFloatingTag(image.ref) || /:latest$/.test(image.ref)) {
      fail(`pins:BASE_LATEST:${name}`);
    }
  }

  if (!/^[0-9a-f]{64}$/.test(pins.micromamba?.sha256 ?? "")) fail("pins:MICROMAMBA_SHA256");
  if ((pins.micromamba?.url ?? "").includes("/latest")) fail("pins:MICROMAMBA_LATEST");
  if (!(pins.micromamba?.url ?? "").includes(pins.micromamba?.version ?? "\u0000")) {
    fail("pins:MICROMAMBA_VERSION_URL");
  }

  const direct = pins.pythonLock?.directPins ?? {};
  for (const [name, version] of Object.entries(direct)) {
    if (typeof version !== "string" || !/^\d+(\.\d+)*([.a-z0-9-]*)$/i.test(version) || /[<>=]/.test(version)) {
      fail(`pins:PYTHON_PIN_NOT_EXACT:${name}:${version}`);
    }
  }
  if (pins.pythonLock?.source !== "services/api/uv.lock") fail("pins:PYTHON_LOCK_SOURCE");

  const conda = pins.condaSolverPrefixes ?? {};
  // Elmer ships through the elmer-csc PPA, not conda-forge, so only these
  // three native families are required to have a conda-forge prefix.
  for (const id of ["openfoam", "precice", "code-aster"]) {
    if (!conda[id]) fail(`pins:MISSING_CONDA_SOLVER:${id}`);
  }
  for (const [id, spec] of Object.entries(conda)) {
    for (const [pkg, version] of Object.entries(spec.packages ?? {})) {
      if (!/^\d/.test(String(version)) || /[<>=*]/.test(String(version))) {
        fail(`pins:CONDA_PIN_NOT_EXACT:${id}:${pkg}:${version}`);
      }
    }
    if (!Array.isArray(spec.executables) || spec.executables.length === 0) {
      fail(`pins:CONDA_EXECUTABLES:${id}`);
    }
  }

  const apt = pins.apt?.ppas ?? {};
  for (const [name, spec] of Object.entries(apt)) {
    for (const [pkg, version] of Object.entries(spec.packages ?? {})) {
      if (!version || /[<>=*]/.test(version)) fail(`pins:APT_PIN_NOT_EXACT:${name}:${pkg}`);
    }
  }

  const recorded = pins.recorded ?? {};
  for (const name of ["participants-python", "native-solvers"]) {
    const entry = recorded[name];
    if (!entry) fail(`pins:RECORDED_MISSING:${name}`);
    if (entry.status === "PENDING") {
      if (!entry.reason || !entry.reason.trim()) fail(`pins:PENDING_NEEDS_REASON:${name}`);
      if (entry.digest !== null) fail(`pins:PENDING_DIGEST_SET:${name}`);
    } else if (entry.status === "RESOLVED") {
      if (!DIGEST_RE.test(entry.digest ?? "")) fail(`pins:RESOLVED_NEEDS_DIGEST:${name}`);
    } else {
      fail(`pins:RECORDED_STATUS:${name}`);
    }
  }
  return true;
};

export const validateDockerfile = (name, text, pins, expectations) => {
  validateNoFloating(name, text);
  const froms = parseDockerfileFromLines(text);
  if (froms.length === 0) fail(`${name}:NO_FROM`);
  const expected = pins.baseImages[name];
  if (!expected) fail(`${name}:NO_PIN_ENTRY`);
  const first = froms[0];
  if (!first.image.includes("@")) fail(`${name}:FROM_NOT_DIGEST_PINNED:${first.image}`);
  if (!first.image.endsWith(`@${expected.digest}`)) fail(`${name}:FROM_DIGEST_MISMATCH:${first.image}`);
  if (first.image.split("@")[0] !== expected.ref) fail(`${name}:FROM_REF_MISMATCH:${first.image}`);
  for (const from of froms.slice(1)) {
    if (!from.image.includes("@") && !from.image.startsWith("${")) {
      fail(`${name}:EXTRA_FROM_NOT_DIGEST:${from.image}`);
    }
  }

  if (!/^USER\s+worker\s*$/m.test(text)) fail(`${name}:NO_NON_ROOT_USER`);
  if (/^USER\s+root\s*$/mi.test(text)) fail(`${name}:USER_ROOT`);
  if (!/^ENTRYPOINT\s+\[/m.test(text)) fail(`${name}:NO_ENTRYPOINT`);
  if (!text.includes("--no-install-recommends")) fail(`${name}:NOT_MINIMAL_APT`);

  for (const token of expectations.installTokens ?? []) {
    if (!text.includes(token)) fail(`${name}:MISSING_INSTALL:${token}`);
  }
  for (const token of expectations.forbiddenTokens ?? []) {
    if (text.includes(token)) fail(`${name}:FORBIDDEN_TOKEN:${token}`);
  }
  return froms;
};

export const validateCapabilitySchema = (schema) => {
  if (!String(schema.$schema ?? "").includes("2020-12")) fail("schema:DRAFT");
  const required = schema.required ?? [];
  for (const key of ["schemaVersion", "image", "python", "solvers"]) {
    if (!required.includes(key)) fail(`schema:MISSING_REQUIRED:${key}`);
  }
  const solverItem = schema.properties?.solvers?.items?.properties ?? {};
  if (solverItem.state?.enum?.join() !== "ready,unavailable") fail("schema:STATE_ENUM");
  if (!["executable,library", "library,executable"].includes(solverItem.kind?.enum?.join())) {
    fail("schema:KIND_ENUM");
  }
  const digestPattern = schema.properties?.image?.properties?.digest?.pattern ?? "";
  if (!digestPattern.includes("sha256") || !digestPattern.includes("64")) fail("schema:DIGEST_PATTERN");
  return true;
};

export const validateManifestShape = (manifest, { allowedIds } = {}) => {
  if (manifest.schemaVersion !== 1) fail("manifest:SCHEMA_VERSION");
  if (!manifest.image?.role) fail("manifest:IMAGE_ROLE");
  if (!DIGEST_RE.test(manifest.image?.baseDigest ?? "")) fail("manifest:BASE_DIGEST");
  if (!/^(sha256:[0-9a-f]{64}|PENDING)$/.test(manifest.image?.digest ?? "")) {
    fail("manifest:IMAGE_DIGEST");
  }
  if (!/^3\.12\./.test(manifest.python?.version ?? "")) fail("manifest:PYTHON_VERSION");
  if (!Array.isArray(manifest.solvers) || manifest.solvers.length === 0) fail("manifest:NO_SOLVERS");
  for (const entry of manifest.solvers) {
    if (!entry.id) fail("manifest:SOLVER_ID");
    if (!["ready", "unavailable"].includes(entry.state)) fail(`manifest:STATE:${entry.id}`);
    if (!["executable", "library"].includes(entry.kind)) fail(`manifest:KIND:${entry.id}`);
    if (allowedIds && !allowedIds.has(entry.id)) fail(`manifest:UNKNOWN_ID:${entry.id}`);
  }
  return true;
};

export const validateStartupScript = (text) => {
  if (!/sha256:/.test(text)) fail("startup:NO_DIGEST_PULL");
  if (!/@\$\{?DIGEST/.test(text)) fail("startup:NO_DIGEST_PULL");
  if (/apt-get\s+install[^\n]*\b(openfoam|elmer|precice|code-aster)\b/i.test(text)) {
    fail("startup:RUNTIME_SOLVER_INSTALL");
  }
  if (!/set -euo pipefail/.test(text)) fail("startup:NO_FAIL_CLOSED");
  return true;
};

const DEFAULTS = {
  root: process.cwd(),
};

export const validateWorkspace = ({ root = DEFAULTS.root } = {}) => {
  const workerDir = join(root, "infra", "docker", "worker");
  const pinsPath = join(workerDir, "pins.json");
  const schemaPath = join(workerDir, "capability-manifest.schema.json");
  for (const path of [pinsPath, schemaPath]) {
    if (!existsSync(path)) fail(`MISSING_FILE:${path}`);
  }
  const pins = readJson(pinsPath);
  validatePins(pins);
  validateCapabilitySchema(readJson(schemaPath));

  const expectations = {
    "participants-python": {
      installTokens: ["uv sync --frozen", "cantera==${CANTERA_VERSION}", "ross-rotordynamics"],
      forbiddenTokens: ["micromamba create", "elmerfem-csc="],
    },
    "native-solvers": {
      installTokens: [
        "openfoam=2412",
        "code-aster=18.1.6",
        "precice=3.2.0",
        "elmerfem-csc=9.0-0ppa0-202609171021~9ef450fbb~ubuntu22.04.1",
        "gmsh=4.15.2",
        "uv sync --frozen",
        "cantera==${CANTERA_VERSION}",
      ],
      forbiddenTokens: [],
    },
  };

  const dockerfiles = {};
  for (const [name, spec] of Object.entries(pins.baseImages)) {
    const path = join(root, spec.dockerfile);
    if (!existsSync(path)) fail(`MISSING_DOCKERFILE:${name}`);
    const text = readFileSync(path, "utf8");
    validateDockerfile(name, text, pins, expectations[name]);
    dockerfiles[name] = text;
  }

  const emitterPath = join(workerDir, "emit_capability_manifest.py");
  if (!existsSync(emitterPath)) fail("MISSING_EMITTER");
  const emitter = readFileSync(emitterPath, "utf8");
  for (const id of [...REQUIRED_SOLVER_IDS, "gmsh", "ross", "pybamm"]) {
    if (!emitter.includes(`"${id}"`)) fail(`emitter:MISSING_SOLVER:${id}`);
  }

  const startupPath = join(root, "scripts", "gcp", "worker-image-startup.sh");
  if (!existsSync(startupPath)) fail("MISSING_STARTUP");
  validateStartupScript(readFileSync(startupPath, "utf8"));

  const sample = {
    schemaVersion: 1,
    image: {
      name: "aero-worker-native",
      role: "native-solvers",
      digest: "PENDING",
      builtAt: "2026-09-19T00:00:00Z",
      baseRef: pins.baseImages["native-solvers"].ref,
      baseDigest: pins.baseImages["native-solvers"].digest,
    },
    python: { path: "/opt/participants/.venv/bin/python", version: "3.12.13" },
    solvers: [...REQUIRED_SOLVER_IDS, "gmsh", "ross", "pybamm"].map((id) => ({
      id,
      state: "ready",
      kind: "executable",
      path: id,
      version: "1.0",
    })),
  };
  validateManifestShape(sample, {
    allowedIds: new Set([
      ...REQUIRED_SOLVER_IDS,
      "gmsh",
      "ross",
      "pybamm",
      "cadquery",
      "cantera",
      "openmdao",
    ]),
  });

  return { pins, dockerfiles };
};

const main = () => {
  try {
    const { pins } = validateWorkspace({ root: process.cwd() });
    console.log(
      `worker-image: OK base=${Object.keys(pins.baseImages).join(",")} ` +
        `recorded=${Object.entries(pins.recorded)
          .map(([name, entry]) => `${name}:${entry.status}`)
          .join(",")}`,
    );
    return 0;
  } catch (error) {
    console.error(`worker-image: FAIL ${error.message}`);
    return 1;
  }
};

const invokedDirectly = (() => {
  try {
    return process.argv[1] && process.argv[1].replace(/\\/g, "/").endsWith("scripts/gcp/worker-image-validate.mjs");
  } catch {
    return false;
  }
})();

if (invokedDirectly) process.exitCode = main();
