# Physical 3D file inventory — where the "3D files" workstream actually is

Measured 2026-11-14 on `E:\engineering-portfolio-audit\repos\*`. This is the raw inventory the
"speed up and prioritise the physical 3D files" request has to be aimed at. Two specialist agents
are working the *pipelines*; this is the *inventory* they and the prioritisation depend on.

## Totals by repo

| repo | 3D files | size | composition |
|---|---:|---:|---|
| **drone-mech** | **247** | **1310.1 MB** | 191 `.step`, 31 `.msh`, 14 `.brep`, 6 `.stl`, 4 `.FCStd` |
| research-paper | 51 | 510.6 MB | 36 `.stl`, 15 `.stp` |
| copperline | 120 | 20.1 MB | 120 `.obj` |
| aero-multiphysics-workbench | 49 | 14.2 MB | 14 `.step`, 12 `.brep`, 10 `.msh`, 8 `.stl`, 4 `.stp` |
| drone-arm | 3 | 2.1 MB | 2 `.step`, 1 `.glb` |
| Code-SDR | 1 | 0.8 MB | 1 `.stp` |

**Combined: 471 files, ~1.86 GB.** drone-mech is 70% of the bytes and 52% of the files.

## What this ordering implies

1. **drone-mech is the 3D bottleneck, by an order of magnitude.** 191 STEP files is not a few
   artefacts — it is a generated corpus. Whatever produces them is the thing to speed up, and if
   they are regenerated per run then caching or export-avoidance is the entire optimisation.

2. **102 files (drone-mech STEP+brep) at 1.3 GB means individual files are ~6–7 MB each.** That is
   a CAD interchange size, not a mesh size. So the cost is almost certainly **boolean/export
   operations and disk I/O**, not solver time. The dm-3d-speed agent is timing exactly this.

3. **research-paper's 510 MB of STL/STP is a surprise worth flagging.** A voxel-generative paper
   carrying 36 STL and 15 STP files suggests either a geometry corpus or exported samples. Nobody
   has audited what those are or whether they correspond to any claimed result. That is an
   unexamined deliverable, and it is 27% of all 3D bytes.

4. **copperline's 120 `.obj` files are probably test fixtures, not deliverables.** 120 files for
   20 MB means ~170 KB each — consistent with small generated boards for the router's corpus tests.
   Low priority, but worth confirming they are fixtures so nobody mistakes them for product.

5. **drone-arm and Code-SDR have essentially no 3D assets** (4 files, 2.9 MB total). Their
   "physical" deliverable is the PCB, not a CAD model. So for those two boards the 3D priority is
   **the PCB stackup and enclosure clearance**, not mesh generation.

## Prioritisation I would apply

| rank | target | why |
|---|---|---|
| 1 | **drone-mech STEP/brep generation** | 1.31 GB, 205 files, and it feeds the DM-G1 interference check that currently FAILS |
| 2 | **Code-SDR + drone-arm PCB 3D (stackup + STEP export for mechanical fit)** | the boards are the deliverable; a STEP export is what the enclosure is built from, and neither board has one verified |
| 3 | research-paper STL/STP corpus | 510 MB unaudited; needs an identity check before anyone cites it |
| 4 | aero STEP/brep | 14 MB, already has a timing agent on it |
| 5 | copperline .obj | almost certainly fixtures; confirm and move on |

## The question that decides whether "speed up" is even well-posed

Before optimising, someone has to answer: **are these 3D files generated, or checked in?**

- If **generated per run**, the win is caching plus avoiding re-export, and the number to report is
  seconds-per-artefact.
- If **checked in**, then "sped up" cannot mean generation — it means the *validation* pass over
  them (interference, watertightness, tessellation), and the number to report is seconds-per-file
  validated, plus how much of that can be parallelised across 16 cores.

That distinction is not yet established for drone-mech, and it determines whether the deliverable is
a cache or a parallel sweep. Both dm-3d-speed and aero-3d-speed were asked to time real runs; their
timings will settle it.

## Limit of this inventory

Extension-based counting. Files renamed without a matching extension, or geometry stored inside
`.FCStd` archives (4 of them in drone-mech), are not decomposed here. No file was opened or
validated for watertightness — this says where the bytes are, not whether the geometry is correct.