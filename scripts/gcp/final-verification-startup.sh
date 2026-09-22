#!/bin/bash
# Bounded, no-SSH native verification worker for the approved final check.
set +u
set -o pipefail
LOGDIR=/var/log/proofs
mkdir -p "$LOGDIR"
exec > >(tee -a "$LOGDIR/final-verification.log") 2>&1
echo "=== FINAL VERIFICATION START $(date -u +%FT%TZ) ==="
export DEBIAN_FRONTEND=noninteractive

timeout 300 apt-get update -qq
timeout 300 apt-get install -y -qq git ca-certificates
rm -rf /opt/repo
git clone --depth 1 https://github.com/iamdarshg/aero-multiphysics-workbench.git /opt/repo
cd /opt/repo

# Use the prior governed bootstrap: it installs the frozen services/api Python
# environment, separate native prefixes, and records capability versions.
timeout 5400 bash scripts/gcp/governed-worker-startup.sh || echo "INSTALL_RC=$?"
timeout 2400 bash scripts/gcp/run-benchmarks.sh || echo "BENCHMARK_RC=$?"

# Run the repository's actual governed Code_Aster static/modal participant,
# not only the capability gate. This produces native receipts when run_aster
# completes and preserves a fail-closed diagnostic otherwise.
export PATH=/opt/solvers/bin:/opt/aster/bin:/opt/precice/bin:/opt/py312/bin:$PATH
export LD_LIBRARY_PATH=/opt/solvers/lib:/opt/aster/lib:/opt/precice/lib:${LD_LIBRARY_PATH:-}
export PYTHONPATH="/opt/repo:/opt/repo/solvers"
for directory in /opt/repo/packages/*; do
  [ -d "$directory" ] && PYTHONPATH="$PYTHONPATH:$directory"
done
export PYTHONPATH
timeout 1800 /opt/py312/bin/python scripts/gcp/governed-blocker-run.py \
  --out /var/log/proofs/governed-blockers --issues 07static,07modal \
  || echo "CODE_ASTER_RC=$?"

cd "$LOGDIR"
tar czf final-verification-evidence.tar.gz receipts governed-blockers 2>/dev/null || true
echo "=== FINAL VERIFICATION DONE $(date -u +%FT%TZ) ==="
touch "$LOGDIR/final-verification.done"
