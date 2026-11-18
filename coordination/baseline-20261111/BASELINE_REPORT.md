# BASELINE VERIFICATION — measured on a clean clone

Host: Windows 11, Python 3.12.2, KiCad 9.0.7, torch 2.9.1+cu130.
Base: `origin/info-dump/2026-11-10-handoff` (local branch `work/2026-11-11`).
All raw artifacts in this directory; hashes in `SHA256SUMS.txt`.
Recorded 2026-11-11T23:40 IST by dsh-lead.

A baseline is *reproduced* only if re-running the command yields the same numbers.
Where the handoff figure could not be reproduced, that is stated explicitly rather
than reconciled.

## Reproduced exactly

| repo | gate | command | measured | handoff | agrees |
|---|---|---|---|---|---|
| Code-SDR | CS-G1 | `kicad-cli pcb drc --format json --all-track-errors hardware/v2/Code-SDR-V2.kicad_pcb` | **222** violations (199 `lib_footprint_mismatch`, 13 `via_dangling`, 10 `track_dangling`), 0 unconnected | 222 (199/10/13) | yes |
| Code-SDR | CS-G2 | `python hardware/v2/tools/audit_rf50_routes.py` | exit 0, `RF50 audit passed: 49 nets connected`, `incomplete=[]`, widths `{0.23: 593}` | exit 0, 49/49 | yes |
| Code-SDR | CS-G7 | `python tools/run_tests.py` | **21/21 passed** | 21/21 Icarus | yes |
| Code-SDR | CS-G7 | `python tools/lint_verilog.py` | **5/5 tops clean** (verilator from `C:\msys64\mingw64\bin`) | 5/5 Verilator | yes |
| Code-SDR | CS-G7 | `python tools/check_firmware.py` | PASS, 91648 B flash (4%), 0 warnings | firmware compile | yes |
| copperline | C-G3 | `ctest --test-dir build -LE campaign` | **33/33 passed**, 0 failed, 598.80 s | 33/33 | yes |
| copperline | C-G3 | `python tests/test_corpus_boards.py --tier short --gate legal --router build/router.exe` | **legality gate PASS (4/4 boards legal, 0 violations)** | legality gate 4/4 | yes |
| drone-arm | DA-G1 | `kicad-cli pcb drc --format json hardware/main/rev_b/main_rev_b.kicad_pcb` | **0 violations, 0 unconnected** | (none existed) | new evidence |

## Supersedes the handoff (correction)

| repo | gate | handoff said | measured | explanation |
|---|---|---|---|---|
| drone-arm | DA-G1 | "No DRC/ERC report has been produced on this host yet" | DRC 0/0; ERC on **root** sheet = **1 warning** | Correct ERC target is `main_rev_b.kicad_sch`. ERC on the standalone sub-sheet `rf_915.kicad_sch` gives 37, of which 36 are hierarchy artifacts (`Hierarchical label ... non-existent parent sheet`, library-path and footprint-link warnings resolvable only from the parent directory). Reporting 37 as real defects would be a fabricated finding. |
| research-paper | RP-G0 | suite "675 passed/4 skipped" | **686 passed, 5 skipped, 0 failed** (856 s) | The info-dump branch carries 17 more tests than the figure in the handoff. Suite is green either way. |

## Could NOT be reproduced — do not quote until fixed

| repo | gate | handoff said | measured | why |
|---|---|---|---|---|
| aero | AM-G1 | "mypy 0/505" | `python -m mypy .` aborts: `benchmarks/independence/generic_benchmark.py: error: Source file found twice under different module names: "independence.generic_benchmark" and "benchmarks.independence.generic_benchmark"` — 1 error, checking prevented | Module-mapping defect, not 505 type errors. Needs `--explicit-package-bases`, `__init__.py` files, or `mypy_path` config before any count is meaningful. |
| aero | AM-G2 | "1793/1794" | `python -m pytest -q` → **16 collection errors**, `ModuleNotFoundError: No module named 'examples.gas_turbine'` | Clean clone needs an install step (`pip install -e .`) or repo-root on `PYTHONPATH`. The ratio cannot be produced without it. |

## Known-failing gates confirmed (not regressions)

| repo | gate | command | result |
|---|---|---|---|
| Code-SDR | CS-G3 | `python hardware/v2/tools/validate_route.py` | exit 1: "Signal routing exists on solid In1/In2 ground plane" for ~100 nets. This is the handoff's documented inner-plane contract blocker; it is an assertion in the repo's own validator, and it is a *design-contract* conflict (4-layer contract forbids signal on In1/In2) rather than a routing bug to fix by moving traces blindly. |

## Notes that affect reproducibility

1. **`main` is not the work base.** On `main`, Code-SDR DRC is 391 and the state
   described by the handoff does not exist. All numbers above are from
   `info-dump/2026-11-10-handoff`.
2. **Windows long paths.** `drone-mech` checkout fails without
   `git config --global core.longpaths true`.
3. **`pytest-timeout` is not installed**, so `--timeout=` is rejected by this pytest.
4. **`pcbnew` is only importable under KiCad's Python**
   (`C:\Program Files\KiCad\9.0\bin\python.exe`), not the system Python 3.12.
   RF50 audit and any `pcbnew`-based tool must use that interpreter.
5. **The router binary is `build/router.exe`** on Windows; passing `build/router`
   makes `test_corpus_boards.py` raise `FileNotFoundError` in `cache_key`.
6. `--tier short` boards exhaust their wall budget (BUDGET_EXHAUSTED) but remain
   legal, so the legality gate passes while the completion gate would not. Both
   denominators must be reported (handoff C-G6).