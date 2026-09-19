#!/usr/bin/env bash
# Emit the worker capability manifest (build time and first start).
#
# It only probes the already-installed environment: it never installs a
# solver and never mutates the filesystem outside the requested output path.
set -euo pipefail

OUT="${1:-/opt/worker/capability-manifest.json}"

PY="${WORKER_PYTHON:-/opt/participants/.venv/bin/python}"
if [ ! -x "$PY" ]; then
  PY="$(command -v python3.12 || command -v python3)"
fi

# Solver prefixes (absent in the python-participants image: the probes then
# report unavailable rather than substituting anything).
export PATH="/opt/solvers/openfoam/bin:/opt/solvers/precice/bin:/opt/solvers/code-aster/bin:/opt/solvers/mesh/bin:${PATH}"
export LD_LIBRARY_PATH="/opt/solvers/openfoam/lib:/opt/solvers/precice/lib:/opt/solvers/code-aster/lib:/opt/solvers/mesh/lib:${LD_LIBRARY_PATH:-}"

# OpenFOAM exports WM_PROJECT_VERSION through its prefix bashrc; source it
# best-effort so the environment matches an interactive native run.
if [ -f /opt/solvers/openfoam/etc/bashrc ]; then
  # shellcheck disable=SC1091
  . /opt/solvers/openfoam/etc/bashrc 2>/dev/null || true
fi

PY_VERSION="$("$PY" -c 'import sys; print(sys.version.split()[0])')"

exec "$PY" /opt/worker/emit_capability_manifest.py \
  --out "$OUT" \
  --image "${WORKER_IMAGE:-aero-worker:local}" \
  --role "${WORKER_ROLE:-native-solvers}" \
  --digest "${WORKER_IMAGE_DIGEST:-PENDING}" \
  --base-ref "${WORKER_BASE_REF:-unknown}" \
  --base-digest "${WORKER_BASE_DIGEST:-sha256:0000000000000000000000000000000000000000000000000000000000000000}" \
  --python "$PY" \
  --python-version "$PY_VERSION"
