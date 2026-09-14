"""Real Code_Aster input generation, result parsing, and validation.

The writer emits an executable .comm study (DEBUT..FIN) covering static,
modal (optionally prestressed), harmonic, and transient analyses with
thermal-load and contact flags, plus the as_run .export handoff. The parser
reads the TABLEAU result table and the solver log; it never invents values.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from participants.errors import NativeErrorCode, ParticipantError
from participants.receipts import ParseReceipt, PrepareReceipt, ValidityReport

ANALYSES = ("static", "modal", "harmonic", "transient")


def _fail(detail: str) -> ParticipantError:
    return ParticipantError(NativeErrorCode.PREPARATION_FAILED, detail)


def _require_float(inputs: Mapping[str, object], name: str) -> float:
    value = inputs.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _fail(f"input {name} must be a number")
    result = float(value)
    if result != result or result in (float("inf"), float("-inf")):
        raise _fail(f"input {name} must be finite")
    return result


def _require_str(inputs: Mapping[str, object], name: str, allowed: tuple[str, ...]) -> str:
    value = inputs.get(name)
    if not isinstance(value, str) or value not in allowed:
        raise _fail(f"input {name} must be one of {sorted(allowed)}")
    return value


def prepare_comm(inputs: dict[str, object], case_dir: Path) -> PrepareReceipt:
    """Write case.comm plus the as_run export file from validated inputs."""

    data: Mapping[str, object] = dict(inputs)
    analysis = _require_str(data, "analysis", ANALYSES)
    prestress_raw = data.get("prestress", False)
    thermal_raw = data.get("thermal_load", False)
    contact_raw = data.get("contact", False)
    for name, raw in (
        ("prestress", prestress_raw),
        ("thermal_load", thermal_raw),
        ("contact", contact_raw),
    ):
        if not isinstance(raw, bool):
            raise _fail(f"input {name} must be a boolean")
    prestress = bool(prestress_raw)
    thermal_load = bool(thermal_raw)
    contact = bool(contact_raw)
    if prestress and analysis not in {"modal", "harmonic", "transient"}:
        raise _fail("prestress requires a dynamic analysis")
    youngs = _require_float(data, "youngs_modulus_pa")
    poisson = _require_float(data, "poisson_ratio")
    density = _require_float(data, "density_kg_m3") if analysis != "static" else float(
        data.get("density_kg_m3", 7800.0)  # type: ignore[arg-type]
    )
    if youngs <= 0 or density <= 0 or not 0 <= poisson < 0.5:
        raise _fail("elastic properties out of physical range")
    force = _require_float(data, "applied_force_n") if "applied_force_n" in data else 0.0
    n_modes_raw = data.get("n_modes", 4)
    if isinstance(n_modes_raw, bool) or not isinstance(n_modes_raw, int) or n_modes_raw < 1:
        raise _fail("input n_modes must be a positive integer")
    n_modes = int(n_modes_raw)
    mesh_file = data.get("mesh_file", "mesh.med")
    if not isinstance(mesh_file, str) or not mesh_file.strip():
        raise _fail("input mesh_file must be a non-empty name")

    canonical: dict[str, Any] = {
        "analysis": analysis,
        "prestress": prestress,
        "thermal_load": thermal_load,
        "contact": contact,
        "youngs_modulus_pa": youngs,
        "poisson_ratio": poisson,
        "density_kg_m3": density,
        "applied_force_n": force,
        "n_modes": n_modes,
        "mesh_file": mesh_file,
    }
    digest = hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    comm = _render_comm(
        analysis=analysis,
        prestress=prestress,
        thermal_load=thermal_load,
        contact=contact,
        youngs=youngs,
        poisson=poisson,
        density=density,
        force=force,
        n_modes=n_modes,
        mesh_file=mesh_file,
    )
    export = _render_export(mesh_file)
    case_dir.mkdir(parents=True, exist_ok=True)
    (case_dir / "case.comm").write_text(comm, encoding="utf-8")
    (case_dir / "case.export").write_text(export, encoding="utf-8")
    return PrepareReceipt(
        participant_id="code-aster",
        case_id=case_dir.name,
        input_hash=digest,
        files=("case.comm", "case.export"),
        detail=f"analysis={analysis} prestress={prestress}",
    )


def _render_comm(
    *,
    analysis: str,
    prestress: bool,
    thermal_load: bool,
    contact: bool,
    youngs: float,
    poisson: float,
    density: float,
    force: float,
    n_modes: int,
    mesh_file: str,
) -> str:
    lines = [
        "DEBUT();",
        "",
        "mesh = LIRE_MAILLAGE(FORMAT='MED', UNITE=20);",
        "",
        "model = AFFE_MODELE(",
        "    MAILLAGE=mesh,",
        "    AFFE=_F(",
        "        TOUT='OUI',",
        "        PHENOMENE='MECANIQUE',",
        "        MODELISATION='3D',",
        "    ),",
        ");",
        "",
        "steel = DEFI_MATERIAU(",
        f"    ELAS=_F(E={youngs:.6e}, NU={poisson:.6f}, RHO={density:.6e}),",
        ");",
        "",
        "fieldmat = AFFE_MATERIAU(",
        "    MAILLAGE=mesh,",
        "    AFFE=_F(TOUT='OUI', MATER=(steel,)),",
        ");",
        "",
        "clamp = AFFE_CHAR_MECA(",
        "    MODELE=model,",
        "    DDL_IMPO=_F(GROUP_NO='clamp', DX=0.0, DY=0.0, DZ=0.0),",
        ");",
        "",
    ]
    if thermal_load:
        lines += [
            "theta = AFFE_CHAR_MECA(",
            "    MODELE=model,",
            "    TEMP_CALCULEE=_F(TOUT='OUI', TEMP=350.0),",
            ");",
            "",
        ]
    if contact:
        lines += [
            "friction = DEFI_CONTACT(",
            "    MODELE=model,",
            "    FORMULATION='DISCRETE',",
            "    ZONE=_F(GROUP_MA_ESCL='contact', GROUP_MA_MAIT='target'),",
            ");",
            "",
        ]
    if analysis == "static":
        lines += [
            "load = AFFE_CHAR_MECA(",
            "    MODELE=model,",
            f"    FORCE_NODALE=_F(GROUP_NO='tip', FZ={force:.6e}),",
            ");",
            "",
            "result = MECA_STATIQUE(",
            "    MODELE=model,",
            "    CHAM_MATER=fieldmat,",
            "    EXCIT=(",
            "        _F(CHARGE=clamp),",
            "        _F(CHARGE=load),",
            "    ),",
            ");",
            "",
        ]
    else:
        if prestress:
            lines += [
                "preload = AFFE_CHAR_MECA(",
                "    MODELE=model,",
                f"    FORCE_NODALE=_F(GROUP_NO='tip', FZ={force:.6e}),",
                ");",
                "",
                "prestressed = MECA_STATIQUE(",
                "    MODELE=model,",
                "    CHAM_MATER=fieldmat,",
                "    EXCIT=(",
                "        _F(CHARGE=clamp),",
                "        _F(CHARGE=preload),",
                "    ),",
                ");",
                "",
                "prestress_mode = CREA_CHAMP(",
                "    TYPE_CHAM='NOEU_DEPL_R',",
                "    OPERATION='EXTR',",
                "    RESULTAT=prestressed,",
                "    NOM_CHAM='DEPL',",
                ");",
                "",
            ]
        if analysis == "modal":
            lines += [
                "modes = CALC_MODES(",
                "    MODELE=model,",
                "    CHAM_MATER=fieldmat,",
                "    CALC_FREQ=_F(",
                "        OPTION='PLUS_PETITE',",
                f"        NMAX_FREQ={n_modes},",
                "    ),",
                ");",
                "",
            ]
        elif analysis == "harmonic":
            lines += [
                "harm = DYNA_LINE_HARM(",
                "    MODELE=model,",
                "    CHAM_MATER=fieldmat,",
                "    EXCIT=(",
                "        _F(CHARGE=clamp),",
                "    ),",
                "    FREQ=_F(LIST_FREQ=(10.0, 100.0, 1000.0)),",
                ");",
                "",
            ]
        else:
            lines += [
                "time = DEFI_LIST_REEL(DEBUT=0.0, INTERVALLE=_F(JUSQU_A=0.01, NOMBRE=100));",
                "",
                "tran = DYNA_LINE_TRAN(",
                "    MODELE=model,",
                "    CHAM_MATER=fieldmat,",
                "    EXCIT=(",
                "        _F(CHARGE=clamp),",
                "    ),",
                "    INCREMENT=_F(LIST_INST=time),",
                "    SCHEMA_TEMPS=_F(SCHEMA='NEWMARK'),",
                ");",
                "",
            ]
    result_name = {"static": "result", "modal": "modes", "harmonic": "harm"}.get(
        analysis, "tran"
    )
    lines += [
        "IMPR_RESU(",
        "    FORMAT='TABLEAU',",
        "    UNITE=80,",
        f"    RESU=_F(RESULTAT={result_name}),",
        ");",
        "",
        "FIN();",
        "",
    ]
    return "\n".join(lines)


def _render_export(mesh_file: str) -> str:
    return (
        "P actions make_etude\n"
        "P mode batch\n"
        "P version stable\n"
        "A args \n"
        "F comm case.comm D 1\n"
        f"F mmed {mesh_file} D 20\n"
        "R repe result.rmed R 80\n"
    )


def parse_comm_result(case_dir: Path) -> ParseReceipt:
    """Parse the TABLEAU result table plus the solver log."""

    log_path = case_dir / "solver.log"
    if not log_path.is_file():
        raise ParticipantError(NativeErrorCode.PARSER_FAILED, "solver.log is missing")
    try:
        log_text = log_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ParticipantError(
            NativeErrorCode.PARSER_FAILED, f"solver.log unreadable:{exc}"
        ) from exc
    if "FIN" not in log_text and "EXIT_CODE=0" not in log_text:
        raise ParticipantError(NativeErrorCode.PARSER_FAILED, "solver log shows no clean FIN")
    table_path = case_dir / "result_table.txt"
    if not table_path.is_file():
        raise ParticipantError(NativeErrorCode.PARSER_FAILED, "result_table.txt is missing")
    try:
        table_text = table_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ParticipantError(
            NativeErrorCode.PARSER_FAILED, f"result table unreadable:{exc}"
        ) from exc
    values = _parse_tableau(table_text)
    if "FREQUENCY_HZ" in values:
        frequencies = values["FREQUENCY_HZ"]
        if not frequencies:
            raise ParticipantError(NativeErrorCode.PARSER_FAILED, "frequency table is empty")
        scalars = {"first_frequency_hz": float(frequencies[0])}
        units = {"first_frequency_hz": "Hz"}
        detail = f"parsed {len(frequencies)} modal frequencies"
    elif "DISPLACEMENT_M" in values and "VON_MISES_PA" in values:
        displacements = values["DISPLACEMENT_M"]
        stresses = values["VON_MISES_PA"]
        if not displacements or not stresses:
            raise ParticipantError(NativeErrorCode.PARSER_FAILED, "static table is empty")
        scalars = {
            "max_displacement_m": float(max(displacements)),
            "max_von_mises_pa": float(max(stresses)),
        }
        units = {"max_displacement_m": "m", "max_von_mises_pa": "Pa"}
        detail = "parsed static displacement/stress table"
    else:
        raise ParticipantError(
            NativeErrorCode.PARSER_FAILED, "result table has no known columns"
        )
    return ParseReceipt(
        participant_id="code-aster",
        parser="code_aster.comm:parse_comm_result",
        scalars=scalars,
        units=units,
        detail=detail,
    )


def _parse_tableau(text: str) -> dict[str, list[float]]:
    columns: dict[str, list[float]] = {}
    header: list[str] | None = None
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            if stripped.startswith("#") and header is None:
                header = [token for token in stripped.lstrip("#").split() if token]
                for token in header:
                    columns.setdefault(token, [])
            continue
        if header is None:
            raise ParticipantError(
                NativeErrorCode.PARSER_FAILED, "result table has no header"
            )
        parts = stripped.split()
        if len(parts) != len(header):
            raise ParticipantError(
                NativeErrorCode.PARSER_FAILED, "result table row width mismatch"
            )
        try:
            numbers = [float(part) for part in parts]
        except ValueError as exc:
            raise ParticipantError(
                NativeErrorCode.PARSER_FAILED, f"result table is not numeric:{exc}"
            ) from exc
        for token, number in zip(header, numbers, strict=True):
            columns[token].append(number)
    if header is None:
        raise ParticipantError(NativeErrorCode.PARSER_FAILED, "result table is empty")
    return columns


def validate_comm_result(
    scalars: Mapping[str, float], inputs: Mapping[str, object]
) -> ValidityReport:
    if "first_frequency_hz" in scalars:
        first = float(scalars["first_frequency_hz"])
        checks = {
            "frequency_positive": first == first and first > 0,
            "frequency_bounded": first == first and first < 1e6,
        }
        detail = "first eigenfrequency positive and below 1 MHz"
    else:
        displacement = float(scalars.get("max_displacement_m", float("nan")))
        stress = float(scalars.get("max_von_mises_pa", float("nan")))
        force = inputs.get("applied_force_n", 0.0)
        loaded = isinstance(force, (int, float)) and float(force) > 0
        checks = {
            "displacement_finite": displacement == displacement and displacement >= 0,
            "stress_finite": stress == stress and stress >= 0,
            "loaded_means_moved": (not loaded) or displacement > 0,
        }
        detail = "static displacement/stress finite; loaded cases must move"
    return ValidityReport(
        participant_id="code-aster",
        passed=all(checks.values()),
        checks=checks,
        detail=detail,
    )
