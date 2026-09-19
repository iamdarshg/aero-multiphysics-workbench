"""Hardware-in-the-loop and replay interface.

A controller (or digital model) is driven against a :class:`SignalStream`:
either a recorded stream (:func:`replay`, always available and deterministic)
or a live hardware stream (:func:`run_hardware`, capability-gated and fail
closed). The harness knows nothing about any specific product; it only reads
frames and writes commands through typed contracts. Every run reports its
evidence kind, source, fidelity, validity, and provenance.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from aeroworkbench_core.types import Provenance
from aeroworkbench_optimization.design_space import content_digest

from .contracts import DEFAULT_SOFTWARE, EvidenceFidelity, EvidenceKind, SoftwareIdentity, Validity
from .errors import CapabilityUnavailable, ExperimentError, finite
from .provenance import measurement_provenance

__all__ = [
    "Controller",
    "Frame",
    "HilCapability",
    "HilFrame",
    "HilRunReport",
    "ReplayStream",
    "SignalStream",
    "hil_capability",
    "replay",
    "require_hil_hardware",
    "run_hardware",
]


@dataclass(frozen=True, slots=True)
class Frame:
    """One timestamped stream frame read by the harness."""

    time_s: float
    values: Mapping[str, float]
    origin: EvidenceKind

    def __post_init__(self) -> None:
        finite(self.time_s, "frame time")
        for name, value in self.values.items():
            finite(value, f"frame value {name}")

    def canonical(self) -> dict[str, Any]:
        return {
            "timeS": self.time_s,
            "values": {key: float(value) for key, value in sorted(self.values.items())},
            "origin": self.origin.value,
        }


class SignalStream(Protocol):
    """A source of timestamped frames (recorded or live)."""

    def frames(self) -> Iterable[Frame]: ...


class Controller(Protocol):
    """A controller/digital model driven by the harness."""

    def reset(self) -> None: ...

    def update(self, frame: Frame) -> Mapping[str, float]: ...


@dataclass(frozen=True, slots=True)
class ReplayStream:
    """A deterministic recorded stream."""

    recorded: tuple[Frame, ...]

    def __post_init__(self) -> None:
        if not self.recorded:
            raise ExperimentError("REPLAY_STREAM_IS_EMPTY")

    def frames(self) -> tuple[Frame, ...]:
        return self.recorded


@dataclass(frozen=True, slots=True)
class HilFrame:
    """One harness step: measurement in, command out."""

    time_s: float
    measurement: Mapping[str, float]
    command: Mapping[str, float]

    def canonical(self) -> dict[str, Any]:
        return {
            "timeS": self.time_s,
            "measurement": {key: float(value) for key, value in sorted(self.measurement.items())},
            "command": {key: float(value) for key, value in sorted(self.command.items())},
        }


@dataclass(frozen=True, slots=True)
class HilRunReport:
    """A complete HIL/replay run with explicit evidence identity."""

    run_id: str
    origin: EvidenceKind
    fidelity: EvidenceFidelity
    frames: tuple[HilFrame, ...]
    validity: Validity
    inputs_hash: str
    software: SoftwareIdentity
    provenance: Provenance

    @property
    def frame_count(self) -> int:
        return len(self.frames)

    def canonical(self) -> dict[str, Any]:
        return {
            "runId": self.run_id,
            "origin": self.origin.value,
            "fidelity": self.fidelity.value,
            "frameCount": self.frame_count,
            "frames": [frame.canonical() for frame in self.frames],
            "validity": self.validity.canonical(),
            "inputsHash": self.inputs_hash,
            "software": self.software.canonical(),
        }

    def digest(self) -> str:
        return content_digest(self.canonical())


@dataclass(frozen=True, slots=True)
class HilCapability:
    """Whether a native hardware/DAQ capability is present, and why."""

    requirement: str
    state: str
    available: bool
    detail: str = ""


def hil_capability(requirement: str, *, present: bool = False) -> HilCapability:
    """Report hardware/DAQ availability without pretending."""

    if not requirement.strip():
        raise ExperimentError("HIL_REQUIREMENT_REQUIRED")
    if present:
        return HilCapability(requirement, "available", True, "hardware/DAQ backend is wired")
    return HilCapability(requirement, "unavailable", False, "no hardware/DAQ backend is wired")


def require_hil_hardware(requirement: str, *, present: bool = False) -> HilCapability:
    """Fail closed unless live hardware/DAQ is actually wired."""

    state = hil_capability(requirement, present=present)
    if not state.available:
        raise CapabilityUnavailable(f"HIL_CAPABILITY_UNAVAILABLE:{requirement}")
    return state


def _drive(
    controller: Controller,
    frames: Iterable[Frame],
    *,
    run_id: str,
    origin: EvidenceKind,
    fidelity: EvidenceFidelity,
    max_frames: int | None,
) -> tuple[HilFrame, ...]:
    if not run_id.strip():
        raise ExperimentError("HIL_RUN_ID_REQUIRED")
    if max_frames is not None and max_frames < 1:
        raise ExperimentError("HIL_MAX_FRAMES_MUST_BE_POSITIVE")
    controller.reset()
    produced: list[HilFrame] = []
    for index, frame in enumerate(frames):
        if max_frames is not None and index >= max_frames:
            break
        command = controller.update(frame)
        produced.append(
            HilFrame(time_s=frame.time_s, measurement=dict(frame.values), command=dict(command))
        )
    if not produced:
        raise ExperimentError("HIL_RUN_PRODUCED_NO_FRAMES")
    return tuple(produced)


def _report(
    run_id: str,
    origin: EvidenceKind,
    fidelity: EvidenceFidelity,
    frames: tuple[HilFrame, ...],
) -> HilRunReport:
    payload = {
        "runId": run_id,
        "origin": origin.value,
        "fidelity": fidelity.value,
        "frames": [frame.canonical() for frame in frames],
    }
    return HilRunReport(
        run_id=run_id,
        origin=origin,
        fidelity=fidelity,
        frames=frames,
        validity=Validity(
            passed=True,
            checks={"frames-produced": bool(frames)},
            detail="controller driven over the declared stream",
        ),
        inputs_hash=content_digest(payload),
        software=DEFAULT_SOFTWARE,
        provenance=measurement_provenance(
            "hardware-in-the-loop-replay",
            payload,
            assumptions=("commands are produced by the supplied controller",),
        ),
    )


def replay(
    controller: Controller,
    stream: SignalStream,
    *,
    run_id: str,
    max_frames: int | None = None,
) -> HilRunReport:
    """Drive a controller against a recorded stream; always available."""

    frames = _drive(
        controller,
        stream.frames(),
        run_id=run_id,
        origin=EvidenceKind.REPLAY,
        fidelity=EvidenceFidelity.REPLAY,
        max_frames=max_frames,
    )
    return _report(run_id, EvidenceKind.REPLAY, EvidenceFidelity.REPLAY, frames)


def run_hardware(
    controller: Controller,
    stream: SignalStream,
    *,
    run_id: str,
    hardware_present: bool = False,
    max_frames: int | None = None,
) -> HilRunReport:
    """Drive a controller against live hardware; fails closed when absent."""

    require_hil_hardware(f"hil:{run_id}", present=hardware_present)
    frames = _drive(
        controller,
        stream.frames(),
        run_id=run_id,
        origin=EvidenceKind.HARDWARE_IN_LOOP,
        fidelity=EvidenceFidelity.HARDWARE,
        max_frames=max_frames,
    )
    return _report(run_id, EvidenceKind.HARDWARE_IN_LOOP, EvidenceFidelity.HARDWARE, frames)
