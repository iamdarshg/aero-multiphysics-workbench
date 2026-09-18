"""Generic electrical-machine participant: analytical, map, and native levels.

Level 1 (analytical) solves the lumped voltage/back-EMF/resistance/torque
balance in closed form. Level 2 (reduced) interpolates an immutable
current/loss/efficiency map inside its declared validity envelope. Level 3
(native) is the declared Elmer electromagnetic seam and fails closed whenever
the native engine (or its case execution) is unavailable -- analytical or map
results are never relabelled native.
"""

from __future__ import annotations

import math
import shutil
from dataclasses import dataclass, field
from typing import Any

from aeroworkbench_materials import MaterialDatabase

from .parameters import UNITS, MachineParameters
from .validity import FidelityLevel, OutOfEnvelopePolicy, Validity

_NATIVE_EM_IMPLEMENTATION = "declared-elmer-electromagnetic-interface"


class ElectricalModelError(ValueError):
    """A typed, fail-closed electrical-model contract violation."""

    code = "PREPARATION_FAILED"

    def __init__(self, detail: str) -> None:
        super().__init__(detail)


class ElectricalCapabilityUnavailable(RuntimeError):
    """A requested level needs a native engine that is not available."""

    code = "CAPABILITY_UNAVAILABLE"

    def __init__(self, detail: str) -> None:
        super().__init__(detail)


@dataclass(frozen=True, slots=True)
class NativeEmStatus:
    """Actual status of the native electromagnetic seam (never optimistic)."""

    state: str  # "unavailable" | "engine-present-not-wired"
    executable: str | None
    implementation: str
    detail: str


def native_em_status(executable: str = "ElmerSolver") -> NativeEmStatus:
    """Report whether a real native EM engine is present and wired."""

    resolved = shutil.which(executable)
    if resolved is None:
        return NativeEmStatus(
            "unavailable",
            None,
            _NATIVE_EM_IMPLEMENTATION,
            f"{executable} is not installed; native EM level fails closed",
        )
    return NativeEmStatus(
        "engine-present-not-wired",
        resolved,
        _NATIVE_EM_IMPLEMENTATION,
        "ElmerSolver present but only the interface is wired; no rotating-machine EM case",
    )


def native_em_benchmark_inputs() -> dict[str, object]:
    """Bounded generic magnetostatic benchmark definition for the native seam."""

    return {
        "model": "magnetostatic-2d-rectangle",
        "width_mm": 40.0,
        "height_mm": 20.0,
        "permeability": 1.05,
        "applied_mmf_a": 500.0,
        "element_size_mm": 2.0,
    }


@dataclass(frozen=True, slots=True)
class MachineResult:
    """Typed operating point returned by any executing machine level."""

    fidelity: str
    source: str
    speed_rpm: float
    torque_n_m: float
    current_a: float
    electrical_power_w: float
    mechanical_power_w: float
    copper_loss_w: float
    core_loss_w: float
    friction_loss_w: float
    total_loss_w: float
    efficiency: float
    winding_temp_k: float
    magnet_temp_k: float
    heat_load_winding_w: float
    heat_load_core_w: float
    heat_load_magnet_w: float
    validity: Validity
    iterations: int = 1
    detail: str = ""
    warnings: tuple[str, ...] = field(default=())

    def as_scalars(self) -> dict[str, float]:
        return {
            "speed_rpm": float(self.speed_rpm),
            "torque_n_m": float(self.torque_n_m),
            "current_a": float(self.current_a),
            "electrical_power_w": float(self.electrical_power_w),
            "mechanical_power_w": float(self.mechanical_power_w),
            "copper_loss_w": float(self.copper_loss_w),
            "core_loss_w": float(self.core_loss_w),
            "friction_loss_w": float(self.friction_loss_w),
            "total_loss_w": float(self.total_loss_w),
            "efficiency": float(self.efficiency),
            "heat_load_winding_w": float(self.heat_load_winding_w),
            "heat_load_core_w": float(self.heat_load_core_w),
            "heat_load_magnet_w": float(self.heat_load_magnet_w),
        }

    def units(self) -> dict[str, str]:
        return {name: UNITS[name] for name in self.as_scalars()}


@dataclass(frozen=True, slots=True)
class MapPoint:
    """One interpolated point of a reduced machine map."""

    speed_rpm: float
    torque_n_m: float
    current_a: float
    copper_loss_w: float
    core_loss_w: float
    total_loss_w: float
    efficiency: float
    electrical_power_w: float
    mechanical_power_w: float
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class MachineMap:
    """Immutable, validity-bounded current/loss/efficiency map revision."""

    revision: str
    source: str
    speeds_rpm: tuple[float, ...]
    torques_n_m: tuple[float, ...]
    current_a: tuple[tuple[float, ...], ...]
    copper_loss_w: tuple[tuple[float, ...], ...]
    core_loss_w: tuple[tuple[float, ...], ...]
    total_loss_w: tuple[tuple[float, ...], ...]
    efficiency: tuple[tuple[float, ...], ...]
    electrical_power_w: tuple[tuple[float, ...], ...]
    mechanical_power_w: tuple[tuple[float, ...], ...]

    def __post_init__(self) -> None:
        if not self.revision.strip() or not self.source.strip():
            raise ValueError("MAP_REVISION_AND_SOURCE_REQUIRED")
        if len(self.speeds_rpm) < 2 or len(self.torques_n_m) < 2:
            raise ValueError("MAP_NEEDS_AT_LEAST_TWO_AXIS_POINTS")
        for axis in (self.speeds_rpm, self.torques_n_m):
            if any(not low < high for low, high in zip(axis, axis[1:], strict=False)):
                raise ValueError("MAP_AXIS_MUST_BE_STRICTLY_INCREASING")
        shapes = {
            (len(self.speeds_rpm), len(self.torques_n_m))
            for table in (
                self.current_a,
                self.copper_loss_w,
                self.core_loss_w,
                self.total_loss_w,
                self.efficiency,
                self.electrical_power_w,
                self.mechanical_power_w,
            )
        }
        if shapes != {(len(self.speeds_rpm), len(self.torques_n_m))}:
            raise ValueError("MAP_TABLE_SHAPE_MISMATCH")

    @property
    def speed_envelope_rpm(self) -> tuple[float, float]:
        return (self.speeds_rpm[0], self.speeds_rpm[-1])

    @property
    def torque_envelope_n_m(self) -> tuple[float, float]:
        return (self.torques_n_m[0], self.torques_n_m[-1])

    def _locate(
        self, axis: tuple[float, ...], value: float, policy: OutOfEnvelopePolicy, label: str
    ) -> tuple[int, float, str | None]:
        low, high = axis[0], axis[-1]
        if value < low or value > high:
            if policy is OutOfEnvelopePolicy.FAIL:
                raise ElectricalModelError(
                    f"MAP_OUT_OF_ENVELOPE:{label}:{value}:range=[{low},{high}]"
                )
            clamped = min(max(value, low), high)
            index = min(len(axis) - 2, max(0, _search(axis, clamped)))
            return (
                index,
                clamped,
                f"{label} {value} clamped into validity envelope [{low},{high}]",
            )
        return _search(axis, value), value, None

    def evaluate(
        self,
        speed_rpm: float,
        torque_n_m: float,
        policy: OutOfEnvelopePolicy = OutOfEnvelopePolicy.FAIL,
    ) -> MapPoint:
        if not (
            math.isfinite(speed_rpm)
            and math.isfinite(torque_n_m)
        ):
            raise ElectricalModelError("MAP_NONFINITE_REQUEST")
        i_speed, speed, warn_speed = self._locate(
            self.speeds_rpm, speed_rpm, policy, "speed_rpm"
        )
        i_torque, torque, warn_torque = self._locate(
            self.torques_n_m, torque_n_m, policy, "torque_n_m"
        )
        s0, s1 = self.speeds_rpm[i_speed], self.speeds_rpm[i_speed + 1]
        t0, t1 = self.torques_n_m[i_torque], self.torques_n_m[i_torque + 1]
        fs = 0.0 if s1 == s0 else (speed - s0) / (s1 - s0)
        ft = 0.0 if t1 == t0 else (torque - t0) / (t1 - t0)

        def bilinear(table: tuple[tuple[float, ...], ...]) -> float:
            return (
                table[i_speed][i_torque] * (1 - fs) * (1 - ft)
                + table[i_speed + 1][i_torque] * fs * (1 - ft)
                + table[i_speed][i_torque + 1] * (1 - fs) * ft
                + table[i_speed + 1][i_torque + 1] * fs * ft
            )

        warnings = tuple(w for w in (warn_speed, warn_torque) if w is not None)
        return MapPoint(
            speed_rpm=speed,
            torque_n_m=torque,
            current_a=bilinear(self.current_a),
            copper_loss_w=bilinear(self.copper_loss_w),
            core_loss_w=bilinear(self.core_loss_w),
            total_loss_w=bilinear(self.total_loss_w),
            efficiency=bilinear(self.efficiency),
            electrical_power_w=bilinear(self.electrical_power_w),
            mechanical_power_w=bilinear(self.mechanical_power_w),
            warnings=warnings,
        )

    def as_payload(self) -> dict[str, Any]:
        return {
            "revision": self.revision,
            "source": self.source,
            "speedsRpm": list(self.speeds_rpm),
            "torquesNm": list(self.torques_n_m),
        }


def _search(axis: tuple[float, ...], value: float) -> int:
    """Return the lower bracketing index for a value inside the axis."""

    for index in range(len(axis) - 1):
        if axis[index] <= value <= axis[index + 1]:
            return index
    return len(axis) - 2


def build_analytical_map(
    parameters: MachineParameters,
    *,
    speeds_rpm: tuple[float, ...],
    torques_n_m: tuple[float, ...],
    revision: str = "screening-map-r1",
    database: MaterialDatabase | None = None,
) -> MachineMap:
    """Derive a screening current/loss/efficiency map from the analytical model.

    The map is a declared parameter revision, not solver output: its source
    records that it was reduced from the analytical lumped model at the
    reference temperature.
    """

    reference_temp = parameters.reference_temperature_k
    resistance = parameters.winding_resistance_at(reference_temp, database)
    kt = parameters.torque_constant_at(reference_temp)
    current_rows: list[tuple[float, ...]] = []
    copper_rows: list[tuple[float, ...]] = []
    core_rows: list[tuple[float, ...]] = []
    total_rows: list[tuple[float, ...]] = []
    efficiency_rows: list[tuple[float, ...]] = []
    electrical_rows: list[tuple[float, ...]] = []
    mechanical_rows: list[tuple[float, ...]] = []
    for speed in speeds_rpm:
        omega = speed * math.pi / 30.0
        core_power = parameters.core_loss_w_at(speed, database)
        current_row: list[float] = []
        copper_row: list[float] = []
        core_row: list[float] = []
        total_row: list[float] = []
        efficiency_row: list[float] = []
        electrical_row: list[float] = []
        mechanical_row: list[float] = []
        friction_power = parameters.friction_torque_n_m * omega
        for torque in torques_n_m:
            core_torque = core_power / omega if omega > 1e-9 else 0.0
            electromagnetic = torque + core_torque + parameters.friction_torque_n_m
            current = electromagnetic / kt
            copper = current * current * resistance
            mechanical = torque * omega
            total = copper + core_power + friction_power
            electrical = mechanical + total
            current_row.append(current)
            copper_row.append(copper)
            core_row.append(core_power)
            total_row.append(total)
            efficiency_row.append(mechanical / electrical if electrical > 0 else 0.0)
            electrical_row.append(electrical)
            mechanical_row.append(mechanical)
        current_rows.append(tuple(current_row))
        copper_rows.append(tuple(copper_row))
        core_rows.append(tuple(core_row))
        total_rows.append(tuple(total_row))
        efficiency_rows.append(tuple(efficiency_row))
        electrical_rows.append(tuple(electrical_row))
        mechanical_rows.append(tuple(mechanical_row))
    return MachineMap(
        revision=revision,
        source="reduced-from-analytical-lumped-model-at-reference-temperature",
        speeds_rpm=tuple(speeds_rpm),
        torques_n_m=tuple(torques_n_m),
        current_a=tuple(current_rows),
        copper_loss_w=tuple(copper_rows),
        core_loss_w=tuple(core_rows),
        total_loss_w=tuple(total_rows),
        efficiency=tuple(efficiency_rows),
        electrical_power_w=tuple(electrical_rows),
        mechanical_power_w=tuple(mechanical_rows),
    )


def _require_finite(value: float, label: str) -> float:
    if not math.isfinite(value):
        raise ElectricalModelError(f"MACHINE_NONFINITE_INPUT:{label}")
    return value


def solve_machine(
    parameters: MachineParameters,
    *,
    bus_voltage_v: float,
    speed_rpm: float,
    winding_temp_k: float,
    magnet_temp_k: float,
    load_torque_n_m: float | None = None,
    fidelity: str = FidelityLevel.ANALYTICAL,
    machine_map: MachineMap | None = None,
    out_of_envelope_policy: OutOfEnvelopePolicy = OutOfEnvelopePolicy.FAIL,
    database: MaterialDatabase | None = None,
    tolerance: float = 1e-9,
) -> MachineResult:
    """Dispatch one generic machine operating point through the fidelity ladder."""

    level = FidelityLevel(fidelity)
    for label, value in (
        ("bus_voltage_v", bus_voltage_v),
        ("speed_rpm", speed_rpm),
        ("winding_temp_k", winding_temp_k),
        ("magnet_temp_k", magnet_temp_k),
    ):
        _require_finite(value, label)
    if not parameters.min_speed_rpm <= speed_rpm <= parameters.max_speed_rpm:
        raise ElectricalModelError(
            f"MACHINE_SPEED_OUT_OF_VALIDITY:{speed_rpm}:"
            f"[{parameters.min_speed_rpm},{parameters.max_speed_rpm}]"
        )
    if not (
        parameters.min_winding_temp_k
        <= winding_temp_k
        <= parameters.max_winding_temp_k
    ):
        raise ElectricalModelError(f"MACHINE_WINDING_TEMP_OUT_OF_VALIDITY:{winding_temp_k}")
    if not (
        parameters.min_magnet_temp_k
        <= magnet_temp_k
        <= parameters.max_magnet_temp_k
    ):
        raise ElectricalModelError(f"MACHINE_MAGNET_TEMP_OUT_OF_VALIDITY:{magnet_temp_k}")

    if level is FidelityLevel.ANALYTICAL:
        return _solve_analytical(
            parameters,
            bus_voltage_v=bus_voltage_v,
            speed_rpm=speed_rpm,
            winding_temp_k=winding_temp_k,
            magnet_temp_k=magnet_temp_k,
            database=database,
            tolerance=tolerance,
        )
    if level is FidelityLevel.REDUCED:
        if machine_map is None:
            raise ElectricalModelError("MACHINE_REDUCED_LEVEL_REQUIRES_A_MAP")
        if load_torque_n_m is None:
            raise ElectricalModelError("MACHINE_REDUCED_LEVEL_REQUIRES_COMMANDED_TORQUE")
        return _solve_reduced(
            parameters,
            machine_map,
            speed_rpm=speed_rpm,
            load_torque_n_m=load_torque_n_m,
            winding_temp_k=winding_temp_k,
            magnet_temp_k=magnet_temp_k,
            out_of_envelope_policy=out_of_envelope_policy,
        )
    raise ElectricalCapabilityUnavailable(native_em_status().detail)


def _solve_analytical(
    parameters: MachineParameters,
    *,
    bus_voltage_v: float,
    speed_rpm: float,
    winding_temp_k: float,
    magnet_temp_k: float,
    database: MaterialDatabase | None,
    tolerance: float,
) -> MachineResult:
    omega = speed_rpm * math.pi / 30.0
    resistance = parameters.winding_resistance_at(winding_temp_k, database)
    kt = parameters.torque_constant_at(magnet_temp_k)
    ke = parameters.back_emf_at(magnet_temp_k)
    back_emf = ke * omega
    current = (bus_voltage_v - back_emf) / resistance
    electromagnetic = kt * current
    core_power = parameters.core_loss_w_at(speed_rpm, database)
    core_torque = core_power / omega if omega > 1e-9 else 0.0
    shaft = electromagnetic - core_torque - parameters.friction_torque_n_m
    mechanical = shaft * omega
    electrical = bus_voltage_v * current
    copper = current * current * resistance
    friction_power = parameters.friction_torque_n_m * omega
    total_loss = copper + core_power + friction_power
    efficiency = mechanical / electrical if electrical > 0 else 0.0
    balance_error = abs(electrical - mechanical - total_loss)
    checks = {
        "speed_in_envelope": parameters.min_speed_rpm <= speed_rpm <= parameters.max_speed_rpm,
        "temperature_in_envelope": (
            parameters.min_winding_temp_k <= winding_temp_k <= parameters.max_winding_temp_k
            and parameters.min_magnet_temp_k <= magnet_temp_k <= parameters.max_magnet_temp_k
        ),
        "current_in_envelope": abs(current) <= parameters.max_current_a,
        "power_balance": balance_error
        <= tolerance * max(1.0, abs(electrical), abs(mechanical)),
        "efficiency_bounded": 0.0 <= efficiency <= 1.0,
    }
    return MachineResult(
        fidelity=FidelityLevel.ANALYTICAL.value,
        source="analytical-lumped",
        speed_rpm=speed_rpm,
        torque_n_m=shaft,
        current_a=current,
        electrical_power_w=electrical,
        mechanical_power_w=mechanical,
        copper_loss_w=copper,
        core_loss_w=core_power,
        friction_loss_w=friction_power,
        total_loss_w=total_loss,
        efficiency=efficiency,
        winding_temp_k=winding_temp_k,
        magnet_temp_k=magnet_temp_k,
        heat_load_winding_w=copper,
        heat_load_core_w=core_power,
        heat_load_magnet_w=0.0,
        validity=Validity(
            passed=all(checks.values()),
            checks=checks,
            detail="closed-form voltage/back-EMF balance; magnet eddy loss not modeled",
        ),
        iterations=1,
        detail=f"resistance={resistance:.6g} ohm, ke={ke:.6g} V.s/rad",
    )


def _solve_reduced(
    parameters: MachineParameters,
    machine_map: MachineMap,
    *,
    speed_rpm: float,
    load_torque_n_m: float,
    winding_temp_k: float,
    magnet_temp_k: float,
    out_of_envelope_policy: OutOfEnvelopePolicy,
) -> MachineResult:
    point = machine_map.evaluate(speed_rpm, load_torque_n_m, out_of_envelope_policy)
    balance_error = abs(
        point.electrical_power_w - point.mechanical_power_w - point.total_loss_w
    )
    checks = {
        "map_envelope": True,
        "temperature_in_envelope": (
            parameters.min_winding_temp_k <= winding_temp_k <= parameters.max_winding_temp_k
            and parameters.min_magnet_temp_k <= magnet_temp_k <= parameters.max_magnet_temp_k
        ),
        "power_balance": balance_error
        <= 1e-6 * max(1.0, abs(point.electrical_power_w)),
        "efficiency_bounded": 0.0 <= point.efficiency <= 1.0,
    }
    return MachineResult(
        fidelity=FidelityLevel.REDUCED.value,
        source=f"parameter-map:{machine_map.revision}",
        speed_rpm=point.speed_rpm,
        torque_n_m=point.torque_n_m,
        current_a=point.current_a,
        electrical_power_w=point.electrical_power_w,
        mechanical_power_w=point.mechanical_power_w,
        copper_loss_w=point.copper_loss_w,
        core_loss_w=point.core_loss_w,
        friction_loss_w=point.total_loss_w - point.copper_loss_w - point.core_loss_w,
        total_loss_w=point.total_loss_w,
        efficiency=point.efficiency,
        winding_temp_k=winding_temp_k,
        magnet_temp_k=magnet_temp_k,
        heat_load_winding_w=point.copper_loss_w,
        heat_load_core_w=point.core_loss_w,
        heat_load_magnet_w=0.0,
        validity=Validity(
            passed=all(checks.values()),
            checks=checks,
            detail=f"bilinear map {machine_map.revision}; source={machine_map.source}",
        ),
        iterations=1,
        detail=(
            f"map envelope speed={machine_map.speed_envelope_rpm} "
            f"torque={machine_map.torque_envelope_n_m}"
        ),
        warnings=point.warnings,
    )


__all__ = [
    "ElectricalCapabilityUnavailable",
    "ElectricalModelError",
    "MachineMap",
    "MachineResult",
    "MapPoint",
    "NativeEmStatus",
    "build_analytical_map",
    "native_em_benchmark_inputs",
    "native_em_status",
    "solve_machine",
]
