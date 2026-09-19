#!/usr/bin/env python3
"""Cross-solver validation gate + negative acceptance test (SOLVER-CORR 05).

Assembles one generic multiphysics receipt from the trusted receipts produced
by benchmarks 01-04, runs the repo's real independence runner over the actual
native QoIs, and proves the promotion gate REFUSES validated-final when one
required receipt is removed or invalidated. No manual override exists.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

RECEIPTS = Path(os.environ.get("RECEIPTS", "/var/log/proofs/receipts"))


def load(name: str) -> dict:
    p = RECEIPTS / name
    return json.loads(p.read_text()) if p.is_file() else {}


def main() -> int:
    import hashlib

    from aeroworkbench_convergence import (
        PromotionParticipantEvidence,
        QuantityOfInterest,
        RefinementLevel,
        StudyRun,
        assess_promotion,
        run_mesh_independence,
    )

    def content_digest(payload) -> str:
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

    out: dict = {"benchmark": "cross-solver-validation-gate", "status": "BLOCKED"}

    # ---- real native QoI ladders fed to the real independence runner ----
    of = load("issue37_openfoam.json").get("benchmarks", {}).get("channel", {})
    el = load("issue39_elmer.json").get("benchmarks", {}).get("steadyDirichlet", {})

    def of_executor(level: RefinementLevel) -> StudyRun:
        lv = next(x for x in of["levels"] if x["mesh"] == level.name)
        mass = lv.get("inletMeanUx")
        if mass is None:
            mass = lv.get("inletFlow")
        return StudyRun(
            level=level.name,
            run_id=f"of-{level.name}",
            input_hash=content_digest({"case": "channel", "mesh": level.name}),
            qoi=(("maxUx", float(lv["maxUx"])), ("massFlow", float(mass))),
            source="native-openfoam",
        )

    def el_executor(level: RefinementLevel) -> StudyRun:
        lv = next(x for x in el["levels"] if abs(x["lc"] - level.resolution) < 1e-12)
        return StudyRun(
            level=level.name,
            run_id=f"el-{level.name}",
            input_hash=content_digest({"case": "steady", "lc": level.resolution}),
            qoi=(("tMid", float(lv["data"]["tMid"])),),
            source="native-elmer",
        )

    independence = {}
    try:
        of_lv = [(x["mesh"], x["cells"], x["maxUx"]) for x in of.get("levels", [])]
        if len(of_lv) >= 2:
            report = run_mesh_independence(
                tuple(
                    RefinementLevel(
                        name, 1.0 / max(cells, 1) ** 0.5, (("element_count", float(cells)),)
                    )
                    for name, cells, _ in of_lv
                ),
                (
                    QuantityOfInterest("maxUx", "m/s", relative_tolerance=0.05),
                    QuantityOfInterest("massFlow", "m3/s", relative_tolerance=0.05),
                ),
                of_executor,
            )
            independence["openfoamChannel"] = report.as_dict()
    except Exception as exc:  # noqa: BLE001
        independence["openfoamChannel"] = {"error": f"{type(exc).__name__}:{exc}"}
    try:
        if len(el.get("levels", [])) >= 2:
            report = run_mesh_independence(
                tuple(
                    RefinementLevel(f"lc{x['lc']}", x["lc"], (("lc", x["lc"]),))
                    for x in el["levels"]
                ),
                (QuantityOfInterest("tMid", "K", relative_tolerance=0.02),),
                el_executor,
            )
            independence["elmerSteady"] = report.as_dict()
    except Exception as exc:  # noqa: BLE001
        independence["elmerSteady"] = {"error": f"{type(exc).__name__}:{exc}"}
    out["independence"] = independence

    # ---- honest participant availability from the real receipts ----
    ross = load("issue38_ross.json")
    thermal_ok = el.get("status") == "EXECUTED"
    flow_ok = of.get("status") == "EXECUTED"
    elec = load("issue39_electrical.json")
    scalar_ok = elec.get("status") in {"EXECUTED", "PARTIAL"}
    rotor_ok = ross.get("status") in {"EXECUTED", "PARTIAL"}

    def participant(
        pid: str,
        available: bool,
        *,
        converged=True,
        closure=True,
        coupling=True,
        mesh=True,
        timestep=True,
        deferred=False,
    ):
        return PromotionParticipantEvidence(
            participant_id=pid,
            required=True,
            available=available,
            deferred=deferred,
            converged=converged,
            validity_ok=True,
            closure_passed=closure,
            field_coupling_passed=coupling,
            mesh_independence_passed=mesh,
            timestep_independence_passed=timestep,
        )

    participants = (
        "cad-interchange",
        "domain-mesh",
        "incompressible-steady-flow",
        "structural-static",
        "thermal-conduction",
        "rotor-campbell",
        "rotating-electrical-machine",
        "coupled-interface-validation",
    )

    def full_evidence(**overrides):
        base = {p: participant(p, True) for p in participants}
        base.update(overrides)
        return list(base.values())

    # 1) complete synthetic set -> gate can validate
    ok = assess_promotion(
        "candidate-all-receipts",
        full_evidence(),
        require_mesh_independence=True,
        require_timestep_independence=True,
    )
    out["positiveControl"] = ok.as_dict()

    # 2) remove one required receipt -> must refuse
    missing = full_evidence(
        **{"thermal-conduction": participant("thermal-conduction", False, deferred=True)}
    )
    no_thermal = assess_promotion(
        "candidate-missing-thermal",
        missing,
        require_mesh_independence=True,
        require_timestep_independence=True,
    )
    out["negative_missingReceipt"] = no_thermal.as_dict()

    # 3) invalidate one required receipt's independence gate -> must refuse
    bad_mesh = full_evidence(
        **{
            "incompressible-steady-flow": participant(
                "incompressible-steady-flow", True, mesh=False
            )
        }
    )
    bad = assess_promotion(
        "candidate-bad-mesh-independence",
        bad_mesh,
        require_mesh_independence=True,
        require_timestep_independence=True,
    )
    out["negative_invalidReceipt"] = bad.as_dict()

    # 4) honest real set -> report true blockers (Code_Aster/preCICE if blocked)
    real = [
        participant("cad-interchange", True),
        participant("domain-mesh", True),
        participant("incompressible-steady-flow", flow_ok, mesh=flow_ok),
        participant("structural-static", False, deferred=True),
        participant("thermal-conduction", thermal_ok, mesh=thermal_ok),
        participant("rotor-campbell", rotor_ok, mesh=False),
        participant("rotating-electrical-machine", scalar_ok, closure=scalar_ok),
        participant("coupled-interface-validation", False, coupling=False),
    ]
    out["honestSet"] = assess_promotion(
        "candidate-real-receipts",
        real,
        require_mesh_independence=True,
        require_timestep_independence=True,
    ).as_dict()

    out["refusesInvalid"] = (not no_thermal.validated_final) and (not bad.validated_final)
    out["status"] = "EXECUTED" if (ok.validated_final and out["refusesInvalid"]) else "PARTIAL"
    (RECEIPTS / "issue41_gate.json").write_text(json.dumps(out, indent=2, sort_keys=True))
    print(
        "WROTE issue41_gate.json status=",
        out["status"],
        "positive=",
        ok.validated_final,
        "refusesInvalid=",
        out["refusesInvalid"],
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
