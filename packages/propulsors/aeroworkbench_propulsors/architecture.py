"""Generic propulsor architecture contract (unshrouded / open / shrouded).

One immutable, hashable declaration represents one or more rotating propulsor
rows without ever assuming a duct or a stationary stator exists:

* tractor/pusher placement relative to the vehicle;
* coaxial/contra-rotating groupings with opposite rotation directions;
* independent or mechanically linked shafts, each with its own RPM;
* fixed / variable / collective pitch, with an optional cyclic seam;
* spinner/hub/nacelle/shaft geometry and an installation frame.

No product or application name appears here. The same contract represents a
single tractor propeller, a pusher propeller, a coaxial pair, an open-rotor or
propfan pair, and a ducted rotor (which simply sets ``ducted``).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, cast

from aeroworkbench_core.types import Provenance

from .provenance import SOFTWARE_VERSION, analytical_provenance
from .validity import PropulsorError, finite, integer, nonempty

SCHEMA_VERSION = 1

PLACEMENTS: tuple[str, ...] = ("tractor", "pusher")
DIRECTIONS: tuple[str, ...] = ("clockwise", "counterclockwise")
PITCH_CONTROLS: tuple[str, ...] = ("fixed", "variable", "collective", "cyclic")
SHAFT_KINDS: tuple[str, ...] = ("independent", "common", "geared")


@dataclass(frozen=True, slots=True)
class SpinnerGeometry:
    """Spinner/hub/shaft geometry shared by an unshrouded propulsor."""

    nose_radius_m: float
    nose_length_m: float
    hub_radius_m: float
    shaft_radius_m: float = 0.02

    def __post_init__(self) -> None:
        finite(self.nose_radius_m, "spinner.nose_radius_m", positive=True)
        finite(self.nose_length_m, "spinner.nose_length_m", positive=True)
        finite(self.hub_radius_m, "spinner.hub_radius_m", positive=True)
        finite(self.shaft_radius_m, "spinner.shaft_radius_m", positive=True)
        if self.nose_radius_m > self.hub_radius_m * 1.5:
            raise PropulsorError("spinner.nose_radius_m exceeds hub envelope")

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "noseRadiusM": self.nose_radius_m,
            "noseLengthM": self.nose_length_m,
            "hubRadiusM": self.hub_radius_m,
            "shaftRadiusM": self.shaft_radius_m,
        }


@dataclass(frozen=True, slots=True)
class InstallationFrame:
    """Reference frame of the propulsor relative to a vehicle/body."""

    origin_m: tuple[float, float, float] = (0.0, 0.0, 0.0)
    axis: tuple[float, float, float] = (1.0, 0.0, 0.0)
    body_ref: str | None = None

    def __post_init__(self) -> None:
        from math import isfinite

        if len(self.origin_m) != 3 or not all(isfinite(v) for v in self.origin_m):
            raise PropulsorError("installation_frame.origin_m must be 3 finite numbers")
        axis_norm = sum(component * component for component in self.axis) ** 0.5
        if len(self.axis) != 3 or axis_norm <= 0.0:
            raise PropulsorError("installation_frame.axis must be a nonzero 3-vector")

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "originM": list(self.origin_m),
            "axis": list(self.axis),
            "bodyRef": self.body_ref,
        }


@dataclass(frozen=True, slots=True)
class RotorDeclaration:
    """One rotating propulsor row; no stator or duct is implied."""

    rotor_id: str
    blade_count: int
    tip_radius_m: float
    hub_radius_m: float
    rpm: float
    direction: str
    shaft_id: str
    pitch_control: str = "fixed"
    collective_pitch_deg: float = 0.0
    group_id: str | None = None
    geometry_ref: str | None = None
    material_ref: str | None = None

    def __post_init__(self) -> None:
        nonempty(self.rotor_id, "rotor.rotor_id")
        integer(self.blade_count, "rotor.blade_count", minimum=1, maximum=64)
        finite(self.tip_radius_m, "rotor.tip_radius_m", positive=True)
        finite(self.hub_radius_m, "rotor.hub_radius_m", positive=True)
        if self.hub_radius_m >= self.tip_radius_m:
            raise PropulsorError(f"rotor.hub_radius_m must be below tip for {self.rotor_id}")
        finite(self.rpm, "rotor.rpm", minimum=0.0)
        if self.direction not in DIRECTIONS:
            raise PropulsorError(f"rotor.direction unknown:{self.direction}")
        nonempty(self.shaft_id, "rotor.shaft_id")
        if self.pitch_control not in PITCH_CONTROLS:
            raise PropulsorError(f"rotor.pitch_control unknown:{self.pitch_control}")
        finite(self.collective_pitch_deg, "rotor.collective_pitch_deg")

    @property
    def diameter_m(self) -> float:
        return 2.0 * self.tip_radius_m

    @property
    def disk_area_m2(self) -> float:
        from math import pi

        return pi * self.tip_radius_m * self.tip_radius_m

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "rotorId": self.rotor_id,
            "bladeCount": self.blade_count,
            "tipRadiusM": self.tip_radius_m,
            "hubRadiusM": self.hub_radius_m,
            "rpm": self.rpm,
            "direction": self.direction,
            "shaftId": self.shaft_id,
            "pitchControl": self.pitch_control,
            "collectivePitchDeg": self.collective_pitch_deg,
            "groupId": self.group_id,
            "geometryRef": self.geometry_ref,
            "materialRef": self.material_ref,
        }


@dataclass(frozen=True, slots=True)
class ShaftDeclaration:
    """One shaft/spool with independent or linked speed and direction."""

    shaft_id: str
    kind: str = "independent"
    speed_rpm: float | None = None
    linked_shaft_id: str | None = None
    gear_ratio: float | None = None
    mechanical_loss_fraction: float = 0.0

    def __post_init__(self) -> None:
        nonempty(self.shaft_id, "shaft.shaft_id")
        if self.kind not in SHAFT_KINDS:
            raise PropulsorError(f"shaft.kind unknown:{self.kind}")
        if self.speed_rpm is not None:
            finite(self.speed_rpm, "shaft.speed_rpm", minimum=0.0)
        if self.kind == "geared":
            if self.linked_shaft_id is None:
                raise PropulsorError(f"geared shaft needs linked_shaft_id:{self.shaft_id}")
            if self.gear_ratio is None or self.gear_ratio <= 0.0:
                raise PropulsorError(f"geared shaft needs positive gear_ratio:{self.shaft_id}")
        elif self.gear_ratio is not None:
            raise PropulsorError(f"non-geared shaft has gear_ratio:{self.shaft_id}")
        if self.kind == "common" and self.linked_shaft_id is None:
            raise PropulsorError(f"common shaft needs linked_shaft_id:{self.shaft_id}")
        if self.kind == "independent" and self.linked_shaft_id is not None:
            raise PropulsorError(f"independent shaft has linked_shaft_id:{self.shaft_id}")
        finite(
            self.mechanical_loss_fraction,
            "shaft.mechanical_loss_fraction",
            minimum=0.0,
            maximum=0.999,
        )

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "shaftId": self.shaft_id,
            "kind": self.kind,
            "speedRpm": self.speed_rpm,
            "linkedShaftId": self.linked_shaft_id,
            "gearRatio": self.gear_ratio,
            "mechanicalLossFraction": self.mechanical_loss_fraction,
        }


@dataclass(frozen=True, slots=True)
class PitchSchedule:
    """Collective pitch schedule sampled against advance ratio."""

    rotor_id: str
    points: tuple[tuple[float, float], ...]

    def __post_init__(self) -> None:
        nonempty(self.rotor_id, "pitch_schedule.rotor_id")
        if len(self.points) < 2:
            raise PropulsorError("pitch_schedule needs at least two points")
        previous = -1.0
        for advance_ratio, _pitch in self.points:
            finite(advance_ratio, "pitch_schedule.advance_ratio", minimum=0.0)
            if advance_ratio <= previous:
                raise PropulsorError("pitch_schedule advance ratios must increase")
            previous = advance_ratio

    def collective_deg(self, advance_ratio: float) -> float:
        if advance_ratio <= self.points[0][0]:
            return self.points[0][1]
        if advance_ratio >= self.points[-1][0]:
            return self.points[-1][1]
        for (x0, y0), (x1, y1) in zip(self.points, self.points[1:], strict=False):
            if x0 <= advance_ratio <= x1:
                fraction = (advance_ratio - x0) / (x1 - x0)
                return y0 + fraction * (y1 - y0)
        return self.points[-1][1]

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "rotorId": self.rotor_id,
            "points": [list(point) for point in self.points],
        }


@dataclass(frozen=True, slots=True)
class CyclicPitchSeam:
    """Optional cyclic pitch seam reserved for future rotorcraft use."""

    amplitude_deg: float
    phase_deg: float = 0.0

    def __post_init__(self) -> None:
        finite(self.amplitude_deg, "cyclic.amplitude_deg", minimum=0.0)
        finite(self.phase_deg, "cyclic.phase_deg")

    def canonical_payload(self) -> dict[str, Any]:
        return {"amplitudeDeg": self.amplitude_deg, "phaseDeg": self.phase_deg}


@dataclass(frozen=True, slots=True)
class PropulsorArchitecture:
    """Immutable canonical propulsor architecture (ducted or unshrouded)."""

    architecture_id: str
    rotors: tuple[RotorDeclaration, ...]
    shafts: tuple[ShaftDeclaration, ...]
    placement: str = "tractor"
    ducted: bool = False
    stator: bool = False
    duct_geometry_ref: str | None = None
    spinner: SpinnerGeometry | None = None
    nacelle_radius_m: float | None = None
    installation_frame: InstallationFrame = InstallationFrame()
    pitch_schedules: tuple[PitchSchedule, ...] = ()
    cyclic: CyclicPitchSeam | None = None
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise PropulsorError(f"SCHEMA_VERSION_UNSUPPORTED:{self.schema_version}")
        nonempty(self.architecture_id, "architecture.architecture_id")
        if not self.rotors:
            raise PropulsorError("architecture needs at least one rotor")
        if not self.shafts:
            raise PropulsorError("architecture needs at least one shaft")
        if self.placement not in PLACEMENTS:
            raise PropulsorError(f"architecture.placement unknown:{self.placement}")
        if self.nacelle_radius_m is not None:
            finite(self.nacelle_radius_m, "architecture.nacelle_radius_m", positive=True)
        self._validate_unique()
        self._validate_shafts()
        self._validate_rotors()
        self._validate_groups()
        self._validate_schedules()

    def _validate_unique(self) -> None:
        for label, identifiers in (
            ("ROTOR", [rotor.rotor_id for rotor in self.rotors]),
            ("SHAFT", [shaft.shaft_id for shaft in self.shafts]),
        ):
            if len(identifiers) != len(set(identifiers)):
                raise PropulsorError(f"DUPLICATE_{label}")

    def _validate_shafts(self) -> None:
        by_id = {shaft.shaft_id: shaft for shaft in self.shafts}
        for shaft in self.shafts:
            if shaft.linked_shaft_id is not None:
                if shaft.linked_shaft_id not in by_id:
                    raise PropulsorError(f"SHAFT_LINK_UNKNOWN:{shaft.shaft_id}")
                if shaft.linked_shaft_id == shaft.shaft_id:
                    raise PropulsorError(f"SHAFT_SELF_LINK:{shaft.shaft_id}")

    def _validate_rotors(self) -> None:
        by_id = {shaft.shaft_id: shaft for shaft in self.shafts}
        used: dict[str, list[str]] = {}
        for rotor in self.rotors:
            if rotor.shaft_id not in by_id:
                raise PropulsorError(f"ROTOR_SHAFT_UNKNOWN:{rotor.rotor_id}")
            used.setdefault(rotor.shaft_id, []).append(rotor.rotor_id)
            if rotor.pitch_control == "cyclic" and self.cyclic is None:
                raise PropulsorError(f"CYCLIC_SEAM_REQUIRED:{rotor.rotor_id}")
        for shaft_id, rotor_ids in used.items():
            if len(rotor_ids) > 1 and by_id[shaft_id].kind != "common":
                raise PropulsorError(f"SHARED_SHAFT_NOT_COMMON:{shaft_id}")

    def _validate_groups(self) -> None:
        groups: dict[str, list[RotorDeclaration]] = {}
        for rotor in self.rotors:
            if rotor.group_id is not None:
                groups.setdefault(rotor.group_id, []).append(rotor)
        for group_id, members in groups.items():
            if len(members) < 2:
                raise PropulsorError(f"COAXIAL_GROUP_TOO_SMALL:{group_id}")
            ordered = sorted(members, key=lambda item: item.rotor_id)
            for first, second in zip(ordered, ordered[1:], strict=False):
                if first.direction == second.direction:
                    raise PropulsorError(
                        f"CONTRA_ROTATION_DIRECTION_MATCH:{group_id}:{first.rotor_id}"
                    )

    def _validate_schedules(self) -> None:
        rotor_ids = {rotor.rotor_id for rotor in self.rotors}
        seen: set[str] = set()
        for schedule in self.pitch_schedules:
            if schedule.rotor_id not in rotor_ids:
                raise PropulsorError(f"PITCH_SCHEDULE_ROTOR_UNKNOWN:{schedule.rotor_id}")
            if schedule.rotor_id in seen:
                raise PropulsorError(f"DUPLICATE_PITCH_SCHEDULE:{schedule.rotor_id}")
            seen.add(schedule.rotor_id)

    def rotor(self, rotor_id: str) -> RotorDeclaration:
        for rotor in self.rotors:
            if rotor.rotor_id == rotor_id:
                return rotor
        raise PropulsorError(f"ROTOR_UNKNOWN:{rotor_id}")

    def shaft(self, shaft_id: str) -> ShaftDeclaration:
        for shaft in self.shafts:
            if shaft.shaft_id == shaft_id:
                return shaft
        raise PropulsorError(f"SHAFT_UNKNOWN:{shaft_id}")

    def schedule_for(self, rotor_id: str) -> PitchSchedule | None:
        for schedule in self.pitch_schedules:
            if schedule.rotor_id == rotor_id:
                return schedule
        return None

    @property
    def number_of_rotors(self) -> int:
        return len(self.rotors)

    @property
    def is_contra_rotating(self) -> bool:
        return any(rotor.group_id is not None for rotor in self.rotors)

    def coaxial_groups(self) -> dict[str, tuple[RotorDeclaration, ...]]:
        groups: dict[str, list[RotorDeclaration]] = {}
        for rotor in self.rotors:
            if rotor.group_id is not None:
                groups.setdefault(rotor.group_id, []).append(rotor)
        return {
            group_id: tuple(sorted(members, key=lambda item: item.rotor_id))
            for group_id, members in groups.items()
        }

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "schemaVersion": self.schema_version,
            "architectureId": self.architecture_id,
            "placement": self.placement,
            "ducted": self.ducted,
            "stator": self.stator,
            "ductGeometryRef": self.duct_geometry_ref,
            "spinner": None if self.spinner is None else self.spinner.canonical_payload(),
            "nacelleRadiusM": self.nacelle_radius_m,
            "installationFrame": self.installation_frame.canonical_payload(),
            "rotors": [
                rotor.canonical_payload() for rotor in sorted(self.rotors, key=lambda r: r.rotor_id)
            ],
            "shafts": [
                shaft.canonical_payload()
                for shaft in sorted(self.shafts, key=lambda s: s.shaft_id)
            ],
            "pitchSchedules": [
                schedule.canonical_payload()
                for schedule in sorted(self.pitch_schedules, key=lambda s: s.rotor_id)
            ],
            "cyclic": None if self.cyclic is None else self.cyclic.canonical_payload(),
        }

    @property
    def architecture_hash(self) -> str:
        return architecture_hash(self)


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise PropulsorError(f"EXPECTED_OBJECT:{label}")
    return cast(Mapping[str, Any], value)


def _sequence(value: Any, label: str) -> Sequence[Any]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise PropulsorError(f"EXPECTED_ARRAY:{label}")
    return cast(Sequence[Any], value)


def _string(value: Any, label: str) -> str:
    return nonempty(value, label)


def _optional_string(value: Any, label: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise PropulsorError(f"EXPECTED_STRING:{label}")
    return value


def _optional_number(value: Any, label: str) -> float | None:
    if value is None:
        return None
    return finite(value, label)


def _boolean(value: Any, label: str, default: bool) -> bool:
    if value is None:
        return default
    if not isinstance(value, bool):
        raise PropulsorError(f"EXPECTED_BOOLEAN:{label}")
    return value


def _rotor(value: Any, label: str) -> RotorDeclaration:
    item = _mapping(value, label)
    return RotorDeclaration(
        rotor_id=_string(item.get("rotorId"), f"{label}.rotorId"),
        blade_count=integer(item.get("bladeCount"), f"{label}.bladeCount", minimum=1, maximum=64),
        tip_radius_m=finite(item.get("tipRadiusM"), f"{label}.tipRadiusM", positive=True),
        hub_radius_m=finite(item.get("hubRadiusM"), f"{label}.hubRadiusM", positive=True),
        rpm=finite(item.get("rpm", 0.0), f"{label}.rpm", minimum=0.0),
        direction=_string(item.get("direction"), f"{label}.direction"),
        shaft_id=_string(item.get("shaftId"), f"{label}.shaftId"),
        pitch_control=str(item.get("pitchControl", "fixed")),
        collective_pitch_deg=finite(
            item.get("collectivePitchDeg", 0.0), f"{label}.collectivePitchDeg"
        ),
        group_id=_optional_string(item.get("groupId"), f"{label}.groupId"),
        geometry_ref=_optional_string(item.get("geometryRef"), f"{label}.geometryRef"),
        material_ref=_optional_string(item.get("materialRef"), f"{label}.materialRef"),
    )


def _shaft(value: Any, label: str) -> ShaftDeclaration:
    item = _mapping(value, label)
    return ShaftDeclaration(
        shaft_id=_string(item.get("shaftId"), f"{label}.shaftId"),
        kind=str(item.get("kind", "independent")),
        speed_rpm=_optional_number(item.get("speedRpm"), f"{label}.speedRpm"),
        linked_shaft_id=_optional_string(item.get("linkedShaftId"), f"{label}.linkedShaftId"),
        gear_ratio=_optional_number(item.get("gearRatio"), f"{label}.gearRatio"),
        mechanical_loss_fraction=finite(
            item.get("mechanicalLossFraction", 0.0), f"{label}.mechanicalLossFraction",
            minimum=0.0, maximum=0.999,
        ),
    )


def _schedule(value: Any, label: str) -> PitchSchedule:
    item = _mapping(value, label)
    raw_points = _sequence(item.get("points"), f"{label}.points")
    points: list[tuple[float, float]] = []
    for index, point in enumerate(raw_points):
        pair = _sequence(point, f"{label}.points[{index}]")
        if len(pair) != 2:
            raise PropulsorError(f"PITCH_POINT_NEEDS_TWO_VALUES:{label}[{index}]")
        points.append(
            (
                finite(pair[0], f"{label}.points[{index}][0]", minimum=0.0),
                finite(pair[1], f"{label}.points[{index}][1]"),
            )
        )
    return PitchSchedule(
        rotor_id=_string(item.get("rotorId"), f"{label}.rotorId"),
        points=tuple(points),
    )


def _frame(value: Any, label: str) -> InstallationFrame:
    item = _mapping(value or {}, label)
    origin_raw = _sequence(item.get("originM", (0.0, 0.0, 0.0)), f"{label}.originM")
    axis_raw = _sequence(item.get("axis", (1.0, 0.0, 0.0)), f"{label}.axis")
    if len(origin_raw) != 3 or len(axis_raw) != 3:
        raise PropulsorError(f"{label} needs three-component vectors")
    return InstallationFrame(
        origin_m=(
            finite(origin_raw[0], f"{label}.originM[0]"),
            finite(origin_raw[1], f"{label}.originM[1]"),
            finite(origin_raw[2], f"{label}.originM[2]"),
        ),
        axis=(
            finite(axis_raw[0], f"{label}.axis[0]"),
            finite(axis_raw[1], f"{label}.axis[1]"),
            finite(axis_raw[2], f"{label}.axis[2]"),
        ),
        body_ref=_optional_string(item.get("bodyRef"), f"{label}.bodyRef"),
    )


def architecture_from_payload(payload: Mapping[str, Any]) -> PropulsorArchitecture:
    """Build and validate a propulsor architecture from its canonical JSON."""

    document = _mapping(payload, "architecture")
    rotors = tuple(
        _rotor(item, f"rotors[{index}]")
        for index, item in enumerate(_sequence(document.get("rotors") or [], "rotors"))
    )
    shafts = tuple(
        _shaft(item, f"shafts[{index}]")
        for index, item in enumerate(_sequence(document.get("shafts") or [], "shafts"))
    )
    schedules = tuple(
        _schedule(item, f"pitchSchedules[{index}]")
        for index, item in enumerate(
            _sequence(document.get("pitchSchedules") or [], "pitchSchedules")
        )
    )
    spinner_item = document.get("spinner")
    spinner: SpinnerGeometry | None = None
    if spinner_item is not None:
        spinner_map = _mapping(spinner_item, "spinner")
        spinner = SpinnerGeometry(
            nose_radius_m=finite(
                spinner_map.get("noseRadiusM"), "spinner.noseRadiusM", positive=True
            ),
            nose_length_m=finite(
                spinner_map.get("noseLengthM"), "spinner.noseLengthM", positive=True
            ),
            hub_radius_m=finite(
                spinner_map.get("hubRadiusM"), "spinner.hubRadiusM", positive=True
            ),
            shaft_radius_m=finite(
                spinner_map.get("shaftRadiusM", 0.02), "spinner.shaftRadiusM", positive=True
            ),
        )
    frame = _frame(document.get("installationFrame"), "installationFrame")
    cyclic_item = document.get("cyclic")
    cyclic: CyclicPitchSeam | None = None
    if cyclic_item is not None:
        cyclic_map = _mapping(cyclic_item, "cyclic")
        cyclic = CyclicPitchSeam(
            amplitude_deg=finite(
                cyclic_map.get("amplitudeDeg"), "cyclic.amplitudeDeg", minimum=0.0
            ),
            phase_deg=finite(cyclic_map.get("phaseDeg", 0.0), "cyclic.phaseDeg"),
        )
    version = document.get("schemaVersion", SCHEMA_VERSION)
    if not isinstance(version, int) or isinstance(version, bool):
        raise PropulsorError("schemaVersion must be an integer")
    return PropulsorArchitecture(
        architecture_id=_string(document.get("architectureId"), "architectureId"),
        rotors=rotors,
        shafts=shafts,
        placement=str(document.get("placement", "tractor")),
        ducted=_boolean(document.get("ducted"), "ducted", False),
        stator=_boolean(document.get("stator"), "stator", False),
        duct_geometry_ref=_optional_string(document.get("ductGeometryRef"), "ductGeometryRef"),
        spinner=spinner,
        nacelle_radius_m=_optional_number(document.get("nacelleRadiusM"), "nacelleRadiusM"),
        installation_frame=frame,
        pitch_schedules=schedules,
        cyclic=cyclic,
        schema_version=version,
    )


def _as_architecture(
    value: PropulsorArchitecture | Mapping[str, Any],
) -> PropulsorArchitecture:
    if isinstance(value, PropulsorArchitecture):
        return value
    return architecture_from_payload(value)


def canonical_architecture(
    value: PropulsorArchitecture | Mapping[str, Any],
) -> dict[str, Any]:
    return _as_architecture(value).canonical_payload()


def architecture_hash(value: PropulsorArchitecture | Mapping[str, Any]) -> str:
    """Deterministic SHA-256 content hash of the full architecture."""

    import hashlib
    import json

    encoded = json.dumps(
        canonical_architecture(value), sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def architecture_provenance(
    value: PropulsorArchitecture | Mapping[str, Any],
) -> Provenance:
    """Schema identity/provenance for any result derived from this declaration.

    The architecture is a declaration, not a computed result; no solver output
    is fabricated. The returned provenance records the analytical/schema source,
    the software version, and the input hash.
    """

    architecture = _as_architecture(value)
    return analytical_provenance(
        "propulsors.architecture",
        {
            "architectureHash": architecture_hash(architecture),
            "softwareVersion": SOFTWARE_VERSION,
        },
        assumptions=("Canonical topology/rotor/shaft declaration only; no solver execution.",),
    )


__all__ = [
    "DIRECTIONS",
    "PITCH_CONTROLS",
    "PLACEMENTS",
    "SCHEMA_VERSION",
    "SHAFT_KINDS",
    "CyclicPitchSeam",
    "InstallationFrame",
    "PitchSchedule",
    "PropulsorArchitecture",
    "RotorDeclaration",
    "ShaftDeclaration",
    "SpinnerGeometry",
    "architecture_from_payload",
    "architecture_hash",
    "architecture_provenance",
    "canonical_architecture",
]
