#!/bin/bash
# Bounded, no-SSH native verification worker for the approved final check.
set +u
set -o pipefail
LOGDIR=/var/log/proofs
mkdir -p "$LOGDIR"
exec > >(tee -a "$LOGDIR/final-verification.log") 2>&1
echo "=== FINAL VERIFICATION START $(date -u +%FT%TZ) ==="
export DEBIAN_FRONTEND=noninteractive
FINAL_RC=0

timeout 300 apt-get update -qq
timeout 300 apt-get install -y -qq git ca-certificates
rm -rf /opt/repo
git clone --depth 1 https://github.com/iamdarshg/aero-multiphysics-workbench.git /opt/repo
cd /opt/repo

# Use the prior governed bootstrap: it installs the frozen services/api Python
# environment, separate native prefixes, and records capability versions.
timeout 5400 bash scripts/gcp/governed-worker-startup.sh || FINAL_RC=$?
echo "INSTALL_RC=$FINAL_RC"

# Produce the governed Code_Aster and preCICE receipts before the promotion
# benchmark consumes them.  Keeping every receipt in one directory prevents
# the final gate from silently falling back to hard-coded availability.
export PATH=/opt/solvers/bin:/opt/aster/bin:/opt/precice/bin:/opt/py312/bin:$PATH
export LD_LIBRARY_PATH=/opt/solvers/lib:/opt/aster/lib:/opt/precice/lib:${LD_LIBRARY_PATH:-}
export PYTHONPATH="/opt/repo:/opt/repo/solvers"
for directory in /opt/repo/packages/*; do
  [ -d "$directory" ] && PYTHONPATH="$PYTHONPATH:$directory"
done
export PYTHONPATH
timeout 1800 /opt/py312/bin/python scripts/gcp/governed-blocker-run.py \
  --out /var/log/proofs/receipts --issues 07static,07modal,11 \
  || FINAL_RC=$?
echo "GOVERNED_NATIVE_RC=$FINAL_RC"

timeout 2400 bash scripts/gcp/run-benchmarks.sh || FINAL_RC=$?
echo "BENCHMARK_RC=$FINAL_RC"

cd "$LOGDIR"
tar czf final-verification-evidence.tar.gz receipts 2>/dev/null || true
echo "=== FINAL VERIFICATION DONE $(date -u +%FT%TZ) ==="
if [ "$FINAL_RC" -eq 0 ]; then
  touch "$LOGDIR/final-verification.done"
else
  touch "$LOGDIR/final-verification.failed"
fi
exit "$FINAL_RC"
