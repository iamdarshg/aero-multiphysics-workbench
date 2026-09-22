#!/bin/bash
set +u
LOGDIR=/var/log/proofs
mkdir -p "$LOGDIR"
exec > >(tee -a "$LOGDIR/openvsp-native.log") 2>&1
export DEBIAN_FRONTEND=noninteractive

apt-get update -qq
apt-get install -y -qq ca-certificates curl desktop-file-utils libglu1-mesa libgl1 \
  python3.12 python3.12-venv xvfb git
deb=/tmp/OpenVSP-3.52.1-Ubuntu-24.04_amd64.deb
curl -fL "https://openvsp.org/download.php?file=zips/current/linux/OpenVSP-3.52.1-Ubuntu-24.04_amd64.deb" -o "$deb"
apt-get install -y -qq "$deb"

rm -rf /opt/repo
git clone --depth 1 https://github.com/iamdarshg/aero-multiphysics-workbench.git /opt/repo
cd /opt/repo
curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin sh
UV_PROJECT_ENVIRONMENT=/opt/py312 uv sync --frozen --directory services/api
export PYTHONPATH="/opt/repo:/opt/repo/packages/airframe:/opt/repo/packages/core:/opt/repo/packages/geometry:/opt/repo/packages/semantics:/opt/repo/packages/fluid_properties:/opt/repo/solvers"
timeout 900 xvfb-run -a /opt/py312/bin/python scripts/gcp/run-vspaero-native.py \
  > "$LOGDIR/vspaero-native-result.json"
test -s "$LOGDIR/vspaero-native-result.json"
touch "$LOGDIR/openvsp-native.done"
