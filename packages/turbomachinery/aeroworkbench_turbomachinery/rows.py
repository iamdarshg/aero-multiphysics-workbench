"""Blade-row contract: role, frame, spool binding, stations, and geometry state."""

from __future__ import annotations

from dataclasses import dataclass

from .units import Quantity, require_dimension

ROW_ROLES: tuple[str, ...] = (
    "work_adding",
    "work_extracting",
    "turning_only",
    "diffuser_guide",
)

ROW_FRAMES: tuple[str, ...] = ("rotating", "stationary")

FLOW_FAMILIES: tuple[str, ...] = ("axial", "radial", "mixed")


@dataclass(frozen=True, slots=True)
class BladeClearance:
    """Clearance/endwall/shroud state attached to a row."""

    tip_clearance: Quantity | None = None
    endwall_state: str | None = None
    shroud_state: str | None = None

    def __post_init__(self) -> None:
        if self.tip_clearance is not None:
            require_dimension(self.tip_clearance, "length", "tipClearance")

    def canonical(self) -> dict[str, object]:
        return {
            "tipClearance": None if self.tip_clearance is None else self.tip_clearance.canonical(),
            "endwallState": self.endwall_state,
            "shroudState": self.shroud_state,
        }


@dataclass(frozen=True, slots=True)
class BladeRow:
    """One blade row bound into the gas-path graph and a shaft."""

    row_id: str
    node: str
    role: str
    frame: str
    shaft: str | None
    station_in: str
    station_out: str
    row_count: int = 1
    periodicity: int = 1
    family: str = "axial"
    geometry_ref: str | None = None
    clearance: BladeClearance = BladeClearance()
    material_ref: str | None = None
    thermal_ref: str | None = None

    def __post_init__(self) -> None:
        if not self.row_id.strip():
            raise ValueError("ROW_ID_REQUIRED")
        if not self.node.strip():
            raise ValueError("ROW_NODE_REQUIRED")
        if self.role not in ROW_ROLES:
            raise ValueError(f"UNKNOWN_ROW_ROLE:{self.role}")
        if self.frame not in ROW_FRAMES:
            raise ValueError(f"UNKNOWN_ROW_FRAME:{self.frame}")
        if self.family not in FLOW_FAMILIES:
            raise ValueError(f"UNKNOWN_FLOW_FAMILY:{self.family}")
        if not self.station_in.strip() or not self.station_out.strip():
            raise ValueError(f"ROW_STATION_REQUIRED:{self.row_id}")
        if self.row_count < 1 or self.periodicity < 1:
            raise ValueError(f"INVALID_ROW_COUNT_OR_PERIODICITY:{self.row_id}")
        if self.frame == "rotating":
            if not self.shaft:
                raise ValueError(f"ROTATING_ROW_NEEDS_SHAFT:{self.row_id}")
        elif self.shaft:
            raise ValueError(f"STATIONARY_ROW_HAS_SHAFT:{self.row_id}")
        if self.role in ("work_adding", "work_extracting") and self.frame != "rotating":
            raise ValueError(f"WORK_ROW_MUST_ROTATE:{self.row_id}")
        if self.role == "diffuser_guide" and self.frame != "stationary":
            raise ValueError(f"DIFFUSER_GUIDE_MUST_BE_STATIONARY:{self.row_id}")

    def canonical(self) -> dict[str, object]:
        return {
            "id": self.row_id,
            "node": self.node,
            "role": self.role,
            "frame": self.frame,
            "shaft": self.shaft,
            "stationIn": self.station_in,
            "stationOut": self.station_out,
            "rowCount": self.row_count,
            "periodicity": self.periodicity,
            "family": self.family,
            "geometryRef": self.geometry_ref,
            "clearance": self.clearance.canonical(),
            "materialRef": self.material_ref,
            "thermalRef": self.thermal_ref,
        }
