"""Generic N-D performance-map contract.

A performance map is a fitted, revisioned, hashable representation of validated
samples. It records the independent variables and units, the outputs and units,
the validity domain, the source sample ids with their source/fidelity labels,
the interpolation method, an uncertainty estimate, an extrapolation policy, and
a content hash that changes with any revision. Predictions are always labelled
``surrogate``: a map never presents itself as native physics.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from math import isfinite
from typing import Any

from aeroworkbench_optimization.design_space import content_digest

from .contracts import (
    ExtrapolationPolicy,
    MapFidelity,
    SampleKind,
    SoftwareIdentity,
    Validity,
)
from .errors import ExtrapolationError, MapContractError
from .models import SurrogateModel
from .variables import IndependentVariable, OutputVariable

__all__ = [
    "MapPrediction",
    "MapSample",
    "PerformanceMap",
    "build_map",
    "point_key",
]


def point_key(point: Mapping[str, float]) -> tuple[tuple[str, float], ...]:
    return tuple(sorted((str(name), round(float(value), 12)) for name, value in point.items()))


@dataclass(frozen=True, slots=True)
class MapSample:
    """One training sample with explicit source, fidelity, and lineage."""

    sample_id: str
    inputs: Mapping[str, float]
    outputs: Mapping[str, float]
    source: MapFidelity
    kind: SampleKind
    cost: float = 0.0
    lineage: tuple[str, ...] = ()
    solver: tuple[str, str] | None = None
    run_id: str | None = None

    def __post_init__(self) -> None:
        if not self.sample_id.strip():
            raise MapContractError("SAMPLE_ID_REQUIRED")
        if not isfinite(self.cost) or self.cost < 0.0:
            raise MapContractError(f"INVALID_SAMPLE_COST:{self.sample_id}")
        object.__setattr__(self, "inputs", {str(k): float(v) for k, v in self.inputs.items()})
        object.__setattr__(self, "outputs", {str(k): float(v) for k, v in self.outputs.items()})
        if not self.inputs or not self.outputs:
            raise MapContractError(f"SAMPLE_NEEDS_INPUTS_AND_OUTPUTS:{self.sample_id}")
        for name, value in (*self.inputs.items(), *self.outputs.items()):
            if not isfinite(value):
                raise MapContractError(f"NONFINITE_SAMPLE_VALUE:{self.sample_id}:{name}")
        if self.kind is SampleKind.EXPERIMENT and self.source is MapFidelity.NATIVE:
            raise MapContractError(f"EXPERIMENT_CANNOT_BE_NATIVE:{self.sample_id}")
        if self.source is MapFidelity.NATIVE:
            if not self.solver or not all(part.strip() for part in self.solver) or not self.run_id:
                raise MapContractError(f"NATIVE_SAMPLE_NEEDS_SOLVER_IDENTITY:{self.sample_id}")
        elif self.solver is not None:
            raise MapContractError(f"SOLVER_IDENTITY_ONLY_FOR_NATIVE:{self.sample_id}")

    @property
    def inputs_hash(self) -> str:
        return content_digest({"inputs": dict(sorted(self.inputs.items()))})

    def provenance(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "sampleId": self.sample_id,
            "source": self.source.value,
            "kind": self.kind.value,
            "cost": self.cost,
            "lineage": list(self.lineage),
            "inputsHash": self.inputs_hash,
        }
        if self.solver is not None:
            payload["solver"] = {"id": self.solver[0], "version": self.solver[1]}
        if self.run_id is not None:
            payload["runId"] = self.run_id
        return payload

    def as_dict(self) -> dict[str, Any]:
        return {
            **self.provenance(),
            "inputs": dict(sorted(self.inputs.items())),
            "outputs": dict(sorted(self.outputs.items())),
        }


@dataclass(frozen=True, slots=True)
class MapPrediction:
    """A surrogate prediction with uncertainty, validity, and provenance."""

    outputs: Mapping[str, float]
    uncertainty: Mapping[str, float]
    inside_validity: bool
    extrapolated: bool
    requires_escalation: bool
    trusted: bool
    source: MapFidelity
    model_family: str
    map_digest: str
    validity: Validity

    def __post_init__(self) -> None:
        object.__setattr__(self, "outputs", {str(k): float(v) for k, v in self.outputs.items()})
        object.__setattr__(
            self, "uncertainty", {str(k): float(v) for k, v in self.uncertainty.items()}
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "outputs": dict(sorted(self.outputs.items())),
            "uncertainty": dict(sorted(self.uncertainty.items())),
            "insideValidity": self.inside_validity,
            "extrapolated": self.extrapolated,
            "requiresEscalation": self.requires_escalation,
            "trusted": self.trusted,
            "source": self.source.value,
            "modelFamily": self.model_family,
            "mapDigest": self.map_digest,
            "validity": self.validity.canonical(),
        }


@dataclass(frozen=True, slots=True)
class PerformanceMap:
    """A fitted, revisioned, hashable N-D performance map."""

    map_id: str
    revision: int
    variables: tuple[IndependentVariable, ...]
    outputs: tuple[OutputVariable, ...]
    model: SurrogateModel
    samples: tuple[MapSample, ...]
    extrapolation: ExtrapolationPolicy = ExtrapolationPolicy.REJECT
    validation: Any | None = None
    parent_revision: int | None = None
    software: SoftwareIdentity = field(default_factory=SoftwareIdentity)
    provenance: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.map_id.strip():
            raise MapContractError("MAP_ID_REQUIRED")
        if self.revision < 0:
            raise MapContractError("MAP_REVISION_MUST_BE_NONNEGATIVE")
        if not self.variables or not self.outputs:
            raise MapContractError("MAP_NEEDS_VARIABLES_AND_OUTPUTS")
        variable_names = [variable.name for variable in self.variables]
        output_names = [output.name for output in self.outputs]
        if len(set(variable_names)) != len(variable_names):
            raise MapContractError("MAP_DUPLICATE_VARIABLE")
        if len(set(output_names)) != len(output_names):
            raise MapContractError("MAP_DUPLICATE_OUTPUT")
        if not self.samples:
            raise MapContractError("MAP_NEEDS_SAMPLES")
        object.__setattr__(self, "provenance", dict(self.provenance))
        expected_inputs = set(variable_names)
        expected_outputs = set(output_names)
        for sample in self.samples:
            if set(sample.inputs) != expected_inputs:
                raise MapContractError(f"SAMPLE_INPUTS_DO_NOT_MATCH_MAP:{sample.sample_id}")
            if set(sample.outputs) != expected_outputs:
                raise MapContractError(f"SAMPLE_OUTPUTS_DO_NOT_MATCH_MAP:{sample.sample_id}")

    @property
    def source_label(self) -> MapFidelity:
        """Predictions from a fitted map are always surrogate, never native."""

        return MapFidelity.SURROGATE

    def validity_domain(self) -> dict[str, tuple[float, float]]:
        domain: dict[str, tuple[float, float]] = {}
        for variable in self.variables:
            values = [sample.inputs[variable.name] for sample in self.samples]
            domain[variable.name] = (min(values), max(values))
        return domain

    def contains(self, point: Mapping[str, float]) -> bool:
        self._check_point(point)
        for variable in self.variables:
            value = float(point[variable.name])
            low, high = self.validity_domain()[variable.name]
            if not variable.contains(value):
                return False
            if value < low or value > high:
                return False
        return True

    def sample_ids(self) -> tuple[str, ...]:
        return tuple(sorted(sample.sample_id for sample in self.samples))

    def predict(
        self, point: Mapping[str, float], *, policy: ExtrapolationPolicy | None = None
    ) -> MapPrediction:
        self._check_point(point)
        active = self.extrapolation if policy is None else policy
        inside = self.contains(point)
        extrapolated = False
        requires_escalation = False
        query = {name: float(value) for name, value in point.items()}
        if not inside:
            if active is ExtrapolationPolicy.REJECT:
                raise ExtrapolationError(f"EXTRAPOLATION_REJECTED:{self.map_id}")
            if active is ExtrapolationPolicy.CLAMP:
                query = self._clamp(query)
                extrapolated = True
            else:
                extrapolated = True
                requires_escalation = True
        raw = self.model.predict(query)
        return MapPrediction(
            outputs=raw.outputs,
            uncertainty=raw.uncertainty,
            inside_validity=inside,
            extrapolated=extrapolated,
            requires_escalation=requires_escalation,
            trusted=self.validation is not None,
            source=self.source_label,
            model_family=self.model.family,
            map_digest=self.digest(),
            validity=Validity(
                passed=inside,
                checks={"inside-validity": inside, "validated": self.validation is not None},
                detail="" if inside else "query outside declared validity domain",
            ),
        )

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "mapId": self.map_id,
            "revision": self.revision,
            "parentRevision": self.parent_revision,
            "variables": [
                {
                    "name": variable.name,
                    "unit": variable.unit,
                    "kind": variable.kind.value,
                    "lower": variable.lower,
                    "upper": variable.upper,
                    "values": list(variable.values),
                }
                for variable in self.variables
            ],
            "outputs": [
                {"name": output.name, "unit": output.unit} for output in self.outputs
            ],
            "modelFamily": self.model.family,
            "modelConfig": self.model.config(),
            "extrapolation": self.extrapolation.value,
            "validityDomain": {
                name: [low, high] for name, (low, high) in self.validity_domain().items()
            },
            "sourceSampleIds": list(self.sample_ids()),
            "samples": [sample.as_dict() for sample in self.samples],
            "software": self.software.canonical(),
            "provenance": dict(sorted(self.provenance.items())),
        }

    def digest(self) -> str:
        return content_digest(self.canonical_payload())

    def with_revision(
        self,
        *,
        revision: int,
        model: SurrogateModel | None = None,
        samples: tuple[MapSample, ...] | None = None,
        validation: Any | None = None,
        provenance: Mapping[str, Any] | None = None,
    ) -> PerformanceMap:
        return PerformanceMap(
            map_id=self.map_id,
            revision=revision,
            variables=self.variables,
            outputs=self.outputs,
            model=self.model if model is None else model,
            samples=self.samples if samples is None else samples,
            extrapolation=self.extrapolation,
            validation=self.validation if validation is None else validation,
            parent_revision=self.revision,
            software=self.software,
            provenance=self.provenance if provenance is None else provenance,
        )

    def _check_point(self, point: Mapping[str, float]) -> None:
        names = {variable.name for variable in self.variables}
        if set(point) != names:
            missing = sorted(names - set(point))
            unknown = sorted(set(point) - names)
            raise MapContractError(f"MAP_POINT_FIELDS_MISMATCH:{missing}:{unknown}")

    def _clamp(self, point: Mapping[str, float]) -> dict[str, float]:
        clamped: dict[str, float] = {}
        for variable in self.variables:
            low, high = self.validity_domain()[variable.name]
            clamped[variable.name] = min(max(float(point[variable.name]), low), high)
        return clamped


def build_map(
    *,
    map_id: str,
    variables: Sequence[IndependentVariable],
    outputs: Sequence[OutputVariable],
    samples: Sequence[MapSample],
    model: SurrogateModel,
    revision: int = 1,
    extrapolation: ExtrapolationPolicy = ExtrapolationPolicy.REJECT,
    parent_revision: int | None = None,
    provenance: Mapping[str, Any] | None = None,
) -> PerformanceMap:
    """Fit a model on the declared samples and return the map contract."""

    model.fit(
        [dict(sample.inputs) for sample in samples],
        [dict(sample.outputs) for sample in samples],
    )
    return PerformanceMap(
        map_id=map_id,
        revision=revision,
        variables=tuple(variables),
        outputs=tuple(outputs),
        model=model,
        samples=tuple(samples),
        extrapolation=extrapolation,
        parent_revision=parent_revision,
        provenance=provenance or {},
    )
