"""Rolling and journal bearing models for life, loss, and rotordynamics.

Rolling bearings are evaluated from catalog data: dynamic/static ratings,
limiting speed, DN limit, life exponent, and friction coefficient, yielding the
ISO 281 L10 life, DN value, friction torque, and heat generation. Journal
bearings use the Sommerfeld number and Petroff friction torque with a declared
eccentricity. Stiffness/damping for a rotordynamic model must be declared from
a catalog or a detailed-EHL seam; when absent the rotordynamic feed fails
closed instead of inventing coefficients.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import pi, sqrt
from typing import Any

from aeroworkbench_core.types import Provenance
from aeroworkbench_dynamics import BearingSpec

from .lubrication import LubricationState
from .provenance import analytical_provenance, catalog_provenance
from .validity import (
    CapabilityUnavailable,
    LimitExceeded,
    MechanismError,
    Validity,
    finite,
    integer,
)

_OMEGA_FROM_RPM = pi / 30.0


class BearingKind(StrEnum):
    """The generic bearing taxonomy."""

    ROLLING = "rolling"
    JOURNAL = "journal"


@dataclass(frozen=True, slots=True)
class BearingGeometry:
    """Bearing envelope geometry used for DN limits and film estimates."""

    bore_diameter_m: float
    outer_diameter_m: float
    width_m: float
    pitch_diameter_m: float
    rolling_element_count: int = 8
    rolling_element_diameter_m: float = 0.0
    contact_angle_deg: float = 0.0

    def __post_init__(self) -> None:
        bore = finite(self.bore_diameter_m, "bearing.bore_diameter_m", positive=True)
        outer = finite(self.outer_diameter_m, "bearing.outer_diameter_m", positive=True)
        if outer <= bore:
            raise MechanismError("bearing outer diameter must exceed the bore")
        finite(self.width_m, "bearing.width_m", positive=True)
        finite(self.pitch_diameter_m, "bearing.pitch_diameter_m", positive=True)
        integer(self.rolling_element_count, "bearing.rolling_element_count", minimum=1, maximum=200)
        finite(self.rolling_element_diameter_m, "bearing.rolling_element_diameter_m", minimum=0.0)
        finite(self.contact_angle_deg, "bearing.contact_angle_deg")

    @property
    def bore_diameter_mm(self) -> float:
        return self.bore_diameter_m * 1000.0

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "bore_diameter_m": self.bore_diameter_m,
            "outer_diameter_m": self.outer_diameter_m,
            "width_m": self.width_m,
            "pitch_diameter_m": self.pitch_diameter_m,
            "rolling_element_count": self.rolling_element_count,
            "rolling_element_diameter_m": self.rolling_element_diameter_m,
            "contact_angle_deg": self.contact_angle_deg,
        }


@dataclass(frozen=True, slots=True)
class BearingCatalog:
    """Manufacturer catalog ratings and optional rotordynamic coefficients."""

    designation: str
    dynamic_load_rating_n: float
    static_load_rating_n: float
    limiting_speed_rpm: float
    dn_limit_mm_rpm: float
    life_exponent: float = 3.0
    friction_coefficient: float = 0.0015
    radial_stiffness_n_m: float | None = None
    axial_stiffness_n_m: float | None = None
    damping_n_s_m: float | None = None

    def __post_init__(self) -> None:
        if not self.designation.strip():
            raise MechanismError("bearing.designation is required")
        finite(self.dynamic_load_rating_n, "bearing.dynamic_load_rating_n", positive=True)
        finite(self.static_load_rating_n, "bearing.static_load_rating_n", positive=True)
        finite(self.limiting_speed_rpm, "bearing.limiting_speed_rpm", positive=True)
        finite(self.dn_limit_mm_rpm, "bearing.dn_limit_mm_rpm", positive=True)
        finite(self.life_exponent, "bearing.life_exponent", positive=True)
        finite(self.friction_coefficient, "bearing.friction_coefficient", positive=True)
        for label, value in (
            ("radial_stiffness_n_m", self.radial_stiffness_n_m),
            ("axial_stiffness_n_m", self.axial_stiffness_n_m),
            ("damping_n_s_m", self.damping_n_s_m),
        ):
            if value is not None:
                finite(value, f"bearing.{label}", positive=True)

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "designation": self.designation,
            "dynamic_load_rating_n": self.dynamic_load_rating_n,
            "static_load_rating_n": self.static_load_rating_n,
            "limiting_speed_rpm": self.limiting_speed_rpm,
            "dn_limit_mm_rpm": self.dn_limit_mm_rpm,
            "life_exponent": self.life_exponent,
            "friction_coefficient": self.friction_coefficient,
            "radial_stiffness_n_m": self.radial_stiffness_n_m,
            "axial_stiffness_n_m": self.axial_stiffness_n_m,
            "damping_n_s_m": self.damping_n_s_m,
        }


@dataclass(frozen=True, slots=True)
class BearingResult:
    """Evaluated bearing life, loss, film, and rotordynamic coefficients."""

    designation: str
    kind: str
    speed_rpm: float
    dn_value_mm_rpm: float
    equivalent_load_n: float
    life_revolutions: float
    life_hours: float
    friction_torque_n_m: float
    heat_generation_w: float
    radial_stiffness_n_m: float | None
    axial_stiffness_n_m: float | None
    damping_n_s_m: float | None
    min_film_thickness_m: float
    sommerfeld_number: float
    utilization: float
    validity: Validity
    provenance: Provenance

    def units(self) -> dict[str, str]:
        return {
            "speed_rpm": "1/s",
            "dn_value_mm_rpm": "mm",
            "equivalent_load_n": "N",
            "life_revolutions": "dimensionless",
            "life_hours": "s",
            "friction_torque_n_m": "N*m",
            "heat_generation_w": "W",
            "radial_stiffness_n_m": "N/m",
            "axial_stiffness_n_m": "N/m",
            "damping_n_s_m": "N*s/m",
            "min_film_thickness_m": "m",
            "sommerfeld_number": "dimensionless",
        }

    def to_rotor_bearing(self, node: int) -> BearingSpec:
        """Feed declared stiffness/damping into a rotordynamic bearing model."""

        if self.radial_stiffness_n_m is None or self.damping_n_s_m is None:
            raise CapabilityUnavailable(
                f"BEARING_ROTORDYNAMIC_COEFFICIENTS_UNAVAILABLE:{self.designation}"
            )
        return BearingSpec(
            node=node,
            kxx=self.radial_stiffness_n_m,
            kyy=self.radial_stiffness_n_m,
            cxx=self.damping_n_s_m,
            cyy=self.damping_n_s_m,
        )

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "designation": self.designation,
            "kind": self.kind,
            "speed_rpm": self.speed_rpm,
            "dn_value_mm_rpm": self.dn_value_mm_rpm,
            "equivalent_load_n": self.equivalent_load_n,
            "life_hours": self.life_hours,
            "heat_generation_w": self.heat_generation_w,
        }


def evaluate_rolling_bearing(
    catalog: BearingCatalog,
    geometry: BearingGeometry,
    *,
    speed_rpm: float,
    radial_load_n: float,
    axial_load_n: float = 0.0,
    radial_factor: float = 1.0,
    axial_factor: float = 0.0,
    required_life_h: float | None = None,
) -> BearingResult:
    """ISO 281 L10 life, DN value, friction loss, and limit checks."""

    speed = finite(speed_rpm, "speed_rpm", positive=True)
    radial = finite(radial_load_n, "radial_load_n", minimum=0.0)
    axial = finite(axial_load_n, "axial_load_n", minimum=0.0)
    x_factor = finite(radial_factor, "radial_factor", minimum=0.0)
    y_factor = finite(axial_factor, "axial_factor", minimum=0.0)
    equivalent = x_factor * radial + y_factor * axial
    if equivalent <= 0.0:
        raise MechanismError("bearing.equivalent_load must be positive")
    dn_value = geometry.bore_diameter_mm * speed
    life_million_rev = (catalog.dynamic_load_rating_n / equivalent) ** catalog.life_exponent
    life_revolutions = life_million_rev * 1.0e6
    life_hours = life_revolutions / (60.0 * speed)
    friction_torque = 0.5 * catalog.friction_coefficient * equivalent * geometry.pitch_diameter_m
    heat = friction_torque * speed * _OMEGA_FROM_RPM
    utilization = max(speed / catalog.limiting_speed_rpm, dn_value / catalog.dn_limit_mm_rpm)
    checks = {
        "speed_within_limiting": speed <= catalog.limiting_speed_rpm,
        "dn_within_limit": dn_value <= catalog.dn_limit_mm_rpm,
        "static_rating_within_limit": equivalent <= catalog.static_load_rating_n,
        "life_meets_requirement": required_life_h is None or life_hours >= required_life_h,
    }
    provenance = catalog_provenance(
        "mechanisms.bearings.rolling.iso281",
        {
            "catalog": catalog.canonical_payload(),
            "geometry": geometry.canonical_payload(),
            "speed_rpm": speed,
            "radial_load_n": radial,
            "axial_load_n": axial,
        },
        assumptions=("ISO 281 L10 basic rating life; constant equivalent load",),
    )
    result = BearingResult(
        designation=catalog.designation,
        kind=BearingKind.ROLLING.value,
        speed_rpm=speed,
        dn_value_mm_rpm=dn_value,
        equivalent_load_n=equivalent,
        life_revolutions=life_revolutions,
        life_hours=life_hours,
        friction_torque_n_m=friction_torque,
        heat_generation_w=heat,
        radial_stiffness_n_m=catalog.radial_stiffness_n_m,
        axial_stiffness_n_m=catalog.axial_stiffness_n_m,
        damping_n_s_m=catalog.damping_n_s_m,
        min_film_thickness_m=0.0,
        sommerfeld_number=0.0,
        utilization=utilization,
        validity=Validity(
            passed=all(checks.values()),
            checks=checks,
            detail=f"L10 life exponent p={catalog.life_exponent:.6g}",
        ),
        provenance=provenance,
    )
    violations: list[str] = []
    if speed > catalog.limiting_speed_rpm:
        violations.append("limiting_speed")
    if dn_value > catalog.dn_limit_mm_rpm:
        violations.append("dn_limit")
    if equivalent > catalog.static_load_rating_n:
        violations.append("static_rating")
    if violations:
        raise LimitExceeded(
            f"BEARING_LIMIT_EXCEEDED:{catalog.designation}:{','.join(violations)}",
            violations=tuple(violations),
            provenance=provenance,
        )
    return result


@dataclass(frozen=True, slots=True)
class JournalBearingGeometry:
    """A plain journal bearing from diameter, length, and clearance."""

    journal_diameter_m: float
    length_m: float
    radial_clearance_m: float
    eccentricity_ratio: float = 0.5

    def __post_init__(self) -> None:
        finite(self.journal_diameter_m, "journal.journal_diameter_m", positive=True)
        finite(self.length_m, "journal.length_m", positive=True)
        finite(self.radial_clearance_m, "journal.radial_clearance_m", positive=True)
        finite(
            self.eccentricity_ratio,
            "journal.eccentricity_ratio",
            minimum=0.0,
            maximum=0.999,
        )

    @property
    def radius_m(self) -> float:
        return self.journal_diameter_m / 2.0

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "journal_diameter_m": self.journal_diameter_m,
            "length_m": self.length_m,
            "radial_clearance_m": self.radial_clearance_m,
            "eccentricity_ratio": self.eccentricity_ratio,
        }


def evaluate_journal_bearing(
    geometry: JournalBearingGeometry,
    lubricant: LubricationState,
    *,
    speed_rpm: float,
    load_n: float,
    radial_stiffness_n_m: float | None = None,
    damping_n_s_m: float | None = None,
    required_film_ratio: float = 1.0,
) -> BearingResult:
    """Sommerfeld number, Petroff friction loss, and minimum film thickness."""

    speed = finite(speed_rpm, "speed_rpm", positive=True)
    load = finite(load_n, "load_n", positive=True)
    radius = geometry.radius_m
    clearance = geometry.radial_clearance_m
    eccentricity = geometry.eccentricity_ratio
    rev_per_s = speed / 60.0
    unit_load = load / (geometry.length_m * geometry.journal_diameter_m)
    sommerfeld = (
        lubricant.dynamic_viscosity_pa_s * rev_per_s / unit_load * (radius / clearance) ** 2
    )
    min_film = clearance * (1.0 - eccentricity)
    friction_torque = (
        2.0
        * pi
        * lubricant.dynamic_viscosity_pa_s
        * rev_per_s
        * geometry.length_m
        * radius**3
        / (clearance * sqrt(1.0 - eccentricity**2))
    )
    heat = friction_torque * speed * _OMEGA_FROM_RPM
    film_ratio = min_film / clearance
    checks = {
        "film_thickness_positive": min_film > 0.0,
        "sommerfeld_positive": sommerfeld > 0.0,
        "film_ratio_meets_requirement": film_ratio >= required_film_ratio,
    }
    provenance = analytical_provenance(
        "mechanisms.bearings.journal.sommerfeld",
        {
            "geometry": geometry.canonical_payload(),
            "lubricant": lubricant.canonical_payload(),
            "speed_rpm": speed,
            "load_n": load,
        },
        assumptions=("Sommerfeld number and eccentricity-corrected Petroff torque",),
    )
    return BearingResult(
        designation=f"journal-{geometry.journal_diameter_m:.4f}",
        kind=BearingKind.JOURNAL.value,
        speed_rpm=speed,
        dn_value_mm_rpm=geometry.journal_diameter_m * 1000.0 * speed,
        equivalent_load_n=load,
        life_revolutions=0.0,
        life_hours=0.0,
        friction_torque_n_m=friction_torque,
        heat_generation_w=heat,
        radial_stiffness_n_m=radial_stiffness_n_m,
        axial_stiffness_n_m=None,
        damping_n_s_m=damping_n_s_m,
        min_film_thickness_m=min_film,
        sommerfeld_number=sommerfeld,
        utilization=1.0 - film_ratio,
        validity=Validity(
            passed=all(checks.values()),
            checks=checks,
            detail="short-bearing screening; detailed EHL is a native seam",
        ),
        provenance=provenance,
    )


__all__ = [
    "BearingCatalog",
    "BearingGeometry",
    "BearingKind",
    "BearingResult",
    "JournalBearingGeometry",
    "evaluate_journal_bearing",
    "evaluate_rolling_bearing",
]
