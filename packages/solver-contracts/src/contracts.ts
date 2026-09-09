/** Public, side-effect-free contracts shared by scheduler, solver workers, and MCP. */
export type SolverId =
  | "openfoam" | "code-aster" | "precice" | "ross" | "pybamm" | "elmer"
  | "cantera" | "pycycle" | "cadquery" | "gmsh" | "openvsp" | "freecad";

export type ResultKind = "fields" | "scalars" | "geometry" | "mesh" | "coupling" | "report";
export type CapabilityState = "ready" | "unavailable";

export interface SolverManifest {
  readonly id: SolverId;
  readonly displayName: string;
  readonly category: "solver" | "coupling" | "geometry";
  readonly versionProbe: { readonly command: readonly string[] };
  readonly allowedExecutables: readonly string[];
  readonly resultKinds: readonly ResultKind[];
  readonly execution: { readonly trustModel: "native-only"; readonly checkpoint: boolean };
}

export interface Capability {
  readonly available: boolean;
  readonly detail: string;
  readonly version?: string;
  readonly checkedAt?: string;
}

export interface CapabilityReport {
  readonly checkedAt: string;
  readonly ready: readonly (Capability & { readonly id: SolverId })[];
  readonly unavailable: readonly (Capability & { readonly id: SolverId })[];
}

export interface LaunchRequest {
  readonly solverId: SolverId;
  readonly designId: string;
  /** A complete command is retained for compatibility, but is validated against the manifest. */
  readonly command: readonly string[];
  readonly requestedMemoryMiB: number;
  readonly checkpointFrom?: string;
}

export interface RunRecord {
  readonly runId: string;
  readonly solverId: SolverId;
  readonly designId: string;
  readonly state: "accepted" | "rejected" | "completed" | "failed";
  readonly source: "native-solver";
  readonly checkpointFrom?: string;
  readonly provenanceId: string;
}

export interface ResultRecord {
  readonly resultId: string;
  readonly runId: string;
  readonly solverId: SolverId;
  readonly source: "native-solver";
  readonly artifactUri: string;
  readonly digestSha256: string;
  readonly checkpointFrom?: string;
  readonly provenanceId: string;
}

export interface ProvenanceEvent {
  readonly id: string;
  readonly at: string;
  readonly type: "launch-accepted" | "launch-rejected" | "result-recorded";
  readonly detail: string;
}

export interface JobRequest {
  readonly id: string;
  readonly requestedMemoryMiB: number;
  readonly remote: boolean;
  readonly costCeilingUsd: number;
  readonly ownerId?: string;
}

export interface ScheduledJob extends JobRequest {
  readonly state: "queued";
}

export interface LocalProcessResult {
  readonly state: "completed" | "failed";
  readonly exitCode: number | null;
  readonly peakRssMiB: number;
  readonly reason?:
    | "PROCESS_RSS_LIMIT_EXCEEDED"
    | "RSS_MONITOR_UNAVAILABLE"
    | "PROCESS_EXIT_NONZERO"
    | "PROCESS_TIMEOUT"
    | "PROCESS_CANCELLED"
    | "PROCESS_START_FAILED";
}
