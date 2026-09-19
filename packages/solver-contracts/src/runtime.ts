import { createHash, randomUUID } from "node:crypto";
import { spawn } from "node:child_process";
import { stat } from "node:fs/promises";
import { join } from "node:path";
import { CAPABILITY_MANIFESTS, describeManifest } from "./manifests.ts";
import { findParticipant } from "./participants.ts";
import { isPathContained } from "./scheduler.ts";
import type { Capability, CapabilityReport, LaunchRequest, ProvenanceEvent, ResultRecord, RunRecord, SolverId, SolverManifest } from "./contracts.ts";

export type Probe = (manifest: SolverManifest) => Promise<Capability>;

const normalizedExecutable = (command: string): string => process.platform === "win32"
  ? command.toLowerCase().replace(/\.exe$/, "")
  : command;

const unsafeArgument = (arg: string): boolean => arg.includes("\u0000") || /[\r\n]/.test(arg) || /^(?:-Command|-EncodedCommand)$/i.test(arg);

/** Builds an opaque native command through the immutable manifest policy. */
export const buildSolverCommand = (solverId: SolverId, input: { readonly caseDirectory: string }) => {
  const manifest = CAPABILITY_MANIFESTS.find((candidate) => candidate.id === solverId);
  if (!manifest || manifest.allowedExecutables.length === 0) throw new Error(`SOLVER_MANIFEST_UNAVAILABLE: ${solverId}`);
  const command = manifest.buildCommand(input);
  if (normalizedExecutable(command.executable) !== normalizedExecutable(manifest.allowedExecutables[0] as string) || command.args.some(unsafeArgument)) {
    throw new Error(`ARGUMENTS_NOT_ALLOWLISTED: ${solverId}`);
  }
  return command;
};

/** Executes only the immutable registry's fixed version probe; it never installs or starts a solver. */
export const commandProbe: Probe = async (manifest) => new Promise((resolve) => {
  const trustedManifest = CAPABILITY_MANIFESTS.find((candidate) => candidate.id === manifest.id);
  if (trustedManifest !== manifest) {
    resolve({ available: false, detail: "manifest is not from the trusted registry" });
    return;
  }
  const command = manifest.versionProbe.executable;
  const args = manifest.versionProbe.args;
  if (!command) return resolve({ available: false, detail: "empty version probe" });
  let stdout = "";
  let settled = false;
  const finish = (capability: Capability) => {
    if (settled) return;
    settled = true;
    resolve({ ...capability, checkedAt: new Date().toISOString() });
  };
  const child = spawn(command, [...args], { shell: false, windowsHide: true, stdio: ["ignore", "pipe", "pipe"] });
  const timer = setTimeout(() => { child.kill(); finish({ available: false, detail: "version probe timed out" }); }, 5_000);
  child.stdout.on("data", (chunk: Buffer) => { stdout += chunk.toString(); });
  child.once("error", (error) => { clearTimeout(timer); finish({ available: false, detail: error.code === "ENOENT" ? "command not found" : error.message }); });
  child.once("close", (code) => {
    clearTimeout(timer);
    const version = stdout.trim().split(/\r?\n/, 1)[0];
    finish(code === 0 ? { available: true, detail: "native command responded", version } : { available: false, detail: `command exited ${code}` });
  });
});

export class CapabilityDetector {
  private readonly probe: Probe;
  constructor(probe: Probe) { this.probe = probe; }

  async detect(manifests: readonly SolverManifest[] = CAPABILITY_MANIFESTS): Promise<CapabilityReport> {
    const checkedAt = new Date().toISOString();
    const entries = await Promise.all(manifests.map(async (manifest) => ({ id: manifest.id, ...(await this.probe(manifest)), checkedAt })));
    return { checkedAt, ready: entries.filter((entry) => entry.available), unavailable: entries.filter((entry) => !entry.available) };
  }
}

const sha256 = (value: string): string => createHash("sha256").update(value).digest("hex");

/** Environment keys always folded into a cache fingerprint. */
const DEFAULT_ENVIRONMENT_KEYS: readonly string[] = Object.freeze([
  "PATH", "Path", "PATHEXT", "SystemRoot", "windir", "HOME", "USERPROFILE",
]);

/** Prefixes for solver-runtime environment that changes a resolved capability. */
const RELEVANT_ENVIRONMENT_PREFIXES: readonly string[] = Object.freeze([
  "AERO", "SOLVER", "OPENFOAM", "ELMER", "ASTER", "CODE_ASTER", "ROSS", "PYBAMM",
  "CANTERA", "PYCYCLE", "CADQUERY", "GMSH", "VSP", "FREECAD", "CONDA", "VIRTUAL_ENV",
]);

const environmentDigest = (
  environment: Readonly<Record<string, string | undefined>>,
  keys: readonly string[],
): string => {
  const selected = new Map<string, string>();
  for (const key of keys) {
    const value = environment[key];
    if (value !== undefined) selected.set(key, value);
  }
  for (const key of Object.keys(environment).sort()) {
    if (selected.has(key)) continue;
    const upper = key.toUpperCase();
    if (RELEVANT_ENVIRONMENT_PREFIXES.some((prefix) => upper.startsWith(prefix))) {
      const value = environment[key];
      if (value !== undefined) selected.set(key, value);
    }
  }
  const canonical = [...selected.entries()]
    .sort(([left], [right]) => (left < right ? -1 : left > right ? 1 : 0))
    .map(([key, value]) => `${key}=${value}`)
    .join("\u0001");
  return sha256(canonical);
};

const isPathLikeCommand = (command: string): boolean =>
  command.includes("/") || command.includes("\\") || /^[A-Za-z]:/.test(command);

/**
 * Resolves an executable's current on-disk identity without spawning. This is
 * a bounded filesystem lookup (PATH directories × PATHEXT extensions), far
 * cheaper than a process spawn, and it detects an in-place binary replacement.
 */
export const resolveExecutableIdentity = async (
  command: string,
  environment: Readonly<Record<string, string | undefined>> = process.env,
): Promise<string | null> => {
  if (!command) return null;
  const platform = process.platform;
  const candidates: string[] = [];
  if (isPathLikeCommand(command)) {
    candidates.push(command);
  } else {
    const pathValue = environment.PATH ?? environment.Path ?? "";
    const extensions = platform === "win32"
      ? (environment.PATHEXT ?? ".COM;.EXE;.BAT;.CMD").split(";").filter((entry) => entry.length > 0)
      : [""];
    for (const directory of pathValue.split(platform === "win32" ? ";" : ":")) {
      if (!directory) continue;
      for (const extension of extensions) candidates.push(join(directory, `${command}${extension}`));
      if (platform !== "win32") candidates.push(join(directory, command));
    }
  }
  for (const candidate of candidates) {
    try {
      const info = await stat(candidate);
      if (info.isFile()) return `${candidate}|${info.size}|${Math.floor(info.mtimeMs)}`;
    } catch {
      // Keep searching; a missing candidate simply moves the resolution on.
    }
  }
  return null;
};

export interface CapabilityProbeCacheOptions {
  /** The probe to cache; defaults to the immutable registry's {@link commandProbe}. */
  readonly probe?: Probe;
  /** Process-lifetime by default; supply a positive TTL to expire entries. */
  readonly ttlMs?: number;
  /** Injectable clock (epoch ms) for deterministic tests. */
  readonly now?: () => number;
  /** Environment snapshot used for invalidation; defaults to `process.env`. */
  readonly environment?: Readonly<Record<string, string | undefined>>;
  /** Extra environment keys folded into the fingerprint. */
  readonly environmentKeys?: readonly string[];
  /**
   * Optional on-disk executable identity resolver. Off by default because a
   * PATH filesystem scan per executable is not free; when supplied it detects
   * an in-place binary replacement at the bounded identity refresh interval.
   * Without it, executable changes are handled by explicit {@link CapabilityProbeCache.invalidate}.
   */
  readonly executableIdentity?: (command: string) => Promise<string | null> | string | null;
  /** How often an injected executable identity may be re-resolved; default 30s. */
  readonly executableTtlMs?: number;
}

export interface CapabilityProbeCacheStats {
  readonly hits: number;
  readonly misses: number;
  readonly probes: number;
  readonly invalidations: number;
  readonly entries: number;
}

interface CapabilityCacheEntry {
  readonly fingerprint: string;
  readonly capability: Capability;
  readonly probedAtMs: number;
  readonly executableIdentity: string | null;
  readonly identityAtMs: number;
}

/**
 * Process-lifetime cache of native capability/version probes.
 *
 * A cached entry is reused while its fingerprint (manifest descriptor +
 * relevant environment) is unchanged and within TTL. The fingerprint is a
 * cheap synchronous hash, so a warm query never touches the filesystem or
 * spawns a process. Concurrent probes for the same fingerprint are
 * single-flighted. {@link CapabilityProbeCache.invalidate} is the explicit
 * refresh path; an injected executable-identity resolver additionally detects
 * an in-place binary replacement at the bounded refresh interval.
 */
export class CapabilityProbeCache {
  private readonly probe: Probe;
  private readonly now: () => number;
  private readonly ttlMs: number | undefined;
  private readonly environment: Readonly<Record<string, string | undefined>>;
  private readonly environmentKeys: readonly string[];
  private readonly identityResolver: ((command: string) => Promise<string | null>) | null;
  private readonly executableTtlMs: number;
  private readonly entries = new Map<SolverId, CapabilityCacheEntry>();
  private readonly identities = new Map<string, { identity: string | null; atMs: number }>();
  private readonly inflight = new Map<string, Promise<Capability>>();
  private counters = { hits: 0, misses: 0, probes: 0, invalidations: 0 };

  constructor(options: CapabilityProbeCacheOptions = {}) {
    this.probe = options.probe ?? commandProbe;
    this.now = options.now ?? (() => Date.now());
    this.ttlMs = options.ttlMs;
    if (this.ttlMs !== undefined && (!Number.isFinite(this.ttlMs) || this.ttlMs <= 0)) {
      throw new Error("INVALID_CAPABILITY_CACHE_TTL");
    }
    this.environment = options.environment ?? process.env;
    this.environmentKeys = options.environmentKeys ?? DEFAULT_ENVIRONMENT_KEYS;
    const identity = options.executableIdentity;
    this.identityResolver = identity ? async (command: string) => identity(command) : null;
    this.executableTtlMs = options.executableTtlMs ?? 30_000;
    if (!Number.isFinite(this.executableTtlMs) || this.executableTtlMs < 0) {
      throw new Error("INVALID_EXECUTABLE_TTL");
    }
  }

  /** Resolves (and briefly caches) the on-disk identity of a probe executable. */
  async resolveIdentity(command: string): Promise<string | null> {
    if (!this.identityResolver) return resolveExecutableIdentity(command, this.environment);
    const cached = this.identities.get(command);
    const now = this.now();
    if (cached && now - cached.atMs < this.executableTtlMs) return cached.identity;
    const identity = await this.identityResolver(command);
    this.identities.set(command, { identity, atMs: now });
    return identity;
  }

  /** Cheap synchronous fingerprint of the manifest and relevant environment. */
  fingerprint(manifest: SolverManifest): string {
    return sha256([
      describeManifest(manifest),
      environmentDigest(this.environment, this.environmentKeys),
    ].join("\u0002"));
  }

  private withinTtl(probedAtMs: number): boolean {
    return this.ttlMs === undefined || this.now() - probedAtMs < this.ttlMs;
  }

  /**
   * True when the entry can be reused. When an identity resolver is installed,
   * the identity is re-resolved at most once per `executableTtlMs`; a changed
   * identity misses and triggers a fresh probe.
   */
  private async reusable(entry: CapabilityCacheEntry | undefined, fingerprint: string, command: string): Promise<CapabilityCacheEntry | undefined> {
    if (!entry || entry.fingerprint !== fingerprint || !this.withinTtl(entry.probedAtMs)) return undefined;
    if (!this.identityResolver) return entry;
    if (this.now() - entry.identityAtMs < this.executableTtlMs) return entry;
    const identity = await this.resolveIdentity(command);
    if (identity === entry.executableIdentity) return entry;
    return undefined;
  }

  /** Returns a cached capability or performs exactly one probe on a miss. */
  async capability(manifest: SolverManifest): Promise<Capability> {
    const fingerprint = this.fingerprint(manifest);
    const entry = this.entries.get(manifest.id);
    const reusable = await this.reusable(entry, fingerprint, manifest.versionProbe.executable);
    if (reusable) {
      this.counters.hits += 1;
      return reusable.capability;
    }
    const pending = this.inflight.get(fingerprint);
    if (pending) return pending;
    this.counters.misses += 1;
    const promise = (async (): Promise<Capability> => {
      const capability = await this.probe(manifest);
      this.counters.probes += 1;
      const identity = this.identityResolver
        ? await this.resolveIdentity(manifest.versionProbe.executable)
        : null;
      this.entries.set(manifest.id, {
        fingerprint,
        capability,
        probedAtMs: this.now(),
        executableIdentity: identity,
        identityAtMs: this.now(),
      });
      return capability;
    })();
    this.inflight.set(fingerprint, promise);
    try {
      return await promise;
    } finally {
      this.inflight.delete(fingerprint);
    }
  }

  /** Cache-aware replacement for {@link CapabilityDetector.detect}. */
  async detect(manifests: readonly SolverManifest[] = CAPABILITY_MANIFESTS): Promise<CapabilityReport> {
    const checkedAt = new Date().toISOString();
    const entries = await Promise.all(manifests.map(async (manifest) => ({
      id: manifest.id,
      ...(await this.capability(manifest)),
      checkedAt,
    })));
    return {
      checkedAt,
      ready: entries.filter((entry) => entry.available),
      unavailable: entries.filter((entry) => !entry.available),
    };
  }

  /** Explicit invalidation, e.g. on user refresh or a reported environment change. */
  invalidate(solverId?: SolverId): void {
    this.counters.invalidations += 1;
    if (solverId === undefined) {
      this.entries.clear();
      this.identities.clear();
      return;
    }
    this.entries.delete(solverId);
  }

  stats(): CapabilityProbeCacheStats {
    return { ...this.counters, entries: this.entries.size };
  }
}

export interface ProvenanceStore {
  append(event: ProvenanceEvent): void;
  list(): readonly ProvenanceEvent[];
}

export const createInMemoryProvenanceStore = (): ProvenanceStore => {
  const events: ProvenanceEvent[] = [];
  return { append: (event) => events.push(event), list: () => [...events] };
};

/** Does not start a process. A worker may execute only after capability and scheduler admission. */
export class SolverGateway {
  private readonly capabilities: Partial<Record<SolverId, Capability>>;
  private readonly provenance: ProvenanceStore;
  constructor(capabilities: Partial<Record<SolverId, Capability>>, provenance: ProvenanceStore) {
    this.capabilities = capabilities;
    this.provenance = provenance;
  }

  async launch(request: LaunchRequest): Promise<RunRecord> {
    const capability = this.capabilities[request.solverId];
    if (!capability?.available) {
      this.provenance.append({ id: randomUUID(), at: new Date().toISOString(), type: "launch-rejected", detail: `CAPABILITY_UNAVAILABLE:${request.solverId}:${capability?.detail ?? "not checked"}` });
      throw new Error(`CAPABILITY_UNAVAILABLE: ${request.solverId}`);
    }
    if (!request.launch || request.requestedMemoryMiB <= 0 || !Number.isFinite(request.requestedMemoryMiB)) throw new Error("INVALID_LAUNCH_REQUEST");
    const manifest = CAPABILITY_MANIFESTS.find((candidate) => candidate.id === request.solverId);
    if (!manifest) throw new Error(`SOLVER_MANIFEST_UNAVAILABLE: ${request.solverId}`);
    buildSolverCommand(request.solverId, request.launch);
    const provenanceId = randomUUID();
    this.provenance.append({ id: provenanceId, at: new Date().toISOString(), type: "launch-accepted", detail: `${request.solverId}:${request.designId}` });
    return { runId: randomUUID(), solverId: request.solverId, designId: request.designId, state: "accepted", source: "native-solver", checkpointFrom: request.checkpointFrom, provenanceId };
  }

  recordResult(
    run: RunRecord,
    result: { artifactUri: string; digestSha256: string },
    evidence?: NativeResultEvidence,
  ): ResultRecord | NativeResultEnvelope {
    if (!evidence) {
      // No completion evidence exists. Never publish a fabricated result.
      throw new Error("NATIVE_RESULT_PUBLICATION_UNVERIFIED");
    }
    const capability = this.capabilities[run.solverId];
    if (!capability?.available) {
      throw new Error(`CAPABILITY_UNAVAILABLE: ${run.solverId}`);
    }
    return publishNativeResult(run, result, evidence, this.provenance);
  }
}

/** Complete evidence chain required to publish one native result. */
export interface NativeEvidenceFile {
  readonly name: string;
  readonly sha256: string;
  readonly bytes: number;
}

export interface NativeResultEvidence {
  readonly capabilityState: "ready" | "unavailable";
  readonly capabilityDetail: string;
  readonly solverId: SolverId;
  readonly solverName: string;
  readonly solverVersion: string;
  readonly inputHash: string;
  readonly runId: string;
  readonly processState: "completed" | "failed" | "timeout" | "cancelled" | "killed" | "start-failed";
  readonly exitCode: number;
  readonly terminationReason?: string;
  readonly peakRssMiB?: number;
  readonly executionMode: "subprocess" | "in-process";
  readonly stdoutSha256?: string;
  readonly stderrSha256?: string;
  readonly parserName: string;
  readonly parserStatus: "ok" | "failed";
  readonly parserDetail?: string;
  readonly jobRoot: string;
  readonly expectedArtifacts?: readonly string[];
  readonly outputFiles: readonly NativeEvidenceFile[];
  readonly geometryHash?: string;
  readonly meshHash?: string;
  readonly participantId: string;
  readonly manifestVersion: "2";
  readonly validityPassed: boolean;
  readonly validityDetail?: string;
  readonly fidelity: string;
  readonly scalars: Readonly<Record<string, number>>;
  readonly units: Readonly<Record<string, string>>;
  readonly warnings?: readonly string[];
}

/** Canonical durable result: units, validity, identity, and provenance. */
export interface NativeResultEnvelope {
  readonly source: "native_solver";
  readonly resultId: string;
  readonly fidelity: string;
  readonly units: Readonly<Record<string, string>>;
  readonly validity: { readonly passed: boolean };
  readonly inputHash: string;
  readonly solverIdentity: string;
  readonly solverVersion: string;
  readonly runId: string;
  readonly provenanceId: string;
  readonly warnings: readonly string[];
  readonly scalars: Readonly<Record<string, number>>;
  readonly artifacts: readonly NativeEvidenceFile[];
}

const HEX64 = /^[a-f0-9]{64}$/;

/** Flat manifest-declared filenames only; nothing may address outside the job root. */
const isContainedArtifactName = (name: string): boolean => {
  if (!name || name === "." || name === "..") return false;
  if (name.includes("/") || name.includes("\\")) return false;
  if (/^[A-Za-z]:/.test(name) || name.startsWith("~")) return false;
  return true;
};

const stripFileScheme = (uri: string): string => (uri.startsWith("file://") ? uri.slice("file://".length) : uri);

const basenameOf = (uri: string): string => {
  const parts = stripFileScheme(uri).replaceAll("\\", "/").split("/").filter((part) => part.length > 0);
  return parts.at(-1) ?? "";
};

const hasTraversalSegment = (uri: string): boolean =>
  stripFileScheme(uri).replaceAll("\\", "/").split("/").some((part) => part === "..");

const isAbsolutePath = (value: string): boolean =>
  value.startsWith("/") || /^[A-Za-z]:[\\/]/.test(value);

/** Evidence-gated native publication; any gap fails closed without a substitute. */
export const publishNativeResult = (
  run: RunRecord,
  result: { artifactUri: string; digestSha256: string },
  evidence: NativeResultEvidence,
  provenance: ProvenanceStore,
): NativeResultEnvelope => {
  const participant = findParticipant(evidence.participantId);
  if (evidence.manifestVersion !== participant.manifestVersion) {
    throw new Error("RESULT_INVALID:stale participant manifest");
  }
  if (run.state !== "accepted") throw new Error(`RESULT_INVALID:run not accepted:${run.state}`);
  if (evidence.capabilityState !== "ready") throw new Error("RESULT_INVALID:capability not verified");
  if (!evidence.solverName.trim() || !evidence.solverVersion.trim()) {
    throw new Error("RESULT_INVALID:missing solver identity/version");
  }
  if (evidence.solverId !== run.solverId) throw new Error("RESULT_INVALID:solver identity mismatch");
  if (evidence.runId !== run.runId) throw new Error("RESULT_INVALID:run id mismatch");
  if (!HEX64.test(evidence.inputHash)) throw new Error("RESULT_INVALID:input hash must be SHA-256");
  if (evidence.processState === "timeout") throw new Error("PROCESS_TIMEOUT:non-success process state");
  if (evidence.processState === "cancelled") throw new Error("PROCESS_CANCELLED:non-success process state");
  if (evidence.processState === "killed") throw new Error("PROCESS_RSS_LIMIT_EXCEEDED:non-success process state");
  if (evidence.processState === "start-failed") throw new Error("PROCESS_START_FAILED:non-success process state");
  if (evidence.processState !== "completed" || evidence.exitCode !== 0) {
    throw new Error("PROCESS_EXIT_NONZERO:non-success process state");
  }
  if (evidence.terminationReason && evidence.terminationReason.trim()) {
    throw new Error(`PROCESS_EXIT_NONZERO:termination reported:${evidence.terminationReason}`);
  }
  if (evidence.peakRssMiB !== undefined && (!Number.isFinite(evidence.peakRssMiB) || evidence.peakRssMiB < 0)) {
    throw new Error("RESULT_INVALID:invalid peak RSS");
  }
  if (!evidence.parserName.trim()) throw new Error("RESULT_INVALID:parser missing");
  if (evidence.parserStatus !== "ok") throw new Error("RESULT_INVALID:parser failed");
  if (!evidence.jobRoot.trim()) throw new Error("RESULT_INVALID:job root required");
  if (evidence.outputFiles.length === 0) throw new Error("RESULT_INVALID:no artifact evidence");
  for (const file of evidence.outputFiles) {
    if (!isContainedArtifactName(file.name) || !isPathContained(evidence.jobRoot, `${evidence.jobRoot}/${file.name}`)) {
      throw new Error(`RESULT_INVALID:artifact escapes job directory:${file.name}`);
    }
    if (!file.name || !HEX64.test(file.sha256) || !Number.isInteger(file.bytes) || file.bytes < 0) {
      throw new Error(`RESULT_INVALID:artifact evidence incomplete:${file.name}`);
    }
  }
  const expected = evidence.expectedArtifacts ?? participant.artifactOutputs;
  for (const name of expected) {
    if (!evidence.outputFiles.some((file) => file.name === name)) {
      throw new Error(`RESULT_INVALID:missing expected artifact:${name}`);
    }
  }
  if (evidence.executionMode === "subprocess") {
    if (!evidence.stdoutSha256 || !HEX64.test(evidence.stdoutSha256)) {
      throw new Error("RESULT_INVALID:subprocess evidence needs stdout hash");
    }
    if (!evidence.stderrSha256 || !HEX64.test(evidence.stderrSha256)) {
      throw new Error("RESULT_INVALID:subprocess evidence needs stderr hash");
    }
  }
  if (!HEX64.test(result.digestSha256)) throw new Error("RESULT_INVALID:artifact digest must be SHA-256");
  if (hasTraversalSegment(result.artifactUri)) {
    throw new Error("RESULT_INVALID:artifact escapes job directory:uri traversal");
  }
  const strippedUri = stripFileScheme(result.artifactUri);
  if (isAbsolutePath(strippedUri) && !isPathContained(evidence.jobRoot, strippedUri)) {
    throw new Error("RESULT_INVALID:artifact escapes job directory:uri outside job root");
  }
  const candidate = basenameOf(result.artifactUri);
  const matched = evidence.outputFiles.find((file) => file.name === candidate);
  if (!matched || matched.sha256 !== result.digestSha256) {
    throw new Error("RESULT_INVALID:artifact digest mismatch");
  }
  if (evidence.geometryHash !== undefined && !HEX64.test(evidence.geometryHash)) {
    throw new Error("RESULT_INVALID:geometry hash must be SHA-256");
  }
  if (evidence.meshHash !== undefined && !HEX64.test(evidence.meshHash)) {
    throw new Error("RESULT_INVALID:mesh hash must be SHA-256");
  }
  if (!evidence.validityPassed) throw new Error("RESULT_INVALID:validity did not pass");
  if (!evidence.fidelity.trim()) throw new Error("RESULT_INVALID:fidelity is required");
  for (const [name, value] of Object.entries(evidence.scalars)) {
    if (!Number.isFinite(value)) throw new Error(`RESULT_INVALID:non-finite scalar:${name}`);
  }
  const resultId = randomUUID();
  const provenanceId = randomUUID();
  provenance.append({ id: provenanceId, at: new Date().toISOString(), type: "result-recorded", detail: `${run.solverId}:${run.runId}:${resultId}` });
  return {
    source: "native_solver",
    resultId,
    fidelity: evidence.fidelity,
    units: { ...evidence.units },
    validity: { passed: true },
    inputHash: evidence.inputHash,
    solverIdentity: evidence.solverName,
    solverVersion: evidence.solverVersion,
    runId: run.runId,
    provenanceId,
    warnings: [...(evidence.warnings ?? [])],
    scalars: { ...evidence.scalars },
    artifacts: [...evidence.outputFiles],
  };
};
