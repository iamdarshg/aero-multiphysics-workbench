"""Versioned loss/deviation/slip correlations with explicit validity envelopes.

Every correlation declares a stable identity, a model version, a named source,
and the envelope in which it may be applied. Evaluation returns a
:class:`CorrelationValue` that carries the model identity, the source, and any
envelope violations, so no result is ever a bare "magic" number. Constants are
screening coefficients taken from the cited source; they are never presented as
native solver output.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from math import atan, cos, isfinite, radians, sin, sqrt, tan

from aeroworkbench_core.types import FidelityLevel, Provenance, ResultSource

from .errors import MeanlineCorrelationError


@dataclass(frozen=True, slots=True)
class CorrelationSpec:
    """Identity, provenance, and validity envelope of one correlation."""

    identity: str
    version: str
    source: str
    description: str
    validity: tuple[tuple[str, float, float], ...] = ()

    def check(self, values: Mapping[str, float]) -> tuple[str, ...]:
        violations: list[str] = []
        for name, low, high in self.validity:
            if name not in values:
                continue
            value = values[name]
            if not low <= value <= high:
                violations.append(f"{name}={value:.6g} outside [{low:.6g},{high:.6g}]")
        return tuple(violations)


@dataclass(frozen=True, slots=True)
class CorrelationValue:
    """One evaluated correlation value with full provenance."""

    name: str
    value: float
    unit: str
    identity: str
    version: str
    source: str
    validity_passed: bool
    violations: tuple[str, ...] = ()

    def canonical(self) -> dict[str, object]:
        return {
            "name": self.name,
            "value": self.value,
            "unit": self.unit,
            "correlation": self.identity,
            "version": self.version,
            "source": self.source,
            "validityPassed": self.validity_passed,
            "violations": list(self.violations),
        }

    def provenance(self, *, inputs: Mapping[str, object]) -> Provenance:
        return Provenance.from_inputs(
            source=ResultSource.ANALYTICAL,
            model=self.identity,
            model_version=self.version,
            fidelity=FidelityLevel.ANALYTICAL,
            inputs=dict(inputs),
            assumptions=(self.source,),
        )


def _value(
    spec: CorrelationSpec,
    *,
    name: str,
    value: float,
    unit: str,
    inputs: Mapping[str, float],
) -> CorrelationValue:
    if not isfinite(value):
        raise MeanlineCorrelationError(f"NONFINITE_CORRELATION_VALUE:{spec.identity}:{name}")
    violations = spec.check(inputs)
    return CorrelationValue(
        name=name,
        value=value,
        unit=unit,
        identity=spec.identity,
        version=spec.version,
        source=spec.source,
        validity_passed=not violations,
        violations=violations,
    )


CARTER_DEVIATION = CorrelationSpec(
    identity="carter-deviation",
    version="1.0",
    source="Carter (1945); Dixon & Hall, Fluid Mechanics of Turbomachinery",
    description="delta_deg = m*camber_deg/sqrt(solidity), m = 0.23 + 0.1*(stagger/50)",
    validity=(("solidity", 0.4, 3.0), ("camber_deg", 0.0, 70.0)),
)

LIEBLEIN_DIFFUSION = CorrelationSpec(
    identity="lieblein-diffusion-factor",
    version="1.0",
    source="Lieblein, Schwenk & Broderick (NACA RM E53D01, 1953)",
    description=(
        "DF = (1 - W2/W1) + |r2*Vt2 - r1*Vt1| / (2*solidity*W1*r1)"
    ),
    validity=(("solidity", 0.4, 3.0),),
)

LIEBLEIN_PROFILE_LOSS = CorrelationSpec(
    identity="lieblein-profile-loss",
    version="1.0",
    source="Lieblein (1959) minimum-loss data, quadratic screening fit (Dixon & Hall)",
    description="omega_profile = 0.004 + 0.008*DF^2",
    validity=(("diffusion_factor", 0.0, 0.8),),
)

AINLEY_LOADING = CorrelationSpec(
    identity="ainley-loading-parameter",
    version="1.0",
    source="Ainley & Mathieson (1951), ARC R&M 2974",
    description="Z = 4*(tan(b_in) - tan(b_out))^2 * cos(b_out)^2 / cos(b_m)^3",
    validity=(("inlet_angle_deg", -80.0, 80.0), ("outlet_angle_deg", -80.0, 80.0)),
)

AINLEY_MATHIESON_SECONDARY = CorrelationSpec(
    identity="ainley-mathieson-secondary-loss",
    version="1.0",
    source="Ainley & Mathieson (1951) loading-squared secondary form (screening constant)",
    description="Y_secondary = 0.005*(tan(b_in) - tan(b_out))^2/solidity",
    validity=(("inlet_angle_deg", -80.0, 80.0), ("outlet_angle_deg", -80.0, 80.0)),
)

CARTER_SECONDARY = CorrelationSpec(
    identity="carter-secondary-loss",
    version="1.0",
    source="Carter (1945); Dixon & Hall (2014) loading-squared secondary form",
    description="omega_secondary = 0.018*(tan(b_in) - tan(b_out))^2/solidity",
    validity=(("inlet_angle_deg", -80.0, 80.0), ("outlet_angle_deg", -80.0, 80.0)),
)

DUNHAM_CAME_TIP_CLEARANCE = CorrelationSpec(
    identity="dunham-came-tip-clearance-loss",
    version="1.0",
    source="Dunham & Came (1970), Improvements to the Ainley-Mathieson Method",
    description="Y_tip = B * (c/h) * (tau/c)^0.78 * Z; B=0.47 unshrouded, 0.37 shrouded",
    validity=(("clearance_to_chord", 0.0, 0.1), ("chord_to_span", 0.0, 5.0)),
)

CONRAD_INCIDENCE = CorrelationSpec(
    identity="conrad-incidence-loss",
    version="1.0",
    source="Conrad (1945); Dixon & Hall (2014)",
    description="omega_incidence = (meridional*tan(incidence)/W_reference)^2",
    validity=(("incidence_deg", -30.0, 30.0),),
)

LIEBLEIN_BLOCKAGE = CorrelationSpec(
    identity="lieblein-blockage",
    version="1.0",
    source="Lieblein (1959) diffuser/blockage study (screening fit)",
    description="blockage = min(0.2, 0.01 + 0.05*DF)",
    validity=(("diffusion_factor", 0.0, 0.8),),
)

COPPAGE_IMPELLER = CorrelationSpec(
    identity="coppage-impeller-loss",
    version="1.0",
    source="Coppage et al. (1956); Japikse (1996), Centrifugal Compressor Design",
    description="omega_profile = 0.1*(1 - de_haller); de_haller = W_out/W_in",
    validity=(("de_haller", 0.0, 1.0),),
)

AINLEY_MATHIESON_PROFILE = CorrelationSpec(
    identity="ainley-mathieson-profile-loss",
    version="1.0",
    source="Ainley & Mathieson (1951); Dunham & Came (1970) Mach correction",
    description="Y_profile = base*(1 + 0.02*|incidence|) + 60*(M-1)^2 for M>1",
    validity=(("incidence_deg", -40.0, 40.0),),
)

STANITZ_SLIP = CorrelationSpec(
    identity="stanitz-slip-factor",
    version="1.0",
    source="Stanitz (1952), NACA TN 2611",
    description="sigma = 1 - 0.63*pi/blade_count",
    validity=(("blade_count", 6.0, 60.0),),
)

WIESNER_SLIP = CorrelationSpec(
    identity="wiesner-slip-factor",
    version="1.0",
    source="Wiesner (1967), ASME 66-WA/FE-18",
    description="sigma = 1 - sqrt(sin(beta2))/blade_count^0.7",
    validity=(("blade_count", 6.0, 60.0), ("exit_blade_angle_deg", 5.0, 90.0)),
)

DIFFUSER_RECOVERY = CorrelationSpec(
    identity="japikse-diffuser-recovery",
    version="1.0",
    source="Japikse (1996), Centrifugal Compressor Design and Performance",
    description="omega_diffuser = (1 - eta_recovery)*(1 - 1/AR^2)",
    validity=(("area_ratio", 1.0, 4.0),),
)


def carter_deviation_deg(
    *, camber_deg: float, stagger_deg: float, solidity: float
) -> CorrelationValue:
    inputs = {"camber_deg": camber_deg, "stagger_deg": stagger_deg, "solidity": solidity}
    m = max(0.0, 0.23 + 0.1 * (stagger_deg / 50.0))
    deviation = m * camber_deg / sqrt(solidity)
    return _value(
        CARTER_DEVIATION, name="deviation", value=deviation, unit="deg", inputs=inputs
    )


def lieblein_diffusion_factor(
    *,
    inlet_relative_velocity_m_s: float,
    outlet_relative_velocity_m_s: float,
    inlet_tangential_velocity_m_s: float,
    outlet_tangential_velocity_m_s: float,
    inlet_radius_m: float,
    outlet_radius_m: float,
    solidity: float,
) -> CorrelationValue:
    inputs = {"solidity": solidity}
    if inlet_relative_velocity_m_s <= 0.0 or inlet_radius_m <= 0.0:
        raise MeanlineCorrelationError("DIFFUSION_FACTOR_NEEDS_POSITIVE_INLET_STATE")
    velocity_term = 1.0 - outlet_relative_velocity_m_s / inlet_relative_velocity_m_s
    circulation = abs(
        outlet_radius_m * outlet_tangential_velocity_m_s
        - inlet_radius_m * inlet_tangential_velocity_m_s
    )
    circulation_term = circulation / (
        2.0 * solidity * inlet_relative_velocity_m_s * inlet_radius_m
    )
    return _value(
        LIEBLEIN_DIFFUSION,
        name="diffusion_factor",
        value=velocity_term + circulation_term,
        unit="dimensionless",
        inputs=inputs,
    )


def lieblein_profile_loss(*, diffusion_factor: float) -> CorrelationValue:
    return _value(
        LIEBLEIN_PROFILE_LOSS,
        name="profile_loss",
        value=0.004 + 0.008 * diffusion_factor * diffusion_factor,
        unit="dimensionless",
        inputs={"diffusion_factor": diffusion_factor},
    )


def ainley_loading_parameter(
    *, inlet_angle_deg: float, outlet_angle_deg: float
) -> CorrelationValue:
    inputs = {"inlet_angle_deg": inlet_angle_deg, "outlet_angle_deg": outlet_angle_deg}
    beta_in = radians(inlet_angle_deg)
    beta_out = radians(outlet_angle_deg)
    mean_angle = atan((tan(beta_in) + tan(beta_out)) / 2.0)
    cosine_mean = cos(mean_angle)
    if abs(cosine_mean) < 1e-6:
        raise MeanlineCorrelationError("AINLEY_LOADING_SINGULAR_MEAN_ANGLE")
    z = (
        4.0
        * (tan(beta_in) - tan(beta_out)) ** 2
        * cos(beta_out) ** 2
        / cosine_mean**3
    )
    return _value(
        AINLEY_LOADING,
        name="ainley_loading_parameter",
        value=abs(z),
        unit="dimensionless",
        inputs=inputs,
    )


def ainley_mathieson_secondary_loss(
    *, inlet_angle_deg: float, outlet_angle_deg: float, solidity: float
) -> CorrelationValue:
    inputs = {"inlet_angle_deg": inlet_angle_deg, "outlet_angle_deg": outlet_angle_deg}
    beta_in = radians(inlet_angle_deg)
    beta_out = radians(outlet_angle_deg)
    loss = 0.005 * (tan(beta_in) - tan(beta_out)) ** 2 / solidity
    return _value(
        AINLEY_MATHIESON_SECONDARY,
        name="secondary_loss",
        value=abs(loss),
        unit="dimensionless",
        inputs=inputs,
    )


def carter_secondary_loss(
    *, inlet_angle_deg: float, outlet_angle_deg: float, solidity: float
) -> CorrelationValue:
    inputs = {"inlet_angle_deg": inlet_angle_deg, "outlet_angle_deg": outlet_angle_deg}
    beta_in = radians(inlet_angle_deg)
    beta_out = radians(outlet_angle_deg)
    loss = 0.018 * (tan(beta_in) - tan(beta_out)) ** 2 / solidity
    return _value(
        CARTER_SECONDARY,
        name="secondary_loss",
        value=abs(loss),
        unit="dimensionless",
        inputs=inputs,
    )


def dunham_came_tip_clearance_loss(
    *,
    clearance_to_chord: float,
    chord_to_span: float,
    loading_parameter: float,
    shrouded: bool = False,
) -> CorrelationValue:
    inputs = {"clearance_to_chord": clearance_to_chord, "chord_to_span": chord_to_span}
    b = 0.37 if shrouded else 0.47
    loss = b * chord_to_span * clearance_to_chord**0.78 * loading_parameter
    return _value(
        DUNHAM_CAME_TIP_CLEARANCE,
        name="tip_clearance_loss",
        value=loss,
        unit="dimensionless",
        inputs=inputs,
    )


def conrad_incidence_loss(
    *,
    incidence_deg: float,
    meridional_velocity_m_s: float,
    relative_velocity_m_s: float,
) -> CorrelationValue:
    if relative_velocity_m_s <= 0.0:
        raise MeanlineCorrelationError("INCIDENCE_LOSS_NEEDS_POSITIVE_RELATIVE_VELOCITY")
    inputs = {"incidence_deg": incidence_deg}
    mismatch = meridional_velocity_m_s * tan(radians(incidence_deg))
    loss = (mismatch / relative_velocity_m_s) ** 2
    return _value(
        CONRAD_INCIDENCE,
        name="incidence_loss",
        value=loss,
        unit="dimensionless",
        inputs=inputs,
    )


def lieblein_blockage(*, diffusion_factor: float) -> CorrelationValue:
    blockage = min(0.2, 0.01 + 0.05 * max(diffusion_factor, 0.0))
    return _value(
        LIEBLEIN_BLOCKAGE,
        name="blockage",
        value=blockage,
        unit="dimensionless",
        inputs={"diffusion_factor": diffusion_factor},
    )


def radial_impeller_profile_loss(*, de_haller: float) -> CorrelationValue:
    return _value(
        COPPAGE_IMPELLER,
        name="profile_loss",
        value=0.1 * (1.0 - de_haller),
        unit="dimensionless",
        inputs={"de_haller": de_haller},
    )


def ainley_mathieson_profile_loss(
    *, incidence_deg: float, exit_mach: float, base_profile_loss: float = 0.08
) -> CorrelationValue:
    inputs = {"incidence_deg": incidence_deg}
    loss = base_profile_loss * (1.0 + 0.02 * abs(incidence_deg))
    if exit_mach > 1.0:
        loss *= 1.0 + 60.0 * (exit_mach - 1.0) ** 2
    return _value(
        AINLEY_MATHIESON_PROFILE,
        name="profile_loss",
        value=loss,
        unit="dimensionless",
        inputs=inputs,
    )


def slip_factor(
    *, blade_count: int, exit_blade_angle_deg: float | None = None
) -> CorrelationValue:
    if exit_blade_angle_deg is None:
        value = 1.0 - 0.63 * 3.141592653589793 / blade_count
        return _value(
            STANITZ_SLIP,
            name="slip_factor",
            value=value,
            unit="dimensionless",
            inputs={"blade_count": float(blade_count)},
        )
    sine = sqrt(max(0.0, sin(radians(exit_blade_angle_deg))))
    value = 1.0 - sine / blade_count**0.7
    return _value(
        WIESNER_SLIP,
        name="slip_factor",
        value=value,
        unit="dimensionless",
        inputs={
            "blade_count": float(blade_count),
            "exit_blade_angle_deg": exit_blade_angle_deg,
        },
    )


def diffuser_loss_coefficient(
    *, area_ratio: float, recovery_efficiency: float
) -> CorrelationValue:
    if not 0.0 < recovery_efficiency <= 1.0:
        raise MeanlineCorrelationError("DIFFUSER_RECOVERY_EFFICIENCY_OUT_OF_RANGE")
    ideal_recovery = 1.0 - 1.0 / (area_ratio * area_ratio)
    loss = (1.0 - recovery_efficiency) * ideal_recovery
    return _value(
        DIFFUSER_RECOVERY,
        name="diffuser_loss",
        value=loss,
        unit="dimensionless",
        inputs={"area_ratio": area_ratio},
    )


LOSS_CORRELATIONS: dict[str, CorrelationSpec] = {
    spec.identity: spec
    for spec in (
        CARTER_DEVIATION,
        LIEBLEIN_DIFFUSION,
        LIEBLEIN_PROFILE_LOSS,
        AINLEY_LOADING,
        AINLEY_MATHIESON_SECONDARY,
        CARTER_SECONDARY,
        DUNHAM_CAME_TIP_CLEARANCE,
        CONRAD_INCIDENCE,
        COPPAGE_IMPELLER,
        LIEBLEIN_BLOCKAGE,
        AINLEY_MATHIESON_PROFILE,
        STANITZ_SLIP,
        WIESNER_SLIP,
        DIFFUSER_RECOVERY,
    )
}


__all__ = [
    "CorrelationSpec",
    "CorrelationValue",
    "LOSS_CORRELATIONS",
    "CARTER_DEVIATION",
    "LIEBLEIN_DIFFUSION",
    "LIEBLEIN_PROFILE_LOSS",
    "AINLEY_LOADING",
    "AINLEY_MATHIESON_SECONDARY",
    "CARTER_SECONDARY",
    "DUNHAM_CAME_TIP_CLEARANCE",
    "CONRAD_INCIDENCE",
    "COPPAGE_IMPELLER",
    "LIEBLEIN_BLOCKAGE",
    "AINLEY_MATHIESON_PROFILE",
    "STANITZ_SLIP",
    "WIESNER_SLIP",
    "DIFFUSER_RECOVERY",
    "carter_deviation_deg",
    "lieblein_diffusion_factor",
    "lieblein_profile_loss",
    "radial_impeller_profile_loss",
    "ainley_loading_parameter",
    "ainley_mathieson_secondary_loss",
    "carter_secondary_loss",
    "dunham_came_tip_clearance_loss",
    "conrad_incidence_loss",
    "lieblein_blockage",
    "ainley_mathieson_profile_loss",
    "slip_factor",
    "diffuser_loss_coefficient",
]
