# Swarm verification of Fable's six PRs

Six independent verifiers ran concurrently, one per PR, each with a disjoint scratch scope under
`evidence/swarm-verify/<key>/`. Read-only: no verifier modified a tracked file, and none checked out
an `audit/*` branch. This run is a re-run of an earlier attempt that was killed by a host restart;
the verifiers reused the prior scratch directories.

## Results

| repo | PR | verdict | finding |
|---|---|---|---|
| drone-mech | #21 | **SUPPORTED** | `native_motor_interference.json:302` → `FAIL` / exit 1; **50,033.0046 mm³** intersection, 36.0 mm overlap at 36 mm pitch, `collides: true`. Independent BRep rerun matches. Envelope-to-envelope packing only — not an aero result. |
| drone-arm | #39 | **SUPPORTED** | DRC rerun: **0 violations / 0 unconnected / 191 parity** (161 `footprint_symbol_mismatch`, 20 `net_conflict`, 6 `missing_footprint`, 4 `extra_footprint`). Pad nets vs netlist prove the CAN pair is crossed. "0 violations" ≠ clean — the crossing hides inside parity. |
| copperline | #52 | **CONTRADICTED (a fails, b holds)** | (a) the base branch **already** decoded exit codes (`pr52.diff:352-361`, `main.cpp:1203`); the head re-inlines the same logic, so the claimed exit-code fix is a behavioural no-op. (b) the dedupe test does go red→green and was run twice — but it is a script-level `sys.exit` with a single-element assertion, not a pytest test. |
| research-paper | #51 | **OVERSTATED** | Best arm is **35 distinct / 576 = 6.08%**, i.e. 94% duplicates. The **9.9%** figure is a *Pairs-IoU* column measured against a 10% floor — and it **fails that floor by 0.1 pp**. "Latent standardization ends diffusion collapse" is not supported. |
| Code-SDR | #71 | **SUPPORTED** | `wr_idx` and `bins_dropped` are each written in **two** `always` blocks (`verilog/v2_fft_packetizer.v:78` and `:140`). A full 182-line read confirms a genuine multi-driver. |
| aero-multiphysics-workbench | #103 | **CONTRADICTED (but unproven)** | Local run gives **1 failed / 1793 passed / 1794 collected** against a claimed 1797; gate hash `8d159c95` vs pinned `deae9499`. However the checkout is **pre-PR**, so this measures the baseline, not the PR head. Treat as inconclusive rather than refuted. |

## The finding that matters most — and it corrects me

**research-paper #51 is overstated, and my own earlier number was wrong too.**

I previously reported the D3 arm as "576/576 occupancy, 35 distinct, **9.9% unique**". The verifier's
read is sharper: 35/576 = **6.08%**, and the 9.9% I quoted is a *different column* — a Pairs-IoU
metric — which is being compared against a 10% floor and **misses it by 0.1 pp**. So:

- the distinct-sample fraction is **6.08%**, not 9.9%;
- the 9.9% figure is a near-miss on a separate criterion, not a diversity measurement;
- a PR titled "standardization **ends** diffusion collapse" is claiming a win on an arm where
  **94% of samples are duplicates**.

That is the same failure mode I flagged in RP-G10 (the paper saying "five" where its own files say
"two"), and it is directionally the same: the favourable number gets quoted, the unfavourable one
gets dropped.

## Verification discipline notes

- **Two of six verdicts were contradicted**, and one of those (aero #103) is *itself* unproven
  because the verifier's checkout was pre-PR. I am recording it as inconclusive rather than
  accepted, because a verifier that measures the wrong tree cannot refute anything.
- The copperline result is a clean example of a **partial** verification: claim (a) fails, claim (b)
  holds. Reporting a single verdict for the PR would have hidden one of them.
- The drone-arm result shows why an aggregate DRC count is misleading: **0 violations and 0
  unconnected coexist with 191 parity issues**, including six connectors that exist in the
  schematic and in neither the board nor the BOM.

## Artefacts

`evidence/swarm-verify/{drone-mech-21,drone-arm-39,copperline-52,research-paper-51,Code-SDR-71,aero-103}/`

## Cost note

Six concurrent verifiers, 0 failures, one synthesis step. The re-run reused prior scratch dirs,
which is why it completed where the first attempt (killed mid-flight at 01:35 by a host restart) did
not. Durable per-unit scratch directories are what made the restart survivable.