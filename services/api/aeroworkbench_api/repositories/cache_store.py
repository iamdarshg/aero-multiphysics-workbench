"""Persistent content-addressed result cache: SQLite metadata + file values.

The database stores references and metadata only; resolved values live as
content-addressed JSON files. Every read re-derives the value digest so a
corrupted or tampered entry fails closed instead of being served as a hit.
Writes are atomic (temp file + ``os.replace``) and bounded by an LRU byte
budget with pinning for referenced/final results. Invalidating a changed
upstream drops only that key and its declared descendants. Native reuse
requires matching solver identity, validity policy, source, and verifiable
artifact digests, and is recorded as a cache-reuse event rather than relabeled
as a fresh computation.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import threading
import uuid
from collections.abc import Callable
from copy import deepcopy
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

HEX64 = re.compile(r"^[0-9a-f]{64}$")
DEFAULT_MAX_BYTES = 64 * 1024 * 1024


def _canonical(value: Any) -> Any:
    """Canonicalize like the TypeScript cache: sort keys, normalize negative zero."""

    if isinstance(value, bool):
        return value
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            raise ValueError("cache value contains a non-finite number")
        return 0.0 if value == 0 else value
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    if isinstance(value, dict):
        return {key: _canonical(value[key]) for key in sorted(value)}
    return value


def _canonical_json(value: Any) -> str:
    return json.dumps(_canonical(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def content_digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def cache_key(
    *,
    node_type: str,
    geometry_hash: str,
    semantic_hash: str,
    material_hash: str,
    solver: tuple[str, str],
    settings: dict[str, Any],
    upstream_keys: tuple[str, ...] = (),
    input_digest: str | None = None,
    mesh_hash: str | None = None,
    participant: str | None = None,
    fidelity: str | None = None,
    validity_policy_version: str | None = None,
) -> str:
    """One canonical cache key covering every axis that can change a result.

    Optional axes are omitted when unset, mirroring the TypeScript contract;
    any applicable change (geometry/semantic/mesh/material, participant and
    solver identity, settings, upstream hashes, fidelity, validity policy)
    produces a different key, so a hit never crosses an incompatible boundary.
    """

    for name, value in (
        ("geometryHash", geometry_hash),
        ("semanticHash", semantic_hash),
        ("materialHash", material_hash),
        ("inputDigest", input_digest),
        ("meshHash", mesh_hash),
    ):
        if value is not None and not HEX64.fullmatch(value):
            raise ValueError(f"{name} must be a SHA-256 digest")
    for index, upstream in enumerate(upstream_keys):
        if not HEX64.fullmatch(upstream):
            raise ValueError(f"upstreamKeys[{index}] must be a SHA-256 digest")
    if not node_type.strip() or not solver[0].strip() or not solver[1].strip():
        raise ValueError("node type and solver identity must be non-empty")
    for name, value in (
        ("participant", participant),
        ("fidelity", fidelity),
        ("validityPolicyVersion", validity_policy_version),
    ):
        if value is not None and not value.strip():
            raise ValueError(f"{name} must be non-empty when provided")
    payload: dict[str, Any] = {
        "nodeType": node_type,
        "inputDigest": input_digest,
        "geometryHash": geometry_hash,
        "semanticHash": semantic_hash,
        "meshHash": mesh_hash,
        "materialHash": material_hash,
        "participant": participant,
        "solver": {"id": solver[0], "version": solver[1]},
        "settings": settings,
        "upstreamKeys": list(upstream_keys),
        "fidelity": fidelity,
        "validityPolicyVersion": validity_policy_version,
    }
    return content_digest({name: value for name, value in payload.items() if value is not None})


class CacheIntegrityError(RuntimeError):
    """Raised when a stored entry is missing, unreadable, or digest-mismatched."""


class CacheImmutabilityError(ValueError):
    """Raised when a key would be overwritten with different content."""


class CacheReuseError(RuntimeError):
    """Raised when a cached result cannot be trusted for the requested reuse."""

    def __init__(self, reason: str, key: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason
        self.key = key


@dataclass(frozen=True, slots=True)
class CacheArtifactRef:
    uri: str
    sha256: str
    bytes: int

    def __post_init__(self) -> None:
        if not self.uri.strip():
            raise ValueError("artifact uri must be non-empty")
        if not HEX64.fullmatch(self.sha256):
            raise ValueError("artifact sha256 must be a SHA-256 digest")
        if self.bytes < 0:
            raise ValueError("artifact bytes must be non-negative")


@dataclass(frozen=True, slots=True)
class CacheEntryMetadata:
    key: str
    node_type: str
    family: str
    upstream_keys: tuple[str, ...]
    solver_id: str | None
    solver_version: str | None
    participant: str | None
    source: str
    validity_policy_version: str | None
    artifacts: tuple[CacheArtifactRef, ...]
    value_digest: str
    value_bytes: int
    pinned: bool
    created_at: str
    last_accessed_at: str


class PersistentResultCache:
    """Thread-safe persistent cache; values stay content-addressed on disk."""

    def __init__(
        self,
        root: str | Path,
        *,
        max_bytes: int = DEFAULT_MAX_BYTES,
        now: Callable[[], str] | None = None,
    ) -> None:
        if max_bytes <= 0:
            raise ValueError("max_bytes must be positive")
        self.root = Path(root)
        self.values = self.root / "values"
        self.values.mkdir(parents=True, exist_ok=True)
        self._max_bytes = int(max_bytes)
        self._now = now or (lambda: datetime.now(UTC).isoformat())
        self._connection = sqlite3.connect(self.root / "cache.sqlite3", check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._lock = threading.Lock()
        self._key_locks: dict[str, threading.Lock] = {}
        self._migrate()

    # -- schema ----------------------------------------------------------

    def _migrate(self) -> None:
        with self._lock:
            self._connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS result_cache (
                  key TEXT PRIMARY KEY,
                  node_type TEXT NOT NULL,
                  family TEXT NOT NULL,
                  upstream_keys TEXT NOT NULL,
                  solver_id TEXT,
                  solver_version TEXT,
                  participant TEXT,
                  source TEXT NOT NULL,
                  validity_policy_version TEXT,
                  artifacts TEXT NOT NULL,
                  value_digest TEXT NOT NULL,
                  value_bytes INTEGER NOT NULL,
                  pinned INTEGER NOT NULL DEFAULT 0,
                  created_at TEXT NOT NULL,
                  last_accessed_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS result_cache_family ON result_cache(family);
                CREATE TABLE IF NOT EXISTS cache_events (
                  sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                  event_type TEXT NOT NULL,
                  key TEXT NOT NULL,
                  detail TEXT NOT NULL,
                  occurred_at TEXT NOT NULL
                );
                """
            )
            self._connection.commit()

    # -- writes ----------------------------------------------------------

    def put(
        self,
        key: str,
        value: Any,
        *,
        node_type: str,
        family: str,
        upstream_keys: tuple[str, ...] = (),
        solver: tuple[str, str] | None = None,
        participant: str | None = None,
        source: str = "analytical",
        validity_policy_version: str | None = None,
        artifacts: tuple[CacheArtifactRef, ...] = (),
        pinned: bool = False,
    ) -> None:
        self._assert_key(key)
        if not node_type.strip() or not family.strip():
            raise ValueError("cache entries need a node type and family")
        if solver is not None and (not solver[0].strip() or not solver[1].strip()):
            raise ValueError("cache solver identity must be non-empty")
        for upstream in upstream_keys:
            if not HEX64.fullmatch(upstream):
                raise ValueError("upstream keys must be SHA-256 digests")
        refs = tuple(
            item if isinstance(item, CacheArtifactRef) else CacheArtifactRef(**item)
            for item in artifacts
        )
        try:
            value_digest = content_digest(value)
            value_bytes = len(_canonical_json(value).encode("utf-8"))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"cache value is not canonicalizable: {exc}") from exc
        with self._lock:
            existing = self._get_row(key)
            if existing is not None:
                if existing["value_digest"] != value_digest:
                    raise CacheImmutabilityError(
                        f"content-addressed cache entry {key} is immutable"
                    )
                return
            self._write_value(key, value)
            timestamp = self._now()
            try:
                self._connection.execute(
                    "INSERT INTO result_cache(key,node_type,family,upstream_keys,solver_id,"
                    "solver_version,participant,source,validity_policy_version,artifacts,"
                    "value_digest,value_bytes,pinned,created_at,last_accessed_at) "
                    "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        key,
                        node_type,
                        family,
                        _canonical_json(list(upstream_keys)),
                        solver[0] if solver else None,
                        solver[1] if solver else None,
                        participant,
                        source,
                        validity_policy_version,
                        _canonical_json([asdict(item) for item in refs]),
                        value_digest,
                        value_bytes,
                        1 if pinned else 0,
                        timestamp,
                        timestamp,
                    ),
                )
                self._connection.commit()
            except Exception:
                self._connection.rollback()
                (self.values / f"{key}.json").unlink(missing_ok=True)
                raise
        if self._disk_bytes() > self._max_bytes:
            self.evict()

    def compute_if_absent(self, key: str, factory: Callable[[], Any], **meta: Any) -> Any:
        """One in-flight computation per key across concurrent callers."""

        lock = self._key_lock(key)
        with lock:
            loaded = self._load(key)
            if loaded is not None:
                return deepcopy(loaded[1])
            value = factory()
            self.put(key, value, **meta)
            return deepcopy(value)

    def pin(self, key: str, pinned: bool = True) -> None:
        with self._lock:
            if self._get_row(key) is None:
                raise CacheIntegrityError(f"cannot pin missing cache entry {key}")
            self._connection.execute(
                "UPDATE result_cache SET pinned=? WHERE key=?", (1 if pinned else 0, key)
            )
            self._connection.commit()

    # -- reads -----------------------------------------------------------

    def get(self, key: str) -> Any | None:
        loaded = self._load(key)
        if loaded is None:
            return None
        self._touch(key)
        return deepcopy(loaded[1])

    def describe(self, key: str) -> CacheEntryMetadata | None:
        if not HEX64.fullmatch(key):
            raise ValueError("cache key must be a SHA-256 digest")
        with self._lock:
            row = self._get_row(key)
            if row is None:
                return None
            return self._row_metadata(row)

    def keys(self) -> list[str]:
        with self._lock:
            rows = self._connection.execute("SELECT key FROM result_cache").fetchall()
        return sorted(str(row["key"]) for row in rows)

    @property
    def size_bytes(self) -> int:
        return self._disk_bytes()

    # -- invalidation and eviction --------------------------------------

    def invalidate(self, key: str) -> list[str]:
        """Drop the changed key and every entry that declares it upstream."""

        self._assert_key(key)
        dropped: list[str] = []
        with self._lock:
            rows = self._connection.execute(
                "SELECT key, upstream_keys FROM result_cache"
            ).fetchall()
            for row in rows:
                upstream = json.loads(row["upstream_keys"])
                if row["key"] == key or key in upstream:
                    dropped.append(str(row["key"]))
            for dropped_key in dropped:
                self._delete_locked(dropped_key)
            self._connection.commit()
        for dropped_key in dropped:
            self._record_event("cache.invalidate", dropped_key, f"invalidated by {key}")
        return sorted(dropped)

    def invalidate_family(self, family: str) -> list[str]:
        if not family.strip():
            raise ValueError("family must be non-empty")
        with self._lock:
            rows = self._connection.execute(
                "SELECT key FROM result_cache WHERE family=?", (family,)
            ).fetchall()
            dropped = [str(row["key"]) for row in rows]
            for dropped_key in dropped:
                self._delete_locked(dropped_key)
            self._connection.commit()
        for dropped_key in dropped:
            self._record_event("cache.invalidate", dropped_key, f"invalidated family {family}")
        return sorted(dropped)

    def evict(self) -> list[str]:
        evicted: list[str] = []
        with self._lock:
            rows = self._connection.execute(
                "SELECT key, pinned FROM result_cache ORDER BY last_accessed_at, key"
            ).fetchall()
            total = self._disk_bytes()
            for row in rows:
                if total <= self._max_bytes:
                    break
                if row["pinned"]:
                    continue
                size = self._value_size(str(row["key"]))
                self._delete_locked(str(row["key"]))
                total -= size
                evicted.append(str(row["key"]))
            self._connection.commit()
        for evicted_key in evicted:
            self._record_event("cache.evict", evicted_key, "evicted under size budget")
        return evicted

    # -- trusted native reuse -------------------------------------------

    def reuse_if_trusted(
        self,
        key: str,
        *,
        solver_id: str,
        solver_version: str,
        validity_policy_version: str,
        source: str | None = None,
        resolve_artifact: Callable[[CacheArtifactRef], str | None] | None = None,
    ) -> tuple[Any, dict[str, Any]]:
        """Prove a cached native result is reusable, or fail closed.

        The stored value is never relabeled: solver identity, validity policy,
        source, and every referenced artifact digest must match the request.
        The accepted reuse is recorded as a provenance event.
        """

        meta = self.describe(key)
        if meta is None:
            raise CacheReuseError("MISS", key, f"no cache entry for {key}")
        if meta.solver_id != solver_id or meta.solver_version != solver_version:
            raise CacheReuseError(
                "SOLVER_IDENTITY_MISMATCH",
                key,
                f"cached {meta.solver_id}@{meta.solver_version} is not "
                f"{solver_id}@{solver_version}",
            )
        if meta.validity_policy_version != validity_policy_version:
            raise CacheReuseError(
                "VALIDITY_POLICY_MISMATCH",
                key,
                f"cached validity policy {meta.validity_policy_version} is not "
                f"{validity_policy_version}",
            )
        if source is not None and meta.source != source:
            raise CacheReuseError(
                "SOURCE_MISMATCH",
                key,
                f"cached source {meta.source} cannot be relabeled as {source}",
            )
        if resolve_artifact is not None:
            for ref in meta.artifacts:
                actual = resolve_artifact(ref)
                if actual is None:
                    raise CacheReuseError(
                        "ARTIFACT_MISSING", key, f"artifact {ref.uri} is unavailable"
                    )
                if actual != ref.sha256:
                    raise CacheReuseError(
                        "ARTIFACT_DIGEST_MISMATCH",
                        key,
                        f"artifact {ref.uri} digest {actual} does not match {ref.sha256}",
                    )
        loaded = self._load(key)
        if loaded is None:
            raise CacheReuseError("MISS", key, f"no cache entry for {key}")
        self._touch(key)
        detail = {
            "solver_id": solver_id,
            "solver_version": solver_version,
            "validity_policy_version": validity_policy_version,
            "source": meta.source,
            "value_digest": meta.value_digest,
        }
        sequence = self._record_event("cache.reuse", key, json.dumps(detail, sort_keys=True))
        return deepcopy(loaded[1]), {"sequence": sequence, "event_type": "cache.reuse", **detail}

    # -- events ----------------------------------------------------------

    def events(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT sequence,event_type,key,detail,occurred_at FROM cache_events "
                "ORDER BY sequence"
            ).fetchall()
        return [
            {
                "sequence": row["sequence"],
                "event_type": row["event_type"],
                "key": row["key"],
                "detail": json.loads(row["detail"]),
                "occurred_at": row["occurred_at"],
            }
            for row in rows
        ]

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    # -- internals -------------------------------------------------------

    def _assert_key(self, key: str) -> None:
        if not HEX64.fullmatch(key):
            raise ValueError("cache key must be a SHA-256 digest")

    def _get_row(self, key: str) -> sqlite3.Row | None:
        row = self._connection.execute(
            "SELECT * FROM result_cache WHERE key=?", (key,)
        ).fetchone()
        return cast("sqlite3.Row | None", row)

    def _row_metadata(self, row: sqlite3.Row) -> CacheEntryMetadata:
        artifacts = tuple(
            CacheArtifactRef(**item) for item in json.loads(row["artifacts"])
        )
        return CacheEntryMetadata(
            key=str(row["key"]),
            node_type=str(row["node_type"]),
            family=str(row["family"]),
            upstream_keys=tuple(str(item) for item in json.loads(row["upstream_keys"])),
            solver_id=row["solver_id"],
            solver_version=row["solver_version"],
            participant=row["participant"],
            source=str(row["source"]),
            validity_policy_version=row["validity_policy_version"],
            artifacts=artifacts,
            value_digest=str(row["value_digest"]),
            value_bytes=int(row["value_bytes"]),
            pinned=bool(row["pinned"]),
            created_at=str(row["created_at"]),
            last_accessed_at=str(row["last_accessed_at"]),
        )

    def _load(self, key: str) -> tuple[CacheEntryMetadata, Any] | None:
        meta = self.describe(key)
        if meta is None:
            return None
        target = self.values / f"{key}.json"
        if not target.is_file():
            raise CacheIntegrityError(
                f"cache entry {key} has metadata but its value file is missing"
            )
        try:
            raw = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise CacheIntegrityError(f"cache entry {key} is unreadable: {exc}") from exc
        if content_digest(raw) != meta.value_digest:
            raise CacheIntegrityError(f"cache entry {key} failed digest verification")
        return meta, raw

    def _write_value(self, key: str, value: Any) -> int:
        data = _canonical_json(value).encode("utf-8")
        target = self.values / f"{key}.json"
        temporary = self.values / f"{key}.{os.getpid()}.{uuid.uuid4().hex}.tmp"
        try:
            with temporary.open("wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
        return len(data)

    def _delete_locked(self, key: str) -> None:
        self._connection.execute("DELETE FROM result_cache WHERE key=?", (key,))
        (self.values / f"{key}.json").unlink(missing_ok=True)

    def _touch(self, key: str) -> None:
        with self._lock:
            self._connection.execute(
                "UPDATE result_cache SET last_accessed_at=? WHERE key=?",
                (self._now(), key),
            )
            self._connection.commit()

    def _record_event(self, event_type: str, key: str, detail: str) -> int:
        with self._lock:
            cursor = self._connection.execute(
                "INSERT INTO cache_events(event_type,key,detail,occurred_at) VALUES(?,?,?,?)",
                (event_type, key, detail, self._now()),
            )
            self._connection.commit()
            sequence = cursor.lastrowid
            if sequence is None:
                raise RuntimeError("cache event store did not return a sequence")
            return sequence

    def _key_lock(self, key: str) -> threading.Lock:
        with self._lock:
            lock = self._key_locks.get(key)
            if lock is None:
                lock = threading.Lock()
                self._key_locks[key] = lock
            return lock

    def _value_size(self, key: str) -> int:
        target = self.values / f"{key}.json"
        return target.stat().st_size if target.is_file() else 0

    def _disk_bytes(self) -> int:
        return sum(target.stat().st_size for target in self.values.glob("*.json"))
