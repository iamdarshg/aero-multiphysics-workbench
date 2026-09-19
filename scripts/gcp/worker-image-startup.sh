#!/bin/bash
# Pinned worker-image startup for a GCP solver VM (issue #43).
#
# Replaces per-boot solver installation: it pulls a digest-pinned worker image,
# verifies the pulled digest, emits the image capability manifest, and runs the
# bounded governed smoke proof from a commit-pinned repository checkout. It
# never installs OpenFOAM/Elmer/preCICE/Code_Aster at runtime and fails closed
# on any digest/version mismatch.
#
# Required environment (no defaults for anything security-relevant):
#   WORKER_IMAGE_REPO   registry repo, e.g. us-central1-docker.pkg.dev/P/aero-worker-native
#   WORKER_IMAGE_DIGEST optional override; otherwise read from pins.json
#   REPO_COMMIT         immutable commit SHA of iamdarshg/aero-multiphysics-workbench
# Optional:
#   WORKER_IMAGE_NAME   pins key: native-solvers (default) | participants-python
#   REPO_URL, REPO_DIR  checkout source/destination (default /opt/repo)
#   SMOKE_TIMEOUT_S     bound on the smoke container (default 600)
set -euo pipefail

LOGDIR=/var/log/proofs
mkdir -p "$LOGDIR"
exec > >(tee -a "$LOGDIR/worker-image-startup.log") 2>&1
echo "=== worker-image start $(date -u +%FT%TZ) ==="

WORKER_IMAGE_NAME="${WORKER_IMAGE_NAME:-native-solvers}"
WORKER_IMAGE_REPO="${WORKER_IMAGE_REPO:?WORKER_IMAGE_REPO is required}"
REPO_COMMIT="${REPO_COMMIT:?REPO_COMMIT (immutable SHA) is required}"
REPO_URL="${REPO_URL:-https://github.com/iamdarshg/aero-multiphysics-workbench.git}"
REPO_DIR="${REPO_DIR:-/opt/repo}"
SMOKE_TIMEOUT_S="${SMOKE_TIMEOUT_S:-600}"
PINS_FILE="${PINS_FILE:-$(cd "$(dirname "$0")/../.." && pwd)/infra/docker/worker/pins.json}"

command -v docker >/dev/null || { echo "FATAL docker is required"; exit 1; }
[ -f "$PINS_FILE" ] || { echo "FATAL pins missing: $PINS_FILE"; exit 1; }

DIGEST="${WORKER_IMAGE_DIGEST:-$(python3 - "$PINS_FILE" "$WORKER_IMAGE_NAME" <<'PY'
import json, sys
pins = json.load(open(sys.argv[1], encoding="utf-8"))
entry = pins["recorded"][sys.argv[2]]
print(entry.get("digest") or "")
PY
)}"
if [ -z "$DIGEST" ] || [ "$DIGEST" = "PENDING" ]; then
  echo "FATAL image digest is PENDING: build on a Docker/BuildKit host with"
  echo "      scripts/gcp/build-worker-images.sh --push, record recorded.<image>.digest,"
  echo "      or pass WORKER_IMAGE_DIGEST=sha256:<64 hex> explicitly."
  exit 1
fi
case "$DIGEST" in
  sha256:*) ;;
  *) echo "FATAL digest is not an immutable sha256: $DIGEST"; exit 1 ;;
esac

REF="$WORKER_IMAGE_REPO@$DIGEST"
echo "--- pull $REF"
docker pull "$REF"

PULLED="$(docker image inspect --format '{{index .RepoDigests 0}}' "$REF")"
case "$PULLED" in
  *"@$DIGEST") echo "digest verified: $PULLED" ;;
  *) echo "FATAL pulled digest mismatch: got=$PULLED want=$DIGEST"; exit 1 ;;
esac

echo "--- repository checkout @ $REPO_COMMIT"
if [ ! -d "$REPO_DIR/.git" ]; then
  git clone --filter=blob:none --no-checkout "$REPO_URL" "$REPO_DIR"
fi
git -C "$REPO_DIR" fetch --depth 1 origin "$REPO_COMMIT"
git -C "$REPO_DIR" checkout --force "$REPO_COMMIT"
ACTUAL_COMMIT="$(git -C "$REPO_DIR" rev-parse HEAD)"
[ "$ACTUAL_COMMIT" = "$REPO_COMMIT" ] || { echo "FATAL repo commit mismatch: $ACTUAL_COMMIT"; exit 1; }

echo "--- capability manifest (build/first-start receipt)"
docker run --rm \
  -e WORKER_IMAGE_DIGEST="$DIGEST" \
  -v "$LOGDIR":/var/log/proofs \
  "$REF" capabilities /var/log/proofs/capability-manifest.json
python3 -c "import json,sys; d=json.load(open('/var/log/proofs/capability-manifest.json')); print('manifest ready:', ','.join(s['id'] for s in d['solvers'] if s['state']=='ready'))"

echo "--- bounded governed smoke proof"
timeout "$SMOKE_TIMEOUT_S" docker run --rm \
  -e AERO_REPO_ROOT=/opt/repo \
  -e WORKER_IMAGE_DIGEST="$DIGEST" \
  -v "$REPO_DIR":/opt/repo:ro \
  -v "$LOGDIR":/var/log/proofs \
  "$REF" smoke /var/log/proofs/capability-manifest.json

echo "--- receipts"
ls -l "$LOGDIR"/receipts 2>/dev/null || true
touch "$LOGDIR/worker-image.done"
echo "=== worker-image done $(date -u +%FT%TZ) ==="
