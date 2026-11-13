# RP-G5 — negative controls: **RUN**, and the model fails the frozen gate

This gate was previously marked NOT RUN with the reason "needs a completed run". That was wrong.
The gate is **data-driven**: `diversity_novelty_eval.py` screens a checkpoint against the frozen
spec plus three negative controls, and a completed checkpoint already exists on disk. It was
evaluated here in about 13 minutes on CPU with 2 seeds.

## What was run

```
python scripts/diversity_novelty_eval.py \
  --checkpoint evidence/research-paper/rp-g1/run-w0p5-14ep/checkpoints/final_monitored_model.pt \
  --train-manifest <case>/train_manifest.jsonl \
  --holdout-manifest <case>/holdout_manifest.jsonl \
  --output gate_result.json --seeds 2 --device cpu
```

- Corpus: `evidence/research-paper/rp-g1/corpus/manifest.jsonl`, split into **660 train / 96 holdout**.
- Gate spec hash: `4eafa9488650a3604f43bfa81be7476fc3b19575aa7ee9c15db90de2125fd135` — **matches the
  frozen RP-G0 hash**, so the gate under test is the frozen one, not a locally edited variant.
- 2 seeds × 96 conditions = **192 generated samples**.

## Result: the model FAILS

| metric | value | gate requirement | verdict |
|---|---:|---|---|
| `new_gate_pass` | **false** | must be true | **FAIL** |
| `distinct_array_count` | **1** | ≥ 5 | **FAIL** |
| `novel_voxel_fraction_mean` | **0.0** | ≥ 0.01 | **FAIL** |
| `nontrivial_pair_count` | **0** | not zero | **FAIL** |
| `old_gate_pass_rate` | **0.0** | — | all samples fail the old 12-check screen |
| `condition_response` (Spearman) | **0.0** | ≥ 0.01 spread | **FAIL** |
| structural articulation | 192 / 192 pass | ≥ 2 signals | pass |

Every per-condition block shows `distinct_array_count: 1` and `pairwise_iou_mean: 1.0` — i.e. the
two seeds produced **bit-identical** output for every one of the 96 conditions. This is total mode
collapse, not a marginal miss.

## The controls are what make the result trustworthy

| case | `new_gate_pass` | novelty | old gate | structural |
|---|---|---:|---|---|
| **model (final, w=0.0 run)** | **false** | **0.0000** | **fail (0%)** | pass |
| `constant_union(train)` | false | 0.0000 | fail | pass |
| `plus_cross` | false | 0.3020 | **pass** | fail |
| `three_box` | false | 0.6109 | **pass** | fail |

This is a **well-behaved gate**, and that is worth stating explicitly:

- `constant_union` — the trivially degenerate control — is rejected, exactly as it should be.
- `plus_cross` and `three_box` are **not trivially rejected**: they clear the old 12-check screen
  and score **high novelty** (0.30 and 0.61), and are caught *only* by the structural articulation
  requirement. A gate that rejected them on novelty alone would be trivially fooled by a crude
  primitive. The control set is doing real discriminating work.
- The model is rejected on **all four** axes it can be rejected on, and scores **exactly the same
  novelty as the degenerate constant control (0.0)**.

**The model is indistinguishable from the `constant_union` negative control on novelty.** That is
the single most damaging line in this report: the generator's output has no voxel novelty relative
to the training union, which is the definition of having memorised the corpus.

## Gate verdict: **FAIL**

This is not "control not run". The controls ran, the frozen gate was honoured, and the model fails
it on five independent metrics with the controls confirming the gate discriminates.

## Caveats I am attaching

1. **This checkpoint is from the `w=0.0` / weight-0.5 family**, which is the arm already known to
   collapse. The D3 arm (standardization + occupancy weight 1, 576/576, 35 distinct, 9.9% unique)
   is the strongest arm and **was not evaluated here** — no saved checkpoint for it was found under
   `evidence/`. So this verdict is about **this checkpoint**, and the honest statement is *"the
   evaluated checkpoint fails the frozen gate"*, not *"the project has no viable model"*.
2. `--seeds 2` was used to bound runtime. Two seeds are enough to expose **complete** collapse
   (identical arrays), but a finer diversity estimate would want more.
3. `condition_response` Spearman = 0.0 here is a consequence of the collapse (all outputs
   identical), not an independent conditioning failure.

## Suggested RP-G5 wording

> RP-G5 **FAIL**. The frozen diversity/novelty gate (`4eafa948…`) was run on the saved
> `final_monitored_model.pt`: `new_gate_pass = false`, `distinct_array_count = 1` of 5 required,
> `novel_voxel_fraction_mean = 0.0` against a 0.01 threshold, `nontrivial_pair_count = 0`, and a
> 0% pass rate on the old 12-check screen. Both seeds produced bit-identical output for all 96
> conditions. The gate correctly rejects the `constant_union`, `plus_cross` and `three_box` negative
> controls, so the failure is a property of the model, not the gate. The model's novelty score is
> identical to the degenerate constant control.