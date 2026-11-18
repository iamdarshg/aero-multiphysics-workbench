# verify-fab-readiness — independent re-measurement of the 10 fab-* units

All commands run 2026-11-15 18:36–18:55 on KiCad 9.0.7
(`C:\Program Files\KiCad\9.0\bin\kicad-cli.exe`, `...\python.exe` + pcbnew). Nothing written into
any repo; `git -C repos/drone-arm status --porcelain --ignored` = `?? MEMORY.md` (pre-existing,
14 Nov) and `repos/Code-SDR` clean before and after.

## DRC (my own runs, project rules in place)

| board | file | result |
|---|---|---|
| drone-arm main rev_b (repo) | `drc_da_repo.json` | **0 violations / 0 unconnected** |
| ESC rev_b (repo) | `drc_esc_repo.json` | **16 via_dangling (warning) / 499 unconnected** |
| Code-SDR V2 (repo) | `drc_cs_repo.json` | **222 (all warning: 199 lib_footprint_mismatch, 13 via_dangling, 10 track_dangling) / 0 unconnected, 0 errors** |

```
kicad-cli pcb drc --format json --severity-all --units mm -o <out> <board>
```

## Gates on byte-identical copies (sha256 checked)

| copy | gate | result |
|---|---|---|
| `gate_da/` sha 9B3BBA85… (repo board) + `no_hdi.kicad_dru` | via drill ≥ 0.2 | **33 / 0** |
| `gate_fixed/` = fab-da-vias `fixed.kicad_pcb` + same gate | — | **23 / 0** |
| `fixed_own/` = same board, no `.kicad_dru` | board's own rules | **0 / 0** |
| `gate_esc/` sha 99257057… (repo board) + `fab-esc-4oz` 4 oz dru | 4 oz | **523 / 499** |
| `f701_4oz/` = fab-da-servo candidate, same 4 oz dru | 4 oz | **523 / 499 — violation set identical, 0 diff** |
| `servo6/` = fab-da-connectors copy | project rules | **0 / 6** |
| `voidfill/` = fab-da-voidfill `v_r3` | project rules | **0 / 0** |

4 oz type split reproduced: 414 clearance (**371 of them Pad↔Pad at actual 0.2000 mm**), 70 annular,
16 via_diameter, 16 dangling, 4 track_width (0.4000 / 1.6252 / 1.9568 / 1.8087 mm at 0.20),
3 connection_width = 523. `esc_rev_b.kicad_dru` contains **9** rules, not the 11 both reports claim.

## Census (`census.py`, `holes.py`)

| board | GetTracks | segments | vias | holes | non-through | <0.2 mm |
|---|---:|---:|---:|---:|---:|---:|
| DA repo | 2,620 | 2,279 | 341 | 369 (22 PTH + 6 NPTH) | 36 | 33 |
| DA fab-da-vias fixed | 2,639 | **2,301** | 338 | — | 24 | 23 |
| DA voidfill v_r3 | — | 2,279 | 341 | — | 36 | 33 |
| ESC | 2,144 | 154 | 1,990 | 2,218 (223 + 5) | 0 | 0 |
| CS | 12,253 | 11,168 | 1,085 | 1,215 (128 + 2) | 0 | 0 |

`fixed − base` segments = **+22**, not the "+19 track segments" in `fab-da-vias/REPORT.md:251`.

## Packages / patches

* `fab-da-gerbers/package`: PTH 327 hits (0.2/0.3/0.35/0.6), NPTH 6, blind/buried 14+3+4+10+5 = **36**
  (33 @0.1 + 3 @0.3) → 369 total = pcbnew's hole count.
* `fab-checklist/export/cs`: **1,215** drill hits = 1,085 + 128 + 2, matches pcbnew exactly.
* `fab-cs-drc/fabpkg`: PTH **1,211** + NPTH 2 = 1,213, tool `T7C0.600` declared with no holes →
  **2 short**, as the checklist says.
* `repos/drone-arm/hardware/main/pcb-gerbers-1`: 14 files, job `Size 75.05×50.05`, `Finish "None"`,
  `Revision "rev?"`. ESC and Code-SDR trees contain **no** gerber/drill/job/pos at all.
* `title_block_rev_B.patch` and `cs-clock-fix.patch` both apply cleanly in `%TEMP%` and reproduce
  sha256 `984EA325…67` and `A6D7F304…58` — the reported values.
  (Note: `git apply` run inside `E:/engineering-portfolio-audit`, itself a git repo, silently
  resolves paths from that repo root; run these checks in `%TEMP%`.)

## Constraint checks

Stackup copper, read from each board: DA 0.035×4, CS 0.035×4, ESC 0.14/0.0525/0.0525/0.14 — as the
board requires. Coupon: $54.24, headroom $5.76, breaks $60 only above $25.76 shipping.

## Not verified here

Fab capability for 4 oz at 0.200 mm pads, for 0.1 mm annular ring, and any price for any board —
no supplier was asked and no quote exists anywhere in the wave.