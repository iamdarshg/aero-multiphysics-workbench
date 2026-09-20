"""TURBO 10: multi-point off-design maps, controls, and envelope optimization."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from aeroworkbench_core.types import ResultSource
from aeroworkbench_turbomachinery import architecture_from_payload
from aeroworkbench_turbomachinery.cycle import (
    AIR,
    CycleDesign,
    build_screening_map,
    compile_cycle_model,
)
from aeroworkbench_turbomachinery.cycle.components import ComponentParameters
from aeroworkbench_turbomachinery.fidelity.native import (
    CapabilityStatus,
    NativeCapabilityGate,
    NativeCapabilityState,
    NativeReceipt,
)
from aeroworkbench_turbomachinery.offdesign import (
    AggregateOutcome,
    AggregationMode,
    ControlChannel,
    ControlSchedule,
    EnvelopeAxis,
    EnvelopeSpec,
    MapReference,
    NativeOffdesignRequest,
    OffdesignCapabilityUnavailable,
    OffdesignFidelity,
    OffdesignInputError,
    OffdesignPointResult,
    OperatingPoint,
    aggregate_multipoint,
    aggregate_objective,
    classify_match,
    envelope_result,
    evaluate_multipoint,
    evaluate_point,
    generate_envelope,
    native_offdesign_status,
    objectives_from_matches,
    operating_points_hash,
    pareto_front,
    point_result,
    refine_envelope,
    request_native_offdesign,
    surge_margin_for,
)

_FIXTURES = Path(__file__).resolve().parents[1] / "turbo" / "offdesign"


def _arch() -> Any:
    return architecture_from_payload(
        json.loads((_FIXTURES / "single_fan.json").read_text(encoding="utf-8"))
    )


def _design() -> CycleDesign:
    return CycleDesign(
        architecture=_arch(),
        component_parameters=(
            ("inlet", ComponentParameters(pressure_recovery=0.94)),
            (
                "fan",
                ComponentParameters(pressure_ratio=1.158, isentropic_efficiency=0.90),
            ),
            ("nozzle", ComponentParameters(ambient_pressure_pa=101325.0)),
            ("motor", ComponentParameters(machine_efficiency=0.95)),
        ),
        gas=AIR,
        ambient_total_pressure_pa=101325.0,
        ambient_total_temperature_k=288.15,
        mass_flow_kg_s=4.5,
    )


def _fan_map() -> MapReference:
    return MapReference(
        node_id="fan",
        component_map=build_screening_map(
            machine="fan",
            design_corrected_speed=3000.0,
            design_corrected_flow=4.5,
            design_pressure_ratio=1.158,
            design_efficiency=0.90,
        ),
        design_corrected_flow=4.5,
    )


def _points() -> tuple[OperatingPoint, ...]:
    return (
        OperatingPoint(
            point_id="takeoff",
            ambient_pressure_pa=101325.0,
            ambient_temperature_k=288.15,
            mass_flow_kg_s=4.5,
            spool_speeds_rpm=(("fan-spool", 3000.0),),
            throttle=0.9,
            voltage_v=400.0,
            current_a=120.0,
            state_of_charge=0.8,
            bleed_fraction=0.0,
            weight=0.5,
        ),
        OperatingPoint(
            point_id="cruise",
            ambient_pressure_pa=90000.0,
            ambient_temperature_k=280.0,
            ambient_density_kg_m3=1.1,
            inlet_velocity_m_s=120.0,
            inlet_mach=0.35,
            mass_flow_kg_s=3.8,
            spool_speeds_rpm=(("fan-spool", 3000.0),),
            shaft_torque_n_m=150.0,
            shaft_load_w=45000.0,
            throttle=0.7,
            heat_input_w=0.0,
            voltage_v=350.0,
            current_a=90.0,
            state_of_charge=0.8,
            vgv_angle_deg=5.0,
            nozzle_area_m2=0.05,
            weight=0.3,
        ),
        OperatingPoint(
            point_id="idle",
            ambient_pressure_pa=101325.0,
            ambient_temperature_k=288.15,
            mass_flow_kg_s=3.6,
            spool_speeds_rpm=(("fan-spool", 3000.0),),
            throttle=0.3,
            weight=0.2,
        ),
    )


def _schedule(ids: tuple[str, ...]) -> ControlSchedule:
    return ControlSchedule(
        channels=(
            ControlChannel(
                channel_id="fuel",
                variable="fuel_heat_input",
                values=tuple((point_id, 0.5) for point_id in ids),
                lower=0.0,
                upper=1.0,
                max_slew=1.0,
                monotonic="none",
            ),
            ControlChannel(
                channel_id="bleed",
                variable="bleed",
                values=tuple((point_id, 0.01) for point_id in ids),
                lower=0.0,
                upper=0.05,
                max_slew=0.05,
                monotonic="none",
            ),
        )
    )


def test_turbo10_operating_points_cover_all_dimensions() -> None:
    points = _points()
    assert operating_points_hash(points) == operating_points_hash(tuple(reversed(points)))
    cruise = points[1]
    assert cruise.ambient_density_kg_m3 == 1.1
    assert cruise.inlet_mach == 0.35
    assert cruise.state_of_charge == 0.8
    assert cruise.vgv_angle_deg == 5.0


def test_turbo10_operating_point_validation_fails_closed() -> None:
    with pytest.raises(OffdesignInputError):
        OperatingPoint(point_id=" ", mass_flow_kg_s=1.0)
    with pytest.raises(OffdesignInputError):
        OperatingPoint(point_id="bad", mass_flow_kg_s=-1.0)
    with pytest.raises(OffdesignInputError):
        OperatingPoint(point_id="bad", throttle=1.5)
    with pytest.raises(OffdesignInputError):
        OperatingPoint(point_id="bad", bleed_fraction=1.0)
    with pytest.raises(OffdesignInputError):
        operating_points_hash(())
    with pytest.raises(OffdesignInputError):
        operating_points_hash(
            (OperatingPoint(point_id="dup"), OperatingPoint(point_id="dup"))
        )


def test_turbo10_offdesign_matching_solves_every_point() -> None:
    design = _design()
    points = _points()
    matches, model = evaluate_multipoint(
        design, points, maps=(_fan_map(),), schedule=_schedule(tuple(p.point_id for p in points))
    )
    assert model.digest == compile_cycle_model(design).digest
    assert [match.point_id for match in matches] == ["cruise", "idle", "takeoff"]
    for match in matches:
        assert match.converged
        assert match.hard_passed
        assert match.thrust_n >= 0.0
        assert match.shaft_power_w > 0.0
        assert match.map_valid


def test_turbo10_map_validity_and_surge_margin_enforced() -> None:
    design = _design()
    model = compile_cycle_model(design)
    reference = _fan_map()
    good = OperatingPoint(point_id="good", mass_flow_kg_s=4.5)
    match, _ = evaluate_point(model, good, maps=(reference,))
    assert match.map_valid
    assert match.surge_margin > 0.0
    assert surge_margin_for(reference.component_map, 3000.0, 4.5) == pytest.approx(
        match.surge_margin, rel=1e-9
    )
    tiny = OperatingPoint(point_id="tiny", mass_flow_kg_s=0.05)
    choked, _ = evaluate_point(model, tiny, maps=(reference,))
    assert not choked.hard_passed
    assert classify_match(choked, 0.05) == "failed"


def test_turbo10_schedule_constraints_fail_closed() -> None:
    ids = ("a", "b")
    bad_range = ControlSchedule(
        channels=(
            ControlChannel(
                channel_id="fuel",
                variable="fuel_heat_input",
                values=(("a", 0.5), ("b", 2.0)),
                lower=0.0,
                upper=1.0,
            ),
        )
    )
    assert bad_range.validate(ids) == ("fuel:b:range",)
    bad_slew = ControlSchedule(
        channels=(
            ControlChannel(
                channel_id="vgv",
                variable="variable_guide_vane",
                values=(("a", 0.0), ("b", 10.0)),
                lower=-20.0,
                upper=20.0,
                max_slew=1.0,
            ),
        )
    )
    assert bad_slew.validate(ids) == ("vgv:slew",)
    bad_mono = ControlSchedule(
        channels=(
            ControlChannel(
                channel_id="spd",
                variable="speed",
                values=(("a", 2.0), ("b", 1.0)),
                lower=0.0,
                upper=5.0,
                monotonic="increasing",
            ),
        )
    )
    assert bad_mono.validate(ids) == ("spd:monotonicity",)
    with pytest.raises(OffdesignInputError):
        ControlChannel(
            channel_id="x", variable="no-such-variable", values=(("a", 1.0),),
            lower=0.0, upper=1.0,
        )
    with pytest.raises(OffdesignInputError):
        evaluate_multipoint(_design(), _points(), schedule=bad_range)


def test_turbo10_aggregation_modes_and_hard_violation_propagation() -> None:
    matches, _ = evaluate_multipoint(_design(), _points(), maps=(_fan_map(),))
    entries = objectives_from_matches(matches)
    weighted = aggregate_objective(
        entries, "shaft_power_w", AggregationMode.WEIGHTED, maximize=False
    )
    assert isinstance(weighted, AggregateOutcome)
    assert weighted.passed and weighted.score is not None and weighted.score > 0.0
    worst = aggregate_objective(entries, "thrust_n", AggregationMode.WORST_CASE)
    assert worst.score == pytest.approx(min(entry.value("thrust_n") for entry in entries))
    minimax = aggregate_objective(
        entries, "shaft_power_w", AggregationMode.MINIMAX, maximize=False
    )
    assert minimax.score == pytest.approx(
        min(entry.value("shaft_power_w") for entry in entries)
    )
    robust = aggregate_objective(
        entries, "thrust_n", AggregationMode.PERCENTILE, percentile=50.0
    )
    assert robust.passed and robust.score is not None
    both = aggregate_multipoint(
        entries,
        ("thrust_n", "shaft_power_w"),
        AggregationMode.WEIGHTED,
        maximize=(True, False),
    )
    assert len(both) == 2 and all(outcome.passed for outcome in both)
    front = pareto_front(entries, ("thrust_n", "shaft_power_w"), (True, False))
    assert front and set(front) <= {entry.point_id for entry in entries}
    failed = objectives_from_matches(
        (
            next(iter(matches)),
            type(matches[0])(
                point_id="broken",
                converged=False,
                thrust_n=0.0,
                shaft_power_w=0.0,
                max_residual=1.0,
                surge_margin=-1.0,
                map_valid=False,
                checks=(("cycle_converged", False),),
                warnings=(),
            ),
        )
    )
    propagated = aggregate_objective(failed, "thrust_n", AggregationMode.WEIGHTED)
    assert not propagated.passed and propagated.score is None


def test_turbo10_results_carry_full_envelope() -> None:
    matches, _ = evaluate_multipoint(_design(), _points(), maps=(_fan_map(),))
    by_id = {point.point_id: point for point in _points()}
    for match in matches:
        applied = {"fuel": 0.5, "bleed": 0.01}
        result = point_result(
            by_id[match.point_id], match, controls=applied,
            fidelity=OffdesignFidelity.MAP_PRELIMINARY,
        )
        assert isinstance(result, OffdesignPointResult)
        assert result.source == ResultSource.ANALYTICAL.value
        assert result.fidelity == OffdesignFidelity.MAP_PRELIMINARY.value
        assert dict(result.units)["thrustN"] == "N"
        assert result.validity.passed
        assert len(result.input_hash) == 64
        assert result.software.name == "aeroworkbench-turbomachinery-offdesign"
        assert result.provenance.inputs_hash == result.input_hash
        assert result.result_hash == point_result(
            by_id[match.point_id], match, controls=applied
        ).result_hash
    with pytest.raises(OffdesignInputError):
        point_result(by_id["cruise"], next(m for m in matches if m.point_id != "cruise"))


def test_turbo10_envelope_generation_and_refinement_bounded() -> None:
    design = _design()
    model = compile_cycle_model(design)
    reference = _fan_map()

    def _evaluate(point: OperatingPoint):
        match, _ = evaluate_point(model, point, maps=(reference,))
        return match

    base = OperatingPoint(point_id="base", spool_speeds_rpm=(("fan-spool", 3000.0),))
    spec = EnvelopeSpec(
        axes=(
            EnvelopeAxis(field="mass_flow_kg_s", lower=2.0, upper=6.0, cells=3),
            EnvelopeAxis(field="ambient_pressure_pa", lower=80000.0, upper=101325.0, cells=3),
        ),
        base=base,
        min_surge_margin=0.05,
    )
    cells, envelope_points = generate_envelope(_evaluate, spec)
    assert len(cells) == 9
    assert len(envelope_points) == 9
    assert {cell.status for cell in cells} <= {"viable", "constrained", "failed"}
    refined = refine_envelope(_evaluate, spec, cells)
    assert len(refined) <= 16
    envelope = envelope_result(spec, cells, refined)
    assert envelope.source == ResultSource.ANALYTICAL.value
    assert envelope.fidelity == OffdesignFidelity.ENVELOPE_SCREENING.value
    assert len(envelope.input_hash) == 64
    assert envelope.result_hash == envelope_result(spec, cells, refined).result_hash
    counts = envelope.status_counts()
    assert sum(counts.values()) == len(cells) + len(refined)
    with pytest.raises(OffdesignInputError):
        EnvelopeSpec(
            axes=(EnvelopeAxis(field="mass_flow_kg_s", lower=1.0, upper=9.0, cells=9),
                  EnvelopeAxis(field="throttle", lower=0.0, upper=1.0, cells=9)),
            base=base,
        )


def test_turbo10_native_paths_fail_closed() -> None:
    status = native_offdesign_status()
    assert not status.available
    gate = NativeCapabilityGate(
        {"turbomachinery-offdesign-native": CapabilityStatus(
            "turbomachinery-offdesign-native", NativeCapabilityState.READY, "9.9")}
    )
    assert native_offdesign_status(gate).available
    with pytest.raises(OffdesignCapabilityUnavailable):
        request_native_offdesign(NativeOffdesignRequest(points=_points()))
    trusted = NativeReceipt(
        capability="turbomachinery-offdesign-native",
        solver_name="native-offdesign",
        solver_version="9.9",
        run_id="run-1",
        inputs_hash="0" * 64,
        trusted=True,
    )
    with pytest.raises(OffdesignCapabilityUnavailable):
        request_native_offdesign(
            NativeOffdesignRequest(points=_points(), receipt=trusted),
            gate,
        )
