"""Fidelity, validity, errors, and native-engine probes for the cycle solver.

The cycle solver has an explicit fidelity ladder. The analytical screening
level is a cheap labelled estimate; the generic OpenMDAO component network is a
real numerically-executed network at its own fidelity; the pyCycle level is the
native cycle element library. pyCycle and OpenMDAO are optional capabilities: a
requested native level fails closed with ``CAPABILITY_UNAVAILABLE`` when the
engine is absent, and an analytical result is never relabelled native.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from importlib import metadata

CYCLE_ERROR_PREPARATION = "PREPARATION_FAILED"
CYCLE_ERROR_CAPABILITY = "CAPABILITY_UNAVAILABLE"
CYCLE_ERROR_PARSER = "PARSER_FAILED"
CYCLE_ERROR_RESULT = "RESULT_INVALID"


class CycleFidelity(StrEnum):
    """Explicit fidelity ladder for gas-path/cycle results."""

    ANALYTICAL_SCREENING = "analytical-screening"
    MAP_PRELIMINARY = "map-preliminary"
    OPENMDAO_GENERIC = "openmdao-generic-network"
    PYCYCLE_NATIVE = "pycycle-native"


class OutOfEnvelopePolicy(StrEnum):
    """How a map evaluates a request outside its declared validity region."""

    FAIL = "fail"
    CLAMP = "clamp"


class CycleModelError(ValueError):
    """A typed, fail-closed cycle-model contract violation."""

    code = CYCLE_ERROR_PREPARATION

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class CycleParserError(CycleModelError):
    """A native cycle result document failed structural validation."""

    code = CYCLE_ERROR_PARSER


class CycleCapabilityUnavailable(RuntimeError):
    """A requested native cycle engine is not available."""

    code = CYCLE_ERROR_CAPABILITY

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


@dataclass(frozen=True, slots=True)
class CycleValidity:
    """Participant-style validity outcome carried on every cycle result."""

    passed: bool
    checks: dict[str, bool] = field(default_factory=dict)
    detail: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "checks", dict(self.checks))

    def canonical(self) -> dict[str, object]:
        return {
            "passed": self.passed,
            "checks": {key: self.checks[key] for key in sorted(self.checks)},
            "detail": self.detail,
        }


@dataclass(frozen=True, slots=True)
class CycleEngineStatus:
    """Actual availability of one optional native cycle engine."""

    engine: str
    available: bool
    version: str | None
    detail: str
    distributions: tuple[str, ...] = ()

    def canonical(self) -> dict[str, object]:
        return {
            "engine": self.engine,
            "available": self.available,
            "version": self.version,
            "detail": self.detail,
            "distributions": list(self.distributions),
        }


def _probe_distribution(distributions: tuple[str, ...]) -> tuple[str | None, str]:
    for distribution in distributions:
        try:
            version = metadata.version(distribution)
        except metadata.PackageNotFoundError:
            continue
        except Exception as exc:  # noqa: BLE001 - metadata failures never become capability
            return None, f"{distribution} metadata unreadable:{type(exc).__name__}"
        return version, f"{distribution} {version} installed"
    return None, f"none of {', '.join(distributions)} is installed"


def probe_cycle_engine(engine: str) -> CycleEngineStatus:
    """Probe one optional native cycle engine by distribution metadata only."""

    distributions: tuple[str, ...]
    if engine == "pycycle":
        distributions = ("pycycle", "pyCycle")
    elif engine == "openmdao":
        distributions = ("openmdao",)
    else:
        raise CycleModelError(f"UNKNOWN_CYCLE_ENGINE:{engine}")
    version, detail = _probe_distribution(distributions)
    return CycleEngineStatus(
        engine=engine,
        available=version is not None,
        version=version,
        detail=detail,
        distributions=distributions,
    )


def probe_cycle_engines() -> tuple[CycleEngineStatus, ...]:
    """Probe pyCycle and OpenMDAO; stable order, never optimistic."""

    return (probe_cycle_engine("pycycle"), probe_cycle_engine("openmdao"))


__all__ = [
    "CYCLE_ERROR_CAPABILITY",
    "CYCLE_ERROR_PARSER",
    "CYCLE_ERROR_PREPARATION",
    "CYCLE_ERROR_RESULT",
    "CycleCapabilityUnavailable",
    "CycleEngineStatus",
    "CycleFidelity",
    "CycleModelError",
    "CycleParserError",
    "CycleValidity",
    "OutOfEnvelopePolicy",
    "probe_cycle_engine",
    "probe_cycle_engines",
]
