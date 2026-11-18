# hf-dm-3d — HOTFIX 1: corrected error bars + honest cold/warm speed-up

Item: `hf-dm-3d`. Corrects **`evidence/dm-3d-speed/REPORT.md`** (the rejected result).
Hotfix run 2026-11-14, Python 3.12.2 (same interpreter as the original measurements).
Receipts: `verify_hotfix.py` → `hotfix_verification.json` (9/9 checks pass, exit 0).

**Scope of this hotfix: two reporting defects only.** No measurement was re-run and no
repo file was touched (audit stays read-only). Every corrected number below is
re-derived from the *original* receipts (`../dm-3d-speed/*_timings.json`,
`interference_reverification.json`) plus the threshold read from the repo source.
Where the original text is wrong, it is quoted struck through and labelled
**SUPERSEDED** — never restated as current.

---

## 1. What the verifier rejected

| # | defect | verdict |
|---|---|---|
| 1 | The 50,033 mm³ cross-check was quoted as `49,997.5 ± 117.5 mm³` with `117.5` reading as a **1σ** bar, while its own JSON carries `sigma = 58.75` | upheld — `117.5` is the **2σ** half-width |
| 2 | The `45.3×` / `1.69×` speed-ups exclude interpreter boot; end-to-end is `349.5 → 258.8 s = 1.35×` cold, `~30×` warm | upheld — `45.3×` was warm-cache **stage-time** only and is misleading as a headline |

Both defects are arithmetic, and both reproduce exactly from the original receipts
(§2 and §3). The underlying physics does **not** change (§4).

---

## 2. Defect 1 — uncertainty reporting

### 2.1 Corrected error bars (authoritative)

| pair | pitch | exact value (OCC Boolean) | **Monte-Carlo, 1σ** | same, 2σ | was printed as |
|---|---:|---:|---:|---:|---|
| A_R1–A_R2 | 36 mm | 50,033.0046 mm³ | **49,997.51 ± 58.75 mm³** | 49,997.51 ± 117.51 mm³ | ~~± 117.5~~ **SUPERSEDED** |
| A_R1–A_R3 | 72 mm | 157.0796 mm³ | **158.41 ± 2.35 mm³** | 158.41 ± 4.70 mm³ | ~~± 4.7~~ **SUPERSEDED** |

**Read this as: σ = 58.75 mm³ (1σ); the previously quoted ±117.5 is the 2σ / 95.45%
half-width.** If the audit needs a 95% figure it must be written as
`49,997.51 ± 117.51 (95%, 2σ)`; if it is written with no σ label the only defensible
reading is 1σ, i.e. `± 58.75`.

The original §5 table did append `(2σ)` to the `± 117.5`, but the surrounding prose
("consistent at 0.6σ") and the headline number give no 1σ magnitude at all, so the
figure travels as if it were a 1σ bar. That is the defect: a reader can only recover
σ by opening the JSON. Correcting it makes the two statements agree — and it also
makes the *consistency* claim stronger, not weaker:

    |V_MC − V_exact| = |49,997.5106 − 50,033.0046| = 35.494 mm³ = 35.494 / 58.7549 = 0.604 σ

So "consistent at 0.6σ" in the original is correct **only** against σ = 58.75; against
a 1σ reading of 117.5 it would have been 0.30σ. The claim is retained with the σ it
actually belongs to.

### 2.2 Where the number came from (recomputed, not copied)

The JSON's `monte_carlo.sigma_volume_mm3` is rebuilt here from raw counts rather than
trusted: `N = 400,000` samples, `inside_both = 257,666`, overlap box `77,616 mm³`,
`f = 0.644165` → `σ = sqrt(f(1−f)/N) · V_box = 58.7549 mm³` (exact match to the
recorded value).

**Secondary finding:** the JSON field is named `volume_ci95` but evaluates to
`mean ± exactly 2.0000σ` = `[49,880.00, 50,115.02]`, a 95.45% Gaussian interval, not a
95.00% one. The key is a misnomer; anyone re-deriving 1σ from it must divide by 2.
This is flagged in `hotfix_verification.json → uncertainty` so the mistake cannot be
repeat-derived.

---

## 3. Defect 2 — speed-up, both regimes, wall clock

The rejection stands: the `45.3×` headline was **warm-cache, stage-time only**. It
excluded the Python + CadQuery/OCP interpreter boot that every real invocation pays,
and it assumed a cache that only exists because an earlier cold run wrote it. Stated
as a portfolio headline it is **misleading and is withdrawn**.

### 3.1 End-to-end wall clock (boot included) — the honest table

`cadquery_boot_seconds` is recorded in every receipt; end-to-end = boot + stage total.

| regime | stage s | boot s | **end-to-end s** | **vs 349.50 s** |
|---|---:|---:|---:|---:|
| before — serial, no cache | 342.87 | 6.63 | **349.50** | 1.00× |
| after — **cold** cache (86 misses, 8 workers) | 201.77 | 57.02 | **258.79** | **1.35×** |
| after — warm, first warm run (mass stage still uncached) | 60.24 | 6.60 | **66.84** | **5.23×** |
| after — **warm**, steady state | 7.57 | 4.06 | **11.63** | **30.05×** |

**Headline that survives: `~30×` on a warm cache, `1.35×` cold — both end-to-end,
wall clock, boot included.** Cold means *the first run on a machine with an empty
cache*, which is the regime a user meets once; warm is every run after it.

Superseded figures and what they actually measured:

| printed | what it was | status |
|---|---|---|
| ~~45.3×~~ | `342.87 / 7.57` — warm cache, stage time only, boot excluded | **SUPERSEDED — misleading as a headline** |
| ~~1.70×~~ | `342.87 / 201.77` — cold, stage time only, boot excluded | **SUPERSEDED — cold end-to-end is 1.35×** |
| 1.69× | `105.3 / 62.4` interleaved serial-vs-parallel A/B on the import stage | **retained, but narrow**: a parallelism ratio, never an end-to-end speed-up (no boot on either arm, so it cannot be quoted as one) |

### 3.2 Amortisation (a cold run pays for the cache; it must be priced in)

| runs | fast total (s) | baseline total (s) | speed-up |
|---:|---:|---:|---:|
| 1 | 258.79 | 349.5 | 1.35× |
| 2 | 270.42 | 699.0 | 2.58× |
| 3 | 282.05 | 1,048.5 | 3.72× |
| 5 | 305.31 | 1,747.5 | 5.72× |
| 10 | 363.46 | 3,495.0 | 9.62× |
| 100 | 1,410.16 | 34,950.0 | 24.78× |

The 30× is the asymptote, not the first-run behaviour. A one-shot run gets 1.35×.

### 3.3 Caveat that cuts *for* the original (stated so the fix is not one-sided)

The cold boot was 57.02 s, taken while 11 sibling agents loaded the host; the baseline
boot was 6.63 s. With a matched 6.63 s boot the cold run would have been 208.40 s →
**1.68×**. That figure is a **counterfactual, not a measurement**, and is not used as
a headline; the measured cold number is 1.35× and stands. The cold column remains
load-contaminated, and a quiet-host re-run is the only thing that would settle it.

---

## 4. Interference verdict, reconfirmed under the corrected σ

**Question:** does 50,033.0 mm³ stay above threshold at σ = 58.75?

**Yes. FAIL is unchanged, and σ is irrelevant to the decision.**

Threshold, read from the repo source rather than the report
(`repos/drone-mech/highspeed_edf/verification/native_adapters.py`):

- `:250` `boolean_interference(..., tolerance_mm3: float = 1e-6)`
- `:172` `"collides": exact > 1e-6`

Both are **exact-geometry** tests with an absolute tolerance of **1 × 10⁻⁶ mm³** —
any non-trivial positive overlap is an interference, so the test is `V > 1e-6`, not a
threshold anywhere near 50,000.

| quantity | value | margin above 1e-6 mm³ |
|---|---:|---:|
| exact OCC Boolean | 50,033.0046 mm³ | 5.003 × 10¹⁰ × threshold |
| closed form (R=21, L=72 can + 8 mm shaft @ 36 mm pitch) | 50,033.0046 mm³ | 5.003 × 10¹⁰ × |
| Monte-Carlo, mean | 49,997.51 mm³ | 4.999 × 10¹⁰ × |
| **Monte-Carlo, mean − 1σ** | 49,938.76 mm³ | 4.994 × 10¹⁰ × |
| **Monte-Carlo, mean − 3σ** | 49,821.25 mm³ | 4.982 × 10¹⁰ × |

The "no interference" hypothesis (`V ≤ 1e-6`) sits **851σ** below the Monte-Carlo mean.
To flip the verdict the true overlap would have to be ~5 × 10¹⁰ times smaller than
measured. The σ of 58.75 mm³ is 1.2 × 10⁻³ of the measured volume and cannot move a
decision made at 1e-6 mm³.

- **Verdict: FAIL (interference present)** — 15 pairs checked, 6 collisions,
  0 clearance failures. Unchanged by the correction.
- Collision decomposition, re-added: `4 × 50,033.0046 + 2 × 157.0796 = 200,446.18 mm³`.
- Robustness to the unsourced envelope (§6 of the original): the sourced 36 × 70 can
  (R=18, L=70) at 36 mm pitch gives `π(18²)(34) + π(2.5²)(8) = 34,764.86 mm³`, still
  **3.5 × 10¹⁰ × threshold** → qualitatively the same FAIL. The uncertainty that
  actually threatens this item is the *motor dimensions*, not the Monte-Carlo σ.

---

## 5. How to reproduce this hotfix

    cd evidence/hf-dm-3d
    python verify_hotfix.py        # 9 checks, exit 0; rewrites hotfix_verification.json

It (a) rebuilds σ from the raw Monte-Carlo counts, (b) shows the quoted ±117.5 is
exactly 2.0000σ, (c) recomputes end-to-end totals and both speed-ups from the four
timing receipts, (d) amortises N runs, (e) reads the 1e-6 mm³ threshold out of
`native_adapters.py` with a regex instead of trusting prose, and (f) asserts the
verdict holds at mean − 3σ and for the sourced can.

---

## 6. Still unverified (unchanged by this hotfix)

- **Generation cost of the 231 MB STEP set** — unmeasured; the generator writes into
  the repo, forbidden under the read-only rule. Needs a writable checkout.
- **Cold-regime timing is load-contaminated** (57.02 s boot vs 6.63 s baseline on the
  same machine). A quiet-host cold re-run is what would replace 1.35× with a
  trustworthy cold figure. Warm (30×) is bootstrap-dominated and insensitive to load.
- **Exact CI level**: the stored interval is ±2σ = 95.45%; or 95.00% if the 1.96σ
  convention is wanted. No 95.00% interval exists in the receipts.
- CadQuery 2.7.0 / OCP 7.8.1.1.post1 used here; `requirements-cad.txt` pins 2.5.2 /
  7.7.2 and was not cross-checked.
- The 42 × 72 mm motor envelope remains **unsourced** against any datasheet; the FAIL
  does not depend on it (§4), only the 50,033 mm³ magnitude does.