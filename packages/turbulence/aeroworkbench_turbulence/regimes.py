"""Flow-regime contract: Reynolds/Mach regime, transition, and thermal state.

A :class:`FlowState` is the typed physical contract every downstream consumer
(model selection, wall treatment, diagnostics, solver adapters, benchmarks)
reads. It carries the Reynolds number, Mach number, freestream turbulence
intensity, reference length/velocity, wall thermal condition, declared
roughness, expected/observed transition state, and pressure-gradient/separation
indicators. Regime classification is a declared, validity-bounded band, not a
product name.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite
from typing import Any

from aeroworkbench_core.types import Provenance
from aeroworkbench_fluid_properties import (
    IdealGasEvaluation,
    PropertyId,
    SoftwareIdentity,
    WorkingFluid,
    evaluate_ideal_gas,
)

from .contracts import (
    SOFTWARE_IDENTITY,
    analytical_provenance,
)
from .errors import (
    TurbulenceCapabilityUnavailableError,
    TurbulenceValidationError,
)
from .roughness import RoughnessSpec


class FlowRegime(StrEnum):
    """Laminar, transitional, and turbulent are distinct and validity-bounded."""

    LAMINAR = "laminar"
    TRANSITIONAL = "transitional"
    TURBULENT = "turbulent"


class TransitionState(StrEnum):
    """Expected or observed transition character for a region or surface."""

    UNKNOWN = "unknown"
    NATURAL = "natural"
    FORCED = "forced"
    LAMINAR_SEPARATION = "laminar_separation"
    FULLY_TURBULENT = "fully_turbulent"


class CompressibilityRegime(StrEnum):
    """Mach-based compressibility band, independent of the Reynolds regime."""

    INCOMPRESSIBLE = "incompressible"
    SUBSONIC = "subsonic"
    TRANSONIC = "transonic"
    SUPERSONIC = "supersonic"
    HYPERSONIC = "hypersonic"


@dataclass(frozen=True, slots=True)
class RegimeThresholds:
    """Declared Reynolds/Mach regime bands with a cited source and revision."""

    model_id: str
    source: str
    laminar_reynolds_max: float
    turbulent_reynolds_min: float
    mach_compressibility_onset: float = 0.3
    mach_transonic_onset: float = 0.8
    mach_supersonic_onset: float = 1.2
    mach_hypersonic_onset: float = 5.0
    revision: str = "1"

    def __post_init__(self) -> None:
        if not self.model_id.strip() or not self.revision.strip():
            raise TurbulenceValidationError("REGIME_THRESHOLDS_IDENTITY_REQUIRED")
        if not self.source.strip():
            raise TurbulenceValidationError("REGIME_THRESHOLDS_SOURCE_REQUIRED")
        if not 0.0 < self.laminar_reynolds_max < self.turbulent_reynolds_min:
            raise TurbulenceValidationError("INVALID_REYNOLDS_REGIME_BANDS")
        onsets = (
            self.mach_compressibility_onset,
            self.mach_transonic_onset,
            self.mach_supersonic_onset,
            self.mach_hypersonic_onset,
        )
        if not all(isfinite(value) and value > 0.0 for value in onsets):
            raise TurbulenceValidationError("INVALID_MACH_REGIME_ONSETS")
        if list(onsets) != sorted(onsets):
            raise TurbulenceValidationError("MACH_REGIME_ONSETS_NOT_ORDERED")

    def classify_reynolds(self, reynolds_number: float) -> FlowRegime:
        if not isfinite(reynolds_number) or reynolds_number <= 0.0:
            raise TurbulenceValidationError("REYNOLDS_NUMBER_INVALID")
        if reynolds_number <= self.laminar_reynolds_max:
            return FlowRegime.LAMINAR
        if reynolds_number < self.turbulent_reynolds_min:
            return FlowRegime.TRANSITIONAL
        return FlowRegime.TURBULENT

    def classify_mach(self, mach_number: float) -> CompressibilityRegime:
        if not isfinite(mach_number) or mach_number < 0.0:
            raise TurbulenceValidationError("MACH_NUMBER_INVALID")
        if mach_number < self.mach_compressibility_onset:
            return CompressibilityRegime.INCOMPRESSIBLE
        if mach_number < self.mach_transonic_onset:
            return CompressibilityRegime.SUBSONIC
        if mach_number < self.mach_supersonic_onset:
            return CompressibilityRegime.TRANSONIC
        if mach_number < self.mach_hypersonic_onset:
            return CompressibilityRegime.SUPERSONIC
        return CompressibilityRegime.HYPERSONIC

    def canonical(self) -> dict[str, Any]:
        return {
            "modelId": self.model_id,
            "revision": self.revision,
            "source": self.source,
            "laminarReynoldsMax": self.laminar_reynolds_max,
            "turbulentReynoldsMin": self.turbulent_reynolds_min,
            "machCompressibilityOnset": self.mach_compressibility_onset,
            "machTransonicOnset": self.mach_transonic_onset,
            "machSupersonicOnset": self.mach_supersonic_onset,
            "machHypersonicOnset": self.mach_hypersonic_onset,
        }


EXTERNAL_FLOW_THRESHOLDS = RegimeThresholds(
    model_id="external-flow-regime-band",
    source="flat-plate boundary-layer transition Re_x ~ 5e5; declared screening band",
    laminar_reynolds_max=5.0e5,
    turbulent_reynolds_min=1.0e6,
)

INTERNAL_FLOW_THRESHOLDS = RegimeThresholds(
    model_id="internal-flow-regime-band",
    source="pipe-flow transition Re_D 2300 (laminar) / 4000 (turbulent)",
    laminar_reynolds_max=2300.0,
    turbulent_reynolds_min=4000.0,
)

LOW_REYNOLDS_THRESHOLDS = RegimeThresholds(
    model_id="low-reynolds-regime-band",
    source="low-Reynolds airfoil transition screening band Re_c 5e4 / 2e5",
    laminar_reynolds_max=5.0e4,
    turbulent_reynolds_min=2.0e5,
)

REGIME_THRESHOLD_PRESETS: dict[str, RegimeThresholds] = {
    EXTERNAL_FLOW_THRESHOLDS.model_id: EXTERNAL_FLOW_THRESHOLDS,
    INTERNAL_FLOW_THRESHOLDS.model_id: INTERNAL_FLOW_THRESHOLDS,
    LOW_REYNOLDS_THRESHOLDS.model_id: LOW_REYNOLDS_THRESHOLDS,
}


@dataclass(frozen=True, slots=True)
class ReferenceScales:
    """The length and velocity references a Reynolds/Mach number is based on."""

    label: str
    length_m: float
    velocity_m_s: float
    source: str

    def __post_init__(self) -> None:
        if not self.label.strip() or not self.source.strip():
            raise TurbulenceValidationError("REFERENCE_IDENTITY_REQUIRED")
        if not isfinite(self.length_m) or self.length_m <= 0.0:
            raise TurbulenceValidationError("REFERENCE_LENGTH_INVALID")
        if not isfinite(self.velocity_m_s) or self.velocity_m_s < 0.0:
            raise TurbulenceValidationError("REFERENCE_VELOCITY_INVALID")

    def reynolds(self, *, density_kg_m3: float, viscosity_pa_s: float) -> float:
        return reynolds_number(
            density_kg_m3=density_kg_m3,
            velocity_m_s=self.velocity_m_s,
            length_m=self.length_m,
            viscosity_pa_s=viscosity_pa_s,
        )

    def mach(self, *, speed_of_sound_m_s: float) -> float:
        return mach_number(
            velocity_m_s=self.velocity_m_s, speed_of_sound_m_s=speed_of_sound_m_s
        )

    def canonical(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "lengthM": self.length_m,
            "velocityMS": self.velocity_m_s,
            "source": self.source,
        }


@dataclass(frozen=True, slots=True)
class FlowState:
    """The generic flow-regime contract for one aerodynamic region or surface."""

    label: str
    reynolds_number: float
    mach_number: float
    turbulence_intensity: float
    reference: ReferenceScales
    wall_temperature_k: float | None = None
    adiabatic_wall: bool = True
    conjugate_heat_transfer: bool = False
    roughness: RoughnessSpec | None = None
    transition_state: TransitionState = TransitionState.UNKNOWN
    pressure_gradient_parameter: float = 0.0
    separation_fraction: float = 0.0
    thresholds: RegimeThresholds = EXTERNAL_FLOW_THRESHOLDS
    source: str = "declared"

    def __post_init__(self) -> None:
        if not self.label.strip() or not self.source.strip():
            raise TurbulenceValidationError("FLOW_STATE_IDENTITY_REQUIRED")
        if not isfinite(self.reynolds_number) or self.reynolds_number <= 0.0:
            raise TurbulenceValidationError("REYNOLDS_NUMBER_INVALID")
        if not isfinite(self.mach_number) or self.mach_number < 0.0:
            raise TurbulenceValidationError("MACH_NUMBER_INVALID")
        if not isfinite(self.turbulence_intensity) or not 0.0 <= self.turbulence_intensity <= 1.0:
            raise TurbulenceValidationError("TURBULENCE_INTENSITY_OUT_OF_RANGE")
        if not isfinite(self.separation_fraction) or not 0.0 <= self.separation_fraction <= 1.0:
            raise TurbulenceValidationError("SEPARATION_FRACTION_OUT_OF_RANGE")
        if not isfinite(self.pressure_gradient_parameter):
            raise TurbulenceValidationError("PRESSURE_GRADIENT_PARAMETER_INVALID")
        if self.wall_temperature_k is not None and (
            not isfinite(self.wall_temperature_k) or self.wall_temperature_k <= 0.0
        ):
            raise TurbulenceValidationError("WALL_TEMPERATURE_INVALID")
        if self.conjugate_heat_transfer and self.wall_temperature_k is None:
            raise TurbulenceValidationError("CONJUGATE_HEAT_TRANSFER_REQUIRES_WALL_TEMPERATURE")

    @property
    def regime(self) -> FlowRegime:
        return classify_regime(self).regime

    @property
    def compressibility(self) -> CompressibilityRegime:
        return self.thresholds.classify_mach(self.mach_number)

    def canonical(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "reynoldsNumber": self.reynolds_number,
            "machNumber": self.mach_number,
            "turbulenceIntensity": self.turbulence_intensity,
            "reference": self.reference.canonical(),
            "wallTemperatureK": self.wall_temperature_k,
            "adiabaticWall": self.adiabatic_wall,
            "conjugateHeatTransfer": self.conjugate_heat_transfer,
            "roughness": self.roughness.canonical() if self.roughness else None,
            "transitionState": self.transition_state.value,
            "pressureGradientParameter": self.pressure_gradient_parameter,
            "separationFraction": self.separation_fraction,
            "thresholds": self.thresholds.canonical(),
            "source": self.source,
        }


@dataclass(frozen=True, slots=True)
class RegimeClassification:
    """The classified regime with its checks and provenance."""

    flow: FlowState
    regime: FlowRegime
    compressibility: CompressibilityRegime
    checks: dict[str, bool]
    detail: str
    provenance: Provenance
    software: SoftwareIdentity = SOFTWARE_IDENTITY

    def canonical(self) -> dict[str, Any]:
        return {
            "label": self.flow.label,
            "regime": self.regime.value,
            "compressibility": self.compressibility.value,
            "checks": dict(self.checks),
            "detail": self.detail,
            "units": {
                "reynoldsNumber": "1",
                "machNumber": "1",
                "turbulenceIntensity": "1",
                "separationFraction": "1",
            },
            "inputsHash": self.provenance.inputs_hash,
            "source": self.provenance.source.value,
            "software": self.software.canonical(),
        }


def reynolds_number(
    *, density_kg_m3: float, velocity_m_s: float, length_m: float, viscosity_pa_s: float
) -> float:
    """``Re = rho U L / mu`` with every argument validated and finite."""
    for label, value in (
        ("density", density_kg_m3),
        ("velocity", velocity_m_s),
        ("length", length_m),
        ("viscosity", viscosity_pa_s),
    ):
        if not isfinite(value):
            raise TurbulenceValidationError(f"REYNOLDS_INPUT_NONFINITE:{label}")
    if density_kg_m3 <= 0.0 or viscosity_pa_s <= 0.0 or length_m <= 0.0 or velocity_m_s < 0.0:
        raise TurbulenceValidationError("REYNOLDS_INPUT_OUT_OF_RANGE")
    return density_kg_m3 * velocity_m_s * length_m / viscosity_pa_s


def mach_number(*, velocity_m_s: float, speed_of_sound_m_s: float) -> float:
    """``Ma = U / a`` with a strictly positive speed of sound."""
    if not isfinite(velocity_m_s) or velocity_m_s < 0.0:
        raise TurbulenceValidationError("MACH_VELOCITY_INVALID")
    if not isfinite(speed_of_sound_m_s) or speed_of_sound_m_s <= 0.0:
        raise TurbulenceValidationError("MACH_SPEED_OF_SOUND_INVALID")
    return velocity_m_s / speed_of_sound_m_s


def classify_regime(flow: FlowState) -> RegimeClassification:
    """Classify the Reynolds regime and Mach compressibility band.

    An observed transition state overrides the Reynolds band: a declared fully
    turbulent state is turbulent, and a declared natural/forced/laminar-
    separation state is at least transitional. This keeps the three states
    distinct and validity-bounded.
    """
    regime = flow.thresholds.classify_reynolds(flow.reynolds_number)
    if flow.transition_state is TransitionState.FULLY_TURBULENT:
        regime = FlowRegime.TURBULENT
    elif flow.transition_state in (
        TransitionState.NATURAL,
        TransitionState.FORCED,
        TransitionState.LAMINAR_SEPARATION,
    ) and regime is FlowRegime.LAMINAR:
        regime = FlowRegime.TRANSITIONAL
    compressibility = flow.thresholds.classify_mach(flow.mach_number)
    checks = {
        "reynolds_positive": flow.reynolds_number > 0.0,
        "mach_nonnegative": flow.mach_number >= 0.0,
        "intensity_in_range": 0.0 <= flow.turbulence_intensity <= 1.0,
        "separation_in_range": 0.0 <= flow.separation_fraction <= 1.0,
        "transition_consistent": not (
            flow.transition_state is TransitionState.FULLY_TURBULENT
            and flow.reynolds_number <= flow.thresholds.laminar_reynolds_max
        ),
    }
    detail = (
        f"{flow.label}: Re={flow.reynolds_number:.6g} -> {regime.value}; "
        f"Ma={flow.mach_number:.6g} -> {compressibility.value}; "
        f"transition={flow.transition_state.value}"
    )
    provenance = analytical_provenance(
        "turbulence.regime.classification",
        {
            "flow": flow.canonical(),
            "regime": regime.value,
            "compressibility": compressibility.value,
        },
        f"regime bands: {flow.thresholds.model_id}@{flow.thresholds.revision}",
        f"band source: {flow.thresholds.source}",
    )
    return RegimeClassification(
        flow=flow,
        regime=regime,
        compressibility=compressibility,
        checks=checks,
        detail=detail,
        provenance=provenance,
    )


def _require_property(
    evaluation: IdealGasEvaluation, prop: PropertyId, *, fluid: WorkingFluid
) -> float:
    if not evaluation.has(prop):
        raise TurbulenceCapabilityUnavailableError(
            f"MISSING_FLUID_PROPERTY:{prop.value}:{fluid.identity}"
        )
    return evaluation.value(prop)


def flow_state_from_fluid(
    fluid: WorkingFluid,
    *,
    label: str,
    pressure_pa: float,
    temperature_k: float,
    length_m: float,
    velocity_m_s: float,
    turbulence_intensity: float = 0.01,
    transition_state: TransitionState = TransitionState.UNKNOWN,
    wall_temperature_k: float | None = None,
    adiabatic_wall: bool = True,
    conjugate_heat_transfer: bool = False,
    roughness: RoughnessSpec | None = None,
    pressure_gradient_parameter: float = 0.0,
    separation_fraction: float = 0.0,
    thresholds: RegimeThresholds = EXTERNAL_FLOW_THRESHOLDS,
    reference_label: str = "streamwise length",
    reference_source: str = "declared reference scale",
) -> FlowState:
    """Build a :class:`FlowState` from a shared working fluid and operating point.

    Density, viscosity, and speed of sound come from the fluid-properties ideal
    gas system; a missing transport property fails closed instead of guessing.
    """
    evaluation = evaluate_ideal_gas(fluid, temperature_k=temperature_k, pressure_pa=pressure_pa)
    density = _require_property(evaluation, PropertyId.DENSITY, fluid=fluid)
    viscosity = _require_property(evaluation, PropertyId.VISCOSITY, fluid=fluid)
    sound_speed = _require_property(evaluation, PropertyId.SPEED_OF_SOUND, fluid=fluid)
    reference = ReferenceScales(
        label=reference_label,
        length_m=length_m,
        velocity_m_s=velocity_m_s,
        source=reference_source,
    )
    return FlowState(
        label=label,
        reynolds_number=reference.reynolds(density_kg_m3=density, viscosity_pa_s=viscosity),
        mach_number=reference.mach(speed_of_sound_m_s=sound_speed),
        turbulence_intensity=turbulence_intensity,
        reference=reference,
        wall_temperature_k=wall_temperature_k,
        adiabatic_wall=adiabatic_wall,
        conjugate_heat_transfer=conjugate_heat_transfer,
        roughness=roughness,
        transition_state=transition_state,
        pressure_gradient_parameter=pressure_gradient_parameter,
        separation_fraction=separation_fraction,
        thresholds=thresholds,
        source=f"fluid:{fluid.identity}",
    )


__all__ = [
    "EXTERNAL_FLOW_THRESHOLDS",
    "INTERNAL_FLOW_THRESHOLDS",
    "LOW_REYNOLDS_THRESHOLDS",
    "REGIME_THRESHOLD_PRESETS",
    "CompressibilityRegime",
    "FlowRegime",
    "FlowState",
    "ReferenceScales",
    "RegimeClassification",
    "RegimeThresholds",
    "TransitionState",
    "classify_regime",
    "flow_state_from_fluid",
    "mach_number",
    "reynolds_number",
]
