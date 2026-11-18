# W2 · drone-arm · FL50 CAN H/L — root cause and one-line fix

Agent scope: `repos/drone-arm/hardware/main/rev_b/main_rev_b.kicad_sch` + `.kicad_pcb`, branch `work/2026-11-11`.
All writes confined to `evidence/w2-da-can/`. Git untouched (only read `git status`). No fabrication; anything not
measured is labelled UNVERIFIED / ANALYTICAL.

**VERDICT (one line):** the swap is in the *schematic symbol*, not in the copper. FL50's cached
`Device:L_Coupled` was hand-renumbered so its pin numbers pair the windings by *column* while its own drawn
coils pair them by *row*; restoring the library numbering fixes it with zero board changes.

---

## 1. Symbol pin order — schematic copy vs the library it claims

FL50 is `Device:L_Coupled`, in the sub-sheet `/CAN interface/`.

| source | TL | TR | BL | BR | winding pairs asserted by numbers |
|---|---|---|---|---|---|
| cached copy | **1** (`interfaces.kicad_sch:1265`, name/number `:1268`,`:1275`) | **4** (`:1301`,`:1304`,`:1311`) | **2** (`:1283`,`:1286`,`:1293`) | **3** (`:1319`,`:1322`,`:1329`) | {1,4} and {2,3} |
| library `Device` | **1** (`Device.kicad_sym:78481`, sym starts `:78219`) | **2** (`:78517`) | **3** (`:78499`) | **4** (`:78535`) | {1,2} and {3,4} |

Both copies are positionally identical; only the *numbers* differ — that is the whole
`lib_symbol_mismatch` warning.

## 2. Which pins are actually the same winding (graphics decide)

The two symbols' drawing primitives are **identical** (`interfaces.kicad_sch:1072-1263` vs
`Device.kicad_sym:78288-78479`, same arcs/leads/dots). Decoding them:

- five arcs at `y=+2.032` spanning `x=-2.54…+2.54` → one **horizontal** 5-hump winding
  (`interfaces.kicad_sch:1119,1143,1167,1191,1215`); five more at `y=-2.032`
  (`:1131,1155,1179,1203,1227`).
- lead stubs run vertically to the pins: `x=-2.54` up/down to `y=±2.54` (`:1097,1109`), `x=+2.54`
  likewise (`:1241,1253`). Pins sit at `(-5.08,±2.54)` and `(5.08,±2.54)`.

So **winding = the horizontal row**, i.e. the pair {TL,TR} and the pair {BL,BR} — *not* the columns.
The library pairing {1,2}/{3,4} and this geometry agree. The hand-edited pairing {1,4}/{2,3} does not:
it pairs TL with TR only for pin 1↔4, and BL with BR for 2↔3, i.e. it labels the rows the other way round.

**Polarity dots** (`:1074` centre `-3.048,1.524`; `:1085` centre `-3.048,-1.27`) both sit at the **left**
end of each winding → dotted terminals are TL and BL, one per winding, facing the transceiver side.
Under the library numbering that is pins **1 and 3** — textbook CMC. Under the edited numbering the dots
land on pins **1 and 2**, i.e. *both dotted ends on one winding*, which is meaningless for a coupled choke.
That internal contradiction is the proof the edit is a mistake rather than a deliberate adaptation.

## 3. Part map of the fitted choke — UNVERIFIED

- Fitted part: `Value`/`MPN` `ACT45B-110-2P-TL003` (TDK), `interfaces.kicad_sch:2237,2264`; BOM rows
  `docs/hardware/REV_B_BOM.csv:162` (FL50) and `:67` (FL201 — that reference is not on the board).
- Footprint targeted: `Inductor_SMD:L_CommonModeChoke_Coilank_ACM4532` (`interfaces.kicad_sch:2246`).
  Its own `descr` cites Coilank LCSC `C49073870`; **no ACT45B/ACM4532 datasheet exists in the repo**
  (37 PDFs under `docs/datasheets/`, none for this part). TDK product page returns HTTP 403, LCSC
  datasheet URL resolves to a different Coilank part → **terminal-to-winding map: UNVERIFIED**.
- What the footprint *does* declare (`…/Inductor_SMD.pretty/L_CommonModeChoke_Coilank_ACM4532.kicad_mod`):
  `pad 1 (-1.825,-1.125)`, `pad 2 (-1.825,+1.125)`, `pad 3 (+1.825,+1.125)`, `pad 4 (+1.825,-1.125)`;
  2.25 mm row pitch, 3.65 mm column span. Numbers run round the perimeter, so **{1,2} = one edge,
  {3,4} = the other** — the same {1,2}/{3,4} pairing the *stock* symbol asserts. Footprint + stock symbol
  agree; only the edited copy dissents.

## 4. What the copper actually does (measured)

`pcbnew` dump (`pads.py`) and the file itself agree:

| pad | position (mm) | net |
|---|---|---|
| 1 | `(-1.825,-1.125)` | `41 /CAN interface/U50_CANH` (`main_rev_b.kicad_pcb:2104`) |
| 2 | `(-1.825,+1.125)` | `47 /CANH` (`:2112`) |
| 3 | `(+1.825,+1.125)` | `42 /CAN interface/U50_CANL` (`:2120`) |
| 4 | `(+1.825,-1.125)` | `48 /CANL` (`:2128`) |

Schematic netlist (`rev_b.net`, `kicad-cli sch export netlist`): net 41 = {R122.1, U50.7 CANH, **FL50.1**};
net 42 = {R122.2, U50.6 CANL, **FL50.2**}; net 47 = {D50.1, J2.3, **FL50.4**}; net 48 = {D50.2, J2.4, **FL50.3**}.

Parity (`kicad-cli pcb drc --schematic-parity`, `drc_parity.rpt`), 0 DRC violations / 0 unconnected /
**191** footprint-level issues (161 `footprint_symbol_mismatch` + 20 `net_conflict`), of which exactly
**3** are FL50 net conflicts:

```
L360 [net_conflict]: Pad net (/CANH) doesn't match net given by schematic (/CAN interface/U50_CANL).  Pad 2
L363 [net_conflict]: Pad net (/CAN interface/U50_CANL) doesn't match net given by schematic (/CANL).  Pad 3
L366 [net_conflict]: Pad net (/CANL) doesn't match net given by schematic (/CANH).                   Pad 4
```

It is a **3-cycle (rotation)**, not a 2-swap: 1 is fine, 2 and 4 are swapped, 3 takes pad 2's net.
ERC (`erc_rev_b.rpt`): exactly one warning, `lib_symbol_mismatch` on FL50 at `(199.39, 74.93)` (`:5`).

## 5. Why the *schematic* is the broken side

1. The copper is exactly what the **stock** library symbol would produce from these wire positions.
   Positions → library numbers: TL=1, TR=2, BL=3, BR=4; the wires sit TL=CANH, TR=/CANH, BL=CANL,
   BR=/CANL, so the stock netlist is `1=CANH, 2=/CANH, 3=CANL, 4=/CANL` — **identical to the board**.
   The board was laid out from the correct symbol; somebody then renumbered the symbol in the schematic.
2. A board-side "fix" would be fatal: matching the edited numbers would put `CANH` on pad 1 and `CANL`
   on pad 2 — pads 1,2 are the *same edge*, so that shorts the differential pair through one winding and
   leaves `/CANH`,`/CANL` on the other winding with no path to the transceiver.
3. The edited numbering puts both polarity dots on one winding (§2) — self-inconsistent.
4. Footprint and stock symbol both assert {1,2}/{3,4}; the edit is the only dissent.

## 6. The fix — exact edit

**Schematic side only. Do not touch the PCB, the copper, or the net names.**

Restore the library pin numbers on FL50 (KiCad: *Update Symbols from Library* → `Device`, `L_Coupled`,
or edit the six tokens directly):

```
interfaces.kicad_sch  (pristine -> fixed)
:1286  (name   "2"  ->  (name   "3"     # BL
:1293  (number "2"  ->  (number "3"
:1304  (name   "4"  ->  (name   "2"     # TR
:1311  (number "4"  ->  (number "2"
:1322  (name   "3"  ->  (name   "4"     # BR
:1329  (number "3"  ->  (number "4"
```

Nothing else changes: the four wires, their `/CANH`,`/CANL`,`/CAN interface/U50_CANx` labels and all
net names stay put; only the numbers printed on the four pins move.

**Verified on a sandboxed copy** (`simfix/`, byte-identical project, same six-token edit):

| check | before | after |
|---|---|---|
| FL50 net conflicts vs board | 3 (`drc_parity.rpt:360,363,366`) | **0** (`drc_parity_fixed.rpt` — FL50 still appears once, but only as the board-wide `footprint_symbol_mismatch`) |
| parity issue total | 191 (161 footprint-mismatch + 20 net_conflict) | 188 (161 + **17** = exactly the 3 FL50 ones removed) |
| ERC warnings | 1 (`lib_symbol_mismatch`) | **0** |
| netlist FL50 pins | 1=CANH, 2=CANL, 3=/CANL, 4=/CANH | 1=`/CAN interface/U50_CANH`, 2=`/CANH`, 3=`/CAN interface/U50_CANL`, 4=`/CANL` |

The last row is an exact string match to board pads 1-4 (§4) — schematic and copper become the same netlist.

Note: the residual 188 are **not** new debt — the 161 `footprint_symbol_mismatch` warnings are board-wide
(footprints lost their `Lib:Name` prefix during board generation; FL50 is one of them) and the 17 remaining
`net_conflict`s belong to other parts. Neither set changed under the fix, and both are out of scope here.

## 7. Consequence of shipping it wrong

Two distinct failure modes, because the defect is a numbering error, not a wire swap:

- **As the schematic stands, re-generated** (the realistic escape): `CANH` and `CANL` both land on the
  {1,2} winding. The differential pair is shorted by a few µH of wire (winding DCR, sub-ohm) and the
  connector sees no source. Hard bus-down, every frame dead — *and* it looks like a "short" to any tester.
- **If the part's windings were actually row-paired** (the alternative part map — UNVERIFIED), the as-built
  copper would be a true H/L inversion: every dominant bit arrives as `Vdiff ≈ -2.0 V`. Per ISO 11898-2
  receiver thresholds (dominant ≥ 0.9 V, recessive ≤ 0.5 V) an inverted dominant reads as **recessive**, so
  the far nodes see an idle bus and never ACK. ANALYTICAL: TEC +8 per failed transmission, bus-off at
  TEC > 255 → 32 consecutive failures; at 1 Mbit/s with ~110-130-bit frames that is **≈3.5-4.2 ms** to
  bus-off, then auto-recovery retries → a millisecond-cadence bus-off loop behind a nominally healthy
  recessive bus. No error frames from the peers (they see nothing), so nothing flags the wiring: exactly
  the "bus-down or intermittent, not a clean failure" signature. Not measured here.

The repaired schematic removes both readings: one line per winding, dotted ends towards the transceiver.

## 8. Scope, limits, and one correction to wave 1

- Wave-1 recorded "CAN H/L swapped on FL50". The parity message is real, but it indicts the **schematic
  record**, not the routed copper: the copper matches the stock symbol. Whether the *copper* is inverted
  depends on the unverified part map; the **fix does not** — it aligns schematic and footprint to the same
  {1,2}/{3,4} numbering, which is the only self-consistent choice available in-repo.
- UNVERIFIED: ACT45B-110-2P-TL003 terminal-to-winding map (no datasheet in repo, TDK 403). If a datasheet
  ever shows winding 1 = pins 1 and 2 *on opposite edges*, then the footprint itself is mis-numbered and
  the board needs a pad renumber — that is the one fact that would flip §5(2).
- Not attempted: re-routing, DRC fixes, BOM fixes, FL201 (listed in BOM, absent from board — cf. wave-1).
- Read-only on git throughout; the repo files were never modified (all edits made on copies in `simfix/`).

## 9. Files

| file | what |
|---|---|
| `REPORT.md` | this report |
| `rev_b.net` | pristine schematic netlist (evidence for §4) |
| `erc_rev_b.rpt` | ERC, 1× `lib_symbol_mismatch` on FL50 |
| `drc_parity.rpt` | parity DRC, 191 issues incl. 3 FL50 net conflicts |
| `simfix/` | byte-copy of the project with the six-token fix applied |
| `fixed.net` | netlist after fix (FL50 pins == board pads) |
| `drc_parity_fixed.rpt` | parity DRC after fix, 188 issues, 0 FL50 net conflicts |
| `erc_fixed.rpt` | ERC after fix, 0 messages |
| `pads.py` / `apply.py` | pcbnew pad dump; patch script (both reproducible) |

## 10. Reproduce

```powershell
$K="C:\Program Files\KiCad\9.0\bin"
cd E:\engineering-portfolio-audit\repos\drone-arm\hardware\main\rev_b
& "$K\kicad-cli.exe" sch export netlist --format kicadsexpr --output out.net main_rev_b.kicad_sch
& "$K\kicad-cli.exe" sch erc --severity-all --output erc.rpt main_rev_b.kicad_sch
& "$K\kicad-cli.exe" pcb drc --schematic-parity --severity-all --output parity.rpt main_rev_b.kicad_pcb
& "$K\python.exe" pads.py     # FL50 pad -> net dump
```