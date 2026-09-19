"""Local resolution rules from feature, curvature, gap, wake, and gradient scales.

Local target size is derived from the *combination* of declared physical scales:
feature size, surface curvature, gap/clearance, wavelength or expected gradient
scale, wake thickness, a shock/refinement indicator, and structural thickness or
contact extent. The smallest applicable scale wins. A derivation that falls
below a declared mesher floor is flagged, never silently coarsened.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from math import isfinite

from .errors import MeshContractError
from .intents import PhysicsIntent, PhysicsIntentKind

__all__ = [
    "FeatureGeometry",
    "ResolutionConfig",
    "ResolutionDerivation",
    "ResolutionRule",
    "derive_local_size",
    "required_min_size_mm",
    "resolution_rules_from_intents",
]


@dataclass(frozen=True, slots=True)
class ResolutionConfig:
    """Cell-count and fraction constants for local resolution derivation."""

    cells_across_feature: int = 3
    cells_across_gap: int = 8
    cells_per_wavelength: int = 20
    cells_across_wake: int = 5
    cells_through_thickness: int = 3
    cells_across_contact: int = 4
    cells_per_gradient_scale: int = 10
    curvature_fraction: float = 0.5
    shock_refinement_fraction: float = 0.25

    def __post_init__(self) -> None:
        for label, value in (
            ("cells_across_feature", self.cells_across_feature),
            ("cells_across_gap", self.cells_across_gap),
            ("cells_per_wavelength", self.cells_per_wavelength),
            ("cells_across_wake", self.cells_across_wake),
            ("cells_through_thickness", self.cells_through_thickness),
            ("cells_across_contact", self.cells_across_contact),
            ("cells_per_gradient_scale", self.cells_per_gradient_scale),
        ):
            if value < 1:
                raise MeshContractError(f"RESOLUTION_{label.upper()}_INVALID")
        if not 0.0 < self.curvature_fraction <= 1.0:
            raise MeshContractError("RESOLUTION_CURVATURE_FRACTION_INVALID")
        if not 0.0 < self.shock_refinement_fraction <= 1.0:
            raise MeshContractError("RESOLUTION_SHOCK_FRACTION_INVALID")


@dataclass(frozen=True, slots=True)
class FeatureGeometry:
    """Declared geometric scales for one semantic feature (all optional)."""

    feature_size_mm: float | None = None
    curvature_radius_mm: float | None = None
    gap_mm: float | None = None
    wavelength_mm: float | None = None
    wake_thickness_mm: float | None = None
    shock_indicator: float | None = None
    structural_thickness_mm: float | None = None
    contact_length_mm: float | None = None
    gradient_scale_mm: float | None = None

    def __post_init__(self) -> None:
        for label, value in (
            ("feature_size", self.feature_size_mm),
            ("curvature_radius", self.curvature_radius_mm),
            ("gap", self.gap_mm),
            ("wavelength", self.wavelength_mm),
            ("wake_thickness", self.wake_thickness_mm),
            ("structural_thickness", self.structural_thickness_mm),
            ("contact_length", self.contact_length_mm),
            ("gradient_scale", self.gradient_scale_mm),
        ):
            if value is not None and (not isfinite(value) or value <= 0.0):
                raise MeshContractError(f"FEATURE_{label.upper()}_INVALID")
        if self.shock_indicator is not None and not 0.0 <= self.shock_indicator <= 1.0:
            raise MeshContractError("FEATURE_SHOCK_INDICATOR_INVALID")


@dataclass(frozen=True, slots=True)
class ResolutionDerivation:
    """Derived local size plus the drivers and candidates that produced it."""

    size_mm: float
    drivers: tuple[str, ...]
    candidates: tuple[tuple[str, float], ...]
    below_floor: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "sizeMm": self.size_mm,
            "drivers": list(self.drivers),
            "candidates": {name: value for name, value in self.candidates},
            "belowFloor": self.below_floor,
        }


def derive_local_size(
    base_size_mm: float,
    *,
    feature: FeatureGeometry | None = None,
    min_size_mm: float | None = None,
    config: ResolutionConfig | None = None,
) -> ResolutionDerivation:
    """Derive the smallest applicable local size for a declared feature."""

    if not isfinite(base_size_mm) or base_size_mm <= 0.0:
        raise MeshContractError("BASE_SIZE_MUST_BE_FINITE_POSITIVE")
    if min_size_mm is not None and (not isfinite(min_size_mm) or min_size_mm <= 0.0):
        raise MeshContractError("MIN_SIZE_MUST_BE_FINITE_POSITIVE")
    settings = config or ResolutionConfig()
    geometry = feature or FeatureGeometry()

    candidates: list[tuple[str, float]] = [("base", base_size_mm)]
    if geometry.feature_size_mm is not None:
        candidates.append(
            ("feature", geometry.feature_size_mm / settings.cells_across_feature)
        )
    if geometry.curvature_radius_mm is not None:
        candidates.append(
            ("curvature", settings.curvature_fraction * geometry.curvature_radius_mm)
        )
    if geometry.gap_mm is not None:
        candidates.append(("gap", geometry.gap_mm / settings.cells_across_gap))
    if geometry.wavelength_mm is not None:
        candidates.append(
            ("wavelength", geometry.wavelength_mm / settings.cells_per_wavelength)
        )
    if geometry.wake_thickness_mm is not None:
        candidates.append(
            ("wake", geometry.wake_thickness_mm / settings.cells_across_wake)
        )
    if geometry.shock_indicator is not None and geometry.shock_indicator > 0.0:
        factor = 1.0 - (1.0 - settings.shock_refinement_fraction) * geometry.shock_indicator
        candidates.append(("shock", base_size_mm * factor))
    if geometry.structural_thickness_mm is not None:
        candidates.append(
            ("structural", geometry.structural_thickness_mm / settings.cells_through_thickness)
        )
    if geometry.contact_length_mm is not None:
        candidates.append(
            ("contact", geometry.contact_length_mm / settings.cells_across_contact)
        )
    if geometry.gradient_scale_mm is not None:
        candidates.append(
            ("gradient", geometry.gradient_scale_mm / settings.cells_per_gradient_scale)
        )

    size = min(candidates, key=lambda item: item[1])[1]
    drivers = tuple(
        sorted(name for name, value in candidates if value <= size * (1.0 + 1e-12))
    )
    below_floor = min_size_mm is not None and size < min_size_mm
    return ResolutionDerivation(
        size_mm=size,
        drivers=drivers,
        candidates=tuple(sorted(candidates)),
        below_floor=below_floor,
    )


@dataclass(frozen=True, slots=True)
class ResolutionRule:
    """One local refinement rule bound to semantic keys."""

    name: str
    kind: PhysicsIntentKind
    semantic_keys: tuple[str, ...]
    size_mm: float
    drivers: tuple[str, ...]
    below_floor: bool

    def __post_init__(self) -> None:
        if not isfinite(self.size_mm) or self.size_mm <= 0.0:
            raise MeshContractError(f"RESOLUTION_RULE_SIZE_INVALID:{self.name}")

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "kind": self.kind.value,
            "semanticKeys": list(self.semantic_keys),
            "sizeMm": self.size_mm,
            "drivers": list(self.drivers),
            "belowFloor": self.below_floor,
        }


def _merge_features(
    features: Mapping[str, FeatureGeometry], keys: Sequence[str]
) -> FeatureGeometry | None:
    selected = [features[key] for key in keys if key in features]
    if not selected:
        return None

    def _min(attr: str) -> float | None:
        values = [getattr(item, attr) for item in selected]
        present = [value for value in values if value is not None]
        return min(present) if present else None

    shocks = [item.shock_indicator for item in selected if item.shock_indicator is not None]
    return FeatureGeometry(
        feature_size_mm=_min("feature_size_mm"),
        curvature_radius_mm=_min("curvature_radius_mm"),
        gap_mm=_min("gap_mm"),
        wavelength_mm=_min("wavelength_mm"),
        wake_thickness_mm=_min("wake_thickness_mm"),
        shock_indicator=max(shocks) if shocks else None,
        structural_thickness_mm=_min("structural_thickness_mm"),
        contact_length_mm=_min("contact_length_mm"),
        gradient_scale_mm=_min("gradient_scale_mm"),
    )


def resolution_rules_from_intents(
    intents: Sequence[PhysicsIntent],
    features: Mapping[str, FeatureGeometry],
    *,
    base_size_mm: float,
    min_size_mm: float | None = None,
    config: ResolutionConfig | None = None,
) -> tuple[ResolutionRule, ...]:
    """Derive one local rule per intent from its semantic feature geometry."""

    rules: list[ResolutionRule] = []
    seen: set[tuple[str, tuple[str, ...]]] = set()
    for intent in sorted(intents, key=lambda item: (item.kind.value, item.semantic_keys)):
        geometry = _merge_features(features, intent.semantic_keys)
        if geometry is None and intent.target_size_mm is None:
            continue
        signature = (intent.kind.value, intent.semantic_keys)
        if signature in seen:
            continue
        seen.add(signature)
        if geometry is None:
            size = intent.target_size_mm
            assert size is not None
            rules.append(
                ResolutionRule(
                    name=f"{intent.kind.value}:{'+'.join(intent.semantic_keys)}",
                    kind=intent.kind,
                    semantic_keys=intent.semantic_keys,
                    size_mm=size,
                    drivers=("intent_target",),
                    below_floor=min_size_mm is not None and size < min_size_mm,
                )
            )
            continue
        derivation = derive_local_size(
            base_size_mm,
            feature=geometry,
            min_size_mm=min_size_mm,
            config=config,
        )
        size = derivation.size_mm
        drivers = derivation.drivers
        if intent.target_size_mm is not None and intent.target_size_mm < size:
            size = intent.target_size_mm
            drivers = (*drivers, "intent_target")
        rules.append(
            ResolutionRule(
                name=f"{intent.kind.value}:{'+'.join(intent.semantic_keys)}",
                kind=intent.kind,
                semantic_keys=intent.semantic_keys,
                size_mm=size,
                drivers=tuple(sorted(set(drivers))),
                below_floor=min_size_mm is not None and size < min_size_mm,
            )
        )
    return tuple(sorted(rules, key=lambda item: item.name))


def required_min_size_mm(
    rules: Sequence[ResolutionRule], *, fallback_mm: float
) -> float:
    """Smallest rule size, or the fallback (base) size when no rule applies."""

    if not rules:
        return fallback_mm
    return min(rule.size_mm for rule in rules)
