# Aero Multiphysics Workbench Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver, validate, document, and deploy the complete coupled engineering workbench defined by the 85-section source mandate.

**Architecture:** One immutable physical design revision feeds a content-addressed computation graph. OpenMDAO coordinates scalar coupling, preCICE coordinates field coupling, and allowlisted solver workers return provenance-backed result envelopes that must pass global physical convergence and explicit quality gates.

**Tech Stack:** Next.js, React, TypeScript, FastAPI, Pydantic, Python 3.12, OpenMDAO, preCICE, OpenFOAM, Code_Aster, ROSS, PyBaMM, Elmer, Cantera, pyCycle, CadQuery/OpenCascade, Gmsh, FreeCAD, SQLite, VTK/glTF/Parquet/HDF5/Zarr, Docker, Terraform, GCP Batch, official Model Context Protocol SDK.

**Spec:** `docs/superpowers/specs/2026-09-09-aero-multiphysics-workbench-design.md`

## Global Constraints

- Project-owned local processes must stay below 1 GiB aggregate RSS; enforce 896 MiB.
- Remote compute is disabled by default and requires the user's explicit switch and immutable cost limits.
- Every number declares source, fidelity, units, validity, input hash, solver identity, and provenance.
- Native capability failures are explicit; no adapter may substitute mocked, analytical, or surrogate output.
- Use allowlisted executable/argument builders without shell execution.
- Use isolated worktrees; route most implementation tasks to `gpt-5.6-luna`; merge serially after independent review.
- Use Chrome or the built-in browser for rendered verification.

---

### Task 1: Recover, normalize, and integrate the three existing workstreams

**Files:**
- Modify: `package.json`
- Modify: `pnpm-workspace.yaml`
- Modify: `.gitignore`
- Create: `scripts/verify-workspace.ps1`
- Test: `tests/smoke/workspace.test.mjs`

**Interfaces:**
- Consumes: existing `feature/frontend-workbench`, `feature/core-physics-api`, and `feature/platform-integrations` branches.
- Produces: one buildable main branch with `pnpm test`, `pnpm typecheck`, and Python test entrypoints.

- [x] Review and commit each recovered branch without generated logs, caches, virtual environments, or TypeScript build-info files.
- [x] Run each branch's focused tests and record peak process RSS.
- [x] Merge branches serially, resolving root-manifest conflicts by preserving every workspace package and script.
- [x] Add `tests/smoke/workspace.test.mjs` that asserts every declared workspace package has a manifest and test command.
- [x] Run `pnpm install --frozen-lockfile`, `pnpm test`, and the API's `uv run pytest`; expect all focused suites to pass.
- [x] Commit with `chore: integrate initial workbench slices`.

### Task 2: Create the authoritative requirement and evidence ledger

**Files:**
- Create: `packages/schema/src/audit.ts`
- Create: `docs/requirements-audit.json`
- Create: `scripts/audit-requirements.mjs`
- Test: `tests/unit/requirements-audit.test.ts`

**Interfaces:**
- Consumes: the 85 numbered sections and 44 final stopping conditions.
- Produces: `RequirementEvidence { id, title, status, evidence, lastVerifiedAt }` and a failing audit command when mandatory evidence is incomplete.

- [x] Write a failing test requiring unique entries for sections `0` through `85` and stopping conditions `1` through `44`.
- [x] Verify the test fails when an ID or evidence field is absent.
- [x] Implement the typed schema and seed the ledger with honest `PASS`, `PARTIAL`, `FAIL`, or `BLOCKED` states from current evidence.
- [x] Implement `pnpm audit:requirements` so only evidence-linked `PASS` entries satisfy the final gate.
- [x] Run the audit; expect a nonzero exit while mandatory work is incomplete and a machine-readable summary.
- [x] Commit with `feat: add evidence-backed requirement audit`.

### Task 3: Canonical design state, units, variants, DAG, cache, and provenance

**Files:**
- Create: `packages/schema/src/design.ts`
- Create: `packages/units/src/index.ts`
- Create: `packages/cache/src/content-addressed.ts`
- Create: `packages/provenance/src/ledger.ts`
- Create: `services/api/aeroworkbench_api/repositories/sqlite.py`
- Test: `tests/unit/design-state.test.ts`
- Test: `tests/integration/test_sqlite_roundtrip.py`

**Interfaces:**
- Consumes: normalized dimensional inputs and immutable user/compute policy.
- Produces: `DesignRevision`, `VariantRevision`, `ContentKey`, `ProvenanceEvent`, and repository interfaces.

- [x] Write failing tests for unit normalization, deterministic hashes, parent-child variants, cache invalidation, and append-only provenance.
- [x] Verify equal normalized inputs hash equally and a semantic/material/solver change invalidates descendants.
- [x] Implement focused packages and SQLite repositories with migrations.
- [x] Add artifact references for Parquet, VTK, glTF, STEP/BREP, and HDF5/Zarr without placing large fields in SQLite.
- [x] Run unit and database roundtrip tests; expect deterministic hashes across processes.
- [x] Commit with `feat: add canonical design graph and provenance`.

### Task 4: Harden the scheduler, process supervisor, solver gateway, and capability detector

**Files:**
- Modify: `packages/solver-contracts/src/scheduler.ts`
- Modify: `packages/solver-contracts/src/runtime.ts`
- Create: `services/workers/process_supervisor.py`
- Create: `solvers/manifests/*.json`
- Test: `tests/platform/platform.test.ts`
- Test: `tests/integration/test_process_supervisor.py`

**Interfaces:**
- Consumes: `ParticipantManifest`, a per-job directory, resource reservation, and immutable compute policy.
- Produces: capability receipts, bounded `RunReceipt`, sampled peak RSS, termination reason, stdout/stderr artifact hashes, and parsed result eligibility.

- [x] Write failing tests for an 896 MiB aggregate ceiling, process-tree accounting, command allowlisting, path containment, timeout, cancellation, and unavailable capabilities.
- [x] Replace arbitrary command input with solver-specific executable and argument builders.
- [x] Implement Windows process-tree termination and a portable POSIX process-group path.
- [x] Probe OpenFOAM, Code_Aster, preCICE, ROSS, PyBaMM, Elmer, Cantera, pyCycle, CadQuery, Gmsh, OpenVSP, and FreeCAD without shell execution.
- [x] Run the tests plus `scripts/platform/measure-rss.ps1`; the focused worker-tree peak was 103 MiB against the 250 MiB check (the script explicitly labels this non-authoritative host aggregate).
- [x] Commit the worker-boundary implementation and Windows cleanup hardening.

### Task 5: Deliver the real engineering MCP server

**Files:**
- Modify: `mcp/engineering/server.ts`
- Create: `mcp/engineering/tools.ts`
- Create: `mcp/engineering/policy.ts`
- Test: `tests/mcp/engineering.e2e.test.ts`

**Interfaces:**
- Consumes: typed API client, ownership context, local/remote/destructive permissions, and cost limits.
- Produces: official MCP stdio tools for inspection, variant creation, bounded scheduling, cancellation, and provenance retrieval.

- [ ] Write an SDK client E2E test that performs initialize, tools/list, and tools/call over stdio.
- [ ] Verify stdout contains protocol frames only and diagnostic output goes to stderr.
- [ ] Register typed tools with independent mutation, destructive, remote, and cost gates.
- [ ] Reject arbitrary paths, commands, unowned jobs, and attempts to enable remote compute through MCP.
- [ ] Run MCP E2E and platform policy tests; expect all unauthorized calls to fail closed.
- [ ] Commit with `feat: add governed engineering MCP server`.

### Task 6: Geometry, semantic topology, CAD interchange, and meshing

**Files:**
- Create: `packages/geometry/aeroworkbench_geometry/canonical.py`
- Create: `packages/semantics/aeroworkbench_semantics/reconcile.py`
- Create: `packages/mesh/aeroworkbench_mesh/gmsh_adapter.py`
- Create: `solvers/freecad/adapter.py`
- Create: `examples/edf/geometry.py`
- Test: `tests/physics/test_geometry_semantics_mesh.py`

**Interfaces:**
- Consumes: parametric geometry definitions and semantic assignments.
- Produces: shape hashes, STEP/BREP/glTF artifacts, topology maps, mesh receipts, quality metrics, and reconciliation reports.

- [x] Write tests for a parametric 70 mm EDF, semantic face persistence, native artifact receipts, and quality thresholds.
- [ ] Implement CadQuery/OpenCascade canonical geometry and explicit parameter dependencies.
- [x] Implement an explicit unavailable receipt for FCStd/headless FreeCAD when the native capability is missing.
- [ ] Implement Gmsh structural/fluid meshes, boundary layers, rotating regions, and preCICE interface sets.
- [ ] Add guarded mesh morphing with semantic correspondence and quality gates; remesh when either gate fails.
- [ ] Run the geometry/mesh tests and store generated artifact hashes and measured quality.
- [ ] Commit with `feat: add semantic CAD and mesh pipeline`.

### Task 7: OpenMDAO scalar coordination, coupling strength, convergence, and adaptive fidelity

**Files:**
- Create: `packages/coupling/aeroworkbench_coupling/openmdao_problem.py`
- Create: `packages/convergence/aeroworkbench_convergence/manager.py`
- Create: `packages/optimization/aeroworkbench_optimization/fidelity.py`
- Test: `tests/physics/test_scalar_coupling.py`

**Interfaces:**
- Consumes: participant scalar ports, coupling strength, expert overrides, quality history, and constraints.
- Produces: converged scalar state, physical closure report, fidelity decision, DOE/optimization trace, and checkpoint.

- [ ] Write failing cyclic motor-thermal-EDF tests and verify individual residual convergence cannot override an energy-closure failure.
- [ ] Implement the 0.0-1.0 coupling-strength expansion with default 0.90 and visible expert parameters.
- [ ] Implement mass, energy, force, geometry, thermal, electrical, and dynamic convergence measures.
- [ ] Implement DOE, gradient/derivative-free, multiobjective, and adaptive-fidelity selection through OpenMDAO drivers.
- [ ] Run analytical benchmark loops and require energy closure, deterministic checkpoints, and identical warm-start results.
- [ ] Commit with `feat: add multidisciplinary convergence core`.

### Task 8: preCICE field coupling and restartable FSI/CHT

**Files:**
- Create: `packages/coupling/aeroworkbench_coupling/precice.py`
- Create: `solvers/precice/config_builder.py`
- Create: `examples/edf/coupling/precice-config.xml`
- Test: `tests/physics/test_precice_benchmark.py`

**Interfaces:**
- Consumes: typed mesh interfaces, pressure/traction/displacement/temperature/heat-flux fields, and coupling settings.
- Produces: validated preCICE configuration, mapping receipts, interface residuals, checkpoints, rollback events, and benchmark evidence.

- [ ] Write golden-file tests for nonmatching conservative/consistent mappings and implicit quasi-Newton settings.
- [ ] Implement participant adapters and checkpoint/rollback lifecycle.
- [ ] Containerize the supported preCICE environment with pinned versions and built digest capture.
- [ ] Run the canonical preCICE FSI benchmark at two meshes and verify interface conservation within declared tolerance.
- [ ] Measure process-group RSS locally; route the benchmark remotely if admission would exceed 896 MiB.
- [ ] Commit with `feat: add restartable field coupling`.

### Task 9: Electrical propulsion, battery, rotor dynamics, and resonance escalation

**Files:**
- Create: `packages/dynamics/aeroworkbench_dynamics/resonance.py`
- Create: `solvers/pybamm/adapter.py`
- Create: `solvers/ross/adapter.py`
- Create: `solvers/elmer/adapter.py`
- Create: `examples/edf/system.py`
- Test: `tests/physics/test_edf_electrical_dynamic_loop.py`

**Interfaces:**
- Consumes: motor/ESC/battery parameters, temperature, shaft state, blade/stator counts, modal results, and forcing spectra.
- Produces: three motor fidelity levels, ESC losses, calibrated cell/pack state, Campbell diagram, resonance margins, and escalation decisions.

- [ ] Write failing Kv/Kt, electrical/shaft/heat balance, 6S pack voltage, ROSS critical-speed, and resonance-trigger tests.
- [ ] Implement motor levels 1 and 2 plus the temperature-dependent ESC model.
- [ ] Implement PyBaMM ECM/SPMe/DFN selection, six independent series cells, calibration inputs, and validity storage.
- [ ] Implement ROSS shaft/bearing/rotor models and forcing sources including shaft, blade/stator passing, commutation, PWM sidebands, bearings, unbalance, and detected aero/acoustic peaks.
- [ ] Implement Elmer 2D rotating-machine preparation/parsing and feed torque ripple, losses, and Maxwell stress back into the coupled state.
- [ ] Prove the intentionally resonance-prone EDF escalates to harmonic/transient fidelity without labelling steady CFD as validation.
- [ ] Commit with `feat: couple EDF electrical and dynamic physics`.

### Task 10: OpenFOAM, Code_Aster, thermal, and validation benchmarks

**Files:**
- Create: `solvers/openfoam/adapter.py`
- Create: `solvers/code_aster/adapter.py`
- Create: `packages/thermal/aeroworkbench_thermal/network.py`
- Create: `benchmarks/manifest.json`
- Test: `tests/physics/test_native_benchmarks.py`

**Interfaces:**
- Consumes: geometry/mesh artifacts, semantic boundaries, material state, operating point, and solver policy.
- Produces: native flow, stress, modal, harmonic, transient, and thermal result envelopes with benchmark and independence evidence.

- [ ] Write preparation/parser golden tests for compressible/incompressible, MRF/AMI, CHT, external aero, static/prestressed modal/harmonic/transient structural cases.
- [ ] Implement physics-driven OpenFOAM application, turbulence, wall, rotating, time, and thermal selection with expert overrides.
- [ ] Implement Code_Aster centrifugal, aerodynamic, thermal, contact, modal, prestressed modal, harmonic, and transient cases.
- [ ] Run analytical conduction, beam, plate, modal, rotating-blade, duct-flow, external-aero, and CHT benchmarks.
- [ ] Run coarse/medium/fine mesh studies and transient timestep studies; prevent validation labels when sensitivity exceeds tolerance.
- [ ] Commit with `feat: add validated fluid structural thermal solvers`.

### Task 11: Complete the responsive engineering UI and typed API integration

**Files:**
- Modify: `apps/web/src/app/page.tsx`
- Modify: `apps/web/src/app/styles.css`
- Create: `apps/web/src/lib/api.ts`
- Create: `apps/web/src/components/*`
- Create: `tests/e2e/workbench.spec.ts`

**Interfaces:**
- Consumes: workbench state, job event stream, field/geometry assets, quality reports, warnings, variants, and provenance.
- Produces: accessible viewport-led workflows for design, execution, diagnosis, comparison, and export.

- [ ] Initialize Superdesign's six code-context files after the baseline frontend is committed, then reproduce the real screen on canvas.
- [ ] Use the approved Superdesign direction, UI quality rules, and React performance guidance to refine the implementation.
- [ ] Implement lazy 3D/VTK and Plotly islands, design tree, inspector, coupling/expert controls, timeline, Sankey energy view, Campbell/response plots, envelope maps, warnings, provenance, variants, comparison, undo/redo, search, import, export, saved layouts, and keyboard shortcuts.
- [ ] Cover loading, empty, partial, unavailable-solver, success, and error states with source/fidelity labels.
- [ ] Run unit tests, typecheck, production build, and browser E2E at 390, 820, and 1280 px with reduced motion and keyboard-only navigation.
- [ ] Measure project-owned UI/API process RSS below the 896 MiB aggregate ceiling.
- [ ] Commit with `feat: deliver engineering workbench interface`.

### Task 12: Whole-aircraft and operating-envelope workflow

**Files:**
- Create: `packages/envelope/aeroworkbench_envelope/engine.py`
- Create: `examples/aircraft/system.py`
- Create: `examples/aircraft/geometry.py`
- Test: `tests/physics/test_aircraft_demo.py`

**Interfaces:**
- Consumes: aircraft/EDF geometry, controls, atmosphere, attitude/rates, loads, propulsion state, and objective weights.
- Produces: installed-propulsion results, adaptive viable/constrained/failed envelope maps, structural response, and control-authority evidence.

- [ ] Write failing region-classification and adaptive-boundary-refinement tests.
- [ ] Generate wing, fuselage, tail, controls, inlet, EDF, nozzle, and external domain with semantic mappings.
- [ ] Couple internal EDF and complete external flow at high fidelity, including distortion, crossflow, ingestion, jet interaction, and asymmetric loading.
- [ ] Sweep airspeed, Mach, altitude, density, temperature, AoA, sideslip, body rates, load factor, controls, thrust, RPM, current, and SOC.
- [ ] Run the aircraft demonstrator and store actual solver/analytical evidence with clear fidelity.
- [ ] Commit with `feat: add installed EDF aircraft workflow`.

### Task 13: Gas-turbine, compressor, combustor, turbine, and thermoacoustics workflow

**Files:**
- Create: `solvers/pycycle/adapter.py`
- Create: `solvers/cantera/adapter.py`
- Create: `packages/turbomachinery/aeroworkbench_turbomachinery/*`
- Create: `examples/gas_turbine/system.py`
- Test: `tests/physics/test_gas_turbine_demo.py`

**Interfaces:**
- Consumes: inlet conditions, maps/geometry, fuel/chemistry, shaft state, materials, and fidelity policy.
- Produces: matched cycle state, compressor/turbine preliminary geometry, reacting state, thermal/structural evidence, shaft balance, and instability indicators.

- [ ] Write failing mass-flow, pressure/temperature continuity, compressor/turbine work, shaft-power, Cantera reactor, and Rayleigh-indicator tests.
- [ ] Implement pyCycle/OpenMDAO inlet-compressor-combustor-turbine-nozzle matching.
- [ ] Implement axial and radial preliminary compressor paths and turbine preliminary design with velocity triangles, loading, clearance, and stall/surge indicators.
- [ ] Implement Cantera 0D/network chemistry and OpenFOAM reacting-flow preparation/parsing.
- [ ] Implement pressure/heat-release spectra, acoustic-mode alignment, growth indicators, and transient escalation.
- [ ] Generate component CAD and run at least one actual compressor or turbine CFD case plus structural or thermal analysis.
- [ ] Commit with `feat: add coupled gas turbine workflow`.

### Task 14: GCP Batch, object storage, cost controls, and checkpoint/restart

**Files:**
- Modify: `infra/gcp/main.tf`
- Create: `infra/gcp/variables.tf`
- Create: `infra/gcp/outputs.tf`
- Create: `services/scheduler/gcp_batch.py`
- Test: `tests/integration/test_remote_policy.py`

**Interfaces:**
- Consumes: explicit remote switch, job resource request, checkpoint policy, and user cost ceilings.
- Produces: planned cost, rejected/accepted authorization receipt, Batch job ID, artifact/checkpoint URI, preemption event, and resume receipt.

- [ ] Write failing policy tests for disabled remote work and every vCPU/RAM/GPU/concurrency/wall-time/job/daily/project limit.
- [ ] Implement least-privilege service accounts, GCS artifact storage, Batch templates, logs, and budget/label controls.
- [ ] Run `terraform fmt`, `validate`, and `plan`; review that no public worker ingress or unbounded machine choice exists.
- [ ] Apply to the authenticated GCP project only after the plan's resource and cost bounds are recorded.
- [ ] Run a minimal checkpointable job, simulate/preempt it, and verify resume from the accepted checkpoint.
- [ ] Commit with `feat: add governed GCP execution`.

### Task 15: One-command operations, CI, containers, recovery, and security

**Files:**
- Create: `scripts/bootstrap.ps1`
- Create: `scripts/dev.ps1`
- Create: `scripts/demo.ps1`
- Create: `.github/workflows/ci.yml`
- Create: `infra/docker/*`
- Create: `SECURITY.md`
- Test: `tests/e2e/local-stack.test.ts`

**Interfaces:**
- Consumes: manifests, lockfiles, local capabilities, and runtime policy.
- Produces: repeatable bootstrap/start/demo commands, pinned image digests, CI receipts, recovery history, and security guidance.

- [ ] Make bootstrap check/install safe dependencies, initialize SQLite/object storage, build pinned images, and run capability checks.
- [ ] Make development start launch web, API, scheduler, worker, and MCP under one supervisor with ordered shutdown.
- [ ] Add EDF, aircraft, gas-turbine, and benchmark demo selectors.
- [ ] Add formatting, type, unit, integration, lightweight physics, MCP, frontend, dependency, secret, and container/IaC checks to CI; isolate heavyweight solver validation.
- [ ] Build every declared container and record image digests; an unbuilt Dockerfile cannot satisfy its requirement.
- [ ] Exercise bounded remediation for bad mesh, CFD divergence, FSI instability, and cloud interruption while preserving every failed-attempt receipt.
- [ ] Commit with `build: add reproducible operations and CI`.

### Task 16: End-to-end demonstrations, deployment, documentation, and formal completion audit

**Files:**
- Create: `docs/{installation,user-guide,solver-guide,coupling,cloud,mcp,cad,freecad,edf,aircraft,compressor,turbine,combustor,debugging,convergence,provenance,cache,security}.md`
- Modify: `README.md`
- Modify: `docs/requirements-audit.json`
- Test: `tests/e2e/{edf,aircraft,gas-turbine}.spec.ts`

**Interfaces:**
- Consumes: all prior task artifacts and evidence receipts.
- Produces: live workbench URL, local commands, public documentation, benchmark summary, deployment receipt, clean tagged repository, and zero-incomplete audit.

- [ ] Run the complete EDF demo, including geometry, mesh, rotating CFD, loads, thermal/electrical feedback, six-cell battery, prestressed modes, ROSS, forcing spectrum, resonance warning, automatic transient escalation, visualization, cache reuse, variants, provenance, and MCP inspection.
- [ ] Run the complete installed-aircraft demo and complete gas-turbine demo with their required actual solver evidence.
- [ ] Run unit, integration, physics, MCP, frontend, browser, container, infrastructure, and E2E suites under the RSS supervisor.
- [ ] Deploy frontend, API, storage, and functioning worker path; verify browser-to-API-to-artifact flow on the public URL.
- [ ] Write the complete documentation set and link exact versions, commands, capability expectations, and troubleshooting.
- [ ] Run `pnpm audit:requirements`; for every non-PASS item, return to its owning task and repeat verification.
- [ ] Require a clean worktree, pushed public main branch, deployment receipt, and immutable milestone tag.
- [ ] Commit with `release: validate complete multiphysics workbench` and push the release tag.

## Execution policy

Tasks 2-5 establish contracts and safety gates. Tasks 6-10 can then run in parallel in
isolated worktrees. Tasks 11-13 consume those contracts and can overlap after API schemas
stabilize. Task 14 may proceed beside local workflows after compute policy is frozen.
Tasks 15-16 integrate serially. Each task gets a Luna implementer, a spec-conformance
review, a quality/security/numerical review appropriate to its risk, and root integration.
