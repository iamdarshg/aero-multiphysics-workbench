"""Clearance closure / contact / rub seam.

A generic clearance interface closes when the relative displacement exceeds the
declared gap, producing a contact force, friction force, and rub heat. When the
contact force or sliding speed crosses a declared limit the event requests a
higher-fidelity structural/contact participant; the native contact-FEA seam is
capability-gated and fails closed until wired.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aeroworkbench_core.types import Provenance

from .capabilities import NativeRequirement, require_native
from .errors import AeroelasticError
from .provenance import DEFAULT_SOFTWARE, SoftwareIdentity, analytical_provenance
from .validity import AeroelasticFidelity, Validity, finite


@dataclass(frozen=True, slots=True)
class RubContactSpec:
    """One generic clearance/contact interface."""

    interface_id: str
    clearance_m: float
    relative_displacement_m: float
    contact_stiffness_n_m: float
    damping_n_s_m: float = 0.0
    friction_coefficient: float = 0.0
    sliding_speed_m_s: float = 0.0
    normal_velocity_m_s: float = 0.0
    allowable_contact_force_n: float | None = None
    allowable_sliding_speed_m_s: float | None = None

    def __post_init__(self) -> None:
        if not self.interface_id.strip():
            raise AeroelasticError("interface_id is required")
        finite(self.clearance_m, "clearance_m", minimum=0.0)
        finite(self.relative_displacement_m, "relative_displacement_m", minimum=0.0)
        finite(self.contact_stiffness_n_m, "contact_stiffness_n_m", positive=True)
        finite(self.damping_n_s_m, "damping_n_s_m", minimum=0.0)
        finite(self.friction_coefficient, "friction_coefficient", minimum=0.0, maximum=2.0)
        finite(self.sliding_speed_m_s, "sliding_speed_m_s", minimum=0.0)
        finite(self.normal_velocity_m_s, "normal_velocity_m_s")
        if self.allowable_contact_force_n is not None:
            finite(self.allowable_contact_force_n, "allowable_contact_force_n", positive=True)
        if self.allowable_sliding_speed_m_s is not None:
            finite(
                self.allowable_sliding_speed_m_s,
                "allowable_sliding_speed_m_s",
                positive=True,
            )

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "interface_id": self.interface_id,
            "clearance_m": self.clearance_m,
            "relative_displacement_m": self.relative_displacement_m,
            "contact_stiffness_n_m": self.contact_stiffness_n_m,
            "damping_n_s_m": self.damping_n_s_m,
            "friction_coefficient": self.friction_coefficient,
            "sliding_speed_m_s": self.sliding_speed_m_s,
            "normal_velocity_m_s": self.normal_velocity_m_s,
            "allowable_contact_force_n": self.allowable_contact_force_n,
            "allowable_sliding_speed_m_s": self.allowable_sliding_speed_m_s,
        }


@dataclass(frozen=True, slots=True)
class ContactEventResult:
    """The outcome of one clearance-closure / rub event."""

    interface_id: str
    closed: bool
    penetration_m: float
    contact_force_n: float
    friction_force_n: float
    rub_heat_generation_w: float
    escalation_required: bool
    required_capability: str | None
    fidelity: AeroelasticFidelity
    validity: Validity
    provenance: Provenance
    software: SoftwareIdentity = DEFAULT_SOFTWARE

    def units(self) -> dict[str, str]:
        return {
            "penetration_m": "m",
            "contact_force_n": "N",
            "friction_force_n": "N",
            "rub_heat_generation_w": "W",
        }

    def structural_load_payload(self) -> dict[str, float]:
        return {
            "contact_force_n": self.contact_force_n,
            "friction_force_n": self.friction_force_n,
        }

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "interface_id": self.interface_id,
            "closed": self.closed,
            "penetration_m": self.penetration_m,
            "contact_force_n": self.contact_force_n,
            "friction_force_n": self.friction_force_n,
            "rub_heat_generation_w": self.rub_heat_generation_w,
            "escalation_required": self.escalation_required,
            "required_capability": self.required_capability,
            "source": self.provenance.source.value,
            "fidelity": self.fidelity.value,
            "inputs_hash": self.provenance.inputs_hash,
            "software": self.software.canonical(),
        }


def evaluate_contact_event(spec: RubContactSpec) -> ContactEventResult:
    """Evaluate clearance closure, contact force, friction, and rub heat."""

    penetration = max(0.0, spec.relative_displacement_m - spec.clearance_m)
    closed = penetration > 0.0
    contact_force = (
        spec.contact_stiffness_n_m * penetration
        + spec.damping_n_s_m * max(spec.normal_velocity_m_s, 0.0)
        if closed
        else 0.0
    )
    friction_force = spec.friction_coefficient * contact_force
    rub_heat = friction_force * spec.sliding_speed_m_s
    force_exceeded = (
        spec.allowable_contact_force_n is not None
        and contact_force > spec.allowable_contact_force_n
    )
    speed_exceeded = (
        closed
        and spec.allowable_sliding_speed_m_s is not None
        and spec.sliding_speed_m_s > spec.allowable_sliding_speed_m_s
    )
    escalation = bool(force_exceeded or speed_exceeded)
    checks = {
        "penetration_nonnegative": penetration >= 0.0,
        "contact_force_nonnegative": contact_force >= 0.0,
        "rub_heat_nonnegative": rub_heat >= 0.0,
    }
    return ContactEventResult(
        interface_id=spec.interface_id,
        closed=closed,
        penetration_m=penetration,
        contact_force_n=contact_force,
        friction_force_n=friction_force,
        rub_heat_generation_w=rub_heat,
        escalation_required=escalation,
        required_capability=NativeRequirement.CONTACT_FEA.value if escalation else None,
        fidelity=AeroelasticFidelity.SCREENING,
        validity=Validity(
            passed=all(checks.values()),
            checks=checks,
            detail=(
                "contact closed and limit exceeded"
                if escalation
                else ("contact closed" if closed else "clearance open")
            ),
        ),
        provenance=analytical_provenance(
            "aeroelasticity.contact.rub-event",
            {"interface": spec.canonical_payload()},
            assumptions=(
                "penalty contact stiffness; Coulomb friction; rub heat = friction power",
            ),
        ),
    )


def solve_native_contact(spec: RubContactSpec) -> ContactEventResult:
    """Request the native contact/rub FEA level; fails closed until wired."""

    if not spec.interface_id.strip():
        raise AeroelasticError("interface_id is required")
    require_native(NativeRequirement.CONTACT_FEA)


__all__ = [
    "ContactEventResult",
    "RubContactSpec",
    "evaluate_contact_event",
    "solve_native_contact",
]
