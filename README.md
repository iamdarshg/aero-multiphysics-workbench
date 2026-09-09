# Aero Multiphysics Workbench

A local-first engineering environment for exploring a single physical design state through coupled aerodynamic, structural, thermal, electrical, rotor-dynamic, and propulsion models.

The project is under active construction. Numerical results are required to identify their source and fidelity; unavailable native solvers must fail closed instead of returning invented data.

## Resource contract

Local development and validation enforce an **896 MiB aggregate process-tree RSS budget**, leaving headroom below the one-gigabyte host contract. Heavy native solvers are capability-detected and run explicitly, one at a time, or on user-enabled remote workers.

## License

Apache-2.0. See [LICENSE](LICENSE).

