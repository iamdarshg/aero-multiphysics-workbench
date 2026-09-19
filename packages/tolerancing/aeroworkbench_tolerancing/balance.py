"""Generic rotating-body balance and mass-property variation contracts.

The centre of mass, static/dynamic imbalance, correction planes, allowable
residual imbalance, and manufacturing mass scatter are all typed and
hashable. Residual imbalance is exposed as a synchronous forcing line so it can
be fed into the existing rotordynamics/forced-response layer without the
balance layer inventing any frequency.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Any

from aeroworkbench_dynamics.forcings import ForcingLine

from .contracts import (
    DistributionKind,
    ResultEnvelope,
    build_envelope,
)
from .errors import BalanceError

__all__ = [
    "BalanceAssessment",
    "BalanceScatterResult",
    "BalanceSpec",
    "CorrectionPlane",
    "ImbalanceState",
    "MassElement",
    "MassProperties",
    "MassScatterElement",
    "assess_balance",
    "assess_imbalance",
    "balance_scatter",
    "compute_mass_properties",
    "residual_unbalance_forcing",
]

MAX_BALANCE_SAMPLES = 200_000
DEFAULT_BALANCE_SAMPLES = 10_000


@dataclass(frozen=True, slots=True)
class MassElement:
    """A point mass at a location, in SI units."""

    id: str
    mass_kg: float
    x_m: float = 0.0
    y_m: float = 0.0
    z_m: float = 0.0

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise BalanceError("MASS_ELEMENT_ID_REQUIRED")
        for label, value in (
            ("mass_kg", self.mass_kg),
            ("x_m", self.x_m),
            ("y_m", self.y_m),
            ("z_m", self.z_m),
        ):
            if not math.isfinite(value):
                raise BalanceError(f"NONFINITE_{label.upper()}:{self.id}")
        if self.mass_kg < 0:
            raise BalanceError(f"NEGATIVE_MASS:{self.id}")

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "massKg": self.mass_kg,
            "xM": self.x_m,
            "yM": self.y_m,
            "zM": self.z_m,
        }


@dataclass(frozen=True, slots=True)
class MassProperties:
    """Mass, centre of mass, and point-mass inertia tensor about the COM."""

    mass_kg: float
    center_of_mass_m: tuple[float, float, float]
    inertia_kg_m2: tuple[float, ...]
    envelope: ResultEnvelope

    def as_dict(self) -> dict[str, Any]:
        return {
            "massKg": self.mass_kg,
            "centerOfMassM": list(self.center_of_mass_m),
            "inertiaKgM2": list(self.inertia_kg_m2),
            "envelope": self.envelope.as_dict(),
        }


@dataclass(frozen=True, slots=True)
class ImbalanceState:
    """Static and dynamic imbalance derived from a mass-element set."""

    static_magnitude_kg_m: float
    static_angle_rad: float
    dynamic_magnitude_kg_m2: float
    dynamic_angle_rad: float
    mass_properties: MassProperties
    envelope: ResultEnvelope

    def as_dict(self) -> dict[str, Any]:
        return {
            "staticMagnitudeKgM": self.static_magnitude_kg_m,
            "staticAngleRad": self.static_angle_rad,
            "dynamicMagnitudeKgM2": self.dynamic_magnitude_kg_m2,
            "dynamicAngleRad": self.dynamic_angle_rad,
            "massProperties": self.mass_properties.as_dict(),
            "envelope": self.envelope.as_dict(),
        }


@dataclass(frozen=True, slots=True)
class CorrectionPlane:
    """A plane in which balance correction mass may be added or removed."""

    id: str
    axial_location_m: float
    radius_m: float

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise BalanceError("CORRECTION_PLANE_ID_REQUIRED")
        if not math.isfinite(self.axial_location_m) or not math.isfinite(self.radius_m):
            raise BalanceError(f"NONFINITE_CORRECTION_PLANE:{self.id}")
        if self.radius_m <= 0:
            raise BalanceError(f"CORRECTION_PLANE_RADIUS_MUST_BE_POSITIVE:{self.id}")

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "axialLocationM": self.axial_location_m,
            "radiusM": self.radius_m,
        }


@dataclass(frozen=True, slots=True)
class BalanceSpec:
    """Allowable residual imbalance and the planes available for correction."""

    spec_id: str
    correction_planes: tuple[CorrectionPlane, ...]
    allowable_residual_kg_m: float

    def __post_init__(self) -> None:
        if not self.spec_id.strip():
            raise BalanceError("BALANCE_SPEC_ID_REQUIRED")
        if not math.isfinite(self.allowable_residual_kg_m) or self.allowable_residual_kg_m <= 0:
            raise BalanceError(f"ALLOWABLE_RESIDUAL_MUST_BE_POSITIVE:{self.spec_id}")
        seen: set[str] = set()
        for plane in self.correction_planes:
            if plane.id in seen:
                raise BalanceError(f"DUPLICATE_CORRECTION_PLANE:{self.spec_id}:{plane.id}")
            seen.add(plane.id)

    def inputs_payload(self) -> dict[str, Any]:
        return {
            "specId": self.spec_id,
            "correctionPlanes": [plane.as_dict() for plane in self.correction_planes],
            "allowableResidualKgM": self.allowable_residual_kg_m,
        }


@dataclass(frozen=True, slots=True)
class BalanceAssessment:
    """Residual imbalance compared with the allowable limit."""

    spec_id: str
    residual_kg_m: float
    allowable_kg_m: float
    satisfied: bool
    static_magnitude_kg_m: float
    dynamic_magnitude_kg_m2: float
    envelope: ResultEnvelope

    def as_dict(self) -> dict[str, Any]:
        return {
            "specId": self.spec_id,
            "residualKgM": self.residual_kg_m,
            "allowableKgM": self.allowable_kg_m,
            "satisfied": self.satisfied,
            "staticMagnitudeKgM": self.static_magnitude_kg_m,
            "dynamicMagnitudeKgM2": self.dynamic_magnitude_kg_m2,
            "envelope": self.envelope.as_dict(),
        }


@dataclass(frozen=True, slots=True)
class MassScatterElement:
    """A mass element with a manufacturing mass tolerance."""

    id: str
    mass_kg: float
    mass_tolerance_kg: float
    x_m: float = 0.0
    y_m: float = 0.0
    z_m: float = 0.0
    distribution: DistributionKind = DistributionKind.NORMAL

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise BalanceError("SCATTER_ELEMENT_ID_REQUIRED")
        if not math.isfinite(self.mass_kg) or self.mass_kg <= 0:
            raise BalanceError(f"SCATTER_MASS_MUST_BE_POSITIVE:{self.id}")
        if not math.isfinite(self.mass_tolerance_kg) or self.mass_tolerance_kg < 0:
            raise BalanceError(f"SCATTER_TOLERANCE_MUST_BE_NONNEGATIVE:{self.id}")
        for label, value in (("x_m", self.x_m), ("y_m", self.y_m), ("z_m", self.z_m)):
            if not math.isfinite(value):
                raise BalanceError(f"NONFINITE_{label.upper()}:{self.id}")

    def sample_mass(self, rng: random.Random) -> float:
        """Draw a deterministic perturbed mass from the declared distribution."""

        low = self.mass_kg - self.mass_tolerance_kg
        high = self.mass_kg + self.mass_tolerance_kg
        if self.distribution is DistributionKind.CONSTANT or self.mass_tolerance_kg == 0.0:
            return self.mass_kg
        if self.distribution is DistributionKind.UNIFORM:
            return rng.uniform(low, high)
        if self.distribution is DistributionKind.TRIANGULAR:
            return rng.triangular(low, high, self.mass_kg)
        sigma = self.mass_tolerance_kg / 3.0
        return min(max(rng.gauss(self.mass_kg, sigma), low), high)


@dataclass(frozen=True, slots=True)
class BalanceScatterResult:
    """Manufacturing mass scatter propagated into residual imbalance."""

    spec_id: str
    samples: int
    seed: int
    mean_residual_kg_m: float
    std_residual_kg_m: float
    max_residual_kg_m: float
    yield_fraction: float
    ppm: float
    envelope: ResultEnvelope

    def as_dict(self) -> dict[str, Any]:
        return {
            "specId": self.spec_id,
            "samples": self.samples,
            "seed": self.seed,
            "meanResidualKgM": self.mean_residual_kg_m,
            "stdResidualKgM": self.std_residual_kg_m,
            "maxResidualKgM": self.max_residual_kg_m,
            "yieldFraction": self.yield_fraction,
            "ppm": self.ppm,
            "envelope": self.envelope.as_dict(),
        }


def _sums(elements: tuple[MassElement, ...]) -> tuple[float, float, float, float]:
    mass = 0.0
    mx = 0.0
    my = 0.0
    mz = 0.0
    for element in elements:
        mass += element.mass_kg
        mx += element.mass_kg * element.x_m
        my += element.mass_kg * element.y_m
        mz += element.mass_kg * element.z_m
    return mass, mx, my, mz


def compute_mass_properties(elements: tuple[MassElement, ...]) -> MassProperties:
    """Point-mass mass properties; fails closed when no mass is declared."""

    if not elements:
        raise BalanceError("MASS_ELEMENTS_REQUIRED")
    mass, mx, my, mz = _sums(elements)
    if mass <= 0:
        raise BalanceError("TOTAL_MASS_MUST_BE_POSITIVE")
    com = (mx / mass, my / mass, mz / mass)
    ixx = iyy = izz = ixy = ixz = iyz = 0.0
    for element in elements:
        dx = element.x_m - com[0]
        dy = element.y_m - com[1]
        dz = element.z_m - com[2]
        ixx += element.mass_kg * (dy * dy + dz * dz)
        iyy += element.mass_kg * (dx * dx + dz * dz)
        izz += element.mass_kg * (dx * dx + dy * dy)
        ixy -= element.mass_kg * dx * dy
        ixz -= element.mass_kg * dx * dz
        iyz -= element.mass_kg * dy * dz
    envelope = build_envelope(
        model="advphys10-mass-properties",
        inputs={"elements": [element.as_dict() for element in elements]},
        unit="kg",
        assumptions=(
            "each declared element is a rigid point mass",
            "inertia tensor is computed about the mass centre",
        ),
    )
    return MassProperties(
        mass_kg=mass,
        center_of_mass_m=com,
        inertia_kg_m2=(ixx, ixy, ixz, ixy, iyy, iyz, ixz, iyz, izz),
        envelope=envelope,
    )


def assess_imbalance(elements: tuple[MassElement, ...]) -> ImbalanceState:
    """Static and couple imbalance of a declared mass-element set."""

    if not elements:
        raise BalanceError("MASS_ELEMENTS_REQUIRED")
    mass, mx, my, _ = _sums(elements)
    if mass <= 0:
        raise BalanceError("TOTAL_MASS_MUST_BE_POSITIVE")
    dynamic_x = 0.0
    dynamic_y = 0.0
    for element in elements:
        dynamic_x += element.mass_kg * element.x_m * element.z_m
        dynamic_y += element.mass_kg * element.y_m * element.z_m
    static_magnitude = math.hypot(mx, my)
    static_angle = math.atan2(my, mx) if static_magnitude > 0 else 0.0
    dynamic_magnitude = math.hypot(dynamic_x, dynamic_y)
    dynamic_angle = math.atan2(dynamic_y, dynamic_x) if dynamic_magnitude > 0 else 0.0
    mass_properties = compute_mass_properties(elements)
    envelope = build_envelope(
        model="advphys10-imbalance",
        inputs={"elements": [element.as_dict() for element in elements]},
        unit="kg*m",
        assumptions=(
            "static imbalance is sum(m*r) in the rotation plane",
            "dynamic imbalance is the sum(m*r*z) couple about the reference plane",
            "point-mass model; no distributed mass is inferred",
        ),
    )
    return ImbalanceState(
        static_magnitude_kg_m=static_magnitude,
        static_angle_rad=static_angle,
        dynamic_magnitude_kg_m2=dynamic_magnitude,
        dynamic_angle_rad=dynamic_angle,
        mass_properties=mass_properties,
        envelope=envelope,
    )


def assess_balance(
    spec: BalanceSpec,
    elements: tuple[MassElement, ...],
) -> BalanceAssessment:
    """Compare residual imbalance against the declared allowable limit."""

    state = assess_imbalance(elements)
    residual = state.static_magnitude_kg_m
    envelope = build_envelope(
        model="advphys10-balance-assessment",
        inputs={**spec.inputs_payload(), "elements": [element.as_dict() for element in elements]},
        unit="kg*m",
        assumptions=(
            "residual imbalance is the uncorrected static magnitude",
            "dynamic couple is reported separately and not folded into the residual",
        ),
    )
    return BalanceAssessment(
        spec_id=spec.spec_id,
        residual_kg_m=residual,
        allowable_kg_m=spec.allowable_residual_kg_m,
        satisfied=residual <= spec.allowable_residual_kg_m,
        static_magnitude_kg_m=state.static_magnitude_kg_m,
        dynamic_magnitude_kg_m2=state.dynamic_magnitude_kg_m2,
        envelope=envelope,
    )


def balance_scatter(
    spec: BalanceSpec,
    elements: tuple[MassScatterElement, ...],
    *,
    samples: int = DEFAULT_BALANCE_SAMPLES,
    seed: int = 0,
) -> BalanceScatterResult:
    """Propagate manufacturing mass scatter into yield against the balance limit."""

    if not elements:
        raise BalanceError("SCATTER_ELEMENTS_REQUIRED")
    if samples < 1:
        raise BalanceError("BALANCE_SAMPLES_MUST_BE_POSITIVE")
    if samples > MAX_BALANCE_SAMPLES:
        raise BalanceError(f"BALANCE_SAMPLES_EXCEED_BOUND:{MAX_BALANCE_SAMPLES}")
    rng = random.Random(seed)
    count = 0
    mean = 0.0
    m2 = 0.0
    maximum = 0.0
    passed = 0
    for _ in range(samples):
        sx = 0.0
        sy = 0.0
        for element in elements:
            mass = element.sample_mass(rng)
            sx += mass * element.x_m
            sy += mass * element.y_m
        residual = math.hypot(sx, sy)
        count += 1
        delta = residual - mean
        mean += delta / count
        m2 += delta * (residual - mean)
        maximum = max(maximum, residual)
        if residual <= spec.allowable_residual_kg_m:
            passed += 1
    std = math.sqrt(m2 / count) if count > 1 else 0.0
    fraction = passed / count
    envelope = build_envelope(
        model="advphys10-balance-scatter",
        inputs={
            **spec.inputs_payload(),
            "elements": [
                {
                    "id": element.id,
                    "massKg": element.mass_kg,
                    "massToleranceKg": element.mass_tolerance_kg,
                    "distribution": element.distribution.value,
                }
                for element in elements
            ],
            "samples": samples,
            "seed": seed,
        },
        unit="kg*m",
        assumptions=(
            "element masses vary independently within their declared tolerances",
            "point-mass geometry is nominal",
            "fixed seed for reproducibility",
        ),
    )
    return BalanceScatterResult(
        spec_id=spec.spec_id,
        samples=samples,
        seed=seed,
        mean_residual_kg_m=mean,
        std_residual_kg_m=std,
        max_residual_kg_m=maximum,
        yield_fraction=fraction,
        ppm=(1.0 - fraction) * 1.0e6,
        envelope=envelope,
    )


def residual_unbalance_forcing(
    residual_kg_m: float,
    speed_rpm: float,
    *,
    source: str,
    label: str = "residual-unbalance",
) -> ForcingLine:
    """Convert a residual imbalance to a synchronous forcing line (force in N).

    The centrifugal force of an unbalance ``U = m*e`` (kg*m) at angular speed
    ``omega`` is ``F = U*omega^2``. The line is synchronous (order 1), so the
    existing forcing-separation assessment resolves its frequency at each speed
    without this layer inventing a frequency.
    """

    if not math.isfinite(residual_kg_m) or residual_kg_m < 0:
        raise BalanceError("RESIDUAL_IMBALANCE_MUST_BE_NONNEGATIVE")
    if not math.isfinite(speed_rpm) or speed_rpm <= 0:
        raise BalanceError("SPEED_RPM_MUST_BE_POSITIVE")
    if not source.strip():
        raise BalanceError("FORCING_SOURCE_REQUIRED")
    omega = 2.0 * math.pi * speed_rpm / 60.0
    force_n = residual_kg_m * omega * omega
    return ForcingLine(
        source=source,
        label=label,
        amplitude=force_n,
        order=1.0,
        speed_dependence="synchronous",
    )
