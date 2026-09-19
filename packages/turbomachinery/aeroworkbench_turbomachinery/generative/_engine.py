"""Runtime bridge to the shared design-space, generation, campaign, and envelope engines.

The turbomachinery package reuses these engines rather than reimplementing them.
They are imported dynamically so the strict type gate on this package does not
inherit the (separately maintained) typing posture of the optimization and
manufacturing packages.
"""

from __future__ import annotations

from importlib import import_module
from types import ModuleType
from typing import Any, cast

_DESIGN_SPACE = "aeroworkbench_optimization.design_space"
_GENERATION = "aeroworkbench_optimization.generation"
_CAMPAIGN = "aeroworkbench_optimization.campaign"
_MANUFACTURING = "aeroworkbench_manufacturing.design_space"
_GATE = "aeroworkbench_manufacturing.gate"


def _module(name: str) -> ModuleType:
    return import_module(name)


def flatten_design_state(space: Any, state: Any) -> dict[str, Any]:
    function = _module(_DESIGN_SPACE).flatten_design_state
    return cast("dict[str, Any]", function(space, state))


def preflight_design_state(space: Any, state: Any) -> tuple[str, ...]:
    function = _module(_DESIGN_SPACE).preflight_design_state
    return tuple(cast("tuple[str, ...]", function(space, state)))


def candidate_hash(flat: Any) -> str:
    function = _module(_DESIGN_SPACE).candidate_hash
    return cast(str, function(flat))


def validate_design_space(space: Any) -> None:
    function = _module(_DESIGN_SPACE).validate_design_space
    function(space)


def generation_request(**fields: Any) -> Any:
    request = _module(_GENERATION).GenerationRequest
    return cast(Any, request(**fields))


def candidate_generator(space: Any, request: Any) -> Any:
    generator = _module(_GENERATION).CandidateGenerator
    return cast(Any, generator(space, request))


def run_campaign(spec: Any, evaluator: Any, **options: Any) -> Any:
    runner = _module(_CAMPAIGN).run_campaign
    return cast(Any, runner(spec, evaluator, **options))


def campaign_spec(**fields: Any) -> Any:
    spec = _module(_CAMPAIGN).CampaignSpec
    return cast(Any, spec(**fields))


def merge_envelope_constraints(space: Any, envelopes: Any) -> dict[str, Any]:
    function = _module(_MANUFACTURING).merge_envelope_constraints
    return cast("dict[str, Any]", function(space, envelopes))


def envelope_design_constraints(space: Any, envelopes: Any) -> tuple[dict[str, Any], ...]:
    function = _module(_MANUFACTURING).envelope_design_constraints
    return tuple(cast("tuple[dict[str, Any], ...]", function(space, envelopes)))


def manufacturability_gate(envelopes: Any) -> Any:
    gate = _module(_GATE).ManufacturabilityGate
    return cast(Any, gate(envelopes))
