#!/bin/bash
set +u
LOGDIR=/var/log/proofs
mkdir -p "$LOGDIR"
exec > >(tee -a "$LOGDIR/ross-native.log") 2>&1
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq git ca-certificates
rm -rf /opt/repo
git clone --depth 1 https://github.com/iamdarshg/aero-multiphysics-workbench.git /opt/repo
cd /opt/repo
bash scripts/gcp/governed-worker-startup.sh
export PATH=/opt/py312/bin:$PATH
export PYTHONPATH="/opt/repo:/opt/repo/solvers"
for directory in /opt/repo/packages/*; do
  [ -d "$directory" ] && PYTHONPATH="$PYTHONPATH:$directory"
done
export PYTHONPATH
mkdir -p "$LOGDIR/receipts"
timeout 900 /opt/py312/bin/python scripts/gcp/bench_ross.py > "$LOGDIR/receipts/ross-current.json" || echo "ROSS_RC=$?"
test -s "$LOGDIR/receipts/ross-current.json"
touch "$LOGDIR/ross-native.done"
