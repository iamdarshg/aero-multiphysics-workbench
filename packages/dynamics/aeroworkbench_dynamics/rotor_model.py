"""Canonical rotating-assembly model derived from design-state inputs.

This is generic rotordynamics infrastructure. A canonical model carries shaft
segment geometry and material, disks/inertias, bearings/supports, rotating
frames and a speed range, optional gyroscopic settings, and balance/unbalance
definitions. It deliberately contains no application-specific blade counts,
blade-pass frequencies, or other domain forcing assumptions: forcing spectra
are declared separately by participants (see ``forcings``).

Inputs are normalized from either an explicit canonical form (``segments`` or
``shaft``, ``disks``, ``bearings``, ``material``) or the legacy scalar form
(``shaft_length_m``/``shaft_diameter_m``/``n_elements`` plus one optional
``disk`` and two end bearings) so existing participant inputs keep working.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from math import isfinite
from typing import Any

ANALYSES = ("campbell", "modal", "forced")
MAX_SEGMENTS = 64
MAX_SPEED_RPM = 200_000.0


class RotorModelError(ValueError):
    """Raised when a rotating-assembly model is not physically well formed."""


def _finite(
    value: Any,
    name: str,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
    positive: bool = False,
) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RotorModelError(f"{name} must be a number")
    result = float(value)
    if not isfinite(result):
        raise RotorModelError(f"{name} must be finite")
    if positive and result <= 0:
        raise RotorModelError(f"{name} must be positive")
    if minimum is not None and result < minimum:
        raise RotorModelError(f"{name} must be >= {minimum}")
    if maximum is not None and result > maximum:
        raise RotorModelError(f"{name} must be <= {maximum}")
    return result


def _integer(value: Any, name: str, *, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        if isinstance(value, float) and value.is_integer():
            value = int(value)
        else:
            raise RotorModelError(f"{name} must be an integer")
    if value < minimum or value > maximum:
        raise RotorModelError(f"{name} must be within {minimum}..{maximum}")
    return int(value)


def _flag(inputs: Mapping[str, Any], name: str, default: bool) -> bool:
    value = inputs.get(name, default)
    if not isinstance(value, bool):
        raise RotorModelError(f"{name} must be a boolean")
    return value


@dataclass(frozen=True, slots=True)
class MaterialSpec:
    """Isotropic shaft/disk material properties that drive the native model."""

    name: str
    youngs_modulus_pa: float
    shear_modulus_pa: float
    density_kg_m3: float
    poisson_ratio: float = 0.3

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise RotorModelError("material name is required")
        for label, value in (
            ("youngs_modulus_pa", self.youngs_modulus_pa),
            ("shear_modulus_pa", self.shear_modulus_pa),
            ("density_kg_m3", self.density_kg_m3),
        ):
            _finite(value, f"material.{label}", positive=True)
        poisson = _finite(self.poisson_ratio, "material.poisson_ratio")
        if not -1.0 < poisson < 0.5:
            raise RotorModelError("material.poisson_ratio out of physical range")

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "youngs_modulus_pa": self.youngs_modulus_pa,
            "shear_modulus_pa": self.shear_modulus_pa,
            "density_kg_m3": self.density_kg_m3,
            "poisson_ratio": self.poisson_ratio,
        }


STEEL = MaterialSpec(
    name="steel",
    youngs_modulus_pa=211e9,
    shear_modulus_pa=81.2e9,
    density_kg_m3=7810.0,
    poisson_ratio=0.3,
)
ALUMINIUM = MaterialSpec(
    name="aluminium-6061",
    youngs_modulus_pa=68.9e9,
    shear_modulus_pa=26.0e9,
    density_kg_m3=2700.0,
    poisson_ratio=0.33,
)

MATERIAL_REGISTRY: dict[str, MaterialSpec] = {
    STEEL.name: STEEL,
    "steel": STEEL,
    ALUMINIUM.name: ALUMINIUM,
    "aluminium": ALUMINIUM,
    "aluminum": ALUMINIUM,
}


@dataclass(frozen=True, slots=True)
class ShaftSegment:
    """One cylindrical shaft segment with optional bore."""

    length_m: float
    outer_diameter_m: float
    inner_diameter_m: float = 0.0

    def __post_init__(self) -> None:
        _finite(self.length_m, "segment.length_m", positive=True)
        _finite(self.outer_diameter_m, "segment.outer_diameter_m", positive=True)
        inner = _finite(self.inner_diameter_m, "segment.inner_diameter_m", minimum=0.0)
        if inner >= self.outer_diameter_m:
            raise RotorModelError("segment bore must be smaller than the outer diameter")

    def canonical_payload(self) -> dict[str, float]:
        return {
            "length_m": self.length_m,
            "outer_diameter_m": self.outer_diameter_m,
            "inner_diameter_m": self.inner_diameter_m,
        }


@dataclass(frozen=True, slots=True)
class DiskSpec:
    """One lumped disk/inertia attached at a rotor node."""

    position: int
    outer_diameter_m: float
    width_m: float
    inner_diameter_m: float

    def __post_init__(self) -> None:
        if self.position < 0:
            raise RotorModelError("disk.position must be non-negative")
        outer = _finite(self.outer_diameter_m, "disk.outer_diameter_m", positive=True)
        _finite(self.width_m, "disk.width_m", positive=True)
        inner = _finite(self.inner_diameter_m, "disk.inner_diameter_m", minimum=0.0)
        if inner >= outer:
            raise RotorModelError("disk bore must be smaller than the outer diameter")

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "position": self.position,
            "outer_diameter_m": self.outer_diameter_m,
            "width_m": self.width_m,
            "inner_diameter_m": self.inner_diameter_m,
        }


@dataclass(frozen=True, slots=True)
class BearingSpec:
    """One linear bearing/support with a 2x2 stiffness/damping pair."""

    node: int
    kxx: float
    kyy: float
    cxx: float
    cyy: float
    kxy: float = 0.0
    kyx: float = 0.0
    cxy: float = 0.0
    cyx: float = 0.0

    def __post_init__(self) -> None:
        if self.node < 0:
            raise RotorModelError("bearing.node must be non-negative")
        _finite(self.kxx, "bearing.kxx", positive=True)
        _finite(self.kyy, "bearing.kyy", positive=True)
        _finite(self.cxx, "bearing.cxx", minimum=0.0)
        _finite(self.cyy, "bearing.cyy", minimum=0.0)
        for label, value in (
            ("kxy", self.kxy),
            ("kyx", self.kyx),
            ("cxy", self.cxy),
            ("cyx", self.cyx),
        ):
            _finite(value, f"bearing.{label}")

    def canonical_payload(self) -> dict[str, float]:
        return {
            "node": self.node,
            "kxx": self.kxx,
            "kyy": self.kyy,
            "cxx": self.cxx,
            "cyy": self.cyy,
            "kxy": self.kxy,
            "kyx": self.kyx,
            "cxy": self.cxy,
            "cyx": self.cyx,
        }


@dataclass(frozen=True, slots=True)
class UnbalanceSpec:
    """One unbalance mass-eccentricity definition."""

    node: int
    magnitude_kg_m: float
    phase_deg: float = 0.0

    def __post_init__(self) -> None:
        if self.node < 0:
            raise RotorModelError("unbalance.node must be non-negative")
        _finite(self.magnitude_kg_m, "unbalance.magnitude_kg_m", minimum=0.0)
        _finite(self.phase_deg, "unbalance.phase_deg")

    def canonical_payload(self) -> dict[str, float]:
        return {
            "node": self.node,
            "magnitude_kg_m": self.magnitude_kg_m,
            "phase_deg": self.phase_deg,
        }


@dataclass(frozen=True, slots=True)
class RotorModel:
    """A fully specified, physically validated rotating assembly."""

    analysis: str
    material: MaterialSpec
    segments: tuple[ShaftSegment, ...]
    disks: tuple[DiskSpec, ...]
    bearings: tuple[BearingSpec, ...]
    speed_rpm: float
    max_speed_rpm: float
    gyroscopic: bool = True
    shear_effects: bool = True
    rotary_inertia: bool = True
    unbalance: UnbalanceSpec | None = None

    def __post_init__(self) -> None:
        if self.analysis not in ANALYSES:
            raise RotorModelError(f"analysis must be one of {sorted(ANALYSES)}")
        if not self.segments:
            raise RotorModelError("at least one shaft segment is required")
        if len(self.segments) > MAX_SEGMENTS:
            raise RotorModelError(f"at most {MAX_SEGMENTS} shaft segments are supported")
        if self.max_speed_rpm <= 0:
            raise RotorModelError("max_speed_rpm must be positive")
        if self.speed_rpm < 0 or self.speed_rpm > self.max_speed_rpm:
            raise RotorModelError("speed_rpm must lie within 0..max_speed_rpm")
        for disk in self.disks:
            if disk.position > len(self.segments):
                raise RotorModelError("disk.position exceeds the rotor node count")
        for bearing in self.bearings:
            if bearing.node > len(self.segments):
                raise RotorModelError("bearing.node exceeds the rotor node count")
        if self.unbalance is not None and self.unbalance.node > len(self.segments):
            raise RotorModelError("unbalance.node exceeds the rotor node count")

    @property
    def node_count(self) -> int:
        return len(self.segments) + 1

    @property
    def total_length_m(self) -> float:
        return sum(segment.length_m for segment in self.segments)

    @property
    def max_outer_diameter_m(self) -> float:
        return max(segment.outer_diameter_m for segment in self.segments)

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "analysis": self.analysis,
            "material": self.material.canonical_payload(),
            "segments": [segment.canonical_payload() for segment in self.segments],
            "disks": [disk.canonical_payload() for disk in self.disks],
            "bearings": [bearing.canonical_payload() for bearing in self.bearings],
            "speed_rpm": self.speed_rpm,
            "max_speed_rpm": self.max_speed_rpm,
            "gyroscopic": self.gyroscopic,
            "shear_effects": self.shear_effects,
            "rotary_inertia": self.rotary_inertia,
            "unbalance": self.unbalance.canonical_payload() if self.unbalance else None,
        }


def _material(inputs: Mapping[str, Any]) -> MaterialSpec:
    raw = inputs.get("material")
    if raw is not None:
        if isinstance(raw, str):
            try:
                return MATERIAL_REGISTRY[raw.lower()]
            except KeyError as exc:
                raise RotorModelError(f"unknown material:{raw}") from exc
        if not isinstance(raw, Mapping):
            raise RotorModelError("material must be a registry name or a mapping")
        name = str(raw.get("name", "custom"))
        provided = {
            key for key in ("youngs_modulus_pa", "shear_modulus_pa", "density_kg_m3") if key in raw
        }
        named = MATERIAL_REGISTRY.get(name.lower())
        if not provided and named is not None:
            return named
        missing = {
            "youngs_modulus_pa",
            "shear_modulus_pa",
            "density_kg_m3",
        } - provided
        if missing:
            raise RotorModelError(
                f"material {name} needs explicit {','.join(sorted(missing))}"
            )
        return MaterialSpec(
            name=name,
            youngs_modulus_pa=_finite(
                raw.get("youngs_modulus_pa"), "material.youngs_modulus_pa", positive=True
            ),
            shear_modulus_pa=_finite(
                raw.get("shear_modulus_pa"), "material.shear_modulus_pa", positive=True
            ),
            density_kg_m3=_finite(
                raw.get("density_kg_m3"), "material.density_kg_m3", positive=True
            ),
            poisson_ratio=_finite(
                raw.get("poisson_ratio", 0.3), "material.poisson_ratio"
            ),
        )
    provided = {
        key
        for key in ("youngs_modulus_pa", "shear_modulus_pa", "density_kg_m3")
        if key in inputs
    }
    if provided:
        missing = {
            "youngs_modulus_pa",
            "shear_modulus_pa",
            "density_kg_m3",
        } - provided
        if missing:
            raise RotorModelError(
                f"material needs explicit {','.join(sorted(missing))}"
            )
        return MaterialSpec(
            name=str(inputs.get("material_name", "custom")),
            youngs_modulus_pa=_finite(
                inputs.get("youngs_modulus_pa"), "youngs_modulus_pa", positive=True
            ),
            shear_modulus_pa=_finite(
                inputs.get("shear_modulus_pa"), "shear_modulus_pa", positive=True
            ),
            density_kg_m3=_finite(
                inputs.get("density_kg_m3"), "density_kg_m3", positive=True
            ),
        )
    return STEEL


def _segments(inputs: Mapping[str, Any]) -> tuple[ShaftSegment, ...]:
    raw = inputs.get("segments")
    if raw is None:
        raw = inputs.get("shaft")
    if raw is not None:
        if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)) or not raw:
            raise RotorModelError("segments must be a non-empty sequence")
        segments: list[ShaftSegment] = []
        for entry in raw:
            if not isinstance(entry, Mapping):
                raise RotorModelError("each shaft segment must be a mapping")
            segments.append(
                ShaftSegment(
                    length_m=_finite(entry.get("length_m"), "segment.length_m", positive=True),
                    outer_diameter_m=_finite(
                        entry.get("outer_diameter_m"),
                        "segment.outer_diameter_m",
                        positive=True,
                    ),
                    inner_diameter_m=_finite(
                        entry.get("inner_diameter_m", 0.0),
                        "segment.inner_diameter_m",
                        minimum=0.0,
                    ),
                )
            )
        return tuple(segments)
    length = _finite(inputs.get("shaft_length_m"), "shaft_length_m", positive=True)
    diameter = _finite(inputs.get("shaft_diameter_m"), "shaft_diameter_m", positive=True)
    n_elements = _integer(inputs.get("n_elements"), "n_elements", minimum=2, maximum=MAX_SEGMENTS)
    inner = _finite(
        inputs.get("shaft_inner_diameter_m", 0.0),
        "shaft_inner_diameter_m",
        minimum=0.0,
    )
    if inner >= diameter:
        raise RotorModelError("shaft bore must be smaller than the outer diameter")
    element_length = length / n_elements
    return tuple(
        ShaftSegment(element_length, diameter, inner) for _ in range(n_elements)
    )


def _disks(
    inputs: Mapping[str, Any], segments: tuple[ShaftSegment, ...]
) -> tuple[DiskSpec, ...]:
    raw = inputs.get("disks")
    if raw is None:
        single = inputs.get("disk")
        raw = [] if single is None else [single]
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        raise RotorModelError("disks must be a sequence")
    disks: list[DiskSpec] = []
    for entry in raw:
        if not isinstance(entry, Mapping):
            raise RotorModelError("each disk must be a mapping")
        position = _integer(
            entry.get("position"), "disk.position", minimum=0, maximum=len(segments)
        )
        neighbours = [
            segments[index].outer_diameter_m
            for index in (position - 1, position)
            if 0 <= index < len(segments)
        ]
        fallback_inner = max(neighbours)
        disks.append(
            DiskSpec(
                position=position,
                outer_diameter_m=_finite(
                    entry.get("outer_diameter_m"), "disk.outer_diameter_m", positive=True
                ),
                width_m=_finite(entry.get("width_m"), "disk.width_m", positive=True),
                inner_diameter_m=_finite(
                    entry.get("inner_diameter_m", fallback_inner),
                    "disk.inner_diameter_m",
                    minimum=0.0,
                ),
            )
        )
    return tuple(disks)


def _bearings(
    inputs: Mapping[str, Any], segments: tuple[ShaftSegment, ...]
) -> tuple[BearingSpec, ...]:
    raw = inputs.get("bearings")
    if raw is None:
        stiffness = _finite(
            inputs.get("bearing_stiffness_n_m"), "bearing_stiffness_n_m", positive=True
        )
        damping = _finite(
            inputs.get("bearing_damping_n_s_m", 1000.0),
            "bearing_damping_n_s_m",
            minimum=0.0,
        )
        ends = (0, len(segments))
        return tuple(
            BearingSpec(
                node=node, kxx=stiffness, kyy=stiffness, cxx=damping, cyy=damping
            )
            for node in ends
        )
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)) or not raw:
        raise RotorModelError("bearings must be a non-empty sequence")
    bearings: list[BearingSpec] = []
    for entry in raw:
        if not isinstance(entry, Mapping):
            raise RotorModelError("each bearing must be a mapping")
        kxx = _finite(entry.get("kxx"), "bearing.kxx", positive=True)
        kyy = _finite(entry.get("kyy", kxx), "bearing.kyy", positive=True)
        cxx = _finite(entry.get("cxx", 0.0), "bearing.cxx", minimum=0.0)
        cyy = _finite(entry.get("cyy", cxx), "bearing.cyy", minimum=0.0)
        bearings.append(
            BearingSpec(
                node=_integer(
                    entry.get("node"), "bearing.node", minimum=0, maximum=len(segments)
                ),
                kxx=kxx,
                kyy=kyy,
                cxx=cxx,
                cyy=cyy,
                kxy=_finite(entry.get("kxy", 0.0), "bearing.kxy"),
                kyx=_finite(entry.get("kyx", 0.0), "bearing.kyx"),
                cxy=_finite(entry.get("cxy", 0.0), "bearing.cxy"),
                cyx=_finite(entry.get("cyx", 0.0), "bearing.cyx"),
            )
        )
    return tuple(bearings)


def _unbalance(inputs: Mapping[str, Any], n_segments: int) -> UnbalanceSpec | None:
    raw = inputs.get("unbalance")
    if raw is None:
        return None
    if not isinstance(raw, Mapping):
        raise RotorModelError("unbalance must be a mapping")
    node = _integer(raw.get("node", 1), "unbalance.node", minimum=0, maximum=n_segments)
    magnitude = raw.get("magnitude_kg_m", raw.get("unbalance_magnitude", 1e-4))
    return UnbalanceSpec(
        node=node,
        magnitude_kg_m=_finite(magnitude, "unbalance.magnitude_kg_m", minimum=0.0),
        phase_deg=_finite(raw.get("phase_deg", 0.0), "unbalance.phase_deg"),
    )


def normalize_rotor_model(inputs: Mapping[str, Any]) -> RotorModel:
    """Validate raw participant inputs and return the canonical rotor model."""

    analysis = inputs.get("analysis")
    if analysis not in ANALYSES:
        raise RotorModelError(f"analysis must be one of {sorted(ANALYSES)}")
    material = _material(inputs)
    segments = _segments(inputs)
    disks = _disks(inputs, segments)
    bearings = _bearings(inputs, segments)
    gyroscopic = _flag(inputs, "gyroscopic", True)
    shear_effects = _flag(inputs, "shear_effects", True)
    rotary_inertia = _flag(inputs, "rotary_inertia", True)
    unbalance = _unbalance(inputs, len(segments))
    if analysis == "campbell":
        max_speed = _finite(
            inputs.get("max_speed_rpm"),
            "max_speed_rpm",
            positive=True,
            maximum=MAX_SPEED_RPM,
        )
        speed = 0.0
    else:
        max_speed = _finite(
            inputs.get("speed_rpm"), "speed_rpm", minimum=0.0, maximum=MAX_SPEED_RPM
        )
        speed = max_speed
    return RotorModel(
        analysis=str(analysis),
        material=material,
        segments=segments,
        disks=disks,
        bearings=bearings,
        speed_rpm=speed,
        max_speed_rpm=max_speed,
        gyroscopic=gyroscopic,
        shear_effects=shear_effects,
        rotary_inertia=rotary_inertia,
        unbalance=unbalance,
    )
