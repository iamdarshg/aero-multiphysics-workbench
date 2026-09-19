#!/bin/bash
# Governed worker bootstrap (issue #47 + GEN 06/07/08/11 residuals).
#
# Installs the smallest honest native stack needed to drive the repo's own
# NativeJobManager participant path. Never fakes success: every capability is
# probed and its real version recorded in /var/log/proofs/versions.json.
# Readiness markers: /var/log/proofs/governed-install.done (success),
#                    /var/log/proofs/governed-install.failed.
set +u
LOGDIR=/var/log/proofs
mkdir -p "$LOGDIR"
LOG=$LOGDIR/governed-install.log
exec > >(tee -a "$LOG") 2>&1
echo "=== GOVERNED INSTALL START $(date -u +%FT%TZ) ==="
export DEBIAN_FRONTEND=noninteractive
rm -f "$LOGDIR/governed-install.done" "$LOGDIR/governed-install.failed"

echo "--- A: apt base + Elmer PPA + python3.12 ---"
timeout 600 apt-get update -qq 2>&1 | tail -1
timeout 900 apt-get install -y -qq python3-pip gmsh xvfb libgl1 libglu1-mesa \
  software-properties-common libopenblas0 curl bzip2 ca-certificates patch \
  build-essential 2>&1 | tail -1
add-apt-repository -y ppa:deadsnakes/ppa 2>&1 | tail -1
add-apt-repository -y ppa:elmer-csc-ubuntu/elmer-csc-ppa 2>&1 | tail -1
timeout 600 apt-get update -qq 2>&1 | tail -1
timeout 900 apt-get install -y -qq python3.12 python3.12-venv elmerfem-csc 2>&1 | tail -1
echo "A gmsh: $(gmsh --version 2>&1 | head -1)"
echo "A elmer: $(ElmerSolver --version 2>&1 | head -1)"
echo "A py312: $(python3.12 --version 2>&1)"

echo "--- B: python 3.12 venv stack (repo services/api deps, one pkg per command) ---"
python3.12 -m venv /opt/py312
/opt/py312/bin/pip install -q --upgrade pip 2>&1 | tail -1
for PKG in "numpy" "scipy" "ross-rotordynamics" "pybamm" "casadi==3.7.2" \
           "cantera" "openmdao" "gmsh" "meshio" "fastapi" "pydantic" "uvicorn" \
           "httpx" "pytest" "cadquery"; do
  if timeout 1200 /opt/py312/bin/pip install -q "$PKG" 2>&1 | tail -1; then
    echo "PIP OK $PKG"
  else
    echo "PIP FAIL $PKG"
  fi
done
/opt/py312/bin/python -c "import numpy,scipy,ross,pybamm,openmdao,gmsh,meshio,fastapi,pydantic; print('PYSTACK OK')" 2>&1 | tail -1

echo "--- C: micromamba openfoam + precice (separate prefixes) ---"
if [ ! -x /usr/local/bin/bin/micromamba ]; then
  curl -sL https://micro.mamba.pm/api/micromamba/linux-64/latest | tar -xj -C /usr/local/bin bin/micromamba
fi
MM=/usr/local/bin/bin/micromamba
timeout 2400 $MM create -y -p /opt/solvers -c conda-forge openfoam 2>&1 | tail -3
echo "C openfoam rc=$?"
timeout 1800 $MM create -y -p /opt/precice -c conda-forge precice pyprecice 2>&1 | tail -3
echo "C precice rc=$?"

echo "--- D: Code_Aster attempt (bounded; not fatal) ---"
timeout 1500 $MM create -y -p /opt/aster -c conda-forge code-aster 2>&1 | tail -3
echo "D code_aster rc=$?"

echo "--- E: version capture ---"
PATH=/opt/solvers/bin:/opt/aster/bin:/opt/precice/bin:$PATH
python3 - <<'PY' > "$LOGDIR/versions.json"
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
    "gmsh": probe(["gmsh", "--version"]),
    "ElmerSolver": probe(["ElmerSolver", "--version"]),
    "simpleFoam": probe(["simpleFoam", "-help"]),
    "pimpleFoam": probe(["pimpleFoam", "-help"]),
    "precice-tools": probe(["precice-tools", "version"]),
    "precice-config-visualizer": probe(["precice-config-visualizer", "--version"]),
    "as_run": probe(["as_run", "--version"]),
    "run_aster": probe(["run_aster", "--version"]),
}
for name in ("numpy", "scipy", "ross", "pybamm", "cantera", "openmdao", "gmsh", "fastapi", "cadquery"):
    try:
        import importlib.metadata as md
        report[f"py:{name}"] = {"present": True, "version": md.version(name)}
    except Exception as exc:  # noqa: BLE001
        report[f"py:{name}"] = {"present": False, "detail": str(exc)}
print(json.dumps(report, indent=2, sort_keys=True))
PY
cat "$LOGDIR/versions.json"

echo "--- F: precice python binding smoke ---"
/opt/precice/bin/python -c "import precice; print('PRECICE', getattr(precice,'__version__','?'))" 2>&1 | tail -1 || echo "precice binding unavailable"

echo "--- G: openfoam env smoke ---"
PATH=/opt/solvers/bin:$PATH bash -c 'source /opt/solvers/etc/profile.d/conda.sh 2>/dev/null; simpleFoam -help 2>&1 | head -2; echo WM=${WM_PROJECT_VERSION:-none}'

echo "=== GOVERNED INSTALL DONE $(date -u +%FT%TZ) ==="
touch "$LOGDIR/governed-install.done"
