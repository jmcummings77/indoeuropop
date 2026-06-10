# Target Fit Scoring

Target fit scoring compares simulated ancestry trajectories to a
`TargetDataset`. It is the first bridge from exploratory sweeps toward later
ABC-SMC or Bayesian optimization.

## Metrics

`score_result_against_targets` returns a `TargetFit` with:

- `mean_absolute_error`
- `root_mean_squared_error`
- `chi_square`
- `reduced_chi_square`
- `max_abs_z_score`
- `observation_count`

The chi-square metrics use each target row's `uncertainty` value, so a mismatch
against a precise target counts more than the same raw residual against a broad
target.

## Scored Sweeps

`run_scored_parameter_sweep(spec, targets)` runs the deterministic simulator for
Latin-hypercube samples and ranks `ScoredSweepRun` records by fit. The default
ranking metric is `chi_square`.

These ranked runs are not posterior samples. They are a reproducible way to
identify parameter regions worth deeper inference and robustness checks.
