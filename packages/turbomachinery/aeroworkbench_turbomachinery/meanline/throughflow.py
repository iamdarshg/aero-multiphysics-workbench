"""Reduced-order throughflow solver with stage-to-stage row matching.

The solver walks the rows in order. Each row sees the actual total/static state
and swirl angle left by the previous row rather than an independent stage
estimate, so swirl and work are carried and matched through the machine. Losses
come only from the versioned correlations in :mod:`.correlations`; no number in
this module is a bare constant.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import pi

from aeroworkbench_core.types import FidelityLevel, Provenance, ResultSource

from .correlations import (
    CorrelationValue,
    ainley_loading_parameter,
    ainley_mathieson_profile_loss,
    ainley_mathieson_secondary_loss,
    carter_deviation_deg,
    carter_secondary_loss,
    conrad_incidence_loss,
    diffuser_loss_coefficient,
    dunham_came_tip_clearance_loss,
    lieblein_blockage,
    lieblein_diffusion_factor,
    lieblein_profile_loss,
    radial_impeller_profile_loss,
    slip_factor,
)
from .design import MeanlineRow, RowFamilyModel, StageDesign
from .errors import MeanlineInputError
from .limits import LimitIndicator, ScreeningLimits, screen_row
from .properties import IdealGas, MeanlineState, reynolds_number, state_from_total
from .triangles import (
    VelocityTriangle,
    degree_of_reaction,
    euler_work_j_kg,
    solve_triangle,
    triangle_from_angle,
    triangle_from_relative_angle,
)
from .validity import Validity

_ANALYTICAL_SOURCE = "row-matching-meanline-analytical"
_REDUCED_SOURCE = "row-matching-meanline-reduced"


@dataclass(frozen=True, slots=True)
class LossBreakdown:
    """Named loss components plus their summed coefficient."""

    profile: float
    secondary: float
    tip_clearance: float
    incidence: float
    blockage: float
    diffuser: float
    total: float
    components: tuple[CorrelationValue, ...]

    def canonical(self) -> dict[str, object]:
        return {
            "profile": self.profile,
            "secondary": self.secondary,
            "tipClearance": self.tip_clearance,
            "incidence": self.incidence,
            "blockage": self.blockage,
            "diffuser": self.diffuser,
            "total": self.total,
            "components": [component.canonical() for component in self.components],
        }

    def provenance(self, *, inputs: dict[str, object]) -> Provenance:
        return Provenance.from_inputs(
            source=ResultSource.ANALYTICAL,
            model="meanline-loss-breakdown",
            model_version="1.0",
            fidelity=FidelityLevel.ANALYTICAL,
            inputs=inputs,
            assumptions=tuple(
                f"{component.identity}@{component.version}: {component.source}"
                for component in self.components
            ),
        )


@dataclass(frozen=True, slots=True)
class RowResult:
    """State and screening indicators for one solved row."""

    row_family: str
    role: str
    frame: str
    flow_family: str
    inlet_triangle: VelocityTriangle
    outlet_triangle: VelocityTriangle
    inlet_state: MeanlineState
    outlet_state: MeanlineState
    euler_work_j_kg: float
    static_enthalpy_change_j_kg: float
    total_pressure_loss_pa: float
    deviation_deg: float
    incidence_deg: float
    turning_deg: float
    diffusion_factor: float
    loading_coefficient: float
    reaction: float
    reynolds_number: float
    loss_breakdown: LossBreakdown
    indicators: tuple[LimitIndicator, ...]
    provenance: Provenance
    slip_factor: float | None = None

    @property
    def screened(self) -> bool:
        return all(indicator.passed for indicator in self.indicators)

    def canonical(self) -> dict[str, object]:
        return {
            "rowFamily": self.row_family,
            "role": self.role,
            "frame": self.frame,
            "flowFamily": self.flow_family,
            "inletTriangle": self.inlet_triangle.canonical(),
            "outletTriangle": self.outlet_triangle.canonical(),
            "inletState": self.inlet_state.canonical(),
            "outletState": self.outlet_state.canonical(),
            "eulerWorkJkg": self.euler_work_j_kg,
            "staticEnthalpyChangeJkg": self.static_enthalpy_change_j_kg,
            "totalPressureLossPa": self.total_pressure_loss_pa,
            "deviationDeg": self.deviation_deg,
            "incidenceDeg": self.incidence_deg,
            "turningDeg": self.turning_deg,
            "diffusionFactor": self.diffusion_factor,
            "loadingCoefficient": self.loading_coefficient,
            "reaction": self.reaction,
            "reynoldsNumber": self.reynolds_number,
            "lossBreakdown": self.loss_breakdown.canonical(),
            "indicators": [indicator.canonical() for indicator in self.indicators],
            "slipFactor": self.slip_factor,
            "screened": self.screened,
        }


@dataclass(frozen=True, slots=True)
class ThroughflowResult:
    """Solved multi-row meanline state consumed by downstream cycle/fidelity work."""

    name: str
    gas: IdealGas
    inlet_state: MeanlineState
    outlet_state: MeanlineState
    rows: tuple[RowResult, ...]
    total_work_j_kg: float
    pressure_ratio: float
    temperature_rise_k: float
    source: str
    fidelity: str
    validity: Validity
    provenance: Provenance

    @property
    def screened(self) -> bool:
        return all(row.screened for row in self.rows)

    def canonical(self) -> dict[str, object]:
        return {
            "name": self.name,
            "gas": self.gas.canonical(),
            "inletState": self.inlet_state.canonical(),
            "outletState": self.outlet_state.canonical(),
            "rows": [row.canonical() for row in self.rows],
            "totalWorkJkg": self.total_work_j_kg,
            "pressureRatio": self.pressure_ratio,
            "temperatureRiseK": self.temperature_rise_k,
            "source": self.source,
            "fidelity": self.fidelity,
            "validity": self.validity.canonical(),
            "screened": self.screened,
        }


def _meridional_angle(row: MeanlineRow, family: RowFamilyModel, *, inlet: bool) -> float:
    if row.meridional_angle_deg != 0.0:
        return row.meridional_angle_deg
    if family.flow_family == "axial":
        return 0.0
    if family.flow_family == "radial":
        return 0.0 if inlet else 90.0
    return 0.0 if inlet else 45.0


def _resolve_meridional_out(row: MeanlineRow) -> float:
    assert row.meridional_velocity_out_m_s is not None
    return row.meridional_velocity_out_m_s


def _turning_angle(triangle: VelocityTriangle, family: RowFamilyModel) -> float:
    return (
        triangle.relative_angle_deg
        if family.turning_frame == "relative"
        else triangle.absolute_angle_deg
    )


def _linear_loss(
    *,
    family: RowFamilyModel,
    row: MeanlineRow,
    inlet_triangle: VelocityTriangle,
    outlet_triangle: VelocityTriangle,
    incidence_deg: float,
    diffusion_factor: float,
    de_haller: float,
    loading_parameter: float,
    exit_mach: float,
    meridional_velocity_in_m_s: float,
) -> LossBreakdown:
    inlet_angle = _turning_angle(inlet_triangle, family)
    outlet_angle = _turning_angle(outlet_triangle, family)
    components: list[CorrelationValue] = []
    profile = 0.0
    secondary = 0.0
    tip = 0.0
    incidence = 0.0
    blockage = 0.0
    diffuser = 0.0
    for model in family.loss_models:
        if model == "lieblein-profile-loss":
            value = lieblein_profile_loss(diffusion_factor=diffusion_factor)
            profile += value.value
            components.append(value)
        elif model == "coppage-impeller-loss":
            value = radial_impeller_profile_loss(de_haller=de_haller)
            profile += value.value
            components.append(value)
        elif model == "ainley-mathieson-profile-loss":
            value = ainley_mathieson_profile_loss(
                incidence_deg=incidence_deg, exit_mach=exit_mach
            )
            profile += value.value
            components.append(value)
        elif model == "ainley-mathieson-secondary-loss":
            value = ainley_mathieson_secondary_loss(
                inlet_angle_deg=inlet_angle,
                outlet_angle_deg=outlet_angle,
                solidity=row.solidity,
            )
            secondary += value.value
            components.append(value)
        elif model == "carter-secondary-loss":
            value = carter_secondary_loss(
                inlet_angle_deg=inlet_angle,
                outlet_angle_deg=outlet_angle,
                solidity=row.solidity,
            )
            secondary += value.value
            components.append(value)
        elif model == "dunham-came-tip-clearance-loss":
            value = dunham_came_tip_clearance_loss(
                clearance_to_chord=row.tip_clearance_m / row.chord_m,
                chord_to_span=row.chord_m / row.span_m,
                loading_parameter=loading_parameter,
                shrouded=row.shrouded,
            )
            tip += value.value
            components.append(value)
        elif model == "conrad-incidence-loss":
            value = conrad_incidence_loss(
                incidence_deg=incidence_deg,
                meridional_velocity_m_s=meridional_velocity_in_m_s,
                relative_velocity_m_s=inlet_triangle.relative_velocity_m_s,
            )
            incidence += value.value
            components.append(value)
        elif model == "lieblein-blockage":
            value = lieblein_blockage(diffusion_factor=diffusion_factor)
            blockage += value.value
            components.append(value)
        elif model == "japikse-diffuser-recovery":
            value = diffuser_loss_coefficient(
                area_ratio=row.diffuser_area_ratio or 2.0,
                recovery_efficiency=row.recovery_efficiency,
            )
            diffuser += value.value
            components.append(value)
        else:
            raise MeanlineInputError(f"UNKNOWN_LOSS_MODEL:{family.family}:{model}")
    total = (profile + secondary + tip + incidence + blockage + diffuser) * row.loss_scale
    return LossBreakdown(
        profile=profile,
        secondary=secondary,
        tip_clearance=tip,
        incidence=incidence,
        blockage=blockage,
        diffuser=diffuser,
        total=total,
        components=tuple(components),
    )


def solve_throughflow(
    stage: StageDesign,
    *,
    fidelity: str = "analytical",
    limits: ScreeningLimits | None = None,
) -> ThroughflowResult:
    """Solve the row-matched meanline state for a whole stage/compressor/turbine."""

    if fidelity not in ("analytical", "reduced"):
        raise MeanlineInputError(f"UNSUPPORTED_MEANLINE_FIDELITY:{fidelity}")
    gas = stage.gas
    omega = stage.rotational_speed_rpm * 2.0 * pi / 60.0
    total_temperature = stage.inlet_total_temperature_k
    total_pressure = stage.inlet_total_pressure_pa
    swirl_angle = stage.inlet_swirl_angle_deg
    rows: list[RowResult] = []
    total_work = 0.0
    correlations_valid = True
    pressures_positive = True
    temperatures_positive = True
    work_sign_consistent = True

    for index, row in enumerate(stage.rows):
        family = row.family_model
        rotating = family.frame == "rotating"
        uses_lieblein = "lieblein-profile-loss" in family.loss_models
        meridional_angle_in = _meridional_angle(row, family, inlet=True)
        meridional_angle_out = _meridional_angle(row, family, inlet=False)
        radius_in = row.mean_radius_in_m
        radius_out = row.mean_radius_out_m
        blade_speed_in = omega * radius_in if rotating else 0.0
        blade_speed_out = omega * radius_out if rotating else 0.0
        inlet_triangle = triangle_from_angle(
            station_id=f"{stage.name}:{index}:in",
            blade_speed_m_s=blade_speed_in,
            meridional_velocity_m_s=row.meridional_velocity_in_m_s,
            absolute_angle_deg=swirl_angle,
            meridional_angle_deg=meridional_angle_in,
        )
        inlet_state = state_from_total(
            gas=gas,
            total_temperature_k=total_temperature,
            total_pressure_pa=total_pressure,
            mass_flow_kg_s=stage.mass_flow_kg_s,
            velocity_m_s=inlet_triangle.absolute_velocity_m_s,
        )
        deviation = carter_deviation_deg(
            camber_deg=row.camber_deg, stagger_deg=row.stagger_deg, solidity=row.solidity
        )
        exit_angle = row.exit_metal_angle_deg + deviation.value
        meridional_out = _resolve_meridional_out(row)
        if family.turning_frame == "relative":
            outlet_ideal = triangle_from_relative_angle(
                station_id=f"{stage.name}:{index}:out",
                blade_speed_m_s=blade_speed_out,
                meridional_velocity_m_s=meridional_out,
                relative_angle_deg=exit_angle,
                meridional_angle_deg=meridional_angle_out,
            )
        else:
            outlet_ideal = triangle_from_angle(
                station_id=f"{stage.name}:{index}:out",
                blade_speed_m_s=blade_speed_out,
                meridional_velocity_m_s=meridional_out,
                absolute_angle_deg=exit_angle,
                meridional_angle_deg=meridional_angle_out,
            )
        slip_component: CorrelationValue | None = None
        if family.slip:
            slip_component = slip_factor(blade_count=row.blade_count)
            slipped_tangential = (
                slip_component.value * outlet_ideal.tangential_velocity_m_s
            )
            outlet_triangle = solve_triangle(
                station_id=outlet_ideal.station_id,
                blade_speed_m_s=blade_speed_out,
                axial_velocity_m_s=outlet_ideal.axial_velocity_m_s,
                tangential_velocity_m_s=slipped_tangential,
                radial_velocity_m_s=outlet_ideal.radial_velocity_m_s,
            )
        else:
            outlet_triangle = outlet_ideal

        work = euler_work_j_kg(inlet=inlet_triangle, outlet=outlet_triangle)
        total_work += work
        outlet_total_temperature = total_temperature + work / gas.cp_j_kg_k
        outlet_static_temperature = gas.static_temperature_k(
            outlet_total_temperature, outlet_triangle.absolute_velocity_m_s
        )
        if outlet_static_temperature <= 0.0:
            temperatures_positive = False
            outlet_static_temperature = 1e-6
        relative_out = (
            outlet_triangle.relative_velocity_m_s
            if family.turning_frame == "relative"
            else outlet_triangle.absolute_velocity_m_s
        )
        exit_mach = relative_out / gas.sound_speed_m_s(outlet_static_temperature)

        diffusion = lieblein_diffusion_factor(
            inlet_relative_velocity_m_s=inlet_triangle.relative_velocity_m_s,
            outlet_relative_velocity_m_s=outlet_triangle.relative_velocity_m_s,
            inlet_tangential_velocity_m_s=inlet_triangle.tangential_velocity_m_s,
            outlet_tangential_velocity_m_s=outlet_triangle.tangential_velocity_m_s,
            inlet_radius_m=radius_in,
            outlet_radius_m=radius_out,
            solidity=row.solidity,
        )
        inlet_angle = _turning_angle(inlet_triangle, family)
        outlet_angle = _turning_angle(outlet_triangle, family)
        loading = ainley_loading_parameter(
            inlet_angle_deg=inlet_angle, outlet_angle_deg=outlet_angle
        )
        incidence = row.inlet_metal_angle_deg - inlet_angle
        de_haller = (
            outlet_triangle.relative_velocity_m_s / inlet_triangle.relative_velocity_m_s
            if inlet_triangle.relative_velocity_m_s > 0.0
            else 0.0
        )
        breakdown = _linear_loss(
            family=family,
            row=row,
            inlet_triangle=inlet_triangle,
            outlet_triangle=outlet_triangle,
            incidence_deg=incidence,
            diffusion_factor=diffusion.value,
            de_haller=de_haller,
            loading_parameter=loading.value,
            exit_mach=exit_mach,
            meridional_velocity_in_m_s=row.meridional_velocity_in_m_s,
        )
        dynamic_head = (
            0.5 * inlet_state.density_kg_m3 * inlet_triangle.absolute_velocity_m_s**2
        )
        total_pressure_loss = breakdown.total * dynamic_head
        isentropic_total_pressure = total_pressure * (
            outlet_total_temperature / total_temperature
        ) ** (gas.gamma / (gas.gamma - 1.0))
        outlet_total_pressure = isentropic_total_pressure - total_pressure_loss
        if outlet_total_pressure <= 0.0:
            pressures_positive = False
            outlet_total_pressure = 1e-3
        outlet_state = state_from_total(
            gas=gas,
            total_temperature_k=outlet_total_temperature,
            total_pressure_pa=outlet_total_pressure,
            mass_flow_kg_s=stage.mass_flow_kg_s,
            velocity_m_s=outlet_triangle.absolute_velocity_m_s,
        )

        loading_coefficient = work / blade_speed_in**2 if blade_speed_in != 0.0 else 0.0
        reaction = (
            degree_of_reaction(inlet=inlet_triangle, outlet=outlet_triangle)
            if rotating
            else 0.0
        )
        clearance_fraction = (
            breakdown.tip_clearance * row.loss_scale / breakdown.total
            if breakdown.total > 0.0
            else 0.0
        )
        relative_mach_in = (
            inlet_triangle.relative_velocity_m_s
            / gas.sound_speed_m_s(inlet_state.static_temperature_k)
        )
        relative_mach_out = (
            outlet_triangle.relative_velocity_m_s
            / gas.sound_speed_m_s(outlet_state.static_temperature_k)
        )
        row_reynolds = reynolds_number(
            gas=gas,
            static_pressure_pa=inlet_state.static_pressure_pa,
            static_temperature_k=inlet_state.static_temperature_k,
            velocity_m_s=inlet_triangle.relative_velocity_m_s,
            chord_m=row.chord_m,
            dynamic_viscosity_pa_s=stage.dynamic_viscosity_pa_s,
        )
        absolute_exit_mach = (
            outlet_triangle.absolute_velocity_m_s
            / gas.sound_speed_m_s(outlet_state.static_temperature_k)
        )
        indicators = screen_row(
            relative_mach_in=relative_mach_in,
            relative_mach_out=relative_mach_out,
            exit_mach=absolute_exit_mach,
            diffusion_factor=diffusion.value,
            de_haller=de_haller,
            uses_lieblein=uses_lieblein,
            incidence_deg=incidence,
            turning_deg=outlet_angle - inlet_angle,
            loading_coefficient=loading_coefficient,
            reaction=reaction,
            clearance_loss_fraction=clearance_fraction,
            reynolds_number=row_reynolds,
            role=family.role,
            limits=limits,
        )
        all_components: list[CorrelationValue] = list(breakdown.components)
        all_components.extend((deviation, loading))
        if uses_lieblein:
            all_components.append(diffusion)
        if slip_component is not None:
            all_components.append(slip_component)
        for component in all_components:
            if not component.validity_passed:
                correlations_valid = False
        if family.role == "work_adding" and work < -1e-9:
            work_sign_consistent = False
        if family.role == "work_extracting" and work > 1e-9:
            work_sign_consistent = False

        provenance = Provenance.from_inputs(
            source=ResultSource.ANALYTICAL,
            model="meanline-row",
            model_version="1.0",
            fidelity=FidelityLevel.ANALYTICAL,
            inputs={
                "row": row.canonical(),
                "inletTotalTemperatureK": total_temperature,
                "inletTotalPressurePa": total_pressure,
                "inletSwirlAngleDeg": swirl_angle,
            },
            assumptions=(
                "Row-matching reduced-order meanline; correlations carry their own "
                "identity, version, source, and validity envelope.",
            ),
        )
        rows.append(
            RowResult(
                row_family=row.row_family,
                role=family.role,
                frame=family.frame,
                flow_family=family.flow_family,
                inlet_triangle=inlet_triangle,
                outlet_triangle=outlet_triangle,
                inlet_state=inlet_state,
                outlet_state=outlet_state,
                euler_work_j_kg=work,
                static_enthalpy_change_j_kg=gas.cp_j_kg_k
                * (outlet_state.static_temperature_k - inlet_state.static_temperature_k),
                total_pressure_loss_pa=total_pressure_loss,
                deviation_deg=deviation.value,
                incidence_deg=incidence,
                turning_deg=outlet_angle - inlet_angle,
                diffusion_factor=diffusion.value,
                loading_coefficient=loading_coefficient,
                reaction=reaction,
                reynolds_number=row_reynolds,
                loss_breakdown=breakdown,
                indicators=indicators,
                provenance=provenance,
                slip_factor=None if slip_component is None else slip_component.value,
            )
        )
        total_temperature = outlet_total_temperature
        total_pressure = outlet_total_pressure
        swirl_angle = outlet_triangle.absolute_angle_deg

    outlet_state = rows[-1].outlet_state
    checks = {
        "correlations_in_envelope": correlations_valid,
        "total_pressure_positive": pressures_positive,
        "static_temperature_positive": temperatures_positive,
        "work_sign_matches_role": work_sign_consistent,
        "mass_flow_positive": stage.mass_flow_kg_s > 0.0,
    }
    source = _ANALYTICAL_SOURCE if fidelity == "analytical" else _REDUCED_SOURCE
    provenance = Provenance.from_inputs(
        source=ResultSource.ANALYTICAL,
        model="meanline-throughflow",
        model_version="1.0",
        fidelity=FidelityLevel.ANALYTICAL,
        inputs={"stage": stage.canonical(), "fidelity": fidelity},
        assumptions=(
            "Row-matched reduced-order meanline; analytical fidelity, not a native "
            "throughflow/CFD execution.",
        ),
    )
    return ThroughflowResult(
        name=stage.name,
        gas=gas,
        inlet_state=rows[0].inlet_state,
        outlet_state=outlet_state,
        rows=tuple(rows),
        total_work_j_kg=total_work,
        pressure_ratio=outlet_state.total_pressure_pa / stage.inlet_total_pressure_pa,
        temperature_rise_k=outlet_state.total_temperature_k - stage.inlet_total_temperature_k,
        source=source,
        fidelity=fidelity,
        validity=Validity(
            passed=all(checks.values()),
            checks=checks,
            detail="row-matched meanline with versioned correlation provenance",
        ),
        provenance=provenance,
    )


__all__ = [
    "LossBreakdown",
    "RowResult",
    "ThroughflowResult",
    "solve_throughflow",
]
