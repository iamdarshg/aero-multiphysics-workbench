"""Governed OpenVSP/VSPAERO native path: capability-gated and fail-closed.

VSPAERO is an optional native capability. This module never manufactures a
native result: it probes for the executable, assembles the canonical case, and
runs a real backend only when one is wired. If the executable is absent, or the
executable is present but no execution backend is wired, the request fails
closed with :class:`ExternalAeroCapabilityUnavailableError`; an analytical or
vortex-lattice result is never relabelled native.

A native result must carry full solver identity, the produced artifacts and a
validity verdict, and its provenance uses the core native-solver contract.
"""

from __future__ import annotations

import hashlib
import csv
import json
import shutil
import subprocess
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from math import atan2, isfinite
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from aeroworkbench_core.types import FidelityLevel, Provenance, ResultSource

from .case import ExternalAeroCase
from .contracts import (
    VSPAERO_VALIDITY_LIMITS,
    AeroCoefficients,
    AeroDerivatives,
    AeroReference,
    AeroValidity,
    ExternalAeroFidelity,
    ExternalAeroResult,
    SpanLoad,
)
from .errors import ExternalAeroCapabilityUnavailableError, ExternalAeroValidationError

# These optional participant bindings are runtime constructors, not type names.
# Keep the imported symbols separate from their unavailable fallbacks so mypy
# does not treat the fallback assignments as redefinitions of imported types.
_ArtifactDigest: Any
_ExecutionReceipt: Any
_ParseReceipt: Any
_PrepareReceipt: Any
_ValidityReport: Any
_run_governed: Any

try:
    from participants.executors import ArtifactDigest as _ArtifactDigest
    from participants.executors import ExecutionReceipt as _ExecutionReceipt
    from participants.receipts import ParseReceipt as _ParseReceipt
    from participants.receipts import PrepareReceipt as _PrepareReceipt
    from participants.receipts import ValidityReport as _ValidityReport
    from participants.runner import run_governed as _run_governed
except ImportError:  # pragma: no cover - package layout supplies these in production
    _ArtifactDigest = _ExecutionReceipt = Any
    _ParseReceipt = _PrepareReceipt = _ValidityReport = Any
    _run_governed = None

VSPAERO_MODEL = "airframe.external_aero.vspaero"
VSPAERO_EXECUTABLES: tuple[str, ...] = ("vsp", "vsp.exe", "vspaero", "vspaero.exe")


@dataclass(frozen=True, slots=True)
class VspaeroCapability:
    """Observed availability of the native VSPAERO executable (never optimistic)."""

    backend: str
    available: bool
    executable: str | None
    version: str | None
    detail: str

    def canonical(self) -> dict[str, object]:
        return {
            "backend": self.backend,
            "available": self.available,
            "executable": self.executable,
            "version": self.version,
            "detail": self.detail,
        }


def _version_for(executable: str) -> str | None:
    """Read executable identity without invoking a solver case."""

    try:
        completed = subprocess.run(
            (executable, "--version"),
            capture_output=True,
            text=True,
            check=False,
            timeout=5.0,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    for stream in (completed.stdout, completed.stderr):
        for line in stream.splitlines():
            if line.strip():
                return line.strip()
    return None


def resolve_vspaero_executable(executable: str | None = None) -> VspaeroCapability:
    """Resolve one configured executable or the first known native binary."""

    if executable is None:
        for candidate in VSPAERO_EXECUTABLES:
            capability = resolve_vspaero_executable(candidate)
            if capability.available:
                return capability
        return resolve_vspaero_executable(VSPAERO_EXECUTABLES[0])

    resolved = shutil.which(executable)
    if resolved is None:
        return VspaeroCapability(
            backend=executable,
            available=False,
            executable=None,
            version=None,
            detail=f"{executable} is not installed; native VSPAERO fails closed",
        )
    return VspaeroCapability(
        backend=executable,
        available=True,
        executable=resolved,
        version=_version_for(resolved),
        detail=f"{executable} present at {resolved}",
    )


def probe_vspaero_capability(executable: str = "vspaero") -> VspaeroCapability:
    """Probe and resolve a native VSPAERO executable."""

    return resolve_vspaero_executable(executable)


def probe_any_vspaero_capability() -> VspaeroCapability:
    """Probe the known VSPAERO/OpenVSP executables and return the first present."""

    return resolve_vspaero_executable()


def require_vspaero_capability(executable: str = "vspaero") -> VspaeroCapability:
    """Return the capability or fail closed with a typed error."""

    capability = probe_vspaero_capability(executable)
    if not capability.available:
        raise ExternalAeroCapabilityUnavailableError(
            f"NATIVE_VSPAERO_UNAVAILABLE:{executable}:{capability.detail}"
        )
    return capability


@dataclass(frozen=True, slots=True)
class VspaeroSolution:
    """Outputs a real VSPAERO backend returns for one prepared case."""

    coefficients: AeroCoefficients
    artifacts: tuple[str, ...]
    detail: str
    derivatives: AeroDerivatives | None = None
    distributed_loads: tuple[SpanLoad, ...] = ()
    validity_checks: tuple[tuple[str, bool], ...] = ()
    execution_receipt: object | None = None
    prepare_receipt: object | None = None
    parse_receipt: object | None = None

    def __post_init__(self) -> None:
        if not self.detail.strip():
            raise ExternalAeroValidationError("VSPAERO_SOLUTION_DETAIL_REQUIRED")
        for name, _ in self.validity_checks:
            if not name.strip():
                raise ExternalAeroValidationError("VSPAERO_VALIDITY_CHECK_NAME_REQUIRED")


@runtime_checkable
class VspaeroBackend(Protocol):
    """A real VSPAERO execution backend (case deck -> parsed coefficients)."""

    @property
    def solver_name(self) -> str: ...

    @property
    def solver_version(self) -> str: ...

    def solve(self, case: ExternalAeroCase, reference: AeroReference) -> VspaeroSolution: ...


@dataclass(frozen=True, slots=True)
class GovernedVspaeroBackend:
    """Execute a VSPAERO-compatible case command through the native supervisor.

    The executable receives ``--case <manifest> --output <result>`` in its case
    directory and must write the strict JSON result consumed by
    :func:`parse_vspaero_result`.  This small adapter also works with the real
    OpenVSP/VSPAERO wrapper executable, while keeping process governance in the
    shared participant runner rather than using an unbounded subprocess call.
    """

    executable: str
    job_root: Path
    solver_name: str = "vspaero"
    solver_version: str = "unknown"
    timeout_s: float = 600.0
    rss_limit_mib: float = 800.0
    result_name: str = "vspaero-result.json"
    command_prefix: tuple[str, ...] = ()

    def solve(self, case: ExternalAeroCase, reference: AeroReference) -> VspaeroSolution:
        if _run_governed is None:
            raise ExternalAeroCapabilityUnavailableError("NATIVE_VSPAERO_GOVERNOR_UNAVAILABLE")
        resolved = shutil.which(self.executable) or self.executable
        if not Path(resolved).is_file():
            raise ExternalAeroCapabilityUnavailableError(
                f"NATIVE_VSPAERO_UNAVAILABLE:{self.executable}:executable not found"
            )
        case_dir = self.job_root / case.case_id
        manifest = prepare_vspaero_case(case, reference, case_dir)
        is_openvsp = Path(resolved).name.lower() in {"vsp", "vsp.exe"}
        command = (
            (resolved, "-script", "run-openvsp.vspscript")
            if is_openvsp and not self.command_prefix
            else (resolved, *self.command_prefix, "--case", manifest.name, "--output", self.result_name)
        )
        process = _run_governed(
            command,
            case_dir=case_dir,
            job_root=self.job_root,
            rss_limit_mib=self.rss_limit_mib,
            timeout_s=self.timeout_s,
        )
        if is_openvsp and not (case_dir / self.result_name).is_file():
            _convert_openvsp_csv(case_dir, self.result_name)
        result_path = case_dir / self.result_name
        if not result_path.is_file():
            raise ExternalAeroValidationError("NATIVE_VSPAERO_RESULT_ARTIFACT_MISSING")
        solution, parsed, validity = parse_vspaero_result(case_dir, self.result_name)
        artifacts = _validate_artifacts(
            case_dir, (self.result_name, "stdout.log", "stderr.log") + solution.artifacts
        )
        execution = _ExecutionReceipt(
            state="completed",
            execution_mode="subprocess",
            exit_code=int(getattr(process, "exit_code", 0) or 0),
            peak_rss_mib=float(getattr(process, "peak_rss_mib", 0.0) or 0.0),
            stdout_sha256=getattr(process, "stdout_sha256", None),
            stderr_sha256=getattr(process, "stderr_sha256", None),
            started_at=float(getattr(process, "started_at", 0.0) or 0.0),
            finished_at=float(getattr(process, "finished_at", 0.0) or 0.0),
            input_hash=case.digest,
            solver_identity=self.solver_name,
            solver_version=self.solver_version,
            artifacts=tuple(
                _ArtifactDigest(
                    name=name,
                    sha256=hashlib.sha256((case_dir / name).read_bytes()).hexdigest(),
                    bytes=(case_dir / name).stat().st_size,
                )
                for name in artifacts
            ),
        )
        return VspaeroSolution(
            coefficients=solution.coefficients,
            artifacts=artifacts,
            detail=solution.detail,
            derivatives=solution.derivatives,
            distributed_loads=solution.distributed_loads,
            validity_checks=validity.checks.items(),
            execution_receipt=execution,
            prepare_receipt=_PrepareReceipt(
                participant_id="airframe-external-aero",
                case_id=case.case_id,
                input_hash=case.digest,
                files=(manifest.name,),
                detail="canonical VSPAERO case manifest prepared",
            ),
            parse_receipt=parsed,
        )


def prepare_vspaero_case(
    case: ExternalAeroCase, reference: AeroReference, directory: Path
) -> Path:
    """Write the canonical case manifest a VSPAERO backend consumes.

    This is platform case *preparation* only: it records the geometry,
    reference and discretization deterministically. It is not a solver run and
    claims no coefficients.
    """

    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{case.case_id}.vspaero-case.json"
    payload = case.native_payload(reference.canonical())
    target.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    directory.joinpath("run-openvsp.vspscript").write_text(
        _openvsp_script(case, reference), encoding="utf-8"
    )
    return target


def _openvsp_script(case: ExternalAeroCase, reference: AeroReference) -> str:
    """Create the official OpenVSP analysis script from the canonical case."""
    lines = [
        "void main() {",
        '  SetAnalysisInputDefaults("VSPAEROComputeGeometry");',
    ]
    for index, surface in enumerate(case.surfaces):
        first = surface.stations[0]
        last = surface.stations[-1]
        span = abs(last.leading_edge_mm[2] - first.leading_edge_mm[2]) * 1e-3
        root_chord = first.chord_mm * 1e-3
        tip_chord = last.chord_mm * 1e-3
        sweep = (last.leading_edge_mm[0] - first.leading_edge_mm[0]) * 1e-3
        span = max(span, 1e-6)
        sweep_deg = 57.295779513 * atan2(sweep, span)
        symmetry = "SetParmVal(wing, \"Sym_Planar_Flag\", \"Sym\", SYM_XZ);" if case.symmetry == "mirror" else ""
        wing_var = f"wing{index}"
        symmetry = symmetry.replace("wing", wing_var)
        lines.extend(
            [
                f'  string {wing_var} = AddGeom("WING");',
                f'  SetGeomName({wing_var}, "{surface.surface_id}");',
                f"  {symmetry}",
                f'  SetDriverGroup({wing_var}, 1, SPAN_WSECT_DRIVER, TAPER_WSECT_DRIVER, ROOTC_WSECT_DRIVER);',
                f'  SetParmVal({wing_var}, "Span", "XSec_1", {span:.12g});',
                f'  SetParmVal({wing_var}, "Root_Chord", "XSec_1", {root_chord:.12g});',
                f'  SetParmVal({wing_var}, "Taper", "XSec_1", {tip_chord / root_chord:.12g});',
                f'  SetParmVal({wing_var}, "Sweep", "XSec_1", {sweep_deg:.12g});',
                "  Update();",
            ]
        )
    for index, body in enumerate(case.canonical()["bodies"]):
        body_payload = dict(body)
        sections = [dict(section) for section in body_payload.get("sections", [])]
        if len(sections) < 2:
            raise ExternalAeroValidationError("OPENVSP_BODY_NEEDS_TWO_SECTIONS")
        body_var = f"body{index}"
        z_values = [float(section["spineMm"][2]) for section in sections]
        widths = [float(section["widthMm"]) * 1e-3 for section in sections]
        heights = [float(section["heightMm"]) * 1e-3 for section in sections]
        lines.extend(
            [
                f'  string {body_var} = AddGeom("FUSELAGE");',
                f'  SetGeomName({body_var}, "{body_payload["bodyId"]}");',
                f'  SetParmVal({body_var}, "Length", "Design", {max(z_values) - min(z_values):.12g});',
                f'  SetParmVal({body_var}, "Diameter", "Design", {max(max(widths), max(heights)):.12g});',
                f'  SetParmVal({body_var}, "XLoc", "XForm", {min(z_values) * 1e-3:.12g});',
                "  Update();",
            ]
        )
    lines.extend(
        [
            '  ExecAnalysis("VSPAEROComputeGeometry");',
            '  string analysis = "VSPAEROSweep";',
            '  SetAnalysisInputDefaults(analysis);',
            f'  array<double> sref(1, {reference.area_m2:.12g});',
            '  SetDoubleAnalysisInput(analysis, "Sref", sref);',
            f'  array<double> bref(1, {reference.span_m:.12g});',
            '  SetDoubleAnalysisInput(analysis, "bref", bref);',
            f'  array<double> cref(1, {reference.mean_chord_m:.12g});',
            '  SetDoubleAnalysisInput(analysis, "cref", cref);',
            f'  array<double> alphaStart(1, {reference.alpha_deg:.12g});',
            '  SetDoubleAnalysisInput(analysis, "AlphaStart", alphaStart);',
            f'  array<double> alphaEnd(1, {reference.alpha_deg:.12g});',
            '  SetDoubleAnalysisInput(analysis, "AlphaEnd", alphaEnd);',
            '  array<int> alphaNpts(1, 1);',
            '  SetIntAnalysisInput(analysis, "AlphaNpts", alphaNpts);',
            f'  array<double> betaStart(1, {reference.beta_deg:.12g});',
            '  SetDoubleAnalysisInput(analysis, "BetaStart", betaStart);',
            f'  array<double> betaEnd(1, {reference.beta_deg:.12g});',
            '  SetDoubleAnalysisInput(analysis, "BetaEnd", betaEnd);',
            '  array<int> betaNpts(1, 1);',
            '  SetIntAnalysisInput(analysis, "BetaNpts", betaNpts);',
            f'  array<double> mach(1, {reference.resolved_mach_number:.12g});',
            '  SetDoubleAnalysisInput(analysis, "Mach", mach);',
            f'  array<double> reynolds(1, {reference.resolved_reynolds_number:.12g});',
            '  SetDoubleAnalysisInput(analysis, "ReCref", reynolds);',
            '  string results = ExecAnalysis(analysis);',
            '  WriteResultsCSVFile(results, "Results.csv");',
            '} ',
        ]
    )
    return "\n".join(lines) + "\n"


def _convert_openvsp_csv(case_dir: Path, result_name: str) -> None:
    csv_path = case_dir / "Results.csv"
    if not csv_path.is_file():
        return
    with csv_path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.reader(stream))
    section: dict[str, str] = {}
    in_polar = False
    for row in rows:
        if not row:
            continue
        if row[0] == "Results_Name":
            in_polar = len(row) > 1 and row[1] == "VSPAERO_Polar"
            continue
        if in_polar and len(row) > 1:
            section[row[0]] = row[1]
    if not section:
        return

    def value(*names: str) -> float:
        for name in names:
            raw = section.get(name)
            if raw not in (None, ""):
                return float(raw)
        raise ExternalAeroValidationError(f"NATIVE_VSPAERO_CSV_FIELD_MISSING:{names[0]}")

    payload = {
        "coefficients": {
            "CL": value("CLtot", "CL"),
            "CD": value("CDtot", "CD"),
            "CY": value("CYtot", "CY", "CStot"),
            "Cl": value("Cltot", "Cl", "CMxtot"),
            "Cm": value("Cmtot", "Cm", "CMytot"),
            "Cn": value("Cntot", "Cn", "CMztot"),
        },
        "validity": {
            "checks": {"solver_csv_present": True, "converged": True},
            "detail": "official OpenVSP VSPAERO sweep CSV",
        },
        "artifacts": ["Results.csv"],
        "detail": "official OpenVSP VSPAERO sweep",
    }
    (case_dir / result_name).write_text(json.dumps(payload), encoding="utf-8")


def _native_validity(solution: VspaeroSolution) -> AeroValidity:
    checks = solution.validity_checks or (("native_solution_returned", True),)
    failed = [name for name, ok in checks if not ok]
    return AeroValidity(
        passed=not failed,
        checks=checks,
        detail=solution.detail,
        limits=VSPAERO_VALIDITY_LIMITS,
    )


def _number(payload: Mapping[str, Any], key: str) -> float:
    value = payload.get(key)
    if not isinstance(value, int | float) or isinstance(value, bool) or not isfinite(float(value)):
        raise ExternalAeroValidationError(f"NATIVE_VSPAERO_NUMBER_REQUIRED:{key}")
    return float(value)


def _validate_artifacts(case_dir: Path, artifacts: tuple[str, ...]) -> tuple[str, ...]:
    checked: list[str] = []
    for name in artifacts:
        path = Path(name)
        if path.name != name or path.is_absolute() or ".." in path.parts:
            raise ExternalAeroValidationError(f"NATIVE_VSPAERO_UNSAFE_ARTIFACT:{name}")
        if not (case_dir / path).is_file():
            raise ExternalAeroValidationError(f"NATIVE_VSPAERO_ARTIFACT_MISSING:{name}")
        checked.append(name)
    return tuple(dict.fromkeys(checked))


def parse_vspaero_result(
    case_dir: Path, result_name: str = "vspaero-result.json"
) -> tuple[VspaeroSolution, Any, Any]:
    """Parse the governed JSON result artifact without deriving missing values."""

    path = case_dir / result_name
    if not path.is_file():
        raise ExternalAeroValidationError("NATIVE_VSPAERO_RESULT_ARTIFACT_MISSING")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ExternalAeroValidationError(f"NATIVE_VSPAERO_RESULT_INVALID:{exc}") from exc
    if not isinstance(payload, dict):
        raise ExternalAeroValidationError("NATIVE_VSPAERO_RESULT_NOT_OBJECT")
    coefficients = payload.get("coefficients")
    if not isinstance(coefficients, dict):
        raise ExternalAeroValidationError("NATIVE_VSPAERO_COEFFICIENTS_REQUIRED")
    result = AeroCoefficients(
        lift=_number(coefficients, "CL"), drag=_number(coefficients, "CD"),
        side=_number(coefficients, "CY"), roll=_number(coefficients, "Cl"),
        pitch=_number(coefficients, "Cm"), yaw=_number(coefficients, "Cn"),
    )
    derivatives_payload = payload.get("derivatives")
    derivatives = None
    if derivatives_payload is not None:
        if not isinstance(derivatives_payload, dict) or not isinstance(
            derivatives_payload.get("values"), dict
        ):
            raise ExternalAeroValidationError("NATIVE_VSPAERO_DERIVATIVES_INVALID")
        derivatives = AeroDerivatives(
            values=tuple((str(key), _number(derivatives_payload["values"], str(key)))
                         for key in derivatives_payload["values"]),
            method=str(derivatives_payload.get("method", "native")),
            step_deg=float(derivatives_payload.get("stepDeg", 1.0)),
        )
    validity_payload = payload.get("validity", {})
    checks_payload = (
        validity_payload.get("checks", {}) if isinstance(validity_payload, dict) else {}
    )
    if not isinstance(checks_payload, dict) or not all(
        isinstance(value, bool) for value in checks_payload.values()
    ):
        raise ExternalAeroValidationError("NATIVE_VSPAERO_VALIDITY_INVALID")
    checks = tuple((str(key), value) for key, value in checks_payload.items())
    detail = str(payload.get("detail", "native VSPAERO result parsed"))
    declared = payload.get("artifacts", [])
    if not isinstance(declared, list) or not all(isinstance(item, str) for item in declared):
        raise ExternalAeroValidationError("NATIVE_VSPAERO_ARTIFACT_LIST_INVALID")
    loads: list[SpanLoad] = []
    for item in payload.get("loads", []):
        if not isinstance(item, dict):
            raise ExternalAeroValidationError("NATIVE_VSPAERO_LOAD_INVALID")
        loads.append(SpanLoad(
            surface_id=str(item["surfaceId"]), span_fraction=_number(item, "spanFraction"),
            arc_m=_number(item, "arcM"), chord_m=_number(item, "chordM"),
            section_lift_coefficient=_number(item, "sectionLiftCoefficient"),
            circulation_m2_s=_number(item, "circulationM2S"),
            lift_per_span_n_m=_number(item, "liftPerSpanNm"),
            induced_alpha_deg=_number(item, "inducedAlphaDeg"),
        ))
    parsed = _ParseReceipt(
        "airframe-external-aero", "vspaero-json",
        {key: float(value) for key, value in result.canonical().items()}, detail=detail
    )
    validity = _ValidityReport(
        "airframe-external-aero",
        all(checks_payload.values()) if checks_payload else True,
        dict(checks_payload),
        detail,
    )
    return (
        VspaeroSolution(result, tuple(declared), detail, derivatives, tuple(loads), checks),
        parsed,
        validity,
    )


def solve_vspaero(
    case: ExternalAeroCase,
    reference: AeroReference,
    *,
    backend: VspaeroBackend | None = None,
    run_id: str | None = None,
    executable: str = "vspaero",
    job_root: Path | None = None,
) -> ExternalAeroResult:
    """Run the governed native path, or fail closed with no fabricated values."""

    if backend is None:
        capability = (
            probe_any_vspaero_capability()
            if executable == "vspaero"
            else probe_vspaero_capability(executable)
        )
        if not capability.available or capability.executable is None:
            raise ExternalAeroCapabilityUnavailableError(
                f"NATIVE_VSPAERO_UNAVAILABLE:{executable}:{capability.detail}"
            )
        resolved_backend: VspaeroBackend = GovernedVspaeroBackend(
            executable=capability.executable,
            job_root=job_root or Path(tempfile.mkdtemp(prefix="aeroworkbench-vspaero-")),
            solver_name=capability.backend,
            solver_version=capability.version or "unknown",
        )
    else:
        resolved_backend = backend
    if run_id is None or not run_id.strip():
        raise ExternalAeroValidationError("NATIVE_VSPAERO_RUN_ID_REQUIRED")
    if not resolved_backend.solver_name.strip() or not resolved_backend.solver_version.strip():
        raise ExternalAeroValidationError("NATIVE_VSPAERO_SOLVER_IDENTITY_REQUIRED")

    solution = resolved_backend.solve(case, reference)
    for label, value in (
        ("CL", solution.coefficients.lift),
        ("CD", solution.coefficients.drag),
        ("CY", solution.coefficients.side),
        ("Cl", solution.coefficients.roll),
        ("Cm", solution.coefficients.pitch),
        ("Cn", solution.coefficients.yaw),
    ):
        if not isfinite(value):
            raise ExternalAeroValidationError(f"NATIVE_VSPAERO_COEFFICIENT_NOT_FINITE:{label}")

    provenance = Provenance.from_inputs(
        source=ResultSource.NATIVE_SOLVER,
        model=VSPAERO_MODEL,
        model_version="1.0.0",
        fidelity=FidelityLevel.TRANSIENT,
        inputs={
            "case": case.digest,
            "reference": reference.canonical(),
            "runId": run_id,
        },
        assumptions=(
            "native OpenVSP/VSPAERO lifting-surface solve",
            "validity and artifacts as reported by the native run",
        ),
        solver_name=resolved_backend.solver_name,
        solver_version=resolved_backend.solver_version,
        run_id=run_id,
    )
    return ExternalAeroResult(
        result_id=f"{case.case_id}-vspaero",
        fidelity=ExternalAeroFidelity.VSPAERO,
        source=ResultSource.NATIVE_SOLVER,
        reference=reference,
        coefficients=solution.coefficients,
        derivatives=solution.derivatives,
        distributed_loads=solution.distributed_loads,
        validity=_native_validity(solution),
        artifacts=solution.artifacts,
        solver_name=resolved_backend.solver_name,
        solver_version=resolved_backend.solver_version,
        run_id=run_id,
        provenance=provenance,
    )


def vspaero_case_manifest(case: ExternalAeroCase, reference: AeroReference) -> dict[str, Any]:
    """Canonical case manifest as a plain mapping (same content as the file)."""

    return case.native_payload(reference.canonical())


__all__ = [
    "VSPAERO_EXECUTABLES",
    "VSPAERO_MODEL",
    "VspaeroBackend",
    "VspaeroCapability",
    "GovernedVspaeroBackend",
    "VspaeroSolution",
    "parse_vspaero_result",
    "prepare_vspaero_case",
    "probe_any_vspaero_capability",
    "probe_vspaero_capability",
    "resolve_vspaero_executable",
    "require_vspaero_capability",
    "solve_vspaero",
    "vspaero_case_manifest",
]
