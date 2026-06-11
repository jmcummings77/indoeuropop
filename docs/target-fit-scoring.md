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

`scored_sweep_runs_to_csv` and `write_scored_sweep_runs_csv` export ranked
rows with sampled parameter values, aggregate fit metrics, and trajectory
summary fields. `indoeuropop sweep --targets ... --target-fit-csv ...` exposes
the same path from the CLI for small reviewable sweeps.

These ranked runs are not posterior samples. They are a reproducible way to
identify parameter regions worth deeper inference and robustness checks.

## Held-Out Targets

`run_validated_parameter_sweep` ranks the same kind of deterministic sweep on
calibration targets while preserving held-out validation fit. This makes
over-tuned parameter regions easier to spot before introducing ABC-SMC,
Bayesian optimization, or emulator code.
