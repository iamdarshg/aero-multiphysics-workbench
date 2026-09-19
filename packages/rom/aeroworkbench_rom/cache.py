"""Content-addressed artifact cache for maps and model artifacts.

Artifacts are keyed by the SHA-256 digest of their canonical JSON form. Entries
are immutable, every read re-derives the digest so tampering fails closed, and
the store is bounded by an LRU entry count. This reuses the shared canonical
hashing primitive instead of inventing a second cache contract.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from typing import Any

from aeroworkbench_optimization.design_space import canonical_json, content_digest

from .errors import CacheImmutabilityError, CacheIntegrityError, MapContractError

__all__ = ["ArtifactRef", "MapArtifactCache"]


@dataclass(frozen=True, slots=True)
class ArtifactRef:
    """A content-addressed artifact reference."""

    key: str
    size: int

    def as_dict(self) -> dict[str, Any]:
        return {"key": self.key, "size": self.size}


class MapArtifactCache:
    """Bounded, immutable, content-addressed artifact store."""

    def __init__(self, *, max_entries: int = 128) -> None:
        if max_entries <= 0:
            raise MapContractError("ARTIFACT_CACHE_MAX_ENTRIES_MUST_BE_POSITIVE")
        self._max_entries = max_entries
        self._entries: OrderedDict[str, str] = OrderedDict()

    def put(self, value: Any) -> ArtifactRef:
        try:
            canonical = canonical_json(value)
        except (TypeError, ValueError) as exc:
            raise MapContractError(f"ARTIFACT_NOT_CANONICALIZABLE:{exc}") from exc
        key = content_digest(value)
        existing = self._entries.get(key)
        if existing is not None:
            if existing != canonical:
                raise CacheImmutabilityError(f"content-addressed artifact {key} is immutable")
            self._entries.move_to_end(key)
            return ArtifactRef(key, len(canonical.encode("utf-8")))
        self._entries[key] = canonical
        self._entries.move_to_end(key)
        while len(self._entries) > self._max_entries:
            self._entries.popitem(last=False)
        return ArtifactRef(key, len(canonical.encode("utf-8")))

    def get(self, key: str) -> Any:
        canonical = self._entries.get(key)
        if canonical is None:
            raise CacheIntegrityError(f"ARTIFACT_NOT_FOUND:{key}")
        import json

        value = json.loads(canonical)
        if content_digest(value) != key:
            raise CacheIntegrityError(f"ARTIFACT_DIGEST_MISMATCH:{key}")
        self._entries.move_to_end(key)
        return value

    def describe(self, key: str) -> ArtifactRef | None:
        canonical = self._entries.get(key)
        if canonical is None:
            return None
        return ArtifactRef(key, len(canonical.encode("utf-8")))

    def invalidate(self, key: str) -> bool:
        return self._entries.pop(key, None) is not None

    def keys(self) -> tuple[str, ...]:
        return tuple(sorted(self._entries))
