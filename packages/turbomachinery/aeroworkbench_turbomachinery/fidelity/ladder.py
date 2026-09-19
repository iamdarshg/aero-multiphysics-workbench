"""Rotating-gas fidelity ladder: ordered, physics-applicable escalation rungs.

Each rung declares its expected result source and fidelity, the analyses it
delivers, the validity criteria a result must satisfy, and (for native rungs)
the native capabilities it is gated on. The ladder is generic: it never names a
specific product, and applicability is decided by
:class:`~aeroworkbench_turbomachinery.fidelity.features.ArchitectureFeatures`.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from dataclasses import dataclass
from enum import StrEnum
from math import isfinite
from typing import Any

from aeroworkbench_core.types import FidelityLevel, ResultSource
from aeroworkbench_optimization import FidelityImplementation

from ..canonical import content_digest
from .features import ArchitectureFeatures

__all__ = [
    "AnalysisKind",
    "FidelityRung",
    "LadderLevel",
    "RotatingGasFidelityLadder",
    "default_rotating_gas_ladder",
    "ladder_from_payload",
]


class LadderLevel(StrEnum):
    """Canonical rotating-gas fidelity rungs, cheapest first."""

    ALGEBRAIC_PREFLIGHT = "algebraic-buildability-preflight"
    MEANLINE_SCREENING = "thermodynamic-meanline-screening"
    THROUGHFLOW_ROW_MATCHING = "throughflow-reduced-order-row-matching"
    COARSE_STEADY_RANS_MRF = "coarse-steady-rans-mrf"
    MESH_INDEPENDENT_STEADY_CFD = "mesh-independent-steady-cfd"
    MULTIPHYSICS_VERIFICATION = "structural-thermal-rotordynamic-verification"
    TRANSIENT_UNSTEADY_CFD = "transient-sliding-interface-unsteady-cfd"
    DETAILED_COUPLED = "cht-fsi-reacting-em"


class AnalysisKind(StrEnum):
    """Disciplines an analysis can consume or deliver."""

    AERODYNAMIC_SCREENING = "aerodynamic-screening"
    THROUGHFLOW = "throughflow"
    STEADY_RANS = "steady-rans"
    UNSTEADY_CFD = "unsteady-cfd"
    STRUCTURAL = "structural"
    THERMAL = "thermal"
    ROTORDYNAMIC = "rotordynamic"
    ELECTRICAL = "electrical"
    BATTERY = "battery"
    COMBUSTION = "combustion"
    SHAFT_LOAD_BALANCE = "shaft-load-balance"
    ACOUSTICS = "acoustics"
    FIELD_COUPLING = "field-coupling"


@dataclass(frozen=True, slots=True)
class FidelityRung:
    """One declared rung with its cost, source, validity, and native gate."""

    rung_id: str
    level: LadderLevel
    rank: int
    cost: float
    source: ResultSource
    fidelity: FidelityLevel
    analyses: tuple[AnalysisKind, ...]
    validity_criteria: tuple[str, ...] = ()
    capabilities: tuple[str, ...] = ()
    requires_native: bool = False
    native_capabilities: tuple[str, ...] = ()
    description: str = ""

    def __post_init__(self) -> None:
        if not self.rung_id.strip():
            raise ValueError("FIDELITY_RUNG_ID_REQUIRED")
        if self.rank < 0:
            raise ValueError(f"FIDELITY_RUNG_RANK_NEGATIVE:{self.rung_id}")
        if not isfinite(self.cost) or self.cost < 0:
            raise ValueError(f"FIDELITY_RUNG_COST_INVALID:{self.rung_id}")
        if not self.analyses:
            raise ValueError(f"FIDELITY_RUNG_NEEDS_ANALYSES:{self.rung_id}")
        if self.requires_native and not self.native_capabilities:
            raise ValueError(f"NATIVE_RUNG_NEEDS_CAPABILITY:{self.rung_id}")
        if not self.requires_native and self.native_capabilities:
            raise ValueError(f"NON_NATIVE_RUNG_HAS_CAPABILITY:{self.rung_id}")
        if self.requires_native and self.source is not ResultSource.NATIVE_SOLVER:
            raise ValueError(f"NATIVE_RUNG_SOURCE_MISMATCH:{self.rung_id}")
        object.__setattr__(
            self, "analyses", tuple(sorted(self.analyses, key=lambda item: item.value))
        )

    def implementation(self, rank: int | None = None) -> FidelityImplementation:
        """Adapt to the shared optimization-layer fidelity implementation."""
        return FidelityImplementation(
            self.rung_id,
            self.rank if rank is None else rank,
            self.cost,
            self.capabilities,
            self.description,
        )

    def canonical(self) -> dict[str, Any]:
        return {
            "rungId": self.rung_id,
            "level": self.level.value,
            "rank": self.rank,
            "cost": self.cost,
            "source": self.source.value,
            "fidelity": self.fidelity.value,
            "analyses": [item.value for item in self.analyses],
            "validityCriteria": list(self.validity_criteria),
            "capabilities": list(self.capabilities),
            "requiresNative": self.requires_native,
            "nativeCapabilities": list(self.native_capabilities),
            "description": self.description,
        }

    @property
    def digest(self) -> str:
        return content_digest(self.canonical())


@dataclass(frozen=True, slots=True)
class RotatingGasFidelityLadder:
    """Immutable ordered ladder whose ranks form a contiguous range from zero."""

    rungs: tuple[FidelityRung, ...]
    ladder_id: str = "rotating-gas-fidelity-ladder"

    def __post_init__(self) -> None:
        if not self.ladder_id.strip():
            raise ValueError("FIDELITY_LADDER_ID_REQUIRED")
        if not self.rungs:
            raise ValueError("FIDELITY_LADDER_NEEDS_RUNGS")
        ordered = sorted(self.rungs, key=lambda rung: rung.rank)
        if [rung.rank for rung in ordered] != list(range(len(ordered))):
            raise ValueError("FIDELITY_LADDER_MUST_FORM_RANK_LADDER_FROM_ZERO")
        if len({rung.rung_id for rung in ordered}) != len(ordered):
            raise ValueError("FIDELITY_LADDER_DUPLICATE_RUNG")
        if [rung.rung_id for rung in ordered] != [rung.rung_id for rung in self.rungs]:
            object.__setattr__(self, "rungs", tuple(ordered))

    def rung(self, rung_id: str) -> FidelityRung:
        for rung in self.rungs:
            if rung.rung_id == rung_id:
                return rung
        raise ValueError(f"UNKNOWN_FIDELITY_RUNG:{rung_id}")

    def rung_ids(self) -> tuple[str, ...]:
        return tuple(rung.rung_id for rung in self.rungs)

    def cheapest(self) -> FidelityRung:
        return self.rungs[0]

    def next_rung(self, rung_id: str) -> FidelityRung | None:
        current = self.rung(rung_id)
        following = [rung for rung in self.rungs if rung.rank > current.rank]
        return following[0] if following else None

    def applicable(
        self,
        features: ArchitectureFeatures,
        requested: Collection[str] = (),
    ) -> tuple[FidelityRung, ...]:
        requested_set = frozenset(requested)
        return tuple(
            rung for rung in self.rungs if _rung_applies(rung.level, features, requested_set)
        )

    def implementations(
        self, rungs: Collection[FidelityRung] | None = None
    ) -> tuple[FidelityImplementation, ...]:
        selected = tuple(rungs) if rungs is not None else self.rungs
        ordered = sorted(selected, key=lambda rung: rung.rank)
        return tuple(rung.implementation(index) for index, rung in enumerate(ordered))

    def canonical(self) -> dict[str, Any]:
        return {
            "ladderId": self.ladder_id,
            "rungs": [rung.canonical() for rung in self.rungs],
        }

    @property
    def digest(self) -> str:
        return content_digest(self.canonical())


def _rung_applies(
    level: LadderLevel, features: ArchitectureFeatures, requested: frozenset[str]
) -> bool:
    if level is LadderLevel.ALGEBRAIC_PREFLIGHT:
        return True
    if level is LadderLevel.MEANLINE_SCREENING:
        return features.has_flow
    if level is LadderLevel.THROUGHFLOW_ROW_MATCHING:
        return features.has_flow and features.has_rotating_rows
    if level is LadderLevel.COARSE_STEADY_RANS_MRF:
        return features.has_flow and features.has_rotating_rows
    if level is LadderLevel.MESH_INDEPENDENT_STEADY_CFD:
        return features.has_flow and features.has_rotating_rows
    if level is LadderLevel.MULTIPHYSICS_VERIFICATION:
        return (
            features.has_rotating_rows
            or features.has_heat_addition
            or bool(requested & {AnalysisKind.STRUCTURAL, AnalysisKind.THERMAL,
                                  AnalysisKind.ROTORDYNAMIC})
        )
    if level is LadderLevel.TRANSIENT_UNSTEADY_CFD:
        return bool(requested & {AnalysisKind.UNSTEADY_CFD, "aeroelasticity",
                                  AnalysisKind.FIELD_COUPLING})
    if level is LadderLevel.DETAILED_COUPLED:
        return features.has_combustion or bool(
            requested & {AnalysisKind.FIELD_COUPLING, AnalysisKind.THERMAL,
                          AnalysisKind.STRUCTURAL, "cht", "fsi"}
        )
    return False


def default_rotating_gas_ladder() -> RotatingGasFidelityLadder:
    """Canonical eight-rung ladder; applicability is applied per architecture."""
    return RotatingGasFidelityLadder(
        rungs=(
            FidelityRung(
                "algebraic-preflight",
                LadderLevel.ALGEBRAIC_PREFLIGHT,
                0,
                0.0,
                ResultSource.ANALYTICAL,
                FidelityLevel.ANALYTICAL,
                (AnalysisKind.AERODYNAMIC_SCREENING,),
                ("buildable-geometry", "declared-operating-point"),
                ("preflight",),
                description="algebraic/buildability preflight",
            ),
            FidelityRung(
                "meanline-screening",
                LadderLevel.MEANLINE_SCREENING,
                1,
                0.01,
                ResultSource.ANALYTICAL,
                FidelityLevel.ANALYTICAL,
                (AnalysisKind.AERODYNAMIC_SCREENING,),
                ("correlation-validity", "operating-envelope"),
                ("screening", "meanline"),
                description="thermodynamic/meanline screening",
            ),
            FidelityRung(
                "throughflow-row-matching",
                LadderLevel.THROUGHFLOW_ROW_MATCHING,
                2,
                0.05,
                ResultSource.ANALYTICAL,
                FidelityLevel.ANALYTICAL,
                (AnalysisKind.THROUGHFLOW,),
                ("row-matching-residual", "spanwise-validity"),
                ("throughflow", "reduced-order"),
                description="throughflow/reduced-order row matching",
            ),
            FidelityRung(
                "coarse-steady-rans-mrf",
                LadderLevel.COARSE_STEADY_RANS_MRF,
                3,
                1.0,
                ResultSource.NATIVE_SOLVER,
                FidelityLevel.MRF,
                (AnalysisKind.STEADY_RANS,),
                ("solver-convergence", "mass-energy-closure"),
                ("steady-cfd",),
                requires_native=True,
                native_capabilities=("openfoam-steady-ras",),
                description="coarse steady RANS/MRF",
            ),
            FidelityRung(
                "mesh-independent-steady-cfd",
                LadderLevel.MESH_INDEPENDENT_STEADY_CFD,
                4,
                4.0,
                ResultSource.NATIVE_SOLVER,
                FidelityLevel.MRF,
                (AnalysisKind.STEADY_RANS,),
                ("mesh-independence", "solver-convergence"),
                ("steady-cfd", "mesh-independence"),
                requires_native=True,
                native_capabilities=("openfoam-steady-ras",),
                description="mesh-independent steady CFD",
            ),
            FidelityRung(
                "multiphysics-verification",
                LadderLevel.MULTIPHYSICS_VERIFICATION,
                5,
                6.0,
                ResultSource.NATIVE_SOLVER,
                FidelityLevel.TRANSIENT,
                (AnalysisKind.STRUCTURAL, AnalysisKind.THERMAL, AnalysisKind.ROTORDYNAMIC),
                (
                    "structural-stress-margin",
                    "thermal-margin",
                    "resonance-margin",
                    "shaft-load-balance-closure",
                ),
                ("structural", "thermal", "rotordynamic"),
                requires_native=True,
                native_capabilities=(
                    "code-aster-structural",
                    "elmer-thermal",
                    "ross-rotordynamics",
                ),
                description="structural/thermal/rotordynamic verification",
            ),
            FidelityRung(
                "transient-unsteady-cfd",
                LadderLevel.TRANSIENT_UNSTEADY_CFD,
                6,
                12.0,
                ResultSource.NATIVE_SOLVER,
                FidelityLevel.TRANSIENT,
                (AnalysisKind.UNSTEADY_CFD,),
                ("timestep-independence", "sliding-interface-conservation"),
                ("unsteady-cfd", "sliding-interface"),
                requires_native=True,
                native_capabilities=("openfoam-transient-ras",),
                description="transient sliding-interface/unsteady CFD",
            ),
            FidelityRung(
                "detailed-cht-fsi-reacting",
                LadderLevel.DETAILED_COUPLED,
                7,
                25.0,
                ResultSource.NATIVE_SOLVER,
                FidelityLevel.TRANSIENT,
                (
                    AnalysisKind.THERMAL,
                    AnalysisKind.STRUCTURAL,
                    AnalysisKind.COMBUSTION,
                    AnalysisKind.FIELD_COUPLING,
                ),
                (
                    "field-coupling-conservation",
                    "chemistry-validity",
                    "mesh-and-timestep-independence",
                ),
                ("field-coupling", "cht", "fsi", "reacting"),
                requires_native=True,
                native_capabilities=("precice", "cantera"),
                description="CHT/FSI or detailed reacting/EM analysis",
            ),
        )
    )


def ladder_from_payload(payload: Mapping[str, Any]) -> RotatingGasFidelityLadder:
    """Rebuild a ladder from :meth:`RotatingGasFidelityLadder.canonical`."""
    rungs = tuple(
        FidelityRung(
            rung_id=str(item["rungId"]),
            level=LadderLevel(str(item["level"])),
            rank=int(item["rank"]),
            cost=float(item["cost"]),
            source=ResultSource(str(item["source"])),
            fidelity=FidelityLevel(str(item["fidelity"])),
            analyses=tuple(AnalysisKind(str(name)) for name in item["analyses"]),
            validity_criteria=tuple(str(name) for name in item.get("validityCriteria", ())),
            capabilities=tuple(str(name) for name in item.get("capabilities", ())),
            requires_native=bool(item.get("requiresNative", False)),
            native_capabilities=tuple(
                str(name) for name in item.get("nativeCapabilities", ())
            ),
            description=str(item.get("description", "")),
        )
        for item in payload["rungs"]
    )
    return RotatingGasFidelityLadder(rungs, str(payload.get("ladderId", "")))
