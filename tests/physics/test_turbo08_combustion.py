"""TURBO 08: governed combustion, bleed, and cooling for heat-addition systems.

The native Cantera participant is capability-gated and fails closed when the
library is absent. The reduced-order combustor-network, bleed, and cooling
models are analytical, carry provenance, and never claim native fidelity.
Electric fan/compressor architectures pay no combustion setup cost.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from aeroworkbench_core.types import ResultSource
from cantera.case import (
    canonical_combustion_case,
    combustion_input_hash,
    prepare_combustion_case,
)
from cantera.parser import parse_combustion_result, validate_combustion_result
from cantera.participants import combustion_participant
from participants.combustion_case import (
    CombustorNetworkInput,
    combustion_participant_ids,
    cooled_wall_state,
    cooling_penalty,
    evaluate_combustor_network,
    extract_bleed,
    heat_addition_required,
    inject_cooling,
    reacting_cfd_seam,
    reject_reacting_cfd_label,
    required_combustion_inputs,
    validate_combustor_network_result,
)
from participants.errors import NativeErrorCode, ParticipantError
from participants.lifecycle import JobState, NativeJobManager

_ARCH_FIXTURES = Path(__file__).resolve().parents[1] / "turbo" / "fixtures"
_FIXTURES = Path(__file__).resolve().parents[1] / "turbo" / "combustion"
_GOLDEN_RESULT = _FIXTURES / "combustion_ch4_air_result.json"


def _combustion_inputs(**overrides: object) -> dict[str, object]:
    inputs: dict[str, object] = {
        "mechanism": "gri30.yaml",
        "reactor_mode": "equilibrium",
        "finite_rate": False,
        "fuel": {
            "name": "methane",
            "composition": {"CH4": 1.0},
            "provenance": {"source": "user-spec", "reference": "turbo08-fixture"},
        },
        "oxidizer": {
            "name": "air",
            "composition": {"O2": 0.21, "N2": 0.79},
            "provenance": {"source": "user-spec", "reference": "turbo08-fixture"},
        },
        "provenance": {
            "source": "user-spec",
            "reference": "turbo08-fixture",
            "revision": "1",
        },
        "equivalence_ratio": 1.0,
        "inlet_temperature_k": 600.0,
        "inlet_pressure_pa": 792000.0,
        "air_mass_flow_kg_s": 12.0,
        "fuel_mass_flow_kg_s": 0.699,
        "fuel_lower_heating_value_j_kg": 50.0e6,
        "combustion_efficiency": 0.98,
        "pressure_loss_fraction": 0.04,
        "pattern_factor": 0.05,
    }
    inputs.update(overrides)
    return inputs


# -- A. case builder + provenance --------------------------------------------


def test_turbo08_prepare_stages_provenance_and_hash(tmp_path: Path) -> None:
    case_dir = tmp_path / "case"
    receipt = prepare_combustion_case(_combustion_inputs(), case_dir)
    assert receipt.participant_id == "combustion-reacting-flow"
    assert len(receipt.input_hash) == 64

    canonical = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
    assert canonical["library"] == "cantera"
    assert canonical["mechanism"] == "gri30.yaml"
    assert canonical["reactor_mode"] == "equilibrium"
    assert canonical["fuel"]["provenance"]["source"] == "user-spec"
    assert canonical["oxidizer"]["provenance"]["reference"] == "turbo08-fixture"
    assert canonical["provenance"]["revision"] == "1"
    assert receipt.input_hash == combustion_input_hash(canonical)


def test_turbo08_prepare_is_deterministic(tmp_path: Path) -> None:
    first = canonical_combustion_case(_combustion_inputs())
    second = canonical_combustion_case(_combustion_inputs())
    assert combustion_input_hash(first) == combustion_input_hash(second)


@pytest.mark.parametrize(
    ("overrides", "needle"),
    [
        ({"provenance": None}, "COMBUSTION_PROVENANCE_MISSING"),
        ({"mechanism": "not-a-mechanism.yaml"}, "COMBUSTION_MECHANISM_UNSUPPORTED"),
        ({"reactor_mode": "magic"}, "COMBUSTION_REACTOR_MODE_UNSUPPORTED"),
        ({"equivalence_ratio": 0.0}, "COMBUSTION_INPUT_OUT_OF_RANGE"),
        ({"pressure_loss_fraction": 0.9}, "COMBUSTION_INPUT_OUT_OF_RANGE"),
        ({"combustion_efficiency": 0.0}, "COMBUSTION_INPUT_OUT_OF_RANGE"),
        (
            {
                "fuel": {
                    "name": "methane",
                    "provenance": {"source": "s", "reference": "r"},
                }
            },
            "fuel.composition",
        ),
    ],
)
def test_turbo08_prepare_rejects_invalid_cases(
    tmp_path: Path, overrides: dict[str, object], needle: str
) -> None:
    with pytest.raises(ParticipantError) as failed:
        prepare_combustion_case(_combustion_inputs(**overrides), tmp_path / "case")
    assert failed.value.code is NativeErrorCode.PREPARATION_FAILED
    assert needle in failed.value.detail


def test_turbo08_finite_rate_modes_require_finite_rate(tmp_path: Path) -> None:
    with pytest.raises(ParticipantError) as failed:
        prepare_combustion_case(
            _combustion_inputs(reactor_mode="psr", finite_rate=False), tmp_path / "case"
        )
    assert "COMBUSTION_FINITE_RATE_REQUIRED" in failed.value.detail

    case_dir = tmp_path / "psr"
    prepare_combustion_case(
        _combustion_inputs(reactor_mode="psr", finite_rate=True), case_dir
    )
    canonical = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
    assert canonical["reactor_mode"] == "psr"
    assert canonical["finite_rate"] is True


def test_turbo08_reactor_network_requires_reactors(tmp_path: Path) -> None:
    with pytest.raises(ParticipantError) as failed:
        prepare_combustion_case(
            _combustion_inputs(
                reactor_mode="reactor-network", finite_rate=True, reactor_network={}
            ),
            tmp_path / "case",
        )
    assert "reactor_network.reactors" in failed.value.detail

    case_dir = tmp_path / "network"
    prepare_combustion_case(
        _combustion_inputs(
            reactor_mode="reactor-network",
            finite_rate=True,
            reactor_network={"reactors": ["PSR", "PSR"], "residence_time_s": 0.004},
        ),
        case_dir,
    )
    canonical = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
    assert canonical["reactor_network"]["reactors"] == ["PSR", "PSR"]


# -- A/B. parser + validity ---------------------------------------------------


def _golden_case(tmp_path: Path, **mutations: object) -> Path:
    case_dir = tmp_path / "case"
    case_dir.mkdir(parents=True, exist_ok=True)
    payload = json.loads(_GOLDEN_RESULT.read_text(encoding="utf-8"))
    payload.update(mutations)
    (case_dir / "result.json").write_text(json.dumps(payload), encoding="utf-8")
    return case_dir


def test_turbo08_parser_reads_golden_equilibrium(tmp_path: Path) -> None:
    parsed = parse_combustion_result(_golden_case(tmp_path))
    assert parsed.scalars["exit_total_temperature_k"] == pytest.approx(2621.9)
    assert parsed.scalars["exit_total_pressure_pa"] == pytest.approx(760320.0)
    assert parsed.scalars["heat_release_w"] == pytest.approx(34251000.0)
    assert parsed.scalars["combustion_efficiency"] == pytest.approx(0.98)
    assert parsed.scalars["pressure_loss_fraction"] == pytest.approx(0.04)
    assert parsed.scalars["converged"] == pytest.approx(1.0)
    assert parsed.scalars["x_CO2"] == pytest.approx(0.0806)
    assert parsed.units["exit_total_temperature_k"] == "K"
    assert parsed.units["x_CO2"] == "dimensionless"


def test_turbo08_validity_accepts_physical_result(tmp_path: Path) -> None:
    parsed = parse_combustion_result(_golden_case(tmp_path))
    report = validate_combustion_result(dict(parsed.scalars), _combustion_inputs())
    assert report.passed is True
    assert all(report.checks.values())


@pytest.mark.parametrize(
    ("mutation", "failed_check"),
    [
        ({"converged": False}, "converged"),
        ({"exit_total_temperature_k": 100.0}, "temperature_physical"),
        ({"heat_release_w": 1.0e6}, "energy_closure"),
        ({"mole_fractions": {"N2": 0.5, "CO2": 0.5, "CH4": 0.5}}, "species_bounded"),
    ],
)
def test_turbo08_validity_rejects_unphysical_result(
    tmp_path: Path, mutation: dict[str, object], failed_check: str
) -> None:
    parsed = parse_combustion_result(_golden_case(tmp_path, **mutation))
    report = validate_combustion_result(dict(parsed.scalars), _combustion_inputs())
    assert report.passed is False
    assert report.checks[failed_check] is False


def test_turbo08_parser_rejects_non_cantera_result(tmp_path: Path) -> None:
    case_dir = _golden_case(tmp_path, library="openfoam")
    with pytest.raises(ParticipantError) as failed:
        parse_combustion_result(case_dir)
    assert failed.value.code is NativeErrorCode.PARSER_FAILED


# -- B. combustor network -----------------------------------------------------


def test_turbo08_combustor_network_closes_energy_and_pressure() -> None:
    inputs = CombustorNetworkInput(
        inlet_temperature_k=600.0,
        inlet_pressure_pa=792000.0,
        air_mass_flow_kg_s=12.0,
        fuel_mass_flow_kg_s=0.699,
        fuel_lower_heating_value_j_kg=50.0e6,
        combustion_efficiency=0.98,
        pressure_loss_fraction=0.04,
        cp_exit_j_kg_k=1500.0,
        equivalence_ratio=1.0,
        pattern_factor=0.05,
        residence_time_s=0.005,
    )
    result = evaluate_combustor_network(inputs)
    assert result.heat_release_w == pytest.approx(0.98 * 0.699 * 50.0e6)
    assert result.exit_total_pressure_pa == pytest.approx(792000.0 * 0.96)
    assert result.exit_total_temperature_k > inputs.inlet_temperature_k
    assert result.exit_peak_temperature_k > result.exit_total_temperature_k
    assert 0.0 <= result.stability_indicator <= 1.0
    assert result.provenance.source is ResultSource.ANALYTICAL

    report = validate_combustor_network_result(
        result.canonical(), inputs.canonical()
    )
    assert report.passed is True


# -- C. bleed / cooling -------------------------------------------------------


def test_turbo08_bleed_conserves_mass_and_enthalpy() -> None:
    bleed = extract_bleed(
        mass_flow_kg_s=12.0,
        total_temperature_k=700.0,
        total_pressure_pa=8.0e5,
        cp_j_kg_k=1050.0,
        bleed_fraction=0.1,
        composition=(("air", 1.0),),
    )
    assert bleed.bleed_mass_flow_kg_s == pytest.approx(1.2)
    assert bleed.core_mass_flow_kg_s == pytest.approx(10.8)
    assert bleed.enthalpy_closure_error == pytest.approx(0.0, abs=1e-12)
    assert bleed.composition == (("air", 1.0),)


def test_turbo08_cooling_injection_mixes_and_closes() -> None:
    cooling = inject_cooling(
        main_mass_flow_kg_s=10.8,
        main_temperature_k=700.0,
        main_cp_j_kg_k=1050.0,
        coolant_mass_flow_kg_s=1.2,
        coolant_temperature_k=400.0,
        coolant_cp_j_kg_k=1000.0,
        main_composition=(("air", 1.0),),
        coolant_composition=(("air", 1.0),),
    )
    assert cooling.mixed_mass_flow_kg_s == pytest.approx(12.0)
    assert 400.0 < cooling.mixed_temperature_k < 700.0
    assert cooling.enthalpy_closure_error == pytest.approx(0.0, abs=1e-12)
    assert cooling.mass_closure_error == pytest.approx(0.0, abs=1e-12)


def test_turbo08_cooling_penalty_reduces_work_and_efficiency() -> None:
    penalty = cooling_penalty(shaft_power_w=1.0e6, cooling_fraction=0.05)
    assert penalty.work_penalty_w == pytest.approx(5.0e4)
    assert penalty.net_shaft_power_w == pytest.approx(9.5e5)
    assert penalty.efficiency_penalty == pytest.approx(0.05)


def test_turbo08_cooled_wall_feeds_thermal_state() -> None:
    state = cooled_wall_state(
        gas_temperature_k=1400.0,
        coolant_temperature_k=600.0,
        gas_side_h_w_m2_k=500.0,
        coolant_side_h_w_m2_k=3000.0,
        wall_thickness_m=0.003,
        wall_conductivity_w_m_k=25.0,
    )
    assert state.gas_side_heat_flux_w_m2 > 0.0
    assert 600.0 < state.metal_temperature_k < 1400.0
    assert state.provenance.source is ResultSource.ANALYTICAL


# -- F. optionality -----------------------------------------------------------


def _node_kinds(name: str) -> list[str]:
    payload = json.loads((_ARCH_FIXTURES / name).read_text(encoding="utf-8"))
    return [str(node["kind"]) for node in payload["nodes"]]


def test_turbo08_electric_fan_architecture_is_untouched() -> None:
    kinds = _node_kinds("single_ducted_fan.json")
    assert heat_addition_required(kinds) is False
    assert combustion_participant_ids(kinds) == ()
    assert required_combustion_inputs(kinds) == ()


def test_turbo08_heat_addition_architecture_requires_combustion() -> None:
    kinds = _node_kinds("core_compressor_combustor_turbine.json")
    assert heat_addition_required(kinds) is True
    assert combustion_participant_ids(kinds) == ("combustion-reacting-flow",)
    assert "mechanism" in required_combustion_inputs(kinds)


# -- D. reacting CFD is a distinct fidelity ----------------------------------


def test_turbo08_reacting_cfd_is_distinct_and_unavailable() -> None:
    seam = reacting_cfd_seam()
    assert seam.available is False
    assert seam.fidelity == "reacting-rans"
    with pytest.raises(ParticipantError) as failed:
        reject_reacting_cfd_label("reacting-rans")
    assert failed.value.code is NativeErrorCode.PREPARATION_FAILED
    assert reject_reacting_cfd_label("equilibrium") == "equilibrium"


# -- manifest contract --------------------------------------------------------


def test_turbo08_manifest_contract() -> None:
    manifest = combustion_participant()
    assert manifest.participant_id == "combustion-reacting-flow"
    assert manifest.executable.solver_id == "cantera"
    assert manifest.executable.execution_mode == "in-process"
    assert manifest.execute_ref is not None
    assert "equilibrium" in manifest.fidelity_levels
    assert {"psr", "reactor-network"} <= set(manifest.fidelity_levels)
    assert manifest.artifacts == ("case.json", "result.json")
    assert manifest.checkpoint is False


# -- governed path fail-closed -----------------------------------------------


@pytest.fixture
def combustion_registered(monkeypatch: pytest.MonkeyPatch) -> object:
    from participants import lifecycle as lifecycle_mod
    from participants import manifest as manifest_mod

    manifest = combustion_participant()
    monkeypatch.setitem(manifest_mod._REGISTRY, manifest.participant_id, manifest)
    monkeypatch.setattr(
        lifecycle_mod,
        "_ALLOWED_MODULES",
        frozenset(
            set(lifecycle_mod._ALLOWED_MODULES)
            | {"participants.combustion_case", "participants.combustion_parser"}
        ),
    )
    return manifest


def test_turbo08_governed_path_fails_closed_without_cantera(
    tmp_path: Path, combustion_registered: object
) -> None:
    from participants.capabilities import probe_participant

    if probe_participant("combustion-reacting-flow").state == "ready":
        pytest.skip("Cantera library is installed; native run covered separately")

    manager = NativeJobManager(tmp_path / "jobs")
    try:
        job_id = manager.submit(
            "combustion-reacting-flow", _combustion_inputs(), deferred=True
        )
        assert manager.run(job_id) == JobState.FAILED.value
        status = manager.status(job_id)
        assert status["error_code"] == NativeErrorCode.CAPABILITY_UNAVAILABLE.value
        assert [event["state"] for event in manager.events(job_id)] == [
            JobState.QUEUED.value,
            JobState.PREPARING.value,
            JobState.FAILED.value,
        ]
        case_dir = tmp_path / "jobs" / f"case-{job_id[:12]}"
        assert (case_dir / "case.json").is_file()
        assert not (case_dir / "result.json").exists()
    finally:
        manager.close()
