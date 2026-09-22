# Bounded GCP verification (2026-09-22)

This run used short-lived Spot workers in `us-central1-a` under the explicitly
approved US$0.10 additional ceiling. Both workers were deleted after evidence
collection. No result below is promoted unless its native receipt and quality
gate passed.

## Native solver worker

- Worker: `aero-final-verification-20260922`
- Machine: Spot `e2-standard-2`
- Wall time: approximately 5 minutes 4 seconds
- Checkout: `main` at the final-verification worker commit
- Driver: `scripts/gcp/final-verification-startup.sh`, `install-solvers.sh`,
  `run-benchmarks.sh`

Observed receipts:

- OpenFOAM v2412: channel, cavity, and rotating-frame MRF benchmarks executed;
  channel mass imbalance was approximately `1e-9`, and MRF torque sign reversal
  was observed. The MRF cases were diagnostic and not treated as a complete EDF
  AMI proof.
- Elmer 26.2: steady Dirichlet, prescribed-flux, and mesh-level thermal cases
  executed.
- ROSS: `PARTIAL`; the governed participant resolved the wrong `ross` module and
  failed before the requested native model.
- Electrical closure: `BLOCKED`; the worker environment lacked `pydantic`.
- preCICE: `BLOCKED`; the native Python binding/MPI initialization was
  unavailable.
- Cross-solver gate: executed and correctly returned `validatedFinal=false` with
  missing participant, closure, field-coupling, and independence blockers.

## AIRFRAME native capability probe

- Worker: `aero-airframe-native-probe-20260922`
- Machine: Spot `e2-small`
- OpenVSP/VSPAERO package probe: conda-forge has no `openvsp` package in the
  worker environment.
- Observed executables: none (`vspaero`, `vspaero.exe`, `openvsp`, `vsp`).
- Native result published: `false`.

The AIRFRAME governed adapter therefore remains capability-gated and fail
closed. This probe is evidence of unavailable capability, not a native result.
