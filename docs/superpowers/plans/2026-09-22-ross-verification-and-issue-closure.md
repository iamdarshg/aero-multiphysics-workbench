# ROSS Verification and Issue 30–96 Closure Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce fail-closed current-HEAD ROSS evidence, repair any verification-harness defect it exposes, and close only issues 30–96 whose original acceptance criteria are supported by current code, tests, and native receipts.

**Architecture:** Keep the native participant unchanged unless a regression proves it wrong. Strengthen `scripts/gcp/bench_ross.py` so process success and scientific acceptance are separate gates, preserve a bounded native receipt, then audit open issues against their own definitions of done and current-head evidence.

**Tech Stack:** Python 3.12, pytest, `ross-rotordynamics` 2.3.0, uv, pnpm, GitHub issues.

**Spec:** GitHub issues #30–#96, especially #38 and #59.

## Global Constraints

- Native capability must fail closed; no fabricated or analytically substituted result.
- Keep project-owned local process RSS below 1 GB.
- Use local deterministic verification; GCP spend is US$0.00 unless separately authorized.
- Do not close an issue from commit messages or exit code alone.

## Review Focus

- A zero-exit ROSS run whose forced-response sweep never reaches resonance must fail verification.
- Direct-library success must not mask a failed governed participant run.
- Modal and Campbell first-critical results must agree within a declared tolerance.
- Soft bearings must lower the first critical speed and a short/stiff shaft must raise it.
- Issue closure must follow original acceptance criteria, including unavailable native evidence.

---

### Task 1: Make the ROSS verifier fail closed

**Files:**
- Modify: `scripts/gcp/bench_ross.py`
- Modify: `tests/physics/test_ross_forced_api.py`

**Interfaces:**
- Consumes: governed `run_ross.py` JSON receipts.
- Produces: an `issue38_ross.json` receipt with `verificationPassed`, named checks, and a nonzero process exit when required checks fail.

- [ ] **Step 1: Add failing verifier tests**

Add deterministic tests which stub only the slow native case runner and assert that the real verifier rejects a forced peak far from the Campbell critical and targets the governed forced sweep at the detected critical.

- [ ] **Step 2: Run the focused tests and observe the expected failures**

Run: `uv run --directory services/api pytest -q ../../tests/physics/test_ross_forced_api.py`

- [ ] **Step 3: Implement the minimum fail-closed verifier change**

Run the governed forced case at the Campbell-detected first critical, evaluate explicit reference/trend/agreement checks, and prevent direct-library execution from promoting a failed governed result.

- [ ] **Step 4: Re-run the focused tests**

Run: `uv run --directory services/api pytest -q ../../tests/physics/test_ross_forced_api.py`

### Task 2: Generate current-head native ROSS evidence

**Files:**
- Create: `docs/evidence/solver-correction/final-verification-20260922/ross-current.json`
- Modify: `docs/evidence/solver-correction/final-verification-20260922/SUMMARY.md`

**Interfaces:**
- Consumes: corrected verifier and locked service environment.
- Produces: immutable human- and machine-readable evidence tied to the verified commit.

- [ ] **Step 1: Run the bounded native benchmark**

Run `scripts/gcp/bench_ross.py` with `REPO_ROOT`, `PY`, `ROSS_WORK`, and `RECEIPTS` set to explicit local paths.

- [ ] **Step 2: Run focused governed lifecycle tests**

Run the ROSS forced API, GEN10 rotordynamics, participant lifecycle ROSS subset, and EDF ROSS tests.

- [ ] **Step 3: Record exact results without suppressing warnings or limitations**

Copy the fresh receipt into the final-verification evidence directory and update the summary with commit, solver version, case results, checks, duration, and US$0.00 spend.

### Task 3: Audit and clean issue state from #30 through #96

**Files:**
- Modify only evidence/docs/tests/code required by a reproduced blocker.

**Interfaces:**
- Consumes: issue bodies, current source, focused tests, current-head receipts.
- Produces: issue comments and closure mutations only where every required acceptance item is supported.

- [ ] **Step 1: Run repository verification gates**

Run `pnpm test:fast` and the focused AIRFRAME/VEHICLE-SYSTEMS/recursive-platform tests named by open issues #74, #75, #78, #81–#85, #94, and #96.

- [ ] **Step 2: Build the closure matrix**

For each still-open issue in #30–#96, map original acceptance criteria to exact implementation paths, tests, and native receipts; mark unsupported items explicitly.

- [ ] **Step 3: Apply only reproduced, bounded cleanups**

For every code defect, first add and observe a failing regression, then implement one root-cause fix and rerun the owning suite.

- [ ] **Step 4: Close only satisfied issues**

Post current-head evidence and close verified issues. Leave epics or verifier issues open when a required native/integration proof remains unavailable, with a precise blocker comment.

### Task 4: Final verification and delivery

**Files:**
- All changed files from Tasks 1–3.

**Interfaces:**
- Consumes: completed changes and issue matrix.
- Produces: pushed commits and an exact report of closed versus blocked issues.

- [ ] **Step 1: Run fresh final commands**

Re-run the corrected native ROSS benchmark, focused ROSS tests, Python lint for changed files, and relevant repository gates.

- [ ] **Step 2: Review diff and commit in small units**

Use one commit for the verifier/test repair and one for evidence/issue-state cleanup when both are needed.

- [ ] **Step 3: Push and report exact evidence**

Push to the authorized branch and report commit SHAs, commands, pass/fail counts, receipt path, closed issue numbers, and remaining blockers.
