# Perf benchmark tier

Machine-readable contract for the engineering-hot-path performance baselines
(issue #24, PERF 01/07). See [`docs/performance-baselines.md`](../../docs/performance-baselines.md)
for the measured baseline, the overhead-vs-solver split, and the full workflow.

- `budgets.json` — committed regression budgets (generous order-of-magnitude
  ceilings plus cold-start hang guards). Never contains measured numbers.
- `reports/` — **generated** JSON reports and cProfile dumps. Gitignored
  (`benchmarks/perf/.gitignore`); do not commit generated output.

`budgets.json` entry shape:

```json
{ "id": "<benchmark id>", "metric": "p95_ms", "direction": "max", "limit": 5, "rationale": "..." }
```

`metric` is one of `median_ms`, `p95_ms`, `total_ms`, `per_item_ms`,
`items_per_second`, `mib_per_second`; `direction` is `max` (ceiling) or `min`
(floor). A budget is only evaluated for a benchmark that actually ran; skipped
benchmarks (missing capability) never fail the gate.
