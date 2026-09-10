import { contentDigest } from "../../cache/src/content-addressed.ts";

const SHA256 = /^[a-f0-9]{64}$/;
const ARTIFACT_FORMATS = new Set(["parquet", "vtk", "gltf", "step", "brep", "hdf5", "zarr"]);

export interface ArtifactReference {
  format: "parquet" | "vtk" | "gltf" | "step" | "brep" | "hdf5" | "zarr";
  uri: string;
  sha256: string;
  bytes: number;
}

export interface ProvenanceInput {
  eventType: string;
  subjectHash: string;
  actor: string;
  occurredAt: string;
  artifacts: readonly ArtifactReference[];
  details: Readonly<Record<string, unknown>>;
}

export interface ProvenanceEvent extends ProvenanceInput {
  sequence: number;
  previousEventHash: string | null;
  eventHash: string;
}

function freezeEvent(event: ProvenanceEvent): Readonly<ProvenanceEvent> {
  for (const artifact of event.artifacts) Object.freeze(artifact);
  Object.freeze(event.artifacts);
  Object.freeze(event.details);
  return Object.freeze(event);
}

export class ProvenanceLedger {
  readonly #events: Readonly<ProvenanceEvent>[] = [];

  list(): readonly Readonly<ProvenanceEvent>[] {
    return Object.freeze([...this.#events]);
  }

  append(input: ProvenanceInput): Readonly<ProvenanceEvent> {
    if (!input.eventType.trim() || !input.actor.trim()) throw new TypeError("provenance identity must be non-empty");
    if (!SHA256.test(input.subjectHash)) throw new TypeError("subjectHash must be a SHA-256 digest");
    if (Number.isNaN(Date.parse(input.occurredAt))) throw new TypeError("occurredAt must be an ISO timestamp");
    for (const artifact of input.artifacts) {
      if (!ARTIFACT_FORMATS.has(artifact.format)) throw new TypeError(`unsupported artifact format: ${artifact.format}`);
      if (!artifact.uri.trim() || !SHA256.test(artifact.sha256) || !Number.isSafeInteger(artifact.bytes) || artifact.bytes < 0) {
        throw new TypeError("artifact reference is invalid");
      }
    }
    const sequence = this.#events.length + 1;
    const previousEventHash = this.#events.at(-1)?.eventHash ?? null;
    const body = structuredClone({
      eventType: input.eventType,
      subjectHash: input.subjectHash,
      actor: input.actor,
      occurredAt: input.occurredAt,
      artifacts: input.artifacts,
      details: input.details,
      sequence,
      previousEventHash,
    });
    const event = freezeEvent({ ...body, eventHash: contentDigest(body) });
    this.#events.push(event);
    return event;
  }
}
