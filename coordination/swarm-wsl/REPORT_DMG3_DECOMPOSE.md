# DM-G3 addendum — `decomposePar` gives a measured 5.5× speedup

Appended after the serial-run report above. This is the "what would actually close it" item 1,
executed and measured.

## Result

| configuration | steps/min | projection to `endTime 4.0e-3` (~10,368 steps) |
|---|---:|---|
| 1 rank (serial) | 0.60 | ~11.6 days |
| **6 ranks (`decomposePar`, scotch)** | **3.31** | **~2.2 days** |
| speedup | **5.5×** | |

Measured over a 362 s window: **20 steps**, `RC=124` (timeout, i.e. the run was healthy and simply
hit the wall-clock cap I set). Zero NaN, zero `FOAM FATAL`, zero dummy-Pstream aborts.

## What this changes

DM-G3's blocker was characterised as "~11.6 days per anchor, not obtianable here". That was true for
a single-threaded run on a machine whose CPU sat 76% idle. With decomposition the same case runs at
**3.31 steps/min**, so:

- one anchor is **~2.2 days**, not 11.6;
- both anchors are **~4.4 days**, which is a scheduling problem rather than an impossibility;
- raising to 8 ranks on the 16-logical-core host should improve on 6 ranks, untested here.

**DM-G3 therefore moves from "not obtainable on this host" to "obtainable in days, with a
decomposed run".** I am not claiming it is closed: 4.4 days of wall clock has not been spent, and no
force coefficient has been produced. But the earlier verdict overstated the impossibility, and this
measurement is the correction.

## The residual-plateau point still stands

The serial run's Uz residual fell 1.0 → 1.8e-4 by step 200 and then plateaued. If a residual-based
stopping criterion is acceptable for the steady-state question, the run does not need all ~10,368
steps — a few hundred may suffice. That would put a single anchor inside a working session rather
than days. This is a gate-definition decision for the owner, not something I should assume.

## Three environment defects found, all of which failed silently

Each of these cost a failed attempt and none produced a useful error message on its own:

1. **`source $OFOAM/etc/bashrc` terminates a non-interactive script.** The launcher produced *no
   output at all* — no error, no log file. Fixed by setting `PATH`, `LD_LIBRARY_PATH`, `WM_MPLIB`
   and `FOAM_*` explicitly.
2. **WSL kills detached children when the invoking `wsl.exe` call returns.** `nohup cmd &` inside
   `wsl -- bash -c` dies with the session. Fixed by calling a *script file* that uses `setsid`.
3. **The MPI library path has two traps.** `lib/dummy` must not precede the real MPI or every rank
   aborts with *"The dummy Pstream library cannot be used in parallel mode"* — but
   `libkahipDecomp.so` exists **only** in `lib/dummy`, while the real `libscotchDecomp.so` is in
   `lib/`, and `libPstream.so` for MPI lives in `lib/sys-openmpi` (not `lib/openmpi-system`, which
   does not exist on this package). The working combination is:
   - decomposition: `LD_LIBRARY_PATH="$LIB:$LIB/dummy"` (real scotch wins, dummy kahip resolves)
   - solving: `LD_LIBRARY_PATH="$LIB/sys-openmpi:$LIB"` (no dummy)

## Honest limits of this measurement

- 362 s is a short window; the rate is dominated by the early small-timestep phase. Steady-state
  steps take *less* sim time each but the same wall time per step, so 3.31 steps/min is a
  **conservative** figure for the full run.
- 6 ranks on 8 vCPU was chosen to leave headroom. 8 ranks is untested.
- Memory: two 1.69M-cell cases do not fit in the 4 GB WSL allocation. One decomposed case at a time
  is the practical ceiling here. WSL reported ~200 MB free with two serial cases running, and both
  throttled.
- No parallel scaling study was done — the 5.5× is a single measured point, not a curve.

## Artefacts

- `scripts/wsl_decompose_bench.sh` — the working two-phase launcher, with the library-path
  reasoning in its header comment.
- Case: `/root/dmg3/run-ias700-par6` in the `Ubuntu2404` distro.