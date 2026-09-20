"""Typed external-aerodynamics contracts: reference, coefficients, derivatives.

The single contract that trim (:issue:`79`) consumes is
:class:`ExternalAeroResult`. It carries:

* an atmosphere-aware :class:`AeroReference` (area/span/chord, moment reference,
  density/velocity/speed-of-sound/viscosity, attitude, Mach and Reynolds);
* the six force/moment coefficients :class:`AeroCoefficients` (``CL``, ``CD``,
  ``CY``, ``Cl``, ``Cm``, ``Cn``);
* a typed :class:`AeroDerivatives` set of stability/control derivatives;
* a per-check :class:`AeroValidity` verdict against declared Mach/Reynolds/alpha
  limits;
* an optional :class:`ConvergenceRecord` (numerical-independence signal);
* distributed :class:`SpanLoad` records where the fidelity provides them;
* :class:`aeroworkbench_core.types.Provenance` and the package software identity.

Every payload is deterministic and hashable; :attr:`ExternalAeroResult.content_hash`
is the canonical SHA-256 identity consumed by downstream cache/promotion logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite

from aeroworkbench_core.types import FidelityLevel, Provenance, ResultSource
from aeroworkbench_fluid_properties import SoftwareIdentity

from ..canonical import content_digest, normalize_numbers
from .errors import ExternalAeroValidationError

SOFTWARE_NAME = "aeroworkbench-airframe-external-aero"
SOFTWARE_VERSION = "1.0.0"
SOFTWARE_IDENTITY = SoftwareIdentity(name=SOFTWARE_NAME, version=SOFTWARE_VERSION)


class ExternalAeroFidelity(StrEnum):
    """Staged external-aerodynamics fidelity ladder.

    ``ANALYTICAL`` and ``LIFTING_LINE`` are closed-form screening levels.
    ``VLM`` is a real vortex-lattice solution (still analytical/numerical, never
    native). ``VSPAERO`` is the governed native OpenVSP path and is
    capability-gated fail-closed. ``FULL_FIELD`` is the OpenFOAM/SU2 seam and is
    deliberately unimplemented here.
    """

    ANALYTICAL = "analytical"
    LIFTING_LINE = "lifting_line"
    VLM = "vlm"
    VSPAERO = "vspaero"
    FULL_FIELD = "full_field"

    def result_source(self) -> ResultSource:
        if self is ExternalAeroFidelity.VSPAERO:
            return ResultSource.NATIVE_SOLVER
        return ResultSource.ANALYTICAL

    def core_level(self) -> FidelityLevel:
        if self is ExternalAeroFidelity.VSPAERO:
            return FidelityLevel.TRANSIENT
        return FidelityLevel.ANALYTICAL


#: Canonical derivative keys shared with the trim workstream.
D_CL_D_ALPHA = "dCL/dalpha"
D_CD_D_ALPHA = "dCD/dalpha"
D_CY_D_ALPHA = "dCY/dalpha"
D_CM_D_ALPHA = "dCm/dalpha"
D_CL_D_BETA = "dCL/dbeta"
D_CY_D_BETA = "dCY/dbeta"
D_CM_D_BETA = "dCm/dbeta"
D_CL_D_ROLL_RATE = "dCl/dp"
D_CM_D_PITCH_RATE = "dCm/dq"
D_CN_D_YAW_RATE = "dCn/dr"


@dataclass(frozen=True, slots=True)
class AeroValidityLimits:
    """Declared Mach/Reynolds/alpha/beta validity bands with a cited source."""

    model_id: str
    source: str
    mach_min: float
    mach_max: float
    reynolds_min: float
    reynolds_max: float
    alpha_min_deg: float
    alpha_max_deg: float
    beta_min_deg: float
    beta_max_deg: float

    def __post_init__(self) -> None:
        if not self.model_id.strip() or not self.source.strip():
            raise ExternalAeroValidationError("VALIDITY_LIMITS_IDENTITY_REQUIRED")
        for label, low, high in (
            ("mach", self.mach_min, self.mach_max),
            ("reynolds", self.reynolds_min, self.reynolds_max),
            ("alpha", self.alpha_min_deg, self.alpha_max_deg),
            ("beta", self.beta_min_deg, self.beta_max_deg),
        ):
            if not isfinite(low) or not isfinite(high) or low >= high:
                raise ExternalAeroValidationError(f"VALIDITY_BAND_INVALID:{label}")

    def canonical(self) -> dict[str, object]:
        return {
            "modelId": self.model_id,
            "source": self.source,
            "machMin": self.mach_min,
            "machMax": self.mach_max,
            "reynoldsMin": self.reynolds_min,
            "reynoldsMax": self.reynolds_max,
            "alphaMinDeg": self.alpha_min_deg,
            "alphaMaxDeg": self.alpha_max_deg,
            "betaMinDeg": self.beta_min_deg,
            "betaMaxDeg": self.beta_max_deg,
        }


VLM_VALIDITY_LIMITS = AeroValidityLimits(
    model_id="vlm-thin-attached-flow",
    source="linear vortex-lattice theory; attached, subsonic, small-angle assumptions",
    mach_min=0.0,
    mach_max=0.7,
    reynolds_min=5.0e4,
    reynolds_max=1.0e8,
    alpha_min_deg=-12.0,
    alpha_max_deg=18.0,
    beta_min_deg=-15.0,
    beta_max_deg=15.0,
)

ANALYTICAL_VALIDITY_LIMITS = AeroValidityLimits(
    model_id="analytical-screening-subsonic",
    source="closed-form finite-wing screening; incompressible attached subsonic flow",
    mach_min=0.0,
    mach_max=0.6,
    reynolds_min=1.0e5,
    reynolds_max=1.0e8,
    alpha_min_deg=-10.0,
    alpha_max_deg=15.0,
    beta_min_deg=-12.0,
    beta_max_deg=12.0,
)

VSPAERO_VALIDITY_LIMITS = AeroValidityLimits(
    model_id="vspaero-native-lifting-surface",
    source="OpenVSP/VSPAERO declared by the native solver run; propagated verbatim",
    mach_min=0.0,
    mach_max=1.5,
    reynolds_min=1.0e4,
    reynolds_max=1.0e9,
    alpha_min_deg=-20.0,
    alpha_max_deg=20.0,
    beta_min_deg=-30.0,
    beta_max_deg=30.0,
)


@dataclass(frozen=True, slots=True)
class AeroReference:
    """Atmosphere-aware aerodynamic reference and operating point."""

    area_m2: float
    span_m: float
    mean_chord_m: float
    moment_reference_m: tuple[float, float, float]
    density_kg_m3: float
    velocity_m_s: float | None = None
    speed_m_s: float | None = None
    speed_of_sound_m_s: float | None = None
    viscosity_pa_s: float | None = None
    mach_number: float | None = None
    reynolds_number: float | None = None
    alpha_deg: float = 0.0
    beta_deg: float = 0.0
    angular_rates: tuple[float, float, float] = (0.0, 0.0, 0.0)
    altitude_m: float | None = None
    atmosphere_model: str = "ISA@1"
    source: str = "declared"

    def __post_init__(self) -> None:
        for label, value in (
            ("AREA", self.area_m2),
            ("SPAN", self.span_m),
            ("MEAN_CHORD", self.mean_chord_m),
            ("DENSITY", self.density_kg_m3),
        ):
            if not isfinite(value) or value <= 0.0:
                raise ExternalAeroValidationError(f"REFERENCE_{label}_NOT_POSITIVE")
        velocity = self.velocity_m_s if self.velocity_m_s is not None else self.speed_m_s
        if velocity is None or not isfinite(velocity) or velocity < 0.0:
            raise ExternalAeroValidationError("REFERENCE_VELOCITY_INVALID")
        object.__setattr__(self, "velocity_m_s", float(velocity))
        if self.speed_of_sound_m_s is not None and (
            not isfinite(self.speed_of_sound_m_s) or self.speed_of_sound_m_s <= 0.0
        ):
            raise ExternalAeroValidationError("REFERENCE_SPEED_OF_SOUND_NOT_POSITIVE")
        if self.viscosity_pa_s is not None and (
            not isfinite(self.viscosity_pa_s) or self.viscosity_pa_s <= 0.0
        ):
            raise ExternalAeroValidationError("REFERENCE_VISCOSITY_NOT_POSITIVE")
        if self.mach_number is not None and (
            not isfinite(self.mach_number) or self.mach_number < 0.0
        ):
            raise ExternalAeroValidationError("REFERENCE_MACH_INVALID")
        if self.reynolds_number is not None and (
            not isfinite(self.reynolds_number) or self.reynolds_number < 0.0
        ):
            raise ExternalAeroValidationError("REFERENCE_REYNOLDS_INVALID")
        if self.mach_number is None and self.speed_of_sound_m_s is None:
            raise ExternalAeroValidationError("REFERENCE_MACH_UNRESOLVABLE")
        if self.reynolds_number is None and self.viscosity_pa_s is None:
            raise ExternalAeroValidationError("REFERENCE_REYNOLDS_UNRESOLVABLE")
        for label, value in (
            ("ALPHA", self.alpha_deg),
            ("BETA", self.beta_deg),
            ("MOMENT_REFERENCE", self.moment_reference_m[0]),
            ("MOMENT_REFERENCE", self.moment_reference_m[1]),
            ("MOMENT_REFERENCE", self.moment_reference_m[2]),
            ("ANGULAR_RATE", self.angular_rates[0]),
            ("ANGULAR_RATE", self.angular_rates[1]),
            ("ANGULAR_RATE", self.angular_rates[2]),
        ):
            if not isfinite(value):
                raise ExternalAeroValidationError(f"REFERENCE_{label}_NOT_FINITE")
        if not self.source.strip() or not self.atmosphere_model.strip():
            raise ExternalAeroValidationError("REFERENCE_SOURCE_REQUIRED")

    @property
    def resolved_velocity_m_s(self) -> float:
        assert self.velocity_m_s is not None
        return self.velocity_m_s

    @property
    def dynamic_pressure_pa(self) -> float:
        return 0.5 * self.density_kg_m3 * self.resolved_velocity_m_s**2

    @property
    def resolved_mach_number(self) -> float:
        if self.mach_number is not None:
            return self.mach_number
        assert self.speed_of_sound_m_s is not None
        return self.resolved_velocity_m_s / self.speed_of_sound_m_s

    @property
    def resolved_reynolds_number(self) -> float:
        if self.reynolds_number is not None:
            return self.reynolds_number
        assert self.viscosity_pa_s is not None
        return (
            self.density_kg_m3 * self.resolved_velocity_m_s * self.mean_chord_m / self.viscosity_pa_s  # noqa: E501
        )

    def with_state(
        self,
        *,
        alpha_deg: float,
        beta_deg: float = 0.0,
        angular_rates: tuple[float, float, float] = (0.0, 0.0, 0.0),
    ) -> AeroReference:
        return AeroReference(
            area_m2=self.area_m2,
            span_m=self.span_m,
            mean_chord_m=self.mean_chord_m,
            moment_reference_m=self.moment_reference_m,
            density_kg_m3=self.density_kg_m3,
            velocity_m_s=self.resolved_velocity_m_s,
            speed_of_sound_m_s=self.speed_of_sound_m_s,
            viscosity_pa_s=self.viscosity_pa_s,
            mach_number=self.mach_number,
            reynolds_number=self.reynolds_number,
            alpha_deg=alpha_deg,
            beta_deg=beta_deg,
            angular_rates=angular_rates,
            altitude_m=self.altitude_m,
            atmosphere_model=self.atmosphere_model,
            source=self.source,
        )

    def canonical(self) -> dict[str, object]:
        return {
            "areaM2": self.area_m2,
            "spanM": self.span_m,
            "meanChordM": self.mean_chord_m,
            "momentReferenceM": list(self.moment_reference_m),
            "densityKgM3": self.density_kg_m3,
            "velocityMS": self.resolved_velocity_m_s,
            "speedOfSoundMS": self.speed_of_sound_m_s,
            "viscosityPaS": self.viscosity_pa_s,
            "alphaDeg": self.alpha_deg,
            "betaDeg": self.beta_deg,
            "angularRates": list(self.angular_rates),
            "altitudeM": self.altitude_m,
            "atmosphereModel": self.atmosphere_model,
            "machNumber": self.resolved_mach_number,
            "reynoldsNumber": self.resolved_reynolds_number,
            "dynamicPressurePa": self.dynamic_pressure_pa,
            "source": self.source,
        }


@dataclass(frozen=True, slots=True)
class AeroValidity:
    """Per-check validity verdict against declared limits."""

    passed: bool
    checks: tuple[tuple[str, bool], ...]
    detail: str
    limits: AeroValidityLimits

    def __post_init__(self) -> None:
        if not self.detail.strip():
            raise ExternalAeroValidationError("VALIDITY_DETAIL_REQUIRED")

    def check_dict(self) -> dict[str, bool]:
        return dict(self.checks)

    def canonical(self) -> dict[str, object]:
        return {
            "passed": self.passed,
            "checks": {name: value for name, value in self.checks},
            "detail": self.detail,
            "limits": self.limits.canonical(),
        }


def evaluate_aero_validity(
    reference: AeroReference, limits: AeroValidityLimits
) -> AeroValidity:
    """Evaluate a reference against declared limits (never optimistic)."""

    checks = (
        ("mach_in_range", limits.mach_min <= reference.resolved_mach_number <= limits.mach_max),
        (
            "reynolds_in_range",
            limits.reynolds_min <= reference.resolved_reynolds_number <= limits.reynolds_max,
        ),
        ("alpha_in_range", limits.alpha_min_deg <= reference.alpha_deg <= limits.alpha_max_deg),
        ("beta_in_range", limits.beta_min_deg <= reference.beta_deg <= limits.beta_max_deg),
        ("velocity_at_least_sonic_margin", reference.resolved_mach_number < 1.0),
    )
    failed = [name for name, ok in checks if not ok]
    passed = not failed
    detail = (
        f"within {limits.model_id}"
        if passed
        else f"outside {limits.model_id}: {','.join(failed)}"
    )
    return AeroValidity(passed=passed, checks=checks, detail=detail, limits=limits)


@dataclass(frozen=True, slots=True)
class AeroCoefficients:
    """The six non-dimensional aerodynamic force/moment coefficients."""

    lift: float
    drag: float
    side: float
    roll: float
    pitch: float
    yaw: float

    def __post_init__(self) -> None:
        for label, value in (
            ("LIFT", self.lift),
            ("DRAG", self.drag),
            ("SIDE", self.side),
            ("ROLL", self.roll),
            ("PITCH", self.pitch),
            ("YAW", self.yaw),
        ):
            if not isfinite(value):
                raise ExternalAeroValidationError(f"COEFFICIENT_{label}_NOT_FINITE")

    @property
    def lift_to_drag(self) -> float:
        if self.drag == 0.0:
            return 0.0
        return self.lift / self.drag

    def canonical(self) -> dict[str, float]:
        return {
            "CL": self.lift,
            "CD": self.drag,
            "CY": self.side,
            "Cl": self.roll,
            "Cm": self.pitch,
            "Cn": self.yaw,
        }


@dataclass(frozen=True, slots=True)
class AeroDerivatives:
    """Named stability/control derivatives with the finite-difference method."""

    values: tuple[tuple[str, float], ...]
    method: str
    step_deg: float

    def __post_init__(self) -> None:
        if not self.values:
            raise ExternalAeroValidationError("DERIVATIVES_REQUIRE_VALUES")
        seen: set[str] = set()
        for key, value in self.values:
            if not key.strip():
                raise ExternalAeroValidationError("DERIVATIVE_KEY_REQUIRED")
            if key in seen:
                raise ExternalAeroValidationError(f"DUPLICATE_DERIVATIVE:{key}")
            seen.add(key)
            if not isfinite(value):
                raise ExternalAeroValidationError(f"DERIVATIVE_NOT_FINITE:{key}")
        if not self.method.strip():
            raise ExternalAeroValidationError("DERIVATIVE_METHOD_REQUIRED")
        if not isfinite(self.step_deg) or self.step_deg <= 0.0:
            raise ExternalAeroValidationError("DERIVATIVE_STEP_INVALID")

    def get(self, key: str) -> float | None:
        for name, value in self.values:
            if name == key:
                return value
        return None

    def require(self, key: str) -> float:
        value = self.get(key)
        if value is None:
            raise ExternalAeroValidationError(f"MISSING_DERIVATIVE:{key}")
        return value

    @property
    def dcl_dalpha(self) -> float:
        return self.require(D_CL_D_ALPHA)

    @property
    def dcm_dalpha(self) -> float:
        return self.require(D_CM_D_ALPHA)

    def canonical(self) -> dict[str, object]:
        return {
            "method": self.method,
            "stepDeg": self.step_deg,
            "values": {key: value for key, value in self.values},
        }


@dataclass(frozen=True, slots=True)
class SpanLoad:
    """One spanwise strip's resolved load (dimensionless section and per-span)."""

    surface_id: str
    span_fraction: float
    arc_m: float
    chord_m: float
    section_lift_coefficient: float
    circulation_m2_s: float
    lift_per_span_n_m: float
    induced_alpha_deg: float

    def __post_init__(self) -> None:
        if not self.surface_id.strip():
            raise ExternalAeroValidationError("SPAN_LOAD_SURFACE_REQUIRED")
        for label, value in (
            ("SPAN_FRACTION", self.span_fraction),
            ("ARC", self.arc_m),
            ("CHORD", self.chord_m),
            ("SECTION_CL", self.section_lift_coefficient),
            ("CIRCULATION", self.circulation_m2_s),
            ("LIFT_PER_SPAN", self.lift_per_span_n_m),
            ("INDUCED_ALPHA", self.induced_alpha_deg),
        ):
            if not isfinite(value):
                raise ExternalAeroValidationError(f"SPAN_LOAD_{label}_NOT_FINITE")

    def canonical(self) -> dict[str, object]:
        return {
            "surfaceId": self.surface_id,
            "spanFraction": self.span_fraction,
            "arcM": self.arc_m,
            "chordM": self.chord_m,
            "sectionLiftCoefficient": self.section_lift_coefficient,
            "circulationM2S": self.circulation_m2_s,
            "liftPerSpanNm": self.lift_per_span_n_m,
            "inducedAlphaDeg": self.induced_alpha_deg,
        }


@dataclass(frozen=True, slots=True)
class ConvergenceRecord:
    """Numerical-independence evidence from a declared refinement ladder."""

    kind: str
    levels: tuple[str, ...]
    quantity_names: tuple[str, ...]
    quantity_values: tuple[tuple[float, ...], ...]
    observed_order: float | None
    accepted: bool
    reason: str

    def __post_init__(self) -> None:
        if not self.kind.strip() or not self.levels:
            raise ExternalAeroValidationError("CONVERGENCE_IDENTITY_REQUIRED")
        if len(self.quantity_names) != len(self.quantity_values):
            raise ExternalAeroValidationError("CONVERGENCE_QUANTITY_MISMATCH")
        for values in self.quantity_values:
            if len(values) != len(self.levels):
                raise ExternalAeroValidationError("CONVERGENCE_LEVEL_COUNT_MISMATCH")
            for value in values:
                if not isfinite(value):
                    raise ExternalAeroValidationError("CONVERGENCE_VALUE_NOT_FINITE")

    def canonical(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "levels": list(self.levels),
            "quantityNames": list(self.quantity_names),
            "quantityValues": [list(values) for values in self.quantity_values],
            "observedOrder": self.observed_order,
            "accepted": self.accepted,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class ExternalAeroResult:
    """Canonical external-aerodynamics result consumed by trim (:issue:`79`)."""

    result_id: str
    fidelity: ExternalAeroFidelity
    source: ResultSource
    reference: AeroReference
    coefficients: AeroCoefficients
    validity: AeroValidity
    provenance: Provenance
    derivatives: AeroDerivatives | None = None
    distributed_loads: tuple[SpanLoad, ...] = ()
    convergence: ConvergenceRecord | None = None
    artifacts: tuple[str, ...] = ()
    solver_name: str | None = None
    solver_version: str | None = None
    run_id: str | None = None
    software: SoftwareIdentity = SOFTWARE_IDENTITY

    def __post_init__(self) -> None:
        if not self.result_id.strip():
            raise ExternalAeroValidationError("RESULT_ID_REQUIRED")
        if self.source is ResultSource.NATIVE_SOLVER and not all(
            (self.solver_name, self.solver_version, self.run_id)
        ):
            raise ExternalAeroValidationError("NATIVE_RESULT_REQUIRES_SOLVER_IDENTITY")
        if self.fidelity is not ExternalAeroFidelity.VSPAERO and (
            self.source is ResultSource.NATIVE_SOLVER
        ):
            raise ExternalAeroValidationError("NON_VSPAERO_RESULT_CANNOT_BE_NATIVE")

    def canonical(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "resultId": self.result_id,
            "fidelity": self.fidelity.value,
            "source": self.source.value,
            "reference": self.reference.canonical(),
            "coefficients": self.coefficients.canonical(),
            "derivatives": None if self.derivatives is None else self.derivatives.canonical(),
            "validity": self.validity.canonical(),
            "distributedLoads": [load.canonical() for load in self.distributed_loads],
            "convergence": None if self.convergence is None else self.convergence.canonical(),
            "artifacts": list(self.artifacts),
            "solver": {
                "name": self.solver_name,
                "version": self.solver_version,
                "runId": self.run_id,
            },
            "inputsHash": self.provenance.inputs_hash,
            "software": self.software.canonical(),
        }
        return _normalized(payload)

    @property
    def content_hash(self) -> str:
        return content_digest(self.canonical())


def _normalized(payload: dict[str, object]) -> dict[str, object]:
    normalized = normalize_numbers(payload)
    if not isinstance(normalized, dict):
        raise ExternalAeroValidationError("RESULT_PAYLOAD_NOT_A_MAPPING")
    return normalized


__all__ = [
    "ANALYTICAL_VALIDITY_LIMITS",
    "D_CD_D_ALPHA",
    "D_CL_D_ALPHA",
    "D_CL_D_BETA",
    "D_CL_D_ROLL_RATE",
    "D_CM_D_ALPHA",
    "D_CM_D_BETA",
    "D_CM_D_PITCH_RATE",
    "D_CN_D_YAW_RATE",
    "D_CY_D_ALPHA",
    "D_CY_D_BETA",
    "SOFTWARE_IDENTITY",
    "SOFTWARE_NAME",
    "SOFTWARE_VERSION",
    "VLM_VALIDITY_LIMITS",
    "VSPAERO_VALIDITY_LIMITS",
    "AeroCoefficients",
    "AeroDerivatives",
    "AeroReference",
    "AeroValidity",
    "AeroValidityLimits",
    "ConvergenceRecord",
    "ExternalAeroFidelity",
    "ExternalAeroResult",
    "SpanLoad",
    "evaluate_aero_validity",
]
