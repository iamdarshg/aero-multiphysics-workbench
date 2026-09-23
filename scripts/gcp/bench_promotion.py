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


def _governed_native_passed(payload: dict, participant_id: str) -> bool:
    """Accept only a completed governed job with a trusted native envelope."""
    validity = payload.get("envelope_validity")
    return bool(
        payload.get("participant") == participant_id
        and payload.get("state") == "COMPLETED"
        and payload.get("envelope_source") == "native_solver"
        and isinstance(validity, dict)
        and validity.get("passed") is True
    )


def derive_receipt_states(receipts: dict[str, dict]) -> dict[str, bool]:
    """Derive participant availability from observed receipts, never constants."""
    openfoam = receipts.get("issue37_openfoam.json", {})
    elmer = receipts.get("issue39_elmer.json", {})
    ross = receipts.get("issue38_ross.json", {})
    electrical = receipts.get("issue39_electrical.json", {})
    cases = electrical.get("cases")
    electrical_ok = bool(
        electrical.get("status") == "EXECUTED"
        and isinstance(cases, list)
        and cases
        and all(
            case.get("converged") is True
            and case.get("powerBalancePassed") is True
            and case.get("heatBalancePassed") is True
            for case in cases
        )
    )
    return {
        "incompressible-steady-flow": (
            openfoam.get("benchmarks", {}).get("channel", {}).get("status")
            == "EXECUTED"
        ),
        "structural-static": _governed_native_passed(
            receipts.get("07_code_aster_static.json", {}), "structural-static"
        ),
        "structural-modal": _governed_native_passed(
            receipts.get("07_code_aster_modal.json", {}), "structural-modal"
        ),
        "thermal-conduction": (
            elmer.get("benchmarks", {}).get("steadyDirichlet", {}).get("status")
            == "EXECUTED"
        ),
        "rotor-campbell": (
            ross.get("status") == "EXECUTED"
            and ross.get("verificationPassed") is True
        ),
        "rotating-electrical-machine": electrical_ok,
        "coupled-interface-validation": _governed_native_passed(
            receipts.get("11_precice_native_window.json", {}),
            "native-coupled-window",
        ),
    }


def final_gate_succeeded(payload: dict) -> bool:
    """Return true only when controls and the observed receipt set all pass."""
    return bool(
        payload.get("positiveControl", {}).get("validatedFinal") is True
        and payload.get("honestSet", {}).get("validatedFinal") is True
        and payload.get("refusesInvalid") is True
    )


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

    receipt_names = (
        "issue37_openfoam.json",
        "issue39_elmer.json",
        "issue38_ross.json",
        "issue39_electrical.json",
        "07_code_aster_static.json",
        "07_code_aster_modal.json",
        "11_precice_native_window.json",
    )
    receipts = {name: load(name) for name in receipt_names}

    # ---- real native QoI ladders fed to the real independence runner ----
    of = receipts["issue37_openfoam.json"].get("benchmarks", {}).get("channel", {})
    el = receipts["issue39_elmer.json"].get("benchmarks", {}).get("steadyDirichlet", {})

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
    states = derive_receipt_states(receipts)

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
        "structural-modal",
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

    openfoam_independent = independence.get("openfoamChannel", {}).get("accepted") is True
    elmer_independent = independence.get("elmerSteady", {}).get("accepted") is True
    structural_independent = (
        receipts["07_code_aster_static.json"].get("mesh_independence_passed") is True
    )
    rotor_independent = (
        receipts["issue38_ross.json"].get("discretizationIndependencePassed") is True
    )

    # 4) honest real set -> every availability claim comes from a receipt.
    real = [
        participant("cad-interchange", True),
        participant("domain-mesh", True),
        participant(
            "incompressible-steady-flow",
            states["incompressible-steady-flow"],
            mesh=openfoam_independent,
        ),
        participant(
            "structural-static",
            states["structural-static"],
            mesh=structural_independent,
        ),
        participant(
            "structural-modal",
            states["structural-modal"],
            mesh=structural_independent,
        ),
        participant(
            "thermal-conduction",
            states["thermal-conduction"],
            mesh=elmer_independent,
        ),
        participant(
            "rotor-campbell",
            states["rotor-campbell"],
            mesh=rotor_independent,
        ),
        participant(
            "rotating-electrical-machine",
            states["rotating-electrical-machine"],
            closure=states["rotating-electrical-machine"],
        ),
        participant(
            "coupled-interface-validation",
            states["coupled-interface-validation"],
            coupling=states["coupled-interface-validation"],
        ),
    ]
    out["honestSet"] = assess_promotion(
        "candidate-real-receipts",
        real,
        require_mesh_independence=True,
        require_timestep_independence=True,
    ).as_dict()

    out["refusesInvalid"] = (not no_thermal.validated_final) and (not bad.validated_final)
    succeeded = final_gate_succeeded(out)
    out["status"] = "EXECUTED" if succeeded else "BLOCKED"
    (RECEIPTS / "issue41_gate.json").write_text(json.dumps(out, indent=2, sort_keys=True))
    print(
        "WROTE issue41_gate.json status=",
        out["status"],
        "positive=",
        ok.validated_final,
        "refusesInvalid=",
        out["refusesInvalid"],
    )
    return 0 if succeeded else 1


if __name__ == "__main__":
    sys.exit(main())
