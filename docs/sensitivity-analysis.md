# Sensitivity Analysis

The first sensitivity layer is intentionally lightweight. It consumes
`SweepRun` records from deterministic parameter sweeps and reports association
metrics between sampled parameters and a selected trajectory summary outcome.

## Metrics

`analyze_sensitivity` returns one `SensitivityResult` per sampled parameter:

- `pearson_correlation`: linear association with the outcome.
- `spearman_correlation`: rank association with the outcome.
- `linear_slope`: least-squares slope of outcome on parameter value.

Results are sorted by absolute Spearman correlation. This is useful for quick
screening because small exploratory sweeps often care more about monotonic
ordering than exact linear effect size.

`sensitivity_results_to_csv` and `write_sensitivity_csv` export these
diagnostics to a stable CSV schema for review alongside sweep-run summaries.

## Supported Outcomes

The supported outcome names match numeric fields on `TrajectorySummary`:

- `initial_ancestry`
- `final_ancestry`
- `ancestry_delta`
- `ancestry_slope_per_century`
- `min_total_population`
- `final_total_population`

## Guardrail

These metrics are exploratory diagnostics. They are not Sobol indices, Bayes
factors, or posterior probabilities. Use them to decide where to run richer
sweeps or inference, not as final causal claims.
