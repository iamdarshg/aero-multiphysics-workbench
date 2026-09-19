import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

import {
  DIGEST_RE,
  WorkerImageError,
  parseDockerfileFromLines,
  readJson,
  validateCapabilitySchema,
  validateDockerfile,
  validateManifestShape,
  validateNoFloating,
  validatePins,
  validateStartupScript,
  validateWorkspace,
} from "../../scripts/gcp/worker-image-validate.mjs";

const root = fileURLToPath(new URL("../../", import.meta.url));
const workerDir = join(root, "infra", "docker", "worker");
const pins = readJson(join(workerDir, "pins.json"));
const schema = readJson(join(workerDir, "capability-manifest.schema.json"));
const dockerfiles = Object.fromEntries(
  Object.entries(pins.baseImages).map(([name, spec]) => [name, readFileSync(join(root, spec.dockerfile), "utf8")]),
);

test("every base image is pinned by an immutable sha256 digest, never latest", () => {
  assert.equal(validatePins(pins), true);
  for (const [name, image] of Object.entries(pins.baseImages)) {
    assert.match(image.digest, DIGEST_RE, `${name} digest is not immutable`);
    assert.doesNotMatch(image.ref, /:latest$/);
  }
  assert.ok(!JSON.stringify(pins).includes(":latest"));
});

test("Dockerfiles source FROM the pinned digest and declare no second FROM", () => {
  for (const [name, text] of Object.entries(dockerfiles)) {
    const froms = parseDockerfileFromLines(text);
    assert.equal(froms.length, 1, `${name} must have exactly one base stage`);
    assert.ok(froms[0].image.endsWith(`@${pins.baseImages[name].digest}`));
    validateDockerfile(name, text, pins, { installTokens: [] });
  }
});

test("Dockerfiles carry the required solver install surface", () => {
  const python = dockerfiles["participants-python"];
  for (const token of ["uv sync --frozen", "ross-rotordynamics", "cantera=="]) {
    assert.ok(python.includes(token), `participants-python missing ${token}`);
  }
  assert.ok(!python.includes("micromamba create"), "python image must not install native solvers");

  const native = dockerfiles["native-solvers"];
  for (const token of [
    "openfoam=2412",
    "code-aster=18.1.6",
    "precice=3.2.0",
    "elmerfem-csc=9.0-0ppa0-202609171021~9ef450fbb~ubuntu22.04.1",
    "gmsh=4.15.2",
    "ross-rotordynamics",
    "cantera==",
  ]) {
    assert.ok(native.includes(token), `native-solvers missing ${token}`);
  }
});

test("worker images are non-root with an allowlisted entrypoint and minimal apt", () => {
  for (const [name, text] of Object.entries(dockerfiles)) {
    assert.match(text, /^USER worker$/m, `${name} must drop to the worker user`);
    assert.match(text, /^ENTRYPOINT \["/m, `${name} needs an exec-form entrypoint`);
    assert.ok(text.includes("--no-install-recommends"), `${name} must use minimal apt`);
    assert.ok(!/^USER root$/m.test(text), `${name} must not run as root`);
  }
  const entrypoint = readFileSync(join(workerDir, "worker-entrypoint.sh"), "utf8");
  for (const subcommand of ["capabilities", "verify", "smoke", "version"]) {
    assert.ok(entrypoint.includes(subcommand), `entrypoint missing ${subcommand}`);
  }
  assert.ok(entrypoint.includes("unknown subcommand"), "entrypoint must reject unknown commands");
});

test("capability-manifest schema and representative sample validate", () => {
  assert.equal(validateCapabilitySchema(schema), true);
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
    solvers: ["openfoam", "code-aster", "elmer", "precice", "gmsh", "ross", "pybamm"].map((id) => ({
      id,
      state: "ready",
      kind: "executable",
      path: id,
      version: "1.0",
    })),
  };
  assert.equal(validateManifestShape(sample), true);
  assert.throws(
    () => validateManifestShape({ ...sample, schemaVersion: 2 }),
    WorkerImageError,
  );
  assert.throws(
    () => validateManifestShape({ ...sample, image: { ...sample.image, baseDigest: ":latest" } }),
    WorkerImageError,
  );
});

test("startup script pulls by digest, refuses runtime solver installs, fails closed", () => {
  const startup = readFileSync(join(root, "scripts", "gcp", "worker-image-startup.sh"), "utf8");
  assert.equal(validateStartupScript(startup), true);
  assert.ok(startup.includes("PENDING"), "startup must fail closed on an unrecorded digest");
});

test("static validator rejects floating tags and digest drift", () => {
  const native = dockerfiles["native-solvers"];
  assert.throws(
    () => validateNoFloating("x", "FROM ubuntu:22.04:latest"),
    WorkerImageError,
  );
  assert.throws(
    () =>
      validateDockerfile(
        "native-solvers",
        native.replace(pins.baseImages["native-solvers"].digest, "0".repeat(64)),
        pins,
        { installTokens: [] },
      ),
    WorkerImageError,
  );
  const tampered = structuredClone(pins);
  tampered.baseImages["native-solvers"].digest = "sha256:not-a-digest";
  assert.throws(() => validatePins(tampered), WorkerImageError);
  const pendingWithoutReason = structuredClone(pins);
  pendingWithoutReason.recorded["native-solvers"].reason = "";
  assert.throws(() => validatePins(pendingWithoutReason), WorkerImageError);
});

test("full static workspace validation passes (no Docker daemon required)", () => {
  const { pins: resolved } = validateWorkspace({ root });
  assert.equal(resolved.recorded["native-solvers"].status, "PENDING");
  assert.equal(resolved.recorded["participants-python"].status, "PENDING");
});

test("smoke proof records a digest-verified receipt and never fabricates status", () => {
  const smoke = readFileSync(join(root, "scripts", "gcp", "worker-smoke.py"), "utf8");
  assert.ok(smoke.includes(".sha256"), "smoke must write a detached sha256 sidecar");
  assert.ok(smoke.includes('"BLOCKED"') && smoke.includes('"SKIPPED"'), "smoke must report BLOCKED/SKIPPED");
  assert.ok(smoke.includes("capability_agreement"), "smoke must gate on capability agreement");
  assert.ok(smoke.includes("MISMATCH"), "smoke must fail closed on manifest disagreement");
});
