"""Declared compressibility corrections with explicit validity bands."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite, sqrt
from typing import Any

from .contracts import ResultEnvelope, Validity, analytical_envelope, content_digest
from .errors import TransonicContractError, TransonicValidityError
from .regime import INCOMPRESSIBLE_MAX_MACH, assert_not_hypersonic

__all__ = [
    "CorrectionMethod",
    "CorrectionResult",
    "KARMAN_TSIEN_MAX_MACH",
    "LAITONE_MAX_MACH",
    "PRANDTL_GLAUERT_MAX_MACH",
    "apply_correction",
    "compressible_derivative",
    "karman_tsien",
    "laitone",
    "prandtl_glauert",
]

PRANDTL_GLAUERT_MAX_MACH = 0.7
KARMAN_TSIEN_MAX_MACH = 0.8
LAITONE_MAX_MACH = 0.85
CORRECTION_MODEL = "vehicle-systems.transonic.compressibility-correction"

CorrectionMethod = str


def _require_cp(cp0: float) -> float:
    if not isfinite(cp0):
        raise TransonicContractError(f"INVALID_CP0:{cp0!r}")
    return float(cp0)


def _require_subsonic_band(mach: float, limit: float, method: str) -> float:
    assert_not_hypersonic(mach)
    if not isfinite(mach) or mach < 0.0:
        raise TransonicContractError(f"INVALID_MACH:{mach!r}")
    if mach > limit:
        raise TransonicValidityError(f"{method}_OUT_OF_RANGE:mach={mach}:limit={limit}")
    return float(mach)


def prandtl_glauert(cp0: float, mach: float) -> float:
    """Prandtl-Glauert Cp correction, declared valid for M <= 0.7."""

    base = _require_cp(cp0)
    value = _require_subsonic_band(mach, PRANDTL_GLAUERT_MAX_MACH, "PRANDTL_GLAUERT")
    return base / sqrt(1.0 - value * value)


def karman_tsien(cp0: float, mach: float) -> float:
    """Karman-Tsien Cp correction, declared valid for M <= 0.8."""

    base = _require_cp(cp0)
    value = _require_subsonic_band(mach, KARMAN_TSIEN_MAX_MACH, "KARMAN_TSIEN")
    beta = sqrt(1.0 - value * value)
    denominator = beta + (value * value / (1.0 + beta)) * base / 2.0
    if denominator <= 0.0:
        raise TransonicValidityError(f"KARMAN_TSIEN_SINGULAR:cp0={base}:mach={value}")
    return base / denominator


def laitone(cp0: float, mach: float, gamma: float = 1.4) -> float:
    """Laitone Cp correction, declared valid for M <= 0.85."""

    base = _require_cp(cp0)
    value = _require_subsonic_band(mach, LAITONE_MAX_MACH, "LAITONE")
    if not isfinite(gamma) or gamma <= 1.0:
        raise TransonicContractError(f"INVALID_GAMMA:{gamma!r}")
    beta = sqrt(1.0 - value * value)
    mu = value * value * (1.0 + (gamma - 1.0) / 2.0 * value * value) / (2.0 * beta)
    denominator = beta + mu * base / 2.0
    if denominator <= 0.0:
        raise TransonicValidityError(f"LAITONE_SINGULAR:cp0={base}:mach={value}")
    return base / denominator


def compressible_derivative(cl_alpha_incomp_per_rad: float, mach: float) -> float:
    """Scale a lift-curve slope by Prandtl-Glauert; passthrough below M 0.3."""

    if not isfinite(cl_alpha_incomp_per_rad) or cl_alpha_incomp_per_rad <= 0.0:
        raise TransonicContractError(f"INVALID_CL_ALPHA:{cl_alpha_incomp_per_rad!r}")
    value = _require_subsonic_band(mach, PRANDTL_GLAUERT_MAX_MACH, "COMPRESSIBLE_DERIVATIVE")
    if value < INCOMPRESSIBLE_MAX_MACH:
        return float(cl_alpha_incomp_per_rad)
    return float(cl_alpha_incomp_per_rad / sqrt(1.0 - value * value))


@dataclass(frozen=True, slots=True)
class CorrectionResult:
    """A compressibility-corrected pressure coefficient with its envelope."""

    method: str
    mach: float
    cp_incompressible: float
    cp_corrected: float
    correction_factor: float
    validity: Validity
    envelope: ResultEnvelope

    def canonical(self) -> dict[str, Any]:
        return {
            "method": self.method,
            "mach": self.mach,
            "cpIncompressible": self.cp_incompressible,
            "cpCorrected": self.cp_corrected,
            "correctionFactor": self.correction_factor,
            "validity": self.validity.canonical(),
            "envelope": self.envelope.as_dict(),
        }

    @property
    def content_hash(self) -> str:
        return content_digest(self.canonical())

    @property
    def input_hash(self) -> str:
        return self.envelope.inputs_hash


def apply_correction(
    cp0: float, mach: float, method: CorrectionMethod = "karman-tsien"
) -> CorrectionResult:
    """Apply a declared correction; low-Mach input passes through uncorrected."""

    base = _require_cp(cp0)
    value = assert_not_hypersonic(mach)
    if not isfinite(value) or value < 0.0:
        raise TransonicContractError(f"INVALID_MACH:{mach!r}")
    inputs: dict[str, Any] = {"cp0": base, "mach": value, "method": method}
    if value < INCOMPRESSIBLE_MAX_MACH:
        validity = Validity(
            True, {"incompressible_passthrough": True}, "M<0.3:no correction applied"
        )
        envelope = analytical_envelope(
            model=CORRECTION_MODEL,
            inputs=inputs,
            validity=validity,
            assumptions=("incompressible regime; compressibility correction not invoked",),
        )
        return CorrectionResult("none", value, base, base, 1.0, validity, envelope)
    corrected = {
        "prandtl-glauert": prandtl_glauert,
        "karman-tsien": karman_tsien,
        "laitone": laitone,
    }.get(method)
    if corrected is None:
        raise TransonicContractError(f"UNKNOWN_CORRECTION_METHOD:{method}")
    result = corrected(base, value)
    factor = result / base if base != 0.0 else 1.0
    validity = Validity(True, {f"{method}_in_range": True}, f"within {method} validity band")
    envelope = analytical_envelope(
        model=CORRECTION_MODEL,
        inputs=inputs,
        validity=validity,
        assumptions=(f"{method} screening; attached subsonic flow",),
    )
    return CorrectionResult(method, value, base, result, factor, validity, envelope)
