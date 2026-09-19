"""Real Code_Aster input generation, result parsing, and validation.

The writer has two explicitly separated paths:

- a *legacy* scalar path (kept byte-stable for manifest-declared cases) that
  emits the historic DEBUT..FIN static/modal deck, and
- a *governed* path that consumes a validated :class:`StructuralRequest`
  (generated mesh semantic groups, material bindings, orientation frames,
  constraints, and loads) and emits a native deck for static, modal,
  prestressed-modal, harmonic, and transient analyses.

The governed path never invents groups or materials: every reference is
resolved by :mod:`code_aster.structure` against the declared mesh, or the case
fails closed. The parser reads the TABLEAU result table plus the solver log and
optional result metadata; it never invents values.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from participants.errors import NativeErrorCode, ParticipantError
from participants.receipts import ParseReceipt, PrepareReceipt, ValidityReport

from .structure import (
    ConstraintIngestion,
    LoadIngestion,
    MaterialIngestion,
    StructuralRequest,
    ingest_structural_request,
)

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
    """Write case.comm plus the as_run export file from validated inputs.

    A governed request (one that carries a ``mesh`` mapping) is rendered through
    the structural ingestion path; the historic scalar inputs keep their stable
    deck so existing manifest ports remain valid.
    """

    data: Mapping[str, object] = dict(inputs)
    if "mesh" in data:
        return _prepare_governed(data, case_dir)
    return _prepare_legacy(data, case_dir)


# -- legacy scalar path ------------------------------------------------------


def _prepare_legacy(data: Mapping[str, object], case_dir: Path) -> PrepareReceipt:
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


# -- governed path -----------------------------------------------------------


def _prepare_governed(data: Mapping[str, object], case_dir: Path) -> PrepareReceipt:
    request = ingest_structural_request(data)
    digest = hashlib.sha256(
        json.dumps(
            _governed_canonical(request), sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()
    comm = _render_governed_comm(request)
    export = _render_export(request.mesh.file)
    case_dir.mkdir(parents=True, exist_ok=True)
    (case_dir / "case.comm").write_text(comm, encoding="utf-8")
    (case_dir / "case.export").write_text(export, encoding="utf-8")
    return PrepareReceipt(
        participant_id="code-aster",
        case_id=case_dir.name,
        input_hash=digest,
        files=("case.comm", "case.export"),
        geometry_hash=request.mesh.geometry_hash,
        mesh_hash=request.mesh.mesh_hash,
        detail=(
            f"analysis={request.analysis} governed "
            f"volumes={len(request.mesh.volumes)} "
            f"materials={len(request.materials)} "
            f"loads={len(request.loads)}"
        ),
    )


def _governed_canonical(request: StructuralRequest) -> dict[str, Any]:
    return {
        "analysis": request.analysis,
        "prestress": request.prestress,
        "contact": (
            None
            if request.contact is None
            else {
                "mode": request.contact.mode,
                "slave": request.contact.slave,
                "master": request.contact.master,
            }
        ),
        "mesh": {
            "file": request.mesh.file,
            "format": request.mesh.format,
            "volumes": list(request.mesh.volumes),
            "surfaces": list(request.mesh.surfaces),
            "nodes": list(request.mesh.nodes),
            "materialGroups": dict(request.mesh.material_groups),
            "geometryHash": request.mesh.geometry_hash,
            "meshHash": request.mesh.mesh_hash,
            "interfaces": [
                {
                    "name": item.name,
                    "kind": item.kind,
                    "zoneA": item.zone_a,
                    "zoneB": item.zone_b,
                    "surface": item.surface,
                }
                for item in request.mesh.interfaces
            ],
            "frames": {
                name: {
                    "origin": list(frame.origin),
                    "axis": list(frame.axis),
                    "anglesDeg": list(frame.angles_deg),
                }
                for name, frame in sorted(request.mesh.frames.items())
            },
        },
        "materials": [
            {
                "region": material.region,
                "identity": material.identity,
                "symmetry": material.symmetry,
                "properties": {k: material.properties[k] for k in sorted(material.properties)},
                "frame": material.frame,
            }
            for material in request.materials
        ],
        "constraints": [
            {
                "name": constraint.name,
                "mode": constraint.mode,
                "group": constraint.group,
                "groupKind": constraint.group_kind,
                "dofs": {k: constraint.dofs[k] for k in sorted(constraint.dofs)},
            }
            for constraint in request.constraints
        ],
        "loads": [
            {
                "name": load.name,
                "kind": load.kind,
                "target": load.target,
                "groupKind": load.group_kind,
                "parameters": _canonical(load.parameters),
            }
            for load in request.loads
        ],
        "n_modes": request.n_modes,
        "time_end_s": request.time_end_s,
        "n_steps": request.n_steps,
    }


def _canonical(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _canonical(value[key]) for key in sorted(value)}
    if isinstance(value, tuple):
        return [_canonical(item) for item in value]
    return value


def _identifier(text: str) -> str:
    cleaned = "".join(character if character.isalnum() else "_" for character in text)
    if not cleaned or not cleaned[0].isalpha():
        cleaned = f"x_{cleaned}"
    return cleaned


def _tuple_literal(values: Sequence[str]) -> str:
    inner = ", ".join(f"'{value}'" for value in values)
    return f"({inner},)" if len(values) == 1 else f"({inner})"


def _vec_literal(values: Sequence[float]) -> str:
    return "(" + ", ".join(f"{value:.6f}" for value in values) + ")"


def _material_var(region: str) -> str:
    return f"mat_{_identifier(region)}"


def _render_governed_comm(request: StructuralRequest) -> str:
    lines: list[str] = ["DEBUT();", ""]
    lines += [
        f"mesh = LIRE_MAILLAGE(FORMAT='{request.mesh.format}', UNITE=20);",
        "",
        f"solid_groups = {_tuple_literal(request.mesh.volumes)};",
        "",
        "model = AFFE_MODELE(",
        "    MAILLAGE=mesh,",
        "    AFFE=_F(",
        "        GROUP_MA=solid_groups,",
        "        PHENOMENE='MECANIQUE',",
        "        MODELISATION='3D',",
        "    ),",
        ");",
        "",
    ]

    material_vars: dict[str, str] = {}
    for material in request.materials:
        variable = _material_var(material.region)
        material_vars[material.region] = variable
        lines += _render_material(variable, material)

    lines += ["fieldmat = AFFE_MATERIAU(", "    MAILLAGE=mesh,", "    AFFE=("]
    for material in request.materials:
        group = request.mesh.material_groups[material.region]
        lines.append(
            f"        _F(GROUP_MA='{group}', MATER=({material_vars[material.region]},)),"
        )
    lines += ["    ),", ");", ""]

    oriented = [material for material in request.materials if material.frame is not None]
    if oriented:
        lines += ["orientation = AFFE_CARA_ELEM(", "    MODELE=model,", "    ORIENTATION=("]
        for material in oriented:
            frame = request.mesh.frames[material.frame or ""]
            group = request.mesh.material_groups[material.region]
            lines.append(
                f"        _F(GROUP_MA='{group}', ANGL_NAUT={_vec_literal(frame.angles_deg)}),"
            )
        lines += ["    ),", ");", ""]

    nodal_surfaces = sorted(
        {
            str(load.parameters["group"])
            for load in request.loads
            if load.kind == "nodal_force" and load.group_kind == "surface"
        }
    )
    if nodal_surfaces:
        lines += [
            "mesh = DEFI_GROUP(",
            "    reuse=mesh,",
            "    MAILLAGE=mesh,",
            "    CREA_GROUP_NO=(",
        ]
        for group in nodal_surfaces:
            # A node group created from an element group keeps the element
            # group's name (Code_Aster forbids naming it here).
            lines.append(f"        _F(GROUP_MA=('{group}',)),")
        lines += ["    ),", ");", ""]

    if request.contact is not None:
        lines += [
            "contact = DEFI_CONTACT(",
            "    MODELE=model,",
            f"    FORMULATION='{request.contact.mode.upper()}',",
            "    ZONE=_F(",
            f"        GROUP_MA_ESCL='{request.contact.slave}',",
            f"        GROUP_MA_MAIT='{request.contact.master}',",
            "    ),",
            ");",
            "",
        ]

    excitation: list[str] = []
    for constraint in request.constraints:
        variable = f"char_{_identifier(constraint.name)}"
        lines += _render_constraint(variable, constraint)
        excitation.append(variable)

    harmonic_frequencies: list[float] = []
    for load in request.loads:
        if load.kind == "harmonic_spectrum":
            harmonic_frequencies.extend(load.parameters["frequencies_hz"])
            continue
        variable = f"load_{_identifier(load.name)}"
        lines += _render_load(variable, load, request)
        excitation.append(variable)

    if request.prestress:
        lines += [
            "prestressed = MECA_STATIQUE(",
            "    MODELE=model,",
            "    CHAM_MATER=fieldmat,",
            "    EXCIT=(",
            *[f"        _F(CHARGE={variable})," for variable in excitation],
            "    ),",
            ");",
            "",
            "prestress_field = CREA_CHAMP(",
            "    TYPE_CHAM='NOEU_DEPL_R',",
            "    OPERATION='EXTR',",
            "    RESULTAT=prestressed,",
            "    NOM_CHAM='DEPL',",
            ");",
            "",
        ]

    analysis = request.analysis
    if analysis == "static":
        lines += [
            "result = MECA_STATIQUE(",
            "    MODELE=model,",
            "    CHAM_MATER=fieldmat,",
            "    EXCIT=(",
            *[f"        _F(CHARGE={variable})," for variable in excitation],
            "    ),",
            ");",
            "",
        ]
        result_name = "result"
    elif analysis == "modal":
        block = [
            "rigi = ASSEMBLAGE(",
            "    MODELE=model,",
            "    CHAM_MATER=fieldmat,",
            "    NUME_DDL=CO('nume'),",
            "    MATR_ASSE=(_F(MATRICE=CO('RIGI'), OPTION='RIGI_MECA'),),",
            ");",
            "",
            "mass = ASSEMBLAGE(",
            "    MODELE=model,",
            "    CHAM_MATER=fieldmat,",
            "    NUME_DDL=nume,",
            "    MATR_ASSE=(_F(MATRICE=CO('MASS'), OPTION='MASS_MECA'),),",
            ");",
            "",
            "modes = CALC_MODES(",
            "    MATR_RIGI=rigi,",
            "    MATR_MASS=mass,",
        ]
        if request.prestress:
            block.append("    PREC_CONTRAINTE=prestress_field,")
        block += [
            "    CALC_FREQ=_F(",
            "        OPTION='PLUS_PETITE',",
            f"        NMAX_FREQ={request.n_modes},",
            "    ),",
            ");",
            "",
        ]
        lines += block
        result_name = "modes"
    elif analysis == "harmonic":
        freq_literal = "(" + ", ".join(f"{value:.6f}" for value in harmonic_frequencies) + ",)"
        block = [
            "harm = DYNA_LINE_HARM(",
            "    MODELE=model,",
            "    CHAM_MATER=fieldmat,",
        ]
        if request.prestress:
            block.append("    PREC_CONTRAINTE=prestress_field,")
        block += [
            "    EXCIT=(",
            *[f"        _F(CHARGE={variable})," for variable in excitation],
            "    ),",
            f"    FREQ=_F(LIST_FREQ={freq_literal}),",
            ");",
            "",
        ]
        lines += block
        result_name = "harm"
    else:
        block = [
            "time = DEFI_LIST_REEL(",
            "    DEBUT=0.0,",
            f"    INTERVALLE=_F(JUSQU_A={request.time_end_s:.6e}, NOMBRE={request.n_steps}),",
            ");",
            "",
            "tran = DYNA_LINE_TRAN(",
            "    MODELE=model,",
            "    CHAM_MATER=fieldmat,",
        ]
        if request.prestress:
            block.append("    PREC_CONTRAINTE=prestress_field,")
        block += [
            "    EXCIT=(",
            *[f"        _F(CHARGE={variable})," for variable in excitation],
            "    ),",
            "    INCREMENT=_F(LIST_INST=time),",
            "    SCHEMA_TEMPS=_F(SCHEMA='NEWMARK'),",
            ");",
            "",
        ]
        lines += block
        result_name = "tran"

    lines += [
        "IMPR_RESU(",
        "    FORMAT='RESULTAT',",
        "    UNITE=80,",
        "    RESU=_F(",
        f"        RESULTAT={result_name},",
        "        NOM_CHAM='DEPL',",
        "        FORM_TABL='OUI',",
        "    ),",
        ");",
        "",
        "FIN();",
        "",
    ]
    return "\n".join(lines)


def _render_material(variable: str, material: MaterialIngestion) -> list[str]:
    props = material.properties
    if material.symmetry == "isotropic":
        body = [
            "    ELAS=_F(",
            f"        E={props['youngs_modulus_pa']:.6e},",
            f"        NU={props['poisson_ratio']:.6f},",
            f"        RHO={props['density_kg_m3']:.6e},",
            "    ),",
        ]
    elif material.symmetry == "orthotropic":
        body = [
            "    ELAS_ORTH=_F(",
            f"        E_L={props['e_l_pa']:.6e},",
            f"        E_T={props['e_t_pa']:.6e},",
            f"        E_N={props['e_n_pa']:.6e},",
            f"        NU_LT={props['nu_lt']:.6f},",
            f"        NU_LN={props['nu_ln']:.6f},",
            f"        NU_TN={props['nu_tn']:.6f},",
            f"        G_LT={props['g_lt_pa']:.6e},",
            f"        G_LN={props['g_ln_pa']:.6e},",
            f"        G_TN={props['g_tn_pa']:.6e},",
            f"        RHO={props['density_kg_m3']:.6e},",
            "    ),",
        ]
    else:
        body = [
            "    ELAS_ORTH=_F(",
            f"        E_L={props['e_l_pa']:.6e},",
            f"        E_T={props['e_t_pa']:.6e},",
            f"        E_N={props['e_t_pa']:.6e},",
            f"        NU_LT={props['nu_lt']:.6f},",
            f"        NU_LN={props['nu_lt']:.6f},",
            f"        NU_TN={props['nu_tn']:.6f},",
            f"        G_LT={props['g_lt_pa']:.6e},",
            f"        G_LN={props['g_lt_pa']:.6e},",
            f"        G_TN={props['g_tn_pa']:.6e},",
            f"        RHO={props['density_kg_m3']:.6e},",
            "    ),",
        ]
    return [f"{variable} = DEFI_MATERIAU(", *body, ");", ""]


def _render_constraint(variable: str, constraint: ConstraintIngestion) -> list[str]:
    group_kw = "GROUP_NO" if constraint.group_kind == "node" else "GROUP_MA"
    dofs = ", ".join(
        f"{dof}={value:.6e}" for dof, value in sorted(constraint.dofs.items())
    )
    return [
        f"{variable} = AFFE_CHAR_MECA(",
        "    MODELE=model,",
        f"    DDL_IMPO=_F({group_kw}='{constraint.group}', {dofs}),",
        ");",
        "",
    ]


def _render_load(variable: str, load: LoadIngestion, request: StructuralRequest) -> list[str]:
    params = load.parameters
    if load.kind == "nodal_force":
        group = str(params["group"])
        components = ", ".join(
            f"{component}={value:.6e}" for component, value in sorted(params["components"].items())
        )
        return [
            f"{variable} = AFFE_CHAR_MECA(",
            "    MODELE=model,",
            f"    FORCE_NODALE=_F(GROUP_NO='{group}', {components}),",
            ");",
            "",
        ]
    if load.kind in {"distributed_force", "traction"}:
        components = ", ".join(
            f"{component}={value:.6e}" for component, value in sorted(params["components"].items())
        )
        return [
            f"{variable} = AFFE_CHAR_MECA(",
            "    MODELE=model,",
            f"    FORCE_FACE=_F(GROUP_MA='{params['group']}', {components}),",
            ");",
            "",
        ]
    if load.kind == "pressure":
        return [
            f"{variable} = AFFE_CHAR_MECA(",
            "    MODELE=model,",
            f"    PRES=_F(GROUP_MA='{params['group']}', PRES={params['pressure_pa']:.6e}),",
            ");",
            "",
        ]
    if load.kind == "centrifugal":
        frame = request.mesh.frames[str(params["frame"])]
        return [
            f"{variable} = AFFE_CHAR_MECA(",
            "    MODELE=model,",
            "    ROTATION=_F(",
            f"        GROUP_MA='{params['group']}',",
            f"        VITESSE={params['omega_rad_s']:.6e},",
            f"        AXE={_vec_literal(frame.axis)},",
            f"        CENTRE={_vec_literal(frame.origin)},",
            "    ),",
            ");",
            "",
        ]
    if load.kind == "thermal":
        return [
            f"{variable} = AFFE_CHAR_MECA(",
            "    MODELE=model,",
            f"    TEMP_CALCULEE=_F(GROUP_MA='{params['group']}', "
            f"TEMP={params['temperature_k']:.6e}),",
            ");",
            "",
        ]
    # harmonic_spectrum is folded into the analysis FREQ list, never a CHARGE.
    raise _fail(f"UNRENDERABLE_LOAD_KIND:{load.name}:{load.kind}")


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
        "R repe result_table.txt R 80\n"
    )


# -- parsing -----------------------------------------------------------------

_REQUESTED_RESULT_KEYS: dict[str, str] = {
    "displacement": "max_displacement_m",
    "stress": "max_von_mises_pa",
    "strain": "max_strain",
    "reaction": "max_reaction_n",
    "frequency": "first_frequency_hz",
    "mode": "mode_count",
    "harmonic": "peak_harmonic_displacement_m",
    "resonance": "resonance_frequency_hz",
    "transient": "transient_final_time_s",
    "residual": "residual_norm",
}


def parse_comm_result(case_dir: Path) -> ParseReceipt:
    """Parse the TABLEAU result table plus the solver log and metadata."""

    log_path = case_dir / "solver.log"
    if not log_path.is_file():
        raise ParticipantError(NativeErrorCode.PARSER_FAILED, "solver.log is missing")
    try:
        log_text = log_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ParticipantError(
            NativeErrorCode.PARSER_FAILED, f"solver.log unreadable:{exc}"
        ) from exc
    if not _clean_finish(log_text):
        raise ParticipantError(NativeErrorCode.PARSER_FAILED, "solver log shows no clean FIN")
    table_path = _result_table_path(case_dir)
    if table_path is None:
        raise ParticipantError(
            NativeErrorCode.PARSER_FAILED,
            "result table is missing (expected result_table.txt or result.rmed)",
        )
    try:
        table_text = table_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise ParticipantError(
            NativeErrorCode.PARSER_FAILED, f"result table unreadable:{exc}"
        ) from exc
    try:
        values = _parse_tableau(table_text)
    except ParticipantError:
        try:
            values = _parse_resultat_listing(table_text)
        except ParticipantError:
            values = _parse_generic_tableau(table_text)
    if "FREQUENCY_HZ" not in values:
        modal_frequencies = _parse_modal_log_frequencies(log_text)
        if modal_frequencies:
            values["FREQUENCY_HZ"] = modal_frequencies
    scalars, units, detail = _compose_scalars(values)
    scalars.update(_solver_state_scalars(case_dir, scalars))
    (case_dir / "result.json").write_text(
        json.dumps(
            {
                "participant_id": "code-aster",
                "parser": "code_aster.comm:parse_comm_result",
                "detail": detail,
                "scalars": dict(sorted(scalars.items())),
                "units": dict(sorted(units.items())),
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return ParseReceipt(
        participant_id="code-aster",
        parser="code_aster.comm:parse_comm_result",
        scalars=scalars,
        units=units,
        detail=detail,
    )


def _compose_scalars(
    values: Mapping[str, list[float]],
) -> tuple[dict[str, float], dict[str, str], str]:
    scalars: dict[str, float] = {}
    units: dict[str, str] = {}
    detail: list[str] = []

    def take(column: str, key: str, unit: str) -> None:
        column_values = values.get(column)
        if not column_values:
            return
        scalars[key] = float(max(column_values))
        units[key] = unit

    if "FREQUENCY_HZ" in values:
        frequencies = values["FREQUENCY_HZ"]
        if not frequencies:
            raise ParticipantError(NativeErrorCode.PARSER_FAILED, "frequency table is empty")
        scalars["first_frequency_hz"] = float(frequencies[0])
        scalars["mode_count"] = float(len(frequencies))
        units["first_frequency_hz"] = "Hz"
        units["mode_count"] = "dimensionless"
        detail.append(f"{len(frequencies)} modal frequencies")

    take("DISPLACEMENT_M", "max_displacement_m", "m")
    take("VON_MISES_PA", "max_von_mises_pa", "Pa")
    take("STRAIN", "max_strain", "dimensionless")
    take("REACTION_N", "max_reaction_n", "N")
    take("RESIDUAL", "residual_norm", "dimensionless")
    take("TIME_S", "transient_final_time_s", "s")
    take("HARMONIC_DISPLACEMENT_M", "peak_harmonic_displacement_m", "m")
    take("HARMONIC_FREQUENCY_HZ", "resonance_frequency_hz", "Hz")

    if not scalars:
        raise ParticipantError(
            NativeErrorCode.PARSER_FAILED, "result table has no known columns"
        )
    return scalars, units, "; ".join(detail) or "parsed result table"


def _solver_state_scalars(case_dir: Path, scalars: Mapping[str, float]) -> dict[str, float]:
    """Merge optional solver metadata: convergence, residual, load/reaction."""

    meta_path = case_dir / "result.json"
    if not meta_path.is_file():
        return {}
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ParticipantError(
            NativeErrorCode.PARSER_FAILED, f"result.json unreadable:{exc}"
        ) from exc
    if not isinstance(meta, Mapping):
        raise ParticipantError(NativeErrorCode.PARSER_FAILED, "result.json is not an object")

    merged: dict[str, float] = {}
    converged = meta.get("converged")
    if isinstance(converged, bool):
        merged["solver_converged"] = 1.0 if converged else 0.0
    residual = meta.get("residual_norm")
    if isinstance(residual, (int, float)) and not isinstance(residual, bool):
        merged["residual_norm"] = float(residual)
    for label, key in (("loads", "load_total_n"), ("reactions", "reaction_total_n")):
        block = meta.get(label)
        if isinstance(block, Mapping):
            total = block.get("total_force_n")
            if isinstance(total, (int, float)) and not isinstance(total, bool):
                merged[key] = float(total)
    requested = meta.get("requested_results")
    if (
        isinstance(requested, Sequence)
        and not isinstance(requested, (str, bytes))
        and requested
    ):
        known = {*scalars, *merged}
        available = all(
            _REQUESTED_RESULT_KEYS.get(str(item)) in known for item in requested
        )
        merged["requested_results_available"] = 1.0 if available else 0.0
    return merged


def _clean_finish(log_text: str) -> bool:
    if "EXIT_CODE=0" in log_text:
        return True
    return re.search(r"\bFIN\b", log_text) is not None


def _result_table_path(case_dir: Path) -> Path | None:
    for name in ("result_table.txt", "result.rmed"):
        candidate = case_dir / name
        if candidate.is_file():
            return candidate
    return None


_KNOWN_COLUMN_TOKENS = frozenset(
    {
        "DX",
        "DY",
        "DZ",
        "DRX",
        "DRY",
        "DRZ",
        "VMIS",
        "SIXX",
        "SIYY",
        "SIZZ",
        "SIXY",
        "SIXZ",
        "SIYZ",
        "FREQ",
        "FREQUENCE",
        "FREQUENCY_HZ",
        "NUME_ORDRE",
        "NUME_MODE",
        "INST",
        "TEMPS",
        "TIME",
    }
)


def _split_table_row(line: str) -> list[str]:
    return [token for token in re.split(r"[|\s]+", line.strip()) if token]


def _parse_number(token: str) -> float | None:
    try:
        return float(token.replace("D", "E").replace("d", "e"))
    except ValueError:
        return None


def _parse_generic_tableau(text: str) -> dict[str, list[float]]:
    """Tolerant parser for a native Code_Aster TABLEAU/excel-style table.

    Native output labels columns (DX/DY/DZ, VMIS, FREQ, ...) and may include a
    non-numeric identifier column. Only rows whose labelled numeric columns
    parse are used; a table with no recognisable columns/rows fails closed.
    """

    lines = text.splitlines()
    header: list[str] | None = None
    start = 0
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        tokens = _split_table_row(stripped.lstrip("#"))
        upper = [token.upper() for token in tokens]
        if len(tokens) >= 2 and any(token in _KNOWN_COLUMN_TOKENS for token in upper):
            header = upper
            start = index + 1
            break
    if header is None:
        raise ParticipantError(
            NativeErrorCode.PARSER_FAILED, "result table has no recognisable columns"
        )
    rows: list[dict[str, float]] = []
    for line in lines[start:]:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        tokens = _split_table_row(stripped)
        if len(tokens) != len(header):
            continue
        numbers: dict[str, float] = {}
        for token, name in zip(tokens, header, strict=True):
            value = _parse_number(token)
            if value is not None:
                numbers[name] = value
        if numbers:
            rows.append(numbers)
    if not rows:
        raise ParticipantError(NativeErrorCode.PARSER_FAILED, "result table has no numeric rows")

    values: dict[str, list[float]] = {}
    components = ("DX", "DY", "DZ")
    if all(name in header for name in components):
        magnitudes = [
            (
                row.get("DX", 0.0) ** 2
                + row.get("DY", 0.0) ** 2
                + row.get("DZ", 0.0) ** 2
            )
            ** 0.5
            for row in rows
            if any(name in row for name in components)
        ]
        if magnitudes:
            values["DISPLACEMENT_M"] = [max(magnitudes)]
    if "VMIS" in header:
        stresses = [row["VMIS"] for row in rows if "VMIS" in row]
        if stresses:
            values["VON_MISES_PA"] = [max(stresses)]
    elif all(name in header for name in ("SIXX", "SIYY", "SIZZ", "SIXY", "SIXZ", "SIYZ")):
        von_mises = []
        for row in rows:
            if not all(name in row for name in ("SIXX", "SIYY", "SIZZ", "SIXY", "SIXZ", "SIYZ")):
                continue
            sxx, syy, szz = row["SIXX"], row["SIYY"], row["SIZZ"]
            sxy, sxz, syz = row["SIXY"], row["SIXZ"], row["SIYZ"]
            von_mises.append(
                (
                    0.5 * ((sxx - syy) ** 2 + (syy - szz) ** 2 + (szz - sxx) ** 2)
                    + 3.0 * (sxy**2 + sxz**2 + syz**2)
                )
                ** 0.5
            )
        if von_mises:
            values["VON_MISES_PA"] = [max(von_mises)]
    for name in ("FREQ", "FREQUENCE", "FREQUENCY_HZ"):
        if name in header:
            frequencies = [row[name] for row in rows if name in row]
            if frequencies:
                values["FREQUENCY_HZ"] = frequencies
            break
    if not values:
        raise ParticipantError(
            NativeErrorCode.PARSER_FAILED, "result table has no recognised quantity"
        )
    return values


def _parse_modal_log_frequencies(log_text: str) -> list[float]:
    """Native modal-solver frequency table from the message/log listing.

    ``CALC_MODES`` prints a table ``numéro fréquence (HZ) norme d'erreur``.
    Only rows inside that table are read; no value is invented.
    """

    frequencies: list[float] = []
    in_table = False
    for line in log_text.splitlines():
        lowered = line.lower()
        if ("fréquence" in lowered or "frequence" in lowered) and (
            "norme" in lowered or "error" in lowered
        ):
            in_table = True
            continue
        if not in_table:
            continue
        stripped = line.strip()
        if not stripped:
            if frequencies:
                break
            continue
        tokens = stripped.split()
        if len(tokens) < 2:
            continue
        if not tokens[0].isdigit():
            if frequencies:
                break
            in_table = False
            continue
        value = _parse_number(tokens[1])
        if value is None:
            break
        frequencies.append(value)
    return frequencies


def _merge_sign_tokens(tokens: list[str]) -> list[str]:
    """Join a separated sign (``- 2.63E-06``) with the following number."""

    merged: list[str] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token in {"-", "+"} and index + 1 < len(tokens):
            merged.append(token + tokens[index + 1])
            index += 2
            continue
        merged.append(token)
        index += 1
    return merged


def _parse_resultat_listing(text: str) -> dict[str, list[float]]:
    """Parse the native ``IMPR_RESU(FORMAT='RESULTAT')`` listing.

    The listing prints one block per field/order with a ``NODE DX DY DZ``
    header followed by numeric rows (blank lines and separated negative signs
    are tolerated); modal results print a ``FREQUENCY ... NORM`` table. Only
    recognised quantities are returned; an unparseable listing raises.
    """

    displacements: list[float] = []
    frequencies: list[float] = []
    lines = text.splitlines()
    index = 0
    while index < len(lines):
        tokens = _merge_sign_tokens(_split_table_row(lines[index].lstrip("#")))
        upper = [token.upper() for token in tokens]
        if "NODE" in upper and any(name in upper for name in ("DX", "DY", "DZ")):
            components = {name: position for position, name in enumerate(upper)}
            index += 1
            while index < len(lines):
                stripped = lines[index].strip()
                if not stripped:
                    index += 1
                    continue
                row = _merge_sign_tokens(_split_table_row(stripped))
                if not row or row[0].upper() in {"NODE", "FIELD", "GROUP_MA", "SEQUENCE"}:
                    break
                values: dict[str, float] = {}
                for name in ("DX", "DY", "DZ"):
                    position = components.get(name)
                    if position is not None and position < len(row):
                        value = _parse_number(row[position])
                        if value is not None:
                            values[name] = value
                if any(name in values for name in ("DX", "DY", "DZ")):
                    magnitude = (
                        values.get("DX", 0.0) ** 2
                        + values.get("DY", 0.0) ** 2
                        + values.get("DZ", 0.0) ** 2
                    ) ** 0.5
                    displacements.append(magnitude)
                index += 1
            continue
        if "FREQ" in upper and any("NORM" in token or "ERROR" in token for token in upper):
            freq_position = next(
                position
                for position, token in enumerate(upper)
                if token.startswith("FREQ") or token.startswith("FREQUENCE")
            )
            index += 1
            while index < len(lines):
                stripped = lines[index].strip()
                if not stripped:
                    index += 1
                    continue
                row = _merge_sign_tokens(_split_table_row(stripped))
                if not row or row[0].upper() in {"NODE", "FREQ"}:
                    break
                numbers = [
                    number for number in (_parse_number(t) for t in row) if number is not None
                ]
                if len(numbers) > freq_position:
                    frequencies.append(numbers[freq_position])
                elif len(numbers) >= 2:
                    frequencies.append(numbers[1])
                index += 1
            continue
        index += 1

    parsed: dict[str, list[float]] = {}
    if displacements:
        parsed["DISPLACEMENT_M"] = displacements
    if frequencies:
        parsed["FREQUENCY_HZ"] = frequencies
    if not parsed:
        raise ParticipantError(
            NativeErrorCode.PARSER_FAILED, "result listing has no recognised quantity"
        )
    return parsed


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


# -- validity ----------------------------------------------------------------


def validate_comm_result(
    scalars: Mapping[str, float], inputs: Mapping[str, object]
) -> ValidityReport:
    governed = "mesh" in inputs
    checks: dict[str, bool] = {}

    if "first_frequency_hz" in scalars:
        first = float(scalars["first_frequency_hz"])
        checks["frequency_positive"] = first == first and first > 0
        checks["frequency_bounded"] = first == first and first < 1e6
    if "max_displacement_m" in scalars:
        displacement = float(scalars["max_displacement_m"])
        checks["displacement_finite"] = displacement == displacement and displacement >= 0
    if "max_von_mises_pa" in scalars:
        stress = float(scalars["max_von_mises_pa"])
        checks["stress_finite"] = stress == stress and stress >= 0
    if "max_strain" in scalars:
        strain = float(scalars["max_strain"])
        checks["strain_finite"] = strain == strain and strain >= 0
    if "peak_harmonic_displacement_m" in scalars:
        peak = float(scalars["peak_harmonic_displacement_m"])
        checks["harmonic_response_finite"] = peak == peak and peak >= 0

    if governed:
        present = any(
            key in scalars
            for key in (
                "first_frequency_hz",
                "max_displacement_m",
                "max_von_mises_pa",
                "peak_harmonic_displacement_m",
                "transient_final_time_s",
            )
        )
        checks["result_fields_present"] = present
        if "solver_converged" in scalars:
            checks["solver_converged"] = float(scalars["solver_converged"]) == 1.0
        if "requested_results_available" in scalars:
            checks["requested_results_available"] = (
                float(scalars["requested_results_available"]) == 1.0
            )
        if "load_total_n" in scalars and "reaction_total_n" in scalars:
            load = float(scalars["load_total_n"])
            reaction = float(scalars["reaction_total_n"])
            denominator = max(abs(load), abs(reaction), 1e-12)
            checks["load_reaction_consistent"] = (
                abs(load - reaction) / denominator <= 1e-3
            )
    else:
        force = inputs.get("applied_force_n", 0.0)
        loaded = (
            isinstance(force, (int, float))
            and not isinstance(force, bool)
            and float(force) > 0
        )
        if "max_displacement_m" in scalars:
            displacement = float(scalars["max_displacement_m"])
            checks["loaded_means_moved"] = (not loaded) or displacement > 0

    if checks and "frequency_positive" in checks:
        detail = "eigenfrequency positive and below 1 MHz"
    elif checks.get("result_fields_present"):
        detail = "governed result fields finite, converged, and consistency-checked"
    else:
        detail = "displacement/stress finite; loaded cases must move"
    return ValidityReport(
        participant_id="code-aster",
        passed=bool(checks) and all(checks.values()),
        checks=checks,
        detail=detail,
    )
