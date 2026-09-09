from __future__ import annotations

import hashlib
import json
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from .types import Quantity


class FieldChange(BaseModel):
    model_config = ConfigDict(frozen=True)
    before: Quantity
    after: Quantity


class ChangeRecord(BaseModel):
    model_config = ConfigDict(frozen=True)
    author: str
    reason: str
    created_at: datetime
    changed_fields: dict[str, FieldChange]


class PhysicalDesignState(BaseModel):
    model_config = ConfigDict(frozen=True)
    design_id: str
    variant_id: str
    parent_variant_id: str | None = None
    parameters: dict[str, Quantity]
    geometry_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    material_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    scalar_results: dict[str, Quantity] = Field(default_factory=dict)
    change_record: ChangeRecord | None = None

    @property
    def content_hash(self) -> str:
        parameters = {
            key: {"dimension": value.dimension, "value_si": value.si_value}
            for key, value in self.parameters.items()
        }
        payload = {
            "parameters": parameters,
            "geometry_hash": self.geometry_hash,
            "material_hash": self.material_hash,
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()

    def create_variant(
        self,
        *,
        variant_id: str,
        changes: dict[str, Quantity],
        author: str,
        reason: str,
        created_at: datetime,
        scalar_results: dict[str, Quantity] | None = None,
    ) -> PhysicalDesignState:
        updated = {**self.parameters, **changes}
        changed = {
            key: FieldChange(before=self.parameters[key], after=value)
            for key, value in changes.items()
        }
        return PhysicalDesignState(
            design_id=self.design_id,
            variant_id=variant_id,
            parent_variant_id=self.variant_id,
            parameters=updated,
            geometry_hash=self.geometry_hash,
            material_hash=self.material_hash,
            scalar_results=scalar_results if scalar_results is not None else self.scalar_results,
            change_record=ChangeRecord(
                author=author, reason=reason, created_at=created_at, changed_fields=changed
            ),
        )


class Delta(BaseModel):
    absolute_si: float
    percent: float | None


class VariantComparison(BaseModel):
    parameter_deltas: dict[str, Delta]
    result_deltas: dict[str, Delta]


def _deltas(left: dict[str, Quantity], right: dict[str, Quantity]) -> dict[str, Delta]:
    output: dict[str, Delta] = {}
    for key in left.keys() & right.keys():
        absolute = right[key].si_value - left[key].si_value
        percent = None if left[key].si_value == 0 else 100 * absolute / left[key].si_value
        output[key] = Delta(absolute_si=absolute, percent=percent)
    return output


def compare_variants(
    baseline: PhysicalDesignState, candidate: PhysicalDesignState
) -> VariantComparison:
    return VariantComparison(
        parameter_deltas=_deltas(baseline.parameters, candidate.parameters),
        result_deltas=_deltas(baseline.scalar_results, candidate.scalar_results),
    )
