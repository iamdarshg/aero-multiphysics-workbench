# Un-defer Native and AIRFRAME Verification

**Goal:** Remove hard-coded deferrals from the final verification flow, consume real native receipts, and produce a replayable three-family AIRFRAME ledger.

**Constraints:** Native claims remain fail-closed; no fabricated solver output; paid AIRFRAME verification remains capped at US$0.10; tests precede implementation.

## Task 1: Make the cross-solver gate receipt-driven

- Add tests proving Code_Aster, ROSS, electrical, and preCICE availability are derived from governed receipts rather than constants.
- Refactor `bench_promotion.py` to parse and validate those receipts.
- Make the final worker run governed native participants before the promotion gate.

## Task 2: Complete the AIRFRAME ledger contract

- Add tests for observed provenance replay and for rejecting mismatched replay digests.
- Replace the unconditional `pending` replay entry with verified replay evidence when supplied.
- Add a reusable three-family verification input/builder using the shared campaign and result contracts.

## Task 3: Publish bounded verification drivers

- Add a deterministic AIRFRAME final-verification driver and machine-readable receipt.
- Record cost, native capability identity, family stages, provenance, and replay hashes.
- Keep unavailable native capabilities explicit and non-promotable.

## Task 4: Verify and integrate

- Run focused RED/GREEN tests, repository fast gate, and the full Python suite.
- Run native verification where available within the authorized cap.
- Commit/push evidence and close only issues whose definitions of done are actually satisfied.
