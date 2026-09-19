"""Canonical initial-vehicle seeds and their design-space / design-state projections.

A seed is an immutable, hashable bundle of synthesized quantities. It projects
onto two existing contracts without a bespoke optimizer: ``design_parameters``
maps onto the unit-safe ``PhysicalDesignState`` parameter set, and
``build_seed_design_space`` emits an ordinary canonical design-space document that
the shared generator/preflight machinery already understands.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from aeroworkbench_core.design import PhysicalDesignState
from aeroworkbench_core.types import Provenance
from aeroworkbench_core.types import Quantity as DesignQuantity

from ..canonical import content_digest, normalize_numbers
from ..units import Quantity
from .methods import SynthesisQuantity

_DESIGN_UNITS: dict[str, str] = {"length": "m", "force": "N", "power": "W"}


@dataclass(frozen=True, slots=True)
class VehicleSeed:
    """An immutable initial-vehicle seed with per-value provenance and validity."""

    seed_id: str
    architecture_type: str
    quantities: tuple[SynthesisQuantity, ...]
    provenance: Provenance
    assumptions: tuple[str, ...] = ()

    def parameter(self, name: str) -> Quantity:
        for quantity in self.quantities:
            if quantity.name == name:
                return quantity.quantity
        raise KeyError(f"UNKNOWN_SEED_PARAMETER:{name}")

    @property
    def admissibility(self) -> tuple[str, ...]:
        return tuple(
            f"{quantity.name}:{violation}"
            for quantity in self.quantities
            for violation in quantity.validity.violations
        )

    @property
    def admissible(self) -> bool:
        return not self.admissibility

    def canonical_payload(self) -> dict[str, object]:
        return cast(
            dict[str, object],
            normalize_numbers(
                {
                    "seedId": self.seed_id,
                    "architectureType": self.architecture_type,
                    "assumptions": list(self.assumptions),
                    "parameters": [quantity.canonical() for quantity in self.quantities],
                    "provenance": self.provenance.model_dump(mode="json"),
                }
            ),
        )

    @property
    def content_hash(self) -> str:
        return content_digest(self.canonical_payload())

    def design_parameters(self) -> dict[str, DesignQuantity]:
        """Only dimensions the existing design contract can carry are exposed."""
        parameters: dict[str, DesignQuantity] = {}
        for quantity in self.quantities:
            unit = _DESIGN_UNITS.get(quantity.quantity.dimension)
            if unit is None:
                continue
            parameters[quantity.name] = DesignQuantity(value=quantity.quantity.value_si, unit=unit)
        return parameters

    def to_physical_design_state(
        self,
        *,
        design_id: str,
        variant_id: str,
        geometry_hash: str,
        material_hash: str,
    ) -> PhysicalDesignState:
        """Project onto the canonical design revision; geometry/material are seams."""
        return PhysicalDesignState(
            design_id=design_id,
            variant_id=variant_id,
            parameters=self.design_parameters(),
            geometry_hash=geometry_hash,
            material_hash=material_hash,
        )


def _identifier(name: str) -> str:
    cleaned = "".join(character if character.isalnum() else "_" for character in name).strip("_")
    return cleaned or "seed"


def _bounds(value: float, relative_variation: float) -> tuple[float, float]:
    if relative_variation <= 0.0:
        raise ValueError("RELATIVE_VARIATION_MUST_BE_POSITIVE")
    if value == 0.0:
        return (-relative_variation, relative_variation)
    span = abs(value) * relative_variation
    return (value - span, value + span)


def build_seed_design_space(
    seed: VehicleSeed, *, relative_variation: float = 0.1
) -> dict[str, Any]:
    """Emit a canonical design-space document bounded around a seed."""
    variables: list[dict[str, Any]] = []
    for quantity in seed.quantities:
        value = quantity.quantity.value_si
        lower, upper = _bounds(value, relative_variation)
        variable: dict[str, Any] = {
            "id": _identifier(quantity.name),
            "kind": "continuous",
            "bindings": [{"target": "parameter", "path": quantity.name}],
            "baseValue": value,
            "domain": {"kind": "continuous", "lower": lower, "upper": upper},
        }
        if quantity.quantity.dimension == "length":
            variable["unit"] = "m"
        variables.append(variable)
    return {
        "id": f"{_identifier(seed.seed_id)}-space",
        "variables": variables,
        "branches": [],
        "constraints": [],
    }
