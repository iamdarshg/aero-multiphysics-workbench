"""Typed unit-safe components of a canonical flying-vehicle state.

These dataclasses carry declared frames, SI-normalizable units, and explicit
sign/axes conventions. They contain no aerodynamic equations: this module is the
generic physical contract later AIRFRAME/VEHICLE-SYSTEMS issues consume.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite, sqrt

from .units import Quantity, Vec3, require_dimension

SIGN_CONVENTIONS: tuple[str, ...] = (
    "body_axes_aerodynamic",
    "stability_axes_aerodynamic",
    "structural_body_axes",
)

QUATERNION_TOLERANCE = 1e-9


def _angle(quantity: Quantity, label: str) -> None:
    require_dimension(quantity, "angle", label)


def _optional_angle(quantity: Quantity | None, label: str) -> None:
    if quantity is not None:
        _angle(quantity, label)


def _named_angles(
    items: tuple[tuple[str, Quantity], ...], label: str
) -> dict[str, object]:
    names = [name for name, _ in items]
    if len(names) != len(set(names)):
        raise ValueError(f"DUPLICATE_ANGLE_NAME:{label}")
    for name, quantity in items:
        if not name.strip():
            raise ValueError(f"ANGLE_NAME_REQUIRED:{label}")
        _angle(quantity, f"{label}.{name}")
    return {name: quantity.canonical() for name, quantity in sorted(items)}


@dataclass(frozen=True, slots=True)
class InertiaTensor:
    """Symmetric inertia tensor in a declared body frame."""

    ixx: Quantity
    iyy: Quantity
    izz: Quantity
    ixy: Quantity
    ixz: Quantity
    iyz: Quantity
    frame: str

    def __post_init__(self) -> None:
        for name, quantity in (
            ("ixx", self.ixx),
            ("iyy", self.iyy),
            ("izz", self.izz),
            ("ixy", self.ixy),
            ("ixz", self.ixz),
            ("iyz", self.iyz),
        ):
            require_dimension(quantity, "moment_of_inertia", name)
        for name, quantity in (("ixx", self.ixx), ("iyy", self.iyy), ("izz", self.izz)):
            if quantity.value_si <= 0:
                raise ValueError(f"NONPOSITIVE_PRINCIPAL_MOMENT:{name}")
        if not self.frame.strip():
            raise ValueError("INERTIA_FRAME_REQUIRED")

    def canonical(self) -> dict[str, object]:
        return {
            "ixx": self.ixx.canonical(),
            "iyy": self.iyy.canonical(),
            "izz": self.izz.canonical(),
            "ixy": self.ixy.canonical(),
            "ixz": self.ixz.canonical(),
            "iyz": self.iyz.canonical(),
            "dimension": "moment_of_inertia",
            "frame": self.frame,
        }


@dataclass(frozen=True, slots=True)
class MassProperties:
    """Mass, centre of gravity, and full inertia tensor."""

    mass: Quantity
    cg: Vec3
    inertia: InertiaTensor

    def __post_init__(self) -> None:
        require_dimension(self.mass, "mass", "mass")
        require_dimension(self.cg, "length", "cg")
        if self.mass.value_si <= 0:
            raise ValueError("NONPOSITIVE_MASS")

    def canonical(self) -> dict[str, object]:
        return {
            "mass": self.mass.canonical(),
            "cg": self.cg.canonical(),
            "inertia": self.inertia.canonical(),
        }


@dataclass(frozen=True, slots=True)
class Attitude:
    """Orientation declared by an explicit convention between two frames."""

    from_frame: str
    to_frame: str
    convention: str
    angles: tuple[tuple[str, Quantity], ...] = ()
    quaternion: tuple[float, float, float, float] | None = None

    def __post_init__(self) -> None:
        if not self.from_frame.strip() or not self.to_frame.strip():
            raise ValueError("ATTITUDE_FRAMES_REQUIRED")
        if self.from_frame == self.to_frame:
            raise ValueError("ATTITUDE_FRAMES_MUST_DIFFER")
        if self.convention == "euler_321":
            if self.quaternion is not None:
                raise ValueError("ATTITUDE_CONVENTION_MIXED")
            names = {name for name, _ in self.angles}
            if names != {"yaw", "pitch", "roll"}:
                raise ValueError("ATTITUDE_EULER_ANGLES_INCOMPLETE")
            for name, quantity in self.angles:
                _angle(quantity, f"attitude.{name}")
        elif self.convention == "quaternion":
            if self.angles:
                raise ValueError("ATTITUDE_CONVENTION_MIXED")
            if self.quaternion is None or len(self.quaternion) != 4:
                raise ValueError("ATTITUDE_QUATERNION_REQUIRED")
            norm = sqrt(sum(component * component for component in self.quaternion))
            if abs(norm - 1.0) > QUATERNION_TOLERANCE:
                raise ValueError("QUATERNION_NOT_UNIT")
            for component in self.quaternion:
                if not isfinite(component):
                    raise ValueError("NONFINITE_QUATERNION")
        else:
            raise ValueError(f"UNKNOWN_ATTITUDE_CONVENTION:{self.convention}")

    def canonical(self) -> dict[str, object]:
        return {
            "fromFrame": self.from_frame,
            "toFrame": self.to_frame,
            "convention": self.convention,
            "angles": _named_angles(self.angles, "attitude") if self.angles else None,
            "quaternion": None if self.quaternion is None else list(self.quaternion),
        }


@dataclass(frozen=True, slots=True)
class AtmosphereReference:
    """Atmosphere and gravity reference values for a flight state.

    The reference is a declared set of constants or a model identifier; this
    contract never evaluates or fabricates an atmosphere model.
    """

    model: str
    reference_altitude: Quantity | None = None
    density: Quantity | None = None
    temperature: Quantity | None = None
    pressure: Quantity | None = None
    speed_of_sound: Quantity | None = None
    gas_constant: Quantity | None = None
    gravity: Quantity | None = None

    def __post_init__(self) -> None:
        if not self.model.strip():
            raise ValueError("ATMOSPHERE_MODEL_REQUIRED")
        expected = (
            ("referenceAltitude", self.reference_altitude, "length"),
            ("density", self.density, "density"),
            ("temperature", self.temperature, "temperature"),
            ("pressure", self.pressure, "pressure"),
            ("speedOfSound", self.speed_of_sound, "velocity"),
            ("gasConstant", self.gas_constant, "specific_gas_constant"),
            ("gravity", self.gravity, "acceleration"),
        )
        for label, quantity, dimension in expected:
            if quantity is not None:
                require_dimension(quantity, dimension, label)
        if self.density is not None and self.density.value_si < 0:
            raise ValueError("NEGATIVE_ATMOSPHERE_DENSITY")
        if self.speed_of_sound is not None and self.speed_of_sound.value_si <= 0:
            raise ValueError("NONPOSITIVE_SPEED_OF_SOUND")

    def canonical(self) -> dict[str, object]:
        def q(quantity: Quantity | None) -> dict[str, object] | None:
            return None if quantity is None else quantity.canonical()

        return {
            "model": self.model,
            "referenceAltitude": q(self.reference_altitude),
            "density": q(self.density),
            "temperature": q(self.temperature),
            "pressure": q(self.pressure),
            "speedOfSound": q(self.speed_of_sound),
            "gasConstant": q(self.gas_constant),
            "gravity": q(self.gravity),
        }


@dataclass(frozen=True, slots=True)
class FlightQuantities:
    """Unit-safe flight state: altitude, airspeeds, Mach, alpha/beta, loads."""

    altitude: Quantity | None = None
    calibrated_airspeed: Quantity | None = None
    equivalent_airspeed: Quantity | None = None
    true_airspeed: Quantity | None = None
    mach: Quantity | None = None
    dynamic_pressure: Quantity | None = None
    angle_of_attack: Quantity | None = None
    sideslip: Quantity | None = None
    load_factor: Quantity | None = None
    reynolds: Quantity | None = None

    def __post_init__(self) -> None:
        for label, quantity in (
            ("altitude", self.altitude),
            ("calibratedAirspeed", self.calibrated_airspeed),
            ("equivalentAirspeed", self.equivalent_airspeed),
            ("trueAirspeed", self.true_airspeed),
        ):
            if quantity is None:
                continue
            dimension = "length" if label == "altitude" else "velocity"
            require_dimension(quantity, dimension, label)
        for label, quantity in (
            ("mach", self.mach),
            ("loadFactor", self.load_factor),
            ("reynolds", self.reynolds),
        ):
            if quantity is not None:
                require_dimension(quantity, "dimensionless", label)
        if self.dynamic_pressure is not None:
            require_dimension(self.dynamic_pressure, "pressure", "dynamicPressure")
        _optional_angle(self.angle_of_attack, "angleOfAttack")
        _optional_angle(self.sideslip, "sideslip")

    def canonical(self) -> dict[str, object]:
        def q(quantity: Quantity | None) -> dict[str, object] | None:
            return None if quantity is None else quantity.canonical()

        return {
            "altitude": q(self.altitude),
            "airspeed": {
                "calibrated": q(self.calibrated_airspeed),
                "equivalent": q(self.equivalent_airspeed),
                "true": q(self.true_airspeed),
            },
            "mach": q(self.mach),
            "dynamicPressure": q(self.dynamic_pressure),
            "angleOfAttack": q(self.angle_of_attack),
            "sideslip": q(self.sideslip),
            "loadFactor": q(self.load_factor),
            "reynolds": q(self.reynolds),
        }


@dataclass(frozen=True, slots=True)
class ReferenceGeometry:
    """Aerodynamic reference quantities and reference point (generic platform)."""

    frame: str
    area: Quantity | None = None
    span: Quantity | None = None
    chord: Quantity | None = None
    aerodynamic_reference_point: Vec3 | None = None

    def __post_init__(self) -> None:
        if not self.frame.strip():
            raise ValueError("REFERENCE_FRAME_REQUIRED")
        if self.area is not None:
            require_dimension(self.area, "area", "referenceArea")
        for label, quantity in (("span", self.span), ("chord", self.chord)):
            if quantity is not None:
                require_dimension(quantity, "length", f"reference.{label}")
        if self.aerodynamic_reference_point is not None:
            require_dimension(
                self.aerodynamic_reference_point, "length", "aerodynamicReferencePoint"
            )

    def canonical(self) -> dict[str, object]:
        def q(quantity: Quantity | None) -> dict[str, object] | None:
            return None if quantity is None else quantity.canonical()

        return {
            "frame": self.frame,
            "area": q(self.area),
            "span": q(self.span),
            "chord": q(self.chord),
            "aerodynamicReferencePoint": (
                None
                if self.aerodynamic_reference_point is None
                else self.aerodynamic_reference_point.canonical()
            ),
        }


@dataclass(frozen=True, slots=True)
class Controls:
    """Generic controls: surfaces, throttle, RPM, collective, cyclic, tilt."""

    surface_deflections: tuple[tuple[str, Quantity], ...] = ()
    throttle: Quantity | None = None
    rpm: Quantity | None = None
    collective: Quantity | None = None
    cyclic: tuple[tuple[str, Quantity], ...] = ()
    tilt: tuple[tuple[str, Quantity], ...] = ()

    def __post_init__(self) -> None:
        for label, items in (
            ("surfaceDeflections", self.surface_deflections),
            ("cyclic", self.cyclic),
            ("tilt", self.tilt),
        ):
            _named_angles(items, label)
        if self.throttle is not None:
            require_dimension(self.throttle, "dimensionless", "throttle")
            if not 0.0 <= self.throttle.value_si <= 1.0:
                raise ValueError("THROTTLE_OUT_OF_RANGE")
        if self.rpm is not None:
            require_dimension(self.rpm, "rotational_speed", "rpm")
        _optional_angle(self.collective, "collective")

    def canonical(self) -> dict[str, object]:
        return {
            "surfaceDeflections": _named_angles(self.surface_deflections, "surfaceDeflections"),
            "throttle": None if self.throttle is None else self.throttle.canonical(),
            "rpm": None if self.rpm is None else self.rpm.canonical(),
            "collective": None if self.collective is None else self.collective.canonical(),
            "cyclic": _named_angles(self.cyclic, "cyclic"),
            "tilt": _named_angles(self.tilt, "tilt"),
        }


@dataclass(frozen=True, slots=True)
class ForceMoment:
    """A six-axis load with explicit axes, sign, and moment reference point."""

    force: Vec3
    moment: Vec3
    reference_point: Vec3
    axes_frame: str
    sign_convention: str

    def __post_init__(self) -> None:
        require_dimension(self.force, "force", "force")
        require_dimension(self.moment, "moment", "moment")
        require_dimension(self.reference_point, "length", "referencePoint")
        if not self.axes_frame.strip():
            raise ValueError("LOADS_AXES_FRAME_REQUIRED")
        if self.sign_convention not in SIGN_CONVENTIONS:
            raise ValueError(f"UNKNOWN_SIGN_CONVENTION:{self.sign_convention}")

    def canonical(self) -> dict[str, object]:
        return {
            "force": self.force.canonical(),
            "moment": self.moment.canonical(),
            "referencePoint": self.reference_point.canonical(),
            "axesFrame": self.axes_frame,
            "signConvention": self.sign_convention,
        }


@dataclass(frozen=True, slots=True)
class FlightState:
    """Rigid-body motion plus the unit-safe flight quantities and atmosphere."""

    position: Vec3
    attitude: Attitude
    velocity: Vec3
    angular_rates: Vec3
    flight: FlightQuantities
    atmosphere: AtmosphereReference

    def __post_init__(self) -> None:
        require_dimension(self.position, "length", "position")
        require_dimension(self.velocity, "velocity", "velocity")
        require_dimension(self.angular_rates, "angular_rate", "angularRates")

    def canonical(self) -> dict[str, object]:
        return {
            "position": self.position.canonical(),
            "attitude": self.attitude.canonical(),
            "velocity": self.velocity.canonical(),
            "angularRates": self.angular_rates.canonical(),
            "flight": self.flight.canonical(),
            "atmosphere": self.atmosphere.canonical(),
        }
