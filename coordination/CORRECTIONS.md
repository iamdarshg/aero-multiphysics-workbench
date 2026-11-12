# CORRECTIONS — claims in this bundle that later evidence overturned

Appended 2026-11-12T20:30 IST by dsh-lead, after `tannmay-python` (Claude Code / Fable)
published work on the same repos. Every correction below is a claim **this bundle made
that is wrong**. Corrections run in both directions; where Fable was wrong I say so too.

---

## C-1. Code-SDR CS-G7 "Verilator 5/5 tops clean" — FALSE PASS

**What this bundle said:** `code-sdr-lint.log` shows `5/5 tops clean`, reported as a pass.

**What is actually true:** the measurement is real but meaningless as a gate. The host's
Verilator is **5.040**, which does not implement the `MULTIDRIVENPROC` warning code.
`tannmay-python` ran **5.054**, which does, and `v2_top` in FFT mode fails with
`MULTIDRIVENPROC` — two drivers on one register.

**Verified independently by reading the RTL** (`verilog/v2_fft_packetizer.v`): two separate
`always @(posedge clk or negedge rst_n)` blocks, at L78 (intake) and L140 (TX), both drive
`wr_idx` (L80, L94 vs L168) and `bins_dropped` (L96 vs L148). Icarus resolves the conflict by
statement order, which is why all simulations passed.

**Status:** CS-G7 is **not a pass**. Icarus 21/21 and the firmware compile stand; the Verilator
leg does not. Fix is `tannmay-python`'s PR #71 (single-writer intake block, `MULTIDRIVENPROC`
added to the lint gate's FATAL codes).

**Lesson:** a tool-version-dependent gate is not a gate. `tools/lint_verilog.py` should assert a
minimum Verilator version and fail closed below it.

---

## C-2. aero AM-G1/AM-G2 "not reproducible" — MY INVOCATION WAS WRONG

**What this bundle said:** `mypy 0/505` and `1793/1794` have no command trail; from a clean
clone mypy aborts and pytest has 16 collection errors.

**What is actually true:** the checks are fully documented — in `services/api/pyproject.toml`
(`[tool.mypy]` with `strict = true` and a full `mypy_path`; `[tool.pytest.ini_options]` with
`pythonpath` and `testpaths`) and in the root `package.json` `typecheck:py` script (28 targets).
I ran both from the **repo root**, where none of that config applies. That was my error, not a
repo defect.

Running from `services/api` on this host:

| condition | result |
|---|---|
| as-shipped | 18 mypy errors / 505 files |
| after `pip install coolprop` | 17 errors / 505 files |
| `tannmay-python` on macOS with `uv sync` (#103) | **0 errors / 506 files** |

The residual 17 resolve to environment: `services/api/uv.lock` pins **numpy 2.5.3**; this host
has **numpy 2.2.6**, and 13 of the 17 are numpy-stub inference differences.

**Genuinely real, version-independent defects I did find:**
- `solvers/participants/run_scripts/run_ross.py:109,158,159,220,221,301` — 6 × `Name "np.ndarray"
  is not defined`; the module `import numpy` inside a helper and binds `np` only at runtime via
  `np, rs = _load_native_dependencies()`, so module-level `np.ndarray` annotations have no `np`.
- `packages/airframe/aeroworkbench_airframe/campaign.py:63` — `list[str]` vs
  `Iterable[MutationStage]`.

---

## C-3. research-paper RP-G1 — my "lower the occupancy weight" recommendation was WRONG

**What this bundle's PR #50 proposed:** the occupancy objective is switched off; enable
`--geometry-occupancy-mean-weight`. After it collapsed at weight 0.5, I recommended lowering the
weight to 0.005–0.02.

**What is actually true:** `tannmay-python`'s 4-arm controlled experiment (#51) shows the
collapse is **not** a weight-calibration problem. With per-dimension latent std
0.0003–0.043 (mean 0.019) against unit DDPM noise, the diffusion objective is already broken
before any occupancy term is added — arm A2 collapses with **no** occupancy loss at all.
**Latent standardization** is the fix; the occupancy loss is actively harmful here
(D2: standardization + occ w=1 → 25.7% vs C2: standardization alone → 83.3%).

My "lower the weight" advice would have bought a slower collapse, not a fix. PR #50 is
withdrawn as a fix proposal.

My independent collapse data agrees with their B2/A2 arm direction: weight 0.5 run produced
unique fraction 0.542 → 0.042 at epoch 2, occupancy 0.0408, i.e. collapse *and* still over the
0.04 bound.

---

## C-4. research-paper holdout-leak framing — partial over-statement

**What `tannmay-python`'s PR #51 body implies:** the diversity corpus builder writes train and
holdout into one manifest and "the train CLI built its loader from every record", so training
fit held-out data.

**The accurate scope:** this is true of the **`train` CLI** only. `run_monitored_training.py` —
which every actual run in this program used — filters correctly:

```
L1512: split=args.training_split
L1514: promotion_dataset = _build_split_dataset(dataset, args.promotion_split)
```
and the run logs show `Training samples per epoch: 660/756` / `Promotion samples: 96/756
(holdout)`.

**No leak occurred in any monitored run.** The fail-closed guard is still correct to add, but
the corpus runs were not leaky. Reported to them.

---

## C-5. drone-arm FL50 CAN choke — direction of the fix is undetermined

**What `tannmay-python`'s PR #39 concludes:** board pad nets imply windings 1–2 / 3–4 while
TDK's model gives 1–4 / 2–3, so CANH would land on bus CANL.

**Verified state of the board** (`FL50 = L_CommonModeChoke_Coilank_ACM4532`):

```
pad 1  /CAN interface/U50_CANH   (13.175, 18.875)   left,  top
pad 2  /CANH                     (13.175, 21.125)   left,  bottom
pad 3  /CAN interface/U50_CANL   (16.825, 21.125)   right, bottom
pad 4  /CANL                     (16.825, 18.875)   right, top
```

The board pairs pads **by column** (1,2 left / 3,4 right), which keeps H on H and L on L if the
part's windings are the column pairs. The claim is therefore entirely contingent on the ACT45B
pinout, and `revb.pretty/` does **not** contain the footprint nor the datasheet, so it cannot be
settled from the repository. Note the schematic already separates `U50_CANH` from `CANH` as
distinct nets, which hints the board may be right and the symbol mapping wrong — and a "fix" in
the wrong direction re-introduces the swap.

**Status:** real finding, unresolved direction. Owner decision.

---

## C-6. Disk event — E: dropped off the bus mid-session

At 2026-11-12T04:01:27 IST the external USB NVMe enclosure (Realtek RTL9210C) failed and the
volume disappeared, during a 14-epoch training run. Windows logged `disk 51` paging errors and
`NTFS 140/50` "corruption may occur" on VolumeId E:. Nothing was lost permanently; artefacts were
verified after recovery (git `fsck`, checkpoint load at `global_step=1320`, 756 corpus voxels
readable). Recorded because any run spanning that window lost its tail.