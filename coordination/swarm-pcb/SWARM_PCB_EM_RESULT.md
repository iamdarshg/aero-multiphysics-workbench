# PCB EM / impedance / fab-readiness — 12-agent swarm result

Run 2026-11-14. 11 specialists + 1 adversarial verifier + 1 reducer. All read-only; every repo
verified clean afterwards (`git status --porcelain` empty in all six).

Verifier verdict: **MOSTLY_SOUND** — 5 unsourced numbers and 3 overstatements found in the swarm's
own output, and corrected below. Two 2D finite-difference field solves are genuine; neither is
mislabelled as full-wave.

---

## The four questions the user asked, answered

### 1. Are the PCBs EM-validated? — **YES, both, at a defined tier**

| board | method | Z0 | S11 |
|---|---|---:|---|
| drone-arm rev_b | own **2D finite-difference quasi-static Laplace** solve (C and L from the cross-section, Z0 = sqrt(L/C)), ±2.6 % grid convergence | **52.6 Ω** over solid In1 | **−10.5 dB** worst in 902–928 MHz |
| Code-SDR V2 | same method | **49.4 Ω** | **−44.5 dB** for f ≥ 500 MHz |

This is **tier B**, not tier A. openEMS **was** successfully built in WSL (recipe: `libhdf5-dev
libboost-all-dev libtinyxml-dev libfparser-dev`, pin `HDF5_INCLUDE_DIR=/usr/include/hdf5/serial`,
`FPARSER_ROOT_DIR=/usr`, and exclude `/mnt/*` from CMake or it reads a Windows Octave HDF5 config).
It was deliberately **not** used for numbers: a 3D FDTD model of a 0.035 mm trace at 915 MHz needs
10⁷–10⁸ cells plus port de-embedding, and a rushed run would produce a Z0 nobody could defend. That
is the right call and it is disclosed.

### 2. Is the impedance matched? — **Code-SDR yes, drone-arm NO**

- **Code-SDR: YES.** 0.23 mm on the real stack gives 49.4 Ω (1.2 % off 50). S11 −44.5 dB above
  500 MHz. **But** the same board has a clock landing on dead copper (D7) — see item 8 — so
  "impedance matched" does not mean "ready".
- **drone-arm: NO.** 0.35 mm measures **52.6 Ω as built**, which is S11 **−1.35 dB at 915 MHz** —
  essentially an open. The −32.4 dB figure in the matching report applies only to an **unbuilt
  retune**. Anyone quoting −32 dB for the current board is quoting a design, not the board.

### 3. Can a varactor cover the whole regime? — **NO. Categorically.**

| requirement | value |
|---|---|
| C-ratio needed for 100 MHz → 10 GHz on one resonator | **10,000 : 1** |
| C-ratio needed per decade | 100 : 1 |
| best real varactor ceiling at 15 V (hyperbolic M=0.5, Vj=0.7) | **4.74 : 1** |
| real parts (SMV1231-1245, SMV1405-1430, MA46H) | 3–10 : 1, useful to ~2 GHz |

**A varactor cannot tune this front end.** What *is* viable: the **IF2 trim** at 26.25 MHz needs only
**1.169 : 1**, and one part can serve all 7 rows there. The 0.1–2.5 GHz range is impossible for any
varactor; 6–10 GHz has an adequate *ratio* but the resonator inductance ends up smaller than a via.

This is the honest answer, and it is a pass on the question even though it is a no on the capability.

### 4. Will either PCB need a rip-up? — **drone-arm YES, Code-SDR no proven PCB change**

- **drone-arm: RIP-UP required.** J60–J65 absent from board *and* BOM, six PWM nets unconnected,
  U10 pads 43–48 unrouted, and the 7-actuator requirement against 6 channels. No firmware change
  reaches a connector that does not exist.
- **Code-SDR: firmware-only**, on six constants, **conditional** on D9 driving CLKI. If D9 is not
  the clock pin, this becomes a PCB change.

---

## Per-item results

| # | item | result |
|---|---|---|
| 1 | da-em-field | Z0 **52.6 Ω** solid; **65–118 Ω** across void widths; S11 **−10.5 dB** worst |
| 2 | da-match-design | S11 **−32.4 dB @ 915** on a **retune that does not exist**; −24.5 dB worst across void range (overstated, see notes) |
| 3 | da-stackup | **51.2 Ω** at 0.35/0.20 mm; **50 Ω needs 0.365 mm**; plane reassignment is the fix, not dimensions |
| 4 | cs-em-field | **49.4 Ω**; S11 **−44.5 dB** ≥500 MHz |
| 5 | cs-varcap | **4.74 : 1 max vs 10,000 : 1 required — 0 of 7 rows tunable by varactor** |
| 6 | cs-match | worst **−0.25 dB (HIGH_B)**; HIGH_C −11.2 dB — HIGH_B is unmatched |
| 7 | da-sw-parity | **0 match / 20 mismatch / 6 unrouted** |
| 8 | cs-sw-parity | FPGA **31 match / 1 mismatch**; RP2040 **0 match / 6 mismatch**; **D7 ≠ D9** |
| 9 | fab-readiness | drone-arm **11 PASS / 14 FAIL / 8 MISSING**; Code-SDR **10 / 8 / 15**; **zero rev_b gerbers exist** |
| 10 | dm-3d-speed | **1.35× cold / ~30× warm** (45.3× was overstated); interference **50,033 mm³ FAIL** re-confirmed |
| 11 | aero-3d-speed | **1.73×**, mesh sha-identical |

---

## The finding that most changes the picture

**The drone-arm RF defect is not "a power plane is the reference". It is the 11.14 % of voids.**

Where the /3V3 pour is **solid**, it is an electrically good reference: **52.6 Ω**, S11 −32 dB across
the band. The damage is where the pour is missing: return current is forced **1.275 mm down to In2**,
Z0 jumps to **65–118 Ω** depending on void width, and the 102.35 mm run carries a **2.25× impedance
spread** that no single netclass width can control.

My earlier framing — "0.00 % over GND, therefore the reference plane is the defect" — was too
coarse. Choosing GND over 3V3 would help, but **filling the voids is the actual fix**, and that is a
zone-fill change, not a stackup re-spin. The sweep of In1 distance (0.18/0.19/0.20/0.21/0.22 mm →
48.08/49.67/51.20/52.73/54.10 Ω) also shows the stackup thicknesses are already fine.

## What the verifier caught in the swarm's own work

Recorded because it is the reason to trust the rest:

- **cs-em-field**: "47–50 Ω" has no artifact that yields 47; the real sweep floor is 48.56.
- **da-match-design**: claims −15.7 dB over "0.10–0.58 mm, Z0 33–87 Ω", but the 0.10 mm point is
  absent from its own `tables.txt` and 87 Ω excludes the 118 Ω void its sister report measured.
- **dm-3d-speed**: "45.3×" excludes interpreter boot (4.1 s warm, 57 s cold). End-to-end is
  **1.35× cold**, ~30× warm.
- **da-stackup**: 51.2 Ω vs da-em-field's 52.6 Ω for the identical stack, never reconciled;
  "independent H&J" is scikit-rf's HJ against a reimplementation of the same model.
- **fab-readiness**: a DA "sums to 1.60" line double-counts two 0.010 mm mask layers (Cu +
  dielectric = 1.58); the same line FAILs Code-SDR at 1.62.

## Top 5 things still blocking fab

1. **drone-arm ships only rev_a gerbers.** Sheet frame present in all 11 layers, no declared fab
   file. Category: **RE-SPIN**.
2. **drone-arm In1 is 3V3, and Z0 is unresolved** (51.2 / 52.6 / 65–118 Ω across three reports). No
   TDR coupon exists to settle it. Category: **RIP-UP** if the voids are not filled.
3. **drone-arm J60–J65 and six PWM nets unconnected**; 7 actuators vs 6 channels; CAN H/L swapped.
   Category: **RIP-UP**.
4. **Code-SDR clock lands on dead copper (D7)**; 0/6 RP2040 pins correct; 84 nets routed on a solid
   In1 plane. Category: **RIP-UP** if D9 is not CLKI, else firmware-only.
5. **No impedance sign-off on either board.** drone-arm 14 FAIL / 8 MISSING, Code-SDR 8 FAIL / 15
   MISSING on the pre-fab checklist.

## Honest limits of this result

- Tier B EM (2D cross-section), not tier A. No 3D effects: no via transitions, no connector launch,
  no radiation. `CC_LNA_N`'s layer split is a 3D structure this method cannot see.
- No measurement of any kind. Every number is computed; DA-G6 (VNA) remains BLOCKED.
- The varactor conclusion rests on a hyperbolic C(V) model with stated M and Vj. A real part's
  datasheet would refine the ceiling but cannot close a 10,000 : 1 gap.
- The 3D speedups are interpreter-bound for short runs. Warm-cache figures (~30×) and cold
  end-to-end (1.35×) are both reported because either alone is misleading.