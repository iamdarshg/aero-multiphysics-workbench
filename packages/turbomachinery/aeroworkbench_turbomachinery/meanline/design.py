"""Meanline design contracts: row families, rows, and a stage design.

Row families name the reusable machine families required by the issue: axial
fan/compressor rotor and stator, axial turbine nozzle and rotor, radial/mixed
compressor impeller and diffuser, and radial/mixed turbine rotor. A family binds
a role/frame/flow-family to the turning frame and the correlation set used to
close the row, so compressors, turbines, and fans share one contract.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, cast

from .errors import MeanlineInputError
from .properties import IdealGas


@dataclass(frozen=True, slots=True)
class RowFamilyModel:
    """Reusable row family definition."""

    family: str
    role: str
    frame: str
    flow_family: str
    turning_frame: str
    loss_models: tuple[str, ...]
    slip: bool = False

    def __post_init__(self) -> None:
        if self.role not in ("work_adding", "work_extracting", "turning_only", "diffuser_guide"):
            raise MeanlineInputError(f"UNKNOWN_FAMILY_ROLE:{self.family}:{self.role}")
        if self.frame not in ("rotating", "stationary"):
            raise MeanlineInputError(f"UNKNOWN_FAMILY_FRAME:{self.family}:{self.frame}")
        if self.flow_family not in ("axial", "radial", "mixed"):
            raise MeanlineInputError(f"UNKNOWN_FAMILY_FLOW:{self.family}:{self.flow_family}")
        if self.turning_frame not in ("relative", "absolute"):
            raise MeanlineInputError(f"UNKNOWN_TURNING_FRAME:{self.family}:{self.turning_frame}")

    def canonical(self) -> dict[str, object]:
        return {
            "family": self.family,
            "role": self.role,
            "frame": self.frame,
            "flowFamily": self.flow_family,
            "turningFrame": self.turning_frame,
            "lossModels": list(self.loss_models),
            "slip": self.slip,
        }


_COMPRESSOR_LOSSES = (
    "lieblein-profile-loss",
    "carter-secondary-loss",
    "dunham-came-tip-clearance-loss",
    "conrad-incidence-loss",
    "lieblein-blockage",
)
_STATOR_LOSSES = (
    "lieblein-profile-loss",
    "carter-secondary-loss",
    "conrad-incidence-loss",
    "lieblein-blockage",
)
_TURBINE_LOSSES = (
    "ainley-mathieson-profile-loss",
    "ainley-mathieson-secondary-loss",
    "dunham-came-tip-clearance-loss",
    "conrad-incidence-loss",
)
_RADIAL_IMPELLER_LOSSES = (
    "coppage-impeller-loss",
    "carter-secondary-loss",
    "conrad-incidence-loss",
)
_RADIAL_TURBINE_LOSSES = (
    "ainley-mathieson-profile-loss",
    "ainley-mathieson-secondary-loss",
    "conrad-incidence-loss",
)
_MIXED_COMPRESSOR_LOSSES = (
    "coppage-impeller-loss",
    "carter-secondary-loss",
    "dunham-came-tip-clearance-loss",
    "conrad-incidence-loss",
)
_DIFFUSER_LOSSES = ("japikse-diffuser-recovery",)

ROW_FAMILY_MODELS: dict[str, RowFamilyModel] = {
    model.family: model
    for model in (
        RowFamilyModel(
            "axial_compressor_rotor", "work_adding", "rotating", "axial", "relative",
            _COMPRESSOR_LOSSES,
        ),
        RowFamilyModel(
            "axial_compressor_stator", "turning_only", "stationary", "axial", "absolute",
            _STATOR_LOSSES,
        ),
        RowFamilyModel(
            "axial_turbine_nozzle", "turning_only", "stationary", "axial", "absolute",
            _TURBINE_LOSSES,
        ),
        RowFamilyModel(
            "axial_turbine_rotor", "work_extracting", "rotating", "axial", "relative",
            _TURBINE_LOSSES,
        ),
        RowFamilyModel(
            "radial_compressor_impeller", "work_adding", "rotating", "radial", "relative",
            _RADIAL_IMPELLER_LOSSES, slip=True,
        ),
        RowFamilyModel(
            "radial_compressor_diffuser", "diffuser_guide", "stationary", "radial", "absolute",
            _DIFFUSER_LOSSES,
        ),
        RowFamilyModel(
            "radial_turbine_rotor", "work_extracting", "rotating", "radial", "relative",
            _RADIAL_TURBINE_LOSSES,
        ),
        RowFamilyModel(
            "mixed_compressor_rotor", "work_adding", "rotating", "mixed", "relative",
            _MIXED_COMPRESSOR_LOSSES, slip=True,
        ),
        RowFamilyModel(
            "mixed_turbine_rotor", "work_extracting", "rotating", "mixed", "relative",
            _RADIAL_TURBINE_LOSSES,
        ),
    )
}


def _positive(value: float, label: str) -> None:
    if value != value or value in (float("inf"), float("-inf")):
        raise MeanlineInputError(f"NONFINITE_INPUT:{label}")
    if value <= 0.0:
        raise MeanlineInputError(f"NONPOSITIVE_INPUT:{label}")


def _nonnegative(value: float, label: str) -> None:
    if value != value or value in (float("inf"), float("-inf")):
        raise MeanlineInputError(f"NONFINITE_INPUT:{label}")
    if value < 0.0:
        raise MeanlineInputError(f"NEGATIVE_INPUT:{label}")


@dataclass(frozen=True, slots=True)
class MeanlineRow:
    """Preliminary design parameters for one blade row."""

    row_family: str
    mean_radius_in_m: float
    mean_radius_out_m: float
    meridional_velocity_in_m_s: float
    inlet_metal_angle_deg: float
    exit_metal_angle_deg: float
    stagger_deg: float
    camber_deg: float
    solidity: float
    chord_m: float
    span_m: float
    blade_count: int
    meridional_velocity_out_m_s: float | None = None
    tip_clearance_m: float = 0.0
    meridional_angle_deg: float = 0.0
    shrouded: bool = False
    diffuser_area_ratio: float | None = None
    recovery_efficiency: float = 0.85
    loss_scale: float = 1.0

    def __post_init__(self) -> None:
        if self.row_family not in ROW_FAMILY_MODELS:
            raise MeanlineInputError(f"UNKNOWN_ROW_FAMILY:{self.row_family}")
        _positive(self.mean_radius_in_m, "mean_radius_in_m")
        _positive(self.mean_radius_out_m, "mean_radius_out_m")
        _positive(self.meridional_velocity_in_m_s, "meridional_velocity_in_m_s")
        if self.meridional_velocity_out_m_s is None:
            object.__setattr__(self, "meridional_velocity_out_m_s", self.meridional_velocity_in_m_s)
        else:
            _positive(self.meridional_velocity_out_m_s, "meridional_velocity_out_m_s")
        _positive(self.solidity, "solidity")
        _positive(self.chord_m, "chord_m")
        _positive(self.span_m, "span_m")
        if self.blade_count < 1:
            raise MeanlineInputError(f"BLADE_COUNT_MUST_BE_POSITIVE:{self.blade_count}")
        _nonnegative(self.tip_clearance_m, "tip_clearance_m")
        if self.tip_clearance_m >= self.span_m:
            raise MeanlineInputError("TIP_CLEARANCE_MUST_BE_SMALLER_THAN_SPAN")
        _positive(self.loss_scale, "loss_scale")
        if self.diffuser_area_ratio is not None:
            _positive(self.diffuser_area_ratio, "diffuser_area_ratio")

    @property
    def family_model(self) -> RowFamilyModel:
        return ROW_FAMILY_MODELS[self.row_family]

    def canonical(self) -> dict[str, object]:
        return {
            "rowFamily": self.row_family,
            "meanRadiusInM": self.mean_radius_in_m,
            "meanRadiusOutM": self.mean_radius_out_m,
            "meridionalVelocityInMs": self.meridional_velocity_in_m_s,
            "meridionalVelocityOutMs": self.meridional_velocity_out_m_s,
            "inletMetalAngleDeg": self.inlet_metal_angle_deg,
            "exitMetalAngleDeg": self.exit_metal_angle_deg,
            "staggerDeg": self.stagger_deg,
            "camberDeg": self.camber_deg,
            "solidity": self.solidity,
            "chordM": self.chord_m,
            "spanM": self.span_m,
            "bladeCount": self.blade_count,
            "tipClearanceM": self.tip_clearance_m,
            "meridionalAngleDeg": self.meridional_angle_deg,
            "shrouded": self.shrouded,
            "diffuserAreaRatio": self.diffuser_area_ratio,
            "recoveryEfficiency": self.recovery_efficiency,
            "lossScale": self.loss_scale,
        }


@dataclass(frozen=True, slots=True)
class StageDesign:
    """One-dimensional design point for a multi-row gas path."""

    gas: IdealGas
    inlet_total_temperature_k: float
    inlet_total_pressure_pa: float
    mass_flow_kg_s: float
    rotational_speed_rpm: float
    rows: tuple[MeanlineRow, ...]
    name: str = "meanline-stage"
    inlet_swirl_angle_deg: float = 0.0
    dynamic_viscosity_pa_s: float = 1.8e-5

    def __post_init__(self) -> None:
        _positive(self.inlet_total_temperature_k, "inlet_total_temperature_k")
        _positive(self.inlet_total_pressure_pa, "inlet_total_pressure_pa")
        _positive(self.mass_flow_kg_s, "mass_flow_kg_s")
        _nonnegative(self.rotational_speed_rpm, "rotational_speed_rpm")
        _positive(self.dynamic_viscosity_pa_s, "dynamic_viscosity_pa_s")
        if not self.rows:
            raise MeanlineInputError("STAGE_NEEDS_AT_LEAST_ONE_ROW")
        if not self.name.strip():
            raise MeanlineInputError("STAGE_NAME_REQUIRED")

    def canonical(self) -> dict[str, object]:
        return {
            "name": self.name,
            "gas": self.gas.canonical(),
            "inletTotalTemperatureK": self.inlet_total_temperature_k,
            "inletTotalPressurePa": self.inlet_total_pressure_pa,
            "massFlowKgS": self.mass_flow_kg_s,
            "rotationalSpeedRpm": self.rotational_speed_rpm,
            "inletSwirlAngleDeg": self.inlet_swirl_angle_deg,
            "dynamicViscosityPaS": self.dynamic_viscosity_pa_s,
            "rows": [row.canonical() for row in self.rows],
        }


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise MeanlineInputError(f"EXPECTED_OBJECT:{label}")
    return value


def _sequence(value: Any, label: str) -> Sequence[Any]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise MeanlineInputError(f"EXPECTED_ARRAY:{label}")
    return cast(Sequence[Any], value)


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MeanlineInputError(f"EXPECTED_NUMBER:{label}")
    return float(value)


def _optional_number(value: Any, label: str) -> float | None:
    if value is None:
        return None
    return _number(value, label)


def _boolean(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise MeanlineInputError(f"EXPECTED_BOOLEAN:{label}")
    return value


def _row_from_payload(payload: Mapping[str, Any], label: str) -> MeanlineRow:
    return MeanlineRow(
        row_family=str(payload.get("rowFamily", "")),
        mean_radius_in_m=_number(payload.get("meanRadiusInM"), f"{label}.meanRadiusInM"),
        mean_radius_out_m=_number(payload.get("meanRadiusOutM"), f"{label}.meanRadiusOutM"),
        meridional_velocity_in_m_s=_number(
            payload.get("meridionalVelocityInMs"), f"{label}.meridionalVelocityInMs"
        ),
        meridional_velocity_out_m_s=_optional_number(
            payload.get("meridionalVelocityOutMs"), f"{label}.meridionalVelocityOutMs"
        ),
        inlet_metal_angle_deg=_number(
            payload.get("inletMetalAngleDeg"), f"{label}.inletMetalAngleDeg"
        ),
        exit_metal_angle_deg=_number(
            payload.get("exitMetalAngleDeg"), f"{label}.exitMetalAngleDeg"
        ),
        stagger_deg=_number(payload.get("staggerDeg"), f"{label}.staggerDeg"),
        camber_deg=_number(payload.get("camberDeg"), f"{label}.camberDeg"),
        solidity=_number(payload.get("solidity"), f"{label}.solidity"),
        chord_m=_number(payload.get("chordM"), f"{label}.chordM"),
        span_m=_number(payload.get("spanM"), f"{label}.spanM"),
        blade_count=int(_number(payload.get("bladeCount"), f"{label}.bladeCount")),
        tip_clearance_m=_number(payload.get("tipClearanceM", 0.0), f"{label}.tipClearanceM"),
        meridional_angle_deg=_number(
            payload.get("meridionalAngleDeg", 0.0), f"{label}.meridionalAngleDeg"
        ),
        shrouded=_boolean(payload.get("shrouded", False), f"{label}.shrouded"),
        diffuser_area_ratio=_optional_number(
            payload.get("diffuserAreaRatio"), f"{label}.diffuserAreaRatio"
        ),
        recovery_efficiency=_number(
            payload.get("recoveryEfficiency", 0.85), f"{label}.recoveryEfficiency"
        ),
        loss_scale=_number(payload.get("lossScale", 1.0), f"{label}.lossScale"),
    )


def stage_from_payload(payload: Mapping[str, Any]) -> StageDesign:
    """Build a :class:`StageDesign` from a plain canonical JSON document."""

    document = _mapping(payload, "stage")
    gas_document = _mapping(document.get("gas"), "gas")
    gas = IdealGas(
        cp_j_kg_k=_number(gas_document.get("cpJkgK"), "gas.cpJkgK"),
        gamma=_number(gas_document.get("gamma"), "gas.gamma"),
        gas_constant_j_kg_k=_number(gas_document.get("gasConstantJkgK"), "gas.gasConstantJkgK"),
    )
    rows = tuple(
        _row_from_payload(_mapping(item, f"rows[{index}]"), f"rows[{index}]")
        for index, item in enumerate(_sequence(document.get("rows") or [], "rows"))
    )
    return StageDesign(
        gas=gas,
        inlet_total_temperature_k=_number(
            document.get("inletTotalTemperatureK"), "inletTotalTemperatureK"
        ),
        inlet_total_pressure_pa=_number(
            document.get("inletTotalPressurePa"), "inletTotalPressurePa"
        ),
        mass_flow_kg_s=_number(document.get("massFlowKgS"), "massFlowKgS"),
        rotational_speed_rpm=_number(
            document.get("rotationalSpeedRpm"), "rotationalSpeedRpm"
        ),
        rows=rows,
        name=str(document.get("name", "meanline-stage")),
        inlet_swirl_angle_deg=_number(
            document.get("inletSwirlAngleDeg", 0.0), "inletSwirlAngleDeg"
        ),
        dynamic_viscosity_pa_s=_number(
            document.get("dynamicViscosityPaS", 1.8e-5), "dynamicViscosityPaS"
        ),
    )


__all__ = [
    "RowFamilyModel",
    "ROW_FAMILY_MODELS",
    "MeanlineRow",
    "StageDesign",
    "stage_from_payload",
]
