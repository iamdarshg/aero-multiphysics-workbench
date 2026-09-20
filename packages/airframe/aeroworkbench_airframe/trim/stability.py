"""Static stability: static margin, neutral point, and derivative-sign verdicts.

The longitudinal verdict is the sign of ``Cm_alpha`` (negative is stable) and
``CL_alpha`` (positive is required). Static margin is
``-Cm_alpha / CL_alpha`` in fractions of the mean aerodynamic chord, consistent
with the AIRFRAME 03 static-margin constraint convention. Missing derivative
coverage yields an explicit coverage finding and an invalid verdict rather than
a fabricated stability claim.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..units import Quantity
from .contract import (
    LateralDirectionalDerivatives,
    LongitudinalDerivatives,
    ResultMeta,
    result_meta,
)
from .errors import AeroCoefficientError

MODEL = "airframe-trim-static-stability"

_ASSUMPTIONS = (
    "Static margin is -Cm_alpha / CL_alpha in fractions of the reference chord.",
    "Neutral point is CG fraction plus static margin, positive aft.",
    "A missing derivative is a coverage failure, not a stability verdict.",
)

COVERAGE = "coverage"
STABILITY = "stability"


@dataclass(frozen=True, slots=True)
class StabilityFinding:
    kind: str
    name: str
    passed: bool
    value: float | None
    detail: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "name": self.name,
            "passed": self.passed,
            "value": self.value,
            "detail": self.detail,
        }


@dataclass(frozen=True, slots=True)
class StaticStabilityReport:
    valid: bool
    longitudinal_stable: bool | None
    lateral_directional_stable: bool | None
    static_margin: Quantity | None
    neutral_point: Quantity | None
    findings: tuple[StabilityFinding, ...]
    meta: ResultMeta

    @property
    def coverage_complete(self) -> bool:
        return all(finding.passed for finding in self.findings if finding.kind == COVERAGE)

    def as_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "longitudinalStable": self.longitudinal_stable,
            "lateralDirectionalStable": self.lateral_directional_stable,
            "staticMargin": None if self.static_margin is None else self.static_margin.canonical(),
            "neutralPoint": (
                None if self.neutral_point is None else self.neutral_point.canonical()
            ),
            "findings": [finding.as_dict() for finding in self.findings],
            "meta": self.meta.as_dict(),
        }


def static_margin(longitudinal: LongitudinalDerivatives) -> Quantity:
    """Return ``-Cm_alpha / CL_alpha`` in fractions of the reference chord."""

    values = longitudinal.require("cl_alpha", "cm_alpha")
    if values["cl_alpha"] == 0.0:
        raise AeroCoefficientError("ZERO_LIFT_CURVE_SLOPE")
    return Quantity(-values["cm_alpha"] / values["cl_alpha"], "dimensionless")


def neutral_point(longitudinal: LongitudinalDerivatives, *, cg_mac_fraction: float) -> Quantity:
    """Return the neutral-point fraction of chord, positive aft of the reference."""

    return Quantity(cg_mac_fraction + static_margin(longitudinal).value_si, "dimensionless")


def _coverage(name: str, present: bool) -> StabilityFinding:
    return StabilityFinding(
        kind=COVERAGE,
        name=name,
        passed=present,
        value=None,
        detail=(
            f"derivative available: {name}"
            if present
            else f"DERIVATIVE_COVERAGE_INSUFFICIENT:{name}"
        ),
    )


def _stability(name: str, passed: bool, value: float, detail: str) -> StabilityFinding:
    return StabilityFinding(kind=STABILITY, name=name, passed=passed, value=value, detail=detail)


def _longitudinal_findings(
    longitudinal: LongitudinalDerivatives,
) -> tuple[list[StabilityFinding], bool, bool | None]:
    findings = [
        _coverage("cl_alpha", longitudinal.cl_alpha is not None),
        _coverage("cm_alpha", longitudinal.cm_alpha is not None),
    ]
    if longitudinal.cl_alpha is None or longitudinal.cm_alpha is None:
        return findings, False, None
    cl_alpha = longitudinal.cl_alpha
    cm_alpha = longitudinal.cm_alpha
    lift_ok = cl_alpha > 0.0
    pitch_ok = cm_alpha < 0.0
    findings.append(
        _stability(
            "cl_alpha_positive",
            lift_ok,
            cl_alpha,
            f"CL_alpha={cl_alpha!r} per rad; lift curve must be positive",
        )
    )
    findings.append(
        _stability(
            "cm_alpha_negative",
            pitch_ok,
            cm_alpha,
            f"Cm_alpha={cm_alpha!r} per rad; static stability needs Cm_alpha < 0",
        )
    )
    return findings, True, lift_ok and pitch_ok


def _lateral_findings(
    lateral: LateralDirectionalDerivatives,
) -> tuple[list[StabilityFinding], bool, bool | None]:
    required = ("cn_beta", "cl_beta", "cl_p", "cn_r")
    findings = [_coverage(name, getattr(lateral, name) is not None) for name in required]
    if any(getattr(lateral, name) is None for name in required):
        return findings, False, None
    assert lateral.cn_beta is not None
    assert lateral.cl_beta is not None
    assert lateral.cl_p is not None
    assert lateral.cn_r is not None
    weathercock = lateral.cn_beta > 0.0
    dihedral = lateral.cl_beta < 0.0
    roll_damping = lateral.cl_p < 0.0
    yaw_damping = lateral.cn_r < 0.0
    findings.append(
        _stability(
            "cn_beta_positive",
            weathercock,
            lateral.cn_beta,
            f"Cn_beta={lateral.cn_beta!r}; directional stability needs C_n_beta > 0",
        )
    )
    findings.append(
        _stability(
            "cl_beta_negative",
            dihedral,
            lateral.cl_beta,
            f"Cl_beta={lateral.cl_beta!r}; dihedral effect needs C_l_beta < 0",
        )
    )
    findings.append(
        _stability(
            "cl_p_negative",
            roll_damping,
            lateral.cl_p,
            f"Cl_p={lateral.cl_p!r}; roll damping needs C_l_p < 0",
        )
    )
    findings.append(
        _stability(
            "cn_r_negative",
            yaw_damping,
            lateral.cn_r,
            f"Cn_r={lateral.cn_r!r}; yaw damping needs C_n_r < 0",
        )
    )
    stable = weathercock and dihedral and roll_damping and yaw_damping
    return findings, True, stable


def evaluate_static_stability(
    longitudinal: LongitudinalDerivatives,
    lateral: LateralDirectionalDerivatives,
    *,
    cg_mac_fraction: float | None = None,
    high_speed_valid: bool | None = None,
    high_speed_notes: tuple[str, ...] = (),
) -> StaticStabilityReport:
    """Evaluate longitudinal and lateral-directional static stability, fail closed."""

    lon_findings, lon_coverage, lon_stable = _longitudinal_findings(longitudinal)
    lat_findings, lat_coverage, lat_stable = _lateral_findings(lateral)
    findings = lon_findings + lat_findings
    if high_speed_valid is False:
        findings.append(
            _coverage(
                "high_speed_derivatives",
                False,
            )
        )
    margin: Quantity | None = None
    neutral: Quantity | None = None
    if lon_coverage:
        margin = static_margin(longitudinal)
        if cg_mac_fraction is not None:
            neutral = neutral_point(longitudinal, cg_mac_fraction=cg_mac_fraction)
            findings.append(
                _stability(
                    "static_margin_positive",
                    margin.value_si > 0.0,
                    margin.value_si,
                    f"static margin {margin.value_si!r} chord; positive is stable",
                )
            )
    valid = lon_coverage and lat_coverage and high_speed_valid is not False
    inputs = {
        "longitudinal": longitudinal.present(),
        "lateralDirectional": lateral.present(),
        "cgMacFraction": cg_mac_fraction,
    }
    coverage_failures = tuple(
        finding.detail for finding in findings if finding.kind == COVERAGE and not finding.passed
    ) + tuple(high_speed_notes)
    meta = result_meta(
        model=MODEL,
        inputs=inputs,
        valid=valid,
        notes=coverage_failures,
        assumptions=_ASSUMPTIONS,
    )
    return StaticStabilityReport(
        valid=valid,
        longitudinal_stable=lon_stable,
        lateral_directional_stable=lat_stable,
        static_margin=margin,
        neutral_point=neutral,
        findings=tuple(findings),
        meta=meta,
    )


__all__ = [
    "COVERAGE",
    "STABILITY",
    "StaticStabilityReport",
    "StabilityFinding",
    "evaluate_static_stability",
    "neutral_point",
    "static_margin",
]
