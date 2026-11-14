# AGENT BOARD — engineering-portfolio-audit

**This is the pinned board.** Every agent reads this first and writes its status line back here.
One board, one truth. If your work is not on this board, it does not exist.

Pattern: **split the folders · pin one board · tag the teammate.**
Reconstructed from @azizbuildss "WIN HACKATHONS ON EASY MODE" (steps 1–3 on screen; the creator's
own board script is comment-gated, so this is the pattern implemented from the visible steps, not a
copy of their script).

---

## Stage

| stage | state |
|---|---|
| PLAN | done — 2 waves decomposed, 22 units |
| EXECUTE wave 1 (11 units, PCB EM/impedance/fab) | **DONE** — committed `ef9688a` |
| VALIDATE wave 1 | **DONE** — verifier: `MOSTLY_SOUND`, 8 of 11 units rejected |
| HOTFIX wave 1 (6 units) | **DONE** — 6/6 repaired, committed `835e63a` |
| EXECUTE wave 2 (11 units, rectification + 3D) | **running** — 6 of 10 reporting |
| VALIDATE wave 2 | pending |
| HOTFIX wave 2 | pending |

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
1. drone-arm ships only **rev_a gerbers** — sheet frame in all 11 layers. **RE-SPIN.**
2. drone-arm In1 is 3V3 and Z0 is unresolved (51.2 / 52.6 / 65–118 Ω). No TDR coupon. **RIP-UP** unless voids filled.
3. drone-arm **J60–J65 + six PWM nets unconnected**; 7 actuators vs 6 channels; CAN H/L swapped. **RIP-UP.**
4. Code-SDR **clock on dead copper (D7)**; 0/6 RP2040 pins; 84 nets on a solid In1 plane.
5. **No impedance sign-off on either board** — drone-arm 14 FAIL / 8 MISSING, Code-SDR 8 FAIL / 15 MISSING.

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