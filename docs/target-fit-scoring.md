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

`indoeuropop validate-targets` exposes the same check from the CLI. By default
it performs leave-one-region-out validation. Set `--validation-field
note:requested_group_id` for a leave-one-target-group-out diagnostic when target
rows include semicolon-delimited note metadata from the AADR/qpAdm builder. The
command can write ranked validation CSV rows, a Markdown summary, and a
checksummed manifest.

## Parameter Refinement

`indoeuropop refine-target-parameters` uses held-out validation to generate
diagnostic narrowed and expanded sweep grids around validation-best sampled
values. It writes:

- a scenario summary CSV;
- a parameter-range comparison CSV;
- a Markdown report;
- an optional checksummed manifest.

The command accepts `--priority-validation-value` for holdouts that should
improve and `--protected-validation-value` for holdouts that should not degrade.
This makes parameter-grid refinement reviewable before adding heavier inference
or changing model structure.

## Target-Aligned Structure

`indoeuropop structure-target-regions` projects selected target rows into
child model regions before another comparison, validation, or refinement pass.
The default structure field is `note:requested_group_id`, and
`--structure-region` limits the split to one or more parent regions.

The generated sweep TOML is loadable by the same comparison commands. It
splits selected parent initial counts evenly across child regions and copies
parent migration pulses plus parameter overrides. Treat that as a debugging and
curation scaffold; child-region priors should be reviewed before interpreting a
fit change as historical evidence.

`indoeuropop apply-child-region-overrides` applies reviewed partial TOML
overrides to a structured sweep config. The override file can specify child
counts, migration pulses, region parameter tables, and source parameter tables.
Pulse overrides replace inherited pulses for the same child region by default;
append mode is available through `[options] replace_migration_pulses = false`.

`indoeuropop review-override-deltas` compares two validation fit CSV files and
writes fold-level override-minus-baseline deltas. Use priority values for folds
that should improve and protected values for folds that should not degrade
before promoting an override into committed curation.

The current tracked central-Europe candidate is
`curation/aadr-v66-central-europe-child-overrides.toml`. It documents Britain
as the protected holdout and sets the explicit protected-fold tolerance to
`0.03` RMSE; pass the same value with `--refinement-tolerance 0.03` when running
the override-delta acceptance report.
