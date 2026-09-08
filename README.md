# Aero Multiphysics Workbench

A local-first engineering environment for exploring a single physical design state through coupled aerodynamic, structural, thermal, electrical, rotor-dynamic, and propulsion models.

The project is under active construction. Numerical results are required to identify their source and fidelity; unavailable native solvers must fail closed instead of returning invented data.

## Resource contract

Local development and validation are designed to stay below **1 GB resident memory (RSS)** in aggregate. Heavy native solvers are capability-detected and run explicitly, one at a time, or on user-enabled remote workers.

## License

Apache-2.0. See [LICENSE](LICENSE).

