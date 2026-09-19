"""Solver-adapter integration: derive flow-model settings from the contract.

The generic flow-model contract drives the solver dictionaries instead of
hard-coded case types: simulation type, RAS/LES/transition model, near-wall
treatment, and roughness are all derived from the selected model, the wall
requirement, and the declared roughness. A requested native turbulence
capability is capability-gated and fail-closed; a screening correlation is never
relabelled native.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from math import isfinite
from typing import Any, Protocol, runtime_checkable

from aeroworkbench_core.types import Provenance, ResultSource
from aeroworkbench_fluid_properties import SoftwareIdentity

from .contracts import (
    SOFTWARE_IDENTITY,
    TurbulenceFidelity,
    Validity,
    analytical_provenance,
    native_provenance,
)
from .errors import (
    TurbulenceCapabilityUnavailableError,
    TurbulenceValidationError,
)
from .models import ModelSelection, TurbulenceModel
from .regimes import FlowState
from .roughness import RoughnessSpec
from .wall import WallTreatmentMode, WallTreatmentRequirement

_MODEL_NAME = "aeroworkbench-turbulence:native"

_RAS_NAMES: dict[TurbulenceModel, str] = {
    TurbulenceModel.SPALART_ALLMARAS: "SpalartAllmaras",
    TurbulenceModel.K_EPSILON: "kEpsilon",
    TurbulenceModel.K_OMEGA_SST: "kOmegaSST",
    TurbulenceModel.SA_DDES: "SpalartAllmarasDDES",
}

_TRANSITION_NAMES: dict[TurbulenceModel, str] = {
    TurbulenceModel.TRANSITION_GAMMA_RETHETA: "kOmegaSSTLM",
    TurbulenceModel.TRANSITION_KKL_OMEGA: "kkLOmega",
}

_LES_NAMES: dict[TurbulenceModel, str] = {
    TurbulenceModel.WMLES: "WALE",
    TurbulenceModel.LES_SMAGORINSKY: "Smagorinsky",
}

_WALL_FUNCTION_NAMES: dict[TurbulenceModel, str] = {
    TurbulenceModel.K_EPSILON: "nutkWallFunction",
    TurbulenceModel.K_OMEGA_SST: "nutkWallFunction",
}

ROUGHNESS_WALL_FUNCTION = "nutkRoughWallFunction"
DEFAULT_ROUGHNESS_CONSTANT_CS = 0.5
DEFAULT_ROUGHNESS_CONSTANT_SOURCE = "OpenFOAM default roughness constant Cs=0.5 (declared)"


@dataclass(frozen=True, slots=True)
class SolverFlowModel:
    """Solver-ready flow-model settings derived from the generic contract."""

    solver: str
    model: TurbulenceModel
    fidelity: TurbulenceFidelity
    simulation_type: str
    ras_model: str | None
    les_model: str | None
    transition_model: str | None
    wall_treatment: WallTreatmentMode
    wall_function: str | None
    roughness_model: str | None
    roughness_equivalent_sand_grain_m: float | None
    roughness_constant_cs: float | None
    thermal_wall: bool
    provenance: Provenance
    software: SoftwareIdentity = SOFTWARE_IDENTITY

    def __post_init__(self) -> None:
        if not self.solver.strip() or not self.simulation_type.strip():
            raise TurbulenceValidationError("SOLVER_FLOW_MODEL_IDENTITY_REQUIRED")
        if self.roughness_constant_cs is not None and (
            not isfinite(self.roughness_constant_cs) or self.roughness_constant_cs <= 0.0
        ):
            raise TurbulenceValidationError("ROUGHNESS_CONSTANT_INVALID")

    def canonical(self) -> dict[str, Any]:
        return {
            "solver": self.solver,
            "model": self.model.value,
            "fidelity": self.fidelity.value,
            "simulationType": self.simulation_type,
            "rasModel": self.ras_model,
            "lesModel": self.les_model,
            "transitionModel": self.transition_model,
            "wallTreatment": self.wall_treatment.value,
            "wallFunction": self.wall_function,
            "roughnessModel": self.roughness_model,
            "roughnessEquivalentSandGrainM": self.roughness_equivalent_sand_grain_m,
            "roughnessConstantCs": self.roughness_constant_cs,
            "thermalWall": self.thermal_wall,
            "units": {"roughnessEquivalentSandGrainM": "m"},
            "inputsHash": self.provenance.inputs_hash,
            "software": self.software.canonical(),
        }


def _simulation_type(model: TurbulenceModel, fidelity: TurbulenceFidelity) -> str:
    if model is TurbulenceModel.LAMINAR or model is TurbulenceModel.DNS:
        return "laminar"
    if fidelity in (TurbulenceFidelity.RANS, TurbulenceFidelity.TRANSITION_RANS):
        return "RAS"
    if fidelity in (TurbulenceFidelity.HYBRID_RANS_LES, TurbulenceFidelity.LES):
        if model is TurbulenceModel.SA_DDES:
            return "RAS"
        return "LES"
    return "laminar"


def _wall_function(
    model: TurbulenceModel, mode: WallTreatmentMode, roughness: RoughnessSpec | None
) -> str | None:
    if mode is not WallTreatmentMode.WALL_FUNCTION:
        return None
    if roughness is not None and not roughness.hydraulically_smooth:
        return ROUGHNESS_WALL_FUNCTION
    return _WALL_FUNCTION_NAMES.get(model, "nutkWallFunction")


def derive_solver_flow_model(
    *,
    flow: FlowState,
    selection: ModelSelection,
    wall_requirement: WallTreatmentRequirement | None = None,
    roughness: RoughnessSpec | None = None,
    solver: str = "openfoam",
    roughness_constant_cs: float | None = None,
) -> SolverFlowModel:
    """Derive solver settings from the selected model and wall/roughness state."""
    model = selection.model
    fidelity = selection.fidelity
    simulation_type = _simulation_type(model, fidelity)
    ras_model = (
        _TRANSITION_NAMES.get(model) or _RAS_NAMES.get(model)
        if simulation_type == "RAS"
        else None
    )
    les_model = _LES_NAMES.get(model) if simulation_type == "LES" else None
    transition_model = _TRANSITION_NAMES.get(model)
    mode = (
        wall_requirement.mode
        if wall_requirement is not None
        else WallTreatmentMode.NONE
    )
    wall_function = _wall_function(model, mode, roughness)
    thermal_wall = (
        wall_requirement.thermal_wall_required
        if wall_requirement is not None
        else flow.conjugate_heat_transfer
    )
    resolved_roughness = roughness or flow.roughness
    if resolved_roughness is not None and wall_function == ROUGHNESS_WALL_FUNCTION:
        constant = (
            roughness_constant_cs
            if roughness_constant_cs is not None
            else DEFAULT_ROUGHNESS_CONSTANT_CS
        )
    else:
        constant = None
    provenance = analytical_provenance(
        "turbulence.adapter.solver-flow-model",
        {
            "solver": solver,
            "flow": flow.canonical(),
            "selection": selection.canonical(),
            "wallRequirement": (
                wall_requirement.canonical() if wall_requirement is not None else None
            ),
            "roughness": resolved_roughness.canonical() if resolved_roughness else None,
            "roughnessConstantCs": constant,
            "roughnessConstantSource": (
                DEFAULT_ROUGHNESS_CONSTANT_SOURCE if constant is not None else None
            ),
        },
        "solver dictionaries derived from the generic flow-model contract",
    )
    return SolverFlowModel(
        solver=solver,
        model=model,
        fidelity=fidelity,
        simulation_type=simulation_type,
        ras_model=ras_model,
        les_model=les_model,
        transition_model=transition_model,
        wall_treatment=mode,
        wall_function=wall_function,
        roughness_model=(
            resolved_roughness.model.value if resolved_roughness is not None else None
        ),
        roughness_equivalent_sand_grain_m=(
            resolved_roughness.equivalent_sand_grain_m
            if resolved_roughness is not None
            else None
        ),
        roughness_constant_cs=constant,
        thermal_wall=thermal_wall,
        provenance=provenance,
    )


def openfoam_turbulence_properties(model: SolverFlowModel) -> str:
    """Render an OpenFOAM ``constant/turbulenceProperties`` dictionary."""
    header = (
        "FoamFile\n{\n    version     2.0;\n    format      ascii;\n"
        "    class       dictionary;\n    object      turbulenceProperties;\n}\n"
    )
    if model.simulation_type == "laminar":
        return header + "simulationType  laminar;\n"
    if model.simulation_type == "LES":
        les = model.les_model or "Smagorinsky"
        return (
            header
            + "simulationType  LES;\n\nLES\n{\n"
            + f"    LESModel        {les};\n    turbulence      on;\n"
            + "    printCoeffs     on;\n}\n"
        )
    ras = model.ras_model or "kOmegaSST"
    body = (
        header
        + "simulationType  RAS;\n\nRAS\n{\n"
        + f"    RASModel        {ras};\n    turbulence      on;\n"
        + "    printCoeffs     on;\n"
    )
    if model.transition_model is not None:
        body += "    transition      on;\n"
    body += "}\n"
    return body


def openfoam_wall_roughness(model: SolverFlowModel) -> str:
    """Render the declared roughness wall settings for an OpenFOAM case."""
    if model.roughness_equivalent_sand_grain_m is None:
        raise TurbulenceValidationError("ROUGHNESS_NOT_DECLARED")
    if model.roughness_constant_cs is None:
        raise TurbulenceValidationError("ROUGHNESS_CONSTANT_NOT_DECLARED")
    return (
        "FoamFile\n{\n    version     2.0;\n    format      ascii;\n"
        "    class       dictionary;\n    object      wallRoughness;\n}\n"
        f"roughnessModel  {model.roughness_model};\n"
        f"Ks              [0 1 0 0 0 0 0] {model.roughness_equivalent_sand_grain_m:.6e};\n"
        f"Cs              {model.roughness_constant_cs:g};\n"
    )


# -- native turbulence seam --------------------------------------------------


@dataclass(frozen=True, slots=True)
class NativeTurbulenceCapability:
    """Observed availability of a native turbulence executable (never optimistic)."""

    backend: str
    available: bool
    executable: str | None
    version: str | None
    detail: str

    def canonical(self) -> dict[str, Any]:
        return {
            "backend": self.backend,
            "available": self.available,
            "executable": self.executable,
            "version": self.version,
            "detail": self.detail,
        }


_KNOWN_EXECUTABLES = ("foamRun", "simpleFoam", "rhoSimpleFoam", "su2_CFD", "cfx5solve", "fluent")


def probe_native_turbulence_capability(executable: str = "foamRun") -> NativeTurbulenceCapability:
    """Probe for a native turbulence executable without running it."""
    resolved = shutil.which(executable)
    if resolved is None:
        return NativeTurbulenceCapability(
            backend=executable,
            available=False,
            executable=None,
            version=None,
            detail=f"{executable} is not installed; native turbulence fidelity fails closed",
        )
    return NativeTurbulenceCapability(
        backend=executable,
        available=True,
        executable=resolved,
        version=None,
        detail=f"{executable} present at {resolved}",
    )


def probe_any_native_turbulence_capability() -> NativeTurbulenceCapability:
    """Probe the known native executables and return the first available."""
    for executable in _KNOWN_EXECUTABLES:
        capability = probe_native_turbulence_capability(executable)
        if capability.available:
            return capability
    return probe_native_turbulence_capability(_KNOWN_EXECUTABLES[0])


def require_native_turbulence_capability(
    executable: str = "foamRun",
) -> NativeTurbulenceCapability:
    """Return the capability or fail closed with a typed error."""
    capability = probe_native_turbulence_capability(executable)
    if not capability.available:
        raise TurbulenceCapabilityUnavailableError(
            f"NATIVE_TURBULENCE_UNAVAILABLE:{executable}:{capability.detail}"
        )
    return capability


@dataclass(frozen=True, slots=True)
class NativeTurbulenceRequest:
    """Everything a native engine needs to reproduce the turbulence case."""

    case_label: str
    model: TurbulenceModel
    fidelity: TurbulenceFidelity
    wall_treatment: WallTreatmentMode
    roughness_equivalent_sand_grain_m: float | None
    reynolds_number: float
    mach_number: float
    transition_state: str
    reason: str
    payload: dict[str, Any] = field(default_factory=dict)

    def canonical(self) -> dict[str, Any]:
        return {
            "caseLabel": self.case_label,
            "model": self.model.value,
            "fidelity": self.fidelity.value,
            "wallTreatment": self.wall_treatment.value,
            "roughnessEquivalentSandGrainM": self.roughness_equivalent_sand_grain_m,
            "reynoldsNumber": self.reynolds_number,
            "machNumber": self.mach_number,
            "transitionState": self.transition_state,
            "reason": self.reason,
            "payload": self.payload,
        }


@dataclass(frozen=True, slots=True)
class NativeTurbulenceSolution:
    """Transition/separation/field outputs returned by a native backend."""

    transition_location_fraction: float | None
    separation_fraction: float
    skin_friction: tuple[float, ...]
    pressure_coefficient: tuple[float, ...]
    detail: str = ""


@runtime_checkable
class NativeTurbulenceBackend(Protocol):
    """The injectable native turbulence backend contract."""

    backend_id: str
    software_version: str

    def solve(self, request: NativeTurbulenceRequest) -> NativeTurbulenceSolution: ...


@dataclass(frozen=True, slots=True)
class NativeTurbulenceResult:
    """Native turbulence outcome with full solver identity and provenance."""

    request: NativeTurbulenceRequest
    solution: NativeTurbulenceSolution
    solver_name: str
    solver_version: str
    run_id: str
    source: ResultSource
    validity: Validity
    provenance: Provenance
    software: SoftwareIdentity = SOFTWARE_IDENTITY

    def canonical(self) -> dict[str, Any]:
        return {
            "request": self.request.canonical(),
            "transitionLocationFraction": self.solution.transition_location_fraction,
            "separationFraction": self.solution.separation_fraction,
            "skinFriction": list(self.solution.skin_friction),
            "pressureCoefficient": list(self.solution.pressure_coefficient),
            "detail": self.solution.detail,
            "source": self.source.value,
            "validity": self.validity.canonical(),
            "units": {
                "transitionLocationFraction": "1",
                "separationFraction": "1",
                "skinFriction": "1",
                "pressureCoefficient": "1",
            },
            "inputsHash": self.provenance.inputs_hash,
            "solver": {
                "name": self.solver_name,
                "version": self.solver_version,
                "runId": self.run_id,
            },
            "software": self.software.canonical(),
        }


def build_native_turbulence_request(
    flow: FlowState,
    selection: ModelSelection,
    *,
    wall_requirement: WallTreatmentRequirement | None = None,
    roughness: RoughnessSpec | None = None,
    reason: str,
) -> NativeTurbulenceRequest:
    """Assemble the native request from the generic flow-model contract."""
    mode = wall_requirement.mode if wall_requirement is not None else WallTreatmentMode.NONE
    resolved_roughness = roughness or flow.roughness
    payload: dict[str, Any] = {
        "flow": flow.canonical(),
        "selection": selection.canonical(),
        "wallRequirement": (
            wall_requirement.canonical() if wall_requirement is not None else None
        ),
        "roughness": resolved_roughness.canonical() if resolved_roughness else None,
    }
    return NativeTurbulenceRequest(
        case_label=flow.label,
        model=selection.model,
        fidelity=selection.fidelity,
        wall_treatment=mode,
        roughness_equivalent_sand_grain_m=(
            resolved_roughness.equivalent_sand_grain_m
            if resolved_roughness is not None
            else None
        ),
        reynolds_number=flow.reynolds_number,
        mach_number=flow.mach_number,
        transition_state=flow.transition_state.value,
        reason=reason,
        payload=payload,
    )


def evaluate_native_turbulence(
    flow: FlowState,
    selection: ModelSelection,
    *,
    backend: NativeTurbulenceBackend | None = None,
    run_id: str | None = None,
    wall_requirement: WallTreatmentRequirement | None = None,
    roughness: RoughnessSpec | None = None,
    reason: str = "outside screening correlation validity",
) -> NativeTurbulenceResult:
    """Run the native turbulence seam, or fail closed when no backend is wired."""
    if backend is None:
        capability = probe_any_native_turbulence_capability()
        raise TurbulenceCapabilityUnavailableError(
            f"NATIVE_TURBULENCE_BACKEND_REQUIRED:{capability.detail}"
        )
    if run_id is None or not run_id.strip():
        raise TurbulenceValidationError("NATIVE_TURBULENCE_RUN_ID_REQUIRED")
    request = build_native_turbulence_request(
        flow,
        selection,
        wall_requirement=wall_requirement,
        roughness=roughness,
        reason=reason,
    )
    solution = backend.solve(request)
    if not isfinite(solution.separation_fraction) or not 0.0 <= solution.separation_fraction <= 1.0:
        raise TurbulenceValidationError("NATIVE_TURBULENCE_SOLUTION_INVALID")
    if not all(isfinite(value) for value in solution.skin_friction):
        raise TurbulenceValidationError("NATIVE_TURBULENCE_SKIN_FRICTION_NONFINITE")
    if not all(isfinite(value) for value in solution.pressure_coefficient):
        raise TurbulenceValidationError("NATIVE_TURBULENCE_PRESSURE_COEFFICIENT_NONFINITE")
    provenance = native_provenance(
        model=_MODEL_NAME,
        solver_name=backend.backend_id,
        solver_version=backend.software_version,
        run_id=run_id,
        inputs={"request": request.canonical()},
        assumptions=("native turbulence engine solved the escalated case",),
    )
    validity = Validity(
        passed=True,
        checks={"solution_finite": True, "native_identity": True},
        detail=solution.detail or "native turbulence solution accepted",
    )
    return NativeTurbulenceResult(
        request=request,
        solution=solution,
        solver_name=backend.backend_id,
        solver_version=backend.software_version,
        run_id=run_id,
        source=ResultSource.NATIVE_SOLVER,
        validity=validity,
        provenance=provenance,
    )


def solve_native_turbulence_or_fail(
    flow: FlowState,
    selection: ModelSelection,
    *,
    backend: NativeTurbulenceBackend | None = None,
    run_id: str | None = None,
    wall_requirement: WallTreatmentRequirement | None = None,
    roughness: RoughnessSpec | None = None,
    reason: str = "native turbulence fidelity requested",
) -> NativeTurbulenceResult:
    """Explicit fail-closed entry point for a native turbulence request."""
    return evaluate_native_turbulence(
        flow,
        selection,
        backend=backend,
        run_id=run_id,
        wall_requirement=wall_requirement,
        roughness=roughness,
        reason=reason,
    )


__all__ = [
    "DEFAULT_ROUGHNESS_CONSTANT_CS",
    "DEFAULT_ROUGHNESS_CONSTANT_SOURCE",
    "ROUGHNESS_WALL_FUNCTION",
    "NativeTurbulenceBackend",
    "NativeTurbulenceCapability",
    "NativeTurbulenceRequest",
    "NativeTurbulenceResult",
    "NativeTurbulenceSolution",
    "SolverFlowModel",
    "build_native_turbulence_request",
    "derive_solver_flow_model",
    "evaluate_native_turbulence",
    "openfoam_turbulence_properties",
    "openfoam_wall_roughness",
    "probe_any_native_turbulence_capability",
    "probe_native_turbulence_capability",
    "require_native_turbulence_capability",
    "solve_native_turbulence_or_fail",
]
