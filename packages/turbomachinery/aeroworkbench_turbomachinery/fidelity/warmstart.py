"""Warm-start reuse gated by existing topology and content-hash validity rules.

Geometry, mesh, maps, and converged state may only be reused from a previous
candidate when the keys they depend on are unchanged. Any topology change
invalidates every downstream asset; geometry change invalidates mesh and
converged state; a stale or invalid asset fails closed.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from ..canonical import content_digest

__all__ = [
    "WARM_START_RULES",
    "WarmStartAsset",
    "WarmStartDecision",
    "WarmStartKey",
    "WarmStartPolicy",
    "plan_warm_start",
]

WARM_START_RULES: dict[str, tuple[str, ...]] = {
    "geometry": ("topology_digest", "geometry_hash"),
    "mesh": ("topology_digest", "geometry_hash", "mesh_hash"),
    "map": ("topology_digest", "maps_hash"),
    "converged-state": ("topology_digest", "geometry_hash", "state_hash"),
}


@dataclass(frozen=True, slots=True)
class WarmStartKey:
    """Identity of the assets a warm start may reuse."""

    topology_digest: str
    geometry_hash: str
    mesh_hash: str = ""
    maps_hash: str = ""
    state_hash: str = ""

    def __post_init__(self) -> None:
        if not self.topology_digest.strip():
            raise ValueError("WARM_START_TOPOLOGY_DIGEST_REQUIRED")
        if not self.geometry_hash.strip():
            raise ValueError("WARM_START_GEOMETRY_HASH_REQUIRED")

    def field(self, name: str) -> str:
        if name not in {
            "topology_digest",
            "geometry_hash",
            "mesh_hash",
            "maps_hash",
            "state_hash",
        }:
            raise ValueError(f"UNKNOWN_WARM_START_KEY_FIELD:{name}")
        return str(getattr(self, name))

    def canonical(self) -> dict[str, Any]:
        return {
            "topologyDigest": self.topology_digest,
            "geometryHash": self.geometry_hash,
            "meshHash": self.mesh_hash,
            "mapsHash": self.maps_hash,
            "stateHash": self.state_hash,
        }

    @property
    def digest(self) -> str:
        return content_digest(self.canonical())


@dataclass(frozen=True, slots=True)
class WarmStartAsset:
    """One candidate asset offered for reuse, with its validity flag."""

    kind: str
    artifact_hash: str
    validity_ok: bool = True

    def __post_init__(self) -> None:
        if not self.kind.strip():
            raise ValueError("WARM_START_ASSET_KIND_REQUIRED")
        if not self.artifact_hash.strip():
            raise ValueError(f"WARM_START_ASSET_HASH_REQUIRED:{self.kind}")


@dataclass(frozen=True, slots=True)
class WarmStartPolicy:
    rules: Mapping[str, tuple[str, ...]] = field(
        default_factory=lambda: dict(WARM_START_RULES)
    )

    def required_fields(self, kind: str) -> tuple[str, ...] | None:
        return self.rules.get(kind)


@dataclass(frozen=True, slots=True)
class WarmStartDecision:
    reuse: bool
    reusable: tuple[str, ...]
    blocked: tuple[tuple[str, str], ...]
    reasons: tuple[str, ...]
    digest: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "reuse": self.reuse,
            "reusable": list(self.reusable),
            "blocked": [[kind, reason] for kind, reason in self.blocked],
            "reasons": list(self.reasons),
            "digest": self.digest,
        }


def plan_warm_start(
    previous: WarmStartKey,
    current: WarmStartKey,
    assets: Sequence[WarmStartAsset],
    *,
    policy: WarmStartPolicy | None = None,
) -> WarmStartDecision:
    """Decide which previous assets can seed the current candidate."""
    active = policy if policy is not None else WarmStartPolicy()
    reusable: list[str] = []
    blocked: list[tuple[str, str]] = []
    reasons: list[str] = []
    for asset in sorted(assets, key=lambda item: item.kind):
        required = active.required_fields(asset.kind)
        if required is None:
            blocked.append((asset.kind, "unknown-asset-kind"))
            reasons.append(f"no warm-start rule for {asset.kind}")
            continue
        if not asset.validity_ok:
            blocked.append((asset.kind, "asset-invalid"))
            reasons.append(f"{asset.kind} is not valid for reuse")
            continue
        mismatch = next(
            (
                name
                for name in required
                if previous.field(name) != current.field(name)
            ),
            None,
        )
        if mismatch is not None:
            blocked.append((asset.kind, f"field-changed:{mismatch}"))
            reasons.append(f"{asset.kind} blocked: {mismatch} changed")
            continue
        reusable.append(asset.kind)
        reasons.append(f"{asset.kind} reusable; {'/'.join(required)} unchanged")
    payload = {
        "previous": previous.canonical(),
        "current": current.canonical(),
        "assets": sorted(
            [
                {"kind": item.kind, "artifactHash": item.artifact_hash,
                 "validityOk": item.validity_ok}
                for item in assets
            ],
            key=lambda item: str(item["kind"]),
        ),
        "reusable": reusable,
        "blocked": [[kind, reason] for kind, reason in blocked],
    }
    return WarmStartDecision(
        reuse=bool(reusable) and not blocked,
        reusable=tuple(reusable),
        blocked=tuple(blocked),
        reasons=tuple(reasons),
        digest=content_digest(payload),
    )
