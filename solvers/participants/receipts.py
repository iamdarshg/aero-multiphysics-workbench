"""Typed receipts exchanged between lifecycle phases.

Prepare, parse, validity, and capability probes all return frozen receipts.
The lifecycle never passes raw solver output forward; only receipts.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class CapabilityProbe:
    """Outcome of probing one participant's executable capability."""

    participant_id: str
    solver_id: str
    executable: str
    state: str  # "ready" | "unavailable"
    version: str | None
    detail: str

    def __post_init__(self) -> None:
        if self.state not in {"ready", "unavailable"}:
            raise ValueError("INVALID_CAPABILITY_STATE")
        if not self.detail.strip():
            raise ValueError("CAPABILITY_DETAIL_REQUIRED")


@dataclass(frozen=True, slots=True)
class PrepareReceipt:
    """Proof that a solver case was prepared from validated inputs."""

    participant_id: str
    case_id: str
    input_hash: str
    files: tuple[str, ...]
    geometry_hash: str | None = None
    mesh_hash: str | None = None
    detail: str = ""

    def __post_init__(self) -> None:
        if len(self.input_hash) != 64 or any(
            character not in "0123456789abcdef" for character in self.input_hash
        ):
            raise ValueError("PREPARE_RECEIPT_NEEDS_INPUT_HASH")
        if not self.files:
            raise ValueError("PREPARE_RECEIPT_NEEDS_FILES")


@dataclass(frozen=True, slots=True)
class ParseReceipt:
    """Proof that a parser converted solver output into typed scalars."""

    participant_id: str
    parser: str
    scalars: dict[str, float] = field(default_factory=dict)
    units: dict[str, str] = field(default_factory=dict)
    detail: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "scalars", dict(self.scalars))
        object.__setattr__(self, "units", dict(self.units))
        for name, value in self.scalars.items():
            if not isinstance(value, float):
                raise ValueError(f"PARSER_SCALAR_MUST_BE_FLOAT:{name}")


@dataclass(frozen=True, slots=True)
class ValidityReport:
    """Outcome of participant-specific validity checks on parsed scalars."""

    participant_id: str
    passed: bool
    checks: dict[str, bool] = field(default_factory=dict)
    detail: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "checks", dict(self.checks))
