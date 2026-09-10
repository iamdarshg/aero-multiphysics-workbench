import { createHash } from "node:crypto";

const SHA256 = /^[a-f0-9]{64}$/;

function canonicalize(value: unknown): unknown {
  if (typeof value === "number") {
    if (!Number.isFinite(value)) throw new TypeError("canonical content cannot contain non-finite numbers");
    return Object.is(value, -0) ? 0 : value;
  }
  if (Array.isArray(value)) return value.map(canonicalize);
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>)
        .filter(([, item]) => item !== undefined)
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([key, item]) => [key, canonicalize(item)]),
    );
  }
  return value;
}

export function canonicalJson(value: unknown): string {
  return JSON.stringify(canonicalize(value));
}

export function contentDigest(value: unknown): string {
  return createHash("sha256").update(canonicalJson(value)).digest("hex");
}

export interface ContentKeyInput {
  nodeType: string;
  geometryHash: string;
  semanticHash: string;
  materialHash: string;
  upstreamKeys: readonly string[];
  solver: { id: string; version: string };
  settings: Readonly<Record<string, unknown>>;
}

export function createContentKey(input: ContentKeyInput): string {
  for (const [name, digest] of [
    ["geometryHash", input.geometryHash],
    ["semanticHash", input.semanticHash],
    ["materialHash", input.materialHash],
    ...input.upstreamKeys.map((digest, index) => [`upstreamKeys[${index}]`, digest]),
  ]) {
    if (!SHA256.test(digest)) throw new TypeError(`${name} must be a SHA-256 digest`);
  }
  if (!input.nodeType.trim() || !input.solver.id.trim() || !input.solver.version.trim()) {
    throw new TypeError("node type and solver identity must be non-empty");
  }
  return contentDigest(input);
}

export class ContentAddressedCache<T> {
  readonly #entries = new Map<string, { canonical: string; value: T }>();

  put(key: string, value: T): void {
    if (!SHA256.test(key)) throw new TypeError("cache key must be a SHA-256 digest");
    const canonical = canonicalJson(value);
    const existing = this.#entries.get(key);
    if (existing && existing.canonical !== canonical) {
      throw new Error(`content-addressed cache entry ${key} is immutable`);
    }
    if (!existing) this.#entries.set(key, { canonical, value: structuredClone(value) });
  }

  get(key: string): T | undefined {
    const entry = this.#entries.get(key);
    return entry ? structuredClone(entry.value) : undefined;
  }
}
