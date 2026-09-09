# Solver integration contract

| ID | Version probe | Acceptable result kinds |
| --- | --- | --- |
| OpenFOAM | `foamVersion` | fields, scalars |
| Code_Aster | `as_run --version` | fields, scalars |
| preCICE | `precice-config-visualizer --version` | coupling, report |
| ROSS | `ross --version` | scalars, report |
| PyBaMM | `pybamm --version` | scalars, report |
| Elmer | `ElmerSolver --version` | fields, scalars |
| Cantera | `cantera --version` | scalars, report |
| pyCycle | `pycycle --version` | scalars, report |
| CadQuery | `cadquery --version` | geometry |
| Gmsh | `gmsh --version` | mesh, geometry |
| OpenVSP | `vsp --version` | geometry, mesh |
| FreeCAD | `FreeCADCmd --version` | geometry, mesh |

The authoritative list is `packages/solver-contracts/src/manifests.ts`; this table is an operator reference. Each integration has `native-only` trust semantics. A successful version probe establishes neither a usable solver case nor valid results.

Workers must implement `LaunchRequest` through the manifest-specific typed command builder and return `RunRecord` through `SolverGateway`. They cannot launch if the corresponding capability is unavailable. Solver probes are bound to the immutable registry's executable/version probe; no caller-supplied command or arbitrary `string[]` reaches the runner. Checkpoints are explicit lineage references, never automatic recovery claims. Native result publication is disabled until a completed run receipt, approved artifact root, parser receipt, exact 64-hex SHA-256, solver version, and input/checkpoint lineage are all verified.
