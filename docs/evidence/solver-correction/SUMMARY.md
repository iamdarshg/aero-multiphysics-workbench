# SOLVER-CORR 01–05 native correctness evidence (GCP)

Short-lived Spot `e2-standard-2` VM `aero-solvercorr-202609190517`
(us-central1-a, Ubuntu 22.04, 60 GB) — created 2026-09-19T05:18Z, **deleted
2026-09-19T07:12Z (verified)**. Wall ≈ 114 min. Estimated spend ≈ **US$0.04**
(Spot; see `summary.json`). The pre-existing RUNNING instance
`instance-20260823-180846` was never touched.

Reproduce: `scripts/gcp/install-solvers.sh` (bootstrap) + `scripts/gcp/run-benchmarks.sh`
(all benchmarks). Raw receipts: `receipts/*.json`; run logs: `install.log`,
`benchmarks.log`. Every number below is parsed from a real solver artifact.

## Applied benchmark table

| Issue | Solver (version) | Case | Status | Key real numbers |
|---|---|---|---|---|
| 37 | OpenFOAM v2412 | plane channel, inlet/outlet | EXECUTED | Q_in 0.001 → Q_out 0.000999999999 m³/s, **mass imbalance 1.0e-9**; max Ux 1.4973 vs analytic 1.5 (**0.18%**); 3-mesh ladder 1.4547/1.4886/1.4973 |
| 37 | OpenFOAM v2412 | lid-driven cavity | EXECUTED | min Ux −0.19092/−0.20386/−0.20692 (10²/20²/40²); rel deltas 6.3%, 1.5% |
| 37 | OpenFOAM v2412 | rotating-frame MRF shear (1- and 2-zone) | EXECUTED | upper Mz −0.04676 (ω>0) vs +0.03227 (ω<0) → **sign flips**; stationary lower opposite sign; two zones independent rates |
| 37 | OpenFOAM | transient AMI | **BLOCKED (time)** | no sliding-interface case executed in budget |
| 38 | ROSS 3.0.0 | Jeffcott / soft-bearing / short-stiff | EXECUTED | first critical 8698.0 rpm vs analytic 10693.4 rpm (18.7%, massless-shaft idealisation); modal 8738.1 rpm (0.46% vs Campbell); soft bearing 2887.1 rpm < rigid |
| 38 | ROSS 3.0.0 | unbalance response (direct) | EXECUTED | peak 0.3866 m at 915.05 rad/s = 8738 rpm, coincident with first whirl |
| 38 | ROSS governed script | forced analysis | **BLOCKED** | repo `run_ross.py` passes ROSS 2.x kwarg `frequency`; ROSS 3.0 API uses `speed_range` (product code not modified) |
| 38 | code_aster 18.1.6 | cantilever/modal | **BLOCKED** | `run_aster` present but `as_run` absent; no canonical case executed in budget |
| 39 | Elmer 26.2 | steady 1-D Dirichlet | EXECUTED | T_mid 50.0 K vs analytic 50.0 (**0.0%**); mesh independent |
| 39 | Elmer 26.2 | prescribed heat flux | EXECUTED | T_left 10.0 K vs analytic 10.0 (**0.0%**) |
| 39 | Elmer 26.2 | transient uniform heating | EXECUTED | T=1.0 K at t=0.1 vs analytic 1.0 (**0.0%**) energy accumulation |
| 39 | OpenMDAO participants | machine+drive+battery+thermal closure | EXECUTED | delivered 1847.162841025 W = consumed 1847.162841036 W, **residual −1.19e-8 W**; power/heat balance pass; 12000 rpm fail-closed |
| 40 | preCICE 3.4.0 | native implicit nonmatching exchange | EXECUTED | 2 resolutions (4, 8); both participants exit 0; consistent-mapping max error 1.25 → 0.625; 15 checkpoint/rollback events each |
| 41 | convergence gate + GEN 12 | end-to-end receipt + negative acceptance | EXECUTED | positive control validated-final=true; removing a receipt → refused (`required-participant-unavailable:thermal-conduction`); invalidating independence → refused |

## Gated / not done (honest)

- OpenFOAM **transient AMI** and **multi-stage MRF** — BLOCKED BY TIME.
- ROSS **governed forced analysis** — BLOCKED on a ROSS 3.0 API change (direct ROSS 3.x
  unbalance response was run instead and is labelled as such).
- **Code_Aster** — runner present, no native structural receipt → BLOCKED for #38/#41.
- Elmer **multi-material** conduction — BLOCKED BY TIME.
- preCICE **conservative-mapping integral conservation** not separately quantified
  (consistent-mapping error at two resolutions is recorded).

Nothing above was substituted by an analytical result; screening/analytic paths are
labelled and never counted as native.
