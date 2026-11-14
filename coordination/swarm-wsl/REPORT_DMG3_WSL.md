# DM-G3 — transonic campaign: runs stably on the passing mesh, cannot reach `endTime` on this host

Measured in **native WSL2 OpenFOAM 2406** (`/usr/lib/openfoam/openfoam2406`), not the Docker
container. The 2406 build matches the container digest used for DM-G2.

## What was run

| item | value |
|---|---|
| mesh | `wing_centerline_t30_c1.msh`, sha256 `7fadb8d7…` — the DM-G2-passing mesh |
| `checkMesh` | **`Mesh OK`**, 1,690,534 cells, 100% tets |
| solver | `rhoPimpleFoam`, OpenFOAM 2406 |
| anchor | 700 km/h IAS — M 0.676, U 222.13 m/s, p 70,100 Pa (from the repo's `candidate.json`) |
| controlDict | `deltaT 1e-5`, `adjustTimeStep yes`, `maxCo 0.4`, `endTime 0.004` |
| host allocation | WSL2, 8 vCPU, 4 GB |

## Achieved state

| metric | value |
|---|---|
| steps completed | **218** |
| simulation time reached | **8.068e-5 s** of the 4.0e-3 s target (2.0%) |
| Uz initial residual | 1.000 → **5.90e-4** (step 50) → 2.74e-4 (100) → 1.83e-4 (200) → **2.60e-4** (218) |
| Courant max | 0.404 at steady state (a 9.29 spike occurs in the first startup step only) |
| NaN / bounding / FOAM FATAL | **0 / 0 / 0** |
| wall-clock | ~6.1 h → **≈0.6 steps/min** |

**The case is stable on the passing mesh.** Residuals collapse by three orders of magnitude in
the first 50 steps and then plateau at ~2e-4, which is a normal floor for `rhoPimpleFoam` on this
kind of case. There is no divergence, no bounding, and no fatal error across 218 steps.

## Why DM-G3 still cannot be closed

`endTime 0.004` needs roughly **10,000 steps** at the observed ~3.7e-7 s/step. At 0.6 steps/min
that is **~11.6 days for one anchor**, and ~23 days for two. The wall-clock blocker is unchanged
from the Docker measurement (6.8 days) — native WSL removed the 9p-mount I/O penalty but did not
change the fundamental cost, which is arithmetic on 1.69M cells with an acoustic-limited timestep.

Two things were tried and did **not** fix it:

1. **Raising WSL to 8 vCPU** — `rhoPimpleFoam` is single-threaded as invoked. CPU is 76% idle
   during a run; the bottleneck is not cores. `decomposePar` would be the fix, and was not done.
2. **Running both anchors concurrently** — with two 1.69M-cell cases in a 4 GB allocation, WSL
   reported ~200 MB free and both throttled. Serialising gave the surviving run the whole budget.

A `sed` on `controlDict` to shorten `endTime` silently did nothing, because this `controlDict` is
**single-line** (`startFrom startTime; startTime 0; …; endTime 0.004;`), so an anchored
`^endTime` pattern never matched. The run therefore targeted 4.0e-3 throughout, not the 5e-5 the
launcher intended. Anyone re-running this must not assume the anchored form.

## Honest verdict on DM-G3

**BLOCKED on wall-clock, not on physics.** The evidence supports exactly this much:

> The Phase-15 transonic case runs stably on the mesh that passes DM-G2 — 218 steps, no NaN, no
> bounding, residuals 1.0 → 2.6e-4 — but the configured `endTime` of 4.0e-3 s needs ~10,000 steps,
> i.e. ~11.6 days per anchor on a 2-core-effective laptop. No converged solution is obtainable here.

**No drag, lift, CL or CD is claimed.** No `forceCoeffs` function object is configured in the
committed case, so none were produced; and 2% of the time history would not support a force claim
even if they had been.

## What would actually close it

Ordered by cost-to-benefit on this hardware:

1. **`decomposePar` into 4–8 subdomains.** 16 logical cores are idle during a run. This is the
   single biggest available win and needs no physics change.
2. **Residual-based stopping instead of a fixed `endTime`.** Residuals plateau at ~2e-4 by step
   100, so the remaining ~9,800 steps buy little. A convergence criterion is defensible for a
   steady-state question; a fixed 4 ms transient is not the right target for one.
3. **`simpleFoam` / a steady solver** if the gate wants a steady answer (the FSI path is what
   needs the transient solver).
4. **`maxCo` above 0.4.** The acoustic timestep dominates; bounded schemes tolerate more.

Item 1 is the one I would do next: nothing else changes the order of magnitude, and it does not
touch the physics.

## Artefacts

- Case: `/root/dmg3/run-ias700` inside the WSL distro `Ubuntu2404` (785 MB). Not committed —
  it is regenerable from the launcher.
- Launchers: `scripts/wsl_launch_cfd.sh`, `scripts/wsl_run_detached.sh`,
  `scripts/wsl_poll_cfd.sh`, `scripts/wsl_case_report.sh`
- This report: `evidence/drone-mech/dm-g3/REPORT_DMG3_WSL.md`

## Two launcher defects found and fixed along the way

Worth recording because both failed *silently*:

1. **`source $OFOAM/etc/bashrc` kills a non-interactive script.** The first launcher sourced it and
   produced no output at all — no error, no log. Fixed by setting `PATH`, `LD_LIBRARY_PATH` and
   `FOAM_*` explicitly instead.
2. **WSL terminates detached children when the invoking `wsl.exe` call returns.** `nohup cmd &`
   inside `wsl -- bash -c` dies with the session. Fixed by wrapping in `setsid` from a script file.

Third, unrelated but costly: **inline bash in a PowerShell `-Command` string mangles `$(...)` and
unquoted globs.** Every script in this bundle is therefore a file under `scripts/`, never inline.