"""Typed, revisioned tolerance contract and shared result envelope.

The contract is *data*: every callout carries a typed engineering quantity with
an explicit unit, an interval of allowed deviation, an optional bounding datum
reference frame, the distribution assumed across that interval, and a
provenance record. It reuses the manufacturing envelope provenance and the
canonical design-space digest so it binds into the existing revision system
instead of inventing a parallel one.
"""

from __future__ import annotations

import math
import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from enum import StrEnum
from math import isfinite
from typing import Any

from aeroworkbench_core.types import FidelityLevel, Provenance, ResultSource
from aeroworkbench_manufacturing.envelopes import LimitProvenance, LimitSourceKind
from aeroworkbench_manufacturing.units import (
    SUPPORTED_UNITS,
    UnitConversionError,
    unit_dimension,
)
from aeroworkbench_optimization.design_space import content_digest

from .errors import ToleranceContractError

__all__ = [
    "TOLERANCE_SCHEMA_VERSION",
    "DatumReference",
    "DistributionKind",
    "ResultEnvelope",
    "SoftwareIdentity",
    "ToleranceCallout",
    "ToleranceClass",
    "ToleranceContract",
    "build_envelope",
    "deviation_scale",
    "scale_of",
]

TOLERANCE_SCHEMA_VERSION = "advphys10-v1"
SOFTWARE_IDENTITY = "aeroworkbench-tolerancing"
SOFTWARE_VERSION = "1.0.0"


class ToleranceClass(StrEnum):
    """Generic geometric/engineering characteristic families."""

    DIMENSION = "dimension"
    ANGLE = "angle"
    POSITION = "position"
    CONCENTRICITY = "concentricity"
    RUNOUT = "runout"
    FLATNESS = "flatness"
    PROFILE = "profile"
    SURFACE_FINISH = "surface_finish"
    MATERIAL_VARIABILITY = "material_variability"
    PROCESS_VARIABILITY = "process_variability"
    CLEARANCE = "clearance"
    PRELOAD = "preload"


class DistributionKind(StrEnum):
    """Declared distribution across a tolerance interval.

    ``NORMAL`` is interpreted as a truncated normal whose limits sit at
    ``+/- sigma_multiplier`` standard deviations; ``CONSTANT`` is deterministic.
    """

    NORMAL = "normal"
    UNIFORM = "uniform"
    TRIANGULAR = "triangular"
    CONSTANT = "constant"


@dataclass(frozen=True, slots=True)
class SoftwareIdentity:
    """The software that produced a tolerancing result."""

    name: str = SOFTWARE_IDENTITY
    version: str = SOFTWARE_VERSION

    def canonical(self) -> dict[str, str]:
        return {"name": self.name, "version": self.version}


def scale_of(unit: str) -> float:
    """Linear scale of a unit relative to SI, failing closed when unknown."""

    definition = SUPPORTED_UNITS.get(unit)
    if definition is None:
        raise ToleranceContractError(f"UNKNOWN_UNIT:{unit}")
    return definition.scale


def require_unit(unit: str) -> str:
    """Validate a unit and return its dimension, translating to a contract error."""

    try:
        return unit_dimension(unit)
    except UnitConversionError as error:
        raise ToleranceContractError(f"UNKNOWN_UNIT:{unit}") from error


def deviation_scale(unit: str) -> float:
    """Scale that converts a *relative* deviation in ``unit`` to SI.

    Deviations never include the absolute offset of scales such as degC, so an
    unknown unit fails closed rather than silently passing through.
    """

    require_unit(unit)
    return scale_of(unit)


@dataclass(frozen=True, slots=True)
class DatumReference:
    """A datum feature reference used to bound a tolerance callout."""

    datum_id: str
    feature: str
    precedence: int = 1

    def __post_init__(self) -> None:
        if not self.datum_id.strip():
            raise ToleranceContractError("DATUM_ID_REQUIRED")
        if not self.feature.strip():
            raise ToleranceContractError("DATUM_FEATURE_REQUIRED")
        if self.precedence < 1:
            raise ToleranceContractError(f"DATUM_PRECEDENCE_INVALID:{self.datum_id}")

    def as_dict(self) -> dict[str, Any]:
        return {
            "datumId": self.datum_id,
            "feature": self.feature,
            "precedence": self.precedence,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> DatumReference:
        return cls(
            datum_id=str(payload["datumId"]),
            feature=str(payload["feature"]),
            precedence=int(payload.get("precedence", 1)),
        )


@dataclass(frozen=True, slots=True)
class ResultEnvelope:
    """Source/fidelity/units/validity/hash/software/provenance envelope."""

    source: str
    fidelity: str
    unit: str
    validity: str
    inputs_hash: str
    software: SoftwareIdentity
    provenance: Provenance
    assumptions: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "fidelity": self.fidelity,
            "unit": self.unit,
            "validity": self.validity,
            "inputsHash": self.inputs_hash,
            "software": self.software.canonical(),
            "assumptions": list(self.assumptions),
            "provenance": dict(self.provenance.model_dump(mode="json")),
        }


def build_envelope(
    *,
    model: str,
    inputs: Mapping[str, Any],
    unit: str,
    assumptions: Sequence[str],
    validity: str = "valid",
) -> ResultEnvelope:
    """Build an analytical result envelope from declared inputs and assumptions."""

    provenance = Provenance.from_inputs(
        source=ResultSource.ANALYTICAL,
        model=model,
        model_version=SOFTWARE_VERSION,
        fidelity=FidelityLevel.ANALYTICAL,
        inputs=dict(inputs),
        assumptions=tuple(assumptions),
    )
    return ResultEnvelope(
        source=provenance.source.value,
        fidelity=provenance.fidelity.value,
        unit=unit,
        validity=validity,
        inputs_hash=provenance.inputs_hash,
        software=SoftwareIdentity(),
        provenance=provenance,
        assumptions=tuple(assumptions),
    )


@dataclass(frozen=True, slots=True)
class ToleranceCallout:
    """One revisioned tolerance callout over a typed engineering quantity.

    ``lower_deviation`` and ``upper_deviation`` are signed deviations from
    ``nominal`` expressed in ``unit`` (asymmetric tolerances are supported).
    """

    id: str
    characteristic: str
    tolerance_class: ToleranceClass
    nominal: float
    unit: str
    lower_deviation: float
    upper_deviation: float
    distribution: DistributionKind = DistributionKind.NORMAL
    datums: tuple[DatumReference, ...] = ()
    sigma_multiplier: float = 3.0
    provenance: LimitProvenance = field(
        default_factory=lambda: LimitProvenance(
            LimitSourceKind.USER_REQUIREMENT, "unspecified"
        )
    )
    revision: int = 1
    detail: str = ""

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ToleranceContractError("CALLOUT_ID_REQUIRED")
        if not self.characteristic.strip():
            raise ToleranceContractError(f"CALLOUT_CHARACTERISTIC_REQUIRED:{self.id}")
        require_unit(self.unit)
        for label, value in (
            ("nominal", self.nominal),
            ("lower_deviation", self.lower_deviation),
            ("upper_deviation", self.upper_deviation),
        ):
            if not isfinite(value):
                raise ToleranceContractError(f"NONFINITE_{label.upper()}:{self.id}")
        if self.lower_deviation > self.upper_deviation:
            raise ToleranceContractError(f"TOLERANCE_INTERVAL_INVERTED:{self.id}")
        if self.distribution is DistributionKind.NORMAL and self.sigma_multiplier <= 0:
            raise ToleranceContractError(f"NORMAL_NEEDS_POSITIVE_SIGMA:{self.id}")
        if self.revision < 1:
            raise ToleranceContractError(f"INVALID_CALLOUT_REVISION:{self.id}")
        seen: set[str] = set()
        for datum in self.datums:
            if datum.datum_id in seen:
                raise ToleranceContractError(f"DUPLICATE_DATUM:{self.id}:{datum.datum_id}")
            seen.add(datum.datum_id)

    @property
    def nominal_si(self) -> float:
        return self.nominal * scale_of(self.unit)

    @property
    def lower_si(self) -> float:
        return self.nominal_si + self.lower_deviation * deviation_scale(self.unit)

    @property
    def upper_si(self) -> float:
        return self.nominal_si + self.upper_deviation * deviation_scale(self.unit)

    @property
    def half_range_si(self) -> float:
        return 0.5 * (self.upper_si - self.lower_si)

    def to_distribution_sigma_si(self) -> float:
        """Equivalent standard deviation of this callout's distribution, in SI."""

        span = self.half_range_si
        if self.distribution is DistributionKind.CONSTANT or span == 0.0:
            return 0.0
        if self.distribution is DistributionKind.UNIFORM:
            return (2.0 * span) / math.sqrt(12.0)
        if self.distribution is DistributionKind.TRIANGULAR:
            return (2.0 * span) / math.sqrt(24.0)
        return span / self.sigma_multiplier

    def sample_deviation(self, rng: random.Random) -> float:
        """Draw one deterministic deviation from the declared distribution.

        The truncation to the declared interval is deliberate and reported as
        an assumption: no sample escapes the drawing limits.
        """

        low = self.lower_deviation
        high = self.upper_deviation
        if self.distribution is DistributionKind.CONSTANT or low == high:
            return low
        if self.distribution is DistributionKind.UNIFORM:
            return rng.uniform(low, high)
        if self.distribution is DistributionKind.TRIANGULAR:
            mode = 0.5 * (low + high)
            return rng.triangular(low, high, mode)
        sigma = self.sigma_multiplier
        if sigma <= 0:
            raise ToleranceContractError(f"NORMAL_NEEDS_POSITIVE_SIGMA:{self.id}")
        center = 0.5 * (low + high)
        draw = rng.gauss(center, (high - low) / (2.0 * sigma))
        return min(max(draw, low), high)

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "characteristic": self.characteristic,
            "toleranceClass": self.tolerance_class.value,
            "nominal": self.nominal,
            "unit": self.unit,
            "lowerDeviation": self.lower_deviation,
            "upperDeviation": self.upper_deviation,
            "distribution": self.distribution.value,
            "sigmaMultiplier": self.sigma_multiplier,
            "datums": [datum.as_dict() for datum in self.datums],
            "provenance": self.provenance.as_dict(),
            "revision": self.revision,
            "detail": self.detail,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> ToleranceCallout:
        return cls(
            id=str(payload["id"]),
            characteristic=str(payload["characteristic"]),
            tolerance_class=ToleranceClass(str(payload["toleranceClass"])),
            nominal=float(payload["nominal"]),
            unit=str(payload["unit"]),
            lower_deviation=float(payload["lowerDeviation"]),
            upper_deviation=float(payload["upperDeviation"]),
            distribution=DistributionKind(
                str(payload.get("distribution", DistributionKind.NORMAL.value))
            ),
            datums=tuple(DatumReference.from_dict(item) for item in payload.get("datums", ())),
            sigma_multiplier=float(payload.get("sigmaMultiplier", 3.0)),
            provenance=LimitProvenance.from_dict(payload["provenance"]),
            revision=int(payload.get("revision", 1)),
            detail=str(payload.get("detail", "")),
        )


@dataclass(frozen=True, slots=True)
class ToleranceContract:
    """A revisioned set of tolerance callouts bound to a design revision."""

    contract_id: str
    revision: int = 1
    callouts: tuple[ToleranceCallout, ...] = ()
    schema_version: str = TOLERANCE_SCHEMA_VERSION
    parent_hash: str | None = None

    def __post_init__(self) -> None:
        if not self.contract_id.strip():
            raise ToleranceContractError("CONTRACT_ID_REQUIRED")
        if self.revision < 1:
            raise ToleranceContractError(f"INVALID_CONTRACT_REVISION:{self.contract_id}")
        seen: set[str] = set()
        for callout in self.callouts:
            if callout.id in seen:
                raise ToleranceContractError(f"DUPLICATE_CALLOUT:{self.contract_id}:{callout.id}")
            seen.add(callout.id)

    def callout(self, callout_id: str) -> ToleranceCallout:
        for callout in self.callouts:
            if callout.id == callout_id:
                return callout
        raise ToleranceContractError(f"UNKNOWN_CALLOUT:{callout_id}")

    def by_characteristic(self, characteristic: str) -> tuple[ToleranceCallout, ...]:
        return tuple(
            callout for callout in self.callouts if callout.characteristic == characteristic
        )

    def datum_index(self) -> dict[str, str]:
        """Map every referenced datum id to its feature, failing closed on conflict."""

        index: dict[str, str] = {}
        for callout in self.callouts:
            for datum in callout.datums:
                existing = index.get(datum.datum_id)
                if existing is not None and existing != datum.feature:
                    raise ToleranceContractError(
                        f"DATUM_FEATURE_CONFLICT:{datum.datum_id}:{existing}:{datum.feature}"
                    )
                index[datum.datum_id] = datum.feature
        return index

    def content_payload(self) -> dict[str, Any]:
        return {
            "kind": "tolerance-contract",
            "contractId": self.contract_id,
            "revision": self.revision,
            "callouts": [callout.as_dict() for callout in self.callouts],
            "schemaVersion": self.schema_version,
            "parentHash": self.parent_hash,
        }

    @property
    def content_hash(self) -> str:
        return content_digest(self.content_payload())

    def as_dict(self) -> dict[str, Any]:
        payload = self.content_payload()
        payload["contentHash"] = self.content_hash
        return payload

    def revise(self, **changes: Any) -> ToleranceContract:
        if "revision" in changes:
            raise ToleranceContractError("REVISE_MUST_NOT_SET_REVISION")
        return replace(self, **changes, revision=self.revision + 1, parent_hash=self.content_hash)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> ToleranceContract:
        return cls(
            contract_id=str(payload["contractId"]),
            revision=int(payload.get("revision", 1)),
            callouts=tuple(
                ToleranceCallout.from_dict(item) for item in payload.get("callouts", ())
            ),
            schema_version=str(payload.get("schemaVersion", TOLERANCE_SCHEMA_VERSION)),
            parent_hash=None if payload.get("parentHash") is None else str(payload["parentHash"]),
        )
