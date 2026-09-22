#!/bin/bash
set +u
LOGDIR=/var/log/proofs
mkdir -p "$LOGDIR"
exec > >(tee -a "$LOGDIR/code-aster-native.log") 2>&1
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq git ca-certificates
rm -rf /opt/repo
git clone --depth 1 https://github.com/iamdarshg/aero-multiphysics-workbench.git /opt/repo
cd /opt/repo
bash scripts/gcp/governed-worker-startup.sh
export PATH=/opt/solvers/bin:/opt/aster/bin:/opt/precice/bin:/opt/py312/bin:$PATH
export LD_LIBRARY_PATH=/opt/solvers/lib:/opt/aster/lib:/opt/precice/lib:${LD_LIBRARY_PATH:-}
export PYTHONPATH="/opt/repo:/opt/repo/solvers:/opt/repo/services/api"
for directory in /opt/repo/packages/*; do
  [ -d "$directory" ] && PYTHONPATH="$PYTHONPATH:$directory"
done
export PYTHONPATH
timeout 1200 /opt/py312/bin/python scripts/gcp/governed-blocker-run.py \
  --out "$LOGDIR/governed-blockers" --issues 07static,07modal || echo "ASTER_RC=$?"
test -d "$LOGDIR/governed-blockers"
touch "$LOGDIR/code-aster-native.done"
