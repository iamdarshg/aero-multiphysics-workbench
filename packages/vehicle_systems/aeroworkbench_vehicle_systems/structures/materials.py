"""Member material binding for isotropic and laminated structural members.

An isotropic member binds an immutable :class:`MaterialRevision`. A laminated
member binds a :class:`LaminateRevision` plus a :class:`StrengthLibrary` so the
ply/laminate semantics from the composites workstream (#72) travel with the
member unchanged: the ply materials, stacking order, and fibre angles are never
collapsed to a single isotropic modulus. Thickness sizing scales every ply by a
common factor, preserving that architecture, and re-derives the homogenized
membrane properties explicitly through classical laminate theory.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aeroworkbench_composites import (
    FailureCriterion,
    LaminateLoad,
    StrengthLibrary,
    analyze_laminate,
    first_ply_failure,
)
from aeroworkbench_materials import (
    LaminateRevision,
    MaterialRevision,
    Ply,
    effective_orthotropic,
)

from .errors import StructuralContractError

__all__ = ["MemberMaterial"]

_MIN_PLY_THICKNESS_M = 1.0e-5


@dataclass(frozen=True, slots=True)
class MemberMaterial:
    """A structural member's material: isotropic revision or preserved laminate."""

    material: MaterialRevision
    laminate: LaminateRevision | None = None
    strengths: StrengthLibrary | None = None

    def __post_init__(self) -> None:
        if self.laminate is not None:
            if self.strengths is None:
                raise StructuralContractError(
                    "LAMINATED_MEMBER_REQUIRES_STRENGTH_LIBRARY"
                )
            if self.laminate.total_thickness_m <= 0.0:
                raise StructuralContractError("LAMINATE_THICKNESS_MUST_BE_POSITIVE")

    @property
    def kind(self) -> str:
        return "laminate" if self.laminate is not None else "isotropic"

    @property
    def identity(self) -> str:
        if self.laminate is not None:
            return self.laminate.identity
        return self.material.identity

    @property
    def ply_angles_deg(self) -> tuple[float, ...]:
        if self.laminate is None:
            return ()
        return tuple(ply.angle_deg for ply in self.laminate.plies)

    @property
    def ply_count(self) -> int:
        if self.laminate is None:
            return 0
        return len(self.laminate.plies)

    @property
    def minimum_thickness_m(self) -> float:
        return float(self.ply_count) * _MIN_PLY_THICKNESS_M

    def youngs_modulus_pa(self) -> float:
        return self.material.evaluate("youngs_modulus")

    def density_kg_m3(self) -> float:
        try:
            return self.material.evaluate("density")
        except KeyError as exc:
            raise StructuralContractError(
                f"MATERIAL_HAS_NO_DENSITY:{self.identity}"
            ) from exc

    def poisson_ratio(self) -> float:
        if "poisson_ratio" in self.material.properties:
            return self.material.evaluate("poisson_ratio")
        return 0.3

    def shear_modulus_pa(self) -> float:
        if "shear_modulus" in self.material.properties:
            return self.material.evaluate("shear_modulus")
        return self.youngs_modulus_pa() / (2.0 * (1.0 + self.poisson_ratio()))

    def allowable_pa(self, *, compression: bool = False) -> float:
        keys = ("yield_strength", "ultimate_strength") if compression else (
            "ultimate_strength",
            "yield_strength",
        )
        for key in keys:
            if key in self.material.properties:
                return self.material.evaluate(key)
        raise StructuralContractError(
            f"MATERIAL_HAS_NO_STRENGTH_ALLOWABLE:{self.identity}"
        )

    def with_thickness(self, thickness_m: float) -> MemberMaterial:
        """Return a member material sized to ``thickness_m``.

        Isotropic members are unchanged; laminated members scale every ply by a
        common factor so the stacking sequence and fibre angles are preserved.
        """

        if self.laminate is None:
            return self
        if thickness_m < self.minimum_thickness_m:
            raise StructuralContractError(
                f"LAMINATE_THICKNESS_BELOW_MINIMUM_PLY_STACK:{thickness_m}"
            )
        base = self.laminate.total_thickness_m
        scale = thickness_m / base
        plies = tuple(
            Ply(
                material=ply.material,
                angle_deg=ply.angle_deg,
                thickness_m=ply.thickness_m * scale,
            )
            for ply in self.laminate.plies
        )
        scaled = LaminateRevision(
            laminate_id=self.laminate.laminate_id,
            revision=self.laminate.revision,
            plies=plies,
            provenance=self.laminate.provenance,
        )
        homogenized = effective_orthotropic(scaled)
        return MemberMaterial(
            material=homogenized,
            laminate=scaled,
            strengths=self.strengths,
        )

    def composite_failure_index(
        self,
        *,
        membrane_load_n_m: float,
        criterion: FailureCriterion = FailureCriterion.TSAI_WU,
    ) -> float:
        """First-ply failure index from the composites workstream (no re-impl)."""

        if self.laminate is None or self.strengths is None:
            raise StructuralContractError("NOT_A_LAMINATED_MEMBER")
        analysis = analyze_laminate(self.laminate)
        result = first_ply_failure(
            analysis,
            LaminateLoad(n_x_n_m=membrane_load_n_m),
            self.strengths,
            criterion=criterion,
        )
        return float(result.index)

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "kind": self.kind,
            "identity": self.identity,
            "material": self.material.identity,
            "plyAnglesDeg": list(self.ply_angles_deg),
            "plyCount": self.ply_count,
        }
        if self.laminate is not None:
            payload["laminate"] = self.laminate.identity
            payload["thicknessM"] = self.laminate.total_thickness_m
        return payload
