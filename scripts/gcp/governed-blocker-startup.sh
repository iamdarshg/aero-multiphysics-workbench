#!/bin/bash
# Governed blocker-run orchestrator for a GCP worker (no SSH required).
#
# Baked into the VM's startup metadata. It clones the public repo at an
# immutable commit, applies the integrator's uncommitted fix patch from GCS,
# runs the worker bootstrap (install), runs the governed blocker driver, and
# uploads every log + evidence artifact back to GCS. A final DONE object is
# written only after all uploads succeed, so the launcher can poll for it and
# delete the VM. A heartbeat object + live log are uploaded at every step so a
# stalled stage is visible without SSH.
#
# Instance metadata:
#   BUCKET        GCS bucket to read the patch from and upload evidence to
#   REPO_COMMIT   immutable commit SHA
# Optional metadata:
#   REPO_URL, REPO_DIR, PATCH_OBJECT, EVIDENCE_DIR, ISSUES
set +u
set -o pipefail
LOGDIR=/var/log/proofs
mkdir -p "$LOGDIR"
LOG="$LOGDIR/blocker-startup.log"
exec > >(tee -a "$LOG") 2>&1
echo "=== BLOCKER RUN START $(date -u +%FT%TZ) ==="

MDS="http://metadata.google.internal/computeMetadata/v1/instance/attributes"
MD="Metadata-Flavor: Google"
md_attr() { curl -s -H "$MD" "$MDS/$1"; }

BUCKET="${BUCKET:-$(md_attr BUCKET)}"
REPO_COMMIT="${REPO_COMMIT:-$(md_attr REPO_COMMIT)}"
REPO_URL="${REPO_URL:-https://github.com/iamdarshg/aero-multiphysics-workbench.git}"
REPO_DIR="${REPO_DIR:-/opt/repo}"
PATCH_OBJECT="${PATCH_OBJECT:-fixes.patch}"
EVIDENCE_DIR="${EVIDENCE_DIR:-/opt/governed-run}"
ISSUES="${ISSUES:-06,06ami,07static,07modal,08,11}"

TOKEN_URL="http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token"
ACCESS_TOKEN="$(curl -s -H "$MD" "$TOKEN_URL" | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])' 2>/dev/null)"
STEP=0

gs_put() {
  local file="$1" name="$2"
  [ -s "$file" ] || return 0
  local rc
  rc=$(curl -s -o /dev/null -w "%{http_code}" -X POST --data-binary @"$file" \
    -H "Authorization: Bearer $ACCESS_TOKEN" \
    -H "Content-Type: application/octet-stream" \
    "https://storage.googleapis.com/upload/storage/v1/b/$BUCKET/o?uploadType=media&name=$name")
  echo "gs_put $name http=$rc"
}

gs_get() {
  local name="$1" out="$2"
  curl -s -H "Authorization: Bearer $ACCESS_TOKEN" \
    "https://storage.googleapis.com/storage/v1/b/$BUCKET/o/$name?alt=media" -o "$out"
}

beat() {
  STEP=$((STEP + 1))
  echo "[$(date -u +%FT%TZ)] STEP $STEP: $1"
  echo "step=$STEP at=$(date -u +%FT%TZ) detail=$1" > "$LOGDIR/heartbeat.txt"
  gs_put "$LOGDIR/heartbeat.txt" heartbeat.txt
  gs_put "$LOG" blocker-startup.log
}

OVERALL=0
echo "token ${#ACCESS_TOKEN} chars; bucket=$BUCKET commit=$REPO_COMMIT"
beat "token acquired"

echo "--- apt prerequisites ---"
timeout 600 apt-get update -qq 2>&1 | tail -1
timeout 600 apt-get install -y -qq git curl ca-certificates python3 2>&1 | tail -1
beat "apt prerequisites"

echo "--- clone $REPO_URL @ $REPO_COMMIT ---"
if [ ! -d "$REPO_DIR/.git" ]; then
  git clone --filter=blob:none --no-checkout "$REPO_URL" "$REPO_DIR" 2>&1 | tail -2
fi
if git -C "$REPO_DIR" fetch --depth 1 origin "$REPO_COMMIT" 2>&1 | tail -2; then
  git -C "$REPO_DIR" checkout --force FETCH_HEAD 2>&1 | tail -2
else
  echo "fetch of $REPO_COMMIT failed"; OVERALL=1
fi
if [ ! -f "$REPO_DIR/scripts/gcp/governed-worker-startup.sh" ]; then
  echo "REPO CHECKOUT EMPTY"; OVERALL=1
fi
git -C "$REPO_DIR" clean -fdq 2>&1 | tail -2
git -C "$REPO_DIR" rev-parse HEAD > "$LOGDIR/repo_head.txt" 2>&1
beat "repo checkout"

echo "--- apply fix patch $PATCH_OBJECT ---"
gs_get "$PATCH_OBJECT" /tmp/fixes.patch
if [ -s /tmp/fixes.patch ]; then
  if git -C "$REPO_DIR" apply --whitespace=nowarn /tmp/fixes.patch 2>&1 | tail -5; then
    echo "patch applied"
  else
    echo "PATCH APPLY FAILED"; OVERALL=1
  fi
else
  echo "PATCH OBJECT EMPTY"; OVERALL=1
fi
beat "patch applied"

if [ "$OVERALL" -ne 0 ]; then
  echo "ABORTING after checkout/patch failure"
else
  echo "--- install (pinned uv env + native prefixes) ---"
  REPO_ROOT="$REPO_DIR" bash "$REPO_DIR/scripts/gcp/governed-worker-startup.sh" 2>&1 | tail -40
  INSTALL_RC=${PIPESTATUS[0]}
  echo "install rc=$INSTALL_RC"
  beat "install finished rc=$INSTALL_RC"

  echo "--- governed blocker driver ---"
  cp "$REPO_DIR/scripts/gcp/governed-blocker-run.py" /tmp/governed-blocker-run.py
  REPO_ROOT="$REPO_DIR" PY312=/opt/py312 bash "$REPO_DIR/scripts/gcp/run-blockers.sh" \
    "$EVIDENCE_DIR" --issues "$ISSUES" 2>&1 | tail -80
  DRIVER_RC=${PIPESTATUS[0]}
  echo "driver rc=$DRIVER_RC"
  [ "$DRIVER_RC" -eq 0 ] || OVERALL=1
  beat "driver finished rc=$DRIVER_RC"
fi

echo "--- package evidence ---"
tar czf /tmp/evidence.tgz -C "$EVIDENCE_DIR" . 2>/dev/null
tar czf /tmp/proofs.tgz -C "$LOGDIR" . 2>/dev/null
cp "$LOGDIR/versions.json" /tmp/versions.json 2>/dev/null
beat "evidence packaged"

echo "--- upload ---"
gs_put /tmp/evidence.tgz evidence.tgz
gs_put /tmp/proofs.tgz proofs.tgz
gs_put /tmp/versions.json versions.json
for f in capabilities.json precice-interpreters.json governed-install.log governed-install.done governed-install.failed repo_head.txt blocker-startup.log heartbeat.txt; do
  [ -f "$LOGDIR/$f" ] && gs_put "$LOGDIR/$f" "$f"
done

echo "=== BLOCKER RUN END $(date -u +%FT%TZ) overall=$OVERALL ==="
if [ "$OVERALL" -eq 0 ]; then
  echo "DONE $(date -u +%FT%TZ)" > /tmp/DONE
  gs_put /tmp/DONE DONE
  gs_put "$LOG" blocker-startup.log
else
  echo "FAILED $(date -u +%FT%TZ)" > /tmp/FAILED
  gs_put /tmp/FAILED FAILED
  gs_put "$LOG" blocker-startup.log
fi
