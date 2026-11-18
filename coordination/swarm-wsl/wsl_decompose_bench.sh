#!/bin/bash
# DM-G3 decomposePar speedup measurement.
#
# Two env phases are required, and getting this wrong cost two failed attempts:
#
#   1. decomposePar links libkahipDecomp.so / libscotchDecomp.so, which on this
#      openfoam.com package exist ONLY under lib/dummy. So decomposition runs with
#      lib/dummy on LD_LIBRARY_PATH.
#   2. rhoPimpleFoam -parallel must NOT see lib/dummy, or every rank aborts with
#      "The dummy Pstream library cannot be used in parallel mode". The solver runs
#      with the real system OpenMPI instead (WM_MPLIB=SYSTEMOPENMPI).
#
# Usage: wsl_decompose_bench.sh [NP] [SECONDS]

NP=${1:-6}
SECS=${2:-420}

OFOAM=/usr/lib/openfoam/openfoam2406
ARCH=linux64GccDPInt32Opt
LIB=$OFOAM/platforms/$ARCH/lib
BIN=$OFOAM/platforms/$ARCH/bin

export WM_PROJECT=OpenFOAM WM_PROJECT_VERSION=2406 WM_PROJECT_DIR=$OFOAM FOAM_ETC=$OFOAM/etc
export WM_MPLIB=SYSTEMOPENMPI FOAM_MPI=openmpi-system
export FOAM_LIBBIN=$LIB FOAM_APPBIN=$BIN
export PATH="$BIN:$OFOAM/bin:$OFOAM/wmake:/usr/local/bin:/usr/bin:/bin:${PATH:-}"

SRC=/root/dmg3/run-ias700
DST=/root/dmg3/run-ias700-par$NP

# ---- phase 1: decompose with the dummy-capable lib path ----
if [ ! -d "$DST/processor0" ]; then
  rm -rf "$DST"
  mkdir -p "$DST"
  cp -r "$SRC/0" "$DST/0"
  cp -r "$SRC/system" "$DST/system"
  cp -r "$SRC/constant" "$DST/constant"
  cat > "$DST/system/decomposeParDict" <<EOF
FoamFile { version 2.0; format ascii; class dictionary; object decomposeParDict; }
numberOfSubdomains $NP;
method scotch;
EOF
  cd "$DST" || exit 1
  echo "=== decomposePar ($NP), dummy lib path ==="
  LD_LIBRARY_PATH="$LIB/openmpi-system:$LIB:$LIB/dummy:$LD_LIBRARY_PATH" decomposePar -force > decompose.log 2>&1
  if [ ! -d processor0 ]; then
    echo "DECOMPOSE_FAILED"
    tail -6 decompose.log
    exit 1
  fi
fi

cd "$DST" || exit 1
echo "=== ranks on disk: $(ls -d processor* 2>/dev/null | wc -l) ==="

# ---- phase 2: solve with real MPI ----
export LD_LIBRARY_PATH="$LIB/openmpi-system:$LIB:$LD_LIBRARY_PATH"
echo "=== running $NP ranks for ${SECS}s ==="
start=$(date +%s)
timeout "$SECS" /usr/bin/mpirun --allow-run-as-root --oversubscribe -np "$NP" rhoPimpleFoam -parallel > solve.log 2>&1
rc=$?
elapsed=$(( $(date +%s) - start ))

steps=$(grep -c '^Time = ' solve.log 2>/dev/null); steps=${steps:-0}
echo "RC=$rc elapsed=${elapsed}s steps=$steps"
awk -v s="$steps" -v e="$elapsed" 'BEGIN{if(e>0) printf "RATE %.2f steps/min\n", s/(e/60.0)}'
echo "--- last time ---"; grep '^Time = ' solve.log 2>/dev/null | tail -1
echo "--- Uz residual ---"; grep 'Solving for Uz,' solve.log 2>/dev/null | tail -1
printf -- '--- faults --- nan=%s fatal=%s dummy=%s\n' \
  "$(grep -ci nan solve.log 2>/dev/null)" \
  "$(grep -c 'FOAM FATAL' solve.log 2>/dev/null)" \
  "$(grep -c 'dummy Pstream' solve.log 2>/dev/null)"

