from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from .models.common import analytical_provenance
from .types import FidelityLevel, Provenance


class ResonanceRegime(StrEnum):
    CLEAR = "clear"
    WATCH = "watch"
    CRITICAL = "critical"


class Excitation(BaseModel):
    name: str
    frequency_hz: float = Field(gt=0)


class Mode(BaseModel):
    name: str
    frequency_hz: float = Field(gt=0)
    damping_ratio: float = Field(ge=0)


class ResonanceReport(BaseModel):
    regime: ResonanceRegime
    minimum_separation_fraction: float
    required_fidelity: FidelityLevel
    escalation_required: bool
    explanation: str
    provenance: Provenance


class ResonanceDetector:
    def evaluate(
        self, *, excitations: list[Excitation], modes: list[Mode], current_fidelity: FidelityLevel
    ) -> ResonanceReport:
        if not excitations or not modes:
            raise ValueError("at least one excitation and mode are required")
        separation = min(
            abs(ex.frequency_hz - mode.frequency_hz) / mode.frequency_hz
            for ex in excitations
            for mode in modes
        )
        if separation <= 0.02:
            regime = ResonanceRegime.CRITICAL
            required = FidelityLevel.HARMONIC_RESPONSE
        elif separation <= 0.10:
            regime = ResonanceRegime.WATCH
            required = FidelityLevel.HARMONIC_RESPONSE
        else:
            regime = ResonanceRegime.CLEAR
            required = current_fidelity
        rank = {
            FidelityLevel.ANALYTICAL: 0,
            FidelityLevel.MRF: 1,
            FidelityLevel.HARMONIC_RESPONSE: 2,
            FidelityLevel.TRANSIENT: 3,
        }
        escalation = rank[required] > rank[current_fidelity]
        return ResonanceReport(
            regime=regime,
            minimum_separation_fraction=separation,
            required_fidelity=required,
            escalation_required=escalation,
            explanation=f"Closest excitation is within {separation:.2%} of a mode.",
            provenance=analytical_provenance(
                "frequency-separation-resonance-detector",
                {
                    "excitations": [excitation.model_dump() for excitation in excitations],
                    "modes": [mode.model_dump() for mode in modes],
                    "current_fidelity": current_fidelity.value,
                },
                "frequency-only separation check; no forced-response amplitude is computed",
            ),
        )
