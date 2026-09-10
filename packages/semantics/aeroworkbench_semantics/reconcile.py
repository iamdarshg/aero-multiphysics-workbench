"""Preserve engineering boundary semantics across regenerated topology."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SemanticAssignment:
    surface_id: str
    semantic_key: str
    role: str
    boundary: str


@dataclass(frozen=True, slots=True)
class ReconciliationReport:
    persistent: tuple[SemanticAssignment, ...]
    missing: tuple[str, ...]
    added: tuple[SemanticAssignment, ...]
    ambiguous: tuple[str, ...]

    @property
    def valid(self) -> bool:
        return not self.missing and not self.ambiguous


def reconcile_surfaces(
    previous: tuple[SemanticAssignment, ...], current: tuple[SemanticAssignment, ...]
) -> ReconciliationReport:
    """Match by semantic key and reject duplicate or role-changing matches."""

    previous_by_key: dict[str, list[SemanticAssignment]] = {}
    current_by_key: dict[str, list[SemanticAssignment]] = {}
    for assignment in previous:
        previous_by_key.setdefault(assignment.semantic_key, []).append(assignment)
    for assignment in current:
        current_by_key.setdefault(assignment.semantic_key, []).append(assignment)
    ambiguous = tuple(
        sorted(
            key
            for key, values in (*previous_by_key.items(), *current_by_key.items())
            if len(values) > 1
        )
    )
    persistent: list[SemanticAssignment] = []
    missing: list[str] = []
    for key, old_values in previous_by_key.items():
        new_values = current_by_key.get(key, [])
        if not new_values:
            missing.append(key)
        elif len(old_values) == 1 and len(new_values) == 1:
            old, new = old_values[0], new_values[0]
            if old.role != new.role or old.boundary != new.boundary:
                ambiguous = (*ambiguous, key)
            else:
                persistent.append(new)
    added = [
        values[0]
        for key, values in current_by_key.items()
        if key not in previous_by_key and len(values) == 1
    ]
    return ReconciliationReport(
        persistent=tuple(sorted(persistent, key=lambda item: item.semantic_key)),
        missing=tuple(sorted(missing)),
        added=tuple(sorted(added, key=lambda item: item.semantic_key)),
        ambiguous=tuple(sorted(set(ambiguous))),
    )
