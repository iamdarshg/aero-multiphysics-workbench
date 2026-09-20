"""Lifting-body campaign fixture built on the generic campaign adapter.

This module deliberately contains no optimizer.  Requirements produce the
existing analytical seam seed, and the shared campaign engine refines that seed
over its ordinary design space.  Native evaluation is an injected capability so
the fixture cannot fabricate a solver result.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from aeroworkbench_optimization import (
    CampaignBudget,
    Candidate,
    EvaluationResult,
    FidelityImplementation,
    GenerationRequest,
    PhysicsFlags,
    StudyObjective,
)

from ..aero_geometry import AirfoilProfile, LiftingSurface, LoftedBody, Planform
from ..campaign import (
    AirframeCampaignSession,
    AirframeCampaignSpec,
    AirframeMutationPolicy,
    build_airframe_campaign_spec,
)
from ..external_aero import ExternalAeroCase
from .requirements import CompiledRequirements
from .seams import synthesize_lifting_body_seam
from .seeds import VehicleSeed

NativeEvaluator = Callable[[Candidate, ExternalAeroCase], EvaluationResult]


@dataclass(frozen=True, slots=True)
class LiftingBodyCampaignFixture:
    """Requirements-to-case fixture for medium/native campaign validation."""

    requirements: CompiledRequirements
    seed: VehicleSeed
    case: ExternalAeroCase
    spec: AirframeCampaignSpec

    def evaluator(
        self, native: NativeEvaluator | None = None
    ) -> Callable[[Candidate, str], EvaluationResult]:
        def evaluate(candidate: Candidate, fidelity: str) -> EvaluationResult:
            values = {
                item.variable_id: float(item.value)
                for item in candidate.assignment
                if item.point_id is None and isinstance(item.value, (int, float))
            }
            area = values.get(
                "lifting_body_planform_area",
                self.seed.parameter("lifting_body_planform_area").value_si,
            )
            span = values.get("span_limit", self.seed.parameter("span_limit").value_si)
            thickness = values.get(
                "lifting_body_thickness_ratio",
                self.seed.parameter("lifting_body_thickness_ratio").value_si,
            )
            volume = area * span * thickness
            cg = 0.28
            static_margin = 0.42 - cg
            trim_margin = 0.35 - abs(0.04 / 0.8)
            constraints = {
                "volume_m3": volume,
                "cg_mac_fraction": cg,
                "static_margin": static_margin,
                "trim_margin_rad": trim_margin,
            }
            limits = {item.metric: item for item in self.requirements.requirements}
            volume_limit = limits.get("volume_limit")
            volume_upper = volume_limit.upper_si if volume_limit else None
            volume_ok = volume_upper is not None and volume <= volume_upper
            margin_requirement = limits.get("static_margin")
            margin_lower = margin_requirement.lower_si if margin_requirement else None
            cg_ok = margin_lower is not None and static_margin >= margin_lower
            trim_ok = trim_margin >= 0.0
            if fidelity == "native":
                if native is None:
                    return EvaluationResult(
                        outputs=constraints,
                        flags=PhysicsFlags(
                            converged=False, closure_passed=False, validity_ok=False
                        ),
                        fidelity=fidelity,
                        source="unknown",
                        detail="NATIVE_LIFTING_BODY_CAPABILITY_UNAVAILABLE",
                    )
                return native(candidate, self.case)
            return EvaluationResult(
                outputs={**constraints, "constraint_passed": volume_ok and cg_ok and trim_ok},
                flags=PhysicsFlags(
                    converged=True,
                    closure_passed=volume_ok and cg_ok and trim_ok,
                    validity_ok=True,
                ),
                fidelity=fidelity,
                source="analytical",
                detail="analytical lifting-body volume/CG/trim screening",
            )

        return evaluate

    def session(self, native: NativeEvaluator | None = None) -> AirframeCampaignSession:
        return AirframeCampaignSession(
            self.spec,
            self.evaluator(native),
            evaluator_identity="lifting-body-campaign-v1",
            mutation_policy=AirframeMutationPolicy.default(),
        )


def _case_from_seed(seed: VehicleSeed) -> ExternalAeroCase:
    area = seed.parameter("lifting_body_planform_area").value_si
    span = seed.parameter("span_limit").value_si
    thickness = seed.parameter("lifting_body_thickness_ratio").value_si
    sweep = seed.parameter("lifting_body_sweep").value_si
    root = 2.0 * area / span / 1.2
    tip = root * 0.2
    surface = LiftingSurface.from_planform(
        "lifting-body-planform",
        "lifting_body",
        Planform(
            span_mm=span * 1000.0,
            root_chord_mm=root * 1000.0,
            tip_chord_mm=tip * 1000.0,
            sweep_deg=sweep,
        ),
        AirfoilProfile(family="naca4", thickness_ratio=min(thickness, 0.2)),
        n_stations=7,
    )
    body = LoftedBody.from_spine(
        "lifting-body-centerbody",
        "lifting_body",
        ((0.0, 0.0, 0.0), (0.0, 0.0, span * 500.0), (0.0, 0.0, span * 1000.0)),
        (100.0, root * 1000.0, 100.0),
        (60.0, root * thickness * 1000.0, 60.0),
        frame="aerodynamic-body",
    )
    return ExternalAeroCase("lifting-body-campaign", (surface,), bodies=(body,), symmetry="mirror")


def build_lifting_body_campaign_fixture(
    compiled: CompiledRequirements,
    *,
    evaluations: int = 4,
) -> LiftingBodyCampaignFixture:
    """Build requirements -> seed -> generic campaign refinement fixture."""
    seam = synthesize_lifting_body_seam(compiled)
    if not seam.available or not seam.seeds:
        raise ValueError(seam.reason)
    seed = seam.seeds[0]
    spec = build_airframe_campaign_spec(
        "lifting-body-medium-native",
        seed,
        generation=GenerationRequest("lhs", count=evaluations, budget=evaluations, seed=97),
        objectives=(StudyObjective("volume_m3", "minimize"),),
        fidelity_ladder=(
            FidelityImplementation("analytical", 0, 0.0),
            FidelityImplementation("medium", 1, 0.25),
            FidelityImplementation("native", 2, 1.0),
        ),
        budget=CampaignBudget(max_evaluations=evaluations * 3),
    )
    return LiftingBodyCampaignFixture(compiled, seed, _case_from_seed(seed), spec)


__all__ = ["LiftingBodyCampaignFixture", "build_lifting_body_campaign_fixture"]
