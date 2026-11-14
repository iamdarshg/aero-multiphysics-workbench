# PCB EM + impedance + fab-readiness — acceptance criteria

Written before the 12-agent swarm returned, so the swarm is judged against criteria set in advance
rather than against whatever it happened to produce. If a result misses a criterion below, it is a
gap, not a pass.

## 1. EM validation — what actually counts

The user asked for the PCBs to be **EM-validated**. That is only satisfied if the result comes from
one of these, in descending order of strength:

| tier | method | counts as EM-validated? |
|---|---|---|
| A | 3D full-wave solve (openEMS / HFSS / FEKO) of the actual routed geometry with the actual plane shapes | **yes** |
| B | 2D cross-section solve (finite-difference or FEM Laplace) extracting C and L, giving Z0 = sqrt(L/C), with the real layer stack and the real plane coverage | **yes**, for a uniform trace |
| C | closed-form microstrip/stripline (Hammerstad, Wheeler, IPC-2141) | **NO** — this is analytic, must be labelled analytic |
| D | a quoted number with no stated method | **NO** — reject |

**Non-negotiable:** any number presented as EM must name its tier. Tier C presented as EM is
misrepresentation, and tier D is fabrication.

Acceptance per board:
- drone-arm: Z0 and S11 at 902–928 MHz, computed on the **real** reference situation (In1 = /3V3
  with 11.14% void, not a hypothetical ground plane).
- Code-SDR: Z0 and S11 across **0.1–10 GHz** at each band edge from the repo's own frequency plan.

## 2. Impedance matching — what "matched" means

- Target: **|S11| ≤ −10 dB** (VSWR ≤ 1.92) across the whole declared band, not at a single point.
- A 50 Ω claim at one frequency is **not** a match. Report worst-case in band.
- Every proposed component must be a standard E12/E24 value with a real package size.
- The proposal must state the residual risk that only fabrication can resolve.

drone-arm specifically: the board's own measured condition is 0.00% of the RF run over ground. A
matching network cannot fix a reference-plane defect — it can only compensate for the impedance it
produces. If the result claims matching *without* addressing the reference, flag it.

Code-SDR specifically: if the stackup has **no er defined**, that is a finding, not a detail. An
impedance-controlled claim with no stackup is unfalsifiable.

## 3. Varactor tuning — what "across the whole regime" means

The user asked for varactor-capacitor tuning across the entire SDR regime. Acceptance:

- State the required **Cmin/Cmax ratio** per tuning point, from a stated C(V) model.
- Name a **real part number** and give its actual datasheet ratio and usable frequency ceiling.
- Map the answer onto **all 7 conversion rows**, saying explicitly which rows a varactor can tune
  and which it cannot.
- **An honest "cannot" is a pass.** A claimed 10:1 coverage from a part that is only usable to 2 GHz
  is a fail, and is exactly the overstatement this audit keeps finding.

The likely truth — and the swarm must either confirm with evidence or refute — is that a varactor
belongs in the IF2 / LO-injection / coupling match and cannot tune a 10 MHz–10 GHz front end by
itself. If that is what the evidence says, say it.

## 4. Software parity — what prevents a rip-up

The user's requirement: the PCB must account for its software so nothing needs ripping up at fab.

Acceptance:
- A pin-by-pin table: **pad → board net → firmware/RTL expectation → MATCH / MISMATCH / NOT-ROUTED**.
- Every mismatch classified as either:
  - **PCB CHANGE** — cannot be fixed in software, so it *is* a rip-up risk; or
  - **FIRMWARE ONLY** — fixable without touching copper.
- The classification is the deliverable. A list of mismatches without it does not answer the question.
- Known specific cases that must be resolved explicitly:
  - drone-arm: pads 43–48 / J60–J65 absent from board and BOM; 7-actuator vs 6-PWM conflict.
  - Code-SDR: whether an FPGA **pin constraint file exists at all**. If it does not, no bitstream
    can be targeted and the board is fab-blocked regardless of copper quality.

## 5. 3D / physical files — what "sped up" means

- **Before/after wall-clock timings** per stage, from a real run. A speedup claim with no timing
  pair is rejected.
- **Correctness proof:** the output hash, or the interference count, or the element count, must be
  unchanged. Faster-but-different is not a speedup.
- Any unsourced CAD assumption found must be named. The 42 × 72 mm motor envelope is already
  suspected unsourced, and if DM-G1 rests on it then DM-G1's FAIL rests on an invented dimension —
  that would be a finding about the gate, not the geometry.

## 6. Fab readiness — the ranking that matters

Every pre-fab defect must be tagged as one of:

- **RIP-UP** — the design must change. Highest cost, must be found before fab.
- **RE-SPIN** — same design, new gerbers. Cheap.
- **DOC** — documentation or receipt only. Cheapest.

A flat list of fails is not useful; the tag is. The single highest rip-up risk per board must be
named.

## 7. What will be reported honestly even if it is unpopular

Given this audit's track record — four of my own claims have already been overturned — the swarm's
output will be reported with these rules:

1. If EM validation fails, the gate is **BLOCKED**, not "partially validated".
2. If a matching network is proposed without solving the reference plane, it is **PARTIAL**.
3. If the varactor cannot cover the regime, that is the finding and it gets stated plainly.
4. If either board needs a rip-up, that outranks every other result in the report.
5. No number enters a report without its tier and method.

## Verification method

An adversarial verifier checks every number for: a named method, a real datasheet range where a part
is cited, a timing pair where a speedup is claimed, and evidence where a PASS is claimed. The
verifier's verdict gates the consolidated report.