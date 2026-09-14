#!/bin/bash
# Solver worker: installs the full stack, then runs every cheap native proof.
# Idempotent-ish, no failures fatal. Evidence goes to /var/log/proofs/.
# Repo copy: infra/gcp/solver-worker-startup.sh (public, reproducible).
set +u
LOG=/var/log/proofs/master.log
mkdir -p /var/log/proofs
exec > >(tee -a "$LOG") 2>&1
echo "=== master start $(date -u +%FT%TZ) ==="
export DEBIAN_FRONTEND=noninteractive
# Lessons baked in: Ubuntu 22.04 ships python3.10, but the stack needs 3.12;
# pip packages install ONE PER COMMAND (one bad name must not abort the rest);
# the PyPI name is `ross`, not `ross-rotordynamic`.

echo "--- A: apt base ---"
apt-get update -qq
apt-get install -y -qq docker.io python3-pip gmsh xvfb libgl1 calculix-ccx software-properties-common libopenblas0 2>&1 | tail -1
add-apt-repository -y ppa:deadsnakes/ppa 2>&1 | tail -1
add-apt-repository -y ppa:elmer-csc-ubuntu/elmer-csc-ppa 2>&1 | tail -1
apt-get update -qq 2>&1 | tail -1
apt-get install -y -qq elmerfem-csc python3.12 python3.12-venv 2>&1 | tail -1
curl -sS https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py
python3.12 /tmp/get-pip.py 2>&1 | tail -1

echo "--- B: pip stack (one per command) ---"
for PKG in openmdao ross pybamm cantera; do
  timeout 600 python3.12 -m pip install -q "$PKG" 2>&1 | tail -1
  python3.12 -c "import importlib.util as u; print('P12 $PKG:', u.find_spec('$PKG') is not None)" 2>&1 | tail -1
done
gmsh --version 2>&1 | head -1 | sed 's/^/P gmsh /'
ElmerSolver --version 2>&1 | head -1 | sed 's/^/P elmer /'
ccx -v 2>&1 | head -2 | tr '\n' ' '; echo "(ccx)"

echo "--- C: conda heavies ---"
curl -sL https://micro.mamba.pm/api/micromamba/linux-64/latest | tar -xj -C /usr/local/bin bin/micromamba
/usr/local/bin/bin/micromamba create -y -p /opt/solvers -c conda-forge openfoam precice freecad 2>&1 | tail -1
export PATH=/opt/solvers/bin:$PATH
export LD_LIBRARY_PATH=/opt/solvers/lib:${LD_LIBRARY_PATH:-}
source /opt/solvers/etc/bashrc 2>/dev/null
echo "P openfoam=$WM_PROJECT_VERSION precice=$(precice-tools version 2>/dev/null | head -c 20)"

echo "--- D1: openmdao paraboloid ---"
python3 -c "
import openmdao.api as om
p = om.Problem()
p.model.add_subsystem('p', om.ExecComp('f = (x-3)**2 + x*y + (y+4)**2 - 3'))
p.model.add_design_var('p.x', lower=-50, upper=50)
p.model.add_design_var('p.y', lower=-50, upper=50)
p.model.add_objective('p.f')
p.driver = om.ScipyOptimizeDriver(optimizer='SLSQP')
p.setup(); p.run_driver()
print('R openmdao f =', round(float(p['p.f'][0]), 6))
" 2>&1 | tail -1

echo "--- D2: cantera gri30 HP equilibrate ---"
timeout 120 python3 -c "
import cantera as ct
g = ct.Solution('gri30.yaml'); g.TP = 1200, 101325
g.equilibrate('HP')
print('R cantera Tad =', round(float(g.T), 1), 'K')
" 2>&1 | tail -1

echo "--- D3: pybamm SPM discharge ---"
timeout 150 python3 -c "
import pybamm, numpy as np
model = pybamm.lithium_ion.SPM()
sim = pybamm.Simulation(model)
sol = sim.solve(np.linspace(0, 600, 60))
v = sol['Terminal voltage [V]'].entries
print('R pybamm V =', round(float(v[0]), 3), '->', round(float(v[-1]), 3))
" 2>&1 | tail -3

echo "--- D4: ross modal (best effort) ---"
timeout 150 python3 -c "
import ross as rs
print('R ross import ok')
" 2>&1 | tail -3

echo "--- D5: calculix cantilever ---"
rm -rf /tmp/ccx && mkdir -p /tmp/ccx && cd /tmp/ccx
python3 - <<'PYEOF' > beam.inp
print("*HEADING\ncantilever 10x1x1")
print("*NODE")
nid = 0
nodes = {}
for ix in range(11):
    for iy in range(2):
        for iz in range(2):
            nid += 1
            nodes[(ix, iy, iz)] = nid
            print(f"{nid},{ix*1.0},{iy*1.0},{iz*1.0}")
print("*ELEMENT,TYPE=C3D8,ELSET=E")
eid = 0
for ix in range(10):
    eid += 1
    n = [nodes[(ix,0,0)], nodes[(ix+1,0,0)], nodes[(ix+1,1,0)], nodes[(ix,1,0)],
         nodes[(ix,0,1)], nodes[(ix+1,0,1)], nodes[(ix+1,1,1)], nodes[(ix,1,1)]]
    print(f"{eid}," + ",".join(map(str, n)))
print("*MATERIAL,NAME=STEEL\n*ELASTIC\n210000,0.3\n*DENSITY\n7.85e-9")
print("*SOLID SECTION,ELSET=E,MATERIAL=STEEL")
print("*BOUNDARY\n1,1,3\n2,1,3\n3,1,3\n4,1,3")
print("*STEP\n*STATIC\n*CLOAD\n" + "\n".join(f"{nodes[(10,iy,iz)]},2,-10.0" for iy in range(2) for iz in range(2)))
print("*NODE FILE,OUTPUT=2D\nU\n*EL FILE\nS\n*END STEP")
PYEOF
timeout 200 ccx beam > ccx.log 2>&1; echo "ccx_exit=$?"
grep -a "displacements" ccx.log | head -2
python3 -c "
import re
txt = open('/tmp/ccx/beam.dat').read() if __import__('os').path.exists('/tmp/ccx/beam.dat') else ''
m = re.findall(r'^\s*\d+\s+([-\d.E+]+)\s+([-\d.E+]+)', txt, re.M)
print('R ccx nodes_with_disp =', len(m))
" 2>&1 | tail -1

echo "--- D6: openfoam cavity 10 vs 20 (mesh independence) ---"
for N in 10 20; do
rm -rf /tmp/cav$N && mkdir -p /tmp/cav$N/0 /tmp/cav$N/constant /tmp/cav$N/system && cd /tmp/cav$N
cat > system/controlDict <<EOF
FoamFile { version 2.0; format ascii; class dictionary; object controlDict; }
application icoFoam; startFrom startTime; startTime 0; stopAt endTime; endTime 0.1;
deltaT 0.005; writeControl timeStep; writeInterval 10; purgeWrite 0;
writeFormat ascii; writePrecision 6; writeCompression off; timeFormat general;
timePrecision 6; runTimeModifiable true;
EOF
cat > system/blockMeshDict <<EOF
FoamFile { version 2.0; format ascii; class dictionary; object blockMeshDict; }
convertToMeters 1;
vertices ((0 0 0) (0.1 0 0) (0.1 0.1 0) (0 0.1 0) (0 0 0.01) (0.1 0 0.01) (0.1 0.1 0.01) (0 0.1 0.01));
blocks (hex (0 1 2 3 4 5 6 7) ($N $N 1) simpleGrading (1 1 1));
edges ();
boundary (movingWall { type wall; faces ((3 7 6 2)); }
fixedWalls { type wall; faces ((0 4 7 3) (2 6 5 1) (1 5 4 0)); }
frontAndBack { type empty; faces ((0 3 2 1) (4 5 6 7)); });
EOF
cat > system/fvSchemes <<'EOF'
FoamFile { version 2.0; format ascii; class dictionary; object fvSchemes; }
ddtSchemes { default Euler; } gradSchemes { default Gauss linear; grad(p) Gauss linear; }
divSchemes { default none; div(phi,U) Gauss linear; } laplacianSchemes { default Gauss linear orthogonal; }
interpolationSchemes { default linear; } snGradSchemes { default orthogonal; }
EOF
cat > system/fvSolution <<'EOF'
FoamFile { version 2.0; format ascii; class dictionary; object fvSolution; }
solvers { p { solver PCG; preconditioner DIC; tolerance 1e-06; relTol 0.05; } pFinal { $p; relTol 0; } "(U|k|epsilon|omega|f|v2)" { solver smoothSolver; smoother symGaussSeidel; tolerance 1e-05; relTol 0.1; } }
PISO { nNonOrthogonalCorrectors 0; nCorrectors 2; pRefCell 0; pRefValue 0; } relaxationFactors { equations { U 0.9; } }
EOF
cat > constant/transportProperties <<'EOF'
FoamFile { version 2.0; format ascii; class dictionary; object transportProperties; }
transportModel Newtonian; nu [0 2 -1 0 0 0 0] 0.01;
EOF
cat > 0/p <<'EOF'
FoamFile { version 2.0; format ascii; class volScalarField; object p; }
dimensions [0 2 -2 0 0 0 0]; internalField uniform 0;
boundaryField { movingWall { type zeroGradient; } fixedWalls { type zeroGradient; } frontAndBack { type empty; } }
EOF
cat > 0/U <<'EOF'
FoamFile { version 2.0; format ascii; class volVectorField; object U; }
dimensions [0 1 -1 0 0 0 0]; internalField uniform (0 0 0);
boundaryField { movingWall { type fixedValue; value uniform (1 0 0); } fixedWalls { type noSlip; } frontAndBack { type empty; } }
EOF
timeout 120 blockMesh > bm.log 2>&1; BM=$?
timeout 280 icoFoam > foam.log 2>&1; ICO=$?
CONT=$(grep -a "time step continuity errors" foam.log | tail -1 | head -c 120)
echo "R foam N=$N blockMesh=$BM icoFoam=$ICO cont: $CONT"
done

echo "--- D7: freecad STEP roundtrip ---"
timeout 200 xvfb-run -a /opt/solvers/bin/freecadcmd -c "
import Part
box = Part.makeBox(10, 10, 10)
box.exportStep('/tmp/box.stp')
s = Part.read('/tmp/box.stp')
print('R freecad volume =', round(float(s.Volume), 3))
" 2>&1 | grep -a "R freecad" | tail -1

apt-get clean
df -h / | tail -1
free -m | head -2
echo "=== master done $(date -u +%FT%TZ) ==="
