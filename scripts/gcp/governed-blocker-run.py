#!/usr/bin/env python3
"""Governed native blocker-fix evidence driver (GEN 06/07/08/11).

Every native execution goes through ``NativeJobManager``; the participant
manifest chooses prepare/parse/validate, the lifecycle runs the allowlisted
command, and a ResultEnvelope publishes only on a passed quality gate. Mesh
*conversion* is owned by the OpenFOAM participant (``mesh_conversion``), while
Elmer/Code_Aster mesh building is staged into the case directory before the
governed run and recorded explicitly. Nothing is fabricated.

Usage: governed-blocker-run.py --out <evidence-dir> [--issues 06,07,08,11]
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
        done = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, timeout=timeout)
        return {
            "command": cmd,
            "returncode": done.returncode,
            "stdout": (done.stdout or "")[-4000:],
            "stderr": (done.stderr or "")[-4000:],
            "seconds": round(time.time() - started, 3),
        }
    except subprocess.TimeoutExpired:
        return {"command": cmd, "returncode": 124, "stderr": f"TIMEOUT:{timeout}s"}


class Driver:
    def __init__(self, out: Path, job_root: Path) -> None:
        self.out = out
        self.job_root = job_root
        self.out.mkdir(parents=True, exist_ok=True)
        job_root.mkdir(parents=True, exist_ok=True)
        self.manager = NativeJobManager(job_root, timeout_s=600.0)
        self.receipts: dict[str, dict] = {}

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

    def copy_artifact(self, source: Path, dest_name: str) -> None:
        if source.is_file():
            shutil.copyfile(source, self.out / dest_name)

    def write(self, name: str, payload) -> None:
        (self.out / name).write_text(
            json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8"
        )

    def close(self) -> None:
        self.manager.close()


# -- GEN 06: OpenFOAM --------------------------------------------------------

_OPENFOAM_TEMPLATE_INPUTS = {
    "compressibility": "incompressible",
    "steady": False,
    "rotating_model": "none",
    "thermal_model": "isothermal",
    "turbulence": "laminar",
    "inlet_velocity_m_s": 0.5,
    "outlet_pressure_pa": 0.0,
    "density_kg_m3": 1000.0,
    "viscosity_pa_s": 1.0e-3,
    "end_time": 0.01,
    "result_requests": ["mass_flow", "residuals", "continuity", "pressure"],
}


def _openfoam_duct_mesh(work: Path, name: str) -> dict:
    """Build a governed 2D duct mesh artifact (domain.msh + mapping)."""

    import gmsh  # type: ignore

    work.mkdir(parents=True, exist_ok=True)
    msh_path = work / "domain.msh"
    gmsh.initialize()
    try:
        gmsh.model.add(name)
        gmsh.model.occ.addRectangle(0.0, 0.0, 0.0, 0.5, 0.1, tag=1)
        gmsh.model.occ.synchronize()
        gmsh.model.addPhysicalGroup(2, [1], name="fluid")
        for dim, tag in gmsh.model.getEntities(1):
            xmin, ymin, _, xmax, ymax, _ = gmsh.model.getBoundingBox(dim, tag)
            if abs(xmin) < 1e-9:
                label = "inlet"
            elif abs(xmax - 0.5) < 1e-9:
                label = "outlet"
            else:
                label = "walls"
            gmsh.model.addPhysicalGroup(dim, [tag], name=label)
        gmsh.option.setNumber("Mesh.MeshSizeMin", 0.01)
        gmsh.option.setNumber("Mesh.MeshSizeMax", 0.02)
        gmsh.model.mesh.generate(2)
        gmsh.write(str(msh_path))
    finally:
        gmsh.finalize()
    mesh_hash = sha256_file(msh_path)
    mapping = {
        "provenance": {
            "geometryHash": "a" * 64,
            "meshHash": mesh_hash,
            "topologyDigest": sha256_bytes(b"openfoam-duct"),
        },
        "exports": [
            {
                "participant": "openfoam",
                "zones": [{"name": "fluid", "motion": "stationary", "domain": "fluid"}],
                "patches": [
                    {"name": "inlet", "kind": "inlet", "nativeType": "patch"},
                    {"name": "outlet", "kind": "outlet", "nativeType": "patch"},
                    {"name": "walls", "kind": "wall", "nativeType": "wall"},
                ],
                "interfaces": [],
            }
        ],
    }
    (work / "mesh_mapping.json").write_text(json.dumps(mapping, indent=2), encoding="utf-8")
    return {"dir": work, "msh": msh_path, "mesh_hash": mesh_hash}


def issue_06_openfoam(driver: Driver) -> dict:
    work = driver.out / "gen06_work"
    built = _openfoam_duct_mesh(work, "duct")
    return driver.governed(
        "06_openfoam_transient",
        "incompressible-steady-flow",
        {
            **_OPENFOAM_TEMPLATE_INPUTS,
            "mesh_artifact_dir": str(built["dir"]),
            "mesh_conversion": "gmshToFoam",
            "geometry_hash": "a" * 64,
            "mesh_hash": built["mesh_hash"],
            "required_patch_kinds": ["inlet", "outlet", "wall"],
        },
        analysis="transient",
        extra={"mesh_hash": built["mesh_hash"]},
    )


def _openfoam_ami_mesh(work: Path) -> dict:
    """Build a two-region rotor/stator mesh with a non-conformal AMI gap."""

    import gmsh  # type: ignore

    work.mkdir(parents=True, exist_ok=True)
    msh_path = work / "domain.msh"
    gmsh.initialize()
    try:
        gmsh.model.add("ami")
        rotor = gmsh.model.occ.addDisk(0.0, 0.0, 0.0, 0.049, 0.049)
        outer = gmsh.model.occ.addDisk(0.0, 0.0, 0.0, 0.12, 0.12)
        gmsh.model.occ.synchronize()
        stator, _ = gmsh.model.occ.cut([(2, outer)], [(2, rotor)])
        gmsh.model.occ.synchronize()
        gmsh.model.addPhysicalGroup(2, [rotor], name="rotor")
        gmsh.model.addPhysicalGroup(2, stator, name="stator")
        # Interface curves: closest to r=0.049 -> seal_master; r=0.12 -> walls.
        for dim, tag in gmsh.model.getEntities(1):
            xmin, ymin, _, xmax, ymax, _ = gmsh.model.getBoundingBox(dim, tag)
            radius = max(abs(xmin), abs(xmax), abs(ymin), abs(ymax))
            if abs(radius - 0.049) < 1e-4:
                gmsh.model.addPhysicalGroup(dim, [tag], name="seal_master")
            elif abs(radius - 0.12) < 1e-4:
                gmsh.model.addPhysicalGroup(dim, [tag], name="seal_slave")
        gmsh.option.setNumber("Mesh.MeshSizeMin", 0.006)
        gmsh.option.setNumber("Mesh.MeshSizeMax", 0.012)
        gmsh.model.mesh.generate(2)
        gmsh.write(str(msh_path))
    finally:
        gmsh.finalize()
    return {"dir": work, "msh": msh_path, "mesh_hash": sha256_file(msh_path)}


def issue_06_ami(driver: Driver) -> dict:
    work = driver.out / "gen06_ami_work"
    try:
        built = _openfoam_ami_mesh(work)
    except Exception as exc:  # noqa: BLE001
        return driver.governed(
            "06_openfoam_ami",
            "rotating-flow-mrf",
            {**_OPENFOAM_TEMPLATE_INPUTS, "rotating_model": "AMI"},
            analysis="transient-ami",
            extra={"mesh_build_error": f"{type(exc).__name__}:{exc}"},
        )
    return driver.governed(
        "06_openfoam_ami",
        "rotating-flow-mrf",
        {
            **_OPENFOAM_TEMPLATE_INPUTS,
            "rotating_model": "AMI",
            "mesh_artifact_dir": str(built["dir"]),
            "mesh_conversion": "gmshToFoam",
            "geometry_hash": "a" * 64,
            "mesh_hash": built["mesh_hash"],
            "required_patch_kinds": ["inlet", "outlet"],
            "rotating_zones": [{"name": "rotor", "rotation_rate_rpm": 500.0}],
            "ami_pairs": [
                {
                    "name": "seal",
                    "zone_a": "rotor",
                    "zone_b": "stator",
                    "master_patch": "seal_master",
                    "slave_patch": "seal_slave",
                }
            ],
        },
        analysis="transient-ami",
        extra={"mesh_hash": built["mesh_hash"]},
    )


# -- GEN 07: Code_Aster ------------------------------------------------------


def _aster_mesh(work: Path) -> dict:
    import gmsh  # type: ignore

    work.mkdir(parents=True, exist_ok=True)
    msh_path = work / "mesh.msh"
    gmsh.initialize()
    try:
        gmsh.model.add("cantilever")
        gmsh.model.occ.addBox(0.0, 0.0, 0.0, 0.4, 0.05, 0.05, tag=1)
        gmsh.model.occ.synchronize()
        gmsh.model.addPhysicalGroup(3, [1], name="solid")
        for dim, tag in gmsh.model.getEntities(2):
            xmin, _, _, xmax, _, _ = gmsh.model.getBoundingBox(dim, tag)
            if abs(xmin) < 1e-9:
                gmsh.model.addPhysicalGroup(dim, [tag], name="clamp-face")
            elif abs(xmax - 0.4) < 1e-9:
                gmsh.model.addPhysicalGroup(dim, [tag], name="tip-face")
        gmsh.option.setNumber("Mesh.MeshSizeMin", 0.02)
        gmsh.option.setNumber("Mesh.MeshSizeMax", 0.04)
        gmsh.model.mesh.generate(3)
        gmsh.write(str(msh_path))
    finally:
        gmsh.finalize()
    return {"msh": msh_path, "mesh_hash": sha256_file(msh_path)}


def _aster_inputs(built: dict, analysis: str) -> dict:
    return {
        "analysis": analysis,
        "mesh": {
            "file": "mesh.msh",
            "format": "GMSH",
            "volumes": ["solid"],
            "surfaces": ["clamp-face", "tip-face"],
            "nodes": [],
            "material_groups": {"solid": "material_solid"},
            "interfaces": [],
            "frames": {},
            "geometry_hash": "a" * 64,
            "mesh_hash": built["mesh_hash"],
        },
        "materials": [
            {
                "region": "solid",
                "identity": "steel",
                "symmetry": "isotropic",
                "youngs_modulus_pa": 2.1e11,
                "poisson_ratio": 0.3,
                "density_kg_m3": 7800.0,
            }
        ],
        "constraints": [{"name": "clamp", "mode": "fixed", "group": "clamp-face"}],
        "loads": [
            {
                "name": "tip-load",
                "kind": "traction",
                "target": "tip-face",
                "FZ": -1.0e6,
            }
        ],
        "n_modes": 4,
    }


def issue_07_aster(driver: Driver, analysis: str) -> dict:
    work = driver.out / "gen07_work"
    built = _aster_mesh(work)
    mesh_source = built["msh"]

    def pre(case_dir: Path) -> None:
        case_dir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(mesh_source, case_dir / "mesh.msh")

    return driver.governed(
        f"07_code_aster_{analysis}",
        "structural-modal" if analysis == "modal" else "structural-static",
        _aster_inputs(built, analysis),
        analysis=analysis,
        pre=pre,
        extra={"mesh_hash": built["mesh_hash"]},
    )


# -- GEN 08: Elmer -----------------------------------------------------------


def _elmer_two_material_mesh(work: Path) -> dict:
    import gmsh  # type: ignore

    work.mkdir(parents=True, exist_ok=True)
    msh_path = work / "domain.msh"
    gmsh.initialize()
    try:
        gmsh.model.add("two_material")
        a = gmsh.model.occ.addBox(0.0, 0.0, 0.0, 0.3, 0.1, 0.05)
        b = gmsh.model.occ.addBox(0.3, 0.0, 0.0, 0.3, 0.1, 0.05)
        gmsh.model.occ.synchronize()
        gmsh.model.addPhysicalGroup(3, [a], name="material_body_a")
        gmsh.model.addPhysicalGroup(3, [b], name="material_body_b")
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
    body_ids = {
        "body_a": names.get("material_body_a", 1),
        "body_b": names.get("material_body_b", 2),
    }
    boundary_ids = {"left": names.get("left", 3), "right": names.get("right", 4)}
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
                    {"name": "body_a", "motion": "stationary", "domain": "solid"},
                    {"name": "body_b", "motion": "stationary", "domain": "solid"},
                ],
                "patches": [
                    {"name": "left", "kind": "wall"},
                    {"name": "right", "kind": "wall"},
                ],
                "interfaces": [],
                "materials": [
                    {"name": "body_a", "material": "steel-high-k"},
                    {"name": "body_b", "material": "insulator-low-k"},
                ],
                "bodyIds": body_ids,
                "boundaryIds": boundary_ids,
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
                "deterministic": True,
                "properties": {"conductivity": 2.0, "heat_capacity": 1.0, "density": 1.0},
            },
            "insulator-low-k": {
                "deterministic": True,
                "properties": {"conductivity": 0.5, "heat_capacity": 1.0, "density": 1.0},
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
            "boundary_ids": boundary_ids,
        },
    )
    case_dir = Path(record.get("case_dir", ""))
    if case_dir.is_dir():
        for name in ("result.dat", "solver.log", "case.sif"):
            driver.copy_artifact(case_dir / name, f"08_{name}")
        for boundary in case_dir.glob("boundary_*.dat"):
            driver.copy_artifact(boundary, f"08_{boundary.name}")
    return record


# -- GEN 11: native preCICE coupled window -----------------------------------


def issue_11(driver: Driver) -> dict:
    return driver.governed(
        "11_precice_native_window",
        "native-coupled-window",
        {
            "participants": ["A", "B"],
            "coupling_dt_s": 1.0,
            "max_iterations": 8,
            "tolerance": 1.0e-6,
            "n_interface_points": 8,
        },
        analysis="implicit-iqn",
        extra={},
    )


def _probes(driver: Driver) -> dict:
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
    return probes


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--issues", default="06,06ami,07static,07modal,08,11")
    args = parser.parse_args()
    out = Path(args.out)
    driver = Driver(out, JOB_ROOT)
    selected = {item.strip() for item in args.issues.split(",") if item.strip()}
    print("PYTHON", sys.version.split()[0], sys.executable)
    print("REPO", REPO, "JOB_ROOT", JOB_ROOT)
    probes = _probes(driver)
    for participant in (
        "incompressible-steady-flow",
        "rotating-flow-mrf",
        "structural-static",
        "structural-modal",
        "thermal-conduction",
        "native-coupled-window",
    ):
        entry = probes.get(participant, {})
        print("PROBE", participant, entry.get("state"), entry.get("detail"))
    try:
        if "06" in selected:
            print("== GEN 06 governed OpenFOAM transient (converted mesh) ==")
            driver.write("06_openfoam_transient.json", issue_06_openfoam(driver))
        if "06ami" in selected:
            print("== GEN 06 governed OpenFOAM transient AMI ==")
            try:
                driver.write("06_openfoam_ami.json", issue_06_ami(driver))
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
        if "07static" in selected:
            print("== GEN 07 governed Code_Aster static ==")
            try:
                driver.write("07_code_aster_static.json", issue_07_aster(driver, "static"))
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
        if "07modal" in selected:
            print("== GEN 07 governed Code_Aster modal ==")
            try:
                driver.write("07_code_aster_modal.json", issue_07_aster(driver, "modal"))
            except Exception as exc:  # noqa: BLE001
                driver.write(
                    "07_code_aster_modal.json",
                    {
                        "issue": "07_code_aster_modal",
                        "state": "BLOCKED",
                        "reason": f"{type(exc).__name__}:{exc}",
                        "traceback": traceback.format_exc()[-4000:],
                    },
                )
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
        if "11" in selected:
            print("== GEN 11 governed native preCICE window ==")
            try:
                driver.write("11_precice_native_window.json", issue_11(driver))
            except Exception as exc:  # noqa: BLE001
                driver.write(
                    "11_precice_native_window.json",
                    {
                        "issue": "11_precice_native_window",
                        "state": "BLOCKED",
                        "reason": f"{type(exc).__name__}:{exc}",
                        "traceback": traceback.format_exc()[-4000:],
                    },
                )
    finally:
        driver.close()
    print("GOVERNED BLOCKER RUN DONE ->", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
