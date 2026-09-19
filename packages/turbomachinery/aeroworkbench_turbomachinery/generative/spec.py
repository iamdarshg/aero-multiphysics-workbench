"""Declarative bounds for the rotating-gas generative design space.

The spec only declares search bounds, enumerations, and identity. It contains no
solver math and no application assumptions beyond the rotating-gas vocabulary
already owned by :mod:`aeroworkbench_turbomachinery`.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["DEFAULT_MATERIALS", "DEFAULT_PROCESSES", "GenerativeSpec", "default_spec"]

DEFAULT_MATERIALS: tuple[str, ...] = ("aluminum", "titanium", "nickel")
DEFAULT_PROCESSES: tuple[str, ...] = ("subtractive-5axis", "additive-lpbf")


@dataclass(frozen=True, slots=True)
class GenerativeSpec:
    """Bounded, deterministic assumptions for one generative design space."""

    space_id: str = "rotating-gas-generative"
    max_stages: int = 4
    max_rows: int = 6
    max_spools: int = 3
    levels: int = 3
    materials: tuple[str, ...] = DEFAULT_MATERIALS
    processes: tuple[str, ...] = DEFAULT_PROCESSES

    def __post_init__(self) -> None:
        if not self.space_id.strip():
            raise ValueError("GENERATIVE_SPACE_ID_REQUIRED")
        if self.max_stages < 1:
            raise ValueError("GENERATIVE_MAX_STAGES_MUST_BE_POSITIVE")
        if self.max_rows < 2:
            raise ValueError("GENERATIVE_MAX_ROWS_MUST_BE_AT_LEAST_TWO")
        if self.max_spools < 1:
            raise ValueError("GENERATIVE_MAX_SPOOLS_MUST_BE_POSITIVE")
        if self.levels < 1:
            raise ValueError("GENERATIVE_LEVELS_MUST_BE_POSITIVE")
        if not self.materials:
            raise ValueError("GENERATIVE_MATERIALS_REQUIRED")
        if not self.processes:
            raise ValueError("GENERATIVE_PROCESSES_REQUIRED")
        for label, values in (("materials", self.materials), ("processes", self.processes)):
            if len(set(values)) != len(values):
                raise ValueError(f"GENERATIVE_DUPLICATE_{label.upper()}")

    @property
    def row_point_ids(self) -> tuple[str, ...]:
        return tuple(f"r{index}" for index in range(self.max_rows))

    @property
    def spool_point_ids(self) -> tuple[str, ...]:
        return tuple(f"r{index}" for index in range(self.max_spools))

    @property
    def stage_point_ids(self) -> tuple[str, ...]:
        return tuple(f"s{index}" for index in range(self.max_stages))


def default_spec() -> GenerativeSpec:
    return GenerativeSpec()
