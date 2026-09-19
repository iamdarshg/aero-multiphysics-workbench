#!/bin/bash
# Governed worker bootstrap (issue #47 + GEN 06/07/08/11 residuals).
#
# Installs the pinned repo python environment with uv (services/api/uv.lock)
# and the native solver prefixes needed to drive the repo's own
# NativeJobManager participant path. Never fakes success: every step is
# bounded and non-fatal, every capability is probed and its real version
# recorded in /var/log/proofs/versions.json, and the readiness marker
# /var/log/proofs/governed-install.done is only written when the stack needed
# by the requested participants is actually present. A missing stack writes
# /var/log/proofs/governed-install.failed with the exact reasons.
set +u
LOGDIR=/var/log/proofs
mkdir -p "$LOGDIR"
LOG=$LOGDIR/governed-install.log
exec > >(tee -a "$LOG") 2>&1
echo "=== GOVERNED INSTALL START $(date -u +%FT%TZ) ==="
export DEBIAN_FRONTEND=noninteractive
REPO_ROOT="${REPO_ROOT:-/opt/repo}"
rm -f "$LOGDIR/governed-install.done" "$LOGDIR/governed-install.failed"

echo "--- A: apt base + Elmer PPA + python3.12 ---"
timeout 600 apt-get update -qq 2>&1 | tail -1
timeout 900 apt-get install -y -qq python3-pip gmsh xvfb libgl1 libglu1-mesa \
  software-properties-common libopenblas0 curl bzip2 ca-certificates patch \
  build-essential pkg-config 2>&1 | tail -1
add-apt-repository -y ppa:deadsnakes/ppa 2>&1 | tail -1
add-apt-repository -y ppa:elmer-csc-ubuntu/elmer-csc-ppa 2>&1 | tail -1
timeout 600 apt-get update -qq 2>&1 | tail -1
timeout 900 apt-get install -y -qq python3.12 python3.12-venv elmerfem-csc 2>&1 | tail -1
echo "A gmsh: $(gmsh --version 2>&1 | head -1)"
echo "A elmer: $(ElmerSolver --version 2>&1 | head -1)"
echo "A py312: $(python3.12 --version 2>&1)"

echo "--- B: micromamba openfoam + precice + code_aster (separate prefixes) ---"
if [ ! -x /usr/local/bin/bin/micromamba ]; then
  curl -sL https://micro.mamba.pm/api/micromamba/linux-64/latest | tar -xj -C /usr/local/bin bin/micromamba
fi
MM=/usr/local/bin/bin/micromamba
timeout 2400 $MM create -y -p /opt/solvers -c conda-forge openfoam 2>&1 | tail -3
echo "B openfoam rc=$?"
timeout 2400 $MM create -y -p /opt/precice -c conda-forge precice pyprecice python=3.11 2>&1 | tail -3
echo "B precice rc=$?"
timeout 1500 $MM create -y -p /opt/aster -c conda-forge code-aster 2>&1 | tail -3
echo "B code_aster rc=$?"

echo "--- C: pinned repo python env via uv (services/api/uv.lock) ---"
curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin sh 2>&1 | tail -2
export PATH=/usr/local/bin:$PATH
uv --version 2>&1 | tail -1
if [ -d "$REPO_ROOT/services/api" ]; then
  ( cd "$REPO_ROOT" && UV_PROJECT_ENVIRONMENT=/opt/py312 timeout 2400 uv sync --frozen --directory services/api ) 2>&1 | tail -5
  echo "C uv sync rc=$?"
else
  echo "C FAIL repo checkout missing at $REPO_ROOT"
fi
if [ ! -x /opt/py312/bin/python ]; then
  echo "C fallback: venv creation (uv sync unavailable)"
  python3.12 -m venv /opt/py312
fi
/opt/py312/bin/python --version 2>&1 | tail -1

echo "--- D: pyprecice into the repo interpreter (best-effort, bounded) ---"
if [ -x /opt/precice/bin/python ]; then
  export PRECICE_ROOT=/opt/precice
  export LD_LIBRARY_PATH=/opt/precice/lib:${LD_LIBRARY_PATH:-}
  export CPATH=/opt/precice/include:${CPATH:-}
  export LIBRARY_PATH=/opt/precice/lib:${LIBRARY_PATH:-}
  timeout 900 /opt/py312/bin/python -m pip install -q pyprecice 2>&1 | tail -3
  echo "D py312 pyprecice pip rc=$?"
fi

echo "--- E: version capture (repo interpreter; capability probes must agree) ---"
PATH=/opt/solvers/bin:/opt/aster/bin:/opt/precice/bin:/opt/py312/bin:$PATH
/opt/py312/bin/python - <<'PY' > "$LOGDIR/versions.json"
import json, shutil, subprocess, sys

def probe(cmd):
    exe = shutil.which(cmd[0])
    if exe is None:
        return {"present": False}
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        text = (out.stdout or out.stderr).strip().splitlines()
        return {"present": True, "path": exe, "version": text[0][:200] if text else ""}
    except Exception as exc:  # noqa: BLE001
        return {"present": True, "path": exe, "detail": f"{type(exc).__name__}:{exc}"}

report = {
    "python": {"present": True, "path": sys.executable, "version": sys.version.split()[0]},
    "gmsh": probe(["gmsh", "--version"]),
    "ElmerSolver": probe(["ElmerSolver", "--version"]),
    "simpleFoam": probe(["simpleFoam", "-help"]),
    "pimpleFoam": probe(["pimpleFoam", "-help"]),
    "precice-tools": probe(["precice-tools", "version"]),
    "as_run": probe(["as_run", "--version"]),
    "run_aster": probe(["run_aster", "--version"]),
}
for name in ("numpy", "scipy", "ross", "pybamm", "cantera", "openmdao", "gmsh", "fastapi", "cadquery", "meshio"):
    try:
        import importlib.metadata as md
        report[f"py:{name}"] = {"present": True, "version": md.version(name)}
    except Exception as exc:  # noqa: BLE001
        report[f"py:{name}"] = {"present": False, "detail": str(exc)}
print(json.dumps(report, indent=2, sort_keys=True))
PY
cat "$LOGDIR/versions.json"

echo "--- F: precice binding interpreter attempts ---"
/opt/py312/bin/python - "$REPO_ROOT" <<'PY' > "$LOGDIR/precice-interpreters.json"
import json, sys
from pathlib import Path

repo = Path(sys.argv[1])
sys.path.insert(0, str(repo))
sys.path.insert(0, str(repo / "solvers"))
try:
    from precice.interpreter import find_precice_interpreter
    interp, attempts = find_precice_interpreter()
    print(json.dumps({"interpreter": interp, "attempts": attempts}, indent=2, sort_keys=True))
except Exception as exc:  # noqa: BLE001
    print(json.dumps({"interpreter": None, "attempts": [f"discovery failed:{type(exc).__name__}:{exc}"]}, indent=2))
PY
cat "$LOGDIR/precice-interpreters.json"

echo "--- G: openfoam env smoke ---"
PATH=/opt/solvers/bin:$PATH bash -c 'source /opt/solvers/etc/profile.d/conda.sh 2>/dev/null; simpleFoam -help 2>&1 | head -2; echo WM=${WM_PROJECT_VERSION:-none}'

echo "--- H: readiness preflight (requested participants) ---"
PATH=/opt/solvers/bin:/opt/aster/bin:/opt/precice/bin:/opt/py312/bin:$PATH \
LD_LIBRARY_PATH=/opt/solvers/lib:/opt/aster/lib:/opt/precice/lib:${LD_LIBRARY_PATH:-} \
/opt/py312/bin/python - "$LOGDIR" "$REPO_ROOT" <<'PY'
import json, sys
from pathlib import Path

logdir = Path(sys.argv[1])
repo = Path(sys.argv[2])
sys.path.insert(0, str(repo))
sys.path.insert(0, str(repo / "solvers"))
packages = repo / "packages"
if packages.is_dir():
    for child in packages.iterdir():
        if child.is_dir():
            sys.path.insert(0, str(child))

required = {
    "incompressible-steady-flow",
    "rotating-flow-mrf",
    "structural-static",
    "structural-modal",
    "thermal-conduction",
    "native-coupled-window",
}
try:
    from participants.capabilities import probe_all
    probes = {p.participant_id: p for p in probe_all()}
    report = {
        pid: {
            "state": probes[pid].state,
            "solver_id": probes[pid].solver_id,
            "executable": probes[pid].executable,
            "version": probes[pid].version,
            "detail": probes[pid].detail,
        }
        for pid in sorted(probes)
    }
    (logdir / "capabilities.json").write_text(json.dumps(report, indent=2, sort_keys=True))
    missing = sorted(pid for pid in required if probes.get(pid) is None or probes[pid].state != "ready")
    if missing:
        (logdir / "governed-install.failed").write_text("missing:" + ",".join(missing) + "\n")
        print("READINESS FAIL missing:", ",".join(missing))
    else:
        (logdir / "governed-install.done").write_text("ready\n")
        print("READINESS OK")
except Exception as exc:  # noqa: BLE001
    (logdir / "governed-install.failed").write_text(f"preflight error:{type(exc).__name__}:{exc}\n")
    print("READINESS ERROR", type(exc).__name__, exc)
PY

echo "=== GOVERNED INSTALL DONE $(date -u +%FT%TZ) ==="
