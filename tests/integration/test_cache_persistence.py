from __future__ import annotations

import json
import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from aeroworkbench_api.repositories.cache_store import (
    CacheArtifactRef,
    CacheImmutabilityError,
    CacheIntegrityError,
    CacheReuseError,
    PersistentResultCache,
    cache_key,
    content_digest,
)


def _digest(character: str) -> str:
    return character * 64


def _open(root: Path, *, max_bytes: int = 64 * 1024 * 1024) -> PersistentResultCache:
    return PersistentResultCache(root, max_bytes=max_bytes)


def test_cache_persistence_survives_restart_and_hits(tmp_path: Path) -> None:
    root = tmp_path / "cache"
    key = _digest("1")
    calls = {"count": 0}

    def compute() -> dict[str, int]:
        calls["count"] += 1
        return {"value": 7}

    cache = _open(root)
    cold = time.perf_counter()
    first = cache.compute_if_absent(key, compute, node_type="edf.performance", family="analysis")
    cold_ms = (time.perf_counter() - cold) * 1000
    warm = time.perf_counter()
    second = cache.compute_if_absent(key, compute, node_type="edf.performance", family="analysis")
    warm_ms = (time.perf_counter() - warm) * 1000
    cache.close()

    restarted = _open(root)
    resumed = restarted.compute_if_absent(
        key, compute, node_type="edf.performance", family="analysis"
    )
    restarted.close()

    assert first == {"value": 7}
    assert second == {"value": 7}
    assert resumed == {"value": 7}
    assert calls["count"] == 1
    print(f"[cache-persistence] cold={cold_ms:.1f}ms warm={warm_ms:.1f}ms restart=hit")


def test_cache_persistence_coalesces_concurrent_candidates(tmp_path: Path) -> None:
    root = tmp_path / "cache"
    key = _digest("2")
    cache = _open(root)
    calls = {"count": 0}
    guard = threading.Lock()

    def compute() -> dict[str, int]:
        with guard:
            calls["count"] += 1
        time.sleep(0.05)
        return {"value": 42}

    def request() -> dict[str, int]:
        return cache.compute_if_absent(key, compute, node_type="mesh.case", family="mesh")

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=16) as pool:
        results = [future.result() for future in [pool.submit(request) for _ in range(64)]]
    elapsed_ms = (time.perf_counter() - started) * 1000
    stored_keys = cache.keys()
    cache.close()

    assert calls["count"] == 1, "in-flight duplicate work must coalesce"
    assert all(result == {"value": 42} for result in results)
    assert len(stored_keys) == 1
    print(f"[cache-persistence] coalesced 64 requests into 1 task in {elapsed_ms:.1f}ms")


def test_cache_persistence_fails_closed_on_corruption(tmp_path: Path) -> None:
    root = tmp_path / "cache"
    key = _digest("3")
    cache = _open(root)
    cache.put(key, {"value": 1}, node_type="post", family="post")
    cache.close()

    target = root / "values" / f"{key}.json"
    target.write_text('{"value": 999}', encoding="utf-8")

    reopened = _open(root)
    with pytest.raises(CacheIntegrityError, match="digest verification"):
        reopened.get(key)
    reopened.close()


def test_cache_persistence_rejects_overwrite(tmp_path: Path) -> None:
    cache = _open(tmp_path / "cache")
    key = _digest("4")
    cache.put(key, {"value": 1}, node_type="post", family="post")
    cache.put(key, {"value": 1}, node_type="post", family="post")
    with pytest.raises(CacheImmutabilityError, match="immutable"):
        cache.put(key, {"value": 2}, node_type="post", family="post")
    cache.close()


def test_cache_persistence_evicts_bounded_but_keeps_pinned(tmp_path: Path) -> None:
    cache = _open(tmp_path / "cache", max_bytes=8192)
    pinned_key = _digest("a")
    cache.put(pinned_key, {"payload": "pin"}, node_type="post", family="post", pinned=True)
    for index in range(24):
        cache.put(
            index.to_bytes(32, "big").hex(),
            {"payload": "x" * 1024},
            node_type="post",
            family="post",
        )

    assert cache.size_bytes <= 8192
    assert cache.get(pinned_key) == {"payload": "pin"}
    assert len(cache.keys()) < 25, "size pressure must evict unpinned entries"
    oldest = (0).to_bytes(32, "big").hex()
    assert cache.get(oldest) is None, "evicted entries become unavailable, not regenerated"
    assert cache.describe(oldest) is None
    cache.close()


def test_cache_persistence_invalidates_only_changed_subtree(tmp_path: Path) -> None:
    cache = _open(tmp_path / "cache")
    upstream = _digest("b")
    child = _digest("c")
    unrelated = _digest("d")
    cache.put(upstream, {"value": 1}, node_type="geometry", family="geometry")
    cache.put(
        child,
        {"value": 2},
        node_type="mesh",
        family="mesh",
        upstream_keys=(upstream,),
    )
    cache.put(unrelated, {"value": 3}, node_type="post", family="post")

    dropped = cache.invalidate(upstream)
    assert dropped == sorted([upstream, child])
    assert cache.get(upstream) is None
    assert cache.get(child) is None
    assert cache.get(unrelated) == {"value": 3}
    cache.close()


def test_cache_persistence_requires_trusted_native_reuse(tmp_path: Path) -> None:
    cache = _open(tmp_path / "cache")
    key = _digest("e")
    artifact = CacheArtifactRef(uri="artifacts/result.json", sha256=_digest("f"), bytes=12)
    cache.put(
        key,
        {"source": "native_solver", "scalars": {"first_critical_rpm": 1234.0}},
        node_type="rotor-campbell",
        family="analysis",
        solver=("ross", "2.3.0"),
        source="native_solver",
        validity_policy_version="policy-v1",
        artifacts=(artifact,),
    )

    value, event = cache.reuse_if_trusted(
        key,
        solver_id="ross",
        solver_version="2.3.0",
        validity_policy_version="policy-v1",
        source="native_solver",
        resolve_artifact=lambda ref: _digest("f"),
    )
    assert value["scalars"]["first_critical_rpm"] == 1234.0
    assert event["event_type"] == "cache.reuse"
    assert cache.events()[-1]["event_type"] == "cache.reuse"

    with pytest.raises(CacheReuseError) as solver_error:
        cache.reuse_if_trusted(
            key,
            solver_id="ross",
            solver_version="2.4.0",
            validity_policy_version="policy-v1",
            resolve_artifact=lambda ref: _digest("f"),
        )
    assert solver_error.value.reason == "SOLVER_IDENTITY_MISMATCH"

    with pytest.raises(CacheReuseError) as policy_error:
        cache.reuse_if_trusted(
            key,
            solver_id="ross",
            solver_version="2.3.0",
            validity_policy_version="policy-v2",
            resolve_artifact=lambda ref: _digest("f"),
        )
    assert policy_error.value.reason == "VALIDITY_POLICY_MISMATCH"

    with pytest.raises(CacheReuseError) as source_error:
        cache.reuse_if_trusted(
            key,
            solver_id="ross",
            solver_version="2.3.0",
            validity_policy_version="policy-v1",
            source="analytical",
            resolve_artifact=lambda ref: _digest("f"),
        )
    assert source_error.value.reason == "SOURCE_MISMATCH"

    with pytest.raises(CacheReuseError) as digest_error:
        cache.reuse_if_trusted(
            key,
            solver_id="ross",
            solver_version="2.3.0",
            validity_policy_version="policy-v1",
            resolve_artifact=lambda ref: _digest("0"),
        )
    assert digest_error.value.reason == "ARTIFACT_DIGEST_MISMATCH"

    with pytest.raises(CacheReuseError) as missing_error:
        cache.reuse_if_trusted(
            key,
            solver_id="ross",
            solver_version="2.3.0",
            validity_policy_version="policy-v1",
            resolve_artifact=lambda ref: None,
        )
    assert missing_error.value.reason == "ARTIFACT_MISSING"
    cache.close()


def test_cache_persistence_writes_atomically(tmp_path: Path) -> None:
    cache = _open(tmp_path / "cache")
    for index in range(5):
        cache.put(
            index.to_bytes(32, "big").hex(),
            {"value": index},
            node_type="post",
            family="post",
        )
    files = sorted(path.name for path in (cache.values).iterdir())
    assert not [name for name in files if name.endswith(".tmp")]
    assert len([name for name in files if name.endswith(".json")]) == 5
    cache.close()


def test_cache_persistence_canonical_key_covers_reuse_axes() -> None:
    common = {
        "node_type": "edf.performance",
        "geometry_hash": _digest("a"),
        "semantic_hash": _digest("b"),
        "material_hash": _digest("c"),
        "solver": ("analytical-edf", "1.0.0"),
        "settings": {"tolerance": 0.000001},
        "upstream_keys": (_digest("d"),),
    }
    baseline = cache_key(**common)
    assert cache_key(**common) == baseline
    assert cache_key(**{**common, "mesh_hash": _digest("e")}) != baseline
    assert cache_key(**{**common, "input_digest": _digest("e")}) != baseline
    assert cache_key(**{**common, "fidelity": "high"}) != baseline
    assert cache_key(**{**common, "participant": "rotor-campbell"}) != baseline
    assert cache_key(**{**common, "validity_policy_version": "policy-v2"}) != baseline
    assert cache_key(**{**common, "solver": ("analytical-edf", "1.0.1")}) != baseline
    assert cache_key(**{**common, "settings": {"tolerance": 0.001}}) != baseline
    assert cache_key(**{**common, "semantic_hash": _digest("e")}) != baseline


def test_cache_persistence_metadata_is_refs_not_blobs(tmp_path: Path) -> None:
    """The SQLite index stores references and metadata; values stay on disk."""

    root = tmp_path / "cache"
    cache = _open(root)
    key = _digest("9")
    cache.put(key, {"payload": "y" * 256}, node_type="post", family="post")
    cache.close()

    connection = sqlite3.connect(root / "cache.sqlite3")
    columns = {row[1] for row in connection.execute("PRAGMA table_info(result_cache)")}
    row = connection.execute(
        "SELECT value_digest, value_bytes, source FROM result_cache WHERE key=?", (key,)
    ).fetchone()
    connection.close()

    assert "value" not in columns
    assert row is not None
    stored = json.loads((root / "values" / f"{key}.json").read_text(encoding="utf-8"))
    assert row[0] == content_digest(stored)
    assert row[1] == (root / "values" / f"{key}.json").stat().st_size
    assert row[2] == "analytical"
