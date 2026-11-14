#!/usr/bin/env bash
# Launch N independent CFD anchors in WSL, detached, one process tree per anchor.
# Each anchor owns its own case directory, so there is no shared mutable state.
#
# NOTE: do NOT `source $OFOAM/etc/bashrc` here. That script terminates the caller
# (it is written to be sourced by an interactive login shell), which silently killed
# this launcher on the first attempt. The env is set explicitly instead.

OFOAM=/usr/lib/openfoam/openfoam2406
ARCH=linux64GccDPInt32Opt
export FOAM_INST_DIR=/usr/lib/openfoam
export WM_PROJECT=OpenFOAM
export WM_PROJECT_VERSION=2406
export WM_PROJECT_DIR=$OFOAM
export FOAM_ETC=$OFOAM/etc
export PATH="$OFOAM/platforms/$ARCH/bin:$OFOAM/bin:$OFOAM/wmake:$PATH"
export LD_LIBRARY_PATH="$OFOAM/platforms/$ARCH/lib:$OFOAM/platforms/$ARCH/lib/dummy:$OFOAM/platforms/$ARCH/lib/openmpi-system:${LD_LIBRARY_PATH:-}"
export FOAM_LIBBIN=$OFOAM/platforms/$ARCH/lib
export FOAM_APPBIN=$OFOAM/platforms/$ARCH/bin

ROOT=/root/dmg3
MESH="$ROOT/input/wing.msh"
CASE_SRC="/mnt/e/engineering-portfolio-audit/repos/drone-mech/highspeed_edf/phase15/fsi/results/local_openfoam_20261030/experiments/centerline_halfwing_ias/cases"

echo "checkMesh resolves to: $(command -v checkMesh)"
echo "rhoPimpleFoam resolves to: $(command -v rhoPimpleFoam)"

launch() {
  local anchor="$1"
  local dir="$ROOT/run-$anchor"
  local src="$CASE_SRC/$anchor"

  if [ ! -d "$src" ]; then
    echo "SKIP $anchor (no case dir at $src)"
    return
  fi
  if [ -f "$dir/.done" ]; then
    echo "SKIP $anchor (already done)"
    return
  fi

  rm -rf "$dir"
  mkdir -p "$dir/constant" "$dir/input"
  cp -r "$src/system" "$dir/system"
  cp -r "$src/0"      "$dir/0"
  cp "$src/constant/thermophysicalProperties" "$dir/constant/" 2>/dev/null
  cp "$src/constant/turbulenceProperties"     "$dir/constant/" 2>/dev/null
  cp "$MESH" "$dir/input/wing.msh"

  (
    cd "$dir" || exit 1
    echo "gmshToFoam..."
    gmshToFoam input/wing.msh > convert.log 2>&1
    if [ ! -f constant/polyMesh/boundary ]; then
      echo "CONVERT_FAILED" > FAILED
      exit 1
    fi
    # gmshToFoam tags every boundary as 'patch'. The case dictionaries require
    # fsi=wall and rootWall=symmetryPlane, otherwise rhoPimpleFoam aborts with
    # "Attempt to cast type patch to type symmetryPlane".
    perl -0pi -e 's/(\n\s*fsi\s*\n\s*\{\s*\n\s*type\s+)patch;/${1}wall;/' constant/polyMesh/boundary
    perl -0pi -e 's/(\n\s*rootWall\s*\n\s*\{\s*\n\s*type\s+)patch;/${1}symmetryPlane;/' constant/polyMesh/boundary
    echo "checkMesh..."
    checkMesh -allTopology -allGeometry > checkMesh.log 2>&1
    grep -q 'Mesh OK' checkMesh.log || echo "MESH_NOT_OK" > WARN

    # Bound the physics target so a job can finish inside a session. 5e-5 s is
    # ~28 chord-times at 1.75 ms/chord-time -- a stable residual trend, and
    # explicitly NOT a converged solution. Do not report forces from this.
    sed -i 's/^endTime .*/endTime 5e-5;/' system/controlDict
    sed -i 's/^writeInterval .*/writeInterval 50;/' system/controlDict

    echo "rhoPimpleFoam..."
    rhoPimpleFoam > solve.log 2>&1
    echo "$?" > EXIT
    touch .done
  ) > "$dir/launch.log" 2>&1 &

  echo "launched $anchor bg_pid=$!"
}

for a in ias700 ias900; do
  launch "$a"
done

echo "all launched"
wait