"""Validity outcome carried on every meanline result and correlation value."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class Validity:
    """Named boolean checks plus a human-readable detail string."""

    passed: bool
    checks: dict[str, bool] = field(default_factory=dict)
    detail: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "checks", dict(self.checks))

    def canonical(self) -> dict[str, object]:
        return {"passed": self.passed, "checks": dict(self.checks), "detail": self.detail}


__all__ = ["Validity"]
