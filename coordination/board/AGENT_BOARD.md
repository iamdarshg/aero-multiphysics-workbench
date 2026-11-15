# AGENT BOARD — engineering-portfolio-audit

**This is the pinned board.** Every agent reads this first and writes its status line back here.

### Governing principle — owner, 2026-11-15

**More spend now means less effort in the long run. Always keep that in mind.**

This refines the "least effort" steer: the objective is least **total lifetime** effort, not least
immediate effort. A cheap choice that forces rework, a second spin, or a recurring manual step is
the expensive choice. Spend is acceptable when it removes future effort.

How to apply it:

| situation | pick |
|---|---|
| a $60 coupon that may settle Z0 vs a $300 set that definitely settles it | take the set that actually settles it, if it prevents a respin — state the case, do not silently refuse |
| a routing move that dodges today's voids, vs reassigning In1 to a solid ground plane | the structural fix if the board is going to be revised anyway |
| a part swap that fits the current footprint at the edge of its rating, vs a package change that has margin | the one with margin, because an under-rated part becomes a warranty problem |
| fab cost to hold a tighter tolerance vs a design that needs the tighter tolerance | pay for the tolerance; a design change costs more |
| deleting nets to make a measurement look clean, vs routing them properly | route them |

The $60 cap on coupons and the no-HDI rule stand. This principle does not override an explicit
limit; it tells you how to spend *within* one and how to argue for more when the evidence says the
limit is the false economy.

---


### Board roster and copper weight — owner, 2026-11-15 (measured against the files)

**Every board is 4-layer. No board may use HDI. Standard plated through vias only.**

| board | file | layers | copper | owner rule |
|---|---|---|---|---|
| **ESC rev_b** | `drone-arm/hardware/esc/rev_b/esc_rev_b.kicad_pcb` | 4 | **0.14 mm outer = 4 oz**, 0.0525 mm inner | **4 oz required** — already declared |
| drone-arm main rev_b | `drone-arm/hardware/main/rev_b/main_rev_b.kicad_pcb` | 4 | 0.035 mm = 1 oz | 1 oz |
| Code-SDR V2 | `Code-SDR/hardware/v2/Code-SDR-V2.kicad_pcb` | 4 | 0.035 mm = 1 oz | 1 oz |

Measured by parsing the `(stackup ...)` block of each file. Thicknesses map as
0.035 = 1 oz, 0.0525 ≈ 1.5 oz, 0.07 = 2 oz, 0.14 = 4 oz.

**Consequences that are now hard requirements:**

1. **A 0.1 mm drill is not fabricable on a 4-layer non-HDI board.** Any via below the fab's
   mechanical minimum (typically 0.2 mm, sometimes 0.15 mm) must be converted to a standard through
   via. This is why the "36 × 0.1 mm HDI vias on drone-arm rev_b" is a genuine blocker and not a
   labelling issue — on a 4-layer standard board those vias cannot exist.
2. **4 oz copper on the ESC forces larger minimum trace width and spacing.** Typical 4 oz design
   rules are **0.20–0.25 mm minimum trace and space** versus 0.10–0.15 mm at 1 oz, plus a larger
   minimum via annular ring. Any ESC routing drawn to 1 oz rules must be checked against 4 oz rules,
   and likely will not pass.
3. **4 oz changes the achievable impedance.** The ESC is a power board so this matters mainly for
   creepage and current, not for RF — but if any controlled-impedance net runs on the ESC it must be
   recomputed at 0.14 mm copper.
4. **Only the ESC gets 4 oz.** Main rev_b and Code-SDR V2 stay at 1 oz. An ESC-only weight change
   does not touch the other two boards.

---

### drone-mech body — FINAL state (rev5)

**Deliverable:** `evidence/pdf-rev5/drone_mech_body_evidence_rev5.pdf` — **18 pages**, 101,890 chars,
**0 formatting escapes**, `assert_clean` G1–G6 pass, 300-row provenance table.

| quantity | value | tier |
|---|---|---|
| body of record | 42_6 shell, 4 solids, 742,306.360 mm³ | MEASURED |
| **mass** | **472.273 g**, band 431.943–521.637 g | ANALYTICAL on MEASURED volume |
| wall | 145.739 g printed PLA core + 105.779 g CF/glass wrap = 251.518 g | ANALYTICAL |
| fill | 624,770.5 mm³ at effective 353.3 kg/m³ = 220.755 g | ANALYTICAL |
| empty-interior floor | 372.31 g | ANALYTICAL |
| ceiling | 1,088.1 g | ANALYTICAL |
| **optimisation package** | **−95.9 g (−17.44%)**, band −125.1…−66.7 g | ANALYTICAL |
| drag total | 87.96 cm² (body 67.04, nose row 30.03) | ANALYTICAL on MEASURED areas |
| facts graded | 87 MEASURED · 112 ANALYTICAL · 41 ASSUMED · **0 SOLVER** | — |

The optimisation withdrawal is **RESOLVED**: rev4 withdrew −47.4 g as unquotable until re-costed on
the reconciled wall and fill; rev5 publishes **−95.9 g** on the corrected basis. It is larger than the
withdrawn figure because the wall is now priced as PLA core plus wrap rather than as a single
laminate, and the fill carries its real 28.04 % deposition factor.

**The verifier over-fired on this document twice, and both times the text was right.**

| flagged as false | reality |
|---|---|
| "material section ≈ 5 cm² at z=−300, 21× low" | **correct.** 473.529 mm perimeter × 1.2 mm = **5.68 cm²**, the *material band of the shell*. The verifier compared it to **120.13 cm²**, the *closed envelope* section — a different quantity. The document already says "this is stated so nobody fixes it later", which is exactly what the review tried to do. |
| "2 loops > 1.2 mm is false, 0.87 < 1.2" | **correct.** 0.42 + 0.45 = 0.87 mm **per face**, **1.74 mm across both faces**, and 1.74 > 1.2 is why the wall region prints solid. The verifier compared the per-face figure to the total. |

I applied **one clarity edit, not a correction**: the cell now reads "0.87 mm per face, 1.74 mm across
both faces > 1.2 mm" so the ambiguity that produced two wrong reviews cannot recur. **Blindly
applying both requested "fixes" would have corrupted a correct document.**

Lesson recorded: a verifier verdict is evidence, not authority. When a review says a published number
is wrong, verify the quantity before editing — two agents refused to make these edits, and they were
right to.

---

### drone-mech body — corrected mass (supersedes every earlier figure)

Three mass models have been tried. All were wrong. The fourth is the one with a real input basis.

| model | figure | why it was wrong |
|---|---|---|
| wave 1, ρ=1550 on all | 1,150.6 g | assumed the whole 742,305.5 mm³ was carbon laminate |
| wave 1, ρ=150 on all | 111.3 g | assumed the whole thing was light fill |
| wave 2, split | 275.9 g | right structure, wrong both inputs — 34.9 % below the empty-interior floor |
| **wave 3, reconciled** | **472.27 g** | band **431.94–521.64 g** |

**Why it went up, not down.** Two inputs were wrong and both under-counted:

1. **The fill is not 150 kg/m³.** The repo's own saved OrcaSlicer profile sets **15 % sparse infill**
   (`effective-process.json:109`) with **1.26 g/cm³** PLA (`effective-filament.json:72-74`). But the
   slicer also prints a **0.87 mm solid perimeter skin** on every boundary, so a real 15 % slice
   deposits **~27 %** of the solid model's volume — verified against the repo's **two real slices**
   at 27.10 % and 23.20 % against a model of 26.80 % and 23.58 % (**±1.63 %**). Effective fill
   density is **353.3 kg/m³**. Fill weighs **220.76 g, not 93.72 g**.
2. **The wall is not carbon laminate.** The CAD wall is **printed PLA**; the repo books a PLA-core
   mass *and* a separate laminate mass over the same mid-surface
   (`phase12_fixed_powertrain_design.json:197, :203-210`). Charged correctly the wall is
   **251.52 g, not 182.17 g**, and the missing wrap is **105.78 g** that neither previous model
   counted.

**The 275.89 g figure is not merely low, it is physically unreachable.** Even a body with a
completely **empty interior** — printed skins only — weighs **372.31 g**. The previous figure sat
**96.42 g (34.9 %) below that floor.**

**Genuine upper bound: 1,088.09 g** — solid material at the slicer's own density plus the repo's
maximum layup. The withdrawn 1,150.57 g exceeded it by 5.7 %, so it is refuted on a second,
independent basis.

**Mass is a function of infill, not a band:**

| infill | 0 % | 5 % | 10 % | 15 % | 25 % | 40 % | 100 % |
|---|---|---|---|---|---|---|---|
| mass | 372.3 g | 405.6 g | 439.0 g | **472.3 g** | 538.9 g | 638.9 g | 1,038.7 g |

All 52 citations machine-checked (52/52) before any number is believed.

### Deliverable

`evidence/pdf-rev3/drone_mech_body_evidence_rev3.pdf` — **14 pages**, sha256
`21C0FC22E2B57ED65ECC1E09C46E03B9CBA0B5A1BF577DF94B1FB5C467CBB70C`, **208 graded facts:
81 MEASURED · 86 ANALYTICAL · 41 ASSUMED · 0 SOLVER**. Supersedes rev1 (8 pp) and rev2 (11 pp).

Three revisions because the first two were wrong, and each wrong version was caught by an adversarial
verifier rather than by the author. The withdrawals table is cumulative — nothing withdrawn has been
quietly dropped.

---

## HARD CONSTRAINTS — owner, 2026-11-15 (these override the "fab burden is free" steer)

1. **NO HDI ON ANY BOARD. No 0.1 mm microvias, no laser-drilled vias, no blind or buried via
   process.** Every board is 4-layer, so every via must be a **standard plated through via** in the
   normal mechanical drill range (0.2–0.3 mm typical). This overrides any earlier note that HDI burden was acceptable.

   **Corrected attribution (2026-11-15):** Code-SDR V2 has **ZERO** microvias — all 1085 of its vias
   are standard plated-through at 0.200 / 0.250 / 0.400 mm, so Constraint 1 is already satisfied
   there and no work is needed. The **36 × 0.1 mm HDI vias are on drone-arm rev_b**, not Code-SDR.
   My earlier board note said Code-SDR and was wrong.
2. **Coupon / prototype spend cap: $60 total.** Not $283, not $310. Any test-coupon, panel or
   prototype order must come in **at or under $60**, including launches and shipping. If a coupon
   set cannot be built for $60, redesign it smaller rather than asking for more money.

Everything else from the earlier steer still stands: prefer part swaps and constraint edits over
copper changes, prefer copper moves over stackup changes, and do not avoid awkward panelisation or
tight tolerances to spare the fab house.

---

One board, one truth. If your work is not on this board, it does not exist.

Pattern source: **@azizbuildss, "WIN HACKATHONS ON EASY MODE"** (Instagram `DfOLEP6v3AR`,
1 Nov 2026, 61 s). On-screen overlays: *split the folders · pin one board · tag the teammate*.

**Correction to an earlier reading of mine.** I first inferred the mechanism from those three
overlay words alone and wrote it up as a plan/execute/validate/hotfix pipeline. That was wrong.
The caption is comment-bait — *"comment HACK and i'll send you the agent board script"* — and
describes no workflow at all. The real method is legible only in the **screen recordings**:

- `tools/board` with `post / read / unread / wait` — a board CLI agents poll
- `AGENTS.md` wiring Claude Code hooks into that board
- an `orchestrator/src/store.ts` `StateStore` exporting **`claimTask` · `renewLease` ·
  `completeTask` · `setAgentTarget` · `createEscalation` · `appendAudit`** plus
  **`heartbeat` / `reapExpired`**
- a four-column **ownership table**: stream · owner · path scope
- handoffs tagged `[Aziz's Firstmate worker]`, `[Diego's Claude Code]`, `[Aziz's Codex]`
- PRs marked **"Ready PR only, no merge."** and a re-review answered *"5 min later"*

So the mechanism is **task-claiming with leases, heartbeats and escalation** — work distribution
plus liveness. That is not the same thing as plan/validate/hotfix stages, and my earlier write-up
conflated them.

Implemented here as `tools/board.py` (claim · renew · heartbeat · complete · escalate · target ·
reap · post/read · audit), with lease expiry so a crashed worker cannot block a task and scope
collision so two workers cannot duplicate one. Smoke-tested: double-claim refused, scope collision
refused, expired lease reaped and re-claimable, audit trail written.

The pipeline discipline (plan → execute → validate → hotfix) is still used, but as **our** working
method on top of the board, not as a description of the reel.

---

## Stage

| stage | state |
|---|---|
| PLAN | done — 2 waves decomposed, 22 units |
| EXECUTE wave 1 (11 units, PCB EM/impedance/fab) | **DONE** — committed `ef9688a` |
| VALIDATE wave 1 | **DONE** — verifier: `MOSTLY_SOUND`, 8 of 11 units rejected |
| HOTFIX wave 1 (6 units) | **DONE** — 6/6 repaired, committed `835e63a` |
| EXECUTE wave 2 (10 units, rectification + 3D) | **DONE** — 10/10 |
| VALIDATE wave 2 | **DONE** — `MOSTLY_SOUND`, 6 items rejected |
| HOTFIX wave 2 | **needed** — see the reject table below |

### Wave 2 — verified results

| item | result | ready to apply |
|---|---|---|
| da-voidfill | 20 voids, 4.1701 mm², 9.834 % reduced to **1.307 %** by moving 13 In1 segments | **no** — B.Cu reroute UNVERIFIED; the 1.307 % refill is a copy with 13 nets deleted, not a fabbable board |
| da-connectors | J60–J66 1x03 at y=79.50, x=80.00 to 95.24, pitch 2.54; 6 missing_footprint becomes 0 | **no** — 0 free lanes at pads 43–49 |
| da-can | 6 tokens `interfaces.kicad_sch:1286-1329`; net_conflict 20 to **17**, parity 191 to **188**, ERC 1 to **0** | **yes** |
| da-gerbers | 11 Gerbers + 5 blind/buried drills + 161-row `.pos`; Edge_Cuts **140.000 x 100.000 mm** | **yes** (rev still reads rev-question-mark) |
| cs-clock | `v2_top.lpf:16` D7 to D9 plus `build_diamond.tcl:99`; 55 items, 42.371 mm, 0 unconnected | **yes** — but NOT firmware-only |
| cs-varcap-real | 4 x **SMV1236-079LF**, k **1.293:1** against 1.169 needed; corner 44.63–51.05 MHz | model-only, no VNA |
| dm-step | **923.371 s to 218.003 s = 4.24x**, 205/205 records, digest `99301ffc3fd3…` identical | **yes** |
| aero-turbo | turbo 70.751 to **28.439 s (2.49x)**; batch 232.678 to **61.727 s (3.77x)** | **yes** |
| da-tdr | 20 coupons, 35 SMA launches | **no** — panel 140x200 vs 205; W1 110x8 |
| rp-stl | 51 files, 535,362,331 B, 47 hashes, 4 duplicate pairs | audit only |

**The 3D speedup is real and larger than first reported: drone-mech 4.24x (repeat 4.17x) with an
identical canonical digest over 205 paths, and aero 2.49x on the turbo path / 3.77x on the batch
path with sha-equal meshes.** The earlier 1.35x figure was cold end-to-end on a contended host and
is superseded.

### Wave-2 verification rejects (hotfix needed)

| unit | defect |
|---|---|
| da-tdr | 35 launches sum to **$283**, not $310; a 95 mm strip for 10 coupons at 10 mm pitch needs at least 98; W1 has no 100 mm slot; two-way resolution is 3.37 mm, not 2.9 |
| da-can | "191 = 161+20" is wrong, it is **161+20+6+4**; the 181 and 178 sums are also wrong |
| da-voidfill | cites `12_measure.json` which **does not exist**; the "measured" 1.307 % is a deleted-net refill, not a fabbable board; B.Cu is claimed to have room but is 12,728.8 of 14,036 mm2 already filled |
| da-connectors | the placement needs a lane that does not exist at pads 43 to 49 |
| cs-varcap-real | "it is the design" is validated only against the repo's own LC CSV — a model, not a measurement |
| rp-stl | 510.56 **MiB** = 535.36 MB, not MB |
| da-gerbers | report says er **4.5**; board lines `:58/:69/:80` say **4.2** — the report is wrong, the board line above stands |

### Hotfix wave 1 — outcome

All six rejections repaired, each keeping the original visible and striking the superseded
numbers rather than restating them.

| unit | was | corrected |
|---|---|---|
| cs-em-field | "47–50 Ω" band | **WITHDRAWN**; band **48.56–49.92 Ω** at er 3.0–4.5, numerical 49.28–49.54, central 49.43 unchanged |
| da-match-design | "−15.7 dB over 0.10–0.58 mm", "−24.5 dB all voids" | 0.100 mm row now computed (−19.60 dB @ 32.7 Ω); cascaded **−25.1 dB** with real fills; **−11.5 … −32.3 dB** if the 11.14 % is forced onto that path |
| da-match-design | "entire plausible void range" | **scope wrong** — the void is on CC_PA / CC_LNA_N / CC_LNA_P / GNSS_RF_IN, **not** on the matching path |
| dm-3d-speed | ±117.5 mm³, 45.3× | 117.5 is **2σ** (σ 58.75); 45.3× withdrawn, **1.35× cold** |
| da-stackup | 51.2 Ω, 0.365 mm, "independent" | **51.3 Ω**, **0.366 mm**, word *independent* dropped — it was one model twice |
| cs-varcap | SMV1231-1245 on a 2.426 GHz trim | relabelled **BRIEF-SUPPLIED**; item now states P3 **exceeds** the part ceiling by 1.223× |
| fab-readiness | "sums to 1.60"; "impedance never solved" | mask layers excluded from body thickness, both boards re-evaluated alike; impedance **was** solved, what is missing is a **measurement** |

---

## Folder split — nobody writes outside their own row

| owner | directory | scope |
|---|---|---|
| da-em-field | `evidence/da-em-field/` | 915 MHz field solve, void sweep |
| da-match-design | `evidence/da-match-design/` | matching network |
| da-stackup | `evidence/da-stackup/` | stackup + plane reassignment |
| cs-em-field | `evidence/cs-em-field/` | Code-SDR field solve |
| cs-varcap | `evidence/cs-varcap/` | varactor feasibility |
| cs-match | `evidence/cs-match/` | per-band matching |
| da-sw-parity | `evidence/da-sw-parity/` | pin map vs firmware |
| cs-sw-parity | `evidence/cs-sw-parity/` | pin map vs RTL |
| fab-readiness | `evidence/fab-readiness/` | pre-fab checklist |
| dm-3d-speed | `evidence/dm-3d-speed/` | drone-mech 3D pipeline |
| aero-3d-speed | `evidence/aero-3d-speed/` | aero mesh pipeline |
| w2-* (11) | `evidence/w2-*/` | wave 2 rectification |
| hf-* (6) | `evidence/hf-*/` | hotfix of wave-1 rejects |

**Never write:** another row's directory, any repo working tree, any `audit/*` branch.

---

## What is true right now (verified)

### PCBs
| question | answer |
|---|---|
| EM-validated? | **YES both**, tier B — 2D finite-difference quasi-static Laplace, ±2.6 % grid |
| drone-arm Z0 | **52.6 Ω** over solid In1 pour; **65–118 Ω** over void |
| Code-SDR Z0 | **49.4 Ω** at 0.23 mm; S11 −44.5 dB ≥500 MHz |
| Impedance matched? | **Code-SDR yes · drone-arm NO** (as built S11 −1.35 dB at 915 MHz) |
| Varactor covers regime? | **NO** — 10,000:1 needed, 4.74:1 ceiling at 15 V; only IF2 trim viable (1.169:1) |
| Rip-up needed? | **drone-arm YES** · Code-SDR firmware-only, conditional on D9 = CLKI |

### The finding that re-framed the drone-arm RF defect
Not "a power plane is the reference". It is the **11.14 % of voids**. Solid pour gives 52.6 Ω and
S11 −32 dB; a void forces the return 1.275 mm down to In2 and Z0 jumps to 65–118 Ω. **Fill the
voids** — that is a zone-fill change, not a stackup re-spin. The In1 distance sweep
(0.18–0.22 mm → 48.08–54.10 Ω) shows the stackup thicknesses were already fine.

### 3D corpus
471 files / 1.86 GB. **drone-mech is 247 files / 1.31 GB** (191 STEP + 14 brep) — 70 % of all bytes.
research-paper 51 files / 510 MB (36 STL + 15 STP), never audited. copperline 120 `.obj` ≈ 170 KB
each, almost certainly test fixtures.

Speed achieved so far: drone-mech **1.35× cold / ~30× warm** (the 45.3× first reported was
warm-cache only and is withdrawn) · aero **1.73×**, mesh sha-identical.

### Top 5 blocking fab

1. **drone-arm ships only rev_a gerbers.** A valid rev_b package now regenerates (Edge_Cuts
   140.000 x 100.000 mm) but the rev field still reads unresolved. Category: **RE-SPIN.**
2. **drone-arm In1 is 3V3 and the void fill is not yet fabbable.** The fix is moving 13 In1
   segments, not a zone tweak (zone parameters alone only reach 8.97 % void). The 1.307 % result
   comes from a copy with 13 nets deleted, and the B.Cu reroute is unverified. Category: **RIP-UP.**
3. **drone-arm J60–J66 has no lane at pads 43–49** and the servo rail protection is undersized —
   a 0.75 A PTC against a 3–9 A requirement. That is a safety item, not a nicety.
4. **Code-SDR clock is a two-line fix, not firmware-only**: `v2_top.lpf:16` D7 to D9 plus
   `build_diamond.tcl:99`. Open question: is D9 clock-capable on this part. Also 36 HDI 0.1 mm vias
   and 84 nets routed on a solid In1 plane.
5. **No impedance sign-off on either board.** Two 2D FD solves exist; a measurement does not.
   The TDR coupon design is not yet buildable (panel 140x200 vs 205, W1 110x8, $283 vs $310).

### Decisions — resolved

| # | decision | resolution |
|---|---|---|
| 1 | void fill vs In1 re-spin | **void fill**, but see the buildability report: the 1.307 % result came from a copy with 13 nets deleted. Minimum move set is being measured. |
| 2 | is D9 clock-capable | **YES, confirmed.** D9 = `PB16A` = **`PCLKT2_0`**, a dedicated primary-clock pad in bank 2 (Lattice CrossLink datasheet FPGA-DS-02007-2.2, p.51, which the repo itself cites). Not merely clock-capable — a dedicated clock pad. **No copper change, no respin.** |
| 3 | servo rail PTC | **Re-pointed and it is a COPPER fix.** The 0.75 A PTC is **F701 on the ESC rev_b board** (`REV_B_BOM.csv:57`), not the flight-control board. No PTC at 3–9 A exists in that footprint, so it is not a BOM swap. The fix is deleting **six pad-to-net connections**, not rebuilding the board. |
| 4 | 36 HDI vias | **Not on Code-SDR at all** — that board has zero microvias. The 36 are on **drone-arm rev_b**. Conversion plan required there. |
| 5 | coupon spend | **$54.24, inside the $60 cap** with $5.76 headroom. 2 coupons on one 100×100 mm panel, **2 SMA launches total**, 5 boards ordered (6 coupons each: 3 × CA + 3 × CB). |
| 6 | research-paper 2-vs-5 arrays | pending the rp-stl hotfix |

### The coupon that was designed — and why it is worth the money

The single uncertainty worth paying to measure: **Z0 of the as-built cross-section where In1 is
absent, with the 0.25 mm-gap stitched F.Cu coplanar pour either present (74.5 Ω) or inert (118.1 Ω).**
Those two models are **43.6 Ω apart**, and which is true decides whether the coplanar pour is
carrying the reference or doing nothing.

| coupon | predicted | purpose |
|---|---|---|
| CA | **74.53 Ω** (pour present) vs **118.12 Ω** (pour inert) | the measurement that resolves it |
| CB | **50.19 Ω** | control — same line with In1 solid |

That is a properly designed experiment: one coupon for the unknown, one control, and a refutation
criterion. It fits the budget because it drops from 35 SMA launches to 2.

---

## Wave-1 validation rejects (being hotfixed)

| unit | defect |
|---|---|
| cs-em-field | "47–50 Ω" band; no artifact yields 47, real floor 48.56 |
| da-match-design | 0.10 mm row absent from its own tables; 87 Ω excludes the 118 Ω void; uniform-h_eff contradicted by the FD result |
| dm-3d-speed | ±117.5 mm³ is 2σ (σ = 58.75); 45.3× was warm-cache only |
| da-stackup | 51.2 vs 52.6 Ω unreconciled; "independent" HJ is the same model twice |
| cs-varcap | SMV1231-1245 (~2 GHz) assigned to a 2.426 GHz trim |
| fab-readiness | stackup sum double-counts two 0.010 mm masks; "impedance never solved" contradicts two FD solves |

---

## Rules for any agent reading this

1. **Read this board before doing anything.** Do not re-derive a number that is already on it.
2. **Write only in your folder.** If you need another owner's output, read it; do not edit it.
3. **Every number carries a method.** Tier A field solve / Tier B 2D FD / Tier C closed form.
   Calling a Tier C number "EM-validated" is misrepresentation.
4. **Do not contradict this board silently.** If you find a number here is wrong, write
   `BOARD CORRECTION:` in your report and say which line. Do not restate it as a new finding.
5. **UNVERIFIED is a valid, rewarded answer.** Inventing a plausible number is the worst outcome.
6. **Nothing in a repo.** No commit, no push, no `audit/*` branch, ever.

---

## Corrections this board already carries

This program has overturned four of its own claims. They stay visible:

| was | is |
|---|---|
| "0.00 % over GND, so the power plane is the defect" | the **voids** are the defect; solid 3V3 is a fine reference at 52.6 Ω |
| drone-arm stackup "undefined" | **fully defined** — F.Cu 0.035 / prepreg 0.200 er 4.2 / In1 / core 1.040 / In2 / prepreg 0.200 / B.Cu |
| "0.35 mm is not 50 Ω" | **it is** — 48.61 / 53.98 / 51.23 Ω by three closed forms |
| drone-mech 3D speedup 45.3× | **1.35× cold**, ~30× warm |
| research-paper arm "9.9 % unique" | **6.08 %** distinct (35/576); 9.9 % was a Pairs-IoU column |

---

*Maintained by dsh-lead. Last updated when the hotfix and wave-2 runs report.*
