"""Versioned, validity-bounded correlations for internal-flow physics.

Every model here declares a :class:`CorrelationRef` (identity, version, source,
and validity ranges) and every coefficient is a :class:`DeclaredCoefficient`
with a source, so no anonymous constant can enter a result. A query outside a
declared range raises :class:`InternalFlowValidityError` rather than
extrapolating; the caller turns that into a native-CFD escalation request.

Reused property inputs (density, viscosity, conductivity, Prandtl, cp) come
from :mod:`aeroworkbench_fluid_properties`, so the correlations stay valid under
temperature-dependent properties.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import exp, isfinite, log, log10, pi, sqrt
from typing import Any

from aeroworkbench_fluid_properties import FluidValidityError, ValidityRange

from .errors import InternalFlowValidationError, InternalFlowValidityError

__all__ = [
    "ANNULAR_SEAL_LAMINAR",
    "CHURCHILL_FRICTION",
    "COUNTERFLOW_HX",
    "DAILY_NECE_LAMINAR",
    "DAILY_NECE_TURBULENT",
    "DITTUS_BOELTER",
    "HAALAND_FRICTION",
    "INCOMPRESSIBLE_ORIFICE",
    "LABYRINTH_SEAL",
    "LAMINAR_FRICTION",
    "CorrelationRef",
    "DeclaredCoefficient",
    "annular_seal_linear_resistance",
    "annular_seal_mass_flow",
    "churchill_friction_factor",
    "churchill_friction_factor_unchecked",
    "counterflow_effectiveness",
    "duct_convection_coefficient",
    "dittus_boelter_nusselt",
    "haaland_friction_factor",
    "heat_exchanger_duty",
    "labyrinth_seal_mass_flow",
    "laminar_friction_factor",
    "orifice_mass_flow",
    "orifice_pressure_drop",
    "require_annular_seal_validity",
    "require_labyrinth_seal_validity",
    "require_orifice_validity",
    "windage_moment_coefficient",
    "windage_power_w",
]


def _require_positive(value: float, name: str) -> float:
    if not isfinite(value) or value <= 0.0:
        raise InternalFlowValidationError(f"{name.upper()}_MUST_BE_POSITIVE")
    return float(value)


def _require_nonnegative(value: float, name: str) -> float:
    if not isfinite(value) or value < 0.0:
        raise InternalFlowValidationError(f"{name.upper()}_MUST_BE_NONNEGATIVE")
    return float(value)


@dataclass(frozen=True, slots=True)
class CorrelationRef:
    """Identity, version, source, and declared validity of one model."""

    correlation_id: str
    version: str
    source: str
    validity: tuple[ValidityRange, ...] = ()

    def __post_init__(self) -> None:
        if not self.correlation_id.strip():
            raise InternalFlowValidationError("CORRELATION_ID_REQUIRED")
        if not self.version.strip():
            raise InternalFlowValidationError(f"CORRELATION_VERSION_REQUIRED:{self.correlation_id}")
        if not self.source.strip():
            raise InternalFlowValidationError(f"CORRELATION_SOURCE_REQUIRED:{self.correlation_id}")

    def require(self, **values: float) -> None:
        """Fail closed unless every declared validity range has a matching value."""
        for rng in self.validity:
            if rng.quantity not in values:
                raise InternalFlowValidationError(
                    f"CORRELATION_VALIDITY_VALUE_MISSING:{self.correlation_id}:{rng.quantity}"
                )
            try:
                rng.require(values[rng.quantity], label=rng.quantity)
            except FluidValidityError as exc:
                raise InternalFlowValidityError(str(exc)) from exc

    def canonical(self) -> dict[str, Any]:
        return {
            "correlationId": self.correlation_id,
            "version": self.version,
            "source": self.source,
            "validity": [rng.canonical() for rng in self.validity],
        }


@dataclass(frozen=True, slots=True)
class DeclaredCoefficient:
    """A named, sourced coefficient; anonymous constants are rejected."""

    name: str
    value: float
    unit: str
    source: str
    version: str = "1.0"
    validity: ValidityRange | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise InternalFlowValidationError("COEFFICIENT_NAME_REQUIRED")
        if not self.unit.strip():
            raise InternalFlowValidationError(f"COEFFICIENT_UNIT_REQUIRED:{self.name}")
        if not self.source.strip():
            raise InternalFlowValidationError(f"COEFFICIENT_SOURCE_REQUIRED:{self.name}")
        if not isfinite(self.value):
            raise InternalFlowValidationError(f"COEFFICIENT_NONFINITE:{self.name}")

    def require(self, query: float, label: str | None = None) -> float:
        if self.validity is None:
            return float(query)
        try:
            return self.validity.require(query, label=label or self.name)
        except FluidValidityError as exc:
            raise InternalFlowValidityError(str(exc)) from exc

    def canonical(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "unit": self.unit,
            "source": self.source,
            "version": self.version,
            "validity": None if self.validity is None else self.validity.canonical(),
        }


# -- friction -----------------------------------------------------------------

LAMINAR_FRICTION = CorrelationRef(
    "pipe-friction-laminar-hagen-poiseuille",
    "1.0",
    "Hagen-Poiseuille laminar pipe flow, Darcy factor f=64/Re",
    (ValidityRange("reynolds_number", "1", 1e-3, 2300.0),),
)

HAALAND_FRICTION = CorrelationRef(
    "pipe-friction-haaland",
    "1.0",
    "Haaland (1983) explicit turbulent friction approximation",
    (
        ValidityRange("reynolds_number", "1", 4000.0, 1e8),
        ValidityRange("relative_roughness", "1", 0.0, 0.05),
    ),
)

CHURCHILL_FRICTION = CorrelationRef(
    "pipe-friction-churchill",
    "1.0",
    "Churchill (1977) continuous Darcy friction correlation valid for all Re",
    (
        ValidityRange("reynolds_number", "1", 1e-3, 1e9),
        ValidityRange("relative_roughness", "1", 0.0, 0.05),
    ),
)


def laminar_friction_factor(reynolds_number: float) -> float:
    LAMINAR_FRICTION.require(reynolds_number=reynolds_number)
    return 64.0 / reynolds_number


def haaland_friction_factor(reynolds_number: float, relative_roughness: float) -> float:
    HAALAND_FRICTION.require(
        reynolds_number=reynolds_number, relative_roughness=relative_roughness
    )
    inverse = -1.8 * log10((relative_roughness / 3.7) ** 1.11 + 6.9 / reynolds_number)
    return 1.0 / (inverse * inverse)


def churchill_friction_factor(reynolds_number: float, relative_roughness: float) -> float:
    """Continuous Churchill (1977) Darcy friction factor; 64/Re in the laminar limit."""
    CHURCHILL_FRICTION.require(
        reynolds_number=reynolds_number, relative_roughness=relative_roughness
    )
    return churchill_friction_factor_unchecked(reynolds_number, relative_roughness)


def churchill_friction_factor_unchecked(
    reynolds_number: float, relative_roughness: float
) -> float:
    """The Churchill expression without a validity gate, for intermediate iterates."""
    a = (2.457 * log(1.0 / ((7.0 / reynolds_number) ** 0.9 + 0.27 * relative_roughness))) ** 16
    b = (37530.0 / reynolds_number) ** 16
    return float(8.0 * ((8.0 / reynolds_number) ** 12 + 1.0 / (a + b) ** 1.5) ** (1.0 / 12.0))


# -- orifice ------------------------------------------------------------------

INCOMPRESSIBLE_ORIFICE = CorrelationRef(
    "orifice-incompressible-discharge",
    "1.0",
    "incompressible orifice equation m=Cd A sqrt(2 rho dp)",
    (ValidityRange("pressure_ratio", "1", 0.0, 0.1),),
)


def require_orifice_validity(pressure_drop_pa: float, upstream_pressure_pa: float) -> float:
    _require_positive(upstream_pressure_pa, "upstream_pressure")
    pressure_ratio = abs(pressure_drop_pa) / upstream_pressure_pa
    INCOMPRESSIBLE_ORIFICE.require(pressure_ratio=pressure_ratio)
    return pressure_ratio


def orifice_pressure_drop(
    *, mass_flow_kg_s: float, density_kg_m3: float, area_m2: float, discharge_coefficient: float
) -> float:
    _require_positive(density_kg_m3, "density")
    _require_positive(area_m2, "area")
    _require_positive(discharge_coefficient, "discharge_coefficient")
    velocity_scale = mass_flow_kg_s / (density_kg_m3 * discharge_coefficient * area_m2)
    return 0.5 * density_kg_m3 * velocity_scale * abs(velocity_scale)


def orifice_mass_flow(
    *, pressure_drop_pa: float, density_kg_m3: float, area_m2: float, discharge_coefficient: float
) -> float:
    _require_positive(density_kg_m3, "density")
    _require_positive(area_m2, "area")
    _require_positive(discharge_coefficient, "discharge_coefficient")
    magnitude = discharge_coefficient * area_m2 * sqrt(2.0 * density_kg_m3 * abs(pressure_drop_pa))
    return magnitude if pressure_drop_pa >= 0.0 else -magnitude


# -- seals --------------------------------------------------------------------

ANNULAR_SEAL_LAMINAR = CorrelationRef(
    "annular-seal-laminar-poiseuille",
    "1.0",
    "laminar pressure-driven annular clearance flow",
    (
        ValidityRange("reynolds_number", "1", 0.0, 2000.0),
        ValidityRange("clearance_ratio", "1", 0.0, 0.01),
        ValidityRange("length_ratio", "1", 0.1, 1e4),
    ),
)

LABYRINTH_SEAL = CorrelationRef(
    "labyrinth-seal-egli",
    "1.0",
    "Egli carry-over labyrinth leakage model m=Cd A sqrt(2 rho dp / carry-over)",
    (ValidityRange("pressure_ratio", "1", 0.0, 0.9),),
)


def require_annular_seal_validity(
    *, reynolds_number: float, clearance_ratio: float, length_ratio: float
) -> None:
    ANNULAR_SEAL_LAMINAR.require(
        reynolds_number=reynolds_number,
        clearance_ratio=clearance_ratio,
        length_ratio=length_ratio,
    )


def require_labyrinth_seal_validity(pressure_ratio: float) -> None:
    LABYRINTH_SEAL.require(pressure_ratio=pressure_ratio)


def annular_seal_linear_resistance(
    *, diameter_m: float, clearance_m: float, length_m: float, viscosity_pa_s: float
) -> float:
    """dp = R * Q for laminar annular clearance flow; R in Pa*s/m^3."""
    _require_positive(diameter_m, "diameter")
    _require_positive(clearance_m, "clearance")
    _require_positive(length_m, "length")
    _require_positive(viscosity_pa_s, "viscosity")
    return 12.0 * viscosity_pa_s * length_m / (pi * diameter_m * clearance_m**3)


def annular_seal_mass_flow(
    *,
    diameter_m: float,
    clearance_m: float,
    length_m: float,
    viscosity_pa_s: float,
    density_kg_m3: float,
    pressure_drop_pa: float,
) -> float:
    resistance = annular_seal_linear_resistance(
        diameter_m=diameter_m,
        clearance_m=clearance_m,
        length_m=length_m,
        viscosity_pa_s=viscosity_pa_s,
    )
    return density_kg_m3 * pressure_drop_pa / resistance


def labyrinth_seal_mass_flow(
    *,
    discharge_coefficient: float,
    area_m2: float,
    density_kg_m3: float,
    pressure_drop_pa: float,
    carry_over_factor: float,
) -> float:
    _require_positive(discharge_coefficient, "discharge_coefficient")
    _require_positive(area_m2, "area")
    _require_positive(density_kg_m3, "density")
    if not isfinite(carry_over_factor) or carry_over_factor < 1.0:
        raise InternalFlowValidationError("LABYRINTH_CARRY_OVER_FACTOR_BELOW_ONE")
    magnitude = (
        discharge_coefficient
        * area_m2
        * sqrt(2.0 * density_kg_m3 * abs(pressure_drop_pa) / carry_over_factor)
    )
    return magnitude if pressure_drop_pa >= 0.0 else -magnitude


# -- heat transfer ------------------------------------------------------------

COUNTERFLOW_HX = CorrelationRef(
    "counterflow-effectiveness-ntu",
    "1.0",
    "counter-flow heat-exchanger effectiveness-NTU analytical relation",
    (),
)


DITTUS_BOELTER = CorrelationRef(
    "dittus-boelter-turbulent-tube",
    "1.0",
    "Dittus-Boelter Nu=0.023 Re^0.8 Pr^n (n=0.4 heating, 0.3 cooling); L/D>=10",
    (
        ValidityRange("reynolds_number", "1", 1.0e4, 1.2e5),
        ValidityRange("prandtl_number", "1", 0.7, 160.0),
        ValidityRange("length_diameter_ratio", "1", 10.0, 1e6),
    ),
)


def dittus_boelter_nusselt(
    *, reynolds_number: float, prandtl_number: float, length_diameter_ratio: float, heating: bool
) -> float:
    DITTUS_BOELTER.require(
        reynolds_number=reynolds_number,
        prandtl_number=prandtl_number,
        length_diameter_ratio=length_diameter_ratio,
    )
    exponent = 0.4 if heating else 0.3
    return float(0.023 * reynolds_number**0.8 * prandtl_number**exponent)


def duct_convection_coefficient(
    *,
    reynolds_number: float,
    prandtl_number: float,
    length_diameter_ratio: float,
    conductivity_w_m_k: float,
    diameter_m: float,
    heating: bool,
) -> float:
    _require_positive(conductivity_w_m_k, "conductivity")
    _require_positive(diameter_m, "diameter")
    nusselt = dittus_boelter_nusselt(
        reynolds_number=reynolds_number,
        prandtl_number=prandtl_number,
        length_diameter_ratio=length_diameter_ratio,
        heating=heating,
    )
    return nusselt * conductivity_w_m_k / diameter_m


def _safe_exp(value: float) -> float:
    return exp(value) if value < 700.0 else float("inf")


def counterflow_effectiveness(ntu: float, capacity_ratio: float) -> float:
    """Counter-flow heat-exchanger effectiveness (analytical, deterministic)."""
    if not isfinite(ntu) or ntu < 0.0:
        raise InternalFlowValidationError("NTU_MUST_BE_NONNEGATIVE")
    if not isfinite(capacity_ratio) or not 0.0 <= capacity_ratio <= 1.0:
        raise InternalFlowValidationError("CAPACITY_RATIO_OUT_OF_RANGE")
    if ntu == 0.0:
        return 0.0
    if capacity_ratio == 1.0:
        return ntu / (1.0 + ntu)
    factor = (1.0 - capacity_ratio) * ntu
    denominator = 1.0 - capacity_ratio * _safe_exp(-factor)
    return (1.0 - _safe_exp(-factor)) / denominator


def heat_exchanger_duty(
    *,
    effectiveness: float,
    hot_capacity_rate_w_k: float,
    hot_inlet_k: float,
    cold_inlet_k: float,
) -> float:
    if not 0.0 <= effectiveness <= 1.0:
        raise InternalFlowValidationError("EFFECTIVENESS_OUT_OF_RANGE")
    _require_nonnegative(hot_capacity_rate_w_k, "capacity_rate")
    return effectiveness * hot_capacity_rate_w_k * (hot_inlet_k - cold_inlet_k)


# -- rotating cavity / windage ------------------------------------------------

DAILY_NECE_LAMINAR = CorrelationRef(
    "daily-nece-windage-moment-laminar",
    "1.0",
    "Daily & Nece laminar disk moment coefficient Cm=3.87 Re_phi^-0.5",
    (ValidityRange("rotational_reynolds", "1", 1.0, 3.0e5),),
)

DAILY_NECE_TURBULENT = CorrelationRef(
    "daily-nece-windage-moment-turbulent",
    "1.0",
    "Daily & Nece turbulent disk moment coefficient Cm=0.073 Re_phi^-0.2",
    (ValidityRange("rotational_reynolds", "1", 3.0e5, 1e9),),
)


def windage_moment_coefficient(rotational_reynolds: float) -> tuple[float, CorrelationRef]:
    """Return the disk moment coefficient and the correlation that produced it."""
    if rotational_reynolds < 3.0e5:
        DAILY_NECE_LAMINAR.require(rotational_reynolds=rotational_reynolds)
        return 3.87 * rotational_reynolds**-0.5, DAILY_NECE_LAMINAR
    DAILY_NECE_TURBULENT.require(rotational_reynolds=rotational_reynolds)
    return 0.073 * rotational_reynolds**-0.2, DAILY_NECE_TURBULENT


def windage_power_w(
    *,
    density_kg_m3: float,
    angular_velocity_rad_s: float,
    radius_m: float,
    moment_coefficient: float,
    sides: int = 1,
) -> float:
    _require_positive(density_kg_m3, "density")
    _require_nonnegative(angular_velocity_rad_s, "angular_velocity")
    _require_positive(radius_m, "radius")
    if not isfinite(moment_coefficient) or moment_coefficient < 0.0:
        raise InternalFlowValidationError("MOMENT_COEFFICIENT_NONNEGATIVE_REQUIRED")
    if sides < 1:
        raise InternalFlowValidationError("WINDAGE_SIDES_MUST_BE_POSITIVE")
    return (
        sides
        * moment_coefficient
        * 0.5
        * density_kg_m3
        * angular_velocity_rad_s**3
        * radius_m**5
    )
