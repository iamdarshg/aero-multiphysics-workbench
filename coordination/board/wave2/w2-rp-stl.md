# W2 · research-paper — audit of the 510 MB unaudited STL/STP

Repo: `E:/engineering-portfolio-audit/repos/research-paper`
Branch: `work/2026-11-11` (verified via `git rev-parse --abbrev-ref HEAD`; read-only, nothing committed)
Evidence dir: `E:/engineering-portfolio-audit/evidence/w2-rp-stl/`
Wave-1 numbers are cited, not re-derived.

---

## 0. Headline

**All 51 mesh files (510.56 MB) are NASA CRM _ground-truth reference geometry_ plus four
hand-made test fixtures. Not one of them is a generated sample.** The generative claim
(45 draws) is carried by voxel arrays, not by any checked-in mesh, so "are there 45 STL?"
has the answer **zero**, and the 36-vs-45 arithmetic is not the discrepancy it looks like.

The real discrepancies found are different and are reported in §6.

---

## 1. Inventory

Command (all counts below are from this):

```
Get-ChildItem -Path $repo -Recurse -File -Force -Include *.stl,*.STL,*.stp,*.STP,*.step,*.STEP
```

| Metric | Value |
| --- | --- |
| Total files | **51** |
| `.stl` | **36** |
| `.stp` | **15** |
| Total bytes | **535,362,331** |
| Total | **510.56 MB** (0.4986 GiB) |
| Distinct SHA-256 | **47** |
| In manifest | **47 / 51** |

Full per-file inventory with size + SHA-256: `inventory.csv`
Hash-vs-manifest verdict per file: `hash-vs-manifest.csv`

### Where they live

| Group | Files | Bytes | What it is |
| --- | ---: | ---: | --- |
| `docs/dataset/nasa_crm_whole_aircraft/step/**` | 15 | 519,962,427 B = 495.87 MB | NASA-published STEP source, 1 per config |
| `.../stl_source/**` | 15 | 5,263,210 B = 5.02 MB | semispan / as-published source STL |
| `.../stl_full/**` | 15 | 7,597,160 B = 7.25 MB | mirrored full-span STL derived from source |
| `.../stl_half/**` | 2 | 398,918 B = 0.38 MB | byte-identical copies of `stl_source` |
| repo root | 4 | 2,140,616 B = 2.04 MB | test fixtures (see §5) |

Check: 495.87 + 12.65 + 2.04 = 510.56 MB ✔

The 15 STP dominate: **495.87 MB of 510.56 MB (97.12%)** is the STEP corpus. The whole STL
side (all 32 dataset STL) is only 12.65 MB — so the "510 MB" headline is 97% uncompressed
STEP text, not mesh.

### Composition (36 STL)

`15 source + 15 full + 2 half + 4 root fixtures = 36` ✔

### Code path that writes / reads them

| Path | Role |
| --- | --- |
| `CLI/build_nasa_crm_whole_aircraft_context.py:831-832` | defines `stl_source_root` / `stl_full_root` |
| `CLI/build_nasa_crm_whole_aircraft_context.py:873-874` | writes `stl_source/<id>.stl` and `stl_full/<id>_full.stl` |
| `CLI/build_nasa_crm_whole_aircraft_context.py:747-762` | dataset/manifest/provenance/report output roots |
| `docs/dataset/nasa_crm_whole_aircraft_manifest.jsonl` | 15 records; declares `full_stl_sha256`, `source_stl_sha256`, `step_sha256`, `voxel_sha256`, `zip_sha256` |
| `scripts/agent_d_validity_harness.py:23` | reads `docs\dataset\nasa_crm_whole_aircraft\voxels` (downstream of the STL) |
| `tests/test_manifest_validator.py:104`, `tests/test_diversity_novelty_gate.py:48` | validate the manifest |

Writer is the CRM builder; the readers are the validity harness and the two manifest
tests. **No generative-model code path writes an STL into this repo.**

---

## 2. Provenance — ground truth, generated, or hand-made?

**Ground-truth NASA CRM.** Three independent lines of evidence:

1. **Manifest hash agreement.** 47 of 51 files hash exactly to a SHA-256 declared in
   `nasa_crm_whole_aircraft_manifest.jsonl` (`hash-vs-manifest.csv`). The 4 that do not are
   the root fixtures. 15 records → each record declares 15 distinct `step_sha256` values and
   15 distinct `full_stl_sha256` values, so the manifest is 1:1 with the files.
2. **Producer strings.** CRM STL headers carry
   `STL Exported by Open CASCADE Technology [dev.opencascade.org...}` — matching the
   manifest's `geometry_provenance` ("exported to STL with CadQuery/OpenCascade"). The
   provenance file pins `cadquery 2.7.0`, `trimesh 4.10.0`, `torch 2.9.1+cu130`.
3. **Derivation arithmetic.** `stl_full` triangles = exactly 2 × `stl_source` triangles
   (e.g. `crm_hs_dpw6_cf`: 2626 → 5252), consistent with `mirror_info.mode =
   mirror_semispan_source` with `mirror_axis_label = "y"`. The full-span files are
   *manufactured by mirroring the source*, not independent geometry.

Source URLs in the manifest are NASA-hosted
(`commonresearchmodel.larc.nasa.gov/...`), split labels `test`/`val`/`holdout`, and
`source_license` = "not_stated_public_nasa_download_bounded_by_nasa_data_use_policy".

**Verdict: 0 generated samples, 0 hand-authored references among the 47 dataset files.**

---

## 3. Duplicates by hash

**4 duplicate pairs → 8 files collapse to 4 distinct hashes → 47 distinct of 51.**

| SHA-256 (16) | Bytes | Files |
| --- | ---: | --- |
| `1C7723C46A786943` | 1,515,034 | `stl_full/crm_hl_ntf_2p7_landing_full.stl` = `stl_source/crm_hl_ntf_2p7_landing.stl` |
| `BC5639A10EBC102F` | 1,413,134 | `stl_full/crm_hl_ntf_2p7_takeoff_full.stl` = `stl_source/crm_hl_ntf_2p7_takeoff.stl` |
| `41C8EC5EF8D14118` | 199,984 | `stl_half/crm_hl_reference_ldg.stl` = `stl_source/crm_hl_reference_ldg.stl` |
| `6C52E3A0666869D2` | 198,934 | `stl_half/crm_hl_reference_tko25.stl` = `stl_source/crm_hl_reference_tko25.stl` |

**These are not generative collapse.** All four are declared, benign redundancy:

- The two `2p7` cases carry `mirror_info.mode = copy_fullspan_source` — the source *is*
  already full-span, so the builder copies rather than mirrors, and `full` == `source`
  by construction (manifest shows identical `full_stl_sha256` / `source_stl_sha256`).
- The two `stl_half` files are an intermediate naming convention left alongside
  `stl_source`; their hash is the one the manifest calls `source_stl_sha256`.

So: **duplicate hash count = 4 pairs**, and none is evidence of a collapsed generator,
because none of the 51 files is an output of the generator. The generative-collapse
evidence lives in the voxel arrays and is already in the gate (§4).

---

## 4. Does any claim depend on these files? Does the count match?

### Yes — one claim depends on them directly, and it names the files.

From `paper/CLAIMS_EVIDENCE_MATRIX.md:66`:

> Validity screen re-audited 2026-11-01 (harness `scripts/agent_d_validity_harness.py`):
> frozen NASA CRM whole-aircraft voxels **15/15 pass**; bundled root STLs **0/4 fail**
> (biplane: symmetry, normalization_margin, tail_body_plausibility; F-18: normaliz...

Repeated at `paper/SCIENTIFIC_GATE_STATUS.md:34`, `paper/REVIEWER_KIT.md:66` and `:114`,
`paper/CLAIMS_EVIDENCE_MATRIX.md:51`, and in the paper text itself (`main.pdf`):

> the screen also stays bounded: frozen NASA CRM whole-aircraft voxels pass 15/15, while
> the bundled root STLs (biplane, F-18, cylinder, 20mm cube) fail 0/4, with quantified
> failure modes such as...

The four fixtures are named individually in the paper, so the C09 screen-boundary claim
**rests on these exact 4 files**, and the 15 CRM voxels are produced by
`AircraftDesignDataset._voxelize_stl` from the 15 `stl_full` files. Dependency: **yes**, and
it is the strongest provenance link in the package — every number in it is hash-pinned.

Secondary dependency: `biplane.stl` is the "frozen biplane corpus" used for the LBM
reference-area normalization discussion (`results-and-discussion.tex:364`, grids 16/24/32/64).
`20mm_cube.stl` is the geometry behind `benchmark_results/multi_stl_adaptive_latest.json`
(adaptive-mesh sweep, 5 cases); `F-18_Hornet.stl` is behind
`benchmark_results/fa18_timing_report.md` (32³, 200 steps, 9.69× vs OpenFOAM).

### Count vs claimed

| Claim unit | Claimed | Present as mesh | Present as voxel |
| --- | ---: | ---: | ---: |
| Generated draws | 45 (`45/45` pass) | **0** | not checked in |
| Held-out records | 9 | 0 | 9 ✓ |
| Ground-truth CRM configs | 15 | 15 STP + 15 STL ✓ | 15 `.npy` ✓ |
| Bundled negative-control STL | 4 | 4 ✓ | — |

**The paper never claims 45 STL.** Its 45 "artifacts" are voxel arrays, and the export
path writes `constant/triSurface/design.stl` only at runtime (`main.pdf`: "emits a concrete
OpenFOAM case with the generated STL in `constant/triSurface/design.stl`"). Repo-wide there
are exactly **15 `.npy`** files, all ground-truth CRM voxels — **zero generated voxel or mesh
artifacts are checked in.** So the 36-vs-45 gap is not a discrepancy; the correct statement
is that the 45-draw claim has no checked-in geometry at all, and its evidence is the gate
report, not files.

---

## 5. The four root fixtures (the only non-manifest meshes)

| File | Bytes | Kind | Triangles | Producer |
| --- | ---: | --- | ---: | --- |
| `20mm_cube.stl` | 1,521 | ASCII | ~29 | hand-written `solid model`, 20 mm cube |
| `test_cylinder.stl` | 190,327 | ASCII | — | hand-written `solid ascii` cylinder |
| `biplane.stl` | 1,864,984 | binary | 37,298 | no header; frozen LBM corpus |
| `F-18_Hornet.stl` | 83,784 | binary | 1,674 | `STL File created by netfabb ... UNITS=M` (third-party download) |

These are correctly described as fixtures, are deliberately the **negative controls** that
fail 0/4, and are not part of the dataset manifest. Their presence is defensible; their
unhashed/unmanifested status is a minor packaging gap.

---

## 6. Discrepancies and what could NOT be verified

### 6a. The paper and the gate file disagree on the same 45 artifacts

| File:line | Statement |
| --- | --- |
| `paper/SCIENTIFIC_GATE_STATUS.md:19` | "the 45 draws contain only **two** distinct voxel arrays" |
| `paper/SCIENTIFIC_GATE_STATUS.md:55` | "only **two** distinct voxel arrays among 45 draws; mean IoU ... 1.000" |
| `paper/SCIENTIFIC_GATE_STATUS.md:71` | "only **two** voxel arrays among 45, mean cross-condition IoU 1.000" |
| `paper/sections/results-and-discussion.tex:265` | "The 45 generated artifacts contain **five** distinct voxel arrays (maximum pairwise Hamming distance one voxel, mean pairwise IoU 0.99905)" |
| `main.pdf` (rendered) | same: "contain **five** distinct voxel arrays ... pairwise IoU 0.99905" |

Both statements describe the same 45 artifacts and give different counts (2 vs 5) and
different IoU (1.000 vs 0.99905). The most likely reconciliation is that "two" counts
distinct *condition-level* arrays while "five" counts distinct *bit-level* arrays (the tex
adds "within a condition the five seeds are not bit-identical, yielding 1–4 distinct arrays"),
but the repo presents them as the same quantity and does not reconcile them. Either way the
scientific conclusion is unchanged and honest — the generator is collapsed — but the count is
not stated consistently across files in the same submission. **This is a real reporting defect.**

### 6b. The briefed figures 35/576 (6.08%) and 9.9% "Pairs-IoU" are NOT in this tree — UNVERIFIED

The assignment states the paper's files report "35 distinct samples of 576 (6.08%)" and a
"9.9% figure [that] is a Pairs-IoU column". I could not confirm either, and I am not going to
restate them as findings. Search evidence:

```
# standalone token, all text formats in the repo
Select-String -Pattern '\b576\b'  -> only "7,576 unpack_hook calls"
                                     (.superpowers/sdd/optimization-plan/p6j-report.md:1,40;
                                      docs/archive/2026-09/residual-blackbox-report.md:86,100)
Select-String -Pattern '6\.08|35 distinct|distinct samples' -> 0 relevant hits
Select-String -Pattern 'Pairs-IoU|PairsIoU|pairs_iou'       -> 0 hits, repo-wide
Select-String -Pattern '9\.9\s*%|0\.099'                    -> 0 relevant hits
```

PDF text extraction (`pymupdf`, texts saved as `main.pdf.txt` / `research-paper.pdf.txt`):

| Document | Pages | `576` | `6.08` | `9.9%` | `Pairs` | `distinct` |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `paper/main.pdf` | 17 | 0 | 0 | 0 | 0 | 8 |
| `paper/research-paper.pdf` | 14 | 0 | 0 | 0 | 0 | 0 |

All 8 "distinct" hits in `main.pdf` are the "five distinct voxel arrays" / "six distinct
voxel arrays" / "distinct-geometry count" family. `35/576 = 6.076%` is arithmetically
self-consistent, so the figure is probably real *somewhere* — but it is **not in this repo at
`work/2026-11-11`, in either PDF, or in any manifest/benchmark JSON**, so I cannot tie it to
these files. Flagging for the delegating agent: this claim may belong to a different branch,
a different repo, or an earlier revision.

### 6c. Other UNVERIFIED items

- **No manifest for the 4 root fixtures** — no hash, no provenance record. Their 0/4 role is
  documented; their origin is not.
- **`stl_half/` is a dead naming convention** — 2 files, both byte-identical to `stl_source`.
  No code path was found that reads `stl_half`; the builder writes `stl_source`/`stl_full`
  only (`build_nasa_crm_whole_aircraft_context.py:873-874`). Harmless but misleading.
- **I did not open the 486 MB of STEP** beyond header/manifest-hash verification; I did not
  re-export STEP→STL to check the tolerance used (`cad_export_tolerance 0.5`,
  `angular_tolerance 0.8` in provenance). Mesh fidelity of `stl_*` vs `step` is unverified.
- **I did not re-run** `scripts/agent_d_validity_harness.py`, so the "15/15 pass / 0/4 fail"
  numbers are **cited from** `CLAIMS_EVIDENCE_MATRIX.md:66`, not re-measured by me.
- **No `build/` tree exists** in the checkout, so the 45-draw artifacts, the 20-record
  reference bundle and `grounded_corpus/generated_voxels/*.npy` are all absent and could not
  be inspected at all.

---

## 7. Bottom line

The 510 MB is **legitimate ground truth, correctly hashed, and the one claim that cites it
(15/15 CRM vs 0/4 bundled STL) is real and traceable**. There is no generative mesh to
collapse — the "duplicates" are 4 declared artifacts of the mirror/copy pipeline, not
generator failures. The generator's collapse is a *voxel-level* fact already recorded by the
gate (2 or 5 arrays out of 45, IoU ≈ 1.000), and the paper reports it honestly. The defects
worth escalating are (i) the gate-vs-paper 2-vs-5 inconsistency, and (ii) the briefed
35/576/6.08% and 9.9%-Pairs-IoU figures being absent from this branch entirely.