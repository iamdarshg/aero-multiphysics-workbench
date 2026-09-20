from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Lock
from time import sleep

import pytest

from aeroworkbench_api.repositories.cache_store import (
    CacheImmutabilityError,
    PersistentResultCache,
    cache_key,
)


def test_transitive_invalidation_preserves_history_and_explains_miss(tmp_path):
    cache = PersistentResultCache(tmp_path)
    a, b, c, d = [x*64 for x in "abcd"]
    for key, upstream in ((a, ()), (b, (a,)), (c, (b,)), (d, ())):
        cache.put(key, {"value": key[0]}, node_type="analysis", family="analysis",
                  upstream_keys=upstream)
    assert cache.invalidate(a) == [a, b, c]
    assert cache.lookup(c).reason == "INVALIDATED"
    assert cache.get(c) is None
    assert cache.get_historical(c) == {"value": "c"}
    assert cache.lookup(d).status == "exact_hit"
    assert cache.lookup("e"*64).reason == "NOT_FOUND"
    with pytest.raises(CacheImmutabilityError):
        cache.put(c, {"value": "different"}, node_type="analysis", family="analysis")
    cache.close()


def test_warm_start_requires_compatible_contract_and_is_not_exact(tmp_path):
    cache = PersistentResultCache(tmp_path)
    old, new, context = "a"*64, "b"*64, "c"*64
    cache.put(old, {"x": 2}, node_type="analysis", family="analysis",
              compatibility_digest=context)
    warm = cache.lookup(new, warm_start_key=old, compatibility_digest=context)
    assert warm.status == "warm_start"
    assert warm.value == {"x": 2}
    assert warm.source_key == old
    assert cache.get(new) is None
    assert cache.lookup(new, warm_start_key=old,
                        compatibility_digest="d"*64).reason == "INCOMPATIBLE_WARM_START"
    assert {event["event_type"] for event in cache.events()} >= {"cache.warm_start", "cache.miss"}
    cache.close()


def test_cross_instance_single_flight_and_bounded_lock_state(tmp_path):
    caches = [PersistentResultCache(tmp_path), PersistentResultCache(tmp_path)]
    barrier, guard = Barrier(2), Lock()
    calls = []

    def factory():
        with guard:
            calls.append(1)
        sleep(.05)
        return {"answer": 42}

    def request(cache):
        barrier.wait(timeout=3)
        return cache.compute_if_absent("a"*64, factory, node_type="a", family="a")

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(request, caches))
    assert results == [{"answer": 42}, {"answer": 42}]
    assert len(calls) == 1
    for cache in caches:
        cache.close()


def test_hierarchy_axes_change_cache_key():
    base = dict(node_type="subtree", geometry_hash="a"*64, semantic_hash="b"*64,
                material_hash="c"*64, solver=("analytical", "1"), settings={})
    original = cache_key(**base)
    for axis in ("subtree_digest", "boundary_digest", "interface_digest", "transform_digest",
                 "mapping_digest", "harmonic_digest", "temporal_digest", "qoi_digest"):
        assert cache_key(**base, **{axis: "d"*64}) != original


def test_reverse_dependency_index_supports_siblings_and_reachability(tmp_path):
    cache = PersistentResultCache(tmp_path)
    root, left, right, leaf = [x * 64 for x in "abcd"]
    cache.put(root, {"value": "root"}, node_type="boundary", family="boundary")
    cache.put(left, {"value": "left"}, node_type="mapping", family="mapping",
              upstream_keys=(root,))
    cache.put(right, {"value": "right"}, node_type="mapping", family="mapping",
              upstream_keys=(root,))
    cache.put(leaf, {"value": "leaf"}, node_type="harmonic", family="harmonic",
              upstream_keys=(left,))

    assert cache.downstream_dependencies(root, transitive=False) == [left, right]
    assert cache.downstream_dependencies(root) == [left, right, leaf]
    assert cache.is_reachable(root, leaf)
    assert not cache.is_reachable(right, leaf)
    assert cache.invalidate(left) == [left, leaf]
    assert cache.get(right) == {"value": "right"}
    cache.close()


def test_lookup_exposes_typed_explainable_outcomes(tmp_path):
    cache = PersistentResultCache(tmp_path)
    old, new, context = "a" * 64, "b" * 64, "c" * 64
    cache.put(old, {"x": 1}, node_type="mapping", family="mapping",
              compatibility_digest=context)
    assert cache.lookup(old).status == "exact_hit"
    assert cache.lookup(
        new, warm_start_key=old, compatibility_digest=context
    ).status == "warm_start"
    assert cache.lookup(
        new, warm_start_key=old, compatibility_digest="d" * 64
    ).reason == "INCOMPATIBLE_WARM_START"
    assert cache.lookup("f" * 64).reason == "NOT_FOUND"
    cache.close()
