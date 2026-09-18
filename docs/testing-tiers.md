# Testing tiers and runtime budgets

Issue #30 makes the default developer/agent edit loop fast, bounded, and
deterministic while keeping native, scientific, and release validation
available as explicit tiers. No acceptance criterion, provenance guarantee, or
solver path is weakened by tiering: the tiers differ only in **which** suites
run and **how long** they are allowed to run.

## Tiers

| Command | Purpose | Budget | Network / solvers |
| --- | --- | --- | --- |
| `pnpm test:fast` | Unit/contracts + tiny pure-Python tests | <= 120 s | No network; native solver execution excluded |
| `pnpm test:focused` | Changed-path selection, bounded | <= 300 s | Depends on selection; no network |
| `pnpm test:integration` | Local API/job/MCP/stack integration | <= 300 s | Local only; no cloud |
| `pnpm test:native-smoke` | Tiny installed-solver proofs | <= 300 s | Opt-in; requires provisioned solvers |
| `pnpm test:science` | Mesh/time-independence and coupled heavy benchmarks | <= 900 s | Explicit; solver-equipped hosts only |
| `pnpm test:all` | CI/release aggregation | <= 1200 s | Full; not the default edit loop |

The runner is `scripts/test/tier.mjs`. It can also be invoked directly, which is
useful for ad-hoc budgets:

```powershell
node scripts/test/tier.mjs fast
node scripts/test/tier.mjs focused --paths services/api/pyproject.toml
node scripts/test/tier.mjs list
```

### Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Tier passed |
| `1` | A test failed |
| `2` | Usage error (unknown tier/flag) |
| `3` | A step or the whole tier exceeded its hard budget / watchdog |

### Budgets are hard

Each step has its own timeout and the tier has an overall budget. When either is
exhausted the runner kills the whole child process tree (Windows
`taskkill /T /F`, POSIX process group `SIGKILL`) and exits `3`, so a hung test
fails fast instead of stalling an agent.

Every Python step in the integration, native-smoke, science, and all tiers also
loads the per-test watchdog `scripts/test/pytest_hang_guard.py` via
`pytest -p pytest_hang_guard`, armed by `AERO_TEST_TIMEOUT_SECONDS`. A single
hung test
dumps its live traceback and exits `3`. Node suites use the runner's own
`--test-timeout`.

## Fast tier contents

The fast tier is a real, passing subset scoped to contracts and pure logic:

- JS contracts: `tests/unit/*.test.ts` except the process-spawning
  `stack-live` case and the byte-pinned release `requirements-audit` contract
  (which pins `package.json`/evidence hashes and belongs to the `all` tier and
  CI, not the per-edit loop).
- Platform contracts: `tests/platform/platform.test.ts`,
  `participants.test.ts`, `doctor.test.ts`.
- Web: `pnpm --filter @aero/web test`.
- Workspace manifest smoke: `tests/smoke/workspace.test.mjs`.
- This issue's own tests: `tests/fast/**`.
- Python: `tests/core`, `tests/integration`, and the pure-physics files
  (`aircraft`, `gas turbine`, `scalar coupling`, `result inspection`, `EDF
  electrical loop`, `geometry/semantics/mesh planning`, `precice mapping`,
  native case builders, participant lifecycle).

Python steps run `uv run --no-sync ... pytest -c pyproject.toml <paths>`.
`--no-sync` means **no implicit network access**; if the venv is missing the
step fails closed. Set `AERO_TEST_ALLOW_SYNC=1` to permit `uv sync` when you
deliberately want to provision dependencies.

## Changed-area helper

`node scripts/test/tier.mjs focused` reads `git diff`/untracked paths and runs
only the owning steps. You can also pass paths explicitly with `--paths`.

| Changed path | Selected tier steps |
| --- | --- |
| `apps/web/**` | `js-web` |
| `tests/unit/**`, `packages/**` (TS), `scripts/platform/**` | `js-unit-fast` or `js-platform-fast` |
| `scripts/audit-requirements*`, `docs/requirements-audit.json`, `tests/unit/requirements-audit.test.ts` | `js-audit` |
| `tests/platform/**`, `packages/solver-contracts/**` | `js-platform-fast` |
| `tests/smoke/**`, `tests/fast/**` | `js-smoke`, `js-fast-tests` |
| `tests/core/**` | `py-core` |
| `tests/integration/**` | `py-integration` |
| `tests/physics/**` (pure) | `py-fast-physics` |
| `tests/physics/test_native_execution.py` | `py-native-execution`, `py-native-smoke` |
| `tests/physics/test_governed_product_jobs.py` | `py-integration-native` |
| `tests/physics/test_edf_80mm_three_stage.py` | `py-science-edf` |
| `tests/physics/test_generic_multiphysics_substrate.py` | `py-science-substrate` |
| `tests/physics/test_milestone3_orchestration.py` | `py-science-milestone3` |
| `services/api/**` | `py-core`, `py-integration`, `py-fast-physics` |
| anything else (e.g. docs) | none -> falls back to `fast` |

## Duration visibility

- The runner prints a total and the slowest steps per tier.
- Python steps pass `--durations=15` so pytest logs the slowest tests.
- Node suites report per-test durations natively.
- `--json` appends a machine-readable `TIER_SUMMARY {...}` line for CI log
  parsing and trend tracking.

## CI sharding (recommended wiring)

The `platform.yml` workflow is owned by another workstream; this issue provides
the commands and expectations so that workstream can adopt them without
duplicating builds:

- Keep the existing independent jobs; they already shard by concern
  (JS unit, platform/MCP, Python, build, native opt-in).
- Run `pnpm test:fast` as the PR default and reserve `pnpm test:integration`,
  `pnpm test:native-smoke`, and `pnpm test:science` for labeled/manual jobs.
- Native benchmarks remain opt-in and never faked; the
  `native-solver-benchmarks` job keeps its manual/label gate.
- Cache only the pnpm store and uv package downloads across jobs. Never cache
  generated artifacts, SQLite state, solver output, provenance ledgers, or
  `.next` output.
- Build the web UI once and hand the `.next` directory to E2E/container jobs as
  an artifact instead of rebuilding per job where handoff is safe.

## Measured runtimes

Measured locally on Windows 11, Node 24, Python 3.12 (issue #30 validation):

| Tier | Result | Wall time | Budget |
| --- | --- | --- | --- |
| `fast` | PASS (202 checks) | ~20-24 s | 120 s |
| `focused --paths services/api/pyproject.toml` | PASS | ~12 s | 300 s |
| `native-smoke` | PASS | ~38 s | 300 s |
| `integration` | PASS | ~157 s | 300 s |
| `science` | see note | ~138 s | 900 s |

The fast tier is comfortably inside its two-minute target. The slowest fast
steps are the pure-physics selection (~6 s) and `tests/core` (~4 s).

**Science note:** at validation time `tests/physics/test_milestone3_orchestration.py::test_dag_change_impact_matches_design_contract`
fails because `packages/schema/src/design.ts` was mid-edit by a concurrent
workstream while the Python `CHANGE_IMPACT` registry did not yet carry the new
keys (`geometryBindings`, `geometryRebuildPolicy`, `topologyDigest`). That is a
cross-package contract in flight, not a tiering defect; `py-science-edf` and
`py-science-substrate` both pass. Re-run `pnpm test:science` after the schema
workstream lands.

The full `pnpm test` gate and `.github/workflows/platform.yml` are unchanged;
tiering adds bounded entry points and never removes an existing check.

