/**
 * Persistent, content-addressed node cache with verification, bounded
 * eviction, upstream invalidation, and trust-preserving native reuse.
 *
 * Values are small engineering records (scalars, receipts, artifact
 * references); large artifacts stay in content-addressed blob storage and are
 * referenced here only by uri + digest. Every value is written through a
 * temporary file and an atomic rename, and every read re-derives the value
 * digest so a corrupted or tampered entry fails closed instead of
 * masquerading as a hit. Entries are immutable: a key with a different value
 * is rejected rather than overwritten.
 */

import { existsSync, mkdirSync, readFileSync, readdirSync, renameSync, rmSync, statSync, writeFileSync } from "node:fs";
import { join } from "node:path";

import { canonicalJson, contentDigest } from "./content-addressed.ts";

const SHA256 = /^[a-f0-9]{64}$/;
const DEFAULT_MAX_BYTES = 64 * 1024 * 1024;
let temporaryCounter = 0;

export class CacheIntegrityError extends Error {
  readonly key: string;

  constructor(key: string, message: string) {
    super(message);
    this.name = "CacheIntegrityError";
    this.key = key;
  }
}

export class CacheImmutabilityError extends Error {
  readonly key: string;

  constructor(key: string, message: string) {
    super(message);
    this.name = "CacheImmutabilityError";
    this.key = key;
  }
}

export class CacheReuseError extends Error {
  readonly key: string;
  readonly reason: string;

  constructor(reason: string, key: string, message: string) {
    super(message);
    this.name = "CacheReuseError";
    this.key = key;
    this.reason = reason;
  }
}

export interface CacheArtifactRef {
  readonly uri: string;
  readonly sha256: string;
  readonly bytes: number;
}

export interface CacheEntryInput {
  readonly nodeType: string;
  readonly family: string;
  readonly upstreamKeys?: readonly string[];
  readonly solver?: { readonly id: string; readonly version: string };
  readonly participant?: string;
  readonly source?: string;
  readonly validityPolicyVersion?: string;
  readonly artifacts?: readonly CacheArtifactRef[];
  readonly pinned?: boolean;
}

export interface CacheEntryMetadata {
  readonly key: string;
  readonly nodeType: string;
  readonly family: string;
  readonly upstreamKeys: readonly string[];
  readonly solver: { readonly id: string; readonly version: string } | null;
  readonly participant: string | null;
  readonly source: string;
  readonly validityPolicyVersion: string | null;
  readonly artifacts: readonly CacheArtifactRef[];
  readonly valueDigest: string;
  readonly valueBytes: number;
  readonly pinned: boolean;
  readonly createdAt: string;
  readonly lastAccessedAt: string;
}

export interface TrustedReuseRequest {
  readonly solverId: string;
  readonly solverVersion: string;
  readonly validityPolicyVersion: string;
  readonly source?: string;
  /** Returns the on-disk sha256 for a referenced artifact, or undefined when missing. */
  readonly resolveArtifact?: (ref: CacheArtifactRef) => string | undefined;
}

export interface TrustedReuse {
  readonly key: string;
  readonly valueDigest: string;
  readonly value: unknown;
}

export interface PersistentCacheOptions {
  readonly root: string;
  readonly maxBytes?: number;
  readonly now?: () => Date;
}

interface StoredRecord<T> extends CacheEntryMetadata {
  readonly value: T;
}

export class PersistentContentAddressedCache<T> {
  readonly #root: string;
  readonly #values: string;
  readonly #maxBytes: number;
  readonly #now: () => Date;
  readonly #inFlight = new Map<string, Promise<unknown>>();

  constructor(options: PersistentCacheOptions) {
    if (!options.root.trim()) throw new TypeError("cache root must be non-empty");
    if (options.maxBytes !== undefined && (!Number.isSafeInteger(options.maxBytes) || options.maxBytes <= 0)) {
      throw new TypeError("cache maxBytes must be a positive safe integer");
    }
    this.#root = options.root;
    this.#values = join(options.root, "values");
    this.#maxBytes = options.maxBytes ?? DEFAULT_MAX_BYTES;
    this.#now = options.now ?? (() => new Date());
    mkdirSync(this.#values, { recursive: true });
  }

  get sizeBytes(): number {
    return this.#diskBytes();
  }

  keys(): string[] {
    return readdirSync(this.#values)
      .filter((name) => name.endsWith(".json") && SHA256.test(name.slice(0, -5)))
      .map((name) => name.slice(0, -5))
      .sort();
  }

  describe(key: string): CacheEntryMetadata | undefined {
    const record = this.#read(key);
    if (!record) return undefined;
    const { value: _value, ...metadata } = record;
    void _value;
    return metadata;
  }

  get(key: string): T | undefined {
    const record = this.#read(key);
    if (!record) return undefined;
    this.#touch(key, record.lastAccessedAt);
    return structuredClone(record.value);
  }

  put(key: string, value: T, meta: CacheEntryInput): void {
    this.#assertKey(key);
    this.#assertMeta(meta);
    const valueDigest = contentDigest(value);
    const existing = this.#read(key);
    if (existing) {
      if (existing.valueDigest !== valueDigest) {
        throw new CacheImmutabilityError(key, `content-addressed cache entry ${key} is immutable`);
      }
      return;
    }
    const canonical = canonicalJson(value);
    if (typeof canonical !== "string") throw new TypeError("cache values must be JSON-serializable");
    const timestamp = this.#now().toISOString();
    const record: StoredRecord<T> = {
      key,
      nodeType: meta.nodeType,
      family: meta.family,
      upstreamKeys: [...(meta.upstreamKeys ?? [])],
      solver: meta.solver ? { id: meta.solver.id, version: meta.solver.version } : null,
      participant: meta.participant ?? null,
      source: meta.source ?? "analytical",
      validityPolicyVersion: meta.validityPolicyVersion ?? null,
      artifacts: (meta.artifacts ?? []).map((artifact) => ({ ...artifact })),
      valueDigest,
      valueBytes: Buffer.byteLength(canonical, "utf8"),
      pinned: meta.pinned ?? false,
      createdAt: timestamp,
      lastAccessedAt: timestamp,
      value: structuredClone(value),
    };
    this.#write(record);
    if (this.#diskBytes() > this.#maxBytes) this.evict();
  }

  async getOrCompute(
    key: string,
    meta: CacheEntryInput,
    compute: () => T | Promise<T>,
  ): Promise<T> {
    const shared = this.#inFlight.get(key);
    if (shared) return shared as Promise<T>;
    const pending = (async (): Promise<T> => {
      const hit = this.get(key);
      if (hit !== undefined) return hit;
      const value = await compute();
      this.put(key, value, meta);
      return value;
    })();
    this.#inFlight.set(key, pending);
    const release = () => {
      if (this.#inFlight.get(key) === pending) this.#inFlight.delete(key);
    };
    void pending.then(release, release);
    return pending;
  }

  pin(key: string, pinned = true): void {
    const record = this.#read(key);
    if (!record) throw new CacheIntegrityError(key, `cannot pin missing cache entry ${key}`);
    this.#write({ ...record, pinned });
  }

  /** Drop the key together with every entry that depends on it. */
  invalidate(key: string): string[] {
    this.#assertKey(key);
    const dropped: string[] = [];
    for (const candidate of this.#rawRecords()) {
      if (candidate.key === key || candidate.upstreamKeys.includes(key)) {
        this.#remove(candidate.key);
        dropped.push(candidate.key);
      }
    }
    return dropped.sort();
  }

  /** Drop every entry of one node family (design-section invalidation). */
  invalidateFamily(family: string): string[] {
    if (!family.trim()) throw new TypeError("family must be non-empty");
    const dropped: string[] = [];
    for (const candidate of this.#rawRecords()) {
      if (candidate.family === family) {
        this.#remove(candidate.key);
        dropped.push(candidate.key);
      }
    }
    return dropped.sort();
  }

  evict(): string[] {
    const candidates = this.#rawRecords().sort((left, right) =>
      left.lastAccessedAt.localeCompare(right.lastAccessedAt) || left.key.localeCompare(right.key),
    );
    let total = this.#diskBytes();
    const evicted: string[] = [];
    for (const candidate of candidates) {
      if (total <= this.#maxBytes) break;
      if (candidate.pinned) continue;
      const bytes = candidate.diskBytes;
      this.#remove(candidate.key);
      total -= bytes;
      evicted.push(candidate.key);
    }
    return evicted;
  }

  /**
   * Prove that a cached native result may be reused, or fail closed.
   *
   * The stored value is never relabeled: source, solver identity, fidelity,
   * and validity policy must match the request, and every referenced artifact
   * must still exist with its recorded digest.
   */
  reuseIfTrusted(key: string, request: TrustedReuseRequest): TrustedReuse {
    const record = this.#read(key);
    if (!record) throw new CacheReuseError("MISS", key, `no cache entry for ${key}`);
    if (!record.solver || record.solver.id !== request.solverId || record.solver.version !== request.solverVersion) {
      throw new CacheReuseError(
        "SOLVER_IDENTITY_MISMATCH",
        key,
        `cached solver ${record.solver?.id ?? "unknown"}@${record.solver?.version ?? "unknown"} is not ${request.solverId}@${request.solverVersion}`,
      );
    }
    if (record.validityPolicyVersion !== request.validityPolicyVersion) {
      throw new CacheReuseError(
        "VALIDITY_POLICY_MISMATCH",
        key,
        `cached validity policy ${record.validityPolicyVersion ?? "none"} is not ${request.validityPolicyVersion}`,
      );
    }
    if (request.source !== undefined && record.source !== request.source) {
      throw new CacheReuseError(
        "SOURCE_MISMATCH",
        key,
        `cached source ${record.source} cannot be relabeled as ${request.source}`,
      );
    }
    if (request.resolveArtifact) {
      for (const artifact of record.artifacts) {
        const actual = request.resolveArtifact(artifact);
        if (actual === undefined) {
          throw new CacheReuseError("ARTIFACT_MISSING", key, `artifact ${artifact.uri} is unavailable`);
        }
        if (actual !== artifact.sha256) {
          throw new CacheReuseError(
            "ARTIFACT_DIGEST_MISMATCH",
            key,
            `artifact ${artifact.uri} digest ${actual} does not match ${artifact.sha256}`,
          );
        }
      }
    }
    this.#touch(key, record.lastAccessedAt);
    return { key, valueDigest: record.valueDigest, value: structuredClone(record.value) };
  }

  #assertKey(key: string): void {
    if (!SHA256.test(key)) throw new TypeError("cache key must be a SHA-256 digest");
  }

  #assertMeta(meta: CacheEntryInput): void {
    if (!meta.nodeType.trim() || !meta.family.trim()) {
      throw new TypeError("cache entries need a node type and family");
    }
    if (meta.solver && (!meta.solver.id.trim() || !meta.solver.version.trim())) {
      throw new TypeError("cache solver identity must be non-empty");
    }
    for (const upstream of meta.upstreamKeys ?? []) {
      if (!SHA256.test(upstream)) throw new TypeError("upstream keys must be SHA-256 digests");
    }
    for (const artifact of meta.artifacts ?? []) {
      if (!artifact.uri.trim() || !SHA256.test(artifact.sha256) || !Number.isSafeInteger(artifact.bytes) || artifact.bytes < 0) {
        throw new TypeError("cache artifact reference is invalid");
      }
    }
  }

  #path(key: string): string {
    return join(this.#values, `${key}.json`);
  }

  #read(key: string): StoredRecord<T> | undefined {
    this.#assertKey(key);
    const file = this.#path(key);
    if (!existsSync(file)) return undefined;
    let parsed: unknown;
    try {
      parsed = JSON.parse(readFileSync(file, "utf8"));
    } catch (error) {
      throw new CacheIntegrityError(key, `cache entry ${key} is unreadable: ${(error as Error).message}`);
    }
    if (!parsed || typeof parsed !== "object" || (parsed as StoredRecord<T>).key !== key) {
      throw new CacheIntegrityError(key, `cache entry ${key} is malformed`);
    }
    const record = parsed as StoredRecord<T>;
    const actual = contentDigest(record.value);
    if (actual !== record.valueDigest) {
      throw new CacheIntegrityError(
        key,
        `cache entry ${key} failed digest verification: expected ${record.valueDigest}, computed ${actual}`,
      );
    }
    return record;
  }

  #write(record: StoredRecord<T>): void {
    const file = this.#path(record.key);
    const temporary = `${file}.${process.pid}.${(temporaryCounter++).toString(36)}.tmp`;
    writeFileSync(temporary, canonicalJson(record), "utf8");
    try {
      renameSync(temporary, file);
    } catch (error) {
      rmSync(temporary, { force: true });
      throw error;
    }
  }

  #remove(key: string): void {
    rmSync(this.#path(key), { force: true });
  }

  #touch(key: string, previous: string): void {
    const timestamp = this.#now().toISOString();
    if (timestamp === previous) return;
    const record = this.#read(key);
    if (!record) return;
    this.#write({ ...record, lastAccessedAt: timestamp });
  }

  #rawRecords(): Array<CacheEntryMetadata & { readonly diskBytes: number }> {
    const records: Array<CacheEntryMetadata & { readonly diskBytes: number }> = [];
    for (const key of this.keys()) {
      try {
        const record = this.#read(key);
        if (!record) continue;
        const { value: _value, ...metadata } = record;
        void _value;
        records.push({ ...metadata, diskBytes: statSync(this.#path(key)).size });
      } catch (error) {
        if (error instanceof CacheIntegrityError) {
          records.push({
            key,
            nodeType: "corrupt",
            family: "corrupt",
            upstreamKeys: [],
            solver: null,
            participant: null,
            source: "corrupt",
            validityPolicyVersion: null,
            artifacts: [],
            valueDigest: "",
            valueBytes: 0,
            pinned: false,
            createdAt: "",
            lastAccessedAt: "",
            diskBytes: statSync(this.#path(key)).size,
          });
          continue;
        }
        throw error;
      }
    }
    return records;
  }

  #diskBytes(): number {
    let total = 0;
    for (const key of this.keys()) {
      total += statSync(this.#path(key)).size;
    }
    return total;
  }
}
