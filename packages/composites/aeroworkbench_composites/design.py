"""Aggregate composite design evaluation and design-space invalidation wiring.

One call runs manufacturing screening first (cheap, fail-closed), then CLT,
first-ply failure, and optionally a reduced modal estimate, returning a single
provenance-backed, hashable result. Changes to composite inputs are classified
onto the shared design-section vocabulary and mapped through the coupling-DAG
invalidation table, so composite work reruns only when its inputs change.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, cast

from aeroworkbench_core.types import Provenance
from aeroworkbench_materials import LaminateRevision

from .clt import LaminateAnalysis, LaminateLoad, analyze_laminate
from .coupling import ModalEstimate, cantilever_bending_frequency_hz
from .failure import (
    FailureCriterion,
    FirstPlyResult,
    StrengthLibrary,
    first_ply_failure,
)
from .manufacturing import (
    ManufacturingReport,
    PlyProcessLimits,
    require_manufacturable,
)
from .provenance import analytical_provenance
from .validity import CompositesError, Validity, finite

__all__ = [
    "CompositeDesignResult",
    "CompositeInputs",
    "composite_change_sections",
    "composite_invalidated_families",
    "composite_invalidated_for",
    "evaluate_composite_design",
]

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class CompositeInputs:
    """Content identity of the inputs that drive a composite design analysis."""

    part_id: str
    laminate_digest: str
    material_digest: str
    temperature_k: float
    pressure_pa: float = 0.0
    rotational_speed_rad_s: float = 0.0

    def __post_init__(self) -> None:
        if not self.part_id.strip():
            raise CompositesError("composite input part_id is required")
        for name in ("laminate_digest", "material_digest"):
            if not _SHA256.fullmatch(getattr(self, name)):
                raise CompositesError(f"{name} must be a sha256 digest")
        finite(self.temperature_k, "temperature_k", positive=True)
        finite(self.pressure_pa, "pressure_pa")
        finite(self.rotational_speed_rad_s, "rotational_speed_rad_s")

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "partId": self.part_id,
            "laminateDigest": self.laminate_digest,
            "materialDigest": self.material_digest,
            "temperatureK": self.temperature_k,
            "pressurePa": self.pressure_pa,
            "rotationalSpeedRadS": self.rotational_speed_rad_s,
        }

    def digest(self) -> str:
        encoded = json.dumps(
            self.canonical_payload(), sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


def composite_change_sections(
    before: CompositeInputs, after: CompositeInputs
) -> tuple[str, ...]:
    """Classify a composite-input delta onto the design-section vocabulary."""

    sections: set[str] = set()
    if (
        before.material_digest != after.material_digest
        or before.laminate_digest != after.laminate_digest
    ):
        sections.add("materials")
    if (
        before.temperature_k != after.temperature_k
        or before.pressure_pa != after.pressure_pa
        or before.rotational_speed_rad_s != after.rotational_speed_rad_s
    ):
        sections.add("operatingPoints")
    if before.part_id != after.part_id:
        sections.add("parameters")
    return tuple(sorted(sections))


def composite_invalidated_families(
    changed_sections: tuple[str, ...],
) -> tuple[str, ...]:
    """Map changed design sections to invalidated node families via the DAG."""

    from aeroworkbench_coupling.dag import invalidated_families

    return cast(tuple[str, ...], invalidated_families(changed_sections))


def composite_invalidated_for(
    before: CompositeInputs, after: CompositeInputs
) -> tuple[str, ...]:
    """Full change-section to invalidated-family mapping for a composite delta."""

    return composite_invalidated_families(composite_change_sections(before, after))


@dataclass(frozen=True, slots=True)
class CompositeDesignResult:
    """One aggregate composite design outcome."""

    laminate_identity: str
    laminate_digest: str
    analysis: LaminateAnalysis
    failure: FirstPlyResult | None
    manufacturing: ManufacturingReport | None
    modal: ModalEstimate | None
    validity: Validity
    provenance: Provenance
    digest: str

    def units(self) -> dict[str, str]:
        units: dict[str, str] = dict(self.analysis.units())
        if self.failure is not None:
            units["failure_index"] = "1"
            units["reserve_factor"] = "1"
        if self.modal is not None:
            units.update(self.modal.units())
        return units

    def as_dict(self) -> dict[str, Any]:
        return {
            "laminate": self.laminate_identity,
            "laminateDigest": self.laminate_digest,
            "analysis": self.analysis.as_dict(),
            "failure": None if self.failure is None else self.failure.as_dict(),
            "manufacturing": (
                None if self.manufacturing is None else self.manufacturing.as_dict()
            ),
            "modal": None if self.modal is None else self.modal.as_dict(),
            "validity": self.validity.as_dict(),
            "digest": self.digest,
            "inputsHash": self.provenance.inputs_hash,
            "source": self.provenance.source.value,
        }


def evaluate_composite_design(
    laminate: LaminateRevision,
    *,
    process_limits: PlyProcessLimits | None = None,
    strengths: StrengthLibrary | None = None,
    load: LaminateLoad | None = None,
    criterion: FailureCriterion = FailureCriterion.TSAI_WU,
    temperature_k: float | None = None,
    delta_temperature_k: float = 0.0,
    modal_length_m: float | None = None,
    region_radius_m: float | None = None,
    drape_angle_deg: float | None = None,
) -> CompositeDesignResult:
    """Run the composite design chain, refusing expensive work after a hard reject."""

    manufacturing = None
    if process_limits is not None:
        manufacturing = require_manufacturable(
            laminate,
            process_limits,
            region_radius_m=region_radius_m,
            drape_angle_deg=drape_angle_deg,
        )
    analysis = analyze_laminate(
        laminate,
        temperature_k=temperature_k,
        delta_temperature_k=delta_temperature_k,
    )
    failure = None
    if strengths is not None:
        failure = first_ply_failure(
            analysis, load or LaminateLoad(), strengths, criterion=criterion
        )
    modal = None
    if modal_length_m is not None:
        modal = cantilever_bending_frequency_hz(analysis, length_m=modal_length_m)
    checks: dict[str, bool] = {
        "manufacturing_screened": manufacturing is not None,
        "manufacturing_passed": (
            True if manufacturing is None else manufacturing.passed
        ),
        "failure_evaluated": failure is not None,
        "first_ply_below_one": True if failure is None else not failure.failed,
    }
    passed = checks["manufacturing_passed"] and checks["first_ply_below_one"]
    provenance = analytical_provenance(
        "composite-design-evaluation",
        {
            "laminate": laminate.identity,
            "laminateDigest": analysis.laminate_digest,
            "temperatureK": temperature_k,
            "deltaTemperatureK": delta_temperature_k,
            "criterion": criterion.value,
            "failureIndex": None if failure is None else failure.index,
            "manufacturingPassed": checks["manufacturing_passed"],
        },
        assumptions=(
            "composite design chain: manufacturing screen, CLT, first-ply failure",
            "no native structural solver was executed; native paths remain gated",
        ),
    )
    digest = hashlib.sha256(
        json.dumps(
            {
                "laminateDigest": analysis.laminate_digest,
                "failure": None if failure is None else failure.index,
                "manufacturing": None if manufacturing is None else manufacturing.passed,
                "inputsHash": provenance.inputs_hash,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return CompositeDesignResult(
        laminate_identity=laminate.identity,
        laminate_digest=analysis.laminate_digest,
        analysis=analysis,
        failure=failure,
        manufacturing=manufacturing,
        modal=modal,
        validity=Validity(passed=passed, checks=checks, detail=f"design:{laminate.identity}"),
        provenance=provenance,
        digest=digest,
    )
