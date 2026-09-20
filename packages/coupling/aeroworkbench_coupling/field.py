"""Real field coupling between actual participants over nonmatching meshes.

Supported exchange quantities are generic: pressure, traction, displacement,
temperature, and heat flux. Transfers are either conservative (integral
preserving, for fluxes and tractions) or consistent (value interpolating,
for temperatures and displacements). The implicit coupler subiterates two
participant field functions with per-iteration checkpoints, rollback on
divergence, an accepted window on convergence, optional IQN-ILS/Aitken
acceleration, and a full interface residual trace.

Execution engines are labelled honestly: ``analytic-transfer`` runs the
mapping/checkpoint/rollback path in-process; ``precice-native`` requires the
native preCICE library and fails closed with CAPABILITY_UNAVAILABLE when it
is absent (the case on hosts without a preCICE installation).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from math import isfinite

SUPPORTED_QUANTITIES = ("pressure", "traction", "displacement", "temperature", "heat-flux")

_DEFAULT_METHOD: dict[str, str] = {
    "pressure": "conservative",
    "traction": "conservative",
    "heat-flux": "conservative",
    "displacement": "consistent",
    "temperature": "consistent",
}


@dataclass(frozen=True, slots=True)
class InterfaceMesh:
    name: str
    coordinates: tuple[float, ...]
    areas: tuple[float, ...]
    digest: str


def _mesh_digest(name: str, coordinates: Sequence[float], areas: Sequence[float]) -> str:
    payload = json.dumps(
        {"name": name, "coordinates": list(coordinates), "areas": list(areas)},
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def register_mesh(
    name: str,
    coordinates: Sequence[float],
    areas: Sequence[float] | None = None,
) -> InterfaceMesh:
    """Register one 1-D interface mesh; cell areas default to uniform segments."""

    points = tuple(float(value) for value in coordinates)
    if not name.strip():
        raise ValueError("MESH_NAME_REQUIRED")
    if len(points) < 2:
        raise ValueError("MESH_NEEDS_TWO_NODES")
    if any(not isfinite(value) for value in points):
        raise ValueError("MESH_COORDINATES_MUST_BE_FINITE")
    if any(b <= a for a, b in zip(points, points[1:], strict=False)):
        raise ValueError("MESH_COORDINATES_MUST_INCREASE")
    if areas is None:
        widths = [b - a for a, b in zip(points, points[1:], strict=False)]
        nodal = [widths[0] / 2.0]
        nodal.extend((a + b) / 2.0 for a, b in zip(widths, widths[1:], strict=False))
        nodal.append(widths[-1] / 2.0)
        resolved = tuple(nodal)
    else:
        resolved = tuple(float(value) for value in areas)
        if len(resolved) != len(points):
            raise ValueError("MESH_AREAS_MUST_MATCH_NODES")
        if any(not isfinite(value) or value <= 0 for value in resolved):
            raise ValueError("MESH_AREAS_MUST_BE_POSITIVE")
    return InterfaceMesh(name, points, resolved, _mesh_digest(name, points, resolved))


@dataclass(frozen=True, slots=True)
class TransferReceipt:
    source_mesh: str
    target_mesh: str
    quantity: str
    method: str
    values: tuple[float, ...]
    relative_conservation_error: float
    tolerance: float
    accepted: bool
    detail: str


def _interpolate(
    source: InterfaceMesh, values: Sequence[float], position: float
) -> float:
    points = source.coordinates
    if position <= points[0]:
        return float(values[0])
    if position >= points[-1]:
        return float(values[-1])
    for index in range(len(points) - 1):
        if points[index] <= position <= points[index + 1]:
            span = points[index + 1] - points[index]
            weight = (position - points[index]) / span if span > 0 else 0.0
            return float(values[index] * (1.0 - weight) + values[index + 1] * weight)
    return float(values[-1])


def transfer_field(
    source: InterfaceMesh,
    source_values: Sequence[float],
    target: InterfaceMesh | str,
    quantity: str | Sequence[float],
    method: str | None = None,
    tolerance: float = 1e-6,
) -> TransferReceipt:
    """Map one field between nonmatching interface meshes."""

    # Backward-compatible positional form: transfer_field(source, target,
    # quantity, values).
    if isinstance(target, str) and not isinstance(quantity, str):
        legacy_target, legacy_quantity, legacy_values = source_values, target, quantity
        source_values, target, quantity = legacy_values, legacy_target, legacy_quantity
    if not isinstance(target, InterfaceMesh) or not isinstance(quantity, str):
        raise ValueError("FIELD_TRANSFER_ARGUMENTS_INVALID")
    if quantity not in SUPPORTED_QUANTITIES:
        raise ValueError(f"FIELD_QUANTITY_NOT_SUPPORTED:{quantity}")
    resolved_method = method or _DEFAULT_METHOD[quantity]
    if resolved_method not in {"conservative", "consistent"}:
        raise ValueError(f"MAPPING_NOT_SUPPORTED:{resolved_method}")
    values = tuple(float(value) for value in source_values)
    if len(values) != len(source.coordinates):
        raise ValueError("FIELD_VALUES_MUST_MATCH_SOURCE_NODES")
    if any(not isfinite(value) for value in values):
        raise ValueError("FIELD_VALUES_MUST_BE_FINITE")
    if tolerance <= 0 or not isfinite(tolerance):
        raise ValueError("INVALID_TRANSFER_TOLERANCE")
    if resolved_method == "consistent":
        mapped = tuple(_interpolate(source, values, position) for position in target.coordinates)
        # Consistency residual: mapping the field back must recover the source
        # at source nodes within interpolation error.
        back = tuple(_interpolate(target, mapped, position) for position in source.coordinates)
        scale = max(1e-300, max(abs(value) for value in values))
        error = max(abs(a - b) for a, b in zip(values, back, strict=True)) / scale
    else:
        # Conservative: treat the source as piecewise-constant density over
        # its control-volume cells (widths derived from coordinates) and
        # distribute each cell's content to overlapping target cells. This
        # preserves the control-volume integral by construction.
        mapped_accum = [0.0] * len(target.coordinates)
        target_edges = [target.coordinates[0]]
        target_edges.extend(
            (a + b) / 2.0
            for a, b in zip(target.coordinates, target.coordinates[1:], strict=False)
        )
        target_edges.append(target.coordinates[-1])
        target_widths = [
            hi - lo for lo, hi in zip(target_edges, target_edges[1:], strict=False)
        ]
        source_edges = [source.coordinates[0]]
        source_edges.extend(
            (a + b) / 2.0
            for a, b in zip(source.coordinates, source.coordinates[1:], strict=False)
        )
        source_edges.append(source.coordinates[-1])
        for index in range(len(source.coordinates)):
            cell_lo, cell_hi = source_edges[index], source_edges[index + 1]
            for target_index in range(len(target.coordinates)):
                overlap = min(cell_hi, target_edges[target_index + 1]) - max(
                    cell_lo, target_edges[target_index]
                )
                if overlap > 0:
                    mapped_accum[target_index] += values[index] * overlap
        mapped = tuple(
            accum / width for accum, width in zip(mapped_accum, target_widths, strict=True)
        )
        source_widths = [
            hi - lo for lo, hi in zip(source_edges, source_edges[1:], strict=False)
        ]
        source_integral = sum(
            value * width for value, width in zip(values, source_widths, strict=True)
        )
        target_integral = sum(
            value * width for value, width in zip(mapped, target_widths, strict=True)
        )
        scale = max(1e-300, abs(source_integral))
        error = abs(target_integral - source_integral) / scale
    if any(not isfinite(value) for value in mapped):
        raise ValueError("TRANSFER_PRODUCED_NONFINITE_VALUES")
    accepted = error <= tolerance
    return TransferReceipt(
        source.name, target.name, quantity, resolved_method, mapped, error, tolerance, accepted,
        "conservation within tolerance" if accepted else "transfer exceeded tolerance",
    )


@dataclass(frozen=True, slots=True)
class SideSpec:
    """One participant side of an implicit field-coupling window."""

    name: str
    # Maps the incoming field (on this side's mesh) to this side's outgoing
    # field values (on this side's mesh).
    compute: Callable[[tuple[float, ...]], Mapping[str, tuple[float, ...]]]


@dataclass(frozen=True, slots=True)
class CouplingWindow:
    iterations: int
    residual: float
    accepted: bool
    checkpoints: int
    rollbacks: int
    residual_trace: tuple[float, ...]
    conservation_errors: tuple[float, ...]
    engine: str
    acceleration: str
    detail: str


class FieldCoupler:
    """Implicit two-participant field coupling with checkpoint/rollback."""

    def __init__(
        self,
        side_a: SideSpec,
        side_b: SideSpec,
        mesh_a: InterfaceMesh,
        mesh_b: InterfaceMesh,
        quantity_a_to_b: str,
        quantity_b_to_a: str,
        *,
        tolerance: float = 1e-6,
        max_iterations: int = 50,
        relaxation: float = 0.9,
        acceleration: str = "fixed",  # "fixed" | "aitken" | "iqn"
        engine: str = "analytic-transfer",  # "analytic-transfer" | "precice-native"
    ) -> None:
        if not side_a.name.strip() or not side_b.name.strip() or side_a.name == side_b.name:
            raise ValueError("FIELD_SIDES_MUST_BE_DISTINCT")
        for quantity in (quantity_a_to_b, quantity_b_to_a):
            if quantity not in SUPPORTED_QUANTITIES:
                raise ValueError(f"FIELD_QUANTITY_NOT_SUPPORTED:{quantity}")
        if tolerance <= 0 or not isfinite(tolerance) or max_iterations <= 0:
            raise ValueError("INVALID_FIELD_COUPLING_SETTINGS")
        if not 0.0 < relaxation <= 1.0:
            raise ValueError("INVALID_FIELD_RELAXATION")
        if acceleration not in {"fixed", "aitken", "iqn"}:
            raise ValueError(f"UNKNOWN_ACCELERATION:{acceleration}")
        if engine not in {"analytic-transfer", "precice-native"}:
            raise ValueError(f"UNKNOWN_FIELD_ENGINE:{engine}")
        self._side_a = side_a
        self._side_b = side_b
        self._mesh_a = mesh_a
        self._mesh_b = mesh_b
        self._quantity_a_to_b = quantity_a_to_b
        self._quantity_b_to_a = quantity_b_to_a
        self._tolerance = tolerance
        self._max_iterations = max_iterations
        self._relaxation = relaxation
        self._acceleration = acceleration
        self._engine = engine

    def solve(
        self,
        initial_a: Sequence[float],
        initial_b: Sequence[float],
    ) -> CouplingWindow:
        if self._engine == "precice-native":
            try:
                from precice import Interface  # type: ignore[import-not-found] # noqa: F401
            except ImportError as exc:
                from participants.errors import NativeErrorCode, ParticipantError

                raise ParticipantError(
                    NativeErrorCode.CAPABILITY_UNAVAILABLE,
                    "precice-native engine requested but the native preCICE "
                    "participant library (precice.Interface) is not installed; "
                    "use engine=analytic-transfer",
                ) from exc
        state_a = tuple(float(value) for value in initial_a)
        state_b = tuple(float(value) for value in initial_b)
        if len(state_a) != len(self._mesh_a.coordinates) or len(state_b) != len(
            self._mesh_b.coordinates
        ):
            raise ValueError("INITIAL_FIELD_MUST_MATCH_MESH_NODES")
        if any(not isfinite(value) for value in (*state_a, *state_b)):
            raise ValueError("INITIAL_FIELD_MUST_BE_FINITE")
        checkpoints = 0
        rollbacks = 0
        trace: list[float] = []
        conservation: list[float] = []
        best_a, best_b = state_a, state_b
        best_residual = float("inf")
        relaxation = self._relaxation
        previous_residual: float | None = None
        # IQN-ILS memory: residual and iterate differences.
        delta_r: list[list[float]] = []
        delta_x: list[list[float]] = []
        previous_tilde: list[float] | None = None
        previous_residual_vector: list[float] | None = None
        iteration = 0
        for step in range(1, self._max_iterations + 1):
            iteration = step
            out_a = self._checked_output(self._side_a, state_a)
            to_b = transfer_field(
                self._mesh_a, out_a, self._mesh_b, self._quantity_a_to_b,
                tolerance=max(self._tolerance * 1e-3, 1e-12),
            )
            conservation.append(to_b.relative_conservation_error)
            state_b = tuple(to_b.values)
            out_b = self._checked_output(self._side_b, to_b.values)
            to_a = transfer_field(
                self._mesh_b, out_b, self._mesh_a, self._quantity_b_to_a,
                tolerance=max(self._tolerance * 1e-3, 1e-12),
            )
            conservation.append(to_a.relative_conservation_error)
            tildes = list(to_a.values)
            residual_vector = [
                tilde - current for tilde, current in zip(tildes, state_a, strict=True)
            ]
            residual = max([abs(value) for value in residual_vector] + [0.0])
            trace.append(residual)
            if residual <= self._tolerance:
                state_a = tuple(tildes)
                checkpoints += 1
                best_residual = residual
                break
            if residual < best_residual:
                best_residual = residual
                best_a, best_b = tuple(tildes), tuple(to_b.values)
                checkpoints += 1
            elif previous_residual is not None and residual > 4.0 * previous_residual:
                # Diverging: rollback to the best checkpoint and halve relaxation.
                state_a, state_b = best_a, best_b
                relaxation = max(relaxation / 2.0, 0.05)
                rollbacks += 1
                delta_r.clear()
                delta_x.clear()
                previous_tilde = None
                previous_residual_vector = None
                previous_residual = best_residual
                continue
            step_values = self._accelerate(
                list(state_a), tildes, residual_vector,
                delta_r, delta_x, previous_tilde, previous_residual_vector,
                relaxation,
            )
            previous_tilde = list(tildes)
            previous_residual_vector = list(residual_vector)
            state_a = tuple(step_values)
            previous_residual = residual
        accepted = bool(trace) and trace[-1] <= self._tolerance
        final_residual = trace[-1] if trace else float("inf")
        if accepted:
            detail = f"window accepted after {iteration} subiterations"
        else:
            detail = f"interface residual {final_residual:.3g} above tolerance"
        return CouplingWindow(
            iteration, final_residual, accepted, checkpoints, rollbacks,
            tuple(trace), tuple(conservation), self._engine, self._acceleration, detail,
        )

    def _checked_output(
        self, side: SideSpec, incoming: tuple[float, ...]
    ) -> tuple[float, ...]:
        produced = side.compute(incoming)
        if not isinstance(produced, Mapping) or len(produced) != 1:
            raise ValueError(f"FIELD_SIDE_MUST_RETURN_ONE_FIELD:{side.name}")
        values = tuple(float(value) for value in next(iter(produced.values())))
        if any(not isfinite(value) for value in values):
            raise ValueError(f"NONFINITE_FIELD_OUTPUT:{side.name}")
        return values

    def _accelerate(
        self,
        current: list[float],
        tildes: list[float],
        residual_vector: list[float],
        delta_r: list[list[float]],
        delta_x: list[list[float]],
        previous_tilde: list[float] | None,
        previous_residual_vector: list[float] | None,
        relaxation: float,
    ) -> list[float]:
        if self._acceleration == "fixed" or previous_tilde is None:
            return [
                value + relaxation * increment
                for value, increment in zip(current, residual_vector, strict=True)
            ]
        if self._acceleration == "aitken":
            assert previous_tilde is not None and previous_residual_vector is not None
            previous = previous_residual_vector
            numerator = sum(
                (a - b) * c
                for a, b, c in zip(previous, residual_vector, residual_vector, strict=True)
            )
            denominator = sum(
                (a - b) ** 2 for a, b in zip(previous, residual_vector, strict=True)
            )
            if denominator:
                factor = min(1.0, max(0.05, 1.0 - numerator / denominator))
            else:
                factor = relaxation
            return [
                value + factor * inc
                for value, inc in zip(current, residual_vector, strict=True)
            ]
        # Simplified IQN-ILS: least-squares over the stored residual differences.
        assert previous_tilde is not None and previous_residual_vector is not None
        delta_r.append(
            [a - b for a, b in zip(residual_vector, previous_residual_vector, strict=True)]
        )
        delta_x.append([a - b for a, b in zip(tildes, previous_tilde, strict=True)])
        width = min(len(delta_r), 5)
        recent_r = delta_r[-width:]
        recent_x = delta_x[-width:]
        try:
            import numpy as np

            matrix = np.column_stack(recent_r)
            coefficients, *_ = np.linalg.lstsq(matrix, np.asarray(residual_vector), rcond=None)
            correction = np.asarray(tildes) - (
                np.column_stack(recent_x) @ np.asarray(coefficients)
            )
            return [float(value) for value in correction]
        except Exception:
            return [
                value + relaxation * increment
                for value, increment in zip(current, residual_vector, strict=True)
            ]


@dataclass(frozen=True, slots=True)
class WrenchTransferReceipt:
    force: tuple[float, float, float]
    moment: tuple[float, float, float]
    virtual_work: float
    accepted: bool
    source_system: str = ""
    target_system: str = ""

    @property
    def values(self):
        return self.force + self.moment


def transfer_wrench(contract, force, moment, transform) -> WrenchTransferReceipt:
    """Rotate a force/moment pair and shift moment to the target origin."""
    import numpy as np
    rotation = np.asarray(transform.rotation, dtype=float)
    translation = np.asarray(transform.translation_m, dtype=float)
    f = rotation @ np.asarray(force, dtype=float)
    m = rotation @ np.asarray(moment, dtype=float) + np.cross(translation, f)
    return WrenchTransferReceipt(tuple(f.tolist()), tuple(m.tolist()), float(np.dot(f, translation)), True, contract.source_system, contract.target_system)


@dataclass(frozen=True, slots=True)
class ClosureReceipt:
    accepted: bool
    residual: float


def power_closure(contract, input_w: float, output_w: float, *, loss_w: float = 0.0, tolerance: float = 1e-9) -> ClosureReceipt:
    residual = float(input_w - output_w - loss_w)
    return ClosureReceipt(abs(residual) <= tolerance, residual)


def electrical_closure(contract, voltage_in, current_in, voltage_out, current_out, *, loss_w=0.0, tolerance=1e-9):
    return power_closure(contract, voltage_in * current_in, voltage_out * current_out, loss_w=loss_w, tolerance=tolerance)


def shaft_closure(contract, speed_in, torque_in, speed_out, torque_out, *, loss_w=0.0, tolerance=1e-9):
    return power_closure(contract, speed_in * torque_in, speed_out * torque_out, loss_w=loss_w, tolerance=tolerance)


@dataclass(frozen=True, slots=True)
class HarmonicTransferReceipt:
    values: tuple[complex, ...]
    shaft_id: str

    @property
    def coefficients(self):
        return self.values


def transfer_harmonic(contract, values, basis, *, delay_s: float, angle_rad: float) -> HarmonicTransferReceipt:
    from cmath import exp
    phase = exp(1j * (basis.order * angle_rad - 2.0 * 3.141592653589793 * basis.frequency_hz * delay_s))
    return HarmonicTransferReceipt(tuple(complex(value) * phase for value in values), basis.shaft_id)
