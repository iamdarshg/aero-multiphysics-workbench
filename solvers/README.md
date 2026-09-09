# Native solver adapters

The typed registry in `packages/solver-contracts/src/manifests.ts` is the authoritative integration contract for OpenFOAM, Code_Aster, preCICE, ROSS, PyBaMM, Elmer, Cantera, pyCycle, CadQuery, Gmsh, OpenVSP, and FreeCAD.

Adapters are intentionally not bundled with solver binaries. `scripts/platform/capabilities.mjs` runs only each fixed version probe, without a shell. A missing probe yields `unavailable`; it never runs a fallback calculation or fabricates results. Native execution must additionally be admitted by the local scheduler and record a provenance event through `SolverGateway`.

Checkpoint paths are input metadata to `LaunchRequest`. A worker implementation must prove its own checkpoint file exists before native process launch and must label all emitted values `source: native-solver`.
