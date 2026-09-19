"""Uncertain-variable contracts: distributions, provenance, and classification.

An :class:`UncertainVariable` is generic: a name, a unit, a declared
distribution, an uncertainty class (aleatory vs epistemic vs model-form), and a
provenance record naming where the distribution came from. Correlation is
declared separately, so a variable contract never embeds application logic.

Epistemic and model-form uncertainty are deliberately first-class. Model-form
discrepancy is attached to a *fidelity* and marked trusted or not: a cheap
surrogate's model error is epistemic, can never be converted into physical
randomness, and can never by itself yield a reliability claim.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from math import isfinite
from typing import Any

from aeroworkbench_optimization.design_space import content_digest
from aeroworkbench_rom.contracts import SoftwareIdentity

from .distributions import Distribution, DistributionKind
from .errors import UncertaintyError

__all__ = [
    "SOFTWARE_NAME",
    "SOFTWARE_VERSION",
    "CorrelationSpec",
    "ModelFormUncertainty",
    "UncertainVariable",
    "UncertaintyClass",
    "UncertaintySource",
    "UncertaintySpec",
    "VariableProvenance",
    "deterministic_variable",
]

SOFTWARE_NAME = "aeroworkbench-vehicle-systems-robust"
SOFTWARE_VERSION = "1.0.0"


class UncertaintyClass(StrEnum):
    """Whether scatter is physical, reducible by knowledge, or model error."""

    ALEATORY = "aleatory"
    EPISTEMIC = "epistemic"
    MODEL_FORM = "model-form"


class UncertaintySource(StrEnum):
    """Named, generic provenance families for an uncertain variable."""

    MANUFACTURING_TOLERANCE = "manufacturing-tolerance"
    MATERIAL_SCATTER = "material-scatter"
    MASS_CG_VARIATION = "mass-cg-variation"
    ATMOSPHERE_WEATHER = "atmosphere-weather"
    AERODYNAMIC_MODEL_DISCREPANCY = "aerodynamic-model-discrepancy"
    PROPULSION_VARIATION = "propulsion-variation"
    CONTROL_SENSOR = "control-sensor"
    EXPERIMENT_CALIBRATION = "experiment-calibration"
    EXPERT_ELICITATION = "expert-elicitation"


@dataclass(frozen=True, slots=True)
class VariableProvenance:
    """Where an uncertain variable's distribution came from."""

    source: UncertaintySource
    reference: str
    revision: str = "1"
    detail: str = ""

    def __post_init__(self) -> None:
        if not self.reference.strip():
            raise UncertaintyError("PROVENANCE_REFERENCE_REQUIRED")
        if not self.revision.strip():
            raise UncertaintyError("PROVENANCE_REVISION_REQUIRED")

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "source": self.source.value,
            "reference": self.reference,
            "revision": self.revision,
            "detail": self.detail,
        }

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> VariableProvenance:
        return cls(
            source=UncertaintySource(str(payload["source"])),
            reference=str(payload["reference"]),
            revision=str(payload.get("revision", "1")),
            detail=str(payload.get("detail", "")),
        )


@dataclass(frozen=True, slots=True)
class UncertainVariable:
    """A declared uncertain input with unit, distribution, and provenance."""

    name: str
    unit: str
    distribution: Distribution
    provenance: VariableProvenance
    uncertainty_class: UncertaintyClass = UncertaintyClass.ALEATORY
    group: str | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise UncertaintyError("UNCERTAIN_VARIABLE_NAME_REQUIRED")
        if not self.unit.strip():
            raise UncertaintyError(f"UNCERTAIN_VARIABLE_UNIT_REQUIRED:{self.name}")
        if self.group is not None and not self.group.strip():
            raise UncertaintyError(f"UNCERTAIN_VARIABLE_GROUP_EMPTY:{self.name}")

    def canonical_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": self.name,
            "unit": self.unit,
            "uncertaintyClass": self.uncertainty_class.value,
            "distribution": self.distribution.canonical_payload(),
            "provenance": self.provenance.canonical_payload(),
        }
        if self.group is not None:
            payload["group"] = self.group
        return payload

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> UncertainVariable:
        group = payload.get("group")
        return cls(
            name=str(payload["name"]),
            unit=str(payload["unit"]),
            distribution=Distribution.from_payload(payload["distribution"]),
            provenance=VariableProvenance.from_payload(payload["provenance"]),
            uncertainty_class=UncertaintyClass(
                str(payload.get("uncertaintyClass", UncertaintyClass.ALEATORY.value))
            ),
            group=None if group is None else str(group),
        )


@dataclass(frozen=True, slots=True)
class CorrelationSpec:
    """A declared pairwise Pearson correlation between two variables."""

    name_a: str
    name_b: str
    coefficient: float

    def __post_init__(self) -> None:
        if not self.name_a.strip() or not self.name_b.strip():
            raise UncertaintyError("CORRELATION_NEEDS_TWO_NAMES")
        if self.name_a == self.name_b:
            raise UncertaintyError(f"CORRELATION_SELF_REFERENCE:{self.name_a}")
        if not isfinite(self.coefficient) or not -1.0 <= self.coefficient <= 1.0:
            raise UncertaintyError("CORRELATION_COEFFICIENT_OUT_OF_RANGE")

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "nameA": self.name_a,
            "nameB": self.name_b,
            "coefficient": self.coefficient,
        }

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> CorrelationSpec:
        return cls(
            name_a=str(payload["nameA"]),
            name_b=str(payload["nameB"]),
            coefficient=float(payload["coefficient"]),
        )


@dataclass(frozen=True, slots=True)
class ModelFormUncertainty:
    """Model-form discrepancy attached to one fidelity.

    ``trusted`` states whether this fidelity's predictions may support a
    reliability claim. A fine surrogate is still not native physics, so the
    default is ``False`` and reliability remains fail-closed until a trusted
    observation exists.
    """

    fidelity: str
    response: str
    distribution: Distribution
    provenance: VariableProvenance
    trusted: bool = False
    uncertainty_class: UncertaintyClass = UncertaintyClass.MODEL_FORM

    def __post_init__(self) -> None:
        if not self.fidelity.strip():
            raise UncertaintyError("MODEL_FORM_NEEDS_FIDELITY")
        if not self.response.strip():
            raise UncertaintyError("MODEL_FORM_NEEDS_RESPONSE")
        if self.uncertainty_class is not UncertaintyClass.MODEL_FORM:
            raise UncertaintyError("MODEL_FORM_CLASS_MUST_BE_MODEL_FORM")

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "fidelity": self.fidelity,
            "response": self.response,
            "trusted": self.trusted,
            "uncertaintyClass": self.uncertainty_class.value,
            "distribution": self.distribution.canonical_payload(),
            "provenance": self.provenance.canonical_payload(),
        }

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> ModelFormUncertainty:
        return cls(
            fidelity=str(payload["fidelity"]),
            response=str(payload.get("response", "")),
            distribution=Distribution.from_payload(payload["distribution"]),
            provenance=VariableProvenance.from_payload(payload["provenance"]),
            trusted=bool(payload.get("trusted", False)),
        )


@dataclass(frozen=True, slots=True)
class UncertaintySpec:
    """A complete, hashable uncertain-input contract for one study."""

    spec_id: str
    variables: tuple[UncertainVariable, ...]
    correlations: tuple[CorrelationSpec, ...] = ()
    model_form: tuple[ModelFormUncertainty, ...] = ()
    software: SoftwareIdentity = field(
        default_factory=lambda: SoftwareIdentity(name=SOFTWARE_NAME, version=SOFTWARE_VERSION)
    )

    def __post_init__(self) -> None:
        if not self.spec_id.strip():
            raise UncertaintyError("UNCERTAINTY_SPEC_NEEDS_ID")
        if not self.variables:
            raise UncertaintyError("UNCERTAINTY_SPEC_NEEDS_VARIABLES")
        names = [variable.name for variable in self.variables]
        if len(names) != len(set(names)):
            raise UncertaintyError("UNCERTAINTY_SPEC_DUPLICATE_VARIABLE")
        known = set(names)
        for correlation in self.correlations:
            for name in (correlation.name_a, correlation.name_b):
                if name not in known:
                    raise UncertaintyError(f"CORRELATION_UNKNOWN_VARIABLE:{name}")
        seen_pairs: set[tuple[str, str]] = set()
        for correlation in self.correlations:
            left, right = sorted((correlation.name_a, correlation.name_b))
            pair: tuple[str, str] = (left, right)
            if pair in seen_pairs:
                raise UncertaintyError(f"DUPLICATE_CORRELATION:{pair[0]}:{pair[1]}")
            seen_pairs.add(pair)
        fidelities = [item.fidelity for item in self.model_form]
        if len(fidelities) != len(set(fidelities)):
            raise UncertaintyError("DUPLICATE_MODEL_FORM_FIDELITY")

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(variable.name for variable in self.variables)

    def index(self) -> dict[str, UncertainVariable]:
        return {variable.name: variable for variable in self.variables}

    def variable(self, name: str) -> UncertainVariable:
        found = self.index().get(name)
        if found is None:
            raise UncertaintyError(f"UNKNOWN_UNCERTAIN_VARIABLE:{name}")
        return found

    def aleatory(self) -> tuple[UncertainVariable, ...]:
        return tuple(
            variable
            for variable in self.variables
            if variable.uncertainty_class is UncertaintyClass.ALEATORY
        )

    def epistemic(self) -> tuple[UncertainVariable, ...]:
        return tuple(
            variable
            for variable in self.variables
            if variable.uncertainty_class is not UncertaintyClass.ALEATORY
        )

    def model_form_for(self, fidelity: str) -> ModelFormUncertainty | None:
        for item in self.model_form:
            if item.fidelity == fidelity:
                return item
        return None

    def fidelity_is_trusted(self, fidelity: str) -> bool:
        item = self.model_form_for(fidelity)
        return item.trusted if item is not None else False

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "specId": self.spec_id,
            "variables": [variable.canonical_payload() for variable in self.variables],
            "correlations": [item.canonical_payload() for item in self.correlations],
            "modelForm": [item.canonical_payload() for item in self.model_form],
            "software": self.software.canonical(),
        }

    def digest(self) -> str:
        return content_digest(self.canonical_payload())

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> UncertaintySpec:
        return cls(
            spec_id=str(payload["specId"]),
            variables=tuple(
                UncertainVariable.from_payload(item) for item in payload.get("variables", ())
            ),
            correlations=tuple(
                CorrelationSpec.from_payload(item) for item in payload.get("correlations", ())
            ),
            model_form=tuple(
                ModelFormUncertainty.from_payload(item) for item in payload.get("modelForm", ())
            ),
        )


def deterministic_variable(
    name: str,
    unit: str,
    value: float,
    provenance: VariableProvenance,
    *,
    uncertainty_class: UncertaintyClass = UncertaintyClass.ALEATORY,
) -> UncertainVariable:
    """Convenience constructor for a degenerate (spread-free) variable."""

    return UncertainVariable(
        name=name,
        unit=unit,
        distribution=Distribution(DistributionKind.DETERMINISTIC, (value,)),
        provenance=provenance,
        uncertainty_class=uncertainty_class,
    )
