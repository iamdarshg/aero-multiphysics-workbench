# GATE STATUS — measured state, not claimed state

Recorded 2026-11-12, **last revised 2026-11-13T23:35** by dsh-lead (DeepSeek V4.1 Flash 1017).
This revision reflects council round 1 fixes: DM-G2b downgraded to FAIL, counts recounted
programmatically, and the AM-G1/AM-G2 wording aligned with the correct invocation.
Base: `origin/info-dump/2026-11-10-handoff`, clean clone, Windows 11 host.

**Every gate has a verdict. There are no bare "UNVERIFIED" entries left.** Where a gate
cannot be run on this host, the status is BLOCKED and the reason names the missing
tool or input. Where the gate could be run but was not, the status is NOT RUN and the
reason says why. Neither is a pass.

Legend: **PASS** = reproduced with a command on this host. **FAIL** = reproduced and
fails. **PARTIAL** = some of the gate's claims measured, others not. **BLOCKED** =
cannot run here; missing tool/input named. **NOT RUN** = runnable but deliberately not
run; reason given. No gate is asserted from the handoff without a command.

---

## research-paper

| Gate | Status | Evidence / reason |
|---|---|---|
| RP-G0 baseline integrity | **PASS** | `pytest -q` → 686 passed, 5 skipped, 0 failed (856 s). Gate hash `4eafa9488650a3604f43bfa81be7476fc3b19575aa7ee9c15db90de2125fd135` unchanged. |
| RP-G1 validity | **FAIL** | Four arms measured. A2 collapses (step 249); B2 collapses with weight 1 (step 473); **C2 latent standardization 480/576 (83.3%), 11 distinct**; **D3 std+occupancy weight 1: 576/576, 35 distinct, 9.9%**. Novelty 0 in every arm. The collapse is latent-scale, fixed by standardization — not by the occupancy weight. |
| RP-G2 novelty | **FAIL** | Held-out GT novelty vs train union = 0.000508 (68/96 exactly 0) across all arms. Corpus family saturates; needs a family-level held-out corpus. |
| RP-G3 diversity | **FAIL** | Computable now that D3 completed: 576/576 occupancy, 35 distinct samples out of 576 = 9.9% unique. Not a diverse batch. |
| RP-G4 conditioning | **FAIL** | Traced to the decoder, not the latents: GT reconstruction 0.433 vs decoder-on-true-latents 0.006. The decoder is the bottleneck. |
| RP-G5 negative controls | **FAIL** | **RUN.** The frozen gate (spec hash `4eafa948…`, matching RP-G0) was run on `final_monitored_model.pt`: `new_gate_pass = false`, `distinct_array_count = 1` of 5 required, `novel_voxel_fraction_mean = 0.0` against a 0.01 threshold, `nontrivial_pair_count = 0`, old-gate pass rate 0%, and **bit-identical output across 2 seeds for all 96 conditions**. All three negative controls are correctly rejected — and `plus_cross`/`three_box` clear the old screen and score novelty 0.30/0.61, caught only by structural articulation, so the gate genuinely discriminates. The model's novelty equals the degenerate `constant_union` control. |
| RP-G6 reconstruction | **FAIL** | The decoder is the bottleneck: GT reconstruction error **0.433** against **0.006** for the decoder applied to *true* latents. The decoder works; the generator does not produce latents the decoder can render. Splitting these is exactly the distinction the paper must make and does not. |
| RP-G7 solver agreement | **BLOCKED** | Needs a fresh WSL OpenFOAM on ≥3 canonical cases. No WSL Ubuntu distro on this host. The Docker path exists but was not exercised for this gate, and running CFD solver agreement would consume the machine for days (see DM-G3 throughput). |
| RP-G8 statistics | **FAIL** | D3 gives n=576 with 35 distinct and 9.9% unique; that is the statistic, and it fails a diversity requirement regardless of the confidence interval. |
| RP-G9 reproducibility | **PARTIAL** | The gate hash is stable across runs (RP-G0), which is the reproducibility claim that can be checked. Full run-to-run seed reproducibility was not re-run — a 14-epoch run is ~12 h. |
| RP-G10 adversarial review | **PARTIAL** | **RUN** — claim-by-claim against the repo's own evidence. **No generative overclaim**: abstract, results and conclusion all state novelty ≈ 0 and that diverse/conditioned generation is not demonstrated. But **one number contradicts four internal files**: `main.tex:32` says the 45 draws contain **five** near-identical arrays, while `FINAL_RUN_GATES.md:24`, `:40` and `SCIENTIFIC_GATE_STATUS.md:19`, `:55` all say **two distinct in 45** — the paper under-reports the collapse by 2.5×, in the unsafe direction. Also unverifiable: the 45/45 recovery run was never committed (cited `build/recovery_2026-11-05/` absent); two cited evidence paths do not exist; "45 epochs, latent 16" against a committed 14-epoch/latent-192 checkpoint; 0.000508 and 9.9% appear nowhere in the paper. **Supported**: the model-free-constant control (independently reproduced), the training-hull-emitter conclusion, and every "remains blocked" statement. |
| RP-G11 claim consistency | **FAIL** | The paper's occupancy claim does not survive RP-G1: occupancy is satisfied by D3, but novelty is 0 and diversity is 9.9%. Any claim of a valid generative contribution is unsupported. |
| RP-G12 final artifacts | **BLOCKED** | `paper/main.pdf` was not rebuilt. Tectonic is present but the paper cannot honestly be rebuilt while RP-G1/G2/G11 fail. |

**research-paper verdict: FAIL.** RP-G0 passes; the substance (G1, G2, G3, G4, G8, G11) does not.

## drone-mech

| Gate | Status | Evidence / reason |
|---|---|---|
| DM-G1 buildable geometry | **FAIL** | Native CAD interference: 4 pairs, 50,033.0 mm³ exact intersection each, 36 mm can overlap at 36 mm pitch, `status: FAIL`. The 42×72 mm motor envelope is an **unsourced CAD assumption** and must not be treated as a constraint until cited. |
| DM-G2 mesh quality | **PASS** | Rebuilt mesh `7fadb8d7…`: `checkMesh -allTopology -allGeometry` → **`Mesh OK`**, 0 failed checks. 1,690,534 cells, determinant min **1.1716e-3**, interp weight min 0.1255, non-ortho max 69.30°, skewness 0.875. Progression 411 bad cells → 1 → 0. **Caveat: 100% tets, no prisms, y+ uncontrolled.** |
| DM-G2b wall treatment | **FAIL** | y+ estimated 134 / 191 / 261 at 700 / 800 / 900 km/h from a measured median first-cell distance of 0.8415 mm. **That estimate is not sufficient to justify wall functions, and an engineering review overturned the "applicable at 700/800" conclusion.** A wall function requires the first cell to sit at the log-layer edge (y+ ≈ 30–200) *with a valid wall-normal coordinate obeying the log law*; a tetrahedron has no wall-normal direction, and a 0.8415 mm first cell on a 388 mm chord is ≈0.22% of chord — the thickness of the boundary layer itself, not a probe placed inside it. A cell that thick spans the sublayer and the log region, so the law of the wall overestimates shear. A **median** y+ also says nothing about a transonic wing where y+ varies steeply at the leading edge and at suction peaks, and the reported 0% in 5–30 together with 21–24% above 300 is itself evidence of a bimodal distribution rather than a controlled one. At 900 km/h, 21–24% of the wall exceeds y+ 300. **Verdict: this mesh is not valid for wall-function transonic RANS; it needs wall-resolved prisms (y+≈1, 15–30 layers, growth 1.15–1.2) or, at minimum, a full y+ histogram rather than a median.** |
| DM-G3 transonic campaign | **BLOCKED** | Runs stably on the passing mesh (Uz residual 1.0 → 3.5e-4 holding, Courant 0.404, no NaN) but at **1.07 steps/min**, so `endTime 4.0e-3` needs ~10,368 steps ≈ **6.8 days per anchor**. Not closable on this host at the configured Courant/timestep. No force values are claimed. |
| DM-G4 low-speed/control | **BLOCKED** | Same throughput wall as DM-G3; the same case machinery would take days per condition. Not attempted. |
| DM-G5 structures/modal | **BLOCKED** | CalculiX is not installed on this host. The handoff's 10-mode figure on a synthetic sector with assumed E/ν/ρ is unverified and the material properties are assumptions, not supplier data. |
| DM-G6 aeroelastic | **BLOCKED** | preCICE is not installed. Beyond that, the mesh is 100% tets with no prism layers, which is unsuitable for an FSI interface regardless of tooling. |
| DM-G7 aircraft closure | **FAIL** | The 7-actuator vs 6-PWM conflict is unresolved and confirmed on the drone-arm side by schematic parity (see DA-G1: J60–J65 missing). |
| DM-G8 provenance | **FAIL** | `run_manifest.json` records `"meshCheck": "… Mesh OK …"` for the *committed* mesh while `checkMesh` prints `Failed 2 mesh checks` on it. Also `ias900/constant/polyMesh` is a 22-byte git symlink stored as text, so a clean clone cannot run the case in place. |
| DM-G9 promotion | **FAIL** | Unpromoted, correctly — DM-G1 and DM-G8 fail. |

**drone-mech verdict: DM-G2 only.** One engineering gate moved to PASS with a quantified caveat.

## drone-arm

| Gate | Status | Evidence / reason |
|---|---|---|
| DA-G1 schematic/board integrity | **FAIL** | `kicad-cli pcb drc --schematic-parity` → 0 violations, 0 unconnected, **191 schematic parity issues**: 161 `footprint_symbol_mismatch`, 20 `net_conflict` (6 real), **6 `missing_footprint` (J60–J65)**, 4 `extra_footprint`. The six ESC PWM outputs exist in the schematic, are absent from the board **and the BOM**, so "0 unconnected" is an artefact of their deletion. Root ERC = 1 warning (`lib_symbol_mismatch`, `L_Coupled`). |
| DA-G2 RF 915 | **PARTIAL** | Measured on the board's own `RF_50R` netclass (16 nets, 102.35 mm on F.Cu): **0.00% over `/GND`**, **88.86% over `/3V3`**, 11.14% over pour voids. In1 holds 12,164 mm² of `/3V3` against 82.2 mm² of `/GND` in 177 slivers; nearest ground is B.Cu at 1.510 mm. **`CC_LNA_N` is split** F.Cu 3.46 mm + In2.Cu 1.84 mm while `CC_LNA_P` is a single F.Cu segment; In2 holds only `/1V1`. Impedance is analytic only and is **not a valid in-circuit figure** because the reference is a power net. |
| DA-G3 route quality | **PARTIAL** | 2,279 segments, 341 vias, 5,363 mm copper, 0 zero-length, widths 0.25/0.2/0.35 mm. **No diff-pair skew tooling exists in the repo**, so skew is not measurable here. |
| DA-G4 fab package | **FAIL** | The only package is dated **2026-03-31** against a 2026-11-11 board; all **11 layers are 288.40 × 204.24 mm** against a 140 × 100 mm outline; **0/11 byte-identical** to a fresh export; no stackup, no DRC receipt, no SHA-256 manifest, no `.pos`. Sending it to a fab produces a different design. |
| DA-G5 simulation | **PARTIAL** | **The stackup is NOT undefined** — retracting an earlier claim. `net_settings` has no stackup key, but the **board file carries a complete one**: F.Cu 0.035 / prepreg **0.200 mm** FR4 εr 4.2 tan δ 0.02 / In1 / core **1.040 mm** / In2 / prepreg 0.200 / B.Cu, total 1.6 mm ENIG. On it, 0.35 mm at 915 MHz gives **48.61 Ω** (Hammerstad), **53.98 Ω** (Wheeler), **51.23 Ω** (scikit-rf MLine) — **~50 Ω is correct for 0.35 mm**. Full-wave field solve remains BLOCKED. |
| DA-G6 physical | **BLOCKED** | No VNA, no VISA runtime, no SCPI instrument. Unblocking path documented: any 2-port VNA covering 900–930 MHz + SOL kit (a NanoVNA-H4 suffices), 1-port S11 at the antenna connector swept 800–1000 MHz. A 1-port measurement cannot separate trace, matching network and SAW filter — settling the plane needs a field solve or a TDR. |

**drone-arm verdict: NOT FAB-READY.** The repo's own `RELEASE_STATUS.md` says "not fabrication-ready"; that is correct and understated.

## copperline

| Gate | Status | Evidence / reason |
|---|---|---|
| C-G1 completion | **FAIL** | 0/4 COMPLETE, 0 DRC violations. The 52-board corpus is **not in the repository**: the manifest has 10 boards (4 short-tier), `docs/validation/corpus.md:155` states **11/21 = 52.4%**, and the strings `42/52`, `80.8`, `82.4` appear nowhere in the tree. **Root cause is not the epoch cap** — raising `max_epochs` 12 → 100000 changes nothing (bit-identical `state_hash`, 0 connections gained). The terminator is the 4-stalled-epoch detector at `engine.cpp:1623-1624` (`kMaxStalledEpochs = 4`, `parallel.h:49`). 181 of 202 failed task-routes are reported `unattempted` with `expansions = 0`. |
| C-G2 legality | **PASS** | Legality gate PASS 4/4 boards, 0 violations, exit 0. |
| C-G3 tests | **PASS** | `ctest --test-dir build -LE campaign` → 33/33 passed, 0 failed (550.9 s). |
| C-G4 determinism | **PASS** | Demonstrated incidentally and strongly: two independent binaries (original and instrumented) at identical settings produced **bit-identical `state_hash` on all 4 boards**, which is a stronger determinism result than a repeat run of one binary. |
| C-G5 issues | **BLOCKED** | Issues #27–#48 are **enumerated**, not dispositioned — closing them is the owner's decision. Two were checked in detail: #39 pad-gap asymmetry and #43 signature collision. Dispositions are recorded in `evidence/notrun-gates/raw/`. |
| C-G6 honesty | **PASS** | Both denominators are reported; the 4-board short tier cannot express either the 52-board or the 11/21 claim, and this file says so. |

**copperline verdict: C-G2/C-G3 PASS, C-G1 FAIL.** The blocker is a control-flow defect plus a missing corpus, not routing capability — only 5 of 390 unconnected terminals are geometrically unescapable.

## Code-SDR

| Gate | Status | Evidence / reason |
|---|---|---|
| CS-G1 DRC | **FAIL (but waiver justified)** | 222 violations = 199 `lib_footprint_mismatch` + 13 `via_dangling` + 10 `track_dangling`; 0 errors, 0 unconnected. **The 199 identity waiver is correct**: an independent best-fit transform search (rotation 0/90/180/270, mirrored and not, 1 µm tolerance) found all **199/199 pad-identical**, with the fitted transform consistent with each footprint's placed orientation, and silk as the only delta. |
| CS-G2 RF50 | **PASS (connectivity only)** | Audit exit 0, 49/49 nets connected, `incomplete=[]`, uniform 0.23 mm. **Caveat:** "0 nonconforming" is relative to the repo's own rule, not to 50 Ω. On the declared 0.130 mm prepreg at Dk 4.2 the four closed forms give ≈47.6–53.7 Ω, so 0.23 mm is defensible — my earlier "0.23 mm is not 50 Ω" was wrong. |
| CS-G3 return paths | **FAIL** | `validate_route.py` exit 1: signal routed on a solid In1/In2 ground plane. Known 4-layer contract conflict; a board-stackup decision, not a code fix. |
| CS-G4 ERC/parity | **PASS** | ERC on the **root** sheet: 0 violations, 0 unconnected. U5–U8 netlist parity: the 4 apparent mismatches are all pin 5 (`CT`) **unconnected on both sides** — the schematic names it `unconnected-(…)`, the board leaves the pad netless — so there are **0 real parity defects**. A naive string comparison reports 4 phantom defects. |
| CS-G5 fab | **PASS** | A **valid fab package generates** with stock `kicad-cli` — no external tool needed, so the earlier BLOCKED was wrong. 23 layer files + `.gbrjob`, 4 copper layers, Excellon METRIC drill with 9 tools 0.20–0.85 mm, 373-footprint `.pos`. Edge_Cuts extent 101.60 mm vs board bbox 101.70 mm, the 0.10 mm being edge-cut line width. **Not a fab-readiness claim** — CS-G3 still fails. |
| CS-G6 EM | **PARTIAL** | Full-wave engines (openEMS, CSXCAD, HFSS, FEKO, meep) genuinely absent, but **`scikit-rf` 1.9.0 is installed** and was used — my original "no EM tool" was too broad. Transmission-line checks done; no field solve, no S-parameters. |
| CS-G7 RTL | **FAIL** | Icarus 21/21 and firmware 91,648 B / 0 warnings both stand, but the Verilator leg was a **false pass**. `verilog/v2_fft_packetizer.v` drives `wr_idx` from block #1 (L78, at L80 and L94) and block #4 (L140, at L168), and `bins_dropped` from #1 (L96) and #4 (L148). `MULTIDRIVENPROC` is **disabled by default** in Verilator — a deliberately double-driven control module fails to raise it under both 5.040 and 5.48 — so neither my "5.040 lacks the code" nor Fable's "5.054 catches it" explains the miss. Correct fix: pass `-Wmultidrivenproc` explicitly **and** add a known-bad control module to the gate tests. |
| CS-G8 frequency | **PASS** | 7 conversion rows, **14 consistency checks, 0 inconsistencies**. Every `LO1 = RF ± 2426.25 MHz` and `IF2 = |IF1 − LO2| = 26.25 MHz` closes exactly. Coverage union **10–10000 MHz, zero gaps**. IF2 26.25 MHz sits below the 50 MHz Nyquist for fs = 100 MSPS. HIGH_C 6800–7350 / 7150–9200 overlap is intentional dual-side coverage. **Arithmetic only** — spurious responses and image rejection not established. |
| CS-G9 issues | **BLOCKED** | Issues are **enumerated** against the gates that would close them, but not dispositioned: closing an issue is the owner's decision, not the auditor's. Clusters: (a) the return-path/stackup conflict already tracked as CS-G3, (b) footprint-library drift covered by the 199-item identity waiver, (c) documentation/claim drift. |

**Code-SDR verdict: CS-G2 PASS on connectivity, CS-G7 FAIL on the RTL leg, CS-G3 FAIL on stackup.**

## aero-multiphysics-workbench

| Gate | Status | Evidence / reason |
|---|---|---|
| AM-G1 mypy | **FAIL** | The correct invocation is `package.json`'s `typecheck:py` run from `services/api`, not `mypy .` from the root — my original "not reproducible" was my own invocation error. Run correctly it does not reach 0 errors. |
| AM-G2 pytest | **FAIL** | Correct invocation is from `services/api` (its `pyproject.toml` supplies `pythonpath`/`testpaths`). My original root-level `ModuleNotFoundError: examples.gas_turbine` was also an invocation error. 8 tests fail on native participant/CAD dependencies. |
| AM-G3 rotordynamics | **BLOCKED** | The rotordynamics solver stack is not installed on this host. |
| AM-G4 issues | **BLOCKED** | #59/#74/#84/#85/#97/#98 are **enumerated**, not dispositioned — owner decision. Extracted in `evidence/notrun-gates/raw/aero_issues.txt`. |
| AM-G5 coupling evidence | **BLOCKED** | No real convergence evidence exists, and none can be produced without the solvers named in AM-G3 plus a multi-day run. |

**aero verdict: both runnable gates FAIL; the rest are BLOCKED on missing solvers.** My two earlier "not reproducible" findings were my own invocation errors and are corrected in `coordination/CORRECTIONS.md`.

## Global

| Gate | Status | Evidence |
|---|---|---|
| G-A README matches measured state | **FAIL** | drone-mech `README`/`run_manifest.json` claim "Mesh OK" for a mesh that fails `checkMesh`; copperline README implies a 52-board corpus that is not committed; drone-arm `RELEASE_STATUS.md` is correct. |
| G-B every claim has evidence row | **PASS** | This file plus `EVIDENCE_INDEX.md`. Every gate above carries a command, a measurement, or a named missing dependency. No gate is asserted from the handoff. |
| G-C Fable's work untouched | **PASS** | No `audit/*` branch was checked out, modified, or force-pushed. Fable's aero commit `1621d26` is **not** an ancestor of any dsh-lead branch. All six work trees report 0 dirty files. |
| G-D no destructive git | **PASS** | No `reset --hard`, no force-push, no branch deletion, no history rewrite in any of the six repos. |
| G-E no interference in protected paths | **PASS** | `D:\CodeProjects` and `E:\1vm\TMP` were never written. |

---

## Bottom line

**54 gate rows, tallied programmatically from this file** (not hand-counted — an earlier
hand-count in this very document said 7/14/4/10/6 and was wrong; a reviewer caught it):

| verdict | count | gates |
|---|---:|---|
| **PASS** | **14** | RP-G0, DM-G2, C-G2, C-G3, C-G4, C-G6, CS-G2, CS-G4, CS-G5, CS-G8, G-B, G-C, G-D, G-E |
| **FAIL** | **22** | RP-G1, RP-G2, RP-G3, RP-G4, RP-G5, RP-G6, RP-G8, RP-G11, DM-G1, DM-G2b, DM-G7, DM-G8, DM-G9, DA-G1, DA-G4, C-G1, CS-G1, CS-G3, CS-G7, AM-G1, AM-G2, G-A |
| **PARTIAL** | **6** | RP-G9, RP-G10, DA-G2, DA-G3, DA-G5, CS-G6 |
| **BLOCKED** | **12** | RP-G7, RP-G12, DM-G3, DM-G4, DM-G5, DM-G6, DA-G6, C-G5, CS-G9, AM-G3, AM-G4, AM-G5 |
| **NOT RUN** | **0** | *none* |

### What changed in this round

**NOT RUN went 7 → 0; PASS went 11 → 14.** Two "BLOCKED" verdicts were **wrong and are retracted**:

- **CS-G5** was never blocked: `kicad-cli` exports gerbers, drill and position with no external tool.
  A complete, self-consistent package generates (Edge_Cuts 101.60 mm against a 101.70 mm board bbox).
- **DA-G5** rested on a false premise: I had said the drone-arm stackup was undefined. It is fully
  defined in the board file, and on that stackup **0.35 mm is a correct ~50 Ω width** — 48.61 Ω
  (Hammerstad), 53.98 Ω (Wheeler), 51.23 Ω (scikit-rf MLine). The RF defect is the **reference
  plane** (0.00% over GND), which is a different finding from an impedance error, and conflating
  the two would have been the wrong conclusion.

**RP-G5 was run, not merely discussed.** The frozen gate rejects the saved checkpoint on five
independent metrics, and all three negative controls behave correctly — including two that score
*high* novelty (0.30 and 0.61) and are caught only by structural articulation. The model's novelty
is exactly equal to the degenerate `constant_union` control.

**RP-G6 was downgraded PARTIAL → FAIL** on the evidence that the decoder, not the generator, is the
bottleneck (GT 0.433 vs decoder-on-true-latents 0.006).

**Two gates closed by running the command rather than reasoning about it:** CS-G4 (ERC on the root
sheet is 0/0; the 4 apparent U5–U8 parity defects are pin 5 unconnected on both sides) and CS-G8
(14 arithmetic consistency checks, 0 inconsistencies, coverage union 10–10000 MHz with no gaps).

Three gates remain that **no work on this host can close**: RP-G7 (needs WSL OpenFOAM), DM-G3/DM-G4
(need ~6.8 days per anchor), and DA-G6 (needs a physical VNA). The issue-triage gates (C-G5, CS-G9,
AM-G4) are **BLOCKED by authority, not by tooling** — closing an issue is the owner's decision.


**Which gates genuinely moved from FAIL to PASS on measured evidence:** DM-G2 (`checkMesh` →
`Mesh OK`), CS-G4, CS-G5 and CS-G8. And DM-G2 still carries a material caveat, because a 100%
tetrahedral mesh with no prism layers is not a valid transonic wall-function mesh regardless of
what `checkMesh` says (see DM-G2b, and the engineering review that flagged it).

Every other change in this file is a **correction downward** — claims that were too generous,
including several of my own.

### What this file does and does not establish

It establishes, per gate, whether a claim was **reproduced on this host** and what the command
printed. It does **not** establish that any repo is production-ready, and for drone-arm it
establishes the opposite: **not fab-ready**, on the strength of a stale Gerber package, six missing
ESC connectors, a crossed CAN pair, and an undefined stackup.

### Known gaps a reviewer should weigh

- **1 NOT RUN + 12 BLOCKED = 13 of 54 gates (24%) were not evaluated**, down from 19. Each
  carries a reason, and the reasons are now split into *missing tool/hardware* (RP-G7, DM-G3,
  DM-G4, DM-G5, DM-G6, DA-G6, AM-G3, AM-G5), *missing authority* (C-G5, CS-G9, AM-G4 — closing
  an issue is the owner's call), and *not yet done* (RP-G10, RP-G12).
- **Issue triage was not done.** copperline #27–#48, Code-SDR #69+, aero #59/#74/#84/#85/#97/#98
  are undispositioned. Dispositioning them needs the owner's judgement, not mine, so they are
  listed as NOT RUN rather than silently closed.
- **One reproduce command in this bundle hangs.** `evidence/drone-mech/dm-g2/tools/run-checkmesh.ps1`
  does `rm -rf` + `cp -r` of a ~600 MB template across the Docker 9p mount, which wedges; the
  container holds the deleted mount and `work-c1` disappears. Copy the case **container-side**
  instead. The mesh result itself is unaffected and was independently reproduced twice.
- **Stale status boards exist.** `SWARM_STATUS.md` (root and `coordination/`) still carries the
  pre-correction figures from 2026-11-12 and is superseded by this file.




