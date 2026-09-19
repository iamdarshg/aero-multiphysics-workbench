#!/usr/bin/env bash
# Allowlisted worker image entrypoint.
#
# There is deliberately no generic "exec" surface: only these subcommands are
# accepted, so a compromised or misconfigured caller cannot turn the image into
# an arbitrary command runner. Nothing here installs packages or reads secrets.
set -euo pipefail

MANIFEST_DEFAULT=/opt/worker/capability-manifest.json
EMIT=/opt/worker/emit-capability-manifest.sh

resolve_python() {
  if [ -x "${WORKER_PYTHON:-/opt/participants/.venv/bin/python}" ]; then
    printf '%s' "$WORKER_PYTHON"
    return 0
  fi
  command -v python3.12 || command -v python3
}

usage() {
  echo "Usage: worker-entrypoint <capabilities|verify|smoke|version> [args]"
  echo "  capabilities [OUT]    emit the capability manifest (default ${MANIFEST_DEFAULT})"
  echo "  verify [MANIFEST]     re-probe and fail closed if the manifest drifted"
  echo "  smoke [MANIFEST]      run bounded native smoke via AERO_REPO_ROOT (default /opt/repo)"
  echo "  version               print image identity"
}

cmd="${1:-capabilities}"
shift || true

case "$cmd" in
  capabilities)
    exec "$EMIT" "${1:-$MANIFEST_DEFAULT}"
    ;;
  verify)
    manifest="${1:-$MANIFEST_DEFAULT}"
    [ -f "$manifest" ] || { echo "verify: manifest missing: $manifest" >&2; exit 1; }
    fresh="$(mktemp)"
    "$EMIT" "$fresh" >/dev/null
    # Structural agreement only: exact version strings for the same environment.
    "$(resolve_python)" - "$manifest" "$fresh" <<'PY'
import json
import sys

recorded = json.load(open(sys.argv[1], encoding="utf-8"))
fresh = json.load(open(sys.argv[2], encoding="utf-8"))
r = {e["id"]: (e["state"], e["kind"], e["version"]) for e in recorded["solvers"]}
f = {e["id"]: (e["state"], e["kind"], e["version"]) for e in fresh["solvers"]}
if set(r) != set(f):
    print(f"verify: solver set drift recorded={sorted(r)} fresh={sorted(f)}", file=sys.stderr)
    raise SystemExit(1)
drift = {k: (r[k], f[k]) for k in r if r[k] != f[k]}
if drift:
    print(f"verify: capability drift {drift}", file=sys.stderr)
    raise SystemExit(1)
print("verify: ok")
PY
    ;;
  smoke)
    manifest="${1:-$MANIFEST_DEFAULT}"
    repo="${AERO_REPO_ROOT:-/opt/repo}"
    script="$repo/scripts/gcp/worker-smoke.py"
    [ -f "$script" ] || { echo "smoke: governed smoke script missing: $script" >&2; exit 1; }
    exec "$(resolve_python)" "$script" --manifest "$manifest"
    ;;
  version)
    echo "image=${WORKER_IMAGE:-aero-worker:local} role=${WORKER_ROLE:-native-solvers} digest=${WORKER_IMAGE_DIGEST:-PENDING}"
    ;;
  -h|--help|help)
    usage
    ;;
  *)
    echo "worker-entrypoint: unknown subcommand: $cmd" >&2
    usage >&2
    exit 2
    ;;
esac
