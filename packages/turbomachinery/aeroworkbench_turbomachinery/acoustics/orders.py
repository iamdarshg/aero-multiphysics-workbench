"""Rotating-order forcing derived from actual rows, frames, and shaft speeds.

Every order is derived from the declared architecture: shaft orders from the
shaft speed, blade- and vane-passing orders from ``BladeRow.periodicity``,
rotor-stator interaction families from adjacent rotating/stationary rows, and
multi-shaft sidebands from distinct shaft speeds. No blade count is ever
hard-coded and no order is invented: an architecture with no rows produces no
orders.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from math import isfinite
from typing import Any

from ..architecture import RotatingGasArchitecture, architecture_from_payload
from ..canonical import content_digest
from ..rows import BladeRow
from .errors import AcousticInputError

__all__ = [
    "OrderFamily",
    "OrderSpectrum",
    "OrderTerm",
    "RotatingOrder",
    "derive_order_spectrum",
    "shaft_speeds_rpm",
]


class OrderFamily(StrEnum):
    """The physical family a rotating-order line belongs to."""

    SHAFT = "shaft"
    BLADE_PASSING = "blade-passing"
    VANE_PASSING = "vane-passing"
    ROTOR_STATOR = "rotor-stator-interaction"
    MULTI_SHAFT_SIDEBAND = "multi-shaft-sideband"


@dataclass(frozen=True, slots=True)
class OrderTerm:
    """One shaft/order contribution; a sideband combines several terms."""

    shaft: str
    order: float

    def __post_init__(self) -> None:
        if not self.shaft.strip():
            raise AcousticInputError("order term shaft is required")
        value = float(self.order)
        if not isfinite(value):
            raise AcousticInputError("order term order must be finite")

    def canonical(self) -> dict[str, Any]:
        return {"shaft": self.shaft, "order": self.order}


def _finite_speed(speeds_rpm: Mapping[str, float], shaft: str) -> float:
    if shaft not in speeds_rpm:
        raise AcousticInputError(f"missing shaft speed for {shaft}")
    value = speeds_rpm[shaft]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AcousticInputError(f"shaft speed for {shaft} must be a number")
    number = float(value)
    if not isfinite(number) or number < 0.0:
        raise AcousticInputError(f"shaft speed for {shaft} must be finite and non-negative")
    return number


@dataclass(frozen=True, slots=True)
class RotatingOrder:
    """One deterministic rotating-order line derived from the architecture."""

    order_id: str
    family: OrderFamily
    terms: tuple[OrderTerm, ...]
    harmonic: int = 1
    contributing_rows: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.order_id.strip():
            raise AcousticInputError("rotating order id is required")
        if not self.terms:
            raise AcousticInputError(f"rotating order {self.order_id} needs at least one term")
        if self.harmonic < 1:
            raise AcousticInputError(f"rotating order {self.order_id} harmonic must be >= 1")
        ordered = tuple(sorted(self.terms, key=lambda term: (term.shaft, term.order)))
        object.__setattr__(self, "terms", ordered)
        object.__setattr__(self, "contributing_rows", tuple(sorted(set(self.contributing_rows))))

    @property
    def primary_shaft(self) -> str:
        return self.terms[0].shaft

    @property
    def order(self) -> float:
        """Magnitude of the leading term (cycles per revolution of that shaft)."""

        return abs(self.terms[0].order)

    def frequency_hz(self, speeds_rpm: Mapping[str, float]) -> float:
        """Resolve this order to a frequency at the declared shaft speeds."""

        total = 0.0
        for term in self.terms:
            speed = _finite_speed(speeds_rpm, term.shaft)
            total += term.order * speed / 60.0
        return abs(total)

    def canonical(self) -> dict[str, Any]:
        return {
            "orderId": self.order_id,
            "family": self.family.value,
            "terms": [term.canonical() for term in self.terms],
            "harmonic": self.harmonic,
            "contributingRows": list(self.contributing_rows),
        }

    @property
    def digest(self) -> str:
        return content_digest(self.canonical())


@dataclass(frozen=True, slots=True)
class OrderSpectrum:
    """A deterministic, hashable set of rotating-order lines for one architecture."""

    architecture_id: str
    architecture_hash: str
    shaft_speeds_rpm: tuple[tuple[str, float], ...]
    orders: tuple[RotatingOrder, ...]
    harmonics: int = 1
    include_sidebands: bool = True

    def __post_init__(self) -> None:
        if not self.architecture_id.strip():
            raise AcousticInputError("order spectrum architecture_id is required")
        if len(self.architecture_hash) != 64:
            raise AcousticInputError(
                "order spectrum architecture_hash must be a sha-256 hex digest"
            )
        if self.harmonics < 1:
            raise AcousticInputError("order spectrum harmonics must be >= 1")
        speeds = tuple(sorted(self.shaft_speeds_rpm))
        for shaft, speed in speeds:
            if not shaft.strip():
                raise AcousticInputError("order spectrum shaft id is required")
            number = float(speed)
            if not isfinite(number) or number < 0.0:
                raise AcousticInputError(
                    f"order spectrum speed for {shaft} must be finite and non-negative"
                )
        object.__setattr__(self, "shaft_speeds_rpm", speeds)
        identifiers = [order.order_id for order in self.orders]
        if len(identifiers) != len(set(identifiers)):
            raise AcousticInputError("order spectrum has duplicate order ids")
        object.__setattr__(
            self,
            "orders",
            tuple(
                sorted(
                    self.orders,
                    key=lambda order: (order.family.value, order.order_id),
                )
            ),
        )

    def speed_map(self) -> dict[str, float]:
        return dict(self.shaft_speeds_rpm)

    def families(self) -> tuple[OrderFamily, ...]:
        present = {order.family for order in self.orders}
        return tuple(family for family in OrderFamily if family in present)

    def orders_for_family(self, family: OrderFamily) -> tuple[RotatingOrder, ...]:
        return tuple(order for order in self.orders if order.family is family)

    def frequencies_hz(self) -> tuple[tuple[str, float], ...]:
        speeds = self.speed_map()
        return tuple((order.order_id, order.frequency_hz(speeds)) for order in self.orders)

    def canonical(self) -> dict[str, Any]:
        return {
            "architectureId": self.architecture_id,
            "architectureHash": self.architecture_hash,
            "shaftSpeedsRpm": [[shaft, speed] for shaft, speed in self.shaft_speeds_rpm],
            "harmonics": self.harmonics,
            "includeSidebands": self.include_sidebands,
            "orders": [order.canonical() for order in self.orders],
        }

    @property
    def digest(self) -> str:
        return content_digest(self.canonical())


def _as_architecture(
    value: RotatingGasArchitecture | Mapping[str, Any],
) -> RotatingGasArchitecture:
    if isinstance(value, RotatingGasArchitecture):
        return value
    return architecture_from_payload(value)


def shaft_speeds_rpm(
    value: RotatingGasArchitecture | Mapping[str, Any],
) -> tuple[tuple[str, float], ...]:
    """Declared rotational speeds in rpm for every speed-bound shaft, sorted."""

    architecture = _as_architecture(value)
    speeds: list[tuple[str, float]] = []
    for shaft in architecture.shafts:
        if shaft.speed is not None and shaft.speed.kind == "speed":
            speeds.append((shaft.shaft_id, shaft.speed.value.value_si * 60.0))
    return tuple(sorted(speeds))


def _rows_adjacent(first: BladeRow, second: BladeRow) -> bool:
    return bool(
        {first.station_in, first.station_out} & {second.station_in, second.station_out}
    )


def _add(
    collected: dict[str, RotatingOrder],
    order: RotatingOrder,
) -> None:
    collected.setdefault(order.order_id, order)


def derive_order_spectrum(
    value: RotatingGasArchitecture | Mapping[str, Any],
    *,
    harmonics: int = 1,
    include_sidebands: bool = True,
) -> OrderSpectrum:
    """Derive the rotating-order spectrum from an architecture's actual topology."""

    if harmonics < 1:
        raise AcousticInputError("harmonics must be >= 1")
    architecture = _as_architecture(value)
    speeds = dict(shaft_speeds_rpm(architecture))
    rotating_rows = [row for row in architecture.rows if row.frame == "rotating"]
    stationary_rows = [row for row in architecture.rows if row.frame == "stationary"]
    collected: dict[str, RotatingOrder] = {}

    for shaft in architecture.shafts:
        if shaft.shaft_id not in speeds:
            continue
        for index in range(1, harmonics + 1):
            _add(
                collected,
                RotatingOrder(
                    order_id=f"shaft:{shaft.shaft_id}:h{index}",
                    family=OrderFamily.SHAFT,
                    terms=(OrderTerm(shaft.shaft_id, float(index)),),
                    harmonic=index,
                ),
            )

    for row in rotating_rows:
        blades = row.periodicity
        for index in range(1, harmonics + 1):
            _add(
                collected,
                RotatingOrder(
                    order_id=f"blade:{row.row_id}:h{index}",
                    family=OrderFamily.BLADE_PASSING,
                    terms=(OrderTerm(row.shaft or row.row_id, float(index * blades)),),
                    harmonic=index,
                    contributing_rows=(row.row_id,),
                ),
            )

    for rotor in rotating_rows:
        rotor_shaft = rotor.shaft or rotor.row_id
        for stator in stationary_rows:
            if not _rows_adjacent(rotor, stator):
                continue
            vanes = stator.periodicity
            for index in range(1, harmonics + 1):
                _add(
                    collected,
                    RotatingOrder(
                        order_id=f"vane:{stator.row_id}:rotor:{rotor.row_id}:h{index}",
                        family=OrderFamily.VANE_PASSING,
                        terms=(OrderTerm(rotor_shaft, float(index * vanes)),),
                        harmonic=index,
                        contributing_rows=(rotor.row_id, stator.row_id),
                    ),
                )
            for m in range(1, harmonics + 1):
                for n in range(1, harmonics + 1):
                    for sign, tag in ((1.0, "p"), (-1.0, "m")):
                        combined = m * rotor.periodicity + sign * n * vanes
                        if combined <= 0.0:
                            continue
                        _add(
                            collected,
                            RotatingOrder(
                                order_id=f"rs:{rotor.row_id}:{stator.row_id}:m{m}n{n}:{tag}",
                                family=OrderFamily.ROTOR_STATOR,
                                terms=(OrderTerm(rotor_shaft, combined),),
                                harmonic=max(m, n),
                                contributing_rows=(rotor.row_id, stator.row_id),
                            ),
                        )

    if include_sidebands and len(speeds) >= 2:
        dominant = {
            shaft_id: max(
                (row.periodicity for row in rotating_rows if row.shaft == shaft_id),
                default=0,
            )
            for shaft_id in speeds
            if any(row.shaft == shaft_id for row in rotating_rows)
        }
        rotating_shafts = sorted(dominant)
        for first_index, first in enumerate(rotating_shafts):
            for second in rotating_shafts[first_index + 1 :]:
                first_blades = dominant[first]
                second_blades = dominant[second]
                for index in range(1, harmonics + 1):
                    combos = (
                        (
                            OrderTerm(first, float(first_blades)),
                            OrderTerm(second, float(index)),
                            "bp",
                        ),
                        (
                            OrderTerm(first, float(first_blades)),
                            OrderTerm(second, -float(index)),
                            "bm",
                        ),
                        (
                            OrderTerm(first, float(index)),
                            OrderTerm(second, float(second_blades)),
                            "ap",
                        ),
                        (
                            OrderTerm(first, -float(index)),
                            OrderTerm(second, float(second_blades)),
                            "am",
                        ),
                    )
                    for first_term, second_term, tag in combos:
                        _add(
                            collected,
                            RotatingOrder(
                                order_id=f"sb:{first}:{second}:h{index}:{tag}",
                                family=OrderFamily.MULTI_SHAFT_SIDEBAND,
                                terms=(first_term, second_term),
                                harmonic=index,
                                contributing_rows=tuple(
                                    sorted(
                                        row.row_id
                                        for row in rotating_rows
                                        if row.shaft in (first, second)
                                    )
                                ),
                            ),
                        )

    return OrderSpectrum(
        architecture_id=architecture.architecture_id,
        architecture_hash=architecture.architecture_hash,
        shaft_speeds_rpm=tuple(sorted(speeds.items())),
        orders=tuple(collected.values()),
        harmonics=harmonics,
        include_sidebands=include_sidebands,
    )
