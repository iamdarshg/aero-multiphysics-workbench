#!/bin/bash
# Run the bounded native correctness benchmarks on the solver-correction VM.
# Writes machine-readable receipts to /var/log/proofs/receipts and a tarball.
set +u
LOGDIR=/var/log/proofs
RECEIPTS=$LOGDIR/receipts
mkdir -p "$RECEIPTS"
LOG=$LOGDIR/benchmarks.log
exec > >(tee -a "$LOG") 2>&1
echo "=== BENCHMARKS START $(date -u +%FT%TZ) ==="
REPO=/opt/repo
export PYTHONPATH="$REPO:$REPO/solvers"
for d in "$REPO"/packages/*; do
  [ -d "$d" ] && PYTHONPATH="$PYTHONPATH:$d"
done
export PYTHONPATH
export REPO_ROOT="$REPO"
export RECEIPTS="$RECEIPTS"
PY=/opt/py312/bin/python

# --- native solver environment ---
export PATH=/opt/solvers/bin:/opt/aster/bin:/opt/precice/bin:/opt/py312/bin:$PATH
export LD_LIBRARY_PATH=/opt/solvers/lib:/opt/aster/lib:/opt/precice/lib:${LD_LIBRARY_PATH:-}
source /opt/solvers/etc/bashrc 2>/dev/null || true
echo "WM_PROJECT_VERSION=${WM_PROJECT_VERSION:-none} simpleFoam=$(command -v simpleFoam)"
echo "gmsh=$(command -v gmsh) gmshToFoam=$(command -v gmshToFoam)"

echo "--- issue37 openfoam ---"
timeout 1500 "$PY" "$REPO/scripts/gcp/bench_openfoam.py" || echo "OF bench rc=$?"

echo "--- issue39 elmer ---"
timeout 900 "$PY" "$REPO/scripts/gcp/bench_elmer.py" || echo "Elmer bench rc=$?"

echo "--- issue38 ross (governed run script) ---"
timeout 900 "$PY" "$REPO/scripts/gcp/bench_ross.py" || echo "ROSS bench rc=$?"

echo "--- issue39 electrical closure ---"
timeout 600 "$PY" "$REPO/scripts/gcp/bench_electrical.py" || echo "Elec bench rc=$?"

echo "--- issue40 precice ---"
PRECICE_PY=/opt/precice/bin/python
if ! command -v "$PRECICE_PY" >/dev/null; then PRECICE_PY=$PY; fi
# Clear PYTHONPATH so the native binding is imported, not the repo's solvers/precice stub.
( cd /tmp && env -u PYTHONPATH timeout 900 "$PRECICE_PY" "$REPO/scripts/gcp/bench_precice.py" ) || echo "preCICE bench rc=$?"

echo "--- issue41 promotion gate ---"
GATE_RC=0
timeout 300 "$PY" "$REPO/scripts/gcp/bench_promotion.py" || GATE_RC=$?
echo "Gate bench rc=$GATE_RC"

echo "--- collect evidence ---"
cd "$LOGDIR"
tar czf "$LOGDIR/evidence.tar.gz" receipts 2>/dev/null
python3 - <<'PY'
import json, glob, os
for f in sorted(glob.glob('/var/log/proofs/receipts/*.json')):
    try:
        d = json.load(open(f))
        print(os.path.basename(f), '=>', d.get('status', d.get('benchmark', '?')))
    except Exception as e:
        print(os.path.basename(f), 'PARSE_ERR', e)
PY
echo "=== BENCHMARKS DONE $(date -u +%FT%TZ) ==="
if [ "$GATE_RC" -eq 0 ]; then
  touch "$LOGDIR/benchmarks.done"
else
  touch "$LOGDIR/benchmarks.failed"
fi
exit "$GATE_RC"
