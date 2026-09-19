"""Cantera combustion capability boundary.

The governed native entrypoints authorize nothing on their own: callers reach
them only through ``participants.lifecycle.NativeJobManager`` after the
capability probe. The pure case builder and parser are exported for tests and
for the participant-level adapters.
"""

from .case import (
    CANTERA_PARTICIPANT_ID,
    FINITE_RATE_REACTOR_MODES,
    MECHANISMS,
    REACTOR_MODES,
    REPORTED_SPECIES,
    canonical_combustion_case,
    combustion_input_hash,
    execute_combustion_case,
    prepare_combustion_case,
    probed_cantera_version,
)
from .parser import parse_combustion_result, validate_combustion_result
from .participants import (
    COMBUSTION_FIDELITY_LEVELS,
    COMBUSTION_INPUTS,
    COMBUSTION_OUTPUTS,
    combustion_participant,
    combustion_participants,
)

__all__ = [
    "CANTERA_PARTICIPANT_ID",
    "COMBUSTION_FIDELITY_LEVELS",
    "COMBUSTION_INPUTS",
    "COMBUSTION_OUTPUTS",
    "FINITE_RATE_REACTOR_MODES",
    "MECHANISMS",
    "REACTOR_MODES",
    "REPORTED_SPECIES",
    "canonical_combustion_case",
    "combustion_input_hash",
    "combustion_participant",
    "combustion_participants",
    "execute_combustion_case",
    "parse_combustion_result",
    "prepare_combustion_case",
    "probed_cantera_version",
    "validate_combustion_result",
]
