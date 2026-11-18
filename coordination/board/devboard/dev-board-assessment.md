# dev-board — fab-readiness assessment

**Assessed:** 2026-11-17 · **Source (read-only):** `C:/Users/Darsh Gupta/engineering-portfolio-audit/repos/dev-board`
**Evidence:** `D:/devboard-evidence/` · E: was physically detached; nothing on E: was touched.
**Method:** KiCad 9.0.7 `kicad-cli` + bundled `pcbnew`. All numbers measured here, not quoted.

---

## VERDICT: 3 of 5 objective conditions met — and it is HDI by design

| # | condition | result |
|---|---|---|
| 1 | DRC-clean under the correct rules | **PASS (qualified)** — **70 items, ALL WARNINGS, 0 errors**, of which only **8 are real board defects**; 62 are this machine's missing footprint libraries |
| 2 | Zero unconnected nets | **PASS** — **0** on all four DRC runs |
| 3 | Zero unresolved geometry defects | **FAIL** — **5 copper slivers + 2 co-located drilled holes + 1 dangling track = 8** |
| 4 | Revision-stamped package validated against its own board | **PARTIAL** — manifest **48 of 49** verify, but **SurfaceFinish is EMPTY** and the **POS is 28 rows short of the footprint count** |
| 5 | Checklist with no open cell | **written below** |

---

## 1. SPAN CENSUS — it is HDI, and heavily so

`dev-real-production.kicad_pcb`: **105.050 × 105.050 mm = 110.4 cm²**, **4 copper layers**,
**320 footprints (18 on B.Cu)**, 9,310 track segments, **min via drill 0.100 mm**.

| class | count | drill histogram |
|---|---|---|
| through | **1,740** | 0.127 ×689, 0.150 ×894, 0.250 ×82, 0.300 ×75 |
| **micro** | **186** | **0.100 ×174**, 0.150 ×12 |
| **blind** | **1** | 0.150 |
| **buried** | **14** | 0.127 ×7, 0.150 ×7 |
| **NON-THROUGH** | **201** | **→ HDI, sequential lamination required** |

**By layer pair:**

| span | count | class |
|---|---|---|
| **Top → Ground Layer 1** | **183** (0.100 ×171, 0.150 ×12) | blind/micro |
| Ground Layer 1 → Power Layer 2 | 17 (0.100 ×3, 0.127 ×7, 0.150 ×7) | buried |
| Top → Power Layer 2 | 1 | blind |

**201 non-through is 5.6× drone-arm's original 36** and makes this the most HDI-heavy board in the
programme — the ESC is **0 of 1,990**. The concentration matters: **183 of 201 are a single blind span
Top → Ground Layer 1**, i.e. one laser-drilled skip, not multi-span stacking. That is the cheapest class
of HDI, not the expensive kind.

**The three blind/buried *drill files* seen earlier are lamination pairs, not three holes.** Each carries
many. The board is far more HDI than those filenames suggested.

## 2. DRC — 70 warnings, 0 errors, and most are my machine's fault

| rule set | total | unconnected |
|---|---|---|
| board's **own** rules | **70** | **0** |
| 0.200 mm / 1 oz (explicit) | 1,360 | **0** |
| **deliberately absurd** (5.000 mm clearance) | **579** | **0** |
| no `.dru` at all | 70 | **0** |

**Rule-load PROVEN:** the absurd rule changes the count **70 → 579**, so the rule file is genuinely being
read. At its own rules the count equals the no-`.dru` run, because the board's `.kicad_pro` carries the
real rules.

**The 70 by type — and which are real:**

| type | count | real? |
|---|---|---|
| `lib_footprint_issues` | **52** | **NO** — *"The current configuration does not include the footprint library `RP2350B_minimal_hier`"* is **this machine's KiCad library config**, not a board defect. The repo carries the `.pretty` dirs; my profile does not register them |
| `lib_footprint_mismatch` | **10** | **NO** — footprint differs from the library copy (SMA Molex, USB-C GCT). A library-version artefact |
| **`copper_sliver`** | **5** | **YES — real, on Top Layer** |
| **`holes_co_located`** | **2** | **YES — two drilled holes in the same place** |
| **`track_dangling`** | **1** | **YES — one unconnected track end** |
| **all severities** | **70 warnings · 0 errors** | |

**So only 8 of 70 are genuine.** The 1,360 at 0.200 mm is expected and meaningless for this board — it
cannot meet 1 oz standard rules because it is HDI by construction (507 clearance, 199 annular_width,
199 drill_out_of_range, 199 track_width, 186 microvia_drill_out_of_range).

**The shipped report says 176; I measure 70.** Different KiCad version or a different board file — the
release is dated 2026-08-24 and records its own toolchain, so this is a baseline difference, not a
regression. It needs reconciling before either figure is quoted as *the* state.

## 3. PACKAGE — manifest is nearly clean; the gbrjob is not

**SHA-256 manifest (`SHA256SUMS.csv`, 49 entries, sha256sum-style with spaces in filenames):**

| result | count | files |
|---|---|---|
| byte-identical | **46** | — |
| verify **only after normalising CRLF→LF** | **2** | `dev-real-bom.csv`, `dev-real-production-bom.csv` |
| **genuinely stale** | **1** | **`RELEASE_NOTES.md`** |
| not found on disk | **0** | — |

**48 of 49 verify.** The "BOM mismatch" is **proven to be a CRLF checkout artefact** — re-hashing the
normalised file matches the manifest exactly. **Only `RELEASE_NOTES.md` is genuinely out of date**, and
that is a one-command regeneration. My first pass reported *"16 files missing"* — that was **my own
parser splitting on the spaces in filenames**, not a defect; corrected here and worth recording so it is
not repeated.

**Two real package defects:**

1. **`SurfaceFinish` is EMPTY in both `.gbrjob` files** (`dev-real-job.gbrjob`,
   `dev-real-production-job.gbrjob`). A fab cannot know whether to build ENIG, HASL or bare copper.
   **This is fab-blocking.** Board size is correct (105.05 × 105.05 mm vs the measured board), thickness
   **1.6 mm**, **11 layer files** each.
2. **POS rows: 292** against **320 footprints** — **28 components unaccounted for.** The BOM is
   **320 lines**, which matches the footprint count, so the BOM is consistent and the **POS is short.**
   Either 28 parts are DNP (and should be marked as such) or the placement file is incomplete.

## 4. Checklist row

| field | value |
|---|---|
| layers | **4** |
| copper | 1 oz (not stated in the gbrjob; assumed 1 oz, **UNVERIFIED**) |
| min via drill | **0.100 mm** |
| **non-through by span** | **201** = 186 micro (0.100) + 1 blind + 14 buried → **HDI** |
| unconnected | **0** (pcbnew and kicad-cli agree, **not capped**) |
| DRC at own rules | **70 warnings / 0 errors**; **8 real** |
| package state | release exists; manifest **48/49**; **no surface finish**; POS **28 short** |
| revision | **not in the title block** — needs stamping |
| outline + area | **105.050 × 105.050 mm = 110.4 cm²** |
| surface finish | **NOT SPECIFIED — fab-blocking** |
| **orderable** | **NO as the package stands** — blank finish, POS short, 8 real geometry defects |

## 5. What this means

**This board is not a paper design — it has a real release and has plausibly already been fabricated.**
Its 201 HDI vias are **by design**, concentrated in one cheap single-span blind class.

**It is not, however, ready to re-order as-is**, for four fixable reasons:

1. **`SurfaceFinish` empty** in both gbrjobs — one field, fab-blocking
2. **POS 28 rows short** of the footprint count — either mark DNP or regenerate
3. **8 real geometry defects** — 5 copper slivers, 2 co-located holes, 1 dangling track
4. **`RELEASE_NOTES.md` stale** — regenerate the manifest after 1–3

**And two decisions belong to the owner, not to me:**
- **HDI acceptance.** The standing rule is no HDI. This board has 201 non-through vias. If it has already
  been fabbed, the question is whether the rule applies to a board that predates it.
- **Layer-count honesty.** The rest of the programme assumed 4 layers throughout; this board is 4-layer,
  which is consistent — but that is worth stating explicitly given drone-arm silently became 6.

**Basis and limits:** every figure above was measured in this session with KiCad 9.0.7 against the files
named. The 176-versus-70 DRC difference is **not explained** beyond "different baseline" — reconciling it
would need the shipped toolchain's version and rule set.