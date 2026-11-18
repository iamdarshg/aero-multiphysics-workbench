# BLOCKED-GATE ATTEMPT — 4 gates that were assumed unrunnable

Two of these four gates were **not actually blocked**. My earlier BLOCKED verdicts were wrong
because I asserted a tool was absent without checking properly. Corrected below with evidence,
and the scripts are kept so the result is reproducible.

---

## CS-G5 (Code-SDR fab package) — **BLOCKED → PASS**

**What I claimed:** "BLOCKED — no fab package generated."

**Why that was wrong:** `kicad-cli` ships the Gerber, drill and position exporters. Generating a
fab package needs **no external tool at all**. It was marked blocked because I never tried it.

**What was done** — from `hardware/v2/Code-SDR-V2.kicad_pcb`:

```
kicad-cli pcb export gerbers --output <dir>/ Code-SDR-V2.kicad_pcb    -> exit 0
kicad-cli pcb export drill   --output <dir>/ Code-SDR-V2.kicad_pcb    -> exit 0
kicad-cli pcb export pos --format ascii --units mm --output ...pos    -> exit 0
```

**Package produced** (`evidence/blocked-attempt/fab-package/`):

| item | value |
|---|---|
| Gerber files | 23 layer files + `Code-SDR-V2-job.gbrjob` |
| copper layers in job | **4** (F.Cu, In1.Cu, In2.Cu, B.Cu) — matches `GetCopperLayerCount()` = 4 |
| drill file | `Code-SDR-V2.drl`, Excellon, METRIC, 9 tools T1–T9 from 0.20 mm to 0.85 mm |
| position file | `Code-SDR-V2.pos`, 373 footprints, mm, top |
| job `Size` | 101.7 × 101.7 mm |
| board `GetBoardEdgesBoundingBox()` | 101.70 × 101.70 mm |
| **Edge_Cuts gerber extent** | **X span 101.60 mm, Y span 101.60 mm** |
| job `BoardThickness` / `Finish` | 1.6 mm / ENIG |

The 0.10 mm difference between the board bbox and the Edge_Cuts gerber extent is the edge-cut
line width itself, which is expected and is not a mismatch.

**Verdict: PASS as "a valid, self-consistent fab package can be generated."** 

**This is not a fab-readiness claim.** Code-SDR still fails CS-G3 (return paths — signal routed on
a solid In1/In2 ground plane) and has the 222 DRC items, so the correct statement is: *the package
can be produced and is internally consistent; the board is not ready to be ordered.*

---

## CS-G6 (Code-SDR EM) — **BLOCKED → PARTIAL**

**What I claimed:** "BLOCKED — no openEMS/CSXCAD/HFSS/FEKO; meep is a stub."

**What is true:** openEMS, CSXCAD, HFSS, FEKO, pyEPR, femwell, ngspice, PySpice and qucs are all
genuinely absent. **But `scikit-rf` 1.9.0 IS installed** (and 2.2.0 is available on PyPI). My
claim was too broad: a full-wave solver is absent, a transmission-line toolkit is not.

So the gate splits:
- **Full-wave EM (field solve, S-parameters of the routed board): BLOCKED**, and honestly so —
  no FDTD/FEM engine is installed and installing one would exceed the RAM available (≈1 GB free).
- **Transmission-line sanity of the declared stackup: RUN** (see DA-G5 below, same stackup logic).

---

## DA-G5 (drone-arm 915 MHz simulation) — **BLOCKED → PARTIAL, with real numbers**

**A correction first.** I previously reported the drone-arm stackup as **undefined**
(`stackup: {}` in the project file). That was wrong. The project's `net_settings` has no stackup
key, but the **board file itself carries a complete stackup block**:

```
F.Cu  0.035 mm
dielectric 1  prepreg  0.200 mm  FR4  er 4.2  tanD 0.02
In1.Cu 0.035 mm
dielectric 2  core     1.040 mm  FR4  er 4.2  tanD 0.02
In2.Cu 0.035 mm
dielectric 3  prepreg  0.200 mm  FR4  er 4.2  tanD 0.02
B.Cu  0.035 mm            total 1.6 mm,  ENIG
```

The stackup is fully defined. My "undefined stackup" claim is retracted.

**Closed-form transmission-line solve** on that declared stackup, 0.35 mm trace at 915 MHz
(`scripts/da_g2_tline_solve.py`, output `da_g2_tline.json`):

| method | Z0 | eps_eff |
|---|---:|---:|
| Hammerstad-Jensen (finite t) | **48.61 Ω** | 3.217 |
| Wheeler wide/narrow (finite t) | **53.98 Ω** | — |
| scikit-rf `MLine` | **51.23 Ω** | 3.053 |
| width that gives 50 Ω | **0.3313 mm** | — |
| guided wavelength at 915 MHz | 182.8 mm | — |

**Verdict on the impedance question: 0.35 mm is a legitimate ~50 Ω design on this stackup.**
Three independent closed forms land within 48.6–54.0 Ω. My earlier "the declared prepreg gives
47.6–53.7 Ω" was consistent; this confirms it with the stackup read from the board rather than
assumed.

> A note on a bug I caught in my own script: my first Wheeler implementation branched at
> `u = w/h < 1` and returned **155 Ω** — a formula-branching error, not a physics result. Corrected
> to the `u <= 2` switchover, it gives 53.98 Ω. It is recorded here because publishing 155 Ω would
> have been an error of exactly the kind this audit exists to catch.

**What this does NOT settle.** The impedance of the *trace geometry* is fine. The board's problem
is the **reference plane**, and a closed-form microstrip formula assumes a solid ground beneath
the trace. On this board **0.00% of the RF run sits over In1 `/GND`**; 88.9% is over the `/3V3`
plane. So the ~50 Ω figure describes a structure the board does not actually have:

- the return current has to flow in a **power plane**, whose impedance and decoupling are not
  modelled here;
- the next real ground is **In2 at 1.075 mm**, and modelling the trace as a stripline between
  In1 (0.2 mm) and In2 (1.075 mm) gives **≈60 Ω**, not 50 — so In2 is not a usable reference;
- no S-parameters, no return-loss, no coupling to the 3V3 network.

**Verdict: PARTIAL.** Geometry is ~50 Ω by four methods; the reference-plane defect makes the
in-circuit impedance unknown, and only a field solve (DA-G5's true blocker) or a VNA (DA-G6)
would settle it.

---

## DA-G6 (drone-arm physical) — **BLOCKED, confirmed**

**Verified absent:** no VNA, no VISA runtime, no SCPI instrument, no serial port carrying a
measurable instrument. This one stands: no software can substitute for a physical measurement.

**What would unblock it, stated so the owner can act:**
- **Minimum hardware:** any 2-port VNA covering 900–930 MHz, plus a SOL calibration kit and two
  SMA cables. A NanoVNA-H4 (~£50) is sufficient for 1-port S11 and would resolve the reference-plane
  question directly.
- **Measurement:** 1-port S11 at the antenna connector with SOL calibration at the connector plane,
  swept 800–1000 MHz. From that, compute return loss and VSWR, then derive the complex impedance.
- **What to expect:** if the 3V3 reference is as bad as the geometry suggests, expect a
  return loss well short of the >10 dB a 50 Ω design should show, and a frequency shift in the
  minimum — which is the signature of a via/plane discontinuity rather than a trace-width error.
- **What it cannot tell you:** a 1-port measurement at the connector does not separate the trace,
  the matching network and the SAW filter. Settling the plane question specifically needs either
  a field solve or a TDR.

**Verdict: BLOCKED.** Correctly, and with an executable path out.

---

## Summary

| gate | was | now | one-line reason |
|---|---|---|---|
| CS-G5 | BLOCKED | **PASS** | `kicad-cli` exports a complete, self-consistent package; no external tool needed |
| CS-G6 | BLOCKED | **PARTIAL** | full-wave solver genuinely absent; scikit-rf present and used |
| DA-G5 | BLOCKED | **PARTIAL** | stackup is defined (corrected); 48.6–54.0 Ω by four methods; plane still unmodelled |
| DA-G6 | BLOCKED | **BLOCKED** | no VNA; unblocking path and procedure documented |

**Two of four "blocked" gates were not blocked.** Both had been marked BLOCKED on an assumption I
never tested. That is a process failure worth naming: *BLOCKED must be verified the same way PASS
is, by attempting the command and quoting its failure — not inferred from the tool being missing
from PATH or from my memory of what is installed.*

The two corrections that came out of this: **the drone-arm stackup is defined, not undefined**, and
**0.35 mm is a legitimate ~50 Ω width on it**. The RF defect is the reference plane, which is a
different finding from an impedance error and should not be conflated with one.