"""Shaft/spool graph: arbitrary spools and their mechanical/electrical couplings."""

from __future__ import annotations

from dataclasses import dataclass

from .units import Quantity, require_dimension

SHAFT_KINDS: tuple[str, ...] = ("single", "common", "free_power")

COUPLING_KINDS: tuple[str, ...] = (
    "common_shaft",
    "geared",
    "electric_motor",
    "electric_generator",
    "mechanical_load",
)

_COUPLING_TARGET_NODE_KIND = {
    "electric_motor": "motor_coupling",
    "electric_generator": "generator_coupling",
    "mechanical_load": "mechanical_load",
}


@dataclass(frozen=True, slots=True)
class SpeedBound:
    """An imposed rotational speed or shaft torque."""

    kind: str
    value: Quantity

    def __post_init__(self) -> None:
        if self.kind == "speed":
            require_dimension(self.value, "rotational_speed", "speed")
        elif self.kind == "torque":
            require_dimension(self.value, "torque", "torque")
        else:
            raise ValueError(f"UNKNOWN_SPEED_BOUND_KIND:{self.kind}")

    def canonical(self) -> dict[str, object]:
        return {"kind": self.kind, "value": self.value.canonical()}


@dataclass(frozen=True, slots=True)
class ShaftCoupling:
    """One coupling from a shaft to another shaft or to a load/machine node."""

    coupling_id: str
    kind: str
    target_shaft: str | None = None
    target_node: str | None = None
    ratio: float | None = None
    efficiency: float | None = None

    def __post_init__(self) -> None:
        if not self.coupling_id.strip():
            raise ValueError("COUPLING_ID_REQUIRED")
        if self.kind not in COUPLING_KINDS:
            raise ValueError(f"UNKNOWN_COUPLING_KIND:{self.kind}")
        if self.kind in ("common_shaft", "geared"):
            if not self.target_shaft:
                raise ValueError(f"COUPLING_NEEDS_TARGET_SHAFT:{self.coupling_id}")
            if self.target_node:
                raise ValueError(f"SHAFT_COUPLING_HAS_NODE_TARGET:{self.coupling_id}")
            if self.kind == "geared":
                if self.ratio is None or self.ratio <= 0:
                    raise ValueError(f"GEARED_COUPLING_NEEDS_POSITIVE_RATIO:{self.coupling_id}")
            elif self.ratio is not None:
                raise ValueError(f"COMMON_SHAFT_COUPLING_HAS_RATIO:{self.coupling_id}")
        else:
            if not self.target_node:
                raise ValueError(f"COUPLING_NEEDS_TARGET_NODE:{self.coupling_id}")
            if self.target_shaft:
                raise ValueError(f"MACHINE_COUPLING_HAS_SHAFT_TARGET:{self.coupling_id}")
        if self.ratio is not None and self.ratio <= 0:
            raise ValueError(f"INVALID_COUPLING_RATIO:{self.coupling_id}")
        if self.efficiency is not None and not 0 < self.efficiency <= 1:
            raise ValueError(f"INVALID_COUPLING_EFFICIENCY:{self.coupling_id}")

    @property
    def expected_target_node_kind(self) -> str | None:
        return _COUPLING_TARGET_NODE_KIND.get(self.kind)

    def canonical(self) -> dict[str, object]:
        return {
            "id": self.coupling_id,
            "kind": self.kind,
            "targetShaft": self.target_shaft,
            "targetNode": self.target_node,
            "ratio": None if self.ratio is None else self.ratio,
            "efficiency": None if self.efficiency is None else self.efficiency,
        }


@dataclass(frozen=True, slots=True)
class Shaft:
    """One shaft/spool with its row members, speed bound, and couplings."""

    shaft_id: str
    kind: str
    members: tuple[str, ...] = ()
    speed: SpeedBound | None = None
    mechanical_loss_fraction: float = 0.0
    couplings: tuple[ShaftCoupling, ...] = ()

    def __post_init__(self) -> None:
        if not self.shaft_id.strip():
            raise ValueError("SHAFT_ID_REQUIRED")
        if self.kind not in SHAFT_KINDS:
            raise ValueError(f"UNKNOWN_SHAFT_KIND:{self.kind}")
        if len(self.members) != len(set(self.members)):
            raise ValueError(f"DUPLICATE_SHAFT_MEMBER:{self.shaft_id}")
        for member in self.members:
            if not member.strip():
                raise ValueError(f"SHAFT_MEMBER_REQUIRED:{self.shaft_id}")
        if not 0 <= self.mechanical_loss_fraction < 1:
            raise ValueError(f"INVALID_MECHANICAL_LOSS_FRACTION:{self.shaft_id}")
        identifiers = [coupling.coupling_id for coupling in self.couplings]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError(f"DUPLICATE_COUPLING:{self.shaft_id}")

    def canonical(self) -> dict[str, object]:
        return {
            "id": self.shaft_id,
            "kind": self.kind,
            "members": sorted(self.members),
            "speed": None if self.speed is None else self.speed.canonical(),
            "mechanicalLossFraction": self.mechanical_loss_fraction,
            "couplings": [
                coupling.canonical()
                for coupling in sorted(self.couplings, key=lambda c: c.coupling_id)
            ],
        }
