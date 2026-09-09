# Architecture contract

The workbench represents one versioned physical design state. Geometry, semantics,
materials, operating points, solver configuration, coupling configuration, and
compute policy are inputs to a deterministic computation graph rather than separate
application silos.

## Control plane

1. The typed API validates a design mutation and writes an immutable provenance event.
2. The computation graph hashes the normalized inputs and resolves safe cache hits.
3. OpenMDAO owns scalar multidisciplinary variables and nonlinear coordination.
4. preCICE owns spatial field exchange, checkpoints, rollback, and interface convergence.
5. Solver adapters prepare only allowlisted executables and parse outputs into typed,
   unit-bearing result envelopes.
6. The convergence manager evaluates solver residuals together with mass, energy,
   force, geometry, thermal, electrical, and dynamic closure.
7. The fidelity planner escalates models when constraint margins, disagreement, mesh
   sensitivity, or resonance proximity make a lower-fidelity result insufficient.

```text
Design state -> content DAG -> scalar coordinator -> field coordinator
     ^               |                |                    |
     |               v                v                    v
 provenance <- result envelopes <- solver gateway <- isolated workers
     |                                                    |
     +---------- UI / MCP inspection and control ---------+
```

## Result trust contract

Every numerical result must include its source (`analytical`, `surrogate`,
`benchmark`, or `native_solver`), fidelity, units, validity range, input hash,
software identity, and provenance identifier. A native result is publishable only
after an accepted native run. Missing executables, incomplete runs, parser failures,
and failed quality gates produce explicit unavailable or failed states; they never
fall back to invented values.

## Local resource contract

Project-owned processes have a hard aggregate ceiling of 896 MiB RSS, leaving at
least 128 MiB of headroom below the user's 1 GiB limit. Admission control reserves
memory before launch, and the process supervisor samples the complete child process
tree while a job runs. The supervisor terminates the job fail-closed before the hard
ceiling is crossed. Native solver jobs run one at a time locally; large jobs require
the user's explicit remote-compute switch and cost ceiling.

Suggested steady-state envelopes are 192 MiB for the web UI, 160 MiB for the API,
96 MiB for the scheduler, 96 MiB for MCP, and at most 352 MiB for one active local
worker. These are admission budgets, not claims of measured consumption.

## Security and compute boundaries

- Solver identity maps to a fixed executable and argument builder; callers cannot
  submit an arbitrary shell command.
- Local paths are resolved beneath per-job work directories.
- MCP mutation, destructive actions, remote compute, and cost-bearing work have
  independent capability gates.
- Remote compute is disabled by default and cannot be enabled by an AI tool call.
- Large field artifacts live in content-addressed object storage; metadata and
  provenance remain queryable through the durable repository abstraction.
- Secrets are supplied at runtime and never stored in source, results, or provenance.

## User experience contract

The three-dimensional engineering viewport is the primary workspace. The surrounding
design tree, parameter inspector, convergence timeline, warnings, provenance, and
result comparison views are projections of the same state. Warnings explain the
physical reason, supporting values, affected component, and recommended next analysis.
Loading, empty, partial, error, and unavailable-solver states are first-class and must
not masquerade as completed analysis.

## Extension contract

A physics participant declares typed inputs and outputs, units, mesh/interface roles,
coupling direction, convergence measures, executable capability, launch policy,
checkpoint behavior, parser, and benchmark evidence. New participants can therefore
join the scalar and/or field coupling graph without bypassing provenance, resource,
security, or validation gates.
