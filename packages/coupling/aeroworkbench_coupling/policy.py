"""Coupling-strength policy: the 0..1 control expanded to expert parameters.

The mapping is monotonic (strength 0 is loose and cheap, strength 1 is tight
and expensive) and every derived setting is persisted with a digest.
Expert overrides stay visible: each override is recorded with its value in
``overrides_applied`` and wins over the derived mapping.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True, slots=True)
class ExpertPolicy:
    """Visible persisted expert parameters derived from coupling strength."""

    strength: float
    nonlinear_tolerance: float
    linear_tolerance: float
    max_iterations: int
    field_exchange_frequency: int
    geometry_feedback_interval: int
    thermal_feedback_interval: int
    electrical_feedback_interval: int
    time_resolution_s: float
    precice_acceleration: str
    dynamic_activation: bool
    em_escalation: bool
    mesh_update_threshold: float
    overrides_applied: tuple[tuple[str, object], ...]
    digest: str

    def as_dict(self) -> dict[str, object]:
        return {
            "strength": self.strength,
            "nonlinear_tolerance": self.nonlinear_tolerance,
            "linear_tolerance": self.linear_tolerance,
            "max_iterations": self.max_iterations,
            "field_exchange_frequency": self.field_exchange_frequency,
            "geometry_feedback_interval": self.geometry_feedback_interval,
            "thermal_feedback_interval": self.thermal_feedback_interval,
            "electrical_feedback_interval": self.electrical_feedback_interval,
            "time_resolution_s": self.time_resolution_s,
            "precice_acceleration": self.precice_acceleration,
            "dynamic_activation": self.dynamic_activation,
            "em_escalation": self.em_escalation,
            "mesh_update_threshold": self.mesh_update_threshold,
            "overrides_applied": [list(item) for item in self.overrides_applied],
        }


_EXPERT_FIELDS = (
    "nonlinear_tolerance",
    "linear_tolerance",
    "max_iterations",
    "field_exchange_frequency",
    "geometry_feedback_interval",
    "thermal_feedback_interval",
    "electrical_feedback_interval",
    "time_resolution_s",
    "precice_acceleration",
    "dynamic_activation",
    "em_escalation",
    "mesh_update_threshold",
)


def _lerp(loose: float, tight: float, strength: float) -> float:
    return loose + (tight - loose) * strength


def expand_coupling_strength(
    strength: float, overrides: Mapping[str, object] | None = None
) -> ExpertPolicy:
    """Expand a 0..1 coupling strength into persisted expert parameters."""

    if (
        isinstance(strength, bool)
        or not isfinite(strength)
        or not 0.0 <= strength <= 1.0
    ):
        raise ValueError("INVALID_COUPLING_STRENGTH")
    derived: dict[str, object] = {
        "nonlinear_tolerance": _lerp(1e-3, 1e-8, strength),
        "linear_tolerance": _lerp(1e-4, 1e-10, strength),
        "max_iterations": int(round(_lerp(10.0, 100.0, strength))),
        "field_exchange_frequency": int(round(_lerp(1.0, 10.0, strength))),
        "geometry_feedback_interval": int(round(_lerp(10.0, 1.0, strength))),
        "thermal_feedback_interval": int(round(_lerp(10.0, 1.0, strength))),
        "electrical_feedback_interval": int(round(_lerp(10.0, 1.0, strength))),
        "time_resolution_s": _lerp(1e-2, 1e-4, strength),
        "precice_acceleration": "fixed" if strength < 0.33 else (
            "aitken" if strength < 0.66 else "iqn-ils"
        ),
        "dynamic_activation": strength >= 0.5,
        "em_escalation": strength >= 0.66,
        "mesh_update_threshold": _lerp(1e-2, 1e-5, strength),
    }
    applied: list[tuple[str, object]] = []
    for name, value in dict(overrides or {}).items():
        if name not in _EXPERT_FIELDS:
            raise ValueError(f"UNKNOWN_EXPERT_PARAMETER:{name}")
        expected = type(derived[name])
        if not isinstance(value, expected) or isinstance(value, bool) != isinstance(
            derived[name], bool
        ):
            raise ValueError(f"INVALID_EXPERT_OVERRIDE:{name}")
        derived[name] = value
        applied.append((name, value))
    payload = json.dumps(
        {"strength": strength, **{k: derived[k] for k in _EXPERT_FIELDS}},
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        default=str,
    ).encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    return ExpertPolicy(
        strength=strength,
        nonlinear_tolerance=float(derived["nonlinear_tolerance"]),  # type: ignore[arg-type]
        linear_tolerance=float(derived["linear_tolerance"]),  # type: ignore[arg-type]
        max_iterations=int(derived["max_iterations"]),  # type: ignore[arg-type]
        field_exchange_frequency=int(derived["field_exchange_frequency"]),  # type: ignore[arg-type]
        geometry_feedback_interval=int(derived["geometry_feedback_interval"]),  # type: ignore[arg-type]
        thermal_feedback_interval=int(derived["thermal_feedback_interval"]),  # type: ignore[arg-type]
        electrical_feedback_interval=int(derived["electrical_feedback_interval"]),  # type: ignore[arg-type]
        time_resolution_s=float(derived["time_resolution_s"]),  # type: ignore[arg-type]
        precice_acceleration=str(derived["precice_acceleration"]),
        dynamic_activation=bool(derived["dynamic_activation"]),
        em_escalation=bool(derived["em_escalation"]),
        mesh_update_threshold=float(derived["mesh_update_threshold"]),  # type: ignore[arg-type]
        overrides_applied=tuple(applied),
        digest=digest,
    )
