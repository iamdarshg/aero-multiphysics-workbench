"""Quality-gated optimization: invalid physics never ranks as a good design.

Before an objective value is admissible, its declared quality policy must
hold: the solver converged, global physical closure passed, mesh and
timestep sensitivity are acceptable, the result is inside model validity,
and any required resonance margin holds. Points that fail get the explicit
``invalid-sample`` state and are excluded from objective ranking.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True, slots=True)
class QualityPolicy:
    require_converged: bool = True
    require_closure: bool = True
    max_mesh_sensitivity: float = 0.05
    max_timestep_sensitivity: float = 0.05
    require_validity: bool = True
    min_resonance_margin_hz: float | None = None

    def __post_init__(self) -> None:
        for label, value in (
            ("max_mesh_sensitivity", self.max_mesh_sensitivity),
            ("max_timestep_sensitivity", self.max_timestep_sensitivity),
        ):
            if not isfinite(value) or value < 0:
                raise ValueError(f"INVALID_QUALITY_POLICY:{label}")
        if self.min_resonance_margin_hz is not None and (
            not isfinite(self.min_resonance_margin_hz) or self.min_resonance_margin_hz < 0
        ):
            raise ValueError("INVALID_QUALITY_POLICY:min_resonance_margin_hz")


@dataclass(frozen=True, slots=True)
class PhysicsFlags:
    converged: bool
    closure_passed: bool
    validity_ok: bool
    mesh_sensitivity: float = 0.0
    timestep_sensitivity: float = 0.0
    resonance_margin_hz: float | None = None


@dataclass(frozen=True, slots=True)
class SampleVerdict:
    state: str  # "valid" | "invalid-sample"
    reasons: tuple[str, ...]


def assess_sample(flags: PhysicsFlags, policy: QualityPolicy) -> SampleVerdict:
    """Admit a physics sample only when every required quality gate passes."""
    reasons: list[str] = []
    if policy.require_converged and not flags.converged:
        reasons.append("solver did not converge")
    if policy.require_closure and not flags.closure_passed:
        reasons.append("physical closure failed")
    if policy.require_validity and not flags.validity_ok:
        reasons.append("result outside model validity range")
    if not isfinite(flags.mesh_sensitivity) or flags.mesh_sensitivity < 0:
        reasons.append("mesh sensitivity unreported")
    elif flags.mesh_sensitivity > policy.max_mesh_sensitivity:
        reasons.append(f"mesh sensitivity {flags.mesh_sensitivity:.3g} exceeds gate")
    if not isfinite(flags.timestep_sensitivity) or flags.timestep_sensitivity < 0:
        reasons.append("timestep sensitivity unreported")
    elif flags.timestep_sensitivity > policy.max_timestep_sensitivity:
        reasons.append("timestep sensitivity exceeds gate")
    if policy.min_resonance_margin_hz is not None:
        if flags.resonance_margin_hz is None or not isfinite(flags.resonance_margin_hz):
            reasons.append("resonance margin unreported")
        elif flags.resonance_margin_hz < policy.min_resonance_margin_hz:
            reasons.append("resonance margin violated")
    if reasons:
        return SampleVerdict("invalid-sample", tuple(reasons))
    return SampleVerdict("valid", ())
