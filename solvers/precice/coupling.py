"""Implicit field-coupling driver over the shared preCICE contract.

The engine-independent path (``analytic-transfer``) executes real nonmatching
mesh mapping, conservative/consistent transfer, implicit subiterations with
IQN/Aitken acceleration, checkpoints, rollback, and an interface residual
trace. The ``precice-native`` path opens the native participant backends and
fails closed with ``PRECICE_UNAVAILABLE`` when preCICE is absent; it never
falls back to the analytic path and never publishes a coupled result unless a
transport genuinely converged.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from math import isfinite
from typing import Any

from aeroworkbench_coupling.field import (
    FieldCoupler,
    InterfaceMesh,
    SideSpec,
    transfer_field,
)
from aeroworkbench_coupling.precice import (
    CouplingContract,
    CouplingError,
    CouplingFailureCode,
    CouplingField,
    DomainInterface,
)
from participants.errors import ParticipantError

from .backend import open_native_backend

_ACCELERATION = {"iqn-ils": "iqn", "iqn": "iqn", "aitken": "aitken", "fixed": "fixed"}


@dataclass(frozen=True, slots=True)
class MappingRecord:
    """Receipt for one mapped exchange across an interface."""

    interface: str
    field: str
    method: str
    source_participant: str
    target_participant: str
    source_mesh: str
    target_mesh: str
    source_hash: str
    target_hash: str
    relative_conservation_error: float
    tolerance: float
    accepted: bool


@dataclass(frozen=True, slots=True)
class CoupledResult:
    """Outcome of one coupled window with its evidence trail."""

    state: str
    engine: str
    accepted: bool
    iterations: int
    residual: float
    residual_trace: tuple[float, ...]
    checkpoints: int
    rollbacks: int
    conservation_errors: tuple[float, ...]
    mappings: tuple[MappingRecord, ...]
    acceleration: str
    failure_code: str | None
    detail: str

    @property
    def publishable(self) -> bool:
        return (
            self.state == "completed"
            and self.accepted
            and self.failure_code is None
        )


def _default_mapping(field: str) -> str:
    from aeroworkbench_coupling.precice import FIELD_CATALOG

    entry = FIELD_CATALOG.get(field.lower())
    return entry[1] if entry else "conservative"


def map_field(
    source: InterfaceMesh,
    source_values: Sequence[float],
    target: InterfaceMesh,
    field: str,
    method: str | None = None,
    tolerance: float = 1e-6,
    *,
    interface: str = "",
    source_participant: str = "",
    target_participant: str = "",
) -> tuple[tuple[float, ...], MappingRecord]:
    """Map one field between nonmatching meshes and return a mapping receipt."""

    resolved = method or _default_mapping(field)
    try:
        receipt = transfer_field(
            source, source_values, target, field, method=resolved, tolerance=tolerance
        )
    except ValueError as exc:
        raise CouplingError(CouplingFailureCode.MAPPING_FAILURE, str(exc)) from exc
    record = MappingRecord(
        interface,
        field,
        resolved,
        source_participant,
        target_participant,
        source.name,
        target.name,
        source.digest,
        target.digest,
        receipt.relative_conservation_error,
        tolerance,
        receipt.accepted,
    )
    return receipt.values, record


def require_participant(
    manifest_id: str,
    *,
    probe: Any | None = None,  # noqa: ANN401 - injectable capability probe
) -> Any:  # noqa: ANN401 - returns participants.receipts.CapabilityProbe
    """Fail closed with an explicit code when a native participant is absent."""

    if probe is None:
        from participants.capabilities import probe_participant

        probe = probe_participant
    result = probe(manifest_id)
    if getattr(result, "state", "unavailable") != "ready":
        raise CouplingError(
            CouplingFailureCode.PARTICIPANT_UNAVAILABLE,
            f"{manifest_id}: {getattr(result, 'detail', 'unavailable')}",
        )
    return result


def interfaces_from_solver_export(
    export: Any,  # noqa: ANN401 - aeroworkbench_mesh.SolverMeshExport (duck-typed)
    *,
    assignments: Mapping[str, tuple[str, str]],
    fields: Mapping[str, Sequence[CouplingField]],
) -> tuple[DomainInterface, ...]:
    """Turn a GEN 05 preCICE ``SolverMeshExport`` into interface declarations."""

    declared: list[DomainInterface] = []
    for name, kind, zone_a, zone_b, conformal in export.interfaces:
        pair = assignments.get(kind)
        if pair is None or len(pair) != 2 or pair[0] == pair[1]:
            raise CouplingError(
                CouplingFailureCode.INTERFACE_MISMATCH,
                f"no distinct participant assignment for interface kind:{kind}",
            )
        declared.append(
            DomainInterface(
                name,
                zone_a,
                zone_b,
                pair[0],
                pair[1],
                kind,
                bool(conformal),
                tuple(fields.get(kind, ())),
            )
        )
    if not declared:
        raise CouplingError(
            CouplingFailureCode.INTERFACE_MISMATCH, "solver export declares no interfaces"
        )
    return tuple(declared)


def require_publishable(result: CoupledResult) -> CoupledResult:
    """Raise with the explicit reason when a coupled result cannot publish."""

    if not result.publishable:
        code = result.failure_code or CouplingFailureCode.COUPLING_NONCONVERGENCE.value
        raise CouplingError(CouplingFailureCode(code), result.detail)
    return result


def _extract(produced: object, side: str) -> tuple[float, ...]:
    from collections.abc import Mapping

    if not isinstance(produced, Mapping) or len(produced) != 1:
        raise CouplingError(
            CouplingFailureCode.INTERFACE_MISMATCH,
            f"side {side} must return exactly one field",
        )
    return tuple(float(value) for value in next(iter(produced.values())))


def _field_method(interface: DomainInterface, field: str) -> str:
    for declared in interface.fields:
        if declared.name == field:
            return declared.mapping or _default_mapping(field)
    return _default_mapping(field)


def run_implicit_coupling(
    *,
    contract: CouplingContract,
    interface: DomainInterface,
    mesh_a: InterfaceMesh,
    mesh_b: InterfaceMesh,
    side_a: SideSpec,
    side_b: SideSpec,
    quantity_a_to_b: str,
    quantity_b_to_a: str,
    initial_a: Sequence[float],
    initial_b: Sequence[float],
    engine: str = "analytic-transfer",
    tolerance: float | None = None,
    max_iterations: int | None = None,
    relaxation: float = 0.9,
    acceleration: str | None = None,
) -> CoupledResult:
    """Run one coupled window, returning explicit success or failure evidence."""

    resolved_tolerance = tolerance if tolerance is not None else contract.tolerance
    resolved_max = max_iterations if max_iterations is not None else contract.max_iterations
    resolved_acceleration = acceleration or contract.acceleration
    acceleration_kernel = _ACCELERATION.get(resolved_acceleration.lower())
    if acceleration_kernel is None:
        raise CouplingError(
            CouplingFailureCode.INTERFACE_MISMATCH,
            f"unsupported acceleration:{resolved_acceleration}",
        )
    if engine not in {"analytic-transfer", "precice-native"}:
        raise CouplingError(
            CouplingFailureCode.INTERFACE_MISMATCH, f"unknown engine:{engine}"
        )
    if engine == "precice-native":
        return _run_native_window(
            contract=contract,
            interface=interface,
            tolerance=resolved_tolerance,
            max_iterations=resolved_max,
            acceleration=resolved_acceleration,
        )
    return _run_analytic_window(
        interface=interface,
        mesh_a=mesh_a,
        mesh_b=mesh_b,
        side_a=side_a,
        side_b=side_b,
        quantity_a_to_b=quantity_a_to_b,
        quantity_b_to_a=quantity_b_to_a,
        initial_a=initial_a,
        initial_b=initial_b,
        tolerance=resolved_tolerance,
        max_iterations=resolved_max,
        relaxation=relaxation,
        acceleration_kernel=acceleration_kernel,
        acceleration=resolved_acceleration,
        engine=engine,
    )


def _run_analytic_window(
    *,
    interface: DomainInterface,
    mesh_a: InterfaceMesh,
    mesh_b: InterfaceMesh,
    side_a: SideSpec,
    side_b: SideSpec,
    quantity_a_to_b: str,
    quantity_b_to_a: str,
    initial_a: Sequence[float],
    initial_b: Sequence[float],
    tolerance: float,
    max_iterations: int,
    relaxation: float,
    acceleration_kernel: str,
    acceleration: str,
    engine: str,
) -> CoupledResult:
    mappings = _mapping_records(
        interface,
        mesh_a,
        mesh_b,
        side_a,
        side_b,
        initial_a,
        initial_b,
        quantity_a_to_b,
        quantity_b_to_a,
        tolerance,
    )
    failed_mapping = next((record for record in mappings if not record.accepted), None)
    if failed_mapping is not None:
        return CoupledResult(
            "failed",
            engine,
            False,
            0,
            float(failed_mapping.relative_conservation_error),
            (),
            0,
            0,
            (),
            mappings,
            acceleration,
            CouplingFailureCode.MAPPING_FAILURE.value,
            f"mapping {failed_mapping.field} exceeded tolerance "
            f"{failed_mapping.relative_conservation_error:.3g}",
        )
    coupler = FieldCoupler(
        side_a,
        side_b,
        mesh_a,
        mesh_b,
        quantity_a_to_b,
        quantity_b_to_a,
        tolerance=tolerance,
        max_iterations=max_iterations,
        relaxation=relaxation,
        acceleration=acceleration_kernel,
        engine="analytic-transfer",
    )
    window = coupler.solve(initial_a, initial_b)
    if window.accepted:
        return CoupledResult(
            "completed",
            engine,
            True,
            window.iterations,
            window.residual,
            window.residual_trace,
            window.checkpoints,
            window.rollbacks,
            window.conservation_errors,
            mappings,
            acceleration,
            None,
            window.detail,
        )
    return CoupledResult(
        "failed",
        engine,
        False,
        window.iterations,
        window.residual,
        window.residual_trace,
        window.checkpoints,
        window.rollbacks,
        window.conservation_errors,
        mappings,
        acceleration,
        CouplingFailureCode.COUPLING_NONCONVERGENCE.value,
        window.detail,
    )


def _mapping_records(
    interface: DomainInterface,
    mesh_a: InterfaceMesh,
    mesh_b: InterfaceMesh,
    side_a: SideSpec,
    side_b: SideSpec,
    initial_a: Sequence[float],
    initial_b: Sequence[float],
    quantity_a_to_b: str,
    quantity_b_to_a: str,
    tolerance: float,
) -> tuple[MappingRecord, ...]:
    state_a = tuple(float(value) for value in initial_a)
    state_b = tuple(float(value) for value in initial_b)
    out_a = _extract(side_a.compute(state_a), side_a.name)
    out_b = _extract(side_b.compute(state_b), side_b.name)
    _, record_ab = map_field(
        mesh_a,
        out_a,
        mesh_b,
        quantity_a_to_b,
        method=_field_method(interface, quantity_a_to_b),
        tolerance=tolerance,
        interface=interface.name,
        source_participant=side_a.name,
        target_participant=side_b.name,
    )
    _, record_ba = map_field(
        mesh_b,
        out_b,
        mesh_a,
        quantity_b_to_a,
        method=_field_method(interface, quantity_b_to_a),
        tolerance=tolerance,
        interface=interface.name,
        source_participant=side_b.name,
        target_participant=side_a.name,
    )
    return (record_ab, record_ba)


def _run_native_window(
    *,
    contract: CouplingContract,
    interface: DomainInterface,
    tolerance: float,
    max_iterations: int,
    acceleration: str,
) -> CoupledResult:
    """Open native backends; gated here because preCICE is not installed."""

    _ = (tolerance, max_iterations, acceleration)
    try:
        open_native_backend(
            participant=interface.participant_a,
            config_file="precice-config.xml",
        )
        open_native_backend(
            participant=interface.participant_b,
            config_file="precice-config.xml",
        )
    except ParticipantError as exc:
        return CoupledResult(
            "failed",
            "precice-native",
            False,
            0,
            float("inf"),
            (),
            0,
            0,
            (),
            (),
            acceleration,
            CouplingFailureCode.PRECICE_UNAVAILABLE.value,
            exc.detail,
        )
    raise CouplingError(
        CouplingFailureCode.PRECICE_UNAVAILABLE,
        "native preCICE opened but the generated-mesh time-window driver "
        "requires solver-provided boundary operators; no analytic substitution",
    )


def interface_is_finite(values: Sequence[float]) -> bool:
    return all(isfinite(value) for value in values)
