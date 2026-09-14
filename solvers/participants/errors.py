"""Explicit native-pipeline error taxonomy.

Every failure in the governed participant lifecycle carries one of these codes.
Codes are never converted into analytical results; they surface as explicit
job states (FAILED/CANCELLED) with the code preserved end to end.
"""

from __future__ import annotations

from enum import StrEnum


class NativeErrorCode(StrEnum):
    """Closed set of failure codes for the native execution pipeline."""

    CAPABILITY_UNAVAILABLE = "CAPABILITY_UNAVAILABLE"
    ADMISSION_REJECTED = "ADMISSION_REJECTED"
    PREPARATION_FAILED = "PREPARATION_FAILED"
    MESH_INVALID = "MESH_INVALID"
    PROCESS_START_FAILED = "PROCESS_START_FAILED"
    PROCESS_TIMEOUT = "PROCESS_TIMEOUT"
    PROCESS_RSS_LIMIT_EXCEEDED = "PROCESS_RSS_LIMIT_EXCEEDED"
    PROCESS_EXIT_NONZERO = "PROCESS_EXIT_NONZERO"
    PARSER_FAILED = "PARSER_FAILED"
    QUALITY_GATE_FAILED = "QUALITY_GATE_FAILED"
    RESULT_INVALID = "RESULT_INVALID"
    CANCELLED = "CANCELLED"
    INTERRUPTED = "INTERRUPTED"


class ParticipantError(RuntimeError):
    """A lifecycle failure with a stable taxonomy code and human detail."""

    def __init__(self, code: NativeErrorCode, detail: str) -> None:
        if not detail.strip():
            raise ValueError("PARTICIPANT_ERROR_DETAIL_REQUIRED")
        super().__init__(f"{code.value}:{detail}")
        self.code = code
        self.detail = detail
