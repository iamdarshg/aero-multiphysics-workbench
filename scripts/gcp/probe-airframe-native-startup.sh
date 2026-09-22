#!/bin/bash
# Bounded capability probe for the final AIRFRAME native dependency.
set +u
LOGDIR=/var/log/proofs
mkdir -p "$LOGDIR"
exec > >(tee -a "$LOGDIR/airframe-native-probe.log") 2>&1
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq curl bzip2 ca-certificates
curl -sL https://micro.mamba.pm/api/micromamba/linux-64/latest | tar -xj -C /usr/local/bin bin/micromamba
/usr/local/bin/bin/micromamba create -y -p /opt/openvsp -c conda-forge openvsp || true
PATH=/opt/openvsp/bin:$PATH python3 - <<'PY' > "$LOGDIR/airframe-native-capability.json" 2>&1 || true
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
