#!/usr/bin/env python3
"""Governed native-worker evidence driver (issue #47 + GEN 06/07/08/11).

Every native execution goes through the repo's own ``NativeJobManager``: the
participant manifest chooses prepare/parse/validate, the lifecycle claims the
case directory, runs the allowlisted command, and publishes a ResultEnvelope
only when the quality gate passes. Nothing here fabricates a number: a job that
does not COMPLETE is recorded with its real failure code, and anything the
product path cannot execute is labelled BLOCKED with the exact reason.

The only non-governed work is *mesh preparation* (converting a generated gmsh
mesh into the solver-native mesh directory a preCICE/Elmer/OpenFOAM participant
expects), which is staged into the case directory before the governed run; the
solver execution itself is always the governed command.

Usage: governed-run.py --out <evidence-dir> [--issues 47,06,07,08,11]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import traceback
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(os.environ.get("REPO_ROOT", "/opt/repo"))
JOB_ROOT = Path(os.environ.get("AEROWORKBENCH_JOB_ROOT", "/opt/aero-jobs"))
PY312 = os.environ.get("PY312", "/opt/py312/bin/python")


def _bootstrap_path() -> None:
    paths = [str(REPO), str(REPO / "solvers"), str(REPO / "services" / "api")]
    packages = REPO / "packages"
    if packages.is_dir():
        paths.extend(sorted(str(child) for child in packages.iterdir() if child.is_dir()))
    for entry in reversed(paths):
        if entry not in sys.path:
            sys.path.insert(0, entry)


_bootstrap_path()

from participants.lifecycle import NativeJobManager  # noqa: E402


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_text(path: Path, limit: int = 200_000) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:limit]
    except OSError:
        return ""


def sh(cmd: list[str], cwd: Path, timeout: int = 900) -> dict:
    started = time.time()
    try:
        done = subprocess.run(
            cmd, cwd=str(cwd), capture_output=True, text=True, timeout=timeout
        )
        return {
            "command": cmd,
            "returncode": done.returncode,
            "stdout": (done.stdout or "")[-4000:],
            "stderr": (done.stderr or "")[-4000:],
            "seconds": round(time.time() - started, 3),
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "command": cmd,
            "returncode": 124,
            "stdout": (exc.stdout or b"").decode(errors="replace")[-2000:]
            if isinstance(exc.stdout, bytes)
            else str(exc.stdout or "")[-2000:],
            "stderr": f"TIMEOUT:{timeout}s",
            "seconds": round(time.time() - started, 3),
        }


class Driver:
    def __init__(self, out: Path, job_root: Path) -> None:
        self.out = out
        self.job_root = job_root
        self.out.mkdir(parents=True, exist_ok=True)
        job_root.mkdir(parents=True, exist_ok=True)
        self.manager = NativeJobManager(job_root, timeout_s=600.0)
        self.receipts: dict[str, dict] = {}

    # -- generic governed run -------------------------------------------------
    def governed(
        self,
        issue: str,
        participant: str,
        inputs: dict,
        *,
        analysis: str | None = None,
        fidelity: str | None = None,
        pre=None,
        extra: dict | None = None,
    ) -> dict:
        record: dict = {
            "issue": issue,
            "participant": participant,
            "analysis": analysis,
            "fidelity": fidelity,
            "inputs_digest": sha256_bytes(
                json.dumps(inputs, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ),
            "started_at": datetime.now(UTC).isoformat(),
        }
        record.update(extra or {})
        job_id = self.manager.submit(
            participant,
            inputs,
            design_id=f"governed-{issue}",
            analysis=analysis,
            fidelity=fidelity,
            deferred=True,
        )
        record["job_id"] = job_id
        case_dir = self.job_root / f"case-{job_id[:12]}"
        record["case_dir"] = str(case_dir)
        try:
            if pre is not None:
                pre(case_dir)
            started = time.time()
            state = self.manager.run(job_id)
            record["wall_s"] = round(time.time() - started, 3)
        except Exception as exc:  # noqa: BLE001
            record["state"] = "DRIVER_ERROR"
            record["error"] = f"{type(exc).__name__}:{exc}"
            record["traceback"] = traceback.format_exc()[-4000:]
            self.receipts[issue] = record
            return record
        try:
            status = self.manager.status(job_id)
        except Exception as exc:  # noqa: BLE001
            status = {"error": f"{type(exc).__name__}:{exc}"}
        record["state"] = state
        record["status"] = status
        record["events"] = [event["state"] for event in self.manager.events(job_id)]
        if state == "COMPLETED":
            envelope = self.manager.envelope(job_id)
            record["envelope_source"] = envelope.get("source")
            record["envelope_validity"] = envelope.get("validity")
            record["scalars"] = envelope.get("scalars")
            record["units"] = envelope.get("units")
            record["run_id"] = envelope.get("run_id")
            record["provenance_id"] = envelope.get("provenance_id")
            record["artifacts"] = self._artifact_hashes(job_id, case_dir)
            (self.out / f"{issue}_envelope.json").write_text(
                json.dumps(envelope, indent=2, sort_keys=True), encoding="utf-8"
            )
        else:
            # Capture the real failure evidence; never invent a result.
            record["error_code"] = status.get("error_code")
            record["error_detail"] = status.get("error_detail")
            record["solver_log_tail"] = read_text(case_dir / "solver.log")[-4000:]
            record["stdout_tail"] = read_text(case_dir / "stdout.log")[-2000:]
            record["stderr_tail"] = read_text(case_dir / "stderr.log")[-2000:]
        self.receipts[issue] = record
        return record

    def _artifact_hashes(self, job_id: str, case_dir: Path) -> dict:
        hashes: dict = {}
        try:
            metadata = self.manager.artifact_metadata(job_id)
        except Exception as exc:  # noqa: BLE001
            return {"error": f"{type(exc).__name__}:{exc}"}
        for entry in metadata:
            name = entry.get("name")
            path = case_dir / str(name)
            record = dict(entry)
            if path.is_file():
                record["observed_sha256"] = sha256_file(path)
                record["observed_bytes"] = path.stat().st_size
            hashes[str(name)] = record
        return hashes

    # -- helpers --------------------------------------------------------------
    def copy_artifact(self, source: Path, dest_name: str) -> None:
        if source.is_file():
            shutil.copyfile(source, self.out / dest_name)

    def write(self, name: str, payload) -> None:
        (self.out / name).write_text(
            json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8"
        )

    def close(self) -> None:
        self.manager.close()


# -- issue 47: governed ROSS forced ------------------------------------------

def issue_47(driver: Driver) -> dict:
    inputs = {
        "analysis": "forced",
        "shaft_length_m": 1.5,
        "shaft_diameter_m": 0.05,
        "n_elements": 4,
        "bearing_stiffness_n_m": 1.0e8,
        "bearing_damping_n_s_m": 1000.0,
        "speed_rpm": 3000.0,
        "unbalance": {"node": 2, "magnitude_kg_m": 1.0e-4, "phase_deg": 0.0},
    }
    record = driver.governed(
        "47_ross_forced",
        "rotor-campbell",
        inputs,
        analysis="forced",
        fidelity="beam-campbell",
    )
    case_dir = Path(record.get("case_dir", ""))
    if case_dir.is_dir():
        driver.copy_artifact(case_dir / "result.json", "47_result.json")
        driver.copy_artifact(case_dir / "case.json", "47_case.json")
        driver.copy_artifact(case_dir / "solver.log", "47_solver.log")
        driver.copy_artifact(case_dir / "run_ross.py", "47_run_ross.py")
    return record


# -- issue 08: governed Elmer two-material -----------------------------------

def _elmer_two_material_mesh(work: Path) -> dict:
    """Build a conforming two-body 3D slab and convert it for ElmerSolver."""

    import gmsh  # type: ignore

    work.mkdir(parents=True, exist_ok=True)
    msh_path = work / "domain.msh"
    gmsh.initialize()
    try:
        gmsh.model.add("two_material")
        gmsh.model.occ.addBox(0.0, 0.0, 0.0, 0.3, 0.1, 0.05, tag=1)
        gmsh.model.occ.addBox(0.3, 0.0, 0.0, 0.3, 0.1, 0.05, tag=2)
        gmsh.model.occ.fragment([(3, 1), (3, 2)], [])
        gmsh.model.occ.synchronize()
        for dim, tag in gmsh.model.getEntities(3):
            xmin, _, _, xmax, _, _ = gmsh.model.getBoundingBox(dim, tag)
            centre = 0.5 * (xmin + xmax)
            name = "material_body_a" if centre < 0.3 else "material_body_b"
            gmsh.model.addPhysicalGroup(dim, [tag], name=name)
        for dim, tag in gmsh.model.getEntities(2):
            xmin, _, _, xmax, _, _ = gmsh.model.getBoundingBox(dim, tag)
            centre = 0.5 * (xmin + xmax)
            if centre < 0.05:
                gmsh.model.addPhysicalGroup(dim, [tag], name="left")
            elif centre > 0.55:
                gmsh.model.addPhysicalGroup(dim, [tag], name="right")
        gmsh.option.setNumber("Mesh.MeshSizeMin", 0.02)
        gmsh.option.setNumber("Mesh.MeshSizeMax", 0.04)
        gmsh.model.mesh.generate(3)
        gmsh.write(str(msh_path))
    finally:
        gmsh.finalize()
    elmer_grid = sh(["ElmerGrid", "14", "2", str(msh_path), "-out", "domain"], work)
    names_path = work / "domain" / "mesh.names"
    names: dict[str, int] = {}
    if names_path.is_file():
        for line in names_path.read_text(errors="replace").splitlines():
            match = re.match(r"\s*\$?\s*(\w+)\s*=\s*(\d+)", line)
            if match:
                names[match.group(1)] = int(match.group(2))
    return {
        "msh_path": msh_path,
        "elmer_dir": work / "domain",
        "names": names,
        "elmergrid": elmer_grid,
        "mesh_hash": sha256_file(msh_path),
    }


def issue_08(driver: Driver) -> dict:
    work = driver.out / "gen08_work"
    built = _elmer_two_material_mesh(work)
    (driver.out / "08_elmergrid.json").write_text(
        json.dumps(built["elmergrid"], indent=2, sort_keys=True), encoding="utf-8"
    )
    names = built["names"]

    def _sorted(entries: list[tuple[str, int]]) -> list[tuple[str, int]]:
        return sorted(entries, key=lambda item: item[1])

    body_order = [
        name
        for name, _ in _sorted(
            [(name, names[name]) for name in ("material_body_a", "material_body_b") if name in names]
        )
    ]
    patch_order = [
        name
        for name, _ in _sorted(
            [(name, names[name]) for name in ("left", "right") if name in names]
        )
    ]
    if not body_order:
        body_order = ["material_body_a", "material_body_b"]
    if not patch_order:
        patch_order = ["left", "right"]
    region_for = {"material_body_a": "body_a", "material_body_b": "body_b"}
    material_for = {"body_a": "steel-high-k", "body_b": "insulator-low-k"}
    body_ids = {name: names[name] for name in body_order if name in names}
    patch_ids = {name: names[name] for name in patch_order if name in names}
    mapping = {
        "provenance": {
            "geometryHash": "a" * 64,
            "meshHash": built["mesh_hash"],
            "topologyDigest": sha256_bytes(b"governed-gen08-two-material"),
        },
        "exports": [
            {
                "participant": "elmer",
                "zones": [
                    {"name": name, "motion": "stationary", "domain": "solid"}
                    for name in body_order
                ],
                "patches": [{"name": name, "kind": "wall"} for name in patch_order],
                "interfaces": [],
                "materials": [
                    {"name": region_for[name], "material": material_for[region_for[name]]}
                    for name in body_order
                ],
            }
        ],
    }
    inputs = {
        "model": "thermal",
        "analysis": "steady",
        "mesh_mapping": mapping,
        "mesh_file": "domain.msh",
        "mesh_source": str(built["msh_path"]),
        "mesh_hash": built["mesh_hash"],
        "geometry_hash": "a" * 64,
        "materials": {
            "steel-high-k": {
                "conductivity": 2.0,
                "heat_capacity": 1.0,
                "density": 1.0,
            },
            "insulator-low-k": {
                "conductivity": 0.5,
                "heat_capacity": 1.0,
                "density": 1.0,
            },
        },
        "fixed_temperature": [
            {"patch": "left", "temperature_k": 400.0},
            {"patch": "right", "temperature_k": 300.0},
        ],
        "heat_sources": [],
        "energy_balance_tolerance": 1.0e-3,
        "ambient_k": 300.0,
    }
    elmer_dir = built["elmer_dir"]

    def pre(case_dir: Path) -> None:
        case_dir.mkdir(parents=True, exist_ok=True)
        target = case_dir / "domain"
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(elmer_dir, target)

    record = driver.governed(
        "08_elmer_multimaterial",
        "thermal-conduction",
        inputs,
        analysis="steady",
        pre=pre,
        extra={
            "mesh_hash": built["mesh_hash"],
            "elmer_mesh_names": built["names"],
            "body_ids": body_ids,
            "patch_ids": patch_ids,
            "analytic": {
                "conductivity_a_w_m_k": 2.0,
                "conductivity_b_w_m_k": 0.5,
                "length_a_m": 0.3,
                "length_b_m": 0.3,
                "t_left_k": 400.0,
                "t_right_k": 300.0,
                "series_resistance": 0.3 / 2.0 + 0.3 / 0.5,
                "flux_w_m2": 100.0 / (0.3 / 2.0 + 0.3 / 0.5),
                "interface_temperature_k": 400.0 - (100.0 / (0.3 / 2.0 + 0.3 / 0.5)) * (0.3 / 2.0),
            },
        },
    )
    case_dir = Path(record.get("case_dir", ""))
    if case_dir.is_dir():
        for name in ("result.dat", "solver.log"):
            driver.copy_artifact(case_dir / name, f"08_{name}")
        for region in case_dir.glob("region_*.dat"):
            driver.copy_artifact(region, f"08_{region.name}")
        driver.copy_artifact(case_dir / "case.sif", "08_case.sif")
    return record


# -- GEN 06: governed OpenFOAM AMI (capability attempt) ----------------------

def issue_06(driver: Driver) -> dict:
    inputs = {
        "compressibility": "incompressible",
        "steady": False,
        "rotating_model": "AMI",
        "thermal_model": "isothermal",
        "turbulence": "laminar",
        "inlet_velocity_m_s": 1.0,
        "outlet_pressure_pa": 0.0,
        "density_kg_m3": 1.225,
        "viscosity_pa_s": 1.8e-5,
        "end_time": 0.02,
        "rotating_zones": [{"name": "rotor", "rotation_rate_rpm": 1000.0}],
        "ami_pairs": [
            {
                "name": "seal_pair",
                "zone_a": "rotor",
                "zone_b": "stator",
                "master_patch": "seal_master",
                "slave_patch": "seal_slave",
            }
        ],
        "result_requests": ["force", "torque", "mass_flow"],
    }
    return driver.governed(
        "06_openfoam_ami",
        "rotating-flow-mrf",
        inputs,
        analysis="transient-ami",
    )


# -- GEN 07: governed Code_Aster static (capability attempt) -----------------

def issue_07(driver: Driver) -> dict:
    inputs = {
        "analysis": "static",
        "youngs_modulus_pa": 2.1e11,
        "poisson_ratio": 0.3,
        "density_kg_m3": 7800.0,
        "applied_force_n": 1000.0,
        "mesh_file": "mesh.med",
    }
    return driver.governed("07_code_aster_static", "structural-static", inputs)


# -- GEN 11: conservative mapping integral conservation (repo path) ----------

def issue_11(driver: Driver) -> dict:
    from aeroworkbench_coupling.field import register_mesh
    from precice.coupling import map_field

    source = register_mesh("src", (0.0, 0.25, 0.5, 0.75, 1.0))
    values = (7.0,) * 5
    source_integral = 7.0 * (source.coordinates[-1] - source.coordinates[0])
    results = []
    for resolution in ((0.0, 0.5, 1.0), (0.0, 0.2, 0.4, 0.6, 0.8, 1.0), (0.0, 0.125, 0.25, 0.375, 0.5, 0.625, 0.75, 0.875, 1.0)):
        target = register_mesh("tgt", resolution)
        mapped, record = map_field(source, values, target, "pressure", method="conservative")
        widths = [b - a for a, b in zip(target.coordinates, target.coordinates[1:])]
        target_integral = sum(v * w for v, w in zip(mapped, widths))
        results.append(
            {
                "resolution_points": len(resolution),
                "accepted": record.accepted,
                "relative_conservation_error": record.relative_conservation_error,
                "source_integral": source_integral,
                "target_integral": target_integral,
                "target_integral_rel_error": abs(target_integral - source_integral)
                / max(abs(source_integral), 1e-30),
                "method": record.method,
                "source_hash": record.source_hash,
                "target_hash": record.target_hash,
            }
        )
    record = {
        "issue": "11_precice_conservative",
        "engine": "analytic-transfer (repo conservative mapping; not native solver output)",
        "source_integral": source_integral,
        "resolutions": results,
        "native_coupled_window": {
            "status": "BLOCKED",
            "reason": (
                "no governed participant launches a native preCICE coupled window: the "
                "coupled-interface-validation participant only runs precice-config-visualizer "
                "config validation and its run script/command has no native coupling loop; "
                "adding one would require a new manifest + run script outside this run's scope"
            ),
        },
    }
    driver.write("11_precice_conservative.json", record)
    return record


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--issues", default="47,06,07,08,11")
    args = parser.parse_args()
    out = Path(args.out)
    driver = Driver(out, JOB_ROOT)
    selected = {item.strip() for item in args.issues.split(",") if item.strip()}
    print("PYTHON", sys.version.split()[0], sys.executable)
    print("REPO", REPO, "JOB_ROOT", JOB_ROOT)
    from participants.capabilities import probe_all

    probes = {
        probe.participant_id: {
            "state": probe.state,
            "solver_id": probe.solver_id,
            "executable": probe.executable,
            "version": probe.version,
            "detail": probe.detail,
        }
        for probe in probe_all()
    }
    driver.write("capabilities.json", probes)
    for participant in (
        "rotor-campbell",
        "thermal-conduction",
        "rotating-flow-mrf",
        "structural-static",
        "coupled-interface-validation",
    ):
        print("PROBE", participant, probes[participant]["state"], probes[participant]["detail"])
    try:
        if "47" in selected:
            print("== ISSUE 47 governed ROSS forced ==")
            driver.write("47_ross_forced.json", issue_47(driver))
        if "08" in selected:
            print("== GEN 08 governed Elmer multi-material ==")
            try:
                driver.write("08_elmer_multimaterial.json", issue_08(driver))
            except Exception as exc:  # noqa: BLE001
                driver.write(
                    "08_elmer_multimaterial.json",
                    {
                        "issue": "08_elmer_multimaterial",
                        "state": "BLOCKED",
                        "reason": f"mesh/prepare error:{type(exc).__name__}:{exc}",
                        "traceback": traceback.format_exc()[-4000:],
                    },
                )
        if "06" in selected:
            print("== GEN 06 governed OpenFOAM transient AMI ==")
            try:
                driver.write("06_openfoam_ami.json", issue_06(driver))
            except Exception as exc:  # noqa: BLE001
                driver.write(
                    "06_openfoam_ami.json",
                    {
                        "issue": "06_openfoam_ami",
                        "state": "BLOCKED",
                        "reason": f"{type(exc).__name__}:{exc}",
                        "traceback": traceback.format_exc()[-4000:],
                    },
                )
        if "07" in selected:
            print("== GEN 07 governed Code_Aster static ==")
            try:
                driver.write("07_code_aster_static.json", issue_07(driver))
            except Exception as exc:  # noqa: BLE001
                driver.write(
                    "07_code_aster_static.json",
                    {
                        "issue": "07_code_aster_static",
                        "state": "BLOCKED",
                        "reason": f"{type(exc).__name__}:{exc}",
                        "traceback": traceback.format_exc()[-4000:],
                    },
                )
        if "11" in selected:
            print("== GEN 11 conservative mapping conservation ==")
            try:
                driver.write("11_precice_conservative.json", issue_11(driver))
            except Exception as exc:  # noqa: BLE001
                driver.write(
                    "11_precice_conservative.json",
                    {
                        "issue": "11_precice_conservative",
                        "state": "BLOCKED",
                        "reason": f"{type(exc).__name__}:{exc}",
                        "traceback": traceback.format_exc()[-4000:],
                    },
                )
    finally:
        driver.close()
    print("GOVERNED RUN DONE ->", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
