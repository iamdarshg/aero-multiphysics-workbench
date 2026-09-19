#!/bin/bash
# Launch the governed evidence driver with the native solver environments on
# PATH. OpenFOAM binaries need the conda env's WM_PROJECT_DIR/LD_LIBRARY_PATH,
# so the environment is established here and inherited by the governed runner.
set +u
export PATH=/opt/solvers/bin:/opt/aster/bin:/opt/precice/bin:/opt/py312/bin:$PATH
export LD_LIBRARY_PATH=/opt/solvers/lib:/opt/aster/lib:${LD_LIBRARY_PATH:-}
source /opt/solvers/etc/bashrc 2>/dev/null || true
export AEROWORKBENCH_JOB_ROOT="${AEROWORKBENCH_JOB_ROOT:-$HOME/aero-jobs}"
OUT="$1"
shift
mkdir -p "$OUT"
echo "WM_PROJECT_VERSION=${WM_PROJECT_VERSION:-none} FOAM_ETC=${FOAM_ETC:-none}"
echo "PY312=$(/opt/py312/bin/python --version 2>&1)"
/opt/py312/bin/python /tmp/governed-run.py --out "$OUT" "$@" 2>&1 | tee "$OUT/driver.log"
