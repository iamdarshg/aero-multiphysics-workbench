from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from aeroworkbench_core.design import PhysicalDesignState, compare_variants
from aeroworkbench_core.envelope import (
    AircraftDefinition,
    EnvelopeLimits,
    EnvelopePoint,
    EnvelopeStatus,
    evaluate_operating_envelope,
)
from aeroworkbench_core.storage import SQLiteMetadataStore
from aeroworkbench_core.types import Quantity


def test_operating_envelope_classifies_viable_constrained_and_failed_points() -> None:
    aircraft = AircraftDefinition(
        mass_kg=4.0,
        wing_area_m2=0.50,
        cd0=0.025,
        induced_drag_factor=0.055,
        available_thrust_n=45.0,
    )
    limits = EnvelopeLimits(max_current_a=80.0, max_temperature_k=360.0, max_load_factor=8.0)
    points = [
        EnvelopePoint(
            airspeed_m_s=35, density_kg_m3=1.225, load_factor=1, current_a=45, temperature_k=330
        ),
        EnvelopePoint(
            airspeed_m_s=24, density_kg_m3=1.225, load_factor=5, current_a=75, temperature_k=355
        ),
        EnvelopePoint(
            airspeed_m_s=20, density_kg_m3=1.225, load_factor=9, current_a=90, temperature_k=370
        ),
    ]

    result = evaluate_operating_envelope(aircraft, limits, points)

    assert [point.status for point in result.points] == [
        EnvelopeStatus.VIABLE,
        EnvelopeStatus.CONSTRAINED,
        EnvelopeStatus.FAILED,
    ]
    assert result.points[2].violations == (
        "load_factor",
        "motor_current",
        "temperature",
        "insufficient_thrust",
    )


def test_variant_comparison_reports_parameter_and_result_deltas() -> None:
    baseline = PhysicalDesignState(
        design_id="edf",
        variant_id="base",
        parameters={"tip_clearance": Quantity(value=0.30, unit="mm")},
        geometry_hash="a" * 64,
        material_hash="b" * 64,
        scalar_results={"thrust": Quantity(value=40.0, unit="N")},
    )
    candidate = baseline.create_variant(
        variant_id="candidate",
        changes={"tip_clearance": Quantity(value=0.36, unit="mm")},
        author="optimizer",
        reason="margin",
        created_at=datetime(2026, 9, 9, tzinfo=UTC),
        scalar_results={"thrust": Quantity(value=40.16, unit="N")},
    )

    comparison = compare_variants(baseline, candidate)

    assert comparison.parameter_deltas["tip_clearance"].absolute_si == pytest.approx(0.00006)
    assert comparison.result_deltas["thrust"].percent == pytest.approx(0.4)


def test_sqlite_metadata_store_roundtrips_designs_and_job_events(tmp_path: Path) -> None:
    store = SQLiteMetadataStore(tmp_path / "metadata.sqlite3")
    design = PhysicalDesignState(
        design_id="edf",
        variant_id="base",
        parameters={"diameter": Quantity(value=70, unit="mm")},
        geometry_hash="a" * 64,
        material_hash="b" * 64,
    )

    store.save_design(design)
    loaded = store.get_design("edf", "base")
    store.create_job("job-1", "edf-demo")
    store.append_job_event("job-1", "running", {"phase": "analytical"})
    store.append_job_event("job-1", "completed", {"thrust_n": 15.5})

    assert loaded == design
    assert [event.status for event in store.list_job_events("job-1")] == [
        "queued",
        "running",
        "completed",
    ]
    job = store.get_job("job-1")
    assert job is not None
    assert job.status == "completed"
    store.close()
