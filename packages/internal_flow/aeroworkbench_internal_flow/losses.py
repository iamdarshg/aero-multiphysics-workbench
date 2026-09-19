"""Branch loss models that turn geometry plus correlations into a flow law.

Each model is a frozen, sourced contract. Temperature-dependent properties are
taken from the evaluated :class:`BranchState` at both ends of the branch, so a
fluid with no transport model fails closed (the Reynolds number cannot be
formed) instead of silently using a constant viscosity.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite, pi

from .correlations import (
    ANNULAR_SEAL_LAMINAR,
    CHURCHILL_FRICTION,
    INCOMPRESSIBLE_ORIFICE,
    DeclaredCoefficient,
    annular_seal_linear_resistance,
    churchill_friction_factor,
    churchill_friction_factor_unchecked,
    require_annular_seal_validity,
    require_orifice_validity,
)
from .errors import InternalFlowCapabilityUnavailableError, InternalFlowValidationError
from .states import BranchState, HydraulicResistance, LossEvaluation, ModelReference

__all__ = [
    "DuctLoss",
    "ExplicitResistance",
    "LossModel",
    "OrificeLoss",
    "SealLoss",
    "ValveLoss",
    "evaluate_loss_model",
    "loss_model_payload",
    "mean_density",
    "mean_viscosity",
]


def mean_density(first: BranchState, second: BranchState) -> float:
    return 0.5 * (first.density_kg_m3 + second.density_kg_m3)


def mean_viscosity(first: BranchState, second: BranchState, *, model_id: str) -> float:
    if first.viscosity_pa_s is None or second.viscosity_pa_s is None:
        raise InternalFlowCapabilityUnavailableError(
            f"MISSING_TRANSPORT_FOR_REYNOLDS_NUMBER:{model_id}"
        )
    return 0.5 * (first.viscosity_pa_s + second.viscosity_pa_s)


def _positive(value: float, name: str) -> float:
    if not isfinite(value) or value <= 0.0:
        raise InternalFlowValidationError(f"{name.upper()}_MUST_BE_POSITIVE")
    return float(value)


@dataclass(frozen=True, slots=True)
class ExplicitResistance:
    """A directly declared flow law; the source names where it came from."""

    linear_pa_s_m3: float
    quadratic_pa_s2_m6: float
    source: str
    version: str = "1.0"

    def __post_init__(self) -> None:
        HydraulicResistance(self.linear_pa_s_m3, self.quadratic_pa_s2_m6)
        if not self.source.strip():
            raise InternalFlowValidationError("EXPLICIT_RESISTANCE_SOURCE_REQUIRED")


@dataclass(frozen=True, slots=True)
class DuctLoss:
    """Distributed duct/pipe friction plus an optional minor loss."""

    length_m: float
    diameter_m: float
    roughness_m: float
    source: str
    minor_loss_coefficient: DeclaredCoefficient | None = None
    version: str = "1.0"

    def __post_init__(self) -> None:
        _positive(self.length_m, "length")
        _positive(self.diameter_m, "diameter")
        if not isfinite(self.roughness_m) or self.roughness_m < 0.0:
            raise InternalFlowValidationError("ROUGHNESS_MUST_BE_NONNEGATIVE")
        if not self.source.strip():
            raise InternalFlowValidationError("DUCT_LOSS_SOURCE_REQUIRED")

    @property
    def area_m2(self) -> float:
        return pi * self.diameter_m**2 / 4.0


@dataclass(frozen=True, slots=True)
class OrificeLoss:
    """Incompressible orifice with a declared discharge coefficient."""

    area_m2: float
    discharge_coefficient: DeclaredCoefficient
    source: str
    version: str = "1.0"

    def __post_init__(self) -> None:
        _positive(self.area_m2, "area")
        if not self.source.strip():
            raise InternalFlowValidationError("ORIFICE_LOSS_SOURCE_REQUIRED")


@dataclass(frozen=True, slots=True)
class ValveLoss:
    """Minor-loss valve with a declared loss coefficient K."""

    area_m2: float
    loss_coefficient: DeclaredCoefficient
    source: str
    version: str = "1.0"

    def __post_init__(self) -> None:
        _positive(self.area_m2, "area")
        if not self.source.strip():
            raise InternalFlowValidationError("VALVE_LOSS_SOURCE_REQUIRED")


@dataclass(frozen=True, slots=True)
class SealLoss:
    """Laminar annular clearance leakage path."""

    diameter_m: float
    clearance_m: float
    length_m: float
    source: str
    version: str = "1.0"

    def __post_init__(self) -> None:
        _positive(self.diameter_m, "diameter")
        _positive(self.clearance_m, "clearance")
        _positive(self.length_m, "length")
        if not self.source.strip():
            raise InternalFlowValidationError("SEAL_LOSS_SOURCE_REQUIRED")


LossModel = ExplicitResistance | DuctLoss | OrificeLoss | ValveLoss | SealLoss


def _explicit(model: ExplicitResistance) -> tuple[HydraulicResistance, LossEvaluation]:
    resistance = HydraulicResistance(model.linear_pa_s_m3, model.quadratic_pa_s2_m6)
    return resistance, LossEvaluation(None, None, (), (model.source,))


def _duct(
    model: DuctLoss,
    mass_flow_kg_s: float,
    from_state: BranchState,
    to_state: BranchState,
    *,
    enforce_validity: bool,
) -> tuple[HydraulicResistance, LossEvaluation]:
    area = model.area_m2
    viscosity = mean_viscosity(from_state, to_state, model_id="duct-loss")
    reynolds = abs(mass_flow_kg_s) * model.diameter_m / (area * viscosity)
    relative_roughness = model.roughness_m / model.diameter_m
    if reynolds <= 0.0:
        friction = 0.0
    elif enforce_validity:
        friction = churchill_friction_factor(reynolds, relative_roughness)
    else:
        friction = churchill_friction_factor_unchecked(reynolds, relative_roughness)
    quadratic = friction * model.length_m / (2.0 * model.diameter_m * area * area)
    references: list[ModelReference] = [CHURCHILL_FRICTION]
    notes: list[str] = []
    if model.minor_loss_coefficient is not None:
        quadratic += model.minor_loss_coefficient.value / (2.0 * area * area)
        references.append(model.minor_loss_coefficient)
        notes.append(f"minor-loss:{model.minor_loss_coefficient.name}")
    return (
        HydraulicResistance(0.0, quadratic),
        LossEvaluation(reynolds, friction, tuple(references), tuple(notes)),
    )


def _orifice(
    model: OrificeLoss, from_state: BranchState, to_state: BranchState, *, enforce_validity: bool
) -> tuple[HydraulicResistance, LossEvaluation]:
    upstream_pressure = max(from_state.pressure_pa, to_state.pressure_pa)
    reference_drop = abs(from_state.pressure_pa - to_state.pressure_pa)
    if enforce_validity:
        require_orifice_validity(reference_drop, upstream_pressure)
    coefficient = model.discharge_coefficient.value
    if coefficient <= 0.0:
        raise InternalFlowValidationError("ORIFICE_CD_MUST_BE_POSITIVE")
    quadratic = 1.0 / (2.0 * (coefficient * model.area_m2) ** 2)
    return (
        HydraulicResistance(0.0, quadratic),
        LossEvaluation(
            None,
            None,
            (INCOMPRESSIBLE_ORIFICE, model.discharge_coefficient),
            (f"discharge-coefficient:{model.discharge_coefficient.name}",),
        ),
    )


def _valve(model: ValveLoss) -> tuple[HydraulicResistance, LossEvaluation]:
    coefficient = model.loss_coefficient.value
    if coefficient < 0.0:
        raise InternalFlowValidationError("VALVE_K_MUST_BE_NONNEGATIVE")
    quadratic = coefficient / (2.0 * model.area_m2 * model.area_m2)
    return (
        HydraulicResistance(0.0, quadratic),
        LossEvaluation(
            None,
            None,
            (model.loss_coefficient,),
            (f"loss-coefficient:{model.loss_coefficient.name}",),
        ),
    )


def _seal(
    model: SealLoss,
    mass_flow_kg_s: float,
    from_state: BranchState,
    to_state: BranchState,
    *,
    enforce_validity: bool,
) -> tuple[HydraulicResistance, LossEvaluation]:
    viscosity = mean_viscosity(from_state, to_state, model_id="seal-loss")
    area = pi * model.diameter_m * model.clearance_m
    hydraulic_diameter = 2.0 * model.clearance_m
    reynolds = abs(mass_flow_kg_s) * hydraulic_diameter / (area * viscosity)
    clearance_ratio = model.clearance_m / model.diameter_m
    length_ratio = model.length_m / model.diameter_m
    if enforce_validity:
        require_annular_seal_validity(
            reynolds_number=reynolds,
            clearance_ratio=clearance_ratio,
            length_ratio=length_ratio,
        )
    linear = annular_seal_linear_resistance(
        diameter_m=model.diameter_m,
        clearance_m=model.clearance_m,
        length_m=model.length_m,
        viscosity_pa_s=viscosity,
    )
    return (
        HydraulicResistance(linear, 0.0),
        LossEvaluation(reynolds, None, (ANNULAR_SEAL_LAMINAR,), ()),
    )


def evaluate_loss_model(
    model: LossModel,
    *,
    mass_flow_kg_s: float,
    from_state: BranchState,
    to_state: BranchState,
    enforce_validity: bool = True,
) -> tuple[HydraulicResistance, LossEvaluation]:
    """Evaluate any loss model into the one generic hydraulic-resistance contract.

    ``enforce_validity`` is disabled only for intermediate Newton iterates; the
    final reported branch is always evaluated with validity enforced.
    """
    if isinstance(model, ExplicitResistance):
        return _explicit(model)
    if isinstance(model, DuctLoss):
        return _duct(
            model, mass_flow_kg_s, from_state, to_state, enforce_validity=enforce_validity
        )
    if isinstance(model, OrificeLoss):
        return _orifice(model, from_state, to_state, enforce_validity=enforce_validity)
    if isinstance(model, ValveLoss):
        return _valve(model)
    if isinstance(model, SealLoss):
        return _seal(
            model, mass_flow_kg_s, from_state, to_state, enforce_validity=enforce_validity
        )
    raise InternalFlowValidationError("UNKNOWN_LOSS_MODEL")


def loss_model_payload(model: LossModel) -> dict[str, object]:
    """Deterministic, JSON-safe description of a loss model for provenance."""
    if isinstance(model, ExplicitResistance):
        return {
            "kind": "explicit_resistance",
            "linearPaSM3": model.linear_pa_s_m3,
            "quadraticPaS2M6": model.quadratic_pa_s2_m6,
            "source": model.source,
            "version": model.version,
        }
    if isinstance(model, DuctLoss):
        return {
            "kind": "duct_loss",
            "lengthM": model.length_m,
            "diameterM": model.diameter_m,
            "roughnessM": model.roughness_m,
            "minorLossCoefficient": (
                None
                if model.minor_loss_coefficient is None
                else model.minor_loss_coefficient.canonical()
            ),
            "source": model.source,
            "version": model.version,
        }
    if isinstance(model, OrificeLoss):
        return {
            "kind": "orifice_loss",
            "areaM2": model.area_m2,
            "dischargeCoefficient": model.discharge_coefficient.canonical(),
            "source": model.source,
            "version": model.version,
        }
    if isinstance(model, ValveLoss):
        return {
            "kind": "valve_loss",
            "areaM2": model.area_m2,
            "lossCoefficient": model.loss_coefficient.canonical(),
            "source": model.source,
            "version": model.version,
        }
    if isinstance(model, SealLoss):
        return {
            "kind": "seal_loss",
            "diameterM": model.diameter_m,
            "clearanceM": model.clearance_m,
            "lengthM": model.length_m,
            "source": model.source,
            "version": model.version,
        }
    raise InternalFlowValidationError("UNKNOWN_LOSS_MODEL")
