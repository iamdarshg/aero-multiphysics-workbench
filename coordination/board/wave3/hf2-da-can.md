# HF2 · drone-arm FL50 CAN — arithmetic hotfix of the w2-da-can report

**Status of the underlying work: STANDS. The defect was in the tallies, not the finding.**

Scope: repair the arithmetic in `evidence/w2-da-can/REPORT.md`. No repo writes, no git writes
(read-only `git status` / `rev-parse` / `diff` only). All artefacts in `evidence/hf2-da-can/`.

**HEADLINE_COUNT — 191 footprint-level items, four ways:**

| type | before | after | changed? |
|---|---|---|---|
| `footprint_symbol_mismatch` | 161 | 161 | no |
| `net_conflict` | 20 | 17 | **−3** |
| `missing_footprint` | 6 | 6 | no |
| `extra_footprint` | 4 | 4 | no |
| **sum** | **191** | **188** | **−3** |

191 = 161+20+6+4. 188 = 161+17+6+4. Nothing else moved.

---

## 1. What was actually wrong in the original report

Two sentences, both of the same kind: an unary "footprint-level issues" total was written as a
sum of only its *first two* components, and the complement was silently dropped.

| location | was | is |
|---|---|---|
| `w2-da-can/REPORT.md:74-76` | "**191** footprint-level issues (161 `footprint_symbol_mismatch` + 20 `net_conflict`)" | 191 = **161 + 20 + 6 `missing_footprint` + 4 `extra_footprint`** |
| `w2-da-can/REPORT.md:124` | "parity issue total \| 191 (161 footprint-mismatch + 20 net_conflict) \| 188 (161 + **17**) = exactly the 3 FL50 ones removed" | 191 = 161+20+6+4 → 188 = **161+17+6+4**; the −3 is the 3 FL50 `net_conflict` lines, nothing else |
| `w2-da-can/REPORT.md:171` (Files table) | "parity DRC, 191 issues incl. 3 FL50 net conflicts" | 191 items **by four types**; 3 of the 20 `net_conflict` are FL50 |

The arithmetic that the validator rejected, restated so it cannot recur:

- `161 + 20 = 181`, not 191 — short by 10 = 6 missing + 4 extra.
- `161 + 17 = 178`, not 188 — short by the same 10.
- The `−3` delta is unaffected by the omission, which is why the *conclusion* survived the
  *bookkeeping* error: both totals were missing the same 10 items.

**Where the conflation came from (evidence, not excuse).** `kicad-cli` prints one header line for
all four severities of footprint item — `drc_parity.rpt:8`:
`** Found 191 Footprint errors **`. The report quoted that number as "footprint-level issues" and
then glossed it with only the two types it had reason to care about. The header is *correct*; the
gloss was not.

## 2. Recount, from the reports themselves

Reproduce: `& "C:\Program Files\KiCad\9.0\bin\python.exe" evidence\hf2-da-can\tally.py`
(full output kept in `tally.out.txt`; reads the w2 artefacts read-only, no KiCad needed).
KiCad emits one item per `[type]:` line at column 0, so the type counter is exact.

```
BEFORE  drc_parity.rpt        sha256=23fa6fc365b51321...
  ** Found 0 DRC violations **   ** Found 0 unconnected pads **   ** Found 191 Footprint errors **
  footprint_symbol_mismatch   161
  net_conflict                 20
  missing_footprint             6
  extra_footprint               4
  sum of item lines           191          <- matches the header, so nothing is unattributed

AFTER   drc_parity_fixed.rpt  sha256=9ee62add065fa834...
  ** Found 0 DRC violations **   ** Found 0 unconnected pads **   ** Found 188 Footprint errors **
  footprint_symbol_mismatch   161
  net_conflict                 17
  missing_footprint             6
  extra_footprint               4
  sum of item lines           188
```

There is no fifth type in either file: the four named types account for the header total exactly
in both reports. The 6 `missing_footprint` are J60–J65 ESC_PWM_1..6
(`drc_parity.rpt:204,206,208,210,212,214`); the 4 `extra_footprint` are the standoffs H1–H4
(`:564:H2, :567:H4, :570:H1, :573:H3`, file order). Neither set is touched by a schematic pin-number edit.

## 3. The −3, proved by set difference rather than by subtraction

Subtracting totals cannot say *which* items went; diffing the `net_conflict` lines can.

```
before 20 -> after 17   delta -3
REMOVED: [net_conflict]: Pad net (/CANH) doesn't match net given by schematic (/CAN interface/U50_CANL).
REMOVED: [net_conflict]: Pad net (/CAN interface/U50_CANL) doesn't match net given by schematic (/CANL).
REMOVED: [net_conflict]: Pad net (/CANL) doesn't match net given by schematic (/CANH).
ADDED  : (none)
```

Those three are exactly `drc_parity.rpt:360,363,366` — the three FL50 pad lines the original
report quoted, at the line numbers it quoted. No line was added, so the fix removes and invents
nothing.

Split of the 20 by the footprint each line names (so the 17 residual is attributed, not asserted):

| footprint | before | after |
|---|---|---|
| U10 (RP2354B, pads 43–58 pinfunction renames) | 14 | 14 |
| U51 (CLKO/SOF, INT0, INT1) | 3 | 3 |
| **FL50** | **3** | **0** |
| sum | **20** | **17** |

FL50-anchored item lines fall from 4 to 1 in the fixed report, and the survivor is
`@(15.0000 mm, 20.0000 mm): Footprint FL50` (`drc_parity_fixed.rpt:359`) — the board-wide
`footprint_symbol_mismatch` at `:357`, i.e. FL50 is still one of the 161, as the report said.
So "0 FL50 net conflicts" is literally true and "FL50 gone" would not be.

## 4. The other three claims, re-verified

**6 tokens at `interfaces.kicad_sch:1286-1329`.** Byte diff of the repo file against the
sandbox copy `simfix/interfaces.kicad_sch`: 3202 lines each, **exactly 6 lines differ**, and they
are the 6 claimed:

| line | pristine | simfix |
|---|---|---|
| 1286 | `(name "2"` | `(name "3"` |
| 1293 | `(number "2"` | `(number "3"` |
| 1304 | `(name "4"` | `(name "2"` |
| 1311 | `(number "4"` | `(number "2"` |
| 1322 | `(name "3"` | `(name "4"` |
| 1329 | `(number "3"` | `(number "4"` |

Six tokens, two per renumbered pin, and the span 1286–1329 is the BL/TR/BR pin blocks. Every
other schematic sheet and `main_rev_b.kicad_pcb` are **sha256-identical** between repo and
`simfix/` (checked: `main_rev_b.kicad_pcb`, `main_rev_b.kicad_sch`, `mcu`, `gnss`, `power_usb`,
`rf_915`, `sensors`). The schematic-only claim is therefore mechanically true, not just asserted.

**ERC 1 → 0.** `erc_rev_b.rpt:4` one item `[lib_symbol_mismatch]` on `L_Coupled`, anchored
`:6` at `@(199.39 mm, 74.93 mm): Symbol FL50`; summary line `:20`
`** ERC messages: 1  Errors 0  Warnings 1 **`. `erc_fixed.rpt` holds zero item lines and
`** ERC messages: 0  Errors 0  Warnings 0 **`. Unchanged by this hotfix.

**netlist FL50 pins.** Re-derived from `rev_b.net` / `fixed.net`:

| pin | before | after |
|---|---|---|
| 1 | `/CAN interface/U50_CANH` | `/CAN interface/U50_CANH` (unchanged) |
| 2 | `/CAN interface/U50_CANL` | `/CANH` |
| 3 | `/CANL` | `/CAN interface/U50_CANL` |
| 4 | `/CANH` | `/CANL` |

The after-column equals the board pads of §4 exactly
(`{'1': '/CAN interface/U50_CANH', '2': '/CANH', '3': '/CAN interface/U50_CANL', '4': '/CANL'}`,
checked by equality, not by eye). The before-column does not, which is the whole defect.

## 5. Secondary finding — one table cell is shorthand, and reads as a factual error

Not the arithmetic the validator flagged, but found while re-deriving §4, so it is recorded rather
than left to bite the next reader.

`w2-da-can/REPORT.md:126`, the *before* cell of the "netlist FL50 pins" row, reads
`1=CANH, 2=CANL, 3=/CANL, 4=/CANH`. Those are not the nets in `rev_b.net`. Pins 1 and 2 sit on
`/CAN interface/U50_CANH` and `/CAN interface/U50_CANL` (net codes 41 and 42, `rev_b.net:4337-4344`);
`/CANH` (code 47) and `/CANL` (48) are the connector-side nets. The cell is only defensible as
"transceiver-side CANH/CANL" shorthand, and the *after* cell beside it gives full literal strings,
so the two columns are not comparable as written — a reader can conclude pin 1 changed net when it
did not. Corrected here, with the literal strings in §4 above.

Everything else in `w2-da-can/REPORT.md` checked against its own artefact holds: 0 DRC violations
and 0 unconnected pads (`drc_parity.rpt:4,6`), the 3-cycle reading (1 fine, 2↔4 swapped, 3 takes
pad 2's net), and the parity header totals.

## 6. Does the fix still stand?

**Yes.** All four substantive claims survive an arithmetic-clean recount:

1. six pins-tokens at `interfaces.kicad_sch:1286-1329` — 6 changed lines, nothing else in the repo copy;
2. `net_conflict` 20 → 17, and the −3 is exactly the 3 FL50 lines by set difference;
3. parity 191 → 188 = (161+20+6+4) → (161+17+6+4), with 161/6/4 unchanged;
4. ERC 1 → 0.

The evidence that matters is untouched by the hotfix: the copper cannot fix this (a board-side
edit matching the edited numbers puts CANH and CANL on pads 1–2, the *same* winding edge), the
footprint and the stock symbol both assert {1,2}/{3,4} (`drc_parity.rpt:359` pad positions, §3 of
the original), and the after-netlist is string-equal to the board. A schematic-only,
zero-copper change meeting a correctness defect is the least-effort path that preserves physical
fidelity — it is a constraint/token edit, no fab burden, no rework, which is the owner's steer.

Residual 188 are **not** caused by the fix and not in scope: 161 board-wide
`footprint_symbol_mismatch` (footprints lost their `Lib:Name` prefix at board generation), 6
`missing_footprint` (J60–J65, the da-connectors unit), 4 `extra_footprint` (H1–H4 standoffs), 17
`net_conflict` (U10 14, U51 3). The 188 figure must never again be quoted as "161 + 17".

**No BOARD CORRECTION.** `AGENT_BOARD.md:55` (net_conflict 20 to 17, parity 191 to 188, ERC 1 to 0)
and `:74` ("161+20+6+4"; 181 and 178 wrong) are both right and are the numbers this hotfix
reproduces. The board was correct; the w2 report was not.

## 7. Files

| file | what |
|---|---|
| `REPORT.md` | this hotfix report |
| `tally.py` | recount + set-difference + netlist re-derivation, reproducible, read-only on w2 artefacts |
| `tally.out.txt` | captured run of `tally.py` (every figure above) |
| `checksums.txt` | sha256 of the w2 artefacts and of this dir's files, so the tallies are pinned to bytes |

## 8. Reproduce

```powershell
& "C:\Program Files\KiCad\9.0\bin\python.exe" E:\engineering-portfolio-audit\evidence\hf2-da-can\tally.py
```

```powershell
# raw, no script: type histogram straight out of the report
Select-String -LiteralPath E:\engineering-portfolio-audit\evidence\w2-da-can\drc_parity.rpt `
  -Pattern '^\[([a-z_]+)\]:' | ForEach-Object { $_.Matches[0].Groups[1].Value } |
  Group-Object | Sort-Object Name | Format-Table Name,Count
```

```powershell
# the 6-token claim
$a = Get-Content E:\engineering-portfolio-audit\repos\drone-arm\hardware\main\rev_b\interfaces.kicad_sch
$b = Get-Content E:\engineering-portfolio-audit\evidence\w2-da-can\simfix\interfaces.kicad_sch
0..($a.Count-1) | Where-Object { $a[$_] -cne $b[$_] } | ForEach-Object { "line $($_+1): $($a[$_].Trim()) -> $($b[$_].Trim())" }
```

## 9. Limits

- The `191`/`188` counts are KiCad's own item lines in the two `.rpt` files at the hashes in
  §2/`checksums.txt`; this hotfix re-counts them and does **not** re-run `kicad-cli` (that would
  re-derive a number the board already pins, and the reports are the claim under audit).
- Whether `191 → 188` is the *right* parity number for a fab release is not addressed: the 161
  board-wide mismatches and the missing/extra footprints are real and belong to other units.
- UNVERIFIED and unchanged from the original: the ACT45B-110-2P-TL003 terminal-to-winding map.
  Nothing here depends on it; the schematic-only fix is the self-consistent choice either way.
- Read-only on git, as required: `work/2026-11-11` at `07268c3`, working tree clean apart from a
  pre-existing untracked `MEMORY.md` that is not mine, and `hardware/main/rev_b/interfaces.kicad_sch`
  is identical to `HEAD` — the pristine schematic was never modified. All edits live in `simfix/`.