# CORRECTIONS — claims in this bundle that later evidence overturned

Started 2026-11-12T20:30 IST by dsh-lead; **last revised 2026-11-13T21:00 IST**.
Appended after `tannmay-python` (Claude Code / Fable) published work on the same repos.
Every correction below is a claim **this bundle made that is wrong**. Corrections run in
both directions; where Fable was wrong I say so too.

**Revision policy:** entries are amended in place when later evidence overturns them, and
the amendment is labelled. An entry is only current if it carries no "SUPERSEDED" banner.
C-1 was amended as C-1b; C-8 and C-9 were amended on 2026-11-13 after the `--schematic-parity`
run contradicted them. If you are reading a number here that disagrees with
`coordination/gates/GATE_STATUS.md`, GATE_STATUS is the newer document.

---

## C-1. Code-SDR CS-G7 "Verilator 5/5 tops clean" — FALSE PASS

**What this bundle said:** `code-sdr-lint.log` shows `5/5 tops clean`, reported as a pass.

**What is actually true:** the RTL has a genuine two-driver defect that the gate never checked.

**Verified independently by reading the RTL** (`verilog/v2_fft_packetizer.v`): two separate
`always @(posedge clk or negedge rst_n)` blocks, at L78 (intake) and L140 (TX), both drive
`wr_idx` (L80, L94 vs L168) and `bins_dropped` (L96 vs L148). Icarus resolves the conflict by
statement order, which is why all simulations passed. Per Verilator's manual this is legal
SystemVerilog but "typically a synthesis error".

**Status:** CS-G7 is **not a pass**. Icarus 21/21 and the firmware compile stand; the Verilator
leg does not. Fix is `tannmay-python`'s PR #71 (single-writer intake block).

### C-1b. Both explanations of *why* it was missed were wrong
- **This bundle's first explanation** — "5.040 does not implement `MULTIDRIVENPROC`" — is
  **false**. 5.040 implements it.
- **`tannmay-python`'s explanation** — "5.054 flags it, your Verilator predates the check" — is
  **unverified**. 5.054 is not obtainable here, and 5.48 (newer) does not fire it either.

**What is actually true, settled by a control module:** Verilator's manual states
`MULTIDRIVENPROC` is *"Disabled by default as this is a code-style warning; it will simulate
correctly."* A deliberately double-driven control register fails to trigger it under **both**
5.040 and 5.48 with `-Wall`. (Contrast `MULTIDRIVEN`, which *is* on by default but only covers
`always_comb`/`always_ff` intent, which this code does not use.)

Evidence: `evidence/code-sdr-agent/verilator-version-matrix-CORRECTED.log` (control module, both
versions), `docs-multidrivenproc.log` (manual extract).

**Lesson — corrected:** a version check would not have helped. The gate needs to (a) **pass
`-Wmultidrivenproc` explicitly**, because a code in `FATAL_CODES` cannot fire if the warning
itself is disabled, and (b) include a **control module that is deliberately multi-driven**,
asserting the gate reports a FATAL code on it. Without that control, a warning default changing
between releases silently disables the gate — which is exactly what happened.

A first attempt at the version matrix was itself invalid: the "5.48" runs were no-op failures
(`Can't exec "verilator_bin"`, `rev vUNKNOWN`), and were discarded rather than reported.

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
---

## C-7. Copperline C-G1 "42/52 cannot be re-derived" — understated, and the diagnosis was wrong

Two worker agents re-measured this. Both parts of the original claim needed correcting.

**On the corpus.** This bundle said the 52-board corpus "is not committed" and 42/52 "cannot be
re-derived". Accurate but soft. What a full inventory shows:

- `tests/corpus_manifest.json` has **10 boards** (4 `short`, 10 `long`); all 10 inputs resolve.
- `docs/validation/corpus/2026-10-29/boards/` holds **15** files — **5 are inert** (`b009`,
  `b013`–`b016`) because no manifest entry references them.
- The strings `42/52`, `80.8`, `82.4` appear **nowhere in the repository**.
- The repo's own flagship figure is `docs/validation/corpus.md:155`: **11/21 = 52.4%**.
- Historical result files hold 38 / 21 / 118 / 15 entries — **none has 52**.
- **11/21 = 52.4%** vs **42/52 = 80.8%**: transposed digits, shared decimal digits. An 11/21
  measurement most likely became a remembered "42/52".
- 11/21 cannot be re-run either: **8 of 21** source paths survive.

**Maximum evaluable: 10 boards.**

**On the diagnosis.** This bundle said the completion shortfall was "consistent with the
handoff's geometric-cap explanation". **Wrong.** Across 202 failed task-routes: 181 produced no
candidate (89.6%), 21 searched and blocked (10.4%), **0** arbiter-rejected. And:

1. Only **5 of 390** unconnected terminals (1.3%) are geometrically unescapable.
2. All 181 "no candidate" records carry **`expansions = 0`** and no hierarchy guidance guard —
   the search contributed **nothing at all** on tasks nonetheless marked attempted.
3. All 181 carry `UNROUTABLE_UNDER_CONFIGURED_CONSTRAINTS_AND_BUDGET` while showing
   `ripup_attempts > 0` and `modes_attempted = (FAST, RECOVERY, EXHAUSTIVE_LOCAL_RECOVERY)`.

This is an **algorithmic / control-flow defect**, not a geometric bound. `expansions = 0` is the
signature. Caveats that must travel with it: the 4 short boards are a deliberately hard survivor
subset, so "0/4" is not a general rate.

Evidence: `evidence/copperline-agent/REPORT.md` and raw logs.

---

## C-8. Drone-arm DA-G2 RF reference plane — right conclusion, sloppy measurement

The original drone-arm RF claim was built by **net-name matching** (`RF`, `915`, `ANT`, `GNSS`),
which swept in DC/rail nets under the `/915 MHz RF/` sheet (`VDD_CC112` 58 mm, `VDD_CC119` 27 mm,
`3V3_GNSS` 43 mm). Those dominated the length and inflated the total to 603.61 mm.

The board declares netclass **`RF_50R`** in `main_rev_b.kicad_pro` — the authoritative set, 16
nets. Re-measured on that: **102.354 mm**, of which **0.00% over `/GND`**, **88.91% over
`/3V3`**, **11.09% over pour voids**.

So "0% ground" was right; "100% over 3V3" was wrong, and the 11.09% over **voids** is worse than
over the power plane, because a void is no reference at all. Cross-validated with two independent
APIs (`Contains` vs `HitTestFilledArea`, agreeing 8000/8000 samples).

A first containment implementation failed its own self-test (misclassified a through-hole pad)
and was discarded, not reported.

> **AMENDED 2026-11-13.** A later re-measure gave 90.95 mm / 11.40 mm = **88.86% / 11.14%** on a
> 102.35 mm total. The difference from 88.91 / 11.09 is **sampling step**, not a different
> method: 0.05 mm track sampling vs a finer walk. Both agree that `/GND` is **0.00%**. Quote
> **88.9% / 11.1%** and treat the second decimal as noise. The authoritative figure is in
> `coordination/gates/GATE_STATUS.md` (DA-G2).
>
> **An objection was raised and dismissed.** A reviewer argued the numbers were self-inconsistent
> because 88.86 + 11.14 = 100% while the total was "102.35 mm of a 100 mm-class total". That is a
> misreading: 102.35 mm is a **trace length**, not a percentage base, and
> 90.95 + 11.40 + 0.00 = 102.35 mm exactly. The percentage split is internally consistent.
>
> **A second objection was investigated and also dismissed.** "0.00% over GND is implausible on a
> real board, so suspect a measurement bug." Investigated directly: the In1 `/GND` zone fills
> **82.18 mm² across 177 separate outlines**, against `/3V3` at **12,164.05 mm² across 3
> outlines**. `checkMesh`-style sanity does not apply here, but the zone enumeration is decisive
> — In1 `/GND` is a border ring of slivers, not a plane, so 0% contact with an interior RF
> corridor is the expected result rather than a bug. The measurement is sound; the earlier
> net-name-based figure was not.

---

## C-9. Drone-arm FL50 CAN choke — **SUPERSEDED: the pack IS crossed**

> **SUPERSEDED 2026-11-13.** This entry concluded "no swap" from pad geometry. That conclusion
> was **wrong**. KiCad's own netlist comparison contradicts it directly:
> ```
> kicad-cli pcb drc --schematic-parity
>   Pad net (/CANH)                   doesn't match net given by schematic (/CAN interface/U50_CANL)
>   Pad net (/CAN interface/U50_CANL) doesn't match net given by schematic (/CANL)
>   Pad net (/CANL)                   doesn't match net given by schematic (/CANH)
> ```
> **FL50 is crossed.** DA-G1 therefore FAILS partly on this. The reasoning error: pad geometry
> describes the *footprint*, and a footprint can pair its pads however it likes; the winding
> assignment lives in the *symbol's pin order*. Geometry cannot see a swap that only exists in
> the schematic symbol. The parity tool compares actual connectivity, so it is the correct
> source of truth for pin-out, and pad geometry is not.
>
> The original entry is kept below, unedited, because the error is instructive.

Geometry pairs FL50's pads **by column**: {1,2} at x = 13.175 mm and {3,4} at x = 16.825 mm, with
row pitch 2.25 mm and diagonal 4.2878 mm. Column pairing is the natural winding pair, which gives
**one winding in series with each CAN line and no swap** — the intended CMC topology, agreeing
with the schematic `L_Coupled` symbol and the ESC board's `FL201`.

Whether the part is actually {1,4}/{2,3} depends on the TDK ACT45B terminal map, which is **not in
the repository** (37 PDFs checked). An ohmmeter across pads 1–2 vs 1–4 settles it.

This bundle and `tannmay-python`'s PR #39 both frame it as closer to "likely crossed"; the
geometry points the other way. Record it as an **open question for the owner**, not a defect.

> *That last paragraph is the specific claim that the parity run overturned. Note the tell that
> was available at the time and ignored: the single ERC warning in this design is
> `lib_symbol_mismatch` **on `L_Coupled` itself** — the very symbol whose pin order was in
> question. A stale library symbol on a disputed pin-out is evidence, not noise.*
