# Aero Multiphysics Workbench Design

## Product definition

The product is a local-first engineering workbench in which one versioned physical
design state is evaluated by coupled aerodynamic, structural, thermal, electrical,
electromagnetic, rotor-dynamic, battery, combustion, and cycle models. It is not a
collection of independent solver launchers. A run is complete only when its selected
physics participants and the global physical closure checks converge.

The first complete workflows are a roughly 70 mm EDF, an installed-EDF fast aerobatic
aircraft, and a compressor-combustor-turbine engine. Every displayed number identifies
whether it came from an analytical model, a surrogate, a benchmark, or an actual native
solver execution.

## Non-negotiable constraints

- The public source repository is `iamdarshg/aero-multiphysics-workbench` under Apache-2.0.
- Local project-owned processes remain below 1 GiB aggregate RSS. The enforced ceiling
  is 896 MiB so the process group retains at least 128 MiB of headroom.
- Remote compute is disabled by default, enabled only by the user's switch, and bounded
  by immutable vCPU, RAM, GPU, concurrency, wall-time, per-job, daily, and project costs.
- Missing native solvers fail closed. Analytical or surrogate output is never relabelled
  as native-solver evidence.
- Native solver commands are constructed from allowlisted manifests; callers cannot
  pass shell text or arbitrary executables.
- All dimensional values carry units at API and persistence boundaries.
- Chrome or the built-in browser is used for browser verification.

## Architecture

The system is a monorepo with a Next.js web application, a FastAPI control API, a lean
local scheduler/worker, an actual Model Context Protocol server, typed TypeScript and
Pydantic contracts, Python physics orchestration, solver adapters, examples, benchmarks,
and Terraform/container infrastructure.

The canonical flow is:

```text
Design mutation
  -> validated immutable design revision
  -> deterministic content-addressed DAG
  -> OpenMDAO scalar nonlinear coordination
  -> preCICE field coupling where spatial exchange is required
  -> allowlisted solver workers
  -> parsed result envelopes and field assets
  -> global physical convergence and quality gates
  -> provenance-backed UI and MCP views
```

OpenMDAO owns scalar multidisciplinary variables, design variables, constraints,
optimization, DOE, and cyclic nonlinear solves. preCICE owns spatial mapping,
nonmatching interfaces, implicit coupling subiterations, checkpoints, rollback, and
quasi-Newton acceleration. The workbench owns design state, scheduling, convergence,
fidelity planning, caching, provenance, quality scoring, permissions, and presentation.

## Domain contracts

`DesignRevision` is immutable and references geometry, semantic assignments, material
revisions, operating points, objective weights, constraints, solver settings, coupling
settings, and compute policy. Variants form a parent-child graph and store only validated
changes plus their resulting content hash.

`ResultEnvelope<T>` contains `source`, `fidelity`, `units`, `validity`, `input_hash`,
`solver_identity`, `run_id`, `provenance_id`, `warnings`, and typed `value`. A native
envelope requires a successful capability probe, accepted process exit, parser receipt,
and artifact hashes.

`ParticipantManifest` declares inputs, outputs, units, mesh/interface roles, coupling
direction, convergence measures, executable capability, allowlisted argument builder,
checkpoint behavior, parser, and benchmark evidence.

`QualityReport` exposes explicit numerical indicators for convergence, mass and energy
closure, force consistency, mesh independence, timestep independence, resonance margin,
model fidelity, validation status, and solver warnings. It contains no opaque AI
confidence score.

## Physics orchestration

Coupling strength from 0.0 to 1.0 is expanded into visible expert settings: interface
tolerances, iteration caps, geometry feedback interval, exchange frequency, thermal and
electrical feedback rates, time resolution, nonlinear tolerance, preCICE acceleration,
dynamic model activation, electromagnetic escalation, and mesh update threshold. The
serious-analysis default is 0.90; explicit expert overrides remain visible and persisted.

The convergence manager evaluates solver residuals and changes in mass, energy, force,
torque, geometry, clearance, temperature, resistance, voltage, current, modes, critical
speeds, forcing spectra, and resonance separation. A run cannot pass because each solver
reported convergence while the coupled physical state remains inconsistent.

The fidelity planner selects the cheapest model that can answer the current question and
escalates on maturity, tight constraint margins, solver disagreement, sensitivity, mesh
or timestep dependence, and resonance proximity. Resonance escalation is part of the
solve loop: analytical/MRF results can trigger transient sampling, harmonic response,
AMI, transient FSI, or detailed electromagnetic analysis.

## Geometry and data

OpenCascade-compatible BREP/STEP is the canonical shape family. CadQuery produces
parametric geometry; FreeCAD supports FCStd import, headless conversion, STEP/BREP
roundtrips, and named-geometry reconciliation. Semantic entities identify fluid/solid
domains, boundaries, frames, motion, shafts, bearings, materials, electrical regions,
thermal interfaces, FSI interfaces, and controls independently of raw topology.

Gmsh and snappyHexMesh generate structural and fluid meshes. Mesh receipts include
quality measures, boundary-layer intent, interface maps, topology fingerprints, and
parent geometry hashes. Small parameter changes attempt mesh morphing only when quality
and semantic correspondence gates pass; otherwise affected regions remesh.

SQLite stores local metadata behind repository interfaces. Large fields use VTK,
HDF5/Zarr, Parquet, glTF, STEP, or BREP in content-addressed object storage. Cache hits
require matching normalized inputs, solver/container identity, upstream hashes,
semantics, and validity rules.

## Solver and benchmark boundaries

The initial manifests cover OpenFOAM, Code_Aster, preCICE, ROSS, PyBaMM, Elmer,
Cantera, pyCycle, CadQuery, Gmsh, OpenVSP, and FreeCAD. Each adapter has four independent
tests: capability detection, preparation/golden-file validation, parser validation, and
a canonical physics benchmark. A successful exit code alone is insufficient.

Docker images pin tool versions and record built digests. Lightweight Python solvers may
run from the repository virtual environment when their measured process group fits the
local budget. OpenFOAM, Code_Aster, preCICE, Elmer, and other large native workloads run
one at a time locally or on explicitly enabled remote workers.

## User interface

The main screen is an engineering viewport with a searchable design tree, contextual
parameter inspector, run/coupling controls, convergence timeline, explainable warnings,
quality evidence, variants, provenance, and comparison tools. Heavy 3D and plotting code
loads on demand in client-only islands. The interface supports keyboard navigation,
visible focus, reduced motion, 390/820/1280 px layouts, complete loading/empty/partial/
error states, and no generic admin-dashboard visual language.

Warnings link to the physical reason, evidence and values, affected geometry, and the
recommended simulation action. Units, result source, fidelity, validity, and solver
availability stay visible at the point of decision.

## MCP and AI supervision

The engineering MCP server uses the official SDK over stdio and exposes typed, bounded
tools for inspecting designs, capabilities, provenance, convergence, and results;
creating variants; scheduling allowed analyses; cancelling owned jobs; and requesting
explicitly authorized remote work. It never exposes arbitrary filesystem or shell access.
Destructive mutation, remote compute, and cost-bearing operations have separate gates.

## Deployment and recovery

One top-level command starts the UI, API, scheduler, local worker, and MCP within the
resource supervisor. One command each runs EDF, aircraft, gas-turbine, and benchmark
workflows. The web and control API can deploy remotely while heavy workers remain local
or use GCP Batch. Spot jobs checkpoint solver state and artifacts, persist a restart
receipt, and resume from the last accepted checkpoint.

Automated remediation records every attempt and can adjust only bounded, declared solver
settings. It cannot weaken user constraints, quality gates, permissions, or cost limits.

## Validation and completion

Unit, contract, integration, physics, MCP, frontend, browser, container, infrastructure,
and end-to-end tests are separate tiers. The final audit maps every numbered source
requirement and all 44 stopping conditions to evidence. `PASS` requires a linked test,
artifact, deployment receipt, or actual solver run; otherwise the status remains
`PARTIAL`, `FAIL`, or `BLOCKED` and the work continues.
