"""Rotating-flow acoustics, instability, and thermoacoustic escalation (TURBO 09).

Noise and unsteady instability are first-class optional physics for rotating gas
machinery. The subpackage derives rotating-order forcing from the actual
architecture (no hard-coded blade counts), post-processes aeroacoustics through a
capability-gated fidelity ladder, tracks compressor/fan stall/rotating-stall/surge
proximity, screens heat-release/pressure thermoacoustics for heat-addition
systems only, and hands forcing spectra to the shared structural-resonance
policy. Every result carries source/fidelity/units/validity/input-hash/
software-identity/provenance, and native levels fail closed.

Public API:

    from aeroworkbench_turbomachinery.acoustics import (
        AcousticFidelity, AcousticLevel, AcousticRung, AeroacousticLadder,
        default_aeroacoustic_ladder,
        OrderFamily, OrderTerm, RotatingOrder, OrderSpectrum,
        derive_order_spectrum, shaft_speeds_rpm,
        TonalLine, TonalScreeningResult, screen_tonal_orders,
        SurfacePressureSpectrum, surface_pressure_spectrum_from_record,
        ObserverSplResult, observer_spl_from_spectrum, propagate_fw_h,
        StabilityBoundary, OperatingPoint, OscillationLine, UnsteadyOscillation,
        InstabilityIndicators, assess_instability, rotating_stall_order,
        AcousticModeEstimate, HeatReleaseSpectrum, ThermoacousticInput,
        ThermoacousticResult, estimate_acoustic_modes, rayleigh_index,
        assess_thermoacoustics,
        StructuralHandoff, spectrum_to_forcing_lines,
        couple_forcing_to_structure, evaluate_structural_response,
        AcousticPromotion, acoustic_promotion_signals, plan_acoustic_escalation,
    )
"""

from .capabilities import (
    ACOUSTIC_CAPABILITY_GATE,
    NativeAcousticRequirement,
    acoustic_capability_gate,
    native_acoustic_capability,
    require_native_acoustic,
    trusted_acoustic_receipt,
)
from .coupling import (
    StructuralHandoff,
    couple_forcing_to_structure,
    evaluate_structural_response,
    spectrum_to_forcing_lines,
)
from .errors import (
    AcousticCapabilityUnavailable,
    AcousticError,
    AcousticInputError,
    AcousticValidityError,
)
from .escalation import (
    AcousticPromotion,
    acoustic_promotion_signals,
    plan_acoustic_escalation,
)
from .instability import (
    InstabilityIndicators,
    OperatingPoint,
    OscillationLine,
    StabilityBoundary,
    UnsteadyOscillation,
    assess_instability,
    rotating_stall_order,
)
from .orders import (
    OrderFamily,
    OrderSpectrum,
    OrderTerm,
    RotatingOrder,
    derive_order_spectrum,
    shaft_speeds_rpm,
)
from .results import (
    DEFAULT_ACOUSTIC_SOFTWARE,
    REFERENCE_PRESSURE_PA,
    SOFTWARE_IDENTITY,
    SOFTWARE_VERSION,
    AcousticFidelity,
    AcousticSoftware,
    AcousticValidity,
    analytical_provenance,
    check_validity,
    energy_sum_db,
    finite,
    finite_series,
    native_provenance,
    spectrum_lines,
    spl_db,
)
from .spectra import (
    AcousticLevel,
    AcousticRung,
    AeroacousticLadder,
    ObserverSplLine,
    ObserverSplResult,
    SurfacePressureSpectrum,
    TonalLine,
    TonalScreeningResult,
    default_aeroacoustic_ladder,
    observer_spl_from_spectrum,
    propagate_fw_h,
    screen_tonal_orders,
    surface_pressure_spectrum_from_record,
)
from .thermoacoustics import (
    AcousticModeEstimate,
    HeatReleaseSpectrum,
    ThermoacousticInput,
    ThermoacousticResult,
    assess_thermoacoustics,
    estimate_acoustic_modes,
    rayleigh_index,
)

__all__ = [
    "ACOUSTIC_CAPABILITY_GATE",
    "DEFAULT_ACOUSTIC_SOFTWARE",
    "REFERENCE_PRESSURE_PA",
    "SOFTWARE_IDENTITY",
    "SOFTWARE_VERSION",
    "AcousticCapabilityUnavailable",
    "AcousticError",
    "AcousticFidelity",
    "AcousticInputError",
    "AcousticLevel",
    "AcousticModeEstimate",
    "AcousticPromotion",
    "AcousticRung",
    "AcousticSoftware",
    "AcousticValidity",
    "AcousticValidityError",
    "AeroacousticLadder",
    "HeatReleaseSpectrum",
    "InstabilityIndicators",
    "NativeAcousticRequirement",
    "ObserverSplLine",
    "ObserverSplResult",
    "OperatingPoint",
    "OrderFamily",
    "OrderSpectrum",
    "OrderTerm",
    "OscillationLine",
    "RotatingOrder",
    "StabilityBoundary",
    "StructuralHandoff",
    "SurfacePressureSpectrum",
    "ThermoacousticInput",
    "ThermoacousticResult",
    "TonalLine",
    "TonalScreeningResult",
    "UnsteadyOscillation",
    "acoustic_capability_gate",
    "acoustic_promotion_signals",
    "analytical_provenance",
    "assess_instability",
    "assess_thermoacoustics",
    "check_validity",
    "couple_forcing_to_structure",
    "default_aeroacoustic_ladder",
    "derive_order_spectrum",
    "energy_sum_db",
    "estimate_acoustic_modes",
    "evaluate_structural_response",
    "finite",
    "finite_series",
    "native_acoustic_capability",
    "native_provenance",
    "observer_spl_from_spectrum",
    "plan_acoustic_escalation",
    "propagate_fw_h",
    "rayleigh_index",
    "require_native_acoustic",
    "rotating_stall_order",
    "screen_tonal_orders",
    "shaft_speeds_rpm",
    "spectrum_lines",
    "spectrum_to_forcing_lines",
    "spl_db",
    "surface_pressure_spectrum_from_record",
    "trusted_acoustic_receipt",
]
