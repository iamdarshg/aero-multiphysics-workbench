# Code-SDR V2 — clock constraint fix applied, board confirmed otherwise ready

**Item:** `fab-cs-clock` · **Repo:** `E:/engineering-portfolio-audit/repos/Code-SDR`, branch `work/2026-11-11`,
HEAD `6fbc004`, `git status --porcelain` empty before and after this work.
**Evidence dir:** `E:/engineering-portfolio-audit/evidence/fab-cs-clock/` (nothing was written into any repo,
no commit, no branch operation).
**Date:** 2026-11-15.

---

## 0. Verdict — the seven questions

| # | question | answer |
|---|---|---|
| 1 | patch path | **`evidence/fab-cs-clock/cs-clock-fix.patch`** — 2 hunks, 3 changed lines, line count preserved |
| 2 | syntactically valid | **YES as a grammar**: 64/64 statements conform to the LPF grammar shipped inside *this* Diamond install. **Not proven end-to-end** — the vendor engine cannot run (licence, §6). One *site-legality* defect remains (§4). |
| 3 | other bad constraints | **YES, one: `v2_top.lpf:20` puts fabric port `rst_n` on `H2` = `CRESET_B`**, a dedicated configuration pin (Table 5.3/5.6). No other row is wrong; the other 30 SITEs are all real bank-0/1/2 user I/O (§3). |
| 4 | GPIO remap 0,1,2,3,18,29 valid | **YES, 6/6** — pads 2,3,4,5,29,41 map to GPIO 0,1,2,3,18,29 exactly (RP2040 Table 615). The *map* is right; the *SPI0 transport* on those pads is not (§5). |
| 5 | build attempted | **Attempted, not possible.** Diamond **is** installed (`D:\Lattice\bin\nt64\pnmainc.exe`); it fails at **licence checkout** (FlexNet −1,359, `LSC_DIAMOND_A`, `C:\flexlm\license.dat` absent). No synthesis, no PAR, no bitstream (§6). |
| 6 | PCB change needed | **NO.** The clock net is already on `U20.D9`: `ADC_CLK`, 3 pads, 51 segments + 4 vias = 55 items, 42.371 mm, 0 unconnected. `U20.D7` has no net at all. The patch touches only `verilog/` (§7). |
| 7 | remaining Code-SDR fab blockers | **8 open lines, none of them copper for this fix**: no BOM, no assembly drawing, 0 fiducials, 0 test points, no controlled-impedance target stated for a `ImpedanceControlled: true` job file, no IPC-D-356, 4 schematic-parity pads, 84 nets on the "solid" In1 plane. Full table in §9. |

The clock fix is **a constraint edit only**: no copper, no stackup, no drill, no fab step, no respin.

---

## 1. The patch

`evidence/fab-cs-clock/cs-clock-fix.patch` (2,699 B). Generated mechanically (`git diff --no-index` over pristine
copies), then **re-applied to a pristine tree** to prove it applies — `patch/verify.ps1`, receipt in
`patch/verify.out.txt`:

```
== git apply --check ==  exit=0
== git apply ==          exit=0
verilog\v2_top.lpf           MATCH  sha256=A6D7F30424FE4956
verilog\build_diamond.tcl    MATCH  sha256=311FDD6A2EBDC7C2
VERDICT: PATCH APPLIES CLEANLY AND REPRODUCES THE INTENDED FILES
```

### Hunk 1 — `verilog/v2_top.lpf` (the actual fix, 2 lines in place)

```diff
-# Usage:  prj_set_pdc / add this file to the Diamond project as an .lpf.
+# Usage:  readable mirror of the pin map - build_diamond.tcl loads v2_top_generated.lpf.
-LOCATE COMP "clk_100m_in" SITE "D7";      # ADC_CLK (100 MHz tree -> U20.D7)
+LOCATE COMP "clk_100m_in" SITE "D9";      # ADC_CLK -> U20.D9 = PB16A = PCLKT2_0, bank 2
```

Why D7 is not merely wrong but unplaceable, from the package table this board is built to
(ctfBGA80, FPGA-DS-02007-2.2 Table 5.3, p.51, `ds02007_text.txt:2400` header):

| line | row | meaning |
|---|---|---|
| `ds02007_text.txt:2431` | `D7 VCCPLL_DPHY0 DPHY0 — —` | D-PHY PLL **supply** ball, no dual function |
| `ds02007_text.txt:2432` | `D9 PB16A 2 PCLKT2_0 True_OF_PB16B` | bank 2, dedicated **primary clock** pad |
| `design_model.py:505` | `"D7": "VCCPLL_DPHY0", "D9": "PB16A"` | the repo's own model agrees |
| `design_model.py:1557` | `assert ... fpga_pins[ball] is None for ... "D7"` | D7 is asserted to carry **no net** |
| `pcb_facts.out.txt` | `D7 net=''` | measured: D7 has no net on the board |

Line 12 is corrected in the same hunk because it told the reader this file *is* the build's constraint
file; after hunk 2 that is false, and a stale usage note is how the next D7 gets written.

**Both edits are in place, so line numbering is unchanged.** Every document that cites
`v2_top.lpf:16` or `:20` still points at the same constraint, and so does `parse_lpf.py`'s output.

### Hunk 2 — `verilog/build_diamond.tcl` (durable fix, not a precondition)

```diff
-prj_src add verilog/v2_top.lpf
+prj_src add verilog/v2_top_generated.lpf
```

**State this plainly, because `AGENT_BOARD.md:521,619` reads as if line 99 were broken: it is not.**
Line 99 already added `v2_top.lpf`, which is exactly the file hunk 1 repairs, so **hunk 1 alone changes what
the build sees.** Adding `prj_src add <file>.lpf` is the documented way to attach a source LPF
(`D:\Lattice\docs\webhelp\eng\Reference Guides\Tcl Commands\diamond_project_tcl_commands.htm`: *"In this case a
source LPF file, use the prj_src add command as shown below and specify the complete file path"*), and the
file does that correctly.

Hunk 2 is the *structural* fix: it makes the bitstream place against the same copper the gerbers come from.
`v2_top_generated.lpf` is emitted by `tools/gen_lpf.py` from `hardware/v2/Code-SDR-V2.kicad_pcb` — it has said
**D9** all along (`v2_top_generated.lpf:7`). With the build reading the generated file, the D7-class error
cannot be reintroduced by a hand edit, and it also retires the file-formatting risk in §2 (the hand file puts
two constraints on one line in 30 of 32 places; the generated file never does).

---

## 2. Is the syntax valid? — checked against the toolchain's own grammar, not against intuition

Diamond ships its constraint documentation locally. These are the rules I tested the file against:

* `User Guides\Constraints\preference_syntax_guidelines_conventions.htm` — *"Preferences are not case
  sensitive"*; *"Comment strings begin with either # or //"*; *"All statements are terminated with a semicolon,
  and can span multiple lines"*; *"User-supplied identifiers may optionally be enclosed in double quotes"*;
  *"Names of sites, nets, buses, and other design elements are case sensitive"*.
* `Reference Guides\Constraints Ref\locate.htm` — `LOCATE COMP <comp_name> [SITE <site_name> | BANK <bank_num>];`
  with the worked example `LOCATE COMP "A" SITE "11" ; // IO site`.
* `Reference Guides\Constraints Ref\iobuf.htm` — `IOBUF [PORT <port_name>] (<keyword>=<value>)+;` and, for this
  device class, `<keyword> ::= IO_TYPE, OPENDRAIN, DRIVE, PULLMODE, PCICLAMP, SLEWRATE, TERMINATEVTT,
  DIFFRESISTOR, DIFFDRIVE, MULTDRIVE, EQ_CAL`.
* `LVCMOS33` is the vendor's own spelling (`ds02007_text.txt:658, :674` — supported in the bank table), and
  bank 2 runs `VCCIO2 = FPGA_VCCIO2_3V3` (`design_model.py:531-532`), so the standard matches the rail.

Result (`parse_lpf.out.txt`, `parse_lpf_after_patch.out.txt`):

| check | before patch | after patch |
|---|---|---|
| statements parsed | 64 | 64 |
| `LOCATE COMP` / `IOBUF PORT` | 32 / 32 | 32 / 32 |
| **unparsed statements** | **0** | **0** |
| duplicate SITE assignments | 0 | 0 |
| ports in LPF vs ports of the generated top wrapper | 32 / 32, none missing, none extra | same |
| lines holding >1 statement | **30** | still 30 in the hand file (the patch does not reformat it) — but **0 in the file the build now reads** |
| SITEs that are not user I/O | **2** | **1** (§4) |
| hand vs copper-derived pin map | 1 port differs (`D7` vs `D9`) | **0 ports differ** |

**So: the constraint is grammatically valid and semantically placed on a legal clock pad; what is not proven is
that the vendor engine accepts it, because the engine cannot start (§6).** That distinction is the whole point
of §6 — do not read "grammar-valid" as "PAR-clean".

Two grammar-adjacent risks I did **not** wave away:

1. **Two statements per line** (30 lines in the hand file, e.g. `v2_top.lpf:25`). The documented grammar
   delimits by `;` and says statements may *span* lines; it never shows two per line, and every vendor example
   is one statement per line. Retired for the build by hunk 2.
2. **`IOBUF PORT` takes "the signal name attached to the port", not the port name** (`iobuf.htm`, emphasis in
   the original). For a pass-through input like `rst_n`/`clk_100m_in` these are the same identifier, so the
   file is right; it would stop being right if an input were registered inside the top module.

---

## 3. The whole-file sweep — all 32 SITEs against Table 5.3

The question was "does any *other* constraint reference D7 or a non-I/O ball", so all 32 rows were classified
against the 80-ball table rather than eyeballed (`parse_lpf.py`; Table 5.3 parsed to **80/80 rows**, so the
lookup table is complete):

| class | balls in the package | used by the .lpf |
|---|---|---|
| user I/O (`PB*`) | 37 | **30 in the file as shipped, 31 after hunk 1** (D9 joins) — all correct |
| supply (`VCC`, `VCCIO*`, `VCCAUX`, `VCCGPLL`, `VCCPLL_DPHY0/1`, `VCCA_DPHY*`) | 13 | **1 — D7 (wrong, fixed by hunk 1)** |
| ground | 9 | 0 |
| MIPI D-PHY lanes | 20 | 0 |
| **dedicated configuration** | **1 — `H2` = `CRESET_B`** | **1 — `rst_n` (wrong, see §4)** |

The 30 legitimate ones, bank by bank: bank 2 — `D9` (clock), `D10 E9 E10 F9 F10 G9 G10 H9 H10 J10` (ADC),
`K9` (over-range), `K8 K10` (RGMII RX); bank 1 — `E1 E2 F1 F2 J3 J7` (RGMII TX), `J5 K4 K5 K6 J6 K7`
(RGMII RX/MDIO); bank 0 — `K2` (PHY_INT), `G1 K1 H1 J1` (sysCONFIG SPI, all with `PB5x` user-I/O identities).
Every one is a real ball of *this* package and a legal I/O.

**The wrong-table trap is real and worth naming**, because it is how D7 survives review: in the **81-ball
csfBGA81** table, `H2` is `PB49`/`CDONE` (`ds02007_text.txt:2576`), not `CRESET_B`; in the 64-ball table `D7`
*is* `PB16A`. Both are one page away from Table 5.3. `design_model.py:505,512` is on the correct (80-ball)
table, and so is the fix.

---

## 4. Second finding: `rst_n` is constrained to a dedicated configuration pin

`v2_top.lpf:20` — `LOCATE COMP "rst_n" SITE "H2";` and the same row in `v2_top_generated.lpf:69`.

| evidence | value |
|---|---|
| `ds02007_text.txt:2468` | `H2 CRESET_B 0 — —` — bank 0, **dual-function column empty** |
| `ds02007_text.txt:2654` (Table 5.6 *Dedicated Function Pin Descriptions*) | `CRESET_B I Configuration Reset, active LOW.` |
| `design_model.py:512` | `"H2": "CRESET_B"` |
| `design_model.py:555` | `fpga_pins["H2"] = "FPGA_RESET_N"` — the PCB does drive it, correctly, from U10.29 |
| `pcb_facts.out.txt` | `H2 net='FPGA_RESET_N' netcode=61` |
| `v2_top.v:37,63,98` | `rst_n` is a fabric input feeding `reset_n = rst_n & eth_locked` and async resets all over the design |

So the copper is right and the **constraint is the wrong kind of object**: `CRESET_B` is a dedicated
configuration input, not a bank I/O, and the fabric has no route to it. This is the *same* class of error as
D7 — a `LOCATE` on a ball the fabric cannot use — and it is why §3 reports 1 residual non-I/O SITE.

**Honest tier: the datasheet fact is MEASURED; the tool's reaction is UNVERIFIED.** Table 5.3/5.6 admit no I/O
function for `H2`, and no ball of this package is both free and already wired to `FPGA_RESET_N`, so no pin
substitution exists. Whether Diamond rejects the `LOCATE`, silently ignores it, or errors at PAR is unknown
because the engine cannot start (§6). It is **not in the patch**, because the fix is not a constraint edit:

* **Option A (recommended, $0, no copper):** drop `rst_n` from the wrapper/RTL top and derive the fabric reset
  internally (power-on counter off `clk_100m_in`, or reset-on-config). The board's own sequence already
  reconfigures the FPGA on every mode change (`fpga_config.h:1-8`, `fpga_config.cpp:33-53`), so
  reconfiguration *is* the reset path; nothing needs a dedicated ball.
* **Option B (rejected):** route `FPGA_RESET_N` to a free user-I/O ball — `D1, J4, J8, J9, K3` are free, and
  every one of them costs a trace change. That is design rework for no functional gain.

This is the one gateware defect that survives the clock fix. It does **not** block fabrication.

---

## 5. The six GPIO constants — verified 6/6, with one consequence that is not a fab matter

`gpio_check.py` → `gpio_check.out.txt`. Constants live twice — `fpga_config.h:25-30` and
`rp2040_dashboard.ino:91-96` — and both blocks carry the same six pad numbers (the only difference is
`PIN_FPGA_RESET_N` vs `PIN_FPGA_RESET`; both values are 29, so both names resolve).

| constant | PCB pad (U10) | → GPIO | Table 615 row (`rp2040_text.txt`) | SPI0 role on that GPIO |
|---|---|---|---|---|
| `PIN_FPGA_SCK` | 2 | **0** | `GPIO0 2 Digital IO (FT) IOVDD Pull-Down User IO` | `SPI0 RX` |
| `PIN_FPGA_MOSI` | 3 | **1** | `GPIO1 3 …User IO` | `SPI0 CSn` |
| `PIN_FPGA_MISO` | 4 | **2** | `GPIO2 4 …User IO` | `SPI0 SCK` |
| `PIN_FPGA_CS_N` | 5 | **3** | `GPIO3 5 …User IO` | `SPI0 TX` |
| `PIN_FPGA_RESET_N` | 29 | **18** | `GPIO18 29 …User IO` | `SPI0 SCK` |
| `PIN_FPGA_CDONE` | 41 | **29** | `GPIO29 / ADC3 41 Digital IO / Analogue` | `SPI1 CSn` |

**Pad→GPIO: 6/6 correct**, all six are genuine user I/O on the QFN-56, none collides with the QSPI
(pads 51-56), crystal (20/21) or SWD (24/25) groups. GPIO29 is ADC3-capable *and* digital, which is all
`digitalRead` needs. So the remap answer is **yes**.

**But the same table shows the transport cannot be SPI0.** The board wires SCK→GPIO0, MOSI→GPIO1, MISO→GPIO2,
CS→GPIO3, i.e. `(RX, CSn, SCK, TX)`; the peripheral needs `(SCK, TX, RX, CSn)` on exactly those four pads.
Four of four mismatch (`gpio_check.out.txt`, "all four SPI roles realisable: False"). This reproduces
`dec-d9-clock/REPORT.md:117-135` from the primary datasheet table rather than from the Arduino core, and it is
**firmware** work (PIO or SIO bit-bang on GPIO0-3 — SIO/PIO can reach every pin), not a fab item and not part
of the clock fix.

---

## 6. The build: attempted, and blocked by a licence — with the receipt

Diamond **is installed on this host**. The earlier decision record says it is not
(`dec-d9-clock/REPORT.md:178`: *"Diamond is **not installed on this host** (check found no `C:\lscc`, no
`diamondc`)"*). That check looked in the wrong places; `D:\Lattice` exists and so does the batch binary the
build script names in its own header (`build_diamond.tcl:5`).

```
D:\Lattice\bin\nt64\pnmainc.exe            exists
D:\Lattice\bin\nt64\diamondc.exe           absent      (Windows ships pnmainc, not diamondc)
C:\lscc                                    absent
C:\flexlm\license.dat                      absent
D:\Lattice\license\                        license.txt only — no license.dat
env LM_LICENSE_FILE                        unset
```

I staged a copy of `verilog/` into `build-copy/` (so the script's `build/diamond/raw` output lands **outside**
the repo) and ran the script exactly as its header says:

```
cd evidence/fab-cs-clock/build-copy
D:\Lattice\bin\nt64\pnmainc.exe verilog\build_diamond.tcl
```

`pnmainc` is a GUI-subsystem binary: it wrote nothing to stdout (`build.log` = 0 bytes) and raised a modal
dialog titled **"Error"**, which I read with `user32!EnumChildWindows`/`GetWindowText`. Verbatim
(`diamond-license-error.txt`):

> **License checkout failed.** … Feature: `LSC_DIAMOND_A` … Filename: `C:\flexlm\license.dat` …
> **FlexNet Licensing error:-1,359. System Error: 2 "No such file or directory"**

So: **no synthesis, no map, no PAR, no bitstream**, and therefore no vendor verdict on any `SITE` in the .lpf.
The constraint file was validated by parsing (§2-§4) exactly as the task anticipates.

`build-copy/verilog/` now holds the **patched** `v2_top.lpf` and `build_diamond.tcl` (sha256 `A6D7F304…` =
`patch/work/verilog/v2_top.lpf`), so the licence step is genuinely one command: put the free licence at
`C:\flexlm\license.dat`, then `cd evidence/fab-cs-clock/build-copy; D:\Lattice\bin\nt64\pnmainc.exe
verilog\build_diamond.tcl`. The first error it reports will be the `H2`/`CRESET_B` `LOCATE` in §4 — that is the
experiment worth running.

**What would settle it end-to-end, for $0:** Diamond's free licence covers CrossLink and is issued against a
12-digit NIC MAC (`GATEWARE.md`, "Licence path"). Drop the resulting file at `C:\flexlm\license.dat` and
`pnmainc verilog\build_diamond.tcl` becomes a one-command receipt — including a vendor judgement on §4's `H2`
constraint, which is the cheapest way to close that UNVERIFIED. Nothing about the PCB changes either way.

---

## 7. The PCB needs no change for this fix — measured

`pcb_facts.py` → `pcb_facts.out.txt` (KiCad 9.0.7 `pcbnew`, read-only):

| measurement | value |
|---|---|
| `U20.D9` net / netcode | `ADC_CLK` / **12** |
| pads on that net | `R31.2`, `U20.D9`, `U21.2` — clock source, FPGA, ADC. Complete. |
| copper | **51 segments + 4 vias = 55 items, 42.371 mm**, `F.Cu` + `B.Cu` |
| unconnected items | **0** (`GetUnconnectedCount(False)`) |
| `U20.D7` | net `''`, netcode 0 — nothing to move *off*, nothing to move *to* |
| `U20.H2` | `FPGA_RESET_N` (netcode 61) — the RP2040 reset, wired as intended |

The net already lands on the pad the datasheet designates as the primary clock. **The defect was never in the
copper; it was one literal in a text file.** Hence §0 answer 6: no PCB change, no copper move, no re-export
forced by this item, no fab class change (still 4 layers, 1 oz, standard vias).

This also independently reproduces the board's `cs-clock` line (`AGENT_BOARD.md:521`: "55 items, 42.371 mm,
0 unconnected") — same three numbers, measured here.

---

## 8. The fab package — produced, revision-stamped, and checked

Exported from the unmodified board into `evidence/fab-cs-clock/gerbers/` (`MANIFEST.tsv` carries size + sha256
for all 16 files):

```
kicad-cli pcb export gerbers -o gerbers --layers F.Cu,In1.Cu,In2.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts ...
kicad-cli pcb export drill   -o gerbers --format excellon --excellon-units mm --excellon-separate-th --generate-map --map-format gerberx2 ...
kicad-cli pcb export pos     -o Code-SDR-V2-pos-exclude-dnp.csv --format csv --units mm --side both --exclude-dnp ...
```

| check | measured | source |
|---|---|---|
| revision stamp | **`Revision = 2.1`**, matching `(rev "2.1")` in the board title block | `pkg_check.out.txt`, `pcb_facts.out.txt` |
| layer set | 11 functions, **0 missing, 0 extra**; masks `Negative` (correct), copper/silk/profile `Positive` | `pkg_check.out.txt` |
| job file | 4 layers, 1.6 mm, **ENIG**, `ImpedanceControlled: true` | `Code-SDR-V2-job.gbrjob` |
| outline | profile path **101.600 mm** inside a **101.700 mm** bbox — the 0.100 mm cutter line, consistent | `pkg_check.out.txt` |
| PTH drill | **1,213 hits**, 13 tools, **0.200 … 1.570 mm** (= 1,085 vias + 128 through-hole pads) | `Code-SDR-V2-PTH.drl` |
| NPTH drill | **2 hits**, one 3.200 mm tool | `Code-SDR-V2-NPTH.drl` |
| position file | 373 rows unfiltered; **371 placed** with `--exclude-dnp` (R153, R156 are DNP) | `Code-SDR-V2-pos-*.csv` |
| stackup | copper 0.140 + dielectric 1.460 = **1.600 mm**; 1.620 mm if the two 0.010 mm masks are counted | `pkg_check.out.txt` |

Two notes a fab would otherwise ask about: the `.pos` header carries no units field (values are mm per the
export flag), and the DNP parts must be excluded at assembly — hence both position files are kept, with the
`--exclude-dnp` one as the assembly deliverable.

**DRC, under the board's own rules** (`kicad-cli pcb drc --severity-all --schematic-parity --all-track-errors`,
`cs-drc.json`; rules from `Code-SDR-V2.kicad_pro` — `allow_microvias: false`,
`allow_blind_buried_vias: false`, `min_track_width 0.1`, `min_clearance 0.1`, `min_via_diameter 0.4`,
`min_through_hole_diameter 0.15`, `min_via_annular_width 0.1`; plus the 4 deliberate exemptions in
`Code-SDR-V2.kicad_dru` for the five edge-launch SMA lands and the RJ45):

| | count |
|---|---|
| **errors** | **0** |
| warnings | 222 — 199 `lib_footprint_mismatch`, 13 `via_dangling`, 10 `track_dangling` |
| **unconnected items** | **0** |
| schematic parity | 4 `net_conflict` (pad 5 of `U5-U8`, TPS3890 supervisors, "CT" pad with no net) |

And the no-HDI rule, measured rather than declared: **1,085 vias, all through; 0 blind/buried, 0 microvia**;
drills 0.200 ×983, 0.250 ×89, 0.400 ×13; **0 vias below 0.200 mm**. Track widths span 0.100–1.200 mm in 16
values, the minimum exactly at the 0.1 mm rule. Copper is 0.035 mm on all four layers = 1 oz, as the board
requires.

The 222 are all warnings and none is a fabrication defect: 199 are library-sync notices (the board's footprint
copies differ from the library — copper is unaffected), and 23 are dangling via/track stubs. I would clean the
23 because they cost nothing and they are the ones a fab's own DRC will echo back.

---

## 9. What is left on Code-SDR — checklist line by line

Status is for the **bare board plus assembly data**, measured today. "WAIVED" carries its reason.

| # | line | status | evidence / reason |
|---:|---|---|---|
| 1-7 | gerbers exist, complete, correct rev, outline, tolerance | **PASS** | §8 — 11 layers + job, rev `2.1`, 101.600/101.700 profile. *Artefact lives in the evidence dir; it must be promoted to the release path before ordering.* |
| 8 | PTH drill complete | **PASS** | 1,213 hits, 13 tools 0.200-1.570 mm |
| 9 | NPTH / mounting holes | **WAIVED for bare board** | 2 × 3.200 mm only. Bare-board fab is unaffected; an **enclosure needs 4** — mechanical decision, not a fab defect |
| 10 | tooling holes | **WAIVED** | none; the fab can panelise with its own |
| 11 | centroid / `.pos` | **PASS** | 371 placed rows, DNP excluded |
| 12 | assembly drawing | **OPEN** | no top/bottom assembly drawing exists anywhere in the tree |
| 13 | fiducials | **OPEN — the one copper edit** | 0 across 373 footprints, with a **0.65 mm BGA** (U20) and 0.5 mm WSON parts. Assembly needs 2-3 global + 1 local per fine-pitch part |
| 15 | test points | **OPEN** | 0 `TP*`; bring-up of a board with no ICT access is by probing a 0.65 mm BGA — that is a debug cost, not a fab cost |
| 16 | DRC | **PASS on errors, WAIVED on warnings** | 0 errors, 0 unconnected; 222 warnings, of which 199 are library-sync only (§8) |
| 17 | schematic parity | **OPEN** | 4 `net_conflict` — give `U5-U8` pad 5 a no-connect in both schematic and PCB; 4 clicks, no copper |
| 19 | return path / plane integrity | **OPEN — design, not fab** | `tools/validate_route.py` exits 1: **84 nets** route on the "solid" In1/In2 plane (`validate_route_cs.out.txt`) |
| 21 | stackup declared | **PASS** | 1.600 mm on the copper+dielectric basis (1.620 with masks); the job file's `BoardThickness 1.6` is consistent |
| 22 | fab-returned stackup receipt | **WAIVED until the fab answers** | `STACKUP_DRAWING.md` asks the fab to *return* a stack; nothing to verify until one is quoted |
| 23 | controlled impedance + written approval | **OPEN** | the job file says `ImpedanceControlled: true` but **no target Ω per net class is stated on any fab-facing document**. Either publish the targets (`RF_50` 0.23 mm → 49.4 Ω per `cs-em-field`) or clear the flag — a fab cannot answer "true" with no number |
| 24-27 | finish, mask/silk, thickness, layer count | **PASS** | ENIG in board and job; masks Negative; 4 layers, 1.6 mm |
| 28 | revision marking | **PASS** | title block `2.1`, carried into the job file. (No silk revision string — the title block and job file are the machine-readable stamp) |
| 29 | IPC-D-356 | **OPEN** | `export_release.ps1:97` defines `pcb export ipcd356`; no artefact exists |
| 30-32 | BOM, BOM↔PCB, MPNs | **OPEN** | **the board has no BOM at all** — only `redesign/V1_BOM.csv`, a different board. No assembly can be quoted from this tree |
| 33 | DNP | **PASS** | 2 DNP (R153, R156), excluded from the pos |
| 34 | assembly notes | **OPEN** | `FIRST_ARTICLE_VALIDATION.md` is an electrical test plan, not assembly instructions |

**None of these is caused by, or blocked by, the clock fix.** Ordered by what actually stops a purchase:
1. **BOM** (no assembly quote possible); 2. **fiducials** (P&P of a 0.65 mm BGA); 3. **impedance targets**
(the fab will bounce an `ImpedanceControlled: true` job); 4. assembly drawing; 5. IPC-D-356 + 4 parity pads;
6. the 84-net plane question, which is the only item on this list that is *design* rather than *data*.

---

## 10. Corrections and cross-references (nobody else's file was edited)

* **CORRECTION to `dec-d9-clock/REPORT.md:178`** (and to §7 item 1 there): *"Diamond is not installed on this
  host"* is **wrong**. Diamond is installed at `D:\Lattice` and `pnmainc.exe` exists. What blocks the build is a
  **licence checkout failure** (`LSC_DIAMOND_A`, FlexNet −1,359, no `C:\flexlm\license.dat`). The distinction
  matters: absent software is a procurement problem; an unlicensed install is a $0, same-day problem, and it
  changes the plan for whoever runs the first bitstream.
* **NOTE on `AGENT_BOARD.md:521,619`** ("`v2_top.lpf:16` D7 to D9 plus `build_diamond.tcl:99`"): line 99 already
  adds `v2_top.lpf`, so it is not broken and the clock fix does not depend on it (§1). The patch does change it,
  for the structural reason given there. No `BOARD CORRECTION:` is warranted — the board's *decision* stands;
  only the phrasing implies a defect that measurement does not find.
* **Confirmed, not contradicted:** `AGENT_BOARD.md:521` ("55 items, 42.371 mm, 0 unconnected") reproduced exactly
  (§7); `AGENT_BOARD.md:630` (D9 = `PB16A` = `PCLKT2_0`) reproduced from Table 5.3 (§1); the 84-net plane figure
  (`AGENT_BOARD.md:619-621`, blocker #4) reproduced (§9 line 19).
* **NOTE on `evidence/fab-readiness/REPORT.md:134`** ("stackup sums to 1.62 mm vs declared 1.60"): on the
  copper+dielectric basis this board is **exactly 1.600 mm**; 1.620 counts the two 0.010 mm solder masks, which
  is the same basis on which drone-arm was called 1.60. Not a defect either way, but the two boards were being
  measured on different bases.
* **Carried forward from `dec-d9-clock/REPORT.md:197-200`**, and confirmed here: the six GPIO values are a
  correct *map* but not a working *SPI0 transport* (§5).

---

## 11. UNVERIFIED — and what would settle each

| # | open | settled by |
|---|---|---|
| 1 | whether Diamond's mapper **accepts** `SITE "D9"` and what it does with `SITE "H2"` | a licensed `pnmainc verilog\build_diamond.tcl` run; one command once `C:\flexlm\license.dat` exists |
| 2 | whether two statements on one line are accepted (moot for the build after hunk 2, live for any hand edit) | same run, with the hand file temporarily added |
| 3 | whether `LOCATE` on `H2`/`CRESET_B` errors, is ignored, or fails at PAR | same run; §4 Option A removes the question |
| 4 | timing closure at 100 MHz / 125 MHz (no `create_clock` exists yet — `v2_top.lpf:73` is a TODO) | the same run's `.twr` report. **This is a real gap: the .lpf contains no timing constraints at all** |
| 5 | whether the 199 `lib_footprint_mismatch` warnings hide any pad-level difference | a library re-sync and a fresh DRC (copper unchanged either way) |
| 6 | the fab's actual stackup / impedance answer | the fab's quote — and it is the reason the `$54.24` coupon exists |

Item 4 deserves emphasis: the LPF file carries **no** `FREQUENCY`/`PERIOD`/`CLOCK_TO_OUT` preferences, only
pin locations. A bitstream could place and route and still be timing-unclosed. That is gateware debt, not a fab
blocker, and it is the next thing I would fix after the licence.

---

## 12. Files in this directory

| file | what it is |
|---|---|
| `cs-clock-fix.patch` | **the deliverable** — the 2-hunk patch (§1) |
| `patch/pristine/`, `patch/work/`, `patch/apply-test/` | the two files before / after / patched-by-the-patch |
| `patch/verify.ps1`, `patch/verify.out.txt` | proof the patch applies and reproduces the intended bytes |
| `parse_lpf.py`, `parse_lpf.out.txt` | 80/80 Table 5.3 rows; 64 statements; 32 SITEs classified; hand-vs-generated diff (**before**) |
| `parse_lpf_after_patch.out.txt` | the same checks on the **patched** tree: 0 differing ports, 1 non-I/O SITE |
| `pcb_facts.py`, `pcb_facts.out.txt` | pcbnew measurement: identity, stackup, 1,085 vias, widths, D9 copper, assembly inventory |
| `gpio_check.py`, `gpio_check.out.txt` | RP2040 Table 615 pad→GPIO for the 6 constants + the SPI0 role mismatch |
| `pkg_check.py`, `pkg_check.out.txt` | DRC summary, job-file fields, layer set, drill tools/hits, gerber extents, pos |
| `cs-drc.json` | the raw DRC report (222 warnings, 0 errors, 0 unconnected, 4 parity) |
| `gerbers/` + `MANIFEST.tsv` | 11 plotted layers, job file, PTH/NPTH drill + maps, sha256 for each |
| `Code-SDR-V2-pos.csv`, `Code-SDR-V2-pos-exclude-dnp.csv` | centroid, all parts / DNP-excluded |
| `diamond-license-error.txt` | the verbatim licence dialog, the paths searched, and the $0 remedy |
| `build-copy/` | the staged copy of `verilog/` the build was attempted in (repo untouched), already carrying the patch so a licensed run is one command |
| `validate_route_cs.out.txt` | fresh receipt for the 84-net plane assertion (`exit 1`) |

**Provenance.** MEASURED: every PCB number (pcbnew), every DRC count (kicad-cli 9.0.7), every drill/gerber
number (parsed from the plotted files), every `.lpf` classification (Table 5.3 of FPGA-DS-02007-2.2, text
extracted from the PDF the repo cites), every GPIO row (RP2040 Table 615), and the licence dialog text.
VENDOR-DOCUMENTED: the LPF grammar and the `LOCATE`/`IOBUF` syntax (Diamond 3.x help shipped in `D:\Lattice`).
UNVERIFIED: everything that needs a licensed PAR run (§11). No number here is invented, and where the tool was
unavailable the answer is "not proven" rather than a plausible value.

**Read-only compliance:** no file inside `repos/` was created, modified or deleted; `git -C repos/Code-SDR
status --porcelain` is empty and HEAD is still `work/2026-11-11`; no commit, no branch operation, no `audit/*`
branch touched.