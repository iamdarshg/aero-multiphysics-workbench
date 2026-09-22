# Issues 30–96 closure audit (2026-09-22)

## ROSS verification

The current-head ROSS benchmark is recorded in `ross-current.json`. All five
governed cases executed with `ross-rotordynamics 2.3.0`, and the verifier's six
scientific acceptance checks passed:

- first critical speed: 8,697.998 rpm;
- Jeffcott reference difference: 18.66% (limit 25%);
- modal/Campbell difference: 0.458% (limit 5%);
- forced-response peak: 8,806.723 rpm, 1.25% from the first critical (limit 20%);
- soft-bearing critical speed below the rigid-bearing result;
- short/stiff critical speed above the rigid-bearing result.

The benchmark now exits nonzero unless both execution and scientific checks
pass. A direct-library unbalance probe remains supplementary evidence and
cannot promote a failed governed run.

## Verification run

| Gate | Result |
| --- | --- |
| ROSS focused tests | 55 passed, 1 platform skip |
| EDF ROSS regressions | 2 passed, 27 deselected |
| AIRFRAME / VEHICLE-SYSTEMS / recursive-platform regressions | 374 passed |
| Fast repository gate | passed: JS unit 118, platform 48, web 65, smoke 1, fast 11, Python core 61, integration 38, physics 54 + 1 skip, Python-fast 4 |
| Documentation consistency | 5 passed |

## Open-issue disposition in range 30–96

| Issue | Disposition | Evidence or blocker |
| --- | --- | --- |
| #59 | keep open | ROSS is now verified, but the independent all-participant definition still has native Code_Aster, preCICE/electrical-closure, and other receipt blockers recorded in `SUMMARY.md`. |
| #74 | keep open | The AIRFRAME parent explicitly depends on the still-open independent proof in #84. |
| #75 | close | Shared unit normalization replaced the optimizer-local table; multi-dimension and fail-closed tests pass. |
| #78 | close | The governed OpenVSP/VSPAERO execution/parser path has a real native solver receipt; missing capability remains fail-closed. The body-length unit regression found during this audit is fixed and tested. |
| #81 | close | AIRFRAME uses the generic generation/campaign/regeneration/fidelity path; deterministic focused and integration regressions pass. |
| #82 | close | Shared-rotor collective/cyclic, azimuthal loading, inflow, flapping hooks, hub loads, constraints, installed wake exchange, and re-trim regressions pass. |
| #83 | close | The lifting-body requirements-to-generic-campaign fixture preserves thick-body identity and volume constraints; OpenVSP body serialization is meter-correct and the prior native workflow exercised a thick body. |
| #84 | keep open | `verify_airframe_families()` still intentionally returns pending/unavailable without complete family inputs and replay receipts; no current committed three-family passed ledger exists. |
| #85 | keep open | The mission-complete epic depends on #84 and the broader independent integration evidence. |
| #94 | close | Distributed transfer, temporal/harmonic contracts, multi-base harmonics, reverse dependency indexing, selective invalidation, and recursive integration regressions pass. |
| #96 | close | All six residual lanes have executable consumers and focused coverage; the combined AIRFRAME / VEHICLE-SYSTEMS regression cluster passes. |

All other issues from #30 through #96 were already closed at the start of this
audit. This disposition deliberately leaves the four evidence umbrellas open;
passing implementation tests or one native solver receipt is not relabelled as
their broader independent verification.
