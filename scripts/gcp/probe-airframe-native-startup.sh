#!/bin/bash
# Bounded capability probe for the final AIRFRAME native dependency.
set +u
LOGDIR=/var/log/proofs
mkdir -p "$LOGDIR"
exec > >(tee -a "$LOGDIR/airframe-native-probe.log") 2>&1
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq curl bzip2 ca-certificates gdebi-core libglu1-mesa libgl1

# OpenVSP is not published on conda-forge. Install the official, versioned
# Ubuntu package before probing; absence remains an honest capability result.
OPENVSP_VERSION=3.52.1
OPENVSP_DEB=/tmp/OpenVSP-${OPENVSP_VERSION}-Ubuntu-24.04_amd64.deb
curl -fL "https://openvsp.org/download.php?file=zips/current/linux/OpenVSP-${OPENVSP_VERSION}-Ubuntu-24.04_amd64.deb" -o "$OPENVSP_DEB" || true
if [ -s "$OPENVSP_DEB" ]; then
  apt-get install -y -qq "$OPENVSP_DEB" || dpkg -i "$OPENVSP_DEB" || true
  apt-get install -f -y -qq || true
fi

PATH=/opt/openvsp/bin:/usr/bin:/usr/local/bin:$PATH python3 - <<'PY' > "$LOGDIR/airframe-native-capability.json" 2>&1 || true
import json, shutil, subprocess
names = ("vspaero", "vspaero.exe", "openvsp", "vsp")
observed = []
for name in names:
    path = shutil.which(name)
    if not path:
        continue
    try:
        run = subprocess.run((path, "--version"), capture_output=True, text=True, timeout=30)
        observed.append({"name": name, "path": path, "returncode": run.returncode,
                         "version": (run.stdout or run.stderr).strip()[:500]})
    except Exception as exc:
        observed.append({"name": name, "path": path, "error": f"{type(exc).__name__}:{exc}"})
print(json.dumps({"available": bool(observed), "observed": observed,
                  "native_result_published": False}, indent=2, sort_keys=True))
PY
touch "$LOGDIR/airframe-native-probe.done"
