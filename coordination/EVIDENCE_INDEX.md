# EVIDENCE INDEX — every promoted artifact with its command trail

Rule (handoff §12): a number has no standing without the command that produced it.
Each row below was produced by the command in column 3 on this host.

## Baseline verification (2026-11-11)

| Artifact | Command | Result |
|---|---|---|
| `evidence/baseline/code-sdr-drc-infodump.json` | `kicad-cli pcb drc --output out.json --format json --all-track-errors hardware/v2/Code-SDR-V2.kicad_pcb` | 222 violations (199 lib_footprint_mismatch + 13 via_dangling + 10 track_dangling), 0 unconnected |
| `evidence/baseline/code-sdr-drc-identities.csv` | derived from the above (`violations[].items[].uuid`) | 222 item rows, 222 distinct UUIDs |
| `evidence/baseline/code-sdr-rf50.log` | `KiCad-python hardware/v2/tools/audit_rf50_routes.py` | exit 0, 49 nets connected, `incomplete=[]` |
| `evidence/baseline/code-sdr-validate-route.log` | `KiCad-python hardware/v2/tools/validate_route.py` | exit 1 — signal on solid In1/In2 ground plane (known contract blocker) |
| `evidence/baseline/code-sdr-rtl.log` | `python tools/run_tests.py` | 21/21 passed |
| `evidence/baseline/code-sdr-lint.log` | `python tools/lint_verilog.py` | 5/5 tops clean |
| `evidence/baseline/code-sdr-firmware.log` | `python tools/check_firmware.py` | PASS, 91,648 B flash (4%), 0 warnings |
| `evidence/baseline/drone-arm-drc.json` | `kicad-cli pcb drc --format json hardware/main/rev_b/main_rev_b.kicad_pcb` | 0 violations, 0 unconnected |
| `evidence/baseline/drone-arm-erc-root.json` | `kicad-cli sch erc --format json main_rev_b.kicad_sch` | 1 warning (lib_symbol_mismatch, L_Coupled) |
| `evidence/baseline/drone-arm-erc.json` | `kicad-cli sch erc --format json rf_915.kicad_sch` | 37 — 36 are hierarchy artifacts (sub-sheet, not root) |
| `evidence/baseline/copperline-ctest.log` | `ctest --test-dir build -LE campaign` | 33/33 passed, 598.80 s |
| `evidence/baseline/copperline-legality.log` | `python tests/test_corpus_boards.py --tier short --gate legal --router build/router.exe` | legality gate PASS (4/4 boards legal, 0 violations) |
| `evidence/baseline/research-paper-pytest.log` | `python -m pytest -q` | 686 passed, 5 skipped, 0 failed (856 s) |
| `evidence/baseline/aero-mypy.log` | `python -m mypy .` | NOT REPRODUCIBLE — aborts on module mapping |
| `evidence/baseline/aero-pytest.log` | `python -m pytest -q` | NOT REPRODUCIBLE — 16 collection errors |

## Drone-mech DM-G2 (2026-11-12)

| Artifact | Command | Result |
|---|---|---|
| `evidence/drone-mech/checkMesh-ias900.log` | `docker run --rm -v <ev>:/work opencfd/openfoam-default:2406 bash -lc "cd /work/case-ias900 && checkMesh -allTopology -allGeometry"` | **Failed 2 mesh checks**: 49,208 tets; max non-ortho 83.4644° (83 faces >70°); skewness 2.7743; **411 cells with determinant < 0.001 (min 0)**; **14 faces interpolation weight < 0.05** |
| image digest | `docker inspect opencfd/openfoam-default:2406` | `sha256:dd5aa20630a55722663bf83ba0cb74870cba130081303e32e3865007fa2aa35a` |

**Container run, not native.** Case assembled from
`experiments/centerline_halfwing_ias/mesh/polyMesh` because the committed
`ias900/constant/polyMesh` is a git symlink materialized as a 22-byte text file.

## Research-paper RP-G1 (2026-11-11)

| Artifact | Command | Result |
|---|---|---|
| `evidence/research-paper/rp-g1/corpus/` | `python scripts/build_diversity_procedural_corpus.py --train-count 660 --holdout-count 96 --seed 20261106 --output-dir ...` | 660 train + 96 holdout, 2,269 attempts, 1,513 rejected_invalid, 0 rejected_duplicate |
| `evidence/research-paper/rp-g1/corpus/corpus_stats.json` | (written by the script) | matches handoff §17.2 exactly |
| gate hash | `python -c "from diversity_novelty_gate import GATE_SPEC_HASH"` | `4eafa9488650a3604f43bfa81be7476fc3b19575aa7ee9c15db90de2125fd135` — unchanged |
| occupancy wiring proof | `occupancy_mean_matching_loss` + `combine_training_loss_terms` unit check | dense field loss 1403.37 vs sparse 1.00; objective 1403.37 at weight 1.0 vs 0.0 at weight 0.0 |
| throughput | `run_monitored_training.py --stop-after-updates 20` | ~4.3 s/update steady state (RTX 4060 Laptop 8 GB) → ~47 min/epoch → ~11 h for 14 epochs |

## Drone-arm DA-G2 (2026-11-12)

| Artifact | Command | Result |
|---|---|---|
| `evidence/drone-arm/rf915_audit.json` | `KiCad-python scripts/rf915_audit.py main_rev_b.kicad_pcb out.json` | RF nets on F.Cu at 0.35 mm; `CC_LNA_N` alone drops to In2 (2 vias) while its partner `CC_LNA_P` stays on F.Cu |
| impedance estimate | `python scripts/rf915_impedance.py` | IPC-2141 49.01 Ω, Hammerstad-Jensen 49.49 Ω; 50 Ω needs 0.3434 mm vs 0.350 mm used |

**Quasi-static hand calculation only** — not a field solve, not S-parameters, not sign-off.