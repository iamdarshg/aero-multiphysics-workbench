"""Generic semantic topology: stable engineering entities and guarded updates.

Semantic identity is independent of transient kernel face numbers. Each entity
carries a stable ``semantic_key`` plus a geometric ``fingerprint`` recorded at
build time (face/region signature, not an index). Regeneration reconciles by
``(semantic_key, fingerprint)`` and fails closed on ambiguity.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

EntityKind = Literal[
    "solid_region",
    "fluid_region",
    "face",
    "interface",
    "inlet",
    "outlet",
    "wall",
    "symmetry",
    "periodic",
    "rotating_region",
    "stationary_region",
    "motion_frame",
    "shaft",
    "bearing",
    "mechanical_constraint",
    "mechanical_load",
    "material_assignment",
    "electrical_conductor",
    "magnetic_region",
    "heat_source",
    "thermal_contact",
    "fsi_interface",
    "cht_interface",
]

MOTION_KINDS: tuple[str, ...] = ("rotating_region", "stationary_region")

INTERFACE_KINDS: tuple[str, ...] = (
    "interface",
    "periodic",
    "thermal_contact",
    "fsi_interface",
    "cht_interface",
)


@dataclass(frozen=True, slots=True)
class TopologyEntity:
    """One engineering entity with kernel-independent identity."""

    semantic_key: str
    kind: EntityKind
    region: str
    fingerprint: str
    frame: str | None = None
    material_identity: str | None = None
    detail: str = ""

    def __post_init__(self) -> None:
        if not self.semantic_key.strip():
            raise ValueError("SEMANTIC_KEY_REQUIRED")
        if not self.region.strip():
            raise ValueError("ENTITY_REGION_REQUIRED")
        if not self.fingerprint.strip():
            raise ValueError("ENTITY_FINGERPRINT_REQUIRED")


@dataclass(frozen=True, slots=True)
class TopologyModel:
    """Immutable set of semantic entities for one geometry revision."""

    entities: tuple[TopologyEntity, ...]

    def __post_init__(self) -> None:
        keys = [entity.semantic_key for entity in self.entities]
        if len(keys) != len(set(keys)):
            raise ValueError("DUPLICATE_SEMANTIC_KEY")

    def by_key(self, semantic_key: str) -> TopologyEntity:
        for entity in self.entities:
            if entity.semantic_key == semantic_key:
                return entity
        raise KeyError(f"SEMANTIC_KEY_NOT_FOUND:{semantic_key}")

    def of_kind(self, kind: EntityKind) -> tuple[TopologyEntity, ...]:
        return tuple(entity for entity in self.entities if entity.kind == kind)


@dataclass(frozen=True, slots=True)
class TopologyChange:
    """One classified delta between two topology revisions."""

    change: Literal["preserved", "added", "missing", "moved", "split", "merged"]
    semantic_key: str
    detail: str = ""


@dataclass(frozen=True, slots=True)
class TopologyReport:
    """Guarded reconciliation outcome for a regenerated topology."""

    preserved: tuple[TopologyEntity, ...]
    added: tuple[TopologyEntity, ...]
    missing: tuple[str, ...]
    changed: tuple[TopologyChange, ...]
    ambiguous: tuple[str, ...]
    requires_remesh: bool
    reason: str

    @property
    def valid(self) -> bool:
        return not self.missing and not self.ambiguous


def fingerprint_match(previous: str, current: str, *, tolerance_digits: int = 3) -> bool:
    """Compare fingerprints up to a coarser rounding for small-change detection.

    Fingerprints embed rounded floats (``A=<area>|C=<x>,<y>,<z>``). Truncating
    the decimals detects entities that moved slightly versus entities whose
    topology genuinely changed.
    """

    def _coarsen(text: str) -> str:
        import re

        def _cut(match: re.Match[str]) -> str:
            number = match.group(0)
            if "." not in number:
                return number
            head, tail = number.split(".", 1)
            return f"{head}.{tail[:tolerance_digits]}"

        return re.sub(r"-?\d+\.\d+", _cut, text)

    return _coarsen(previous) == _coarsen(current)


def reconcile_topology(
    previous: TopologyModel, current: TopologyModel
) -> TopologyReport:
    """Reconcile regenerated topology with guarded update semantics.

    - exact ``(key, fingerprint)`` match: preserved;
    - same key, coarsened fingerprint match: moved (morph candidate);
    - same key, different fingerprint: changed identity, needs remesh;
    - key only in current: added; key only in previous: missing;
    - duplicate keys in either model: ambiguous, fail closed;
    - fingerprint collisions across different keys: ambiguous, fail closed.
    """

    previous_keys = [entity.semantic_key for entity in previous.entities]
    current_keys = [entity.semantic_key for entity in current.entities]
    ambiguous_hits: list[str] = sorted(
        {
            key
            for key in (*previous_keys, *current_keys)
            if previous_keys.count(key) + current_keys.count(key) > 1
            and (previous_keys.count(key) > 1 or current_keys.count(key) > 1)
        }
    )
    previous_by_fingerprint: dict[str, list[str]] = {}
    current_by_fingerprint: dict[str, list[str]] = {}
    for entity in previous.entities:
        previous_by_fingerprint.setdefault(entity.fingerprint, []).append(
            entity.semantic_key
        )
    for entity in current.entities:
        current_by_fingerprint.setdefault(entity.fingerprint, []).append(
            entity.semantic_key
        )
    for fingerprint, keys in previous_by_fingerprint.items():
        other = current_by_fingerprint.get(fingerprint, [])
        if len(keys) == 1 and len(other) == 1 and keys[0] != other[0]:
            ambiguous_hits.append(f"fingerprint-collision:{fingerprint[:24]}")
    ambiguous = tuple(sorted(set(ambiguous_hits)))

    previous_map = {entity.semantic_key: entity for entity in previous.entities}
    current_map = {entity.semantic_key: entity for entity in current.entities}
    preserved: list[TopologyEntity] = []
    added: list[TopologyEntity] = []
    missing: list[str] = []
    changed: list[TopologyChange] = []

    for key in sorted(set(previous_map) | set(current_map)):
        old = previous_map.get(key)
        new = current_map.get(key)
        if old is not None and new is not None:
            if old.fingerprint == new.fingerprint:
                if old.kind != new.kind or old.region != new.region:
                    changed.append(
                        TopologyChange(
                            "merged" if old.kind != new.kind else "moved",
                            key,
                            f"kind-or-region changed:{old.kind}->{new.kind}",
                        )
                    )
                else:
                    preserved.append(new)
            elif fingerprint_match(old.fingerprint, new.fingerprint):
                changed.append(
                    TopologyChange("moved", key, "fingerprint moved within tolerance")
                )
            else:
                changed.append(
                    TopologyChange(
                        "split", key, "fingerprint changed beyond tolerance"
                    )
                )
        elif new is not None:
            added.append(new)
        elif old is not None:
            missing.append(key)

    needs_remesh = bool(
        missing
        or ambiguous
        or any(item.change in ("split", "merged") for item in changed)
    )
    if ambiguous:
        reason = "RECONCILIATION_AMBIGUOUS:manual intervention required"
    elif missing:
        reason = "RECONCILIATION_MISSING_ENTITIES:remesh affected domains"
    elif any(item.change in ("split", "merged") for item in changed):
        reason = "TOPOLOGY_IDENTITY_CHANGED:remesh affected domains"
    elif changed:
        reason = "SMALL_GEOMETRY_CHANGE:morph candidate subject to quality gates"
    else:
        reason = "TOPOLOGY_PRESERVED"
    return TopologyReport(
        preserved=tuple(sorted(preserved, key=lambda e: e.semantic_key)),
        added=tuple(sorted(added, key=lambda e: e.semantic_key)),
        missing=tuple(sorted(missing)),
        changed=tuple(changed),
        ambiguous=ambiguous,
        requires_remesh=needs_remesh,
        reason=reason,
    )


def topology_from_components(
    assignments: tuple[tuple[str, EntityKind, str, str], ...],
    face_fingerprints: dict[str, tuple[str, ...]],
) -> TopologyModel:
    """Build a topology model from (semantic_key, kind, region, component).

    The entity fingerprint joins the component's face fingerprints so identity
    survives rebuilds while raw face indices do not.
    """

    entities: list[TopologyEntity] = []
    for semantic_key, kind, region, component in assignments:
        faces = face_fingerprints.get(component)
        if faces is None:
            raise KeyError(f"COMPONENT_NOT_BUILT:{component}")
        # Raw face signatures are kept (not hashed) so small geometric moves
        # remain comparable across rebuilds; indices are never stored.
        fingerprint = f"{component}::" + ";;".join(sorted(faces))
        entities.append(
            TopologyEntity(
                semantic_key=semantic_key,
                kind=kind,
                region=region,
                fingerprint=fingerprint,
            )
        )
    return TopologyModel(tuple(entities))
