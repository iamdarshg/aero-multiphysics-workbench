import type { NormalizedQuantity } from "../../units/src/index.ts";
import { contentDigest } from "../../cache/src/content-addressed.ts";

const SHA256 = /^[a-f0-9]{64}$/;

function deepFreeze<T>(value: T): Readonly<T> {
  if (value && typeof value === "object" && !Object.isFrozen(value)) {
    for (const child of Object.values(value as Record<string, unknown>)) deepFreeze(child);
    Object.freeze(value);
  }
  return value;
}

export interface DesignRevision {
  designId: string;
  revisionId: string;
  parentRevisionHash: string | null;
  parameters: Readonly<Record<string, NormalizedQuantity>>;
  geometry: Readonly<{ digest: string; semanticDigest: string }>;
  materials: Readonly<{ digest: string }>;
  solverPolicy: Readonly<{ solver: string; version: string; settings: Readonly<Record<string, unknown>> }>;
  contentHash: string;
  changeRecord?: Readonly<{ author: string; reason: string; createdAt: string }>;
}

export function createDesignRevision(input: Omit<DesignRevision, "contentHash">): Readonly<DesignRevision> {
  if (!input.designId.trim() || !input.revisionId.trim()) throw new TypeError("design and revision ids must be non-empty");
  for (const [name, digest] of Object.entries({
    geometry: input.geometry.digest,
    semantics: input.geometry.semanticDigest,
    materials: input.materials.digest,
  })) {
    if (!SHA256.test(digest)) throw new TypeError(`${name} must be a SHA-256 digest`);
  }
  const parameters = Object.fromEntries(
    Object.entries(input.parameters).map(([name, quantity]) => [name, { ...quantity }]),
  );
  const physicalContent = {
    parameters: Object.fromEntries(
      Object.entries(parameters).map(([name, quantity]) => [name, {
        valueSI: quantity.valueSI,
        dimension: quantity.dimension,
        canonicalUnit: quantity.canonicalUnit,
      }]),
    ),
    geometry: input.geometry,
    materials: input.materials,
    solverPolicy: input.solverPolicy,
  };
  return deepFreeze({
    ...structuredClone(input),
    parameters,
    contentHash: contentDigest(physicalContent),
  }) as Readonly<DesignRevision>;
}

export function createVariantRevision(
  parent: DesignRevision,
  change: {
    revisionId: string;
    parameterChanges: Record<string, NormalizedQuantity>;
    author: string;
    reason: string;
    createdAt: string;
  },
): Readonly<DesignRevision> {
  if (!change.author.trim() || !change.reason.trim() || Number.isNaN(Date.parse(change.createdAt))) {
    throw new TypeError("variant changes require an author, reason, and ISO timestamp");
  }
  for (const [name, quantity] of Object.entries(change.parameterChanges)) {
    const current = parent.parameters[name];
    if (!current) throw new RangeError(`unknown parameter: ${name}`);
    if (current.dimension !== quantity.dimension) throw new TypeError(`parameter ${name} cannot change dimension`);
  }
  return createDesignRevision({
    designId: parent.designId,
    revisionId: change.revisionId,
    parentRevisionHash: parent.contentHash,
    parameters: { ...parent.parameters, ...change.parameterChanges },
    geometry: parent.geometry,
    materials: parent.materials,
    solverPolicy: parent.solverPolicy,
    changeRecord: { author: change.author, reason: change.reason, createdAt: change.createdAt },
  });
}
