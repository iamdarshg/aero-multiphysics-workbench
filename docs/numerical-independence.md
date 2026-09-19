# Numerical independence, closure, and promotion gates (GEN 12)

GEN 12 closes the scientific execution loop: promoted candidates are only
called validated when their numerical sufficiency and physical closure are
proven from executed evidence, and one generic generative campaign is carried
from a mixed design space to a provenance-backed candidate set.

Everything here is integration and validation. No application-specific
acceptance logic and no second solver path are introduced; the runner, gates,
and benchmark reuse the existing quality, convergence, fidelity, campaign,
mesh, coupling, and native-envelope contracts.

## A. Numerical-independence study runner

Module: `packages/convergence/aeroworkbench_convergence/independence.py`

* `RefinementLevel(name, resolution, declared)` — one declared ladder rung. The
  characteristic resolution is a mesh size or a time step; `declared` records
  scalar metadata such as `element_count` or `dt_s` as **evidence only**.
* `QuantityOfInterest(name, unit, relative_tolerance, absolute_tolerance,
  reference_scale)` — each QoI carries its own normalized tolerance band.
* `StudyRun(level, run_id, input_hash, qoi, valid, source, artifact_hash,
  detail)` — the executor must supply the real run id and input hash; the
  runner never invents one.
* `run_mesh_independence(...)` (>= 2 levels) and
  `run_timestep_independence(..., transient=True)` (>= 3 levels for transient
  validation) delegate to `run_independence_study`.

Returned by `IndependenceReport`: all run ids and content hashes, per-QoI
values, successive deltas and relative deltas, observed order and Roache GCI
where mathematically applicable, `accepted`, and the rejection reason.

Acceptance rule (fail-closed):

1. every executor run must be `valid` (or the caller explicitly opts out),
2. the two **finest** solutions must agree within
   `absolute_tolerance + relative_tolerance * max(|finest|, reference_scale)`,
3. a three-or-more-level trend whose finest change *grows* is rejected as
   oscillatory/divergent.

Element count is **not** the basis. Two meshes with identical element counts
and materially different QoI fail; two meshes with different element counts and
a converged QoI pass. `element_count` is reported for audit only.

Observed order `p = ln(|e_fine / e_coarse|) / ln(r)` and
`GCI_fine = F_s |(q_fine - q_coarse) / q_fine| / (r^p - 1)` are reported only
when there are at least three levels, the last two deltas are non-zero and
share a sign (monotone), and the refinement ratio is uniform and `> 1`.
Otherwise they are `None` with the trend detail explaining why.

## B. Physical-closure gates

Module: `packages/convergence/aeroworkbench_convergence/closure.py`

`assess_closure(family, simulated, reference, required=None)` validates each
declared quantity with the existing normalized `ClosureMeasure` tolerances
(`measures.py`), so 1 W and 1 m are never compared against the same raw
number. Family defaults:

| family | default measures |
| --- | --- |
| `mass` | mass |
| `energy` | energy |
| `momentum` | momentum, force, torque |
| `force` | force, torque |
| `electrical-power` | shaft-power |
| `heat-balance` | heat-flow, energy, temperature |
| `field-interface` | mass, energy, force |
| `geometry` | clearance, displacement |
| `resonance` | resonance-separation, critical-speeds, modes, forcing-spectra |

A missing or non-finite declared quantity fails closed with an explicit
`missing` list. Additional gates:

* `assess_field_interface_conservation(field, source, target, tolerance,
  coordinates...)` compares the field integral on both sides of a nonmatching
  interface; a relative error above tolerance (default `1e-6`) fails.
* `assess_resonance_margin(operating_speed, critical_speeds, critical_margin,
  warning_margin)` gates dynamic/resonance margins.
* `assess_geometry_clearance(required, achieved, tolerance)` gates
  geometry/clearance.

## C. Promotion gate

Module: `packages/convergence/aeroworkbench_convergence/promotion.py`

`assess_promotion(candidate_hash, evidence, require_mesh_independence,
require_timestep_independence)` returns `validated-final` only when every
required participant passes **all** of:

* required participant available (not deferred, not unavailable),
* solver converged,
* required mesh and time-step independence passed,
* physical closure passed,
* field coupling passed,
* result inside its validity envelope.

Otherwise the candidate is `incomplete-diagnostic` with the ordered blocker
list. A deferred participant or a failed closure can never be reported as a
validated winner.

## D. Generic generative end-to-end benchmark

Package: `benchmarks/independence/` (`generic_benchmark.py`, `manifest.json`,
`run.py`, `full-science-ci.yml`).

The benchmark is a deliberately simple rotating / thermo-fluid-mechanical
assembly whose acceptance is defined on declared quantities and capabilities,
never on application names. Steps:

1. mixed/conditional design space (numeric, integer, categorical, boolean,
   `activeWhen`, and branch-gated members),
2. candidate generation/permutation from a fixed seed,
3. cheap deterministic evaluations,
4. automatic weighted selection + diversity,
5. multi-fidelity promotion,
6. real CAD regeneration from declared variables (cadquery/OCP),
7. real Gmsh mesh generation,
8. native flow (OpenFOAM) — capability-gated,
9. native structural / thermal (Code_Aster / Elmer) — capability-gated,
10. machine + drive + battery + thermal scalar coupling,
11. rotor dynamics (ROSS native; screening estimate is labelled screening),
12. field exchange (native preCICE; otherwise a clearly labelled
    `analytic-transfer`),
13. mesh and time-step independence over declared QoI,
14. provenance-backed candidate set with promotion gate,
15. deferred-capability audit.

Every capability is probed. An absent native engine is reported `SKIPPED` with
the probe reason. A present native engine is reported `PARTIAL`: the generic
benchmark owns no application-agnostic native case, so the native receipt
belongs to that participant's own benchmark and is never fabricated or
substituted here. The report survives `json.dumps`, and `reproducible`
re-derives the design hash and campaign digest from the same seed.

Run it (bounded, no native binaries):

```
uv run --directory services/api python -m benchmarks.independence.run --output report.json
```

Full science (solver-equipped runner, opt-in, never fakes success):

```
uv run --directory services/api python -m benchmarks.independence.run \
    --execute-native --require-native --output gen12-full-science.json
```

## E. Deferred-capability audit closure

The benchmark's `deferred-capability-audit` step emits one entry per required
capability with `PASS` / `PARTIAL` / `BLOCKED` / `FAIL` and a reason. `PASS`
requires an executed receipt with a real hash (CAD shape hash, Gmsh mesh hash,
converged scalar coupling with passing power/heat balance). A present engine
without a receipt from this benchmark is `PARTIAL`; an absent native engine is
`BLOCKED`. No unrelated product or cloud requirement is touched.

`docs/requirements-audit.json` is owned by a different workstream and is **not**
edited here. The audit evidence produced by the benchmark is therefore emitted
in the benchmark report and summarized below; moving the corresponding audit
rows to `PASS` requires a solver-equipped run and is an explicit blocker on a
host without the native binaries.

## F. Regression gate

`benchmarks/independence/full-science-ci.yml` is a ready-to-install workflow
template (owned by this workstream, deliberately not placed under
`.github/workflows` because that path is outside this workstream's ownership):

* `bounded-gates` runs the solver-free GEN 12 gates on a hosted runner,
* `full-science` runs only on a `[self-hosted, solver-equipped]` runner. It
  first runs the participant native-receipt tests (OpenFOAM, Code_Aster, Elmer,
  native preCICE), then runs the generic benchmark with
  `--execute-native --require-native`, which fails when a required native
  engine is `BLOCKED` and prints `partialCapabilities` so a present-but-unrun
  engine is never presented as a receipt.

A maintainer copies it to `.github/workflows/gen12-full-science.yml`. Neither
job reports success without performing the work.

## Tests

`tests/physics/test_gen12_independence.py`:

* mesh QoI convergence passes on converging synthetic data and fails on
  non-converging data,
* element-count similarity alone cannot satisfy flow-solution independence,
* transient time-step independence requires three levels, passes converging
  data, and fails slowly drifting data,
* closure gates (mass, momentum/force/torque, energy, heat balance, field
  interface conservation, resonance, clearance) pass and fail honestly,
* deferred/unavailable participants and failed closure block validated-final,
* the generic end-to-end campaign is reproducible from seed/design hash,
* final lineage retains every candidate, promotion, evaluation, and
  independence-run link,
* native shortfalls never yield a validated-final candidate or a fabricated
  audit `PASS`,
* real CAD regeneration and real Gmsh meshing execute when the kernel is
  present.

Focused command:

```
uv run --directory services/api pytest -q -k "gen12 or independence"
```

## Executed evidence (this host)

Host capabilities: cadquery/OCP present, Gmsh present, ROSS/PyBaMM present;
OpenFOAM, Code_Aster, Elmer, and native preCICE binaries are **absent**.

Benchmark run (`seed=0`, CAD + mesh enabled, native disabled):

| item | value |
| --- | --- |
| design hash | `c36fde87e74e48377b018c435c4d3587583a306a53837569da90492d83b0b393` |
| campaign digest | `e229bf1039bdad33b5d6f0389121763e055e69cbf1e181e652d35a4947563b70` |
| reproducible | `True` |
| CAD shape hash | `6d2d5f98ad43acab0039f2ec04bb3407ed8a472ce54aed2aa53065b55acd475d` (5 STEP components) |
| mesh hash | `6a997d8bfb6402c4b666b7cb92a2d59dfc30e6aa791805bb882d26c245a72e45` |
| mesh quality | 149 424 elements, `min_sicn=0.171`, 0 inverted |
| scalar coupling | converged in 23 iterations, residual `6.72e-07`, power balance `PASS`, heat balance `PASS` |
| rotor dynamics | `PARTIAL`: ROSS present, labelled screening estimate 340 192 rpm, resonance clear, no native receipt from this benchmark |
| steps | 11 EXECUTED, 1 PARTIAL, 4 SKIPPED, 0 FAILED |
| validated-final candidates | 0 of 18 (native capabilities deferred/unavailable; field coupling analytic-only) |

Independence (declared QoI, not element counts):

| study | QoI | finest | deltas | observed order | GCI | accepted |
| --- | --- | --- | --- | --- | --- | --- |
| mesh | pressure_drop | 1.7834 | -0.2400, -0.0600 | 2.000 | 0.0140 | True |
| mesh | mass_flow | 1.3917 | -0.1200, -0.0300 | 2.000 | 0.0090 | True |
| time step | peak_amplitude | 1.7784 | -0.0300, -0.0150 | 1.000 | 0.0105 | True |

Capability audit: `geometry PASS`, `mesh PASS`, `scalar-coupling PASS`,
`rotordynamics PARTIAL` (screening only, no native receipt),
`flow/structural/thermal/field-coupling BLOCKED` (native engines absent).
No native `PASS` is reported without an executed receipt.

## Explicit blockers / limitations

* The heavyweight native solvers (OpenFOAM, Code_Aster, Elmer, native preCICE)
  are not installed on this host, so the benchmark honestly reports them
  `SKIPPED`/`BLOCKED` and no candidate is `validated-final` here.
* The generic benchmark deliberately does **not** own application-agnostic
  native cases, so even on a solver-equipped runner it reports a present native
  engine as `PARTIAL` rather than fabricating a receipt. Native receipts are
  produced by the participant benchmarks (`test_gen06_openfoam.py`,
  `test_gen07_code_aster.py`, `test_gen08_elmer.py`,
  `test_gen11_precice_native.py`); the full-science workflow runs them before
  the generic capability audit. Reaching `validated-final` therefore requires
  linking those receipts through the promotion gate, which is tracked as an
  explicit integration follow-up rather than faked here.
* `docs/requirements-audit.json` is outside this workstream's ownership; its
  rows for the GEN 01–11 scientific capabilities are updated only from
  verified executed evidence and were not touched here.
* The workload is bounded (18 candidates, one CAD/mesh case); no large sweeps
  or GCP resources were used, so GCP spend is `$0.00`.
