"""TURBO 09: rotating-flow acoustics, instability, and thermoacoustic escalation.

Forcing orders are derived from the actual rows and shaft speeds (never
hard-coded), aeroacoustics follows a capability-gated fidelity ladder that fails
closed, stall/rotating-stall/surge proximity is measured against declared
stability boundaries, thermoacoustics activates only for heat-addition systems
and couples to the TURBO 08 combustion participant, and detected forcing spectra
feed the shared structural-resonance policy.
"""

from __future__ import annotations

import json
from math import pi, sin
from pathlib import Path
from typing import Any

import pytest
from aeroworkbench_aeroelasticity import (
    AeroelasticFidelity,
    ModalBasis,
    StructuralMode,
)
from aeroworkbench_core.types import ResultSource
from aeroworkbench_turbomachinery import architecture_from_payload
from aeroworkbench_turbomachinery.acoustics import (
    AcousticCapabilityUnavailable,
    AcousticFidelity,
    AcousticInputError,
    AcousticLevel,
    AeroacousticLadder,
    HeatReleaseSpectrum,
    InstabilityIndicators,
    NativeAcousticRequirement,
    OperatingPoint,
    OrderFamily,
    OrderSpectrum,
    OscillationLine,
    StabilityBoundary,
    ThermoacousticInput,
    UnsteadyOscillation,
    acoustic_promotion_signals,
    assess_instability,
    assess_thermoacoustics,
    couple_forcing_to_structure,
    default_aeroacoustic_ladder,
    derive_order_spectrum,
    estimate_acoustic_modes,
    evaluate_structural_response,
    observer_spl_from_spectrum,
    plan_acoustic_escalation,
    propagate_fw_h,
    rotating_stall_order,
    screen_tonal_orders,
    shaft_speeds_rpm,
    spectrum_to_forcing_lines,
    surface_pressure_spectrum_from_record,
)
from aeroworkbench_turbomachinery.fidelity import architecture_features
from aeroworkbench_turbomachinery.fidelity.native import (
    CapabilityStatus,
    NativeCapabilityGate,
    NativeCapabilityState,
    NativeReceipt,
)
from participants.combustion_case import CombustorNetworkInput, evaluate_combustor_network

_FIXTURES = Path(__file__).resolve().parents[1] / "turbo" / "acoustics"
_FW_H = NativeAcousticRequirement.FW_H_PROPAGATION.value


def _arch(name: str) -> Any:
    return architecture_from_payload(json.loads((_FIXTURES / name).read_text(encoding="utf-8")))


def _features(name: str, **kwargs: Any) -> Any:
    return architecture_features(_arch(name), **kwargs)


def _spectrum(name: str = "rotating_core.json", **kwargs: Any) -> OrderSpectrum:
    return derive_order_spectrum(_arch(name), **kwargs)


def _order(spectrum: OrderSpectrum, order_id: str) -> Any:
    for order in spectrum.orders:
        if order.order_id == order_id:
            return order
    raise AssertionError(f"missing order {order_id}")


def _ready(capability: str) -> NativeCapabilityGate:
    return NativeCapabilityGate(
        {capability: CapabilityStatus(capability, NativeCapabilityState.READY, "1.0")}
    )


# -- A. rotating-order forcing -------------------------------------------------


def test_turbo09_orders_derive_from_declared_rows_and_speeds() -> None:
    spectrum = _spectrum()
    assert spectrum.architecture_hash == _arch("rotating_core.json").architecture_hash
    assert dict(shaft_speeds_rpm(_arch("rotating_core.json"))) == {
        "lp-spool": 3600.0,
        "hp-spool": 24000.0,
    }

    fan_blade = _order(spectrum, "blade:fan-rotor:h1")
    assert fan_blade.family is OrderFamily.BLADE_PASSING
    assert fan_blade.order == 18.0
    assert fan_blade.frequency_hz({"lp-spool": 3600.0}) == pytest.approx(1080.0)

    comp_blade = _order(spectrum, "blade:comp-rotor:h1")
    turbine_blade = _order(spectrum, "blade:turbine-rotor:h1")
    assert comp_blade.order == 29.0
    assert turbine_blade.order == 37.0

    vane = _order(spectrum, "vane:stator-1:rotor:fan-rotor:h1")
    assert vane.family is OrderFamily.VANE_PASSING
    assert vane.order == 24.0
    assert vane.frequency_hz({"lp-spool": 3600.0}) == pytest.approx(1440.0)

    interaction = _order(spectrum, "rs:comp-rotor:stator-1:m1n1:m")
    assert interaction.family is OrderFamily.ROTOR_STATOR
    assert interaction.order == pytest.approx(abs(29.0 - 24.0))
    summed = _order(spectrum, "rs:fan-rotor:stator-1:m1n1:p")
    assert summed.order == pytest.approx(18.0 + 24.0)

    shaft_order = _order(spectrum, "shaft:hp-spool:h1")
    assert shaft_order.family is OrderFamily.SHAFT
    assert shaft_order.frequency_hz({"hp-spool": 24000.0}) == pytest.approx(400.0)


def test_turbo09_orders_have_no_hard_coded_blade_counts() -> None:
    payload = json.loads((_FIXTURES / "rotating_core.json").read_text(encoding="utf-8"))
    for row in payload["rows"]:
        if row["id"] == "fan-rotor":
            row["periodicity"] = 31
    changed = derive_order_spectrum(architecture_from_payload(payload))
    changed_fan = _order(changed, "blade:fan-rotor:h1")
    assert changed_fan.order == 31.0
    assert changed_fan.frequency_hz({"lp-spool": 3600.0}) == pytest.approx(
        31.0 * 3600.0 / 60.0
    )
    assert changed.digest != _spectrum().digest


def test_turbo09_orders_include_multi_shaft_sidebands_and_are_deterministic() -> None:
    spectrum = _spectrum(include_sidebands=True)
    sidebands = spectrum.orders_for_family(OrderFamily.MULTI_SHAFT_SIDEBAND)
    assert sidebands
    speeds = spectrum.speed_map()
    for order in sidebands:
        assert len(order.terms) == 2
        assert order.frequency_hz(speeds) >= 0.0
    first = derive_order_spectrum(_arch("rotating_core.json"), harmonics=2)
    second = derive_order_spectrum(_arch("rotating_core.json"), harmonics=2)
    assert first.canonical() == second.canonical()
    assert first.digest == second.digest


def test_turbo09_no_rows_produce_no_orders() -> None:
    payload = json.loads((_FIXTURES / "fan_only.json").read_text(encoding="utf-8"))
    payload["rows"] = []
    payload["shafts"] = []
    keep = ("ambient", "inlet", "nozzle", "exhaust")
    payload["nodes"] = [item for item in payload["nodes"] if item["kind"] in keep]
    payload["edges"] = [
        {"from": "ambient", "to": "inlet", "kind": "flow", "station": "0"},
        {"from": "inlet", "to": "nozzle", "kind": "flow", "station": "1"},
        {"from": "nozzle", "to": "exhaust", "kind": "flow", "station": "2"},
    ]
    spectrum = derive_order_spectrum(architecture_from_payload(payload))
    assert spectrum.orders == ()
    assert spectrum.families() == ()


# -- B. fidelity ladder and aeroacoustic post-processing -----------------------


def test_turbo09_aeroacoustic_ladder_is_ordered_and_gated() -> None:
    ladder = default_aeroacoustic_ladder()
    assert isinstance(ladder, AeroacousticLadder)
    assert [rung.rank for rung in ladder.rungs] == list(range(5))
    assert ladder.rungs[0].level is AcousticLevel.TONAL_SCREENING
    assert ladder.next_rung("surface-pressure-spectra").rung_id == "fw-h-propagation"
    assert ladder.digest == default_aeroacoustic_ladder().digest
    for rung in ladder.rungs:
        if rung.requires_native:
            assert rung.source is ResultSource.NATIVE_SOLVER
            assert rung.native_capabilities
        else:
            assert rung.source is ResultSource.ANALYTICAL


def test_turbo09_ladder_applicability_follows_heat_addition() -> None:
    ladder = default_aeroacoustic_ladder()
    fan_levels = {rung.level for rung in ladder.applicable(_features("fan_only.json"))}
    assert AcousticLevel.THERMOACOUSTIC_SCREENING not in fan_levels
    core_levels = {rung.level for rung in ladder.applicable(_features("rotating_core.json"))}
    assert AcousticLevel.THERMOACOUSTIC_SCREENING in core_levels
    assert AcousticLevel.TONAL_SCREENING in core_levels


def test_turbo09_tonal_screening_uses_only_declared_amplitudes() -> None:
    spectrum = _spectrum()
    result = screen_tonal_orders(
        spectrum,
        amplitude_by_order={
            "blade:fan-rotor:h1": 2.0,
            "shaft:hp-spool:h1": 20.0e-6,
        },
    )
    assert len(result.lines) == 2
    assert result.lines[0].order_id == "blade:fan-rotor:h1"
    assert result.lines[0].frequency_hz == pytest.approx(1080.0)
    assert result.lines[0].level_db == pytest.approx(100.0)
    assert result.dominant_level_db == pytest.approx(100.0)
    assert result.fidelity is AcousticFidelity.TONAL_SCREENING
    assert result.provenance.source is ResultSource.ANALYTICAL
    assert result.validity.passed is True
    assert result.units()["level_db"] == "dB"

    with pytest.raises(AcousticInputError):
        screen_tonal_orders(spectrum, amplitude_by_order={})
    with pytest.raises(AcousticInputError):
        screen_tonal_orders(spectrum, amplitude_by_order={"not-an-order": 1.0})


def test_turbo09_surface_pressure_spectrum_recovers_known_tone() -> None:
    sample_rate = 6400.0
    count = 64
    record = tuple(3.0 * sin(2.0 * pi * 800.0 * index / sample_rate) for index in range(count))
    spectrum = surface_pressure_spectrum_from_record(
        record, sample_rate, interface_id="fan-suction"
    )
    assert spectrum.nyquist_hz == pytest.approx(3200.0)
    peak = max(spectrum.lines, key=lambda line: line[1])
    assert peak[0] == pytest.approx(800.0)
    assert peak[1] == pytest.approx(3.0, rel=0.05)
    assert spectrum.fidelity is AcousticFidelity.SURFACE_SPECTRA
    assert spectrum.provenance.source is ResultSource.ANALYTICAL
    with pytest.raises(AcousticInputError):
        surface_pressure_spectrum_from_record((1.0, 2.0), sample_rate, interface_id="x")


def test_turbo09_observer_spl_applies_declared_transmission_loss() -> None:
    record = tuple(sin(2.0 * pi * 800.0 * index / 6400.0) for index in range(64))
    spectrum = surface_pressure_spectrum_from_record(record, 6400.0, interface_id="wall")
    observer = observer_spl_from_spectrum(spectrum, transmission_loss_db=12.0, distance_m=2.0)
    assert observer.fidelity is AcousticFidelity.OBSERVER_SPL
    for line in observer.lines:
        assert line.observer_level_db == pytest.approx(line.source_level_db - 12.0)
    assert observer.overall_level_db >= max(line.observer_level_db for line in observer.lines)


def test_turbo09_fw_h_propagation_fails_closed_but_trusted_receipt_runs() -> None:
    record = tuple(sin(2.0 * pi * 800.0 * index / 6400.0) for index in range(64))
    spectrum = surface_pressure_spectrum_from_record(record, 6400.0, interface_id="wall")

    with pytest.raises(AcousticCapabilityUnavailable):
        propagate_fw_h(spectrum, capability_gate=NativeCapabilityGate(), receipt=None)

    receipt = NativeReceipt(
        capability=_FW_H,
        solver_name="libAcoustics",
        solver_version="1.2.0",
        run_id="run-42",
        inputs_hash="a" * 64,
    )
    with pytest.raises(AcousticCapabilityUnavailable):
        propagate_fw_h(spectrum, capability_gate=_ready(_FW_H), receipt=None)
    with pytest.raises(AcousticCapabilityUnavailable):
        propagate_fw_h(
            spectrum,
            capability_gate=_ready(_FW_H),
            receipt=NativeReceipt(
                capability=_FW_H,
                solver_name="libAcoustics",
                solver_version="1.2.0",
                run_id="run-42",
                inputs_hash="a" * 64,
                trusted=False,
            ),
        )

    result = propagate_fw_h(spectrum, capability_gate=_ready(_FW_H), receipt=receipt)
    assert result.fidelity is AcousticFidelity.FW_H_PROPAGATION
    assert result.provenance.source is ResultSource.NATIVE_SOLVER
    assert result.provenance.solver_name == "libAcoustics"
    assert result.provenance.run_id == "run-42"
    assert result.validity.passed is True


# -- C. compressor/fan instability indicators ----------------------------------


def _surge_boundary() -> StabilityBoundary:
    return StabilityBoundary(
        boundary_id="surge",
        kind="surge",
        speed_rpm=3600.0,
        mass_flow_kg_s=(50.0, 80.0, 110.0, 140.0),
        pressure_ratio=(1.8, 2.0, 2.2, 2.4),
    )


def test_turbo09_instability_margins_track_boundary_distance() -> None:
    clear = assess_instability(
        OperatingPoint(mass_flow_kg_s=200.0, pressure_ratio=2.3, speed_rpm=3600.0),
        surge_boundary=_surge_boundary(),
    )
    assert isinstance(clear, InstabilityIndicators)
    assert clear.state == "clear"
    assert clear.proximity == pytest.approx(1.0)
    assert clear.required_capability is None

    triggered = assess_instability(
        OperatingPoint(mass_flow_kg_s=126.0, pressure_ratio=2.3, speed_rpm=3600.0),
        surge_boundary=_surge_boundary(),
    )
    assert triggered.state == "triggered"
    assert triggered.proximity < 0.1
    assert triggered.required_capability == "transient-cfd"
    assert triggered.promotion_signal()["choke_stall_surge_proximity"] < 0.1

    with pytest.raises(AcousticInputError):
        assess_instability(
            OperatingPoint(mass_flow_kg_s=130.0, pressure_ratio=2.3, speed_rpm=3600.0),
            surge_boundary=_surge_boundary(),
            margin_scale=0.0,
        )


def test_turbo09_rotating_stall_order_and_oscillation_content() -> None:
    oscillation = UnsteadyOscillation(
        signal="mass-flow",
        mean_value=30.0,
        lines=(OscillationLine(label="cell-1", frequency_hz=30.0, amplitude=1.5, order=0.5),),
    )
    assert rotating_stall_order(oscillation, shaft_frequency_hz=60.0) == pytest.approx(0.5)
    indicators = assess_instability(
        OperatingPoint(mass_flow_kg_s=200.0, pressure_ratio=2.3, speed_rpm=3600.0),
        surge_boundary=_surge_boundary(),
        oscillation=oscillation,
    )
    assert indicators.state == "watch"
    assert indicators.rotating_stall_order == pytest.approx(0.5)
    assert indicators.mass_flow_oscillation_fraction == pytest.approx(0.05)
    assert indicators.required_capability == "unsteady-cfd"

    no_order = UnsteadyOscillation(
        signal="pressure",
        mean_value=200000.0,
        lines=(OscillationLine(label="mode-1", frequency_hz=30.0, amplitude=40000.0),),
    )
    assert rotating_stall_order(no_order, shaft_frequency_hz=60.0) == pytest.approx(0.5)


# -- D. thermoacoustics --------------------------------------------------------


def _modes() -> tuple[Any, ...]:
    return estimate_acoustic_modes(
        cavity_length_m=0.3, speed_of_sound_m_s=1150.0, mode_numbers=(1, 2, 3)
    )


def test_turbo09_acoustic_mode_estimation_is_closed_form() -> None:
    modes = _modes()
    assert [mode.frequency_hz for mode in modes] == [
        pytest.approx(1150.0 / 1.2),
        pytest.approx(3.0 * 1150.0 / 1.2),
        pytest.approx(5.0 * 1150.0 / 1.2),
    ]
    half = estimate_acoustic_modes(
        cavity_length_m=0.3, speed_of_sound_m_s=1150.0, mode_numbers=(1,), boundary="half-wave"
    )
    assert half[0].frequency_hz == pytest.approx(1150.0 / 0.6)
    with pytest.raises(AcousticInputError):
        estimate_acoustic_modes(
            cavity_length_m=0.3, speed_of_sound_m_s=1150.0, boundary="magic"
        )


def test_turbo09_thermoacoustics_inactive_without_heat_addition() -> None:
    result = assess_thermoacoustics(ThermoacousticInput(heat_addition=False))
    assert result.active is False
    assert result.state == "inactive"
    assert result.rayleigh_index is None
    assert result.required_capability is None
    assert result.validity.passed is True
    assert result.provenance.source is ResultSource.ANALYTICAL


def test_turbo09_thermoacoustics_detects_rayleigh_growth() -> None:
    modes = _modes()
    frequencies = tuple(mode.frequency_hz for mode in modes)
    pressure = tuple(
        (frequency, amplitude)
        for frequency, amplitude in zip(frequencies, (100.0, 50.0, 25.0), strict=True)
    )
    heat = tuple(
        (frequency, amplitude)
        for frequency, amplitude in zip(frequencies, (1000.0, 500.0, 250.0), strict=True)
    )
    heat_release = HeatReleaseSpectrum(lines=heat, mean_heat_release_w=5.0e6)
    in_phase = ThermoacousticInput(
        heat_addition=True,
        acoustic_modes=modes,
        pressure_spectrum=pressure,
        heat_release=heat_release,
        phases_rad=tuple((frequency, 0.0) for frequency in frequencies),
    )
    unstable = assess_thermoacoustics(in_phase)
    assert unstable.active is True
    assert unstable.rayleigh_index == pytest.approx(1.0)
    assert unstable.state == "unstable"
    assert unstable.required_capability == "reacting-unsteady-cfd"

    out_of_phase = ThermoacousticInput(
        heat_addition=True,
        acoustic_modes=modes,
        pressure_spectrum=pressure,
        heat_release=heat_release,
        phases_rad=tuple((frequency, pi) for frequency in frequencies),
    )
    stable = assess_thermoacoustics(out_of_phase)
    assert stable.rayleigh_index == pytest.approx(-1.0)
    assert stable.state == "stable"
    assert stable.required_capability is None

    with pytest.raises(AcousticInputError):
        assess_thermoacoustics(ThermoacousticInput(heat_addition=True, acoustic_modes=modes))


def test_turbo09_thermoacoustics_couples_to_turbo08_heat_release() -> None:
    combustor = evaluate_combustor_network(
        CombustorNetworkInput(
            inlet_temperature_k=600.0,
            inlet_pressure_pa=792000.0,
            air_mass_flow_kg_s=12.0,
            fuel_mass_flow_kg_s=0.699,
            fuel_lower_heating_value_j_kg=50.0e6,
            combustion_efficiency=0.98,
            pressure_loss_fraction=0.04,
            cp_exit_j_kg_k=1500.0,
            equivalence_ratio=1.0,
            residence_time_s=0.005,
        )
    )
    modes = _modes()
    frequencies = tuple(mode.frequency_hz for mode in modes)
    heat_release = HeatReleaseSpectrum(
        lines=tuple((frequency, 0.02 * combustor.heat_release_w) for frequency in frequencies),
        mean_heat_release_w=combustor.heat_release_w,
        combustor_model="reduced-combustor-network",
        combustor_inputs_hash=combustor.provenance.inputs_hash,
    )
    result = assess_thermoacoustics(
        ThermoacousticInput(
            heat_addition=True,
            acoustic_modes=modes,
            pressure_spectrum=tuple((frequency, 150.0) for frequency in frequencies),
            heat_release=heat_release,
            phases_rad=tuple((frequency, 0.4) for frequency in frequencies),
        )
    )
    assert result.mean_heat_release_w == pytest.approx(combustor.heat_release_w)
    assert 0.0 < result.rayleigh_index < 1.0
    assert result.state in ("near-margin", "unstable")
    assert result.provenance.source is ResultSource.ANALYTICAL


# -- E. structural resonance coupling ------------------------------------------


def test_turbo09_forcing_spectra_couple_to_resonance_policy() -> None:
    spectrum = _spectrum()
    lines = spectrum_to_forcing_lines(spectrum)
    assert any(line.source == "rotating-order-spectrum" for line in lines)
    assert any(abs((line.frequency_hz or 0.0) - 1080.0) < 1e-6 for line in lines)

    near = couple_forcing_to_structure(spectrum, mode_frequencies_hz=(1080.0,))
    assert near.state == "triggered"
    assert near.required_capability == "transient-forced-response"
    assert near.assessment.lines[0].margin_hz == pytest.approx(0.0)
    assert near.fidelity_signal(reference_hz=1000.0)["resonance_proximity"] == pytest.approx(0.0)

    far = couple_forcing_to_structure(spectrum, mode_frequencies_hz=(5000.0,))
    assert far.state == "clear"
    assert far.required_capability is None


def test_turbo09_structural_response_reuses_aeroelastic_harmonic_path() -> None:
    spectrum = _spectrum()
    lines = spectrum_to_forcing_lines(spectrum, amplitude_by_order={"blade:fan-rotor:h1": 500.0})
    basis = ModalBasis(
        basis_id="fan-blade",
        modes=(
            StructuralMode(
                mode_id="mode-1",
                frequency_hz=1080.0,
                damping_ratio=0.02,
                generalized_mass_kg=1.5,
                shape=((0.0, 0.0, 1.0),),
            ),
            StructuralMode(
                mode_id="mode-2",
                frequency_hz=6000.0,
                damping_ratio=0.03,
                generalized_mass_kg=2.0,
                shape=((1.0, 0.0, 0.0),),
            ),
        ),
    )
    result = evaluate_structural_response(basis, lines, speed_rpm=3600.0)
    assert result.fidelity is AeroelasticFidelity.HARMONIC
    assert result.provenance.source is ResultSource.ANALYTICAL
    assert result.validity.passed is True
    assert result.peak_mode_id in ("mode-1", "mode-2")


# -- F. automatic higher-fidelity escalation -----------------------------------


def test_turbo09_escalation_requests_higher_fidelity_and_fails_closed() -> None:
    ladder = default_aeroacoustic_ladder()
    features = _features("rotating_core.json", acoustics_requested=True)
    triggered = assess_instability(
        OperatingPoint(mass_flow_kg_s=126.0, pressure_ratio=2.3, speed_rpm=3600.0),
        surge_boundary=_surge_boundary(),
    )
    signals = acoustic_promotion_signals(instability=triggered, cost_budget=100.0)
    assert signals.choke_stall_surge_proximity < 0.1
    assert signals.required_capability == "transient-cfd"

    blocked = plan_acoustic_escalation(
        "surface-pressure-spectra",
        ladder,
        signals,
        features=features,
        requested=("fw-h",),
        capability_gate=NativeCapabilityGate(),
    )
    assert blocked.blocked is True
    assert blocked.escalate is False
    assert blocked.native_gate_ok is False
    assert blocked.blockers == (f"NATIVE_CAPABILITY_UNAVAILABLE:{_FW_H}",)

    advanced = plan_acoustic_escalation(
        "surface-pressure-spectra",
        ladder,
        signals,
        features=features,
        requested=("fw-h",),
        capability_gate=_ready(_FW_H),
    )
    assert advanced.blocked is False
    assert advanced.escalate is True
    assert advanced.target_rung == "fw-h-propagation"
    assert advanced.native_gate_ok is True

    first = plan_acoustic_escalation(
        "surface-pressure-spectra",
        ladder,
        signals,
        features=features,
        requested=("fw-h",),
        capability_gate=_ready(_FW_H),
    )
    assert first.signal_digest == advanced.signal_digest
    assert advanced.as_dict()["targetRung"] == "fw-h-propagation"


def test_turbo09_escalation_never_buys_an_unaffordable_rung() -> None:
    ladder = default_aeroacoustic_ladder()
    features = _features("rotating_core.json", acoustics_requested=True)
    triggered = assess_instability(
        OperatingPoint(mass_flow_kg_s=126.0, pressure_ratio=2.3, speed_rpm=3600.0),
        surge_boundary=_surge_boundary(),
    )
    signals = acoustic_promotion_signals(instability=triggered, cost_budget=1.0)
    outcome = plan_acoustic_escalation(
        "surface-pressure-spectra",
        ladder,
        signals,
        features=features,
        requested=("fw-h",),
        capability_gate=_ready(_FW_H),
    )
    assert outcome.blocked is True
    assert outcome.blockers == ("COST_BUDGET_EXCLUDED:fw-h-propagation",)
    assert outcome.budget_ok is False


def test_turbo09_escalation_holds_when_conditions_are_healthy() -> None:
    ladder = default_aeroacoustic_ladder()
    features = _features("rotating_core.json", acoustics_requested=True)
    quiet = assess_instability(
        OperatingPoint(mass_flow_kg_s=200.0, pressure_ratio=2.3, speed_rpm=3600.0),
        surge_boundary=_surge_boundary(),
    )
    signals = acoustic_promotion_signals(instability=quiet, cost_budget=100.0)
    outcome = plan_acoustic_escalation(
        "tonal-order-screening",
        ladder,
        signals,
        features=features,
        requested=("fw-h",),
        capability_gate=_ready(_FW_H),
    )
    assert outcome.escalate is False
    assert outcome.blocked is False
    assert outcome.target_rung == "tonal-order-screening"
