"""Coefficient/derivative contract and result metadata for AIRFRAME 05.

AIRFRAME 05 consumes aerodynamics through the small structural
:class:`AerodynamicCoefficientProvider` protocol below. It never imports
VSPAERO/OpenVSP internals: an external-aerodynamics participant (AIRFRAME 04)
only has to return a :class:`DerivativeBundle` in these terms. Every derivative
field is optional so a provider can fail closed honestly by leaving coverage
absent instead of substituting a fabricated zero.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, fields
from enum import StrEnum
from math import cos, isfinite
from typing import Any, Protocol, runtime_checkable

from aeroworkbench_core.types import FidelityLevel, Provenance, ResultSource

from ..canonical import content_digest
from ..state import Controls
from ..units import Quantity, Vec3, require_dimension
from .errors import AeroCoefficientError

SOFTWARE_NAME = "aeroworkbench-airframe-trim"
SOFTWARE_VERSION = "1.0"

TRIM_RESULT_UNITS: tuple[tuple[str, str], ...] = (
    ("force", "N"),
    ("moment", "N.m"),
    ("length", "m"),
    ("area", "m2"),
    ("velocity", "m/s"),
    ("angle", "rad"),
    ("angular_rate", "rad/s"),
    ("density", "kg/m3"),
    ("pressure", "Pa"),
    ("mass", "kg"),
    ("dimensionless", "dimensionless"),
)


def finite(value: float, label: str) -> float:
    """Return ``value`` as a finite float, failing closed otherwise."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AeroCoefficientError(f"NONFINITE_VALUE:{label}")
    number = float(value)
    if not isfinite(number):
        raise AeroCoefficientError(f"NONFINITE_VALUE:{label}")
    return number


@dataclass(frozen=True, slots=True)
class SoftwareIdentity:
    name: str
    version: str

    def __post_init__(self) -> None:
        if not self.name.strip() or not self.version.strip():
            raise ValueError("SOFTWARE_IDENTITY_REQUIRED")

    def as_dict(self) -> dict[str, str]:
        return {"name": self.name, "version": self.version}


DEFAULT_SOFTWARE = SoftwareIdentity(SOFTWARE_NAME, SOFTWARE_VERSION)


@dataclass(frozen=True, slots=True)
class Validity:
    valid: bool
    notes: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {"valid": self.valid, "notes": list(self.notes)}


@dataclass(frozen=True, slots=True)
class ResultMeta:
    """Uniform result metadata: source/fidelity/units/validity/hash/provenance."""

    source: ResultSource
    fidelity: FidelityLevel
    software: SoftwareIdentity
    units: tuple[tuple[str, str], ...]
    validity: Validity
    input_hash: str
    provenance: Provenance

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": self.source.value,
            "fidelity": self.fidelity.value,
            "software": self.software.as_dict(),
            "units": {dimension: unit for dimension, unit in self.units},
            "validity": self.validity.as_dict(),
            "inputHash": self.input_hash,
            "provenance": {
                "source": self.provenance.source.value,
                "model": self.provenance.model,
                "modelVersion": self.provenance.model_version,
                "fidelity": self.provenance.fidelity.value,
                "inputsHash": self.provenance.inputs_hash,
                "assumptions": list(self.provenance.assumptions),
            },
        }


def result_meta(
    *,
    model: str,
    inputs: Mapping[str, Any],
    valid: bool,
    notes: tuple[str, ...] = (),
    assumptions: tuple[str, ...] = (),
    software: SoftwareIdentity = DEFAULT_SOFTWARE,
    source: ResultSource = ResultSource.ANALYTICAL,
    fidelity: FidelityLevel = FidelityLevel.ANALYTICAL,
) -> ResultMeta:
    provenance = Provenance.from_inputs(
        source=source,
        model=model,
        model_version=SOFTWARE_VERSION,
        fidelity=fidelity,
        inputs=dict(inputs),
        assumptions=assumptions,
    )
    return ResultMeta(
        source=source,
        fidelity=fidelity,
        software=software,
        units=TRIM_RESULT_UNITS,
        validity=Validity(valid=valid, notes=notes),
        input_hash=provenance.inputs_hash,
        provenance=provenance,
    )


@dataclass(frozen=True, slots=True)
class AeroReference:
    """Aerodynamic reference quantities and moment reference point."""

    frame: str
    area: Quantity
    span: Quantity
    chord: Quantity
    moment_reference: Vec3
    cg_mac_fraction: float | None = None

    def __post_init__(self) -> None:
        if not self.frame.strip():
            raise ValueError("AERO_REFERENCE_FRAME_REQUIRED")
        require_dimension(self.area, "area", "aeroReference.area")
        require_dimension(self.span, "length", "aeroReference.span")
        require_dimension(self.chord, "length", "aeroReference.chord")
        require_dimension(
            self.moment_reference, "length", "aeroReference.momentReference"
        )
        if (
            self.area.value_si <= 0
            or self.span.value_si <= 0
            or self.chord.value_si <= 0
        ):
            raise ValueError("NONPOSITIVE_AERO_REFERENCE")
        if self.cg_mac_fraction is not None:
            finite(self.cg_mac_fraction, "aeroReference.cgMacFraction")

    def as_dict(self) -> dict[str, Any]:
        return {
            "frame": self.frame,
            "area": self.area.canonical(),
            "span": self.span.canonical(),
            "chord": self.chord.canonical(),
            "momentReference": self.moment_reference.canonical(),
            "cgMacFraction": self.cg_mac_fraction,
        }


@dataclass(frozen=True, slots=True)
class AeroState:
    """One aerodynamic evaluation point: angles, rates, and surface deflections."""

    alpha: Quantity
    beta: Quantity = Quantity(0.0, "rad")
    velocity: Quantity = Quantity(0.0, "m/s")
    mach: float | None = None
    pitch_rate: Quantity = Quantity(0.0, "rad/s")
    roll_rate: Quantity = Quantity(0.0, "rad/s")
    yaw_rate: Quantity = Quantity(0.0, "rad/s")
    deflections: tuple[tuple[str, Quantity], ...] = ()
    controls: Controls = Controls()

    def __post_init__(self) -> None:
        require_dimension(self.alpha, "angle", "aeroState.alpha")
        require_dimension(self.beta, "angle", "aeroState.beta")
        require_dimension(self.velocity, "velocity", "aeroState.velocity")
        require_dimension(self.pitch_rate, "angular_rate", "aeroState.pitchRate")
        require_dimension(self.roll_rate, "angular_rate", "aeroState.rollRate")
        require_dimension(self.yaw_rate, "angular_rate", "aeroState.yawRate")
        for name, quantity in self.deflections:
            if not name.strip():
                raise ValueError("AERO_STATE_DEFLECTION_NAME_REQUIRED")
            require_dimension(quantity, "angle", f"aeroState.deflection.{name}")

    def deflection(self, name: str) -> float:
        for key, quantity in self.deflections:
            if key == name:
                return quantity.value_si
        return 0.0


@dataclass(frozen=True, slots=True)
class FlightCondition:
    """Atmosphere, weight, flight path, and thrust available for a trim point."""

    velocity: Quantity
    density: Quantity
    gravity: Quantity
    mass: Quantity
    gamma: Quantity = Quantity(0.0, "rad")
    load_factor: float | None = None
    bank: Quantity | None = None
    thrust: Quantity | None = None
    thrust_max: Quantity | None = None
    mach: float | None = None

    def __post_init__(self) -> None:
        require_dimension(self.velocity, "velocity", "condition.velocity")
        require_dimension(self.density, "density", "condition.density")
        require_dimension(self.gravity, "acceleration", "condition.gravity")
        require_dimension(self.mass, "mass", "condition.mass")
        require_dimension(self.gamma, "angle", "condition.gamma")
        if self.density.value_si < 0.0:
            raise ValueError("NEGATIVE_DENSITY")
        if self.gravity.value_si <= 0.0:
            raise ValueError("NONPOSITIVE_GRAVITY")
        if self.mass.value_si <= 0.0:
            raise ValueError("NONPOSITIVE_MASS")
        if self.bank is not None:
            require_dimension(self.bank, "angle", "condition.bank")
        for label, quantity in (
            ("thrust", self.thrust),
            ("thrustMax", self.thrust_max),
        ):
            if quantity is not None:
                require_dimension(quantity, "force", f"condition.{label}")
                if quantity.value_si < 0.0:
                    raise ValueError(f"NEGATIVE_{label.upper()}")
        if self.load_factor is not None:
            finite(self.load_factor, "condition.loadFactor")
            if self.load_factor <= 0.0:
                raise ValueError("NONPOSITIVE_LOAD_FACTOR")

    def dynamic_pressure(self) -> Quantity:
        speed = self.velocity.value_si
        return Quantity(0.5 * self.density.value_si * speed * speed, "Pa")

    def weight(self) -> Quantity:
        return Quantity(self.mass.value_si * self.gravity.value_si, "N")

    def resolved_load_factor(self) -> float:
        if self.load_factor is not None:
            return self.load_factor
        if self.bank is not None:
            value = cos(self.bank.value_si)
            if value <= 0.0:
                raise ValueError("BANK_ANGLE_TOO_LARGE")
            return 1.0 / value
        return 1.0

    def as_dict(self) -> dict[str, Any]:
        def q(quantity: Quantity | None) -> dict[str, object] | None:
            return None if quantity is None else quantity.canonical()

        return {
            "velocity": self.velocity.canonical(),
            "density": self.density.canonical(),
            "gravity": self.gravity.canonical(),
            "mass": self.mass.canonical(),
            "gamma": self.gamma.canonical(),
            "loadFactor": self.resolved_load_factor(),
            "bank": q(self.bank),
            "thrust": q(self.thrust),
            "thrustMax": q(self.thrust_max),
            "mach": self.mach,
        }


@dataclass(frozen=True, slots=True)
class AeroCoefficients:
    """Non-dimensional force and moment coefficients at one state."""

    c_lift: float
    c_drag: float
    c_pitch: float
    c_side: float = 0.0
    c_roll: float = 0.0
    c_yaw: float = 0.0

    def as_dict(self) -> dict[str, float]:
        return {
            "cLift": self.c_lift,
            "cDrag": self.c_drag,
            "cPitch": self.c_pitch,
            "cSide": self.c_side,
            "cRoll": self.c_roll,
            "cYaw": self.c_yaw,
        }


@dataclass(frozen=True, slots=True)
class LongitudinalDerivatives:
    """Longitudinal stability/control derivatives (per radian).

    ``*_q`` terms are per ``q c / (2 V)``; ``*_u`` terms are per ``u / V``.
    Every derivative is optional so missing coverage fails closed.
    """

    cl_0: float = 0.0
    cd_0: float = 0.0
    cm_0: float = 0.0
    cl_alpha: float | None = None
    cd_alpha: float | None = None
    cm_alpha: float | None = None
    cl_q: float | None = None
    cm_q: float | None = None
    cl_de: float | None = None
    cm_de: float | None = None
    cl_u: float | None = None
    cd_u: float | None = None
    cm_u: float | None = None

    def present(self) -> dict[str, bool]:
        return {
            field.name: getattr(self, field.name) is not None for field in fields(self)
        }

    def require(self, *names: str) -> dict[str, float]:
        missing = [name for name in names if getattr(self, name, None) is None]
        if missing:
            raise AeroCoefficientError(
                f"MISSING_LONGITUDINAL_DERIVATIVES:{','.join(missing)}"
            )
        return {name: finite(float(getattr(self, name)), name) for name in names}


@dataclass(frozen=True, slots=True)
class LateralDirectionalDerivatives:
    """Lateral-directional derivatives (per radian).

    ``cl_*`` are rolling-moment derivatives and ``cn_*`` yawing-moment
    derivatives. ``*_p``/``*_r`` are per ``p b / (2 V)`` / ``r b / (2 V)``.
    """

    cy_beta: float | None = None
    cl_beta: float | None = None
    cn_beta: float | None = None
    cy_p: float | None = None
    cy_r: float | None = None
    cl_p: float | None = None
    cl_r: float | None = None
    cn_p: float | None = None
    cn_r: float | None = None
    cl_da: float | None = None
    cl_dr: float | None = None
    cn_da: float | None = None
    cn_dr: float | None = None
    cy_da: float | None = None
    cy_dr: float | None = None

    def present(self) -> dict[str, bool]:
        return {
            field.name: getattr(self, field.name) is not None for field in fields(self)
        }

    def require(self, *names: str) -> dict[str, float]:
        missing = [name for name in names if getattr(self, name, None) is None]
        if missing:
            raise AeroCoefficientError(
                f"MISSING_LATERAL_DERIVATIVES:{','.join(missing)}"
            )
        return {name: finite(float(getattr(self, name)), name) for name in names}


@dataclass(frozen=True, slots=True)
class DerivativeBundle:
    """The coefficient/derivative result an external-aerodynamics provider returns."""

    longitudinal: LongitudinalDerivatives
    lateral_directional: LateralDirectionalDerivatives
    valid: bool = True
    notes: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "longitudinal": {
                field.name: getattr(self.longitudinal, field.name)
                for field in fields(self.longitudinal)
            },
            "lateralDirectional": {
                field.name: getattr(self.lateral_directional, field.name)
                for field in fields(self.lateral_directional)
            },
            "valid": self.valid,
            "notes": list(self.notes),
        }

    @property
    def content_hash(self) -> str:
        return content_digest(self.as_dict())


@runtime_checkable
class AerodynamicCoefficientProvider(Protocol):
    """Structural contract consumed by AIRFRAME 05 (the AIRFRAME 04 seam)."""

    @property
    def provider_id(self) -> str: ...

    def reference(self) -> AeroReference: ...

    def coefficients(self, state: AeroState) -> AeroCoefficients: ...

    def derivatives(self, state: AeroState) -> DerivativeBundle: ...


class TrimFidelity(StrEnum):
    """Which level produced a trim/stability result; screening is never native."""

    SCREENING = "screening"
    NATIVE_NONLINEAR = "native_nonlinear"


__all__ = [
    "AeroCoefficients",
    "AeroReference",
    "AeroState",
    "AerodynamicCoefficientProvider",
    "DEFAULT_SOFTWARE",
    "DerivativeBundle",
    "FlightCondition",
    "LateralDirectionalDerivatives",
    "LongitudinalDerivatives",
    "ResultMeta",
    "SOFTWARE_NAME",
    "SOFTWARE_VERSION",
    "SoftwareIdentity",
    "TRIM_RESULT_UNITS",
    "TrimFidelity",
    "Validity",
    "finite",
    "result_meta",
]
