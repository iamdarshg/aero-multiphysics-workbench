"""Native preCICE participant backend and capability probe.

The workbench owns the overall run state; preCICE owns field exchange and
subiterations. This module is the only place that touches the native
``precice`` Python library. When it (or the native executable) is absent, the
backend fails closed with ``CAPABILITY_UNAVAILABLE``; no analytical transfer is
ever substituted for a requested native coupling.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from participants.errors import NativeErrorCode, ParticipantError

_PRECICE_LIBRARY = "precice"

_RUN_SCRIPTS = (
    Path(__file__).resolve().parent.parent / "participants" / "run_scripts"
)


def run_script_source(name: str) -> str:
    """Read one allowlisted governed run script into the case directory."""

    path = _RUN_SCRIPTS / name
    if not path.is_file():
        raise ParticipantError(
            NativeErrorCode.PREPARATION_FAILED, f"run script missing:{name}"
        )
    return path.read_text(encoding="utf-8")


@dataclass(frozen=True, slots=True)
class PrecicePythonCapability:
    state: str  # "ready" | "unavailable"
    detail: str


def probe_precice_python() -> PrecicePythonCapability:
    """Probe the participant library without importing the heavy module."""

    from importlib import metadata

    try:
        version = metadata.version(_PRECICE_LIBRARY)
    except metadata.PackageNotFoundError:
        return PrecicePythonCapability(
            "unavailable", "precice participant library is not installed"
        )
    except Exception as exc:  # noqa: BLE001
        return PrecicePythonCapability("unavailable", f"precice metadata unreadable:{exc}")
    return PrecicePythonCapability("ready", f"precice {version} installed")


@runtime_checkable
class PreciceBackend(Protocol):
    """Structural interface the native adapter drives.

    The real implementation wraps ``precice.Participant``. Tests inject a
    scripted double, which is always labelled ``simulated-precice`` and never
    presented as native field exchange.
    """

    def initialize(self) -> None: ...

    def set_mesh_vertices(
        self, mesh_name: str, coordinates: tuple[float, ...]
    ) -> tuple[int, ...]: ...

    def write_data(self, name: str, values: list[float]) -> None: ...

    def read_data(self, name: str) -> list[float]: ...

    def requires_writing_checkpoint(self) -> bool: ...

    def requires_reading_checkpoint(self) -> bool: ...

    def advance(self, dt: float) -> None: ...

    def is_coupling_ongoing(self) -> bool: ...

    def finalize(self) -> None: ...


class NativePreciceBackend:
    """Version-tolerant wrapper over ``precice.Participant``."""

    def __init__(self, participant: Any) -> None:  # noqa: ANN401 - native handle
        self._participant = participant
        self._mesh_vertices: dict[str, tuple[int, ...]] = {}

    def initialize(self) -> None:
        self._participant.initialize()

    def set_mesh_vertices(
        self, mesh_name: str, coordinates: tuple[float, ...]
    ) -> tuple[int, ...]:
        mesh = self._lookup("get_mesh", mesh_name)
        ids = tuple(int(value) for value in mesh.get_vertex_ids())
        mesh.set_vertices(ids, list(coordinates))
        self._mesh_vertices[mesh_name] = ids
        return ids

    def write_data(self, name: str, values: list[float]) -> None:
        self._participant.write_data(name, values)

    def read_data(self, name: str) -> list[float]:
        return [float(value) for value in self._participant.read_data(name)]

    def requires_writing_checkpoint(self) -> bool:
        return bool(self._participant.requires_writing_checkpoint())

    def requires_reading_checkpoint(self) -> bool:
        return bool(self._participant.requires_reading_checkpoint())

    def advance(self, dt: float) -> None:
        self._participant.advance(dt)

    def is_coupling_ongoing(self) -> bool:
        return bool(self._participant.is_coupling_ongoing())

    def finalize(self) -> None:
        self._participant.finalize()

    def _lookup(self, attribute: str, mesh_name: str) -> Any:  # noqa: ANN401 - native body
        getter = getattr(self._participant, attribute, None)
        if getter is None:
            raise ParticipantError(
                NativeErrorCode.CAPABILITY_UNAVAILABLE,
                f"native preCICE participant lacks {attribute}",
            )
        return getter(mesh_name)


def open_native_backend(
    *,
    participant: str,
    config_file: str | Path,
    rank: int = 0,
    size: int = 1,
    dimensions: int = 3,
) -> NativePreciceBackend:
    """Open a native preCICE participant or fail closed with a stable code."""

    capability = probe_precice_python()
    if capability.state != "ready":
        raise ParticipantError(
            NativeErrorCode.CAPABILITY_UNAVAILABLE,
            "precice-native engine requested but "
            f"{capability.detail}; no analytical transfer is substituted",
        )
    try:
        import precice  # type: ignore[import-not-found]  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover - probe already gated
        raise ParticipantError(
            NativeErrorCode.CAPABILITY_UNAVAILABLE,
            f"precice import failed:{exc}",
        ) from exc
    participant_ctor = getattr(precice, "Participant", None)
    if participant_ctor is None:  # pragma: no cover - version drift
        raise ParticipantError(
            NativeErrorCode.CAPABILITY_UNAVAILABLE,
            "installed precice module exposes no Participant constructor",
        )
    _ = (rank, size, dimensions)
    handle = participant_ctor(participant, str(config_file), rank, size)
    return NativePreciceBackend(handle)
