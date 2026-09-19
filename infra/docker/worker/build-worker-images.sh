#!/usr/bin/env bash
# Build the pinned worker images with BuildKit layer caching, SBOM, and
# provenance, then record the immutable image digests.
#
# Requires a Docker/BuildKit host (not available on the issue #43 workstation).
# Run from the repository root:
#
#   scripts/gcp/build-worker-images.sh --registry REGISTRY/REPO [--push]
#
# Caching: --cache-from/--cache-to reuse the solver layers. A participant-only
# change lives below the solver layers, so it does not rebuild them.
set -euo pipefail

REGISTRY=""
PUSH=0
CACHE_DIR="${CACHE_DIR:-/var/lib/aero-buildkit-cache}"
PLATFORM="${PLATFORM:-linux/amd64}"
TAG="${TAG:-2026.09}"
OUT_PINS="${OUT_PINS:-infra/docker/worker/pins.resolved.json}"

while [ $# -gt 0 ]; do
  case "$1" in
    --registry) REGISTRY="${2:?}"; shift 2 ;;
    --push) PUSH=1; shift ;;
    --tag) TAG="${2:?}"; shift 2 ;;
    *) echo "usage: $0 --registry REGISTRY/REPO [--push] [--tag TAG]"; exit 2 ;;
  esac
done
[ -n "$REGISTRY" ] || { echo "--registry is required"; exit 2; }

PY_IMAGE="$REGISTRY/worker-python:$TAG"
NATIVE_IMAGE="$REGISTRY/worker-native:$TAG"
PUSH_FLAG="--load"
[ "$PUSH" = 1 ] && PUSH_FLAG="--push"

build() {
  local dockerfile="$1" tag="$2"
  docker buildx build --platform "$PLATFORM" \
    -f "$dockerfile" \
    --tag "$tag" \
    --provenance=true --sbom=true \
    --cache-from "type=local,src=${CACHE_DIR}" \
    --cache-to "type=local,dest=${CACHE_DIR},mode=max" \
    "$PUSH_FLAG" .
}

echo "--- building $PY_IMAGE"
build infra/docker/worker/participants-python.Dockerfile "$PY_IMAGE"
echo "--- building $NATIVE_IMAGE"
build infra/docker/worker/native-solvers.Dockerfile "$NATIVE_IMAGE"

resolve_digest() {
  docker image inspect --format '{{index .RepoDigests 0}}' "$1" | sed 's/.*@//'
}

PY_DIGEST="$(resolve_digest "$PY_IMAGE")"
NATIVE_DIGEST="$(resolve_digest "$NATIVE_IMAGE")"
echo "worker-python digest=$PY_DIGEST"
echo "worker-native digest=$NATIVE_DIGEST"

python3 - "$OUT_PINS" "$PY_DIGEST" "$NATIVE_DIGEST" "$PY_IMAGE" "$NATIVE_IMAGE" <<'PY'
import json, sys
out, py_digest, native_digest, py_image, native_image = sys.argv[1:6]
json.dump(
    {
        "schemaVersion": 1,
        "images": {
            "participants-python": {"ref": py_image, "digest": py_digest},
            "native-solvers": {"ref": native_image, "digest": native_digest},
        },
    },
    open(out, "w", encoding="utf-8"),
    indent=2,
    sort_keys=True,
)
print(f"wrote {out}")
PY
