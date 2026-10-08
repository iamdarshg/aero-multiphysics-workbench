# Codex implementation contract: drone-mech generative engineering campaign

**Target:** `iamdarshg/aero-multiphysics-workbench` branch `feat/drone-mech-generative-pipeline`.
**Source aircraft:** `iamdarshg/drone-mech`, particularly `highspeed_edf/` and its Phase 15 implementation.
**Intent:** add a *working* generate → CAD → screen → improve → persist loop. This document is an implementation contract, not evidence that the feature is implemented.

## Critical reconnaissance already done

- Workbench includes `packages/optimization/aeroworkbench_optimization/{generation,campaign,planner,quality}.py` and `packages/airframe/aeroworkbench_airframe/{campaign,synthesis/lifting_body}.py`. REUSE the existing campaign engine rather than duplicating an optimizer.
- Real native CAD/STEP exports already work through `packages/geometry/aeroworkbench_geometry/{parametric,regeneration}.py`, `examples/edf/80mm_three_stage/edf_geometry.py`, and `export_artifacts`. Kernel absence must fail closed.
- Existing EDF analytical screening lives in `examples/edf/80mm_three_stage/edf_screening.py`. Its explicit `freestream_m_s <= 120` precondition makes it UNSUITABLE for scoring 700 km/h (194.4 m/s). Never extrapolate it or silently clamp flight speed.
- Drone-mech `highspeed_edf/phase15/optimization/phase15_high_cost_generative.py` imports `aeroworkbench_vehicle_systems.coupled_optimizer`, which is not present in the current `aero-multiphysics-workbench` main-tree listing. Resolve this interface incompatibility deliberately rather than claiming Phase 15 runs.
- Drone-mech `highspeed_edf/requirements/requirements_r2.yaml` identifies dual 80-mm EDFs, three motors per duct, 700 km/h stretch speed, 16 mm maximum rotor chord and 5 mm maximum stator chord. There are later candidate revisions; read the entire authoritative source/history and reconcile newer user instructions before freezing campaign parameters.
- The unrelated four-FA4119-propeller quad is NOT the high-speed EDF airframe. Do not introduce quad geometry or assume the 13-inch propeller operating point describes duct performance.
- Repository `AGENTS.md` requires tests before code, solver provenance, resource-aware scheduling, aggregate project RSS <1GB and fail-closed native capability handling. Honor it.

## Acceptance-driven deliverables

Create `examples/drone_mech_generative/` as a thin integration using *existing* workbench packages. Preferred files:

1. `requirements.py`: load a local clone/path of the separate `drone-mech` repository, identify the exact requirement revision and hash, validate user-source traceability and reject missing/contradictory mandatory fields. Do not copy another repository's private requirements into workbench.
2. `geometry.py`: adapt actual Phase 15 aircraft geometry construction or canonical native airframe regeneration, combined with true EDF subassemblies; produce at least 3 distinct native, editable CAD candidates and STEP exports. Use safe parametrization, actual B-Rep solids, geometry checks, component interface/clearance checks, mass and CG where supported. An EDF-only assembly or generic cylinders may be an initial diagnostics mode but do not pass the aircraft CAD gate.
3. `screen.py`: a fast **validity-limited** screening model using existing analytical/physics participants; report `source=analytical`, conditions, validity ranges, uncertainties and explicit failed constraints. For 700 km/h, require an appropriate compressible flight/propulsion evaluation or return `unsupported_fidelity` / `needs_native_solver`, NEVER extrapolated static thrust.
4. `experiment.py`: bounded deterministic sample generation using existing `CampaignSpec`, `GenerationRequest`, `run_campaign` and quality gates. A fixed seed generates >=3 distinct valid candidate parameter sets. Run at least one measured mutation/selection step after a first evaluation, and preserve parent hashes.
5. `storage.py`: resume-safe SQLite WAL candidate/solver/approval journal or reuse existing native persistent storage; candidate hashes, source SHA, experiment parameters, solver provenance, failures, output file hashes, timestamps, resumability, cache hits.
6. `cli.py`: deterministic `python -m examples.drone_mech_generative.cli --drone-repo /path/to/drone-mech --out /path/to/output --count 3 --seed 42 --max-native 0` command. Native solver stages are opt-in, budgeted, and capability checked. Support `--resume` and `--status`.
7. `gallery.py`: HTML + SVG or CAD-generated previews for candidate comparison and Pareto/constraint summaries, with visually prominent source/fidelity badges and downloadable STEP. No fabricated render/physics data.
8. `tests/physics/test_drone_mech_generative.py`: deterministic test-first coverage for source mismatch, EDF-vs-quad confusion, design hash stability, parameter mutation, actual STEP/file/hash on kernel-enabled environment, loss of native solver capability, failed or nonconvergent results excluded from Pareto, resume/idempotency, budget enforcement, and a complete three-candidate loop.

## Vertical slice — mandatory first

1. Identify the actual frozen/revised EDF constraints from `drone-mech`. Preserve `source_repo`, commit SHA, requirements hash and any labeled assumptions in an input manifest. This MUST depend on an explicit local clone/path: no downloading dependencies silently.
2. Generate 3 distinct candidate aircraft+EDF native B-Reps, export real STEP, write per-candidate parameter hashes.
3. Run geometry/packaging/mass sanity and an actual permitted analytical fidelity. Persist numerical results with unambiguous provenance and explicit invalid/unsupported conditions.
4. Change one parameter set in response to these measured results; generate/evaluate the revised design.
5. Present a standalone HTML gallery and machine-readable comparison.
6. Provide commands, tests, exact output evidence, known limitations.

**DO NOT** mark the loop validated solely from JSON files or nominal method calls. If native CAD is missing, fail closed, retain diagnosis and tests, and do not fabricate STEP. If compressible propulsion/native flow is unavailable, report the high-speed objective unverified while retaining useful lower-fidelity geometry and screening results.

## Integration and cost constraints

- Reuse existing OpenFOAM/Gmsh/ROSS/Code_Aster/Elmer/OpenMDAO/native-scheduler pathways. Do not import new heavy external services or duplicate whole packages.
- Native CFD should be an optional second fidelity rung, never required for inexpensive baseline tests. Configure resource/time/disk caps and no cloud compute provisioning.
- Avoid committing generated STEP/mesh/large solver outputs, cache DBs, or secrets. Add focused ignore patterns.
- Keep `aero-multiphysics-workbench` as the runtime host, `drone-mech` as the authoritative design-input repository. Do not move or rewrite historical drone-mech data.
- Keep one self-contained runner/example testable via existing `uv --directory services/api` environment. Document exact use from both OpenCode/OpenRig and developers.
- Respect <1GB owned-process aggregate RSS for baseline tests; reserve full native CFD for separately admitted jobs.
- Do not merge or push to default branch automatically. Work on the branch; produce a draft PR with evidence and an accurate checklist of unresolved fidelity gates.

## Required validation

At minimum run:
- relevant `pytest` tests under `services/api` in the project's documented environment;
- `ruff` (and mypy where practical) for changed Python files;
- a real native-CAD 3-candidate run when CadQuery is available;
- dry/no-native mode proving accurate fail-closed semantics;
- resume + artifact hash checks.

Claim only tests that actually executed; no synthetic "test output." Record command, exit status, log path and git commit.

## Codex execution discipline

Do not spend the whole turn planning. Inspect relevant files once, write tests first, implement the smallest vertical slice, test and commit incrementally. Then extend. Do not produce a README-only PR. Do not label the feature complete until the loop has demonstrably generated new CAD, evaluated candidates and iterated once. Report unresolved high-speed CFD/structural fidelity honestly.

## OpenCode / OpenRig handoff

Once the implementation branch contains tested code, OpenCode should fetch it onto the GCP VM, check its local clone of `drone-mech`, run the bounded example first (no cloud spend), examine CAD/gallery/results and assign OpenRig integration tasks. Do not declare flight/manufacturing readiness.
