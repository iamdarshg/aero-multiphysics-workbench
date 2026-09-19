"""Solver/test fusion: simulation and experiment samples stay identified.

A map may contain separately identified simulation and experimental samples.
Calibration derives offsets from paired points but never erases source lineage:
calibrated samples keep their original source/kind and record the sample ids
they were derived from.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from aeroworkbench_optimization.design_space import content_digest

from .errors import MapContractError
from .map import MapSample, point_key

__all__ = [
    "CalibrationOffset",
    "SampleSet",
    "calibrate_simulation",
    "calibration_offsets",
    "fused_sample_set",
    "merge_samples",
]


@dataclass(frozen=True, slots=True)
class SampleSet:
    """A fused collection of samples with lineage preserved."""

    samples: tuple[MapSample, ...]

    def simulations(self) -> tuple[MapSample, ...]:
        return tuple(sample for sample in self.samples if sample.kind.value == "simulation")

    def experiments(self) -> tuple[MapSample, ...]:
        return tuple(sample for sample in self.samples if sample.kind.value == "experiment")

    def digest(self) -> str:
        return content_digest([sample.as_dict() for sample in self.samples])


@dataclass(frozen=True, slots=True)
class CalibrationOffset:
    """Mean measured-minus-simulated offset for one output."""

    name: str
    offset: float
    count: int

    def as_dict(self) -> dict[str, object]:
        return {"name": self.name, "offset": self.offset, "count": self.count}


def merge_samples(*groups: Sequence[MapSample]) -> SampleSet:
    """Merge sample groups, rejecting duplicate sample ids."""

    merged: dict[str, MapSample] = {}
    for group in groups:
        for sample in group:
            existing = merged.get(sample.sample_id)
            if existing is not None and existing != sample:
                raise MapContractError(f"DUPLICATE_SAMPLE_ID:{sample.sample_id}")
            merged[sample.sample_id] = sample
    return SampleSet(tuple(merged[sample_id] for sample_id in sorted(merged)))


def calibration_offsets(
    simulation: Sequence[MapSample], experiment: Sequence[MapSample]
) -> tuple[CalibrationOffset, ...]:
    """Per-output mean offsets over points present in both sample sets."""

    simulated = {point_key(sample.inputs): sample for sample in simulation}
    totals: dict[str, float] = {}
    counts: dict[str, int] = {}
    for sample in experiment:
        match = simulated.get(point_key(sample.inputs))
        if match is None:
            continue
        for name, value in sample.outputs.items():
            if name not in match.outputs:
                raise MapContractError(f"CALIBRATION_OUTPUT_MISMATCH:{name}")
            totals[name] = totals.get(name, 0.0) + (value - match.outputs[name])
            counts[name] = counts.get(name, 0) + 1
    return tuple(
        CalibrationOffset(name, totals[name] / counts[name], counts[name])
        for name in sorted(totals)
    )


def calibrate_simulation(
    simulation: Sequence[MapSample],
    offsets: Sequence[CalibrationOffset],
    *,
    revision: int,
) -> tuple[MapSample, ...]:
    """Apply offsets to simulation samples without erasing source lineage."""

    if revision < 1:
        raise MapContractError("CALIBRATION_REVISION_MUST_BE_POSITIVE")
    shift = {offset.name: offset.offset for offset in offsets}
    calibrated: list[MapSample] = []
    for sample in simulation:
        outputs = {
            name: value + shift.get(name, 0.0) for name, value in sample.outputs.items()
        }
        calibrated.append(
            MapSample(
                sample_id=f"{sample.sample_id}~cal{revision}",
                inputs=dict(sample.inputs),
                outputs=outputs,
                source=sample.source,
                kind=sample.kind,
                cost=sample.cost,
                lineage=(sample.sample_id, *sample.lineage),
                solver=sample.solver,
                run_id=sample.run_id,
            )
        )
    return tuple(calibrated)


def fused_sample_set(
    simulation: Sequence[MapSample],
    experiment: Sequence[MapSample],
    *,
    offsets: Sequence[CalibrationOffset] | None = None,
    revision: int = 1,
) -> SampleSet:
    """Fuse simulation and experimental samples, optionally calibrated."""

    active = (
        calibration_offsets(simulation, experiment) if offsets is None else tuple(offsets)
    )
    calibrated = (
        calibrate_simulation(simulation, active, revision=revision)
        if active
        else tuple(simulation)
    )
    return merge_samples(calibrated, experiment)
