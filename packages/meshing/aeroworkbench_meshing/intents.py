"""Physics-aware mesh intent derived from flow regime and expected gradients.

Intent is *generic* and tied to semantic geometry keys, never to application
region names. A :class:`PhysicsIntent` names a mesh mechanism (near-wall,
leading/trailing edge, tip gap, wake, shock, sliding interface, jet, contact,
thermal interface, thin structure, ...) and the semantic keys it applies to.
Physics state and typed rotating-machine primitives are mapped to intents so the
same machinery serves external aero, open/ducted propulsors, turbomachinery,
structures, and thermal problems without product-specific core logic.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from math import isfinite
from typing import Protocol

from aeroworkbench_mesh import SemanticTopologyReceipt

from .contracts import content_digest
from .errors import MeshContractError

__all__ = [
    "BladeClearanceLike",
    "BladeRowLike",
    "FlowRegime",
    "PhysicsIntent",
    "PhysicsIntentKind",
    "PhysicsState",
    "PropellerGeometryLike",
    "QuantityLike",
    "intent_digest",
    "intents_from_blade_rows",
    "intents_from_physics",
    "intents_from_propeller",
]


class QuantityLike(Protocol):
    """Structural view of a unit-bearing scalar (e.g. turbomachinery Quantity)."""

    @property
    def value_si(self) -> float: ...


class BladeClearanceLike(Protocol):
    """Structural view of a blade-row clearance contract."""

    @property
    def tip_clearance(self) -> QuantityLike | None: ...


class BladeRowLike(Protocol):
    """Structural view of a turbomachinery blade row (no product assumptions)."""

    @property
    def row_id(self) -> str: ...

    @property
    def role(self) -> str: ...

    @property
    def frame(self) -> str: ...

    @property
    def clearance(self) -> BladeClearanceLike: ...


class PropellerGeometryLike(Protocol):
    """Structural view of a propulsor rotor geometry primitive."""

    @property
    def rotor_id(self) -> str: ...

    @property
    def coaxial(self) -> bool: ...


class PhysicsIntentKind(StrEnum):
    """Generic mesh mechanisms a participant can request."""

    NEAR_WALL = "near_wall"
    LEADING_EDGE = "leading_edge"
    TRAILING_EDGE = "trailing_edge"
    TIP_GAP = "tip_gap"
    ROOT_GAP = "root_gap"
    WAKE = "wake"
    SLIPSTREAM = "slipstream"
    SHEAR_LAYER = "shear_layer"
    SHOCK = "shock"
    ROTATING_INTERFACE = "rotating_interface"
    SLIDING_INTERFACE = "sliding_interface"
    INTERACTION_REGION = "interaction_region"
    JET = "jet"
    NOZZLE = "nozzle"
    CONTACT = "contact"
    STRESS_CONCENTRATOR = "stress_concentrator"
    THERMAL_GRADIENT = "thermal_gradient"
    THERMAL_INTERFACE = "thermal_interface"
    THIN_STRUCTURE = "thin_structure"
    GAP = "gap"
    CURVATURE = "curvature"
    FEATURE = "feature"


class FlowRegime(StrEnum):
    """Declared flow regime that drives physics-based refinement."""

    LOW_SPEED = "low_speed"
    INCOMPRESSIBLE = "incompressible"
    COMPRESSIBLE_SUBSONIC = "compressible_subsonic"
    TRANSONIC = "transonic"
    SUPERSONIC = "supersonic"
    HYPERSONIC = "hypersonic"


_COMPRESSIBLE_REGIMES = frozenset(
    {
        FlowRegime.COMPRESSIBLE_SUBSONIC,
        FlowRegime.TRANSONIC,
        FlowRegime.SUPERSONIC,
        FlowRegime.HYPERSONIC,
    }
)
_SHOCK_REGIMES = frozenset(
    {FlowRegime.TRANSONIC, FlowRegime.SUPERSONIC, FlowRegime.HYPERSONIC}
)


def _opt_finite(label: str, value: float | None, *, positive: bool = False) -> None:
    if value is None:
        return
    if not isfinite(value):
        raise MeshContractError(f"NONFINITE_PHYSICS_{label.upper()}")
    if positive and value <= 0.0:
        raise MeshContractError(f"PHYSICS_{label.upper()}_MUST_BE_POSITIVE")


@dataclass(frozen=True, slots=True)
class PhysicsState:
    """Typed physical context used to derive refinement intent.

    Only declared, finite values are accepted; a missing value simply produces
    no derived intent for that mechanism instead of a fabricated default.
    """

    regime: FlowRegime
    mach: float | None = None
    reynolds: float | None = None
    gradient_scale_mm: float | None = None
    wake_thickness_mm: float | None = None
    shock_strength: float | None = None
    thermal_gradient_k_mm: float | None = None
    structural_thickness_mm: float | None = None
    tip_clearance_mm: float | None = None
    curvature_radius_mm: float | None = None
    contact_length_mm: float | None = None
    friction_velocity_m_s: float | None = None
    density_kg_m3: float | None = None
    dynamic_viscosity_pa_s: float | None = None

    def __post_init__(self) -> None:
        _opt_finite("mach", self.mach)
        _opt_finite("reynolds", self.reynolds)
        _opt_finite("gradient_scale", self.gradient_scale_mm, positive=True)
        _opt_finite("wake_thickness", self.wake_thickness_mm, positive=True)
        _opt_finite("shock_strength", self.shock_strength)
        _opt_finite("thermal_gradient", self.thermal_gradient_k_mm, positive=True)
        _opt_finite("structural_thickness", self.structural_thickness_mm, positive=True)
        _opt_finite("tip_clearance", self.tip_clearance_mm, positive=True)
        _opt_finite("curvature_radius", self.curvature_radius_mm, positive=True)
        _opt_finite("contact_length", self.contact_length_mm, positive=True)
        _opt_finite("friction_velocity", self.friction_velocity_m_s, positive=True)
        _opt_finite("density", self.density_kg_m3, positive=True)
        _opt_finite("dynamic_viscosity", self.dynamic_viscosity_pa_s, positive=True)
        if self.shock_strength is not None and not 0.0 <= self.shock_strength <= 1.0:
            raise MeshContractError("SHOCK_STRENGTH_OUT_OF_RANGE")

    def compressible(self) -> bool:
        return self.regime in _COMPRESSIBLE_REGIMES

    def shock_prone(self) -> bool:
        return (
            self.regime in _SHOCK_REGIMES
            and self.shock_strength is not None
            and self.shock_strength > 0.0
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "regime": self.regime.value,
            "mach": self.mach,
            "reynolds": self.reynolds,
            "gradientScaleMm": self.gradient_scale_mm,
            "wakeThicknessMm": self.wake_thickness_mm,
            "shockStrength": self.shock_strength,
            "thermalGradientKmm": self.thermal_gradient_k_mm,
            "structuralThicknessMm": self.structural_thickness_mm,
            "tipClearanceMm": self.tip_clearance_mm,
            "curvatureRadiusMm": self.curvature_radius_mm,
            "contactLengthMm": self.contact_length_mm,
            "frictionVelocityMS": self.friction_velocity_m_s,
            "densityKgM3": self.density_kg_m3,
            "dynamicViscosityPaS": self.dynamic_viscosity_pa_s,
        }


@dataclass(frozen=True, slots=True)
class PhysicsIntent:
    """One generic refinement intent bound to semantic geometry keys."""

    kind: PhysicsIntentKind
    semantic_keys: tuple[str, ...]
    target_size_mm: float | None = None
    priority: int = 0
    detail: str = ""

    def __post_init__(self) -> None:
        if not self.semantic_keys:
            raise MeshContractError(f"INTENT_NEEDS_SEMANTIC_KEYS:{self.kind.value}")
        for key in self.semantic_keys:
            if not key.strip():
                raise MeshContractError(f"INTENT_EMPTY_SEMANTIC_KEY:{self.kind.value}")
        if self.target_size_mm is not None and (
            not isfinite(self.target_size_mm) or self.target_size_mm <= 0.0
        ):
            raise MeshContractError(f"INTENT_SIZE_INVALID:{self.kind.value}")
        if self.priority < 0:
            raise MeshContractError(f"INTENT_PRIORITY_INVALID:{self.kind.value}")

    def as_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind.value,
            "semanticKeys": list(self.semantic_keys),
            "targetSizeMm": self.target_size_mm,
            "priority": self.priority,
            "detail": self.detail,
        }


def _sorted_intents(intents: Sequence[PhysicsIntent]) -> tuple[PhysicsIntent, ...]:
    return tuple(
        sorted(
            intents,
            key=lambda item: (item.kind.value, item.semantic_keys, item.priority),
        )
    )


def intent_digest(intents: Sequence[PhysicsIntent]) -> str:
    """Deterministic content digest of an intent set."""

    return content_digest([intent.as_dict() for intent in _sorted_intents(intents)])


def intents_from_physics(
    state: PhysicsState, topology: SemanticTopologyReceipt
) -> tuple[PhysicsIntent, ...]:
    """Derive generic intents from physics state plus semantic topology.

    Region-kind entities become fluid/solid intents, boundary entities become
    near-wall/thermal intents, and interfaces become rotating/sliding or thermal
    intents. Nothing is keyed by application region name.
    """

    intents: list[PhysicsIntent] = []
    for entity in topology.entities:
        key = entity.semantic_key
        kind = entity.kind
        if kind == "wall":
            intents.append(
                PhysicsIntent(PhysicsIntentKind.NEAR_WALL, (key,), None, 0, "wall")
            )
        elif kind in ("fluid_region", "rotating_region", "stationary_region"):
            if state.shock_prone():
                intents.append(
                    PhysicsIntent(
                        PhysicsIntentKind.SHOCK,
                        (key,),
                        None,
                        2,
                        f"regime={state.regime.value}",
                    )
                )
            if state.wake_thickness_mm is not None:
                intents.append(
                    PhysicsIntent(PhysicsIntentKind.WAKE, (key,), None, 1, "wake thickness")
                )
            if state.gradient_scale_mm is not None:
                intents.append(
                    PhysicsIntent(
                        PhysicsIntentKind.SHEAR_LAYER,
                        (key,),
                        None,
                        1,
                        "expected gradient scale",
                    )
                )
            if kind == "rotating_region":
                intents.append(
                    PhysicsIntent(
                        PhysicsIntentKind.ROTATING_INTERFACE,
                        (key,),
                        None,
                        2,
                        "rotating frame",
                    )
                )
        elif kind in ("interface", "fsi_interface", "cht_interface", "thermal_contact"):
            if state.thermal_gradient_k_mm is not None:
                intents.append(
                    PhysicsIntent(
                        PhysicsIntentKind.THERMAL_INTERFACE,
                        (key,),
                        None,
                        1,
                        "thermal coupling",
                    )
                )
            else:
                intents.append(
                    PhysicsIntent(
                        PhysicsIntentKind.SLIDING_INTERFACE,
                        (key,),
                        None,
                        1,
                        "field-coupling interface",
                    )
                )
        elif kind in ("solid_region", "material_assignment"):
            if state.structural_thickness_mm is not None:
                intents.append(
                    PhysicsIntent(
                        PhysicsIntentKind.THIN_STRUCTURE,
                        (key,),
                        None,
                        1,
                        "structural thickness",
                    )
                )
            if state.thermal_gradient_k_mm is not None:
                intents.append(
                    PhysicsIntent(
                        PhysicsIntentKind.THERMAL_GRADIENT,
                        (key,),
                        None,
                        1,
                        "thermal gradient",
                    )
                )
        if state.contact_length_mm is not None and kind in (
            "mechanical_constraint",
            "solid_region",
        ):
            intents.append(
                PhysicsIntent(PhysicsIntentKind.CONTACT, (key,), None, 1, "contact region")
            )
        if state.tip_clearance_mm is not None and kind in ("wall", "rotating_region"):
            intents.append(
                PhysicsIntent(PhysicsIntentKind.TIP_GAP, (key,), None, 2, "tip clearance")
            )
        if state.curvature_radius_mm is not None and kind in ("wall", "fluid_region"):
            intents.append(
                PhysicsIntent(PhysicsIntentKind.CURVATURE, (key,), None, 1, "surface curvature")
            )
    return _sorted_intents(intents)


def intents_from_blade_rows(
    rows: Sequence[BladeRowLike],
    *,
    edge_size_mm: float | None = None,
    wake_size_mm: float | None = None,
    gap_size_mm: float | None = None,
    cells_across_gap: int = 8,
) -> tuple[PhysicsIntent, ...]:
    """Map typed blade rows to generic intents (LE/TE, tip gap, wake, sliding)."""

    if cells_across_gap < 1:
        raise MeshContractError("CELLS_ACROSS_GAP_MUST_BE_POSITIVE")
    intents: list[PhysicsIntent] = []
    for row in rows:
        intents.append(
            PhysicsIntent(
                PhysicsIntentKind.LEADING_EDGE,
                (f"{row.row_id}:leading_edge",),
                edge_size_mm,
                2,
                "blade leading edge",
            )
        )
        intents.append(
            PhysicsIntent(
                PhysicsIntentKind.TRAILING_EDGE,
                (f"{row.row_id}:trailing_edge",),
                edge_size_mm,
                2,
                "blade trailing edge",
            )
        )
        clearance = row.clearance.tip_clearance
        if clearance is not None:
            tip_mm = clearance.value_si * 1000.0
            size = gap_size_mm if gap_size_mm is not None else tip_mm / cells_across_gap
            intents.append(
                PhysicsIntent(
                    PhysicsIntentKind.TIP_GAP,
                    (f"{row.row_id}:tip_gap",),
                    size,
                    3,
                    "tip clearance",
                )
            )
        if row.role in ("work_adding", "work_extracting"):
            intents.append(
                PhysicsIntent(
                    PhysicsIntentKind.WAKE,
                    (f"{row.row_id}:wake",),
                    wake_size_mm,
                    1,
                    "rotor wake",
                )
            )
        if row.frame == "rotating":
            intents.append(
                PhysicsIntent(
                    PhysicsIntentKind.ROTATING_INTERFACE,
                    (f"{row.row_id}:sliding_interface",),
                    None,
                    2,
                    "rotor-stator sliding interface",
                )
            )
    return _sorted_intents(intents)


def intents_from_propeller(
    geometry: PropellerGeometryLike,
    *,
    edge_size_mm: float | None = None,
    wake_size_mm: float | None = None,
    tip_gap_mm: float | None = None,
    cells_across_gap: int = 8,
) -> tuple[PhysicsIntent, ...]:
    """Map a typed propeller geometry to generic open/ducted propulsor intents."""

    if cells_across_gap < 1:
        raise MeshContractError("CELLS_ACROSS_GAP_MUST_BE_POSITIVE")
    rotor = geometry.rotor_id
    intents: list[PhysicsIntent] = [
        PhysicsIntent(
            PhysicsIntentKind.LEADING_EDGE,
            (f"{rotor}:leading_edge",),
            edge_size_mm,
            2,
            "blade leading edge",
        ),
        PhysicsIntent(
            PhysicsIntentKind.TRAILING_EDGE,
            (f"{rotor}:trailing_edge",),
            edge_size_mm,
            2,
            "blade trailing edge",
        ),
        PhysicsIntent(
            PhysicsIntentKind.SLIPSTREAM,
            (f"{rotor}:slipstream",),
            wake_size_mm,
            1,
            "open-propeller wake/slipstream",
        ),
    ]
    if tip_gap_mm is not None:
        intents.append(
            PhysicsIntent(
                PhysicsIntentKind.TIP_GAP,
                (f"{rotor}:tip_gap",),
                tip_gap_mm / cells_across_gap,
                3,
                "tip clearance",
            )
        )
    if geometry.coaxial:
        intents.append(
            PhysicsIntent(
                PhysicsIntentKind.INTERACTION_REGION,
                (f"{rotor}:coaxial_interaction",),
                None,
                2,
                "coaxial/contra-rotating interaction region",
            )
        )
    return _sorted_intents(intents)
