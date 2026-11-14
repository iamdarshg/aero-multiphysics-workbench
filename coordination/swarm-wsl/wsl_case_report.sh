#!/bin/bash
# Report achieved state for a completed/partial CFD anchor.
d=${1:-/root/dmg3/run-ias700}

echo "=== controlDict endTime ==="
grep -o 'endTime[^;]*;' "$d/system/controlDict" 2>/dev/null
echo "=== deltaT / maxCo / writeInterval ==="
grep -o 'deltaT[^;]*;'  "$d/system/controlDict" 2>/dev/null
grep -o 'maxCo[^;]*;'   "$d/system/controlDict" 2>/dev/null

echo "=== steps and sim time reached ==="
grep -c '^Time = ' "$d/solve.log" 2>/dev/null
grep '^Time = ' "$d/solve.log" 2>/dev/null | tail -1

echo "=== Uz residual trend (1st, 50th, 100th, 200th, last) ==="
grep 'Solving for Uz,' "$d/solve.log" 2>/dev/null | awk 'NR==1||NR==50||NR==100||NR==200{print NR": "$0}'
grep 'Solving for Uz,' "$d/solve.log" 2>/dev/null | tail -1

echo "=== Courant max seen ==="
grep -o 'max: [0-9.e+-]*' "$d/solve.log" 2>/dev/null | sed 's/max: //' | sort -g | tail -1

echo "=== fault markers ==="
printf 'nan=%s bounding=%s FATAL=%s\n' \
  "$(grep -ci 'nan' "$d/solve.log" 2>/dev/null)" \
  "$(grep -ci 'bounding' "$d/solve.log" 2>/dev/null)" \
  "$(grep -c 'FOAM FATAL' "$d/solve.log" 2>/dev/null)"

echo "=== postProcessing ==="
ls "$d/postProcessing" 2>/dev/null || echo none

echo "=== disk used by case ==="
du -sh "$d" 2>/dev/null