"""Generic heat-addition, bleed, and cooling models for turbo architectures.

These are reduced-order conservation models, never native-solver output. Every
returned result carries analytical provenance. The governed Cantera participant
(``solvers/cantera``) is the only path that publishes native chemistry results;
this module composes with it, closes cycle mass/enthalpy/species bookkeeping,
and exposes the reacting-CFD and cooled-wall seams.

The governed participant wrappers below are what the central manifest
registers; they delegate the native chemistry to ``cantera.case``.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from aeroworkbench_core.types import FidelityLevel, Provenance, ResultSource
from cantera.case import (
    execute_combustion_case as _execute_native_combustion_case,
)
from cantera.case import (
    prepare_combustion_case as _prepare_native_combustion_case,
)

from participants.errors import NativeErrorCode, ParticipantError
from participants.receipts import PrepareReceipt, ValidityReport

HEAT_ADDITION_NODE_KINDS: tuple[str, ...] = ("combustor", "heat_addition")
BLEED_NODE_KINDS: tuple[str, ...] = ("bleed_extract",)
COOLING_NODE_KINDS: tuple[str, ...] = ("cooling_inject",)

COMBUSTION_PARTICIPANT_ID = "combustion-reacting-flow"
REACTING_CFD_PARTICIPANT_ID = "reacting-compressible-flow"
REACTING_CFD_FIDELITY = "reacting-rans"

AcceptsComposition = Iterable[tuple[str, float]]


def _finite(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a number")
    number = float(value)
    if number != number or number in (float("inf"), float("-inf")):
        raise ValueError(f"{label} must be finite")
    return number


def _positive(value: object, label: str) -> float:
    number = _finite(value, label)
    if number <= 0.0:
        raise ValueError(f"{label} must be positive")
    return number


def _fraction(value: object, label: str) -> float:
    number = _finite(value, label)
    if not 0.0 <= number <= 1.0:
        raise ValueError(f"{label} must be within [0, 1]")
    return number


def _normalize_composition(
    composition: AcceptsComposition,
) -> tuple[tuple[str, float], ...]:
    items = [
        (str(name), _finite(fraction, f"composition.{name}"))
        for name, fraction in composition
    ]
    items = [(name, fraction) for name, fraction in items if fraction > 0.0]
    total = sum(fraction for _, fraction in items)
    if total <= 0.0:
        return ()
    return tuple(sorted((name, fraction / total) for name, fraction in items))


def _analytical_provenance(
    model: str, inputs: Mapping[str, object], *assumptions: str
) -> Provenance:
    return Provenance.from_inputs(
        source=ResultSource.ANALYTICAL,
        model=model,
        model_version="1.0",
        fidelity=FidelityLevel.ANALYTICAL,
        inputs=dict(inputs),
        assumptions=assumptions,
    )


# -- generic combustor network (issue B) -------------------------------------


@dataclass(frozen=True, slots=True)
class CombustorNetworkInput:
    """Reduced-order combustor/heat-addition network boundary conditions."""

    inlet_temperature_k: float
    inlet_pressure_pa: float
    air_mass_flow_kg_s: float
    fuel_mass_flow_kg_s: float
    fuel_lower_heating_value_j_kg: float
    combustion_efficiency: float
    pressure_loss_fraction: float
    cp_exit_j_kg_k: float
    equivalence_ratio: float
    pattern_factor: float = 0.0
    residence_time_s: float | None = None

    def __post_init__(self) -> None:
        _positive(self.inlet_temperature_k, "inlet_temperature_k")
        _positive(self.inlet_pressure_pa, "inlet_pressure_pa")
        _positive(self.air_mass_flow_kg_s, "air_mass_flow_kg_s")
        _positive(self.fuel_mass_flow_kg_s, "fuel_mass_flow_kg_s")
        _positive(self.fuel_lower_heating_value_j_kg, "fuel_lower_heating_value_j_kg")
        efficiency = _fraction(self.combustion_efficiency, "combustion_efficiency")
        if efficiency <= 0.0:
            raise ValueError("combustion_efficiency must be positive")
        loss = _fraction(self.pressure_loss_fraction, "pressure_loss_fraction")
        if loss >= 0.5:
            raise ValueError("pressure_loss_fraction must be below 0.5")
        _positive(self.cp_exit_j_kg_k, "cp_exit_j_kg_k")
        _positive(self.equivalence_ratio, "equivalence_ratio")
        pattern = _fraction(self.pattern_factor, "pattern_factor")
        if pattern >= 1.0:
            raise ValueError("pattern_factor must be below 1.0")
        if self.residence_time_s is not None:
            _positive(self.residence_time_s, "residence_time_s")

    def canonical(self) -> dict[str, object]:
        return {
            "inlet_temperature_k": self.inlet_temperature_k,
            "inlet_pressure_pa": self.inlet_pressure_pa,
            "air_mass_flow_kg_s": self.air_mass_flow_kg_s,
            "fuel_mass_flow_kg_s": self.fuel_mass_flow_kg_s,
            "fuel_lower_heating_value_j_kg": self.fuel_lower_heating_value_j_kg,
            "combustion_efficiency": self.combustion_efficiency,
            "pressure_loss_fraction": self.pressure_loss_fraction,
            "cp_exit_j_kg_k": self.cp_exit_j_kg_k,
            "equivalence_ratio": self.equivalence_ratio,
            "pattern_factor": self.pattern_factor,
            "residence_time_s": self.residence_time_s,
        }


@dataclass(frozen=True, slots=True)
class CombustorNetworkResult:
    exit_total_temperature_k: float
    exit_total_pressure_pa: float
    exit_peak_temperature_k: float
    fuel_mass_flow_kg_s: float
    heat_release_w: float
    combustion_efficiency: float
    pressure_loss_fraction: float
    pattern_factor: float
    residence_time_s: float | None
    stability_indicator: float
    provenance: Provenance

    def canonical(self) -> dict[str, object]:
        return {
            "exit_total_temperature_k": self.exit_total_temperature_k,
            "exit_total_pressure_pa": self.exit_total_pressure_pa,
            "exit_peak_temperature_k": self.exit_peak_temperature_k,
            "fuel_mass_flow_kg_s": self.fuel_mass_flow_kg_s,
            "heat_release_w": self.heat_release_w,
            "combustion_efficiency": self.combustion_efficiency,
            "pressure_loss_fraction": self.pressure_loss_fraction,
            "pattern_factor": self.pattern_factor,
            "residence_time_s": self.residence_time_s,
            "stability_indicator": self.stability_indicator,
        }


def combustor_stability_indicator(
    equivalence_ratio: float, residence_time_s: float | None
) -> float:
    """Bounded lean/rich and residence-time stability descriptor in [0, 1]."""

    proximity = max(0.0, 1.0 - abs(equivalence_ratio - 1.0))
    if residence_time_s is None:
        return round(min(1.0, proximity), 6)
    time_factor = min(1.0, residence_time_s / 1.0e-3)
    return round(min(1.0, proximity * time_factor), 6)


def evaluate_combustor_network(inputs: CombustorNetworkInput) -> CombustorNetworkResult:
    """Close energy, fuel flow, pressure loss, and stability for a combustor."""

    heat_release_w = (
        inputs.combustion_efficiency
        * inputs.fuel_mass_flow_kg_s
        * inputs.fuel_lower_heating_value_j_kg
    )
    total_mass_flow = inputs.air_mass_flow_kg_s + inputs.fuel_mass_flow_kg_s
    exit_temperature = inputs.inlet_temperature_k + heat_release_w / (
        total_mass_flow * inputs.cp_exit_j_kg_k
    )
    exit_pressure = inputs.inlet_pressure_pa * (1.0 - inputs.pressure_loss_fraction)
    return CombustorNetworkResult(
        exit_total_temperature_k=exit_temperature,
        exit_total_pressure_pa=exit_pressure,
        exit_peak_temperature_k=exit_temperature * (1.0 + inputs.pattern_factor),
        fuel_mass_flow_kg_s=inputs.fuel_mass_flow_kg_s,
        heat_release_w=heat_release_w,
        combustion_efficiency=inputs.combustion_efficiency,
        pressure_loss_fraction=inputs.pressure_loss_fraction,
        pattern_factor=inputs.pattern_factor,
        residence_time_s=inputs.residence_time_s,
        stability_indicator=combustor_stability_indicator(
            inputs.equivalence_ratio, inputs.residence_time_s
        ),
        provenance=_analytical_provenance(
            "reduced-combustor-network", inputs.canonical(),
            "steady energy balance with constant exit cp; no finite-rate chemistry",
        ),
    )


# -- bleed and cooling (issue C) ---------------------------------------------


@dataclass(frozen=True, slots=True)
class BleedExtractionResult:
    core_mass_flow_kg_s: float
    bleed_mass_flow_kg_s: float
    total_temperature_k: float
    total_pressure_pa: float
    core_enthalpy_flow_w: float
    bleed_enthalpy_flow_w: float
    enthalpy_closure_error: float
    composition: tuple[tuple[str, float], ...]
    provenance: Provenance


def extract_bleed(
    *,
    mass_flow_kg_s: float,
    total_temperature_k: float,
    total_pressure_pa: float,
    cp_j_kg_k: float,
    bleed_fraction: float,
    composition: AcceptsComposition = (),
) -> BleedExtractionResult:
    """Split a station flow into core and extracted bleed with enthalpy closure."""

    mass_flow = _positive(mass_flow_kg_s, "mass_flow_kg_s")
    temperature = _positive(total_temperature_k, "total_temperature_k")
    pressure = _positive(total_pressure_pa, "total_pressure_pa")
    cp = _positive(cp_j_kg_k, "cp_j_kg_k")
    fraction = _fraction(bleed_fraction, "bleed_fraction")
    bleed_mass_flow = mass_flow * fraction
    core_mass_flow = mass_flow - bleed_mass_flow
    total_enthalpy = mass_flow * cp * temperature
    core_enthalpy = core_mass_flow * cp * temperature
    bleed_enthalpy = bleed_mass_flow * cp * temperature
    closure = abs(total_enthalpy - (core_enthalpy + bleed_enthalpy)) / max(
        total_enthalpy, 1e-30
    )
    return BleedExtractionResult(
        core_mass_flow_kg_s=core_mass_flow,
        bleed_mass_flow_kg_s=bleed_mass_flow,
        total_temperature_k=temperature,
        total_pressure_pa=pressure,
        core_enthalpy_flow_w=core_enthalpy,
        bleed_enthalpy_flow_w=bleed_enthalpy,
        enthalpy_closure_error=closure,
        composition=_normalize_composition(composition),
        provenance=_analytical_provenance(
            "bleed-extraction",
            {
                "mass_flow_kg_s": mass_flow,
                "total_temperature_k": temperature,
                "total_pressure_pa": pressure,
                "cp_j_kg_k": cp,
                "bleed_fraction": fraction,
            },
            "extraction at constant total temperature; species follow the split",
        ),
    )


@dataclass(frozen=True, slots=True)
class CoolingInjectionResult:
    mixed_mass_flow_kg_s: float
    mixed_temperature_k: float
    main_mass_flow_kg_s: float
    coolant_mass_flow_kg_s: float
    enthalpy_closure_error: float
    mass_closure_error: float
    composition: tuple[tuple[str, float], ...]
    provenance: Provenance


def inject_cooling(
    *,
    main_mass_flow_kg_s: float,
    main_temperature_k: float,
    main_cp_j_kg_k: float,
    coolant_mass_flow_kg_s: float,
    coolant_temperature_k: float,
    coolant_cp_j_kg_k: float,
    main_composition: AcceptsComposition = (),
    coolant_composition: AcceptsComposition = (),
) -> CoolingInjectionResult:
    """Reinject coolant into a main stream with mass/enthalpy/species closure."""

    main_mass = _positive(main_mass_flow_kg_s, "main_mass_flow_kg_s")
    main_temperature = _positive(main_temperature_k, "main_temperature_k")
    main_cp = _positive(main_cp_j_kg_k, "main_cp_j_kg_k")
    coolant_mass = _positive(coolant_mass_flow_kg_s, "coolant_mass_flow_kg_s")
    coolant_temperature = _positive(coolant_temperature_k, "coolant_temperature_k")
    coolant_cp = _positive(coolant_cp_j_kg_k, "coolant_cp_j_kg_k")

    mixed_mass = main_mass + coolant_mass
    mixed_cp = (main_mass * main_cp + coolant_mass * coolant_cp) / mixed_mass
    mixed_temperature = (
        main_mass * main_cp * main_temperature
        + coolant_mass * coolant_cp * coolant_temperature
    ) / (mixed_mass * mixed_cp)
    enthalpy_in = (
        main_mass * main_cp * main_temperature
        + coolant_mass * coolant_cp * coolant_temperature
    )
    enthalpy_out = mixed_mass * mixed_cp * mixed_temperature
    enthalpy_closure = abs(enthalpy_in - enthalpy_out) / max(abs(enthalpy_in), 1e-30)
    mass_closure = abs(mixed_mass - (main_mass + coolant_mass)) / mixed_mass

    composition = _mix_composition(
        main_mass,
        _normalize_composition(main_composition),
        coolant_mass,
        _normalize_composition(coolant_composition),
    )
    return CoolingInjectionResult(
        mixed_mass_flow_kg_s=mixed_mass,
        mixed_temperature_k=mixed_temperature,
        main_mass_flow_kg_s=main_mass,
        coolant_mass_flow_kg_s=coolant_mass,
        enthalpy_closure_error=enthalpy_closure,
        mass_closure_error=mass_closure,
        composition=composition,
        provenance=_analytical_provenance(
            "cooling-injection",
            {
                "main_mass_flow_kg_s": main_mass,
                "main_temperature_k": main_temperature,
                "main_cp_j_kg_k": main_cp,
                "coolant_mass_flow_kg_s": coolant_mass,
                "coolant_temperature_k": coolant_temperature,
                "coolant_cp_j_kg_k": coolant_cp,
            },
            "adiabatic mixing on a mass-weighted enthalpy basis",
        ),
    )


def _mix_composition(
    main_mass: float,
    main: tuple[tuple[str, float], ...],
    coolant_mass: float,
    coolant: tuple[tuple[str, float], ...],
) -> tuple[tuple[str, float], ...]:
    if not main and not coolant:
        return ()
    if not main:
        main = ((coolant[0][0], 1.0),) if coolant else ()
    if not coolant:
        coolant = ((main[0][0], 1.0),) if main else ()
    totals: dict[str, float] = {}
    for name, fraction in main:
        totals[name] = totals.get(name, 0.0) + fraction * main_mass
    for name, fraction in coolant:
        totals[name] = totals.get(name, 0.0) + fraction * coolant_mass
    total_mass = main_mass + coolant_mass
    return tuple(sorted((name, mass / total_mass) for name, mass in totals.items()))


@dataclass(frozen=True, slots=True)
class CoolingPenaltyResult:
    shaft_power_w: float
    cooling_fraction: float
    work_penalty_w: float
    net_shaft_power_w: float
    efficiency_penalty: float
    provenance: Provenance


def cooling_penalty(
    *,
    shaft_power_w: float,
    cooling_fraction: float,
    recovery_fraction: float = 0.0,
) -> CoolingPenaltyResult:
    """Work/efficiency penalty of extracting air for cooling."""

    shaft = _positive(shaft_power_w, "shaft_power_w")
    fraction = _fraction(cooling_fraction, "cooling_fraction")
    recovery = _fraction(recovery_fraction, "recovery_fraction")
    penalty = shaft * fraction * (1.0 - recovery)
    return CoolingPenaltyResult(
        shaft_power_w=shaft,
        cooling_fraction=fraction,
        work_penalty_w=penalty,
        net_shaft_power_w=shaft - penalty,
        efficiency_penalty=penalty / shaft,
        provenance=_analytical_provenance(
            "cooling-penalty",
            {
                "shaft_power_w": shaft,
                "cooling_fraction": fraction,
                "recovery_fraction": recovery,
            },
            "linear work penalty proportional to extracted cooling fraction",
        ),
    )


@dataclass(frozen=True, slots=True)
class CooledWallState:
    gas_temperature_k: float
    coolant_temperature_k: float
    gas_side_heat_flux_w_m2: float
    metal_temperature_k: float
    provenance: Provenance


def cooled_wall_state(
    *,
    gas_temperature_k: float,
    coolant_temperature_k: float,
    gas_side_h_w_m2_k: float,
    coolant_side_h_w_m2_k: float,
    wall_thickness_m: float,
    wall_conductivity_w_m_k: float,
) -> CooledWallState:
    """Series-resistance cooled-wall state feeding Elmer/CHT/material limits."""

    gas_temperature = _finite(gas_temperature_k, "gas_temperature_k")
    coolant_temperature = _finite(coolant_temperature_k, "coolant_temperature_k")
    gas_h = _positive(gas_side_h_w_m2_k, "gas_side_h_w_m2_k")
    coolant_h = _positive(coolant_side_h_w_m2_k, "coolant_side_h_w_m2_k")
    thickness = _positive(wall_thickness_m, "wall_thickness_m")
    conductivity = _positive(wall_conductivity_w_m_k, "wall_conductivity_w_m_k")
    wall_resistance = thickness / conductivity
    total_resistance = 1.0 / gas_h + wall_resistance + 1.0 / coolant_h
    heat_flux = (gas_temperature - coolant_temperature) / total_resistance
    metal_temperature = coolant_temperature + heat_flux * (
        wall_resistance + 1.0 / coolant_h
    )
    return CooledWallState(
        gas_temperature_k=gas_temperature,
        coolant_temperature_k=coolant_temperature,
        gas_side_heat_flux_w_m2=heat_flux,
        metal_temperature_k=metal_temperature,
        provenance=_analytical_provenance(
            "cooled-wall-series-resistance",
            {
                "gas_temperature_k": gas_temperature,
                "coolant_temperature_k": coolant_temperature,
                "gas_side_h_w_m2_k": gas_h,
                "coolant_side_h_w_m2_k": coolant_h,
                "wall_thickness_m": thickness,
                "wall_conductivity_w_m_k": conductivity,
            },
            "1D steady series thermal resistance; hot-side metal temperature",
        ),
    )


# -- optionality (issue F) ---------------------------------------------------


def heat_addition_required(node_kinds: Iterable[str]) -> bool:
    """Whether an architecture declares any heat-addition node at all."""

    return any(kind in HEAT_ADDITION_NODE_KINDS for kind in node_kinds)


def combustion_participant_ids(node_kinds: Iterable[str]) -> tuple[str, ...]:
    """Combustion participants an architecture needs; empty without heat addition."""

    return (COMBUSTION_PARTICIPANT_ID,) if heat_addition_required(node_kinds) else ()


def required_combustion_inputs(node_kinds: Iterable[str]) -> tuple[str, ...]:
    """Required combustion input keys; empty for architectures without combustion."""

    if not heat_addition_required(node_kinds):
        return ()
    return (
        "mechanism",
        "reactor_mode",
        "fuel",
        "oxidizer",
        "provenance",
        "equivalence_ratio",
        "inlet_temperature_k",
        "inlet_pressure_pa",
        "air_mass_flow_kg_s",
        "fuel_mass_flow_kg_s",
        "fuel_lower_heating_value_j_kg",
        "combustion_efficiency",
        "pressure_loss_fraction",
    )


# -- reacting CFD seam (issue D) ---------------------------------------------


@dataclass(frozen=True, slots=True)
class ReactingCfdSeam:
    participant_id: str
    fidelity: str
    available: bool
    detail: str


def reacting_cfd_seam() -> ReactingCfdSeam:
    """The reacting-flow CFD fidelity is distinct from 0D/PSR chemistry.

    Native reacting case preparation belongs to the OpenFOAM participant; until
    that capability is present the seam is explicitly unavailable and no
    Cantera result may be relabelled as reacting CFD.
    """

    return ReactingCfdSeam(
        participant_id=REACTING_CFD_PARTICIPANT_ID,
        fidelity=REACTING_CFD_FIDELITY,
        available=False,
        detail=(
            "native reacting OpenFOAM preparation is owned by the OpenFOAM "
            "workstream; Cantera 0D/PSR output is a distinct, lower fidelity"
        ),
    )


def reject_reacting_cfd_label(fidelity: str) -> str:
    """Fail closed when a reactor-network result is relabelled as reacting CFD."""

    if fidelity == REACTING_CFD_FIDELITY:
        raise ParticipantError(
            NativeErrorCode.PREPARATION_FAILED,
            "REACTING_CFD_IS_A_DISTINCT_FIDELITY:Cantera 0D/PSR/network output "
            "must not be labelled as reacting CFD",
        )
    return fidelity


# -- governed participant wrappers (registered centrally) --------------------


def prepare_combustion_case(
    inputs: dict[str, object], case_dir: Path
) -> PrepareReceipt:
    """Governed prepare: validate mixture/fuel/oxidizer and stage ``case.json``."""

    return _prepare_native_combustion_case(inputs, case_dir)


def execute_combustion_case(inputs: Mapping[str, object], case_dir: Path) -> None:
    """Governed in-process native Cantera execution; fails closed if absent."""

    _execute_native_combustion_case(inputs, case_dir)


def combustor_network_payload(result: CombustorNetworkResult) -> dict[str, Any]:
    """Serializable analytical combustor-network result with provenance."""

    payload = result.canonical()
    payload["source"] = result.provenance.source.value
    payload["provenance"] = json.loads(result.provenance.model_dump_json())
    return payload


def validate_combustor_network_result(
    scalars: Mapping[str, float], inputs: Mapping[str, object]
) -> ValidityReport:
    """Energy/fuel closure validity for a reduced-order combustor network."""

    heat_release = float(scalars.get("heat_release_w", float("nan")))
    efficiency = float(scalars.get("combustion_efficiency", float("nan")))
    exit_temperature = float(scalars.get("exit_total_temperature_k", float("nan")))
    inlet_temperature = float(cast("float", inputs.get("inlet_temperature_k", float("nan"))))
    exit_pressure = float(scalars.get("exit_total_pressure_pa", float("nan")))
    inlet_pressure = float(cast("float", inputs.get("inlet_pressure_pa", float("nan"))))
    checks = {
        "heat_release_positive": heat_release == heat_release and heat_release > 0.0,
        "efficiency_bounds": efficiency == efficiency and 0.0 < efficiency <= 1.0,
        "temperature_increases": (
            exit_temperature == exit_temperature
            and inlet_temperature == inlet_temperature
            and exit_temperature > inlet_temperature
        ),
        "pressure_drops": (
            exit_pressure == exit_pressure
            and inlet_pressure == inlet_pressure
            and 0.0 < exit_pressure <= inlet_pressure
        ),
    }
    return ValidityReport(
        participant_id=COMBUSTION_PARTICIPANT_ID,
        passed=all(checks.values()),
        checks=checks,
        detail="combustor network closes energy, temperature rise, and pressure loss",
    )
