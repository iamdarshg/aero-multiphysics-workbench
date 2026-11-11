# DECISIONS

Format: `YYYY-MM-DDTHH:MMZ | member | decision | rationale | reversibility`

## 2026-11-11T22:50Z | dsh-lead | Clone to `E:\engineering-portfolio-audit\repos`

User directed clones onto E:. Disk E: had 37 GB free; the six repos total ~1.9 GB
of git object store and ~5.6 GB checked out (drone-mech alone is 3.7 GB because the
info-dump branch commits solver logs and 3D artifacts). Reversible: delete the tree.

## 2026-11-11T22:52Z | dsh-lead | Set `git config --global core.longpaths true`

`drone-mech` contains tracked paths longer than 260 characters; the first clone
completed its object transfer but failed checkout. This is a git global config, not a
repo change. Reversible: `git config --global --unset core.longpaths`.

## 2026-11-11T22:58Z | dsh-lead | Work from `origin/info-dump/2026-11-10-handoff`

`main` does not contain the state the handoff describes (Code-SDR DRC on `main` is
391; on the info-dump branch it is 222, matching the handoff). Only the info-dump
branch is a valid base for gate work. Local branch named `work/2026-11-11`.
Reversible: `git checkout main`.

## 2026-11-11T23:00Z | dsh-lead | Validate ERC/DRC on the root sheet, not sub-sheets

`hardware/main/rev_b/rf_915.kicad_sch` is a hierarchical sub-sheet. Running ERC on it
standalone yields 37 violations, 36 of which are hierarchy artifacts
(`Hierarchical label ... cannot be connected to non-existent parent sheet`,
plus library-path and footprint-link warnings that resolve only from the parent
directory). The correct DA-G1 invocation is on `main_rev_b.kicad_sch`, which yields
1 warning. Recorded so no later agent reports "37 ERC errors" as a real defect.

## 2026-11-11T23:12Z | dsh-lead | mypy/pytest baselines for aero are NOT quotable as written

`python -m mypy .` aborts with "Source file found twice under different module names"
before type checking, and `python -m pytest -q` fails 16 collections with
`ModuleNotFoundError: No module named 'examples.gas_turbine'`. The handoff's
"mypy 0/505" and "1793/1794" cannot be reproduced from a clean clone without an
install step and a fixed invocation. Per handoff §12 this must be re-derived before
either number is quoted again.

## 2026-11-11T23:25Z | dsh-lead | Fable orchestrator is authoritative

User instruction (2026-11-11): "whatever fable does takes priority ... just open
github issues and prs asking about fixes if you disagree dont overwrite anythign
fable is your god". Therefore dsh-lead will:
- never edit a repo file that Fable has claimed or changed;
- express dissent only as a GitHub issue or a PR left unmerged for Fable to review;
- prefer evidence-only work (reproduce, measure, report) over source edits.
Reversible: user can lift the directive.