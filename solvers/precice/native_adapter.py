"""Native participant read/write hooks for the generated-mesh participants.

One :class:`NativeFieldParticipant` owns one participant's interface mesh, its
unit-bearing field buffers, and the preCICE lifetime hooks: mesh registration,
field read/write, time-window advancement, convergence/checkpoint queries,
checkpoint and rollback, and finalization. The hooks are driven through a
``PreciceBackend`` so the mechanics are testable without the native engine;
the real backend is only reachable when native preCICE is installed.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from math import isfinite

from aeroworkbench_coupling.field import InterfaceMesh
from aeroworkbench_coupling.precice import CouplingError, CouplingFailureCode
from aeroworkbench_coupling.units import convert_value, units_compatible

from .backend import NativePreciceBackend, PreciceBackend


@dataclass(frozen=True, slots=True)
class FieldBuffer:
    """One unit-bearing field buffer on a participant's interface mesh."""

    name: str
    unit: str
    dimension: str  # "scalar" | "vector"


@dataclass(frozen=True, slots=True)
class AdapterEvent:
    sequence: int
    kind: str
    checkpoint: str
    reason: str


class NativeFieldParticipant:
    """preCICE participant adapter over one generated interface mesh."""

    def __init__(
        self,
        *,
        name: str,
        backend: PreciceBackend,
        mesh_name: str,
        mesh: InterfaceMesh,
        buffers: Sequence[FieldBuffer],
        engine: str | None = None,
    ) -> None:
        if not name.strip() or not mesh_name.strip():
            raise CouplingError(
                CouplingFailureCode.INTERFACE_MISMATCH, "participant and mesh names required"
            )
        if not buffers:
            raise CouplingError(
                CouplingFailureCode.INTERFACE_MISMATCH, "at least one field buffer required"
            )
        self._backend = backend
        self._mesh_name = mesh_name
        self._mesh = mesh
        self._buffers: dict[str, FieldBuffer] = {}
        for buffer in buffers:
            if buffer.dimension not in {"scalar", "vector"}:
                raise CouplingError(
                    CouplingFailureCode.INTERFACE_MISMATCH,
                    f"invalid buffer dimension:{buffer.dimension}",
                )
            if buffer.name in self._buffers:
                raise CouplingError(
                    CouplingFailureCode.INTERFACE_MISMATCH,
                    f"duplicate field buffer:{buffer.name}",
                )
            self._buffers[buffer.name] = buffer
        self._values: dict[str, tuple[float, ...]] = {}
        self._checkpoints: dict[str, dict[str, tuple[float, ...]]] = {}
        self._events: list[AdapterEvent] = []
        if engine is not None:
            self.engine = engine
        else:
            self.engine = (
                "precice-native"
                if isinstance(backend, NativePreciceBackend)
                else "simulated-precice"
            )

    # -- lifetime --------------------------------------------------------

    def initialize(self) -> tuple[int, ...]:
        self._backend.initialize()
        vertex_ids = self._backend.set_mesh_vertices(
            self._mesh_name, self._mesh.coordinates
        )
        self._record("initialize", "", f"{len(vertex_ids)} vertices")
        return vertex_ids

    def write_field(
        self,
        name: str,
        values: Sequence[float],
        *,
        unit: str | None = None,
    ) -> None:
        buffer = self._buffer(name)
        converted = self._check_and_convert(buffer, values, unit)
        extracted = list(converted)
        self._values[name] = converted
        self._backend.write_data(name, extracted)

    def read_field(
        self, name: str, *, unit: str | None = None
    ) -> tuple[float, ...]:
        buffer = self._buffer(name)
        raw = tuple(float(value) for value in self._backend.read_data(name))
        if unit is not None and unit != buffer.unit:
            if not units_compatible(unit, buffer.unit):
                raise CouplingError(
                    CouplingFailureCode.FIELD_UNIT_MISMATCH,
                    f"{name}: requested {unit} incompatible with buffer {buffer.unit}",
                )
            raw = tuple(convert_value(value, buffer.unit, unit) for value in raw)
        return raw

    def advance(self, dt: float) -> None:
        if not isfinite(dt) or dt <= 0:
            raise CouplingError(
                CouplingFailureCode.INTERFACE_MISMATCH, f"invalid time-window dt:{dt}"
            )
        self._backend.advance(dt)

    def is_coupling_ongoing(self) -> bool:
        return self._backend.is_coupling_ongoing()

    def checkpoint_required(self) -> str | None:
        if self._backend.requires_writing_checkpoint():
            return "write"
        if self._backend.requires_reading_checkpoint():
            return "read"
        return None

    # -- checkpoint / rollback ------------------------------------------

    def checkpoint(self, token: str) -> AdapterEvent:
        if not token.strip():
            raise CouplingError(
                CouplingFailureCode.CHECKPOINT_ROLLBACK_FAILURE, "checkpoint token required"
            )
        self._checkpoints[token] = dict(self._values)
        return self._record("checkpoint", token, "accepted state")

    def rollback(self, token: str, *, reason: str) -> AdapterEvent:
        if not token.strip() or not reason.strip():
            raise CouplingError(
                CouplingFailureCode.CHECKPOINT_ROLLBACK_FAILURE,
                "rollback requires a token and a reason",
            )
        snapshot = self._checkpoints.get(token)
        if snapshot is None:
            raise CouplingError(
                CouplingFailureCode.CHECKPOINT_ROLLBACK_FAILURE,
                f"unknown checkpoint:{token}",
            )
        self._values = dict(snapshot)
        for name, values in snapshot.items():
            self._backend.write_data(name, list(values))
        return self._record("rollback", token, reason)

    def finalize(self) -> None:
        self._backend.finalize()
        self._record("finalize", "", "participant finalized")

    def events(self) -> tuple[AdapterEvent, ...]:
        return tuple(self._events)

    # -- internals -------------------------------------------------------

    def _buffer(self, name: str) -> FieldBuffer:
        buffer = self._buffers.get(name)
        if buffer is None:
            raise CouplingError(
                CouplingFailureCode.INTERFACE_MISMATCH, f"unknown field buffer:{name}"
            )
        return buffer

    def _check_and_convert(
        self, buffer: FieldBuffer, values: Sequence[float], unit: str | None
    ) -> tuple[float, ...]:
        if unit is not None and unit != buffer.unit:
            if not units_compatible(unit, buffer.unit):
                raise CouplingError(
                    CouplingFailureCode.FIELD_UNIT_MISMATCH,
                    f"{buffer.name}: {unit} incompatible with buffer {buffer.unit}",
                )
            converted = tuple(convert_value(float(value), unit, buffer.unit) for value in values)
        else:
            converted = tuple(float(value) for value in values)
        expected = (
            len(self._mesh.coordinates)
            if buffer.dimension == "scalar"
            else 3 * len(self._mesh.coordinates)
        )
        if len(converted) != expected:
            raise CouplingError(
                CouplingFailureCode.INTERFACE_MISMATCH,
                f"{buffer.name}: {len(converted)} values for {expected} components",
            )
        if any(not isfinite(value) for value in converted):
            raise CouplingError(
                CouplingFailureCode.INTERFACE_MISMATCH, f"{buffer.name}: non-finite values"
            )
        return converted

    def _record(self, kind: str, checkpoint: str, reason: str) -> AdapterEvent:
        event = AdapterEvent(len(self._events) + 1, kind, checkpoint, reason)
        self._events.append(event)
        return event


def adapter_payload(adapter: NativeFieldParticipant) -> Mapping[str, object]:
    """Small read-only summary for receipts; never contains native claims."""

    return {
        "participant": adapter._mesh_name,  # noqa: SLF001 - intentional summary
        "engine": adapter.engine,
        "events": [event.kind for event in adapter.events()],
    }
