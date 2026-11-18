#!/bin/bash
# Poll the detached CFD runs. Prints a compact per-anchor state line.
ROOT=/root/dmg3

echo "=== case dirs ==="
ls -d "$ROOT"/run-* 2>/dev/null || echo "(none)"

echo "=== per-anchor state ==="
for d in "$ROOT"/run-*; do
  [ -d "$d" ] || continue
  a=${d##*/}

  state="RUNNING"
  if [ -f "$d/.done" ]; then
    state="DONE exit=$(cat "$d/EXIT" 2>/dev/null)"
  fi
  if [ -f "$d/FAILED" ]; then
    state="FAILED: $(cat "$d/FAILED" 2>/dev/null)"
  fi

  mesh="no"
  if grep -q 'Mesh OK' "$d/checkMesh.log" 2>/dev/null; then mesh="YES"; fi

  cells=$(grep -m1 -E '^[[:space:]]*cells:' "$d/checkMesh.log" 2>/dev/null | awk '{print $2}')
  steps=$(grep -c '^Time = ' "$d/solve.log" 2>/dev/null)
  if [ -z "$steps" ]; then steps=0; fi
  lastt=$(grep '^Time = ' "$d/solve.log" 2>/dev/null | tail -1 | sed 's/^Time = //')
  lastr=$(grep 'Solving for Uz,' "$d/solve.log" 2>/dev/null | tail -1 | sed 's/.*Initial residual = //; s/,.*//')

  warn=""
  if [ -f "$d/WARN" ]; then warn=" [WARN:$(cat "$d/WARN")]"; fi

  printf '%-14s %-18s meshOK=%-4s cells=%-9s steps=%-5s t=%-12s Uz=%s%s\n' \
    "$a" "$state" "$mesh" "${cells:-?}" "$steps" "${lastt:-0}" "${lastr:-?}" "$warn"
done

echo "=== live processes ==="
printf 'rhoPimpleFoam=%s gmshToFoam=%s checkMesh=%s\n' \
  "$(pgrep -c rhoPimpleFoam 2>/dev/null || echo 0)" \
  "$(pgrep -c gmshToFoam 2>/dev/null || echo 0)" \
  "$(pgrep -c checkMesh 2>/dev/null || echo 0)"

echo "=== load / mem ==="
uptime | sed 's/.*load average/load/'
free -m | awk '/^Mem:/{printf "mem used=%sMB free=%sMB\n", $3, $4}'