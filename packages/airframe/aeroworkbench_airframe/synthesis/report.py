"""Top-level initial synthesis report: fixed-wing seeds plus architecture seams."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from aeroworkbench_core.types import FidelityLevel, Provenance, ResultSource

from ..canonical import content_digest, normalize_numbers
from . import methods
from .fixed_wing import FixedWingAssumptions, generate_fixed_wing_seeds
from .requirements import CompiledRequirements
from .seams import SeamResult, synthesize_lifting_body_seam, synthesize_rotorcraft_seam
from .seeds import VehicleSeed

_ANALYTICAL = ResultSource.ANALYTICAL
_FIDELITY = FidelityLevel.ANALYTICAL


@dataclass(frozen=True, slots=True)
class SynthesisReport:
    """Deterministic bundle of candidate seeds and architecture-seam status."""

    requirements: CompiledRequirements
    seeds: tuple[VehicleSeed, ...]
    seams: tuple[SeamResult, ...]
    assumptions: tuple[str, ...]
    provenance: Provenance

    @property
    def available_seams(self) -> tuple[str, ...]:
        return tuple(seam.architecture_type for seam in self.seams if seam.available)

    @property
    def unavailable_seams(self) -> tuple[str, ...]:
        return tuple(seam.architecture_type for seam in self.seams if not seam.available)

    def canonical_payload(self) -> dict[str, object]:
        return cast(
            dict[str, object],
            normalize_numbers(
                {
                    "requirementsHash": self.requirements.content_hash,
                    "seeds": [seed.canonical_payload() for seed in self.seeds],
                    "seams": [seam.canonical() for seam in self.seams],
                    "assumptions": list(self.assumptions),
                    "provenance": self.provenance.model_dump(mode="json"),
                }
            ),
        )

    @property
    def content_hash(self) -> str:
        return content_digest(self.canonical_payload())


def synthesize_initial_seeds(
    compiled: CompiledRequirements,
    *,
    assumptions: FixedWingAssumptions | None = None,
    seed_count: int = 2,
) -> SynthesisReport:
    """Produce fixed-wing seeds and architecture-seam evidence from requirements."""
    settings = assumptions if assumptions is not None else FixedWingAssumptions()
    fixed_wing = generate_fixed_wing_seeds(compiled, assumptions=settings, seed_count=seed_count)
    seams = (synthesize_rotorcraft_seam(compiled), synthesize_lifting_body_seam(compiled))
    seeds = tuple(
        seed for seam in seams if seam.available for seed in seam.seeds
    ) + fixed_wing
    assumptions_text = (
        "Initial synthesis is screening evidence from declared analytical/empirical relations.",
        "Seeds and seams are not native-solver results; native validation is required.",
    )
    provenance = Provenance.from_inputs(
        source=_ANALYTICAL,
        model=f"{methods.SYNTHESIS_MODEL}:report",
        model_version=methods.SYNTHESIS_MODEL_VERSION,
        fidelity=_FIDELITY,
        inputs={
            "requirementsHash": compiled.content_hash,
            "seedCount": seed_count,
            "assumptions": settings.canonical(),
        },
        assumptions=assumptions_text,
    )
    return SynthesisReport(
        requirements=compiled,
        seeds=seeds,
        seams=seams,
        assumptions=assumptions_text,
        provenance=provenance,
    )
