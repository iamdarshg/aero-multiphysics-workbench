# AGENT BOARD — engineering-portfolio-audit

**This is the pinned board.** Every agent reads this first and writes its status line back here.
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

### Decisions only the owner can make

1. Fill the voids (routing move, keeps the board) or re-spin In1 to ground (stackup change).
2. Is **D9** clock-capable on the LIF-MD6000, and is the 6-GPIO remap to 0,1,2,3,18,29 acceptable.
3. Servo rail: 0.75 A PTC cannot carry 3–9 A. Respecify, or split the rail.
4. Accept 36 HDI 0.1 mm vias, or re-route to standard vias.
5. Authorise the $283 coupon spend.
6. research-paper: the paper says two distinct arrays, its own overview says five. That one is
   still unresolved and is the last open contradiction in the set.

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
