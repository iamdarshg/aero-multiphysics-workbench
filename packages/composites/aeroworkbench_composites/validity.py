"""Fail-closed validity, fidelity, and error contracts for composite design.

The generic validity primitives are reused from the durability package (which
itself builds on the core provenance contract), so composite results report the
same per-check verdicts, fidelity ladder, and typed fail-closed errors as the
rest of the workbench. Nothing is invented when data is absent, and an absent
native structural capability fails closed instead of being replaced by a
screening model.
"""

from __future__ import annotations

from collections.abc import Iterable

from aeroworkbench_core.types import Provenance
from aeroworkbench_durability.validity import (
    CapabilityUnavailable as CapabilityUnavailable,
)
from aeroworkbench_durability.validity import DataUnavailable as DataUnavailable
from aeroworkbench_durability.validity import DurabilityError as DurabilityError
from aeroworkbench_durability.validity import Fidelity as Fidelity
from aeroworkbench_durability.validity import Validity as Validity
from aeroworkbench_durability.validity import finite as finite
from aeroworkbench_durability.validity import finite_vector as finite_vector
from aeroworkbench_durability.validity import flag as flag
from aeroworkbench_durability.validity import integer as integer

__all__ = [
    "CapabilityUnavailable",
    "CompositesError",
    "DataUnavailable",
    "DurabilityError",
    "Fidelity",
    "ManufacturingViolation",
    "Validity",
    "finite",
    "finite_vector",
    "flag",
    "integer",
]


class CompositesError(DurabilityError):
    """A typed composite-design contract violation; the call fails closed."""


class ManufacturingViolation(CompositesError):
    """A declared manufacturing limit was violated before expensive analysis."""

    def __init__(
        self,
        detail: str,
        *,
        violations: Iterable[str],
        provenance: Provenance,
    ) -> None:
        super().__init__(detail)
        self.violations: tuple[str, ...] = tuple(violations)
        self.provenance: Provenance = provenance
