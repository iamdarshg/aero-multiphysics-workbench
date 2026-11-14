# HF2 · research-paper — size-unit hotfix + provenance re-verification

Supersedes the size arithmetic and §6a of `E:/engineering-portfolio-audit/evidence/w2-rp-stl/REPORT.md`.
Repo `E:/engineering-portfolio-audit/repos/research-paper`, branch `work/2026-11-11`, head `8c50ca4`.
Read-only on git: nothing committed, no `audit/*` branch touched, nothing written into the repo.
Board numbers are cited from `AGENT_BOARD.md`, not re-derived.

## 0. Verdicts

| question | verdict |
| --- | --- |
| SIZE | **CORRECTED.** 535,362,331 B = **535.36 MB** = 510.56 MiB. The old "510.56 MB" was MiB labelled MB. One unit (MB) now used everywhere below. |
| ZERO_GENERATED | **CONFIRMED**, per file class. 0 of 51 meshes is a generated sample; 47 are hash-exact ground truth, 4 are hand/third-party fixtures. |
| TWO_OR_FIVE | **FIVE is right.** `main.tex:32`, `results-and-discussion.tex:265`, `conclusion.tex:3`, rendered `main.pdf` are correct. **The wrong document is `paper/SCIENTIFIC_GATE_STATUS.md` (`:19`, `:55`, `:71`)** — and the three summaries that copied it: `FINAL_RUN_GATES.md:24,:40`, `CLAIMS_EVIDENCE_MATRIX.md:15,:82`, `REVIEWER_KIT.md:93`. |
| DUPLICATES | 4 declared pairs, all byte-verified, all declared in an artifact. **None bears on the generative claim** — none of the eight files is a generator output. |

---

## 1. SIZE — the defect and the corrected table

### Convention (stated once, used everywhere below)

**1 MB = 10^6 B; 1 MiB = 1,048,576 B. All sizes in this report are MB (10^6) except the
byte column and the one quoted MiB equivalence.** The old report mixed the two: it wrote
`535,362,331` bytes and then labelled `535,362,331/1,048,576 = 510.561` as "MB". The
number 510.56 is a **MiB** figure; its MB value is 535.36.

```
535,362,331 B / 10^6     = 535.362331 MB
535,362,331 B / 1,048,576 = 510.561 MiB = 0.49859 GiB
510.561 * 1.048576        = 535.362  (MB)   -- cross-check
```

### Corrected inventory (recomputed by me, not copied)

Command: enumerate `*.stl,*.stp,*.step` under the repo, `Get-FileHash -Algorithm SHA256`,
sum by class → `sizes.csv`, `stl_probe.json`, `manifest_verify.json` in this dir.

| class | files | bytes | **MB** | MiB (for reference only) | share |
| --- | ---: | ---: | ---: | ---: | ---: |
| `step/**` | 15 | 519,962,427 | **519.96** | 495.87 | 97.12 % |
| `stl_source/**` | 15 | 5,263,210 | **5.26** | 5.02 | 0.98 % |
| `stl_full/**` | 15 | 7,597,160 | **7.60** | 7.25 | 1.42 % |
| `stl_half/**` | 2 | 398,918 | **0.40** | 0.38 | 0.07 % |
| repo root (fixtures) | 4 | 2,140,616 | **2.14** | 2.04 | 0.40 % |
| **TOTAL** | **51** | **535,362,331** | **535.36** | 510.56 | 100 % |

Arithmetic check, exact to the byte: `519,962,427 + 15,399,904 (all 36 STL) = 535,362,331` ✔
STL side = **15.40 MB**; the 32 dataset STL = **13.26 MB**; STEP = **97.12 %** of bytes.
Distinct SHA-256 = **47** of 51 (see §4).

Everything the old report said in "MB" that was really MiB, restated in MB:
`495.87 → 519.96` · `5.02 → 5.26` · `7.25 → 7.60` · `0.38 → 0.40` · `2.04 → 2.14` ·
`510.56 → 535.36`. Prose consequence: the "510 MB headline" is a **535 MB** headline, and
it is still 97.12 % uncompressed STEP text — the substance of that paragraph survives; only
the unit was wrong.

### Board cross-reference

`AGENT_BOARD.md:62` already carries the safe form — `51 files, 535,362,331 B, 47 hashes,
4 duplicate pairs` — and `:78` states the correction correctly (`510.56 MiB = 535.36 MB,
not MB`). I cite both; nothing in §1 contradicts the board.

**BOARD CORRECTION:** `AGENT_BOARD.md:140` still reads `research-paper 51 files / 510 MB
(36 STL + 15 STP)`. That is the same MiB-as-MB slip line 78 corrects, left in the corpus
paragraph. It should read **535 MB (36 STL + 15 STP)** — bytes 535,362,331, per `:62`.
No other board line is affected: `:139` (471 files / 1.86 GB) is outside my unit scope and
`da-gerbers` was already corrected at `:79`.

---

## 2. ZERO_GENERATED — confirmed per file class

Claim under test: all 51 meshes are NASA CRM ground truth plus hand-made fixtures, and
**zero** are generated samples.

### 2.1 The evidence table, per class

| class | n | provenance evidence | generated? |
| --- | ---: | --- | --- |
| `step/**` | 15 | **15/15 sha256 == manifest `step_sha256`**; NASA-hosted `source_url`; `source_license` = not_stated_public_nasa_download… | no |
| `stl_source/**` | 15 | **15/15 sha256 == manifest `source_stl_sha256`**; header `STL Exported by Open CASCADE Technology [dev.opencascade.org]` on 15/15; semispan bbox (Y ≈ 29,4xx mm) | no |
| `stl_full/**` | 15 | **15/15 sha256 == manifest `full_stl_sha256`**; triangle count is exactly **2 × its source** on the 13 `mirror_semispan_source` records and exactly **1 × source** on the 2 `copy_fullspan_source` records — 15/15 arithmetic identity | no |
| `stl_half/**` | 2 | **byte-identical to the two `stl_source` files** (hashes `41c8ec5e…`, `6c52e3a0…`), and declared as `hashes.half_stl_sha256` in `reports/crm_hl_reference_ldg.json:156` / `crm_hl_reference_tko25.json:156` with `mirror_info.half_faces = 3998` | no |
| root fixtures | 4 | non-manifest, each with its own declared origin (below) | no |

Count check: `15 + 15 + 15 + 2 + 4 = 51` files, `36 STL + 15 STP` ✔.

### 2.2 The geometry test that would catch a generated mesh

The repo's generator emits **voxel arrays**; its only mesh path is
`CLI/aircraft_diffusion_cfd.py:11448` → `<case>/constant/triSurface/design.stl`, written at
run time into an OpenFOAM case. A voxel-derived mesh is a block surface: nearly every facet
normal exactly axis-aligned and a triangle count a multiple of 2 per exposed face. So: if a
generated mesh were smuggled into the tree, its axis-aligned facet fraction would be near
1.0.

Measured (`probe_stl.py` → `stl_probe.json`), fraction of facets whose normal is exactly
one-axis:

| group | axis-aligned facet fraction | triangles |
| --- | --- | --- |
| 30 dataset CRM STL | **0.0000 – 0.0161** (max 1.61 %) | 2,517 – 30,299 |
| `biplane.stl` (frozen LBM corpus) | 0.0180 | 37,298 |
| `F-18_Hornet.stl` (netfabb download) | 0.0108 | 1,674 |
| `test_cylinder.stl` (hand-written ASCII) | 0.3294 | 686 |
| `20mm_cube.stl` (hand-written ASCII) | **1.0000** | 12 |

**The only block-signature mesh in the corpus is the 20 mm cube, and its own text says
`solid model` — it is a declared fixture, not a sample.** Every smooth mesh is hash-pinned
to the NASA manifest or byte-pinned to one.

### 2.3 No generated voxel is checked in either

Repo-wide census (`voxel_census.py` → `voxel_and_dups.json`): exactly **15 `.npy`** files
exist, all shape `(32,32,32)`, **all 15 manifest-declared and all 15 sha256-matching
`voxel_sha256`**. There is no `build/` tree (gitignored, `.gitignore` `build/`), no
`artifacts/`, no `generated_voxels/`, no `triSurface/` dir. The 45 generated draws that the
paper's Gate 7 rests on **do not exist in this checkout** — so the "0 generated meshes"
claim is not merely true, it is the only thing that could be true here.

**Verdict: CONFIRMED — 0 generated samples of 51.** Scope note, stated plainly: this
confirms the *mesh corpus*. It is not evidence about the 45 draws, which are absent (§3.4).

---

## 3. TWO_OR_FIVE — the last open contradiction, resolved

### 3.1 Complete statement inventory (nothing else in the tree speaks to this count)

| file:line | claim |
| --- | --- |
| `paper/main.tex:32` (abstract) | "the 45 draws contain **five** near-identical voxel arrays" |
| `paper/sections/results-and-discussion.tex:265-267` | "contain **five** distinct voxel arrays (maximum pairwise Hamming distance one voxel, mean pairwise IoU 0.99905); within a condition the five seeds are not bit-identical, yielding **1–4** distinct arrays" |
| `paper/sections/conclusion.tex:3` | "the 45 draws contain **five** near-identical voxel arrays" |
| `paper/main.pdf` (rendered) | same as above — text lines 29, 1119-1121, 1853 of `../w2-rp-stl/main.pdf.txt` |
| `paper/SCIENTIFIC_GATE_STATUS.md:19` | "the 45 draws contain only **two** distinct voxel arrays" |
| `paper/SCIENTIFIC_GATE_STATUS.md:55-56` | "only **two** distinct voxel arrays among 45 draws; mean IoU across held-out conditions **1.000**" |
| `paper/SCIENTIFIC_GATE_STATUS.md:71` | "only **two** voxel arrays among 45, mean cross-condition IoU **1.000**" |
| `paper/FINAL_RUN_GATES.md:24` | "(**2** distinct arrays among 45 draws; mean IoU across the nine held-out…)" |
| `paper/FINAL_RUN_GATES.md:40` | "one distinct geometry per condition/seed (**2** distinct arrays in 45)" |
| `paper/CLAIMS_EVIDENCE_MATRIX.md:15` | "the 45 draws contain only **2** distinct arrays" |
| `paper/CLAIMS_EVIDENCE_MATRIX.md:82` | "the 45 generated voxel arrays contain **2** distinct geometries (mean IoU … **1.000**)" |
| `paper/REVIEWER_KIT.md:93` | "there are only **2** distinct arrays among 45, mean cross-condition…" |

There is no third value anywhere in the tree; a repo-wide search for `distinct voxel array`,
`Hamming`, `0.99905`, `distinct geometr*` returns only these.

### 3.2 Why the two families cannot both be right

They differ on **four** coupled quantities, not one — so this is not a rounding dispute:

| quantity | "two" family | "five" family |
| --- | --- | --- |
| distinct arrays in 45 | 2 | 5 |
| within-condition distinct | 1 ("one geometry per condition/seed") | **1–4** |
| mean pairwise IoU | 1.000 | 0.99905 |
| max pairwise Hamming | not stated | 1 voxel |

Distinct-by-hash arrays must differ in ≥1 binarised voxel, and two arrays one voxel apart
have IoU `(N-1)/(N+1) < 1`. So "5 + 0.99905 + 1–4/condition" and "2 + 1.000 + 1/condition"
are alternative *measurements* of the same 45 arrays, not two renderings of one.

**The old report's reconciliation (`w2-rp-stl/REPORT.md:203-206`, "two = condition-level,
five = bit-level") is invalid and I retract it.** If a *single* condition already contains
1–4 bit-level distinct arrays, then the global bit-level total is ≥ 4 and can never be 2.
A condition-level count cannot be 1–4 while the bit-level total is 2 either.

### 3.3 Verdict, and the reasoning tier

**FIVE is correct. The document that is wrong is `paper/SCIENTIFIC_GATE_STATUS.md`**, whose
`:19` sentence is the origin of the "two"; `FINAL_RUN_GATES.md`, `CLAIMS_EVIDENCE_MATRIX.md`
and `REVIEWER_KIT.md` repeat it and are wrong by copy.

Why this way round:

1. **It is one source against one source, not four against one.** All four "two" documents
   give the identical triple (2 / IoU 1.000 / one geometry per condition-seed) and all four
   cite the *same absent* artifact `evidence/research-paper-publish/GENERATOR_RECOVERY_2026-11-05.md`.
   They are a restatement chain, not four independent measurements.
2. **The "five" set is internally a *recount*, and its direction explains all four numbers
   at once.** The "two" set asserts seeds are bit-identical-per-condition and IoU is exactly
   1.000; the "five" set asserts they are *not* bit-identical (1–4 distinct/condition, max
   Hamming one voxel) and IoU is 0.99905. A bit-level recount that discovers last-bit
   differences moves every one of those four numbers in exactly the direction the tex
   records: count 2→5, IoU 1.000→0.99905, per-condition 1→1–4, and it has to *state* a max
   Hamming distance to say how near-identical. The tex is the only document that carries the
   mechanism; the summaries carry only the pre-recount headline.
3. **The tex's companion counts are reproducible from checked-in files — I reproduced them.**
   Using the repo's own convention (`diversity_novelty_gate.array_hash`, binarise >0.5,
   sha256 of the packed array) on the 15 checked-in `voxels/*.npy`:
   - 9 holdout records → **exactly 6 distinct** arrays (`ae300/ae350/ae375/ae400` collapse to
     one hash `d966c83f57420717`) — exactly `main.tex:32`'s "nine held out (**six** distinct
     voxel arrays)" and `results-and-discussion.tex:268`'s "four aeroelastic variants are
     sub-voxel duplicates at 32³".
   - training union (6 records) = **787 occupied voxels**, covering **98.59–99.43 %** of every
     holdout record — exactly the tex's "covers **98.6–99.4 %**" (`:277`).
   Three independent numbers from the same measurement pass, all exact. A prose block that
   computes the ground-truth side correctly is the credible witness for the generator side.
4. **Rendering position.** "five" is in the abstract, the results section, the conclusion and
   the compiled PDF. "two" survives only in governance summaries. Stale summary is the common
   failure mode; a stale abstract that also compiled into the submitted PDF is not.

**Tier: inference (document forensics + partial recomputation), not a recomputation of the
count.** See 3.4.

### 3.4 What could still overturn this — one command, when the arrays exist

The 45 arrays are **not in this checkout**: `evidence/` does not exist (`Test-Path` false),
`build/protocol_final/` is gitignored, `artifacts/` does not exist, the only `runs/` leftovers
are 21 tfevents files of 88–2,600 B, and no file anywhere carries `array_sha256` /
`distinct_array_count` outside the gate code itself (repo-wide grep). So the
generator-side count cannot be re-derived here, and I will not present §3.3 as measured.

The decisive test, when the artifacts are recovered:

```python
import numpy as np
from diversity_novelty_gate import diversity_metrics   # scripts/
arrays = [np.load(p) for p in forty_five_paths]        # 9 conditions x 5 seeds
print(diversity_metrics(arrays))   # distinct_array_count, pairwise_iou_mean
```

`distinct_array_count == 5` and `pairwise_iou_mean == 0.99905` confirms this report;
`== 2` / `1.000` voids it — **and in that case the paper's abstract, results, conclusion and
rendered PDF are all wrong, which is a retraction-level defect rather than a summary typo.**
Either way the contradiction must not ship: one of the two families has to be deleted, not
averaged.

Note in passing (evidence, not proof): the frozen gate sets `diversity_min_distinct = 5`
(`scripts/diversity_novelty_gate.py:22`) — a threshold of exactly 5 is what one declares
after measuring 5, and `corpus_report` fails the corpus outright below it (`:168`).

---

## 4. The 4 declared hash-duplicate pairs

Measured myself: 51 files → **47 distinct sha256**, i.e. **4 two-file groups, 8 files →
4 hashes**. Sizes are exact byte counts and both members are byte-identical (not merely
same-hash-by-declaration).

| # | sha256 (16) | bytes | pair | why it is a duplicate |
| --- | --- | ---: | --- | --- |
| 1 | `1C7723C46A786943` | 1,515,034 | `stl_full/crm_hl_ntf_2p7_landing_full.stl` = `stl_source/crm_hl_ntf_2p7_landing.stl` | record declares `mirror_info.mode = copy_fullspan_source`, `full_faces = source_faces = 30,299`, `mirror_axis_label = null`; the NASA source for this config is **already full-span** (bbox Y 1,590.92 mm, not half of it), so the builder copies instead of mirroring. Manifest declares `full_stl_sha256 == source_stl_sha256` in that same record. |
| 2 | `BC5639A10EBC102F` | 1,413,134 | `stl_full/crm_hl_ntf_2p7_takeoff_full.stl` = `stl_source/…takeoff.stl` | same mechanism, `copy_fullspan_source`, 28,261 = 28,261 faces |
| 3 | `41C8EC5EF8D14118` | 199,984 | `stl_half/crm_hl_reference_ldg.stl` = `stl_source/crm_hl_reference_ldg.stl` | the semispan STL **is** the half file; `reports/crm_hl_reference_ldg.json` declares `hashes.half_stl_sha256 = 41c8ec5e…` and `mirror_info.half_faces = 3,998 = source_faces` |
| 4 | `6C52E3A0666869D2` | 198,934 | `stl_half/crm_hl_reference_tko25.stl` = `stl_source/crm_hl_reference_tko25.stl` | same, `half_faces = 3,977 = source_faces` |

The other 13 records are `mirror_semispan_source` with `mirror_axis_label = "y"`, and their
full STL has **exactly 2 ×** the source triangle count (verified for 13/13, e.g.
`crm_hs_dpw6_ae350` 2,626 → 5,252, `crm_hs_dpw6_cf` 2,626 → 5,252). That is why they are
*not* duplicate pairs: mirroring doubles the geometry, copying does not.

### Does any pair bear on the generative claim? No — and it cannot.

1. Every one of the eight files is NASA-supplied ground truth or a byte-identical copy of it.
   A generator output could not be hash-identical to a manifest-declared NASA blob.
2. **All four pairs are declared, not discovered.** Pairs 1–2 are declared inside the manifest
   record itself (identical `full_stl_sha256`/`source_stl_sha256`); pairs 3–4 are declared as
   `half_stl_sha256` in the very report JSON that produced them. There is no undeclared
   collapse anywhere in the mesh corpus.
3. None of the 51 meshes is a generator output (§2), and the generative claim is carried by
   **voxel arrays** — so a mesh-level hash collision carries zero information about sampler
   diversity, in either direction. Collapse of a sampler is visible only in
   `distinct_array_count`, which is §3's instrument, not this one.

Corollary the old report got right and I confirm: *the 36-vs-45 arithmetic is not a
discrepancy.* 45 draws = voxels; 36 = the STL population of this tree.

---

## 5. Corrections to the old report beyond the unit

Struck numbers stay visible; nothing is restated as if it had always been right.

| `w2-rp-stl/REPORT.md` | was | corrected |
| --- | --- | --- |
| §0, §1, §4, §7 ("510.56 MB", "510 MB") | MB | **535.36 MB**; 510.56 is MiB (§1) |
| §1 table, prose ("495.87 / 5.02 / 7.25 / 0.38 / 2.04 MB") | MiB values under an MB label | 519.96 / 5.26 / 7.60 / 0.40 / **2.14 MB** |
| §5 `20mm_cube.stl` | "~29" triangles | **12** triangles (6 faces × 2), ASCII, bbox exactly 20×20×20, axis-aligned fraction 1.0 |
| §5 `F-18_Hornet.stl` | header "… UNITS=M" | header is **`UNITS=MM`** (`STL File created by netfabb - http://www.netfabb.com UNITS=MM`), 1,674 triangles, bbox 236.463 × 83.560 × 340.088 |
| §5 `test_cylinder.stl` | triangles "—" | **686**, ASCII, bbox 15.0 × 15.0 × 10.0 |
| §2.1 "47 of 51 hash exactly to the manifest; the 4 that do not are the root fixtures" | imprecise | **45 path-claimed** (15 step + 15 source + 15 full, 45/45 exact) **+ 2 hash-only** (`stl_half`, hash equals a declared `source_stl_sha256` but no manifest path claims the file) **= 47**; the 6 path-unclaimed are those 2 plus the 4 fixtures. The 47 is right only as a *hash-value* count. |
| §3 bullet "no code path was found that reads `stl_half`; harmless but misleading" | half-true | no *code* reads it, but the two files **are declared** — `reports/crm_hl_reference_ldg.json:156` / `crm_hl_reference_tko25.json:156` carry `half_stl_path` + `half_stl_sha256` + `half_faces`. Not an orphan; a documented intermediate. |
| §6a reconciliation "two = condition-level, five = bit-level" | hypothesis | **invalid** — a condition containing 1–4 bit-level distinct arrays forces the global bit-level total ≥ 4 (§3.2) |
| §6a "Either way the scientific conclusion is unchanged" | editorial | the conclusion is unchanged, but the *count and the IoU* are not; one of the two families is simply wrong and must be deleted (§3.3) |

Carried forward unchanged (re-verified, not re-argued): 51 files / 36 STL + 15 STP / 47
distinct hashes / 4 duplicate pairs / fixtures are the 0-of-4 negative controls cited at
`CLAIMS_EVIDENCE_MATRIX.md:66` and in `main.pdf`; and the two `benchmark_results` fixture
dependencies (`20mm_cube.stl` → `multi_stl_adaptive_latest.json`, `F-18_Hornet.stl` →
`fa18_timing_report.md`).

Still UNVERIFIED, unchanged from the old report: the briefed `35/576 = 6.08 %` and
`9.9 % Pairs-IoU` figures are absent from `work/2026-11-11`; I did not re-run
`scripts/agent_d_validity_harness.py`, so "15/15 pass / 0/4 fail" remains cited from
`CLAIMS_EVIDENCE_MATRIX.md:66`; STEP→STL mesh fidelity (tolerance 0.5 / angular 0.8) was not
re-exported and is not verified.

---

## 6. Files and how to reproduce

In `E:/engineering-portfolio-audit/evidence/hf2-rp-stl/`:

| file | what it is |
| --- | --- |
| `REPORT.md` | this report |
| `sizes.csv` | 51 rows: path, class, bytes, sha256 (the size/hash source of truth) |
| `stl_probe.json` | per-STL: ASCII/binary, triangles, header, axis-aligned facet fraction, bbox, area stats |
| `manifest_verify.json` | **60/60** declared hashes exact (15 records × step/source/full/voxel) vs disk, per kind; 6 path-unclaimed files |
| `voxel_and_dups.json` | 15 `.npy` census (all manifest-matched) + the 4 duplicate groups |
| `probe_stl.py`, `verify_manifest.py`, `voxel_census.py` | the three probes, rerunnable as-is |

```powershell
# sizes + hashes (51 files)
Get-ChildItem -Recurse -File -Force -Include *.stl,*.stp,*.step | ForEach-Object {
  [pscustomobject]@{p=$_.FullName; b=$_.Length; sha=(Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName).Hash} }
# total / MiB / MB
(Get-ChildItem -Recurse -File -Force -Include *.stl,*.stp,*.step | Measure-Object Length -Sum).Sum
# probes
& 'C:\Program Files\KiCad\9.0\bin\python.exe' probe_stl.py
& 'C:\Program Files\KiCad\9.0\bin\python.exe' verify_manifest.py
& 'C:\Program Files\KiCad\9.0\bin\python.exe' voxel_census.py
```