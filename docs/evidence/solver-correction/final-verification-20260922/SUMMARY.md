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

## AIRFRAME native capability and solve

- Worker: `aero-openvsp-native-20260922e`
- Machine: Spot `e2-small`
- OpenVSP/VSPAERO package: official OpenVSP `3.52.1` Ubuntu 24.04 package,
  installed with its `desktop-file-utils` prerequisite.
- Observed executables: `/usr/local/bin/vspaero` and `/usr/local/bin/vsp`.
- Capability: available and exercised through the official OpenVSP AngelScript
  workflow under the governed participant runner.
- Native receipt: `source=native_solver`, `validity.passed=true`,
  `validity.checks.converged=true`, and `solver_csv_present=true`.
- Native coefficients: `CL=-0.006175042038`, `CD=0.009902860619`,
  `CY=0`, `Cl=0`, `Cm=0.011089761547`, `Cn=0`.
- Native artifacts: `vspaero-result.json`, `stdout.log`, `stderr.log`, and
  official `Results.csv`.
- The Spot worker was deleted after receipt collection.

## Current-head local ROSS re-verification

ROSS was re-run locally after repairing the benchmark harness so that process
success cannot be mistaken for scientific acceptance. The governed forced
response is now centred on the Campbell-detected first critical instead of a
3,000 rpm operating point whose sweep ended before resonance.

- Commit under verification: `7354ee7f678060f9bc1931b4b30dcafeff31d939`.
- Solver: `ross-rotordynamics 2.3.0`; all five governed cases exited zero.
- Jeffcott first critical: 8,697.998 rpm versus the 10,693.425 rpm analytical
  reference (`18.66%`, inside the declared `25%` cross-model tolerance).
- Modal/Campbell first-mode difference: `0.458%` (limit `5%`).
- Soft-bearing first critical: 2,887.080 rpm, below the rigid-bearing result.
- Short/stiff first critical: 46,858.809 rpm, above the rigid reference.
- Forced-response peak: 8,806.723 rpm, `1.25%` from the Campbell first critical
  (limit `20%`).
- Direct-library unbalance probe: `EXECUTED` and retained as supplementary
  evidence; it cannot promote a failed governed run.
- Scientific checks: 6/6 passed; `verificationPassed=true`.
- Focused governed tests: 55 passed, 1 Windows-only RSS probe skipped; EDF ROSS
  tests: 2 passed, 27 deselected.
- Wall time: 65.3 s for the bounded benchmark; GCP spend: US$0.00.
- Receipt: `ross-current.json` in this directory.

The optional `ccp` dependency emitted a missing-REFPROP warning and selected its
CoolProp/HEOS fallback. The warning is preserved in the case receipts; it did
not prevent any ROSS case or acceptance check from executing.
