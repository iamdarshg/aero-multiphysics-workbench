import { randomUUID } from "node:crypto";
import { spawn } from "node:child_process";
import { CAPABILITY_MANIFESTS } from "./manifests.ts";
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

  recordResult(_run: RunRecord, _result: { artifactUri: string; digestSha256: string }): ResultRecord {
    // Native completion receipts, parser receipts, artifact-root checks, and
    // solver/input lineage are not wired yet. Never publish a fabricated result.
    throw new Error("NATIVE_RESULT_PUBLICATION_UNVERIFIED");
  }
}
