"""Persistent metadata repositories for the API boundary."""

from .cache_store import (
    CacheArtifactRef,
    CacheEntryMetadata,
    CacheImmutabilityError,
    CacheIntegrityError,
    CacheReuseError,
    PersistentResultCache,
    cache_key,
)
from .sqlite import ArtifactReference, ImmutableRecordError, ProvenanceEvent, SQLiteRepository

__all__ = [
    "ArtifactReference",
    "CacheArtifactRef",
    "CacheEntryMetadata",
    "CacheImmutabilityError",
    "CacheIntegrityError",
    "CacheReuseError",
    "ImmutableRecordError",
    "PersistentResultCache",
    "ProvenanceEvent",
    "SQLiteRepository",
    "cache_key",
]
