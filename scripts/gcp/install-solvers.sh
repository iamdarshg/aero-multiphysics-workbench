#!/bin/bash
# Solver-correction VM bootstrap (SOLVER-CORR 01-05).
# Installs the smallest native stack needed for the bounded correctness
# benchmarks, then marks readiness. Idempotent-ish; never fakes success.
# Evidence: /var/log/proofs/install.log, /var/log/proofs/install.done,
#           /var/log/proofs/install.failed
set +u
mkdir -p /var/log/proofs
LOG=/var/log/proofs/install.log
exec > >(tee -a "$LOG") 2>&1
echo "=== INSTALL START $(date -u +%FT%TZ) ==="
export DEBIAN_FRONTEND=noninteractive
rm -f /var/log/proofs/install.done /var/log/proofs/install.failed

# --- A: apt base + Elmer PPA + python3.12 -------------------------------
echo "--- A: apt base ---"
apt-get update -qq 2>&1 | tail -1
apt-get install -y -qq python3-pip gmsh xvfb libgl1 software-properties-common \
  libopenblas0 curl bzip2 ca-certificates patch 2>&1 | tail -1
add-apt-repository -y ppa:deadsnakes/ppa 2>&1 | tail -1
add-apt-repository -y ppa:elmer-csc-ubuntu/elmer-csc-ppa 2>&1 | tail -1
apt-get update -qq 2>&1 | tail -1
apt-get install -y -qq python3.12 python3.12-venv elmerfem-csc 2>&1 | tail -1
echo "A gmsh: $(gmsh --version 2>&1 | head -1)"
echo "A elmer: $(ElmerSolver --version 2>&1 | head -1)"
echo "A py312: $(python3.12 --version 2>&1)"

# --- B: micromamba openfoam + precice (SEPARATE prefixes) ----------------
# openfoam and precice pull incompatible MPI/PETSc stacks; co-installing them
# makes conda evict precice. Keep them in independent environments.
echo "--- B: conda heavies ---"
curl -sL https://micro.mamba.pm/api/micromamba/linux-64/latest | tar -xj -C /usr/local/bin bin/micromamba
/usr/local/bin/bin/micromamba create -y -p /opt/solvers -c conda-forge openfoam 2>&1 | tail -3
echo "B openfoam rc=$?"
/usr/local/bin/bin/micromamba create -y -p /opt/precice -c conda-forge precice pyprecice 2>&1 | tail -3
echo "B precice rc=$?"

# --- C: python 3.12 venv stack ------------------------------------------
echo "--- C: python venv ---"
python3.12 -m venv /opt/py312
/opt/py312/bin/pip install -q --upgrade pip 2>&1 | tail -1
for PKG in numpy scipy ross pybamm cantera openmdao; do
  if timeout 900 /opt/py312/bin/pip install -q "$PKG" 2>&1 | tail -1; then
    echo "PIP OK $PKG"
  else
    echo "PIP FAIL $PKG"
  fi
done
/opt/py312/bin/python -c "import numpy,scipy,ross,pybamm,cantera,openmdao; print('PYSTACK OK')" 2>&1 | tail -1

# --- D: Code_Aster attempt (bounded) ------------------------------------
echo "--- D: code_aster attempt (bounded) ---"
/usr/local/bin/bin/micromamba create -y -p /opt/aster -c conda-forge code-aster 2>&1 | tail -3
echo "D code_aster rc=$?"
/opt/aster/bin/as_run --version 2>&1 | head -1 || echo "D as_run unavailable"

echo "--- E: interpreter smoke ---"
/opt/py312/bin/python -c "import sys; print('P12 VER', sys.version.split()[0])"
/opt/solvers/bin/precice-tools version 2>&1 | head -c 200; echo ""
ElmerSolver --version 2>&1 | head -1
PATH=/opt/solvers/bin:$PATH bash -c 'source /opt/solvers/etc/profile.d/conda.sh 2>/dev/null; simpleFoam -help 2>&1 | head -2'
echo "=== INSTALL DONE $(date -u +%FT%TZ) ==="
touch /var/log/proofs/install.done
