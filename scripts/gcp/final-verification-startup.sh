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

# The existing installer and benchmark driver are bounded and fail closed.
timeout 3600 bash scripts/gcp/install-solvers.sh || echo "INSTALL_RC=$?"
timeout 2400 bash scripts/gcp/run-benchmarks.sh || echo "BENCHMARK_RC=$?"

cd "$LOGDIR"
tar czf final-verification-evidence.tar.gz receipts 2>/dev/null || true
echo "=== FINAL VERIFICATION DONE $(date -u +%FT%TZ) ==="
touch "$LOGDIR/final-verification.done"
