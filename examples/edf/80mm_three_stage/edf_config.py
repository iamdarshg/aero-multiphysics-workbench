"""Example-level EDF configuration: 80 mm three-stage ducted fan plus variants.

Everything EDF-specific lives here (the example/domain layer). Stage count,
diameter, blade rows, motor/ESC/battery choices are plain data consumed by
generic M1/M2/M3 facilities -- no core package imports this module.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EDF80Config:
    """One parametric EDF design point. All lengths in mm unless named."""

    name: str
    design_id: str
    outer_diameter_mm: float = 80.0
    inner_diameter_mm: float = 76.0
    hub_diameter_mm: float = 28.0
    length_mm: float = 150.0
    n_stages: int = 3
    blade_counts: tuple[int, ...] = (9, 9, 9)
    stator_counts: tuple[int, ...] = (11, 11)
    exit_deswirler: bool = True
    chord_mm: float = 12.0
    twist_deg: float = 25.0
    thickness_mm: float = 1.2
    axial_gap_mm: float = 8.0
    tip_clearance_mm: float = 0.5
    inlet_radius_mm: float = 6.0
    nozzle_exit_mm: float = 74.0
    kv_rpm_per_v: float = 1150.0
    motor_resistance_ohm: float = 0.008
    motor_no_load_current_a: float = 2.5
    motor_efficiency: float = 0.88
    esc_resistance_ohm: float = 0.002
    battery_n_series: int = 6
    battery_n_parallel: int = 1
    pack_max_voltage_v: float = 25.2
    rated_rpm: float = 42000.0
    max_current_a: float = 90.0
    max_winding_temp_k: float = 393.15
    min_fos: float = 1.5
    max_tip_mach: float = 0.9
    min_resonance_margin_hz: float = 50.0
    blade_material_id: str = "carbon-epoxy-ud-ply"
    shaft_material_id: str = "steel-structural"
    duct_material_id: str = "aluminium-6061-t6"
    magnet_material_id: str = "ndfeb-n42"

    def __post_init__(self) -> None:
        # __post_init__ may only validate; frozen dataclass keeps hashability.
        self.validate()

    def validate(self) -> None:
        if not self.name.strip() or not self.design_id.strip():
            raise ValueError("EDF_CONFIG_NEEDS_NAME_AND_DESIGN_ID")
        if not 0 < self.inner_diameter_mm < self.outer_diameter_mm:
            raise ValueError("EDF_DUCT_DIAMETERS_INCONSISTENT")
        if not 0 < self.hub_diameter_mm < self.inner_diameter_mm:
            raise ValueError("EDF_HUB_DIAMETER_INCONSISTENT")
        if self.n_stages < 1 or self.n_stages > 8:
            raise ValueError("EDF_STAGE_COUNT_OUT_OF_RANGE")
        if len(self.blade_counts) != self.n_stages:
            raise ValueError("EDF_BLADE_COUNTS_MUST_MATCH_STAGES")
        if len(self.stator_counts) != self.n_stages - 1:
            raise ValueError("EDF_STATOR_COUNTS_MUST_MATCH_INTER_STAGE_GAPS")
        if any(count < 2 for count in (*self.blade_counts, *self.stator_counts)):
            raise ValueError("EDF_ROW_COUNTS_MUST_BE_AT_LEAST_TWO")
        for label, value in (
            ("chord_mm", self.chord_mm),
            ("thickness_mm", self.thickness_mm),
            ("axial_gap_mm", self.axial_gap_mm),
            ("tip_clearance_mm", self.tip_clearance_mm),
            ("length_mm", self.length_mm),
        ):
            if not value > 0:
                raise ValueError(f"EDF_GEOMETRY_OUT_OF_RANGE:{label}")
        if self.rated_rpm <= 0 or self.max_current_a <= 0:
            raise ValueError("EDF_RATINGS_OUT_OF_RANGE")

    @property
    def rotor_names(self) -> tuple[str, ...]:
        return tuple(f"rotor_zone_{index}" for index in range(self.n_stages))

    @property
    def stator_names(self) -> tuple[str, ...]:
        return tuple(f"stator_zone_{index}" for index in range(self.n_stages - 1))

    @property
    def zone_length_mm(self) -> float:
        """Axial extent of one rotating row (example-level mapping)."""

        return 2.0 * self.chord_mm

    @property
    def config_hash(self) -> str:
        payload = json.dumps(
            {
                "name": self.name,
                "design_id": self.design_id,
                "outer_diameter_mm": self.outer_diameter_mm,
                "inner_diameter_mm": self.inner_diameter_mm,
                "hub_diameter_mm": self.hub_diameter_mm,
                "length_mm": self.length_mm,
                "n_stages": self.n_stages,
                "blade_counts": list(self.blade_counts),
                "stator_counts": list(self.stator_counts),
                "exit_deswirler": self.exit_deswirler,
                "chord_mm": self.chord_mm,
                "twist_deg": self.twist_deg,
                "thickness_mm": self.thickness_mm,
                "axial_gap_mm": self.axial_gap_mm,
                "tip_clearance_mm": self.tip_clearance_mm,
                "kv_rpm_per_v": self.kv_rpm_per_v,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    @classmethod
    def default(cls) -> EDF80Config:
        """The milestone design: 80 mm OD, three rotating rows."""

        return cls(name="80mm-3stage", design_id="edf-80mm-three-stage")

    @classmethod
    def variants(cls) -> tuple[EDF80Config, ...]:
        """Parameterized reuse proof: same code, other diameters/stage counts."""

        return (
            cls.default(),
            cls(
                name="70mm-2stage",
                design_id="edf-70mm-two-stage",
                outer_diameter_mm=70.0,
                inner_diameter_mm=66.0,
                hub_diameter_mm=24.0,
                length_mm=120.0,
                n_stages=2,
                blade_counts=(8, 8),
                stator_counts=(10,),
                exit_deswirler=False,
                chord_mm=11.0,
            ),
            cls(
                name="90mm-4stage",
                design_id="edf-90mm-four-stage",
                outer_diameter_mm=90.0,
                inner_diameter_mm=86.0,
                hub_diameter_mm=30.0,
                length_mm=190.0,
                n_stages=4,
                blade_counts=(10, 10, 10, 10),
                stator_counts=(12, 12, 12),
                exit_deswirler=True,
                chord_mm=13.0,
                rated_rpm=38000.0,
            ),
        )


# Operating points / objectives / constraints live in design state (4.md D+E).
# Shapes mirror the DesignRevision contract (packages/schema/src/design.ts).
OPERATING_POINTS: tuple[dict[str, object], ...] = (
    {
        "name": "static",
        "values": {
            "freestream_m_s": {"value": 0.0, "unit": "m/s"},
            "rpm": {"value": 35000.0, "unit": "rpm"},
        },
    },
    {
        "name": "forward-flow",
        "values": {
            "freestream_m_s": {"value": 18.0, "unit": "m/s"},
            "rpm": {"value": 38000.0, "unit": "rpm"},
        },
    },
    {
        "name": "max-rpm",
        "values": {
            "freestream_m_s": {"value": 0.0, "unit": "m/s"},
            "rpm": {"value": 42000.0, "unit": "rpm"},
        },
    },
)

OBJECTIVES: tuple[dict[str, object], ...] = (
    {"name": "thrust_n", "target": "maximize", "weight": 1.0, "unit": "N"},
    {"name": "thrust_per_power", "target": "maximize", "weight": 0.8, "unit": "N/W"},
    {"name": "mass_kg", "target": "minimize", "weight": 0.5, "unit": "kg"},
)

CONSTRAINTS: tuple[dict[str, object], ...] = (
    {"name": "outer_diameter_mm", "bound": "upper", "limitSI": 80.0, "unit": "mm"},
    {"name": "current_a", "bound": "upper", "limitSI": 90.0, "unit": "A"},
    {"name": "voltage_v", "bound": "upper", "limitSI": 25.2, "unit": "V"},
    {"name": "winding_temp_k", "bound": "upper", "limitSI": 393.15, "unit": "K"},
    {"name": "fos", "bound": "lower", "limitSI": 1.5, "unit": "dimensionless"},
    {"name": "tip_deflection_mm", "bound": "upper", "limitSI": 0.4, "unit": "mm"},
    {"name": "tip_mach", "bound": "upper", "limitSI": 0.9, "unit": "dimensionless"},
    {"name": "resonance_margin_hz", "bound": "lower", "limitSI": 50.0, "unit": "Hz"},
    {"name": "min_sicn", "bound": "lower", "limitSI": 0.05, "unit": "dimensionless"},
)

MATERIAL_BINDINGS: tuple[dict[str, str], ...] = (
    {"region": "rotor", "material": "blade_material_id"},
    {"region": "stator", "material": "blade_material_id"},
    {"region": "shaft", "material": "shaft_material_id"},
    {"region": "duct", "material": "duct_material_id"},
    {"region": "motor", "material": "magnet_material_id"},
)

__all__ = [
    "CONSTRAINTS",
    "MATERIAL_BINDINGS",
    "OBJECTIVES",
    "OPERATING_POINTS",
    "EDF80Config",
]
