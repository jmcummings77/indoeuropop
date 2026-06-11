# Target Comparison Workflow

The target comparison workflow turns a deterministic sweep plus a target CSV
into review artifacts for one best-ranked run. It is exploratory model
diagnostics, not posterior inference.

## CLI

```bash
uv run indoeuropop compare-targets \
  --config examples/sweep.example.toml \
  --targets examples/sweep-targets.example.csv \
  --sweep-runs-csv results/sweep-runs.csv \
  --sensitivity-csv results/sensitivity.csv \
  --target-fit-csv results/target-fit.csv \
  --target-residuals-csv results/target-residuals.csv \
  --plot results/target-comparison.png \
  --manifest-json results/target-comparison-manifest.json \
  --fit-metric root_mean_squared_error
```

The command runs the configured Latin-hypercube sweep, ranks runs against the
target observations, reruns the best parameter set for a full trajectory, and
writes optional artifacts:

- sweep summary rows;
- sensitivity diagnostics;
- ranked aggregate fit rows;
- best-run per-target residual rows;
- a simulated trajectory plus target-point overlay plot;
- an experiment manifest with checksums for requested artifacts.

## Programmatic Use

```python
from pathlib import Path

from indoeuropop import (
    TargetComparisonOutputPaths,
    load_sweep_spec,
    load_target_dataset,
    run_target_comparison_workflow,
)

result = run_target_comparison_workflow(
    load_sweep_spec("examples/sweep.example.toml"),
    load_target_dataset("examples/sweep-targets.example.csv"),
    paths=TargetComparisonOutputPaths(
        target_fit_csv=Path("results/target-fit.csv"),
        target_residuals_csv=Path("results/target-residuals.csv"),
        plot=Path("results/target-comparison.png"),
    ),
    fit_metric="root_mean_squared_error",
)
```

`result.best_run` contains the ranked sweep row and aggregate fit metrics.
`result.best_comparisons` contains the per-target observed, predicted,
residual, and z-score values used for residual reporting.

## Caveats

The workflow compares model outputs to whatever target CSV is supplied. It does
not decide whether the target curation, qpAdm source model, outgroups, or
uncertainties are scientifically adequate. Those checks remain part of the
human review process before heavier inference.

## AADR V66 Review Config

The repository includes an exploratory multi-region sweep config for the
retained western-Europe AADR v66 qpAdm targets:

```text
curation/aadr-v66-western-europe-comparison.toml
```

After focused qpAdm rerun ingestion and decision filtering have written
`results/qpadm-rerun/accepted-target-observations.csv`, run:

```bash
uv run indoeuropop compare-targets \
  --config curation/aadr-v66-western-europe-comparison.toml \
  --targets results/qpadm-rerun/accepted-target-observations.csv \
  --sweep-runs-csv results/qpadm-rerun/accepted-comparison-sweep-runs.csv \
  --sensitivity-csv results/qpadm-rerun/accepted-comparison-sensitivity.csv \
  --target-fit-csv results/qpadm-rerun/accepted-comparison-target-fit.csv \
  --target-residuals-csv results/qpadm-rerun/accepted-comparison-target-residuals.csv \
  --plot results/qpadm-rerun/accepted-comparison-overlay.png \
  --manifest-json results/qpadm-rerun/accepted-comparison-manifest.json \
  --fit-metric root_mean_squared_error
```

In the current decision-aware local AADR v66.1 run after focused qpAdm rerun
ingestion, this comparison evaluated 24 deterministic sweep samples against 13
retained-with-caveat target observations. The best exploratory run had RMSE
`0.273952`, and the residual review found no absolute z-score outliers. Treat
those as review diagnostics only; they are not calibrated inference.

## Held-Out Validation

Run leave-one-region-out validation against the accepted post-rerun targets:

```bash
uv run indoeuropop validate-targets \
  --config curation/aadr-v66-western-europe-comparison.toml \
  --targets results/qpadm-rerun/accepted-target-observations.csv \
  --validation-fit-csv results/qpadm-rerun/accepted-validation-fit.csv \
  --validation-report-md results/qpadm-rerun/accepted-validation-report.md \
  --manifest-json results/qpadm-rerun/accepted-validation-manifest.json \
  --fit-metric root_mean_squared_error
```

Run a more granular leave-one-requested-group-out check using target-note
metadata:

```bash
uv run indoeuropop validate-targets \
  --config curation/aadr-v66-western-europe-comparison.toml \
  --targets results/qpadm-rerun/accepted-target-observations.csv \
  --validation-field note:requested_group_id \
  --validation-fit-csv results/qpadm-rerun/accepted-group-validation-fit.csv \
  --validation-report-md results/qpadm-rerun/accepted-group-validation-report.md \
  --manifest-json results/qpadm-rerun/accepted-group-validation-manifest.json \
  --fit-metric root_mean_squared_error
```

The current accepted-target validation selected run `9` for both region folds:
Britain held out at RMSE `0.122664`, and central Europe held out at RMSE
`0.305043`. The group-level validation also selected run `9` for every fold;
`Germany_Tiefbrunn_CordedWare-1` had the largest held-out RMSE at `0.630451`.
These are stability diagnostics for this exploratory sweep grid, not evidence
that the parameterization is historically sufficient.

## Validation-Guided Refinement

Use `refine-target-parameters` to compare the current sweep grid with generated
narrowed and expanded ranges centered on validation-best sampled values:

```bash
uv run indoeuropop refine-target-parameters \
  --config curation/aadr-v66-western-europe-comparison.toml \
  --targets results/qpadm-rerun/accepted-target-observations.csv \
  --priority-validation-value central_europe \
  --protected-validation-value britain \
  --refinement-summary-csv results/qpadm-rerun/accepted-region-refinement-summary.csv \
  --refinement-ranges-csv results/qpadm-rerun/accepted-region-refinement-ranges.csv \
  --refinement-report-md results/qpadm-rerun/accepted-region-refinement-report.md \
  --manifest-json results/qpadm-rerun/accepted-region-refinement-manifest.json \
  --fit-metric root_mean_squared_error
```

For the current accepted targets, narrowed and expanded grids both improved the
central-Europe holdout, but both degraded the protected Britain holdout. The
narrowed grid changed central-Europe RMSE by `-0.010448` and Britain by
`+0.019410`; the expanded grid changed central Europe by `-0.007753` and
Britain by `+0.061346`.

A group-level pass can focus on the highest held-out residual while protecting
the Britain groups:

```bash
uv run indoeuropop refine-target-parameters \
  --config curation/aadr-v66-western-europe-comparison.toml \
  --targets results/qpadm-rerun/accepted-target-observations.csv \
  --validation-field note:requested_group_id \
  --priority-validation-value Germany_Tiefbrunn_CordedWare-1 \
  --protected-validation-value England_BellBeaker \
  --protected-validation-value England_BellBeaker-o \
  --protected-validation-value Scotland_BellBeaker \
  --refinement-summary-csv results/qpadm-rerun/accepted-group-refinement-summary.csv \
  --refinement-ranges-csv results/qpadm-rerun/accepted-group-refinement-ranges.csv \
  --refinement-report-md results/qpadm-rerun/accepted-group-refinement-report.md \
  --manifest-json results/qpadm-rerun/accepted-group-refinement-manifest.json \
  --fit-metric root_mean_squared_error
```

The expanded group-level candidate improved
`Germany_Tiefbrunn_CordedWare-1` by RMSE `0.031027`, but it degraded protected
Britain groups by up to `0.168369`. That tradeoff argues for structural model
changes before simply expanding the parameter grid.

## Target-Aligned Structure

Use `structure-target-regions` when a broad region, such as central Europe,
needs explicit target-aligned child regions before another comparison or
validation pass:

```bash
uv run indoeuropop structure-target-regions \
  --config curation/aadr-v66-western-europe-comparison.toml \
  --targets results/qpadm-rerun/accepted-target-observations.csv \
  --structure-region central_europe \
  --structured-targets-out results/qpadm-rerun/central-europe-structured-targets.csv \
  --structured-config-out results/qpadm-rerun/central-europe-structured-comparison.toml
```

By default, structure labels come from `note:requested_group_id`. The command
relabels matching targets, splits selected parent initial counts evenly across
child regions, copies parent migration pulses and parameter overrides, and
writes a loadable sweep TOML. The result is a review scaffold: child-specific
dynamics still need archaeologically and genetically defensible priors before
the split should be interpreted as a scientific model improvement.

After reviewing priors for one or more child regions, apply them as a partial
override TOML:

```bash
uv run indoeuropop apply-child-region-overrides \
  --config results/qpadm-rerun/central-europe-structured-comparison.toml \
  --child-region-overrides curation/aadr-v66-central-europe-child-overrides.toml \
  --overridden-config-out results/qpadm-rerun/central-europe-curated-comparison.toml
```

The override file may include `[counts.<region>]`,
`[[migration_pulses]]`, `[region_parameters.<region>]`, and
`[source_parameters.<region>.<source>]` tables. Migration pulses replace
inherited pulses for the same region by default; set
`[options] replace_migration_pulses = false` to append them.

The tracked central-Europe override is a review candidate with an explicit
protected-fold tolerance of `0.03` RMSE for Britain. Rerun validation against
the structured targets before reviewing deltas:

```bash
uv run indoeuropop validate-targets \
  --config results/qpadm-rerun/central-europe-curated-comparison.toml \
  --targets results/qpadm-rerun/central-europe-structured-targets.csv \
  --validation-field region \
  --validation-fit-csv results/qpadm-rerun/central-europe-curated-validation-fit.csv \
  --validation-report-md results/qpadm-rerun/central-europe-curated-validation-report.md \
  --manifest-json results/qpadm-rerun/central-europe-curated-validation-manifest.json \
  --fit-metric root_mean_squared_error
```

Use `review-override-deltas` to compare validation outputs before and after an
override:

```bash
uv run indoeuropop review-override-deltas \
  --baseline-validation-fit-csv results/qpadm-rerun/central-europe-structured-validation-fit.csv \
  --override-validation-fit-csv results/qpadm-rerun/central-europe-curated-validation-fit.csv \
  --priority-validation-value central_europe__germany_tiefbrunn_cordedware_1 \
  --priority-validation-value central_europe__germany_manchingoberstimm_bellbeaker \
  --protected-validation-value britain \
  --refinement-tolerance 0.03 \
  --override-delta-csv results/qpadm-rerun/central-europe-curated-override-delta.csv \
  --override-delta-report-md results/qpadm-rerun/central-europe-curated-override-delta.md \
  --manifest-json results/qpadm-rerun/central-europe-curated-override-delta-manifest.json \
  --fit-metric root_mean_squared_error
```

Negative validation deltas indicate improved held-out fit. Positive protected
deltas should remain within the committed tolerance before a candidate moves
from review-only to default workflow status.

Generate a Markdown review of the residual table with:

```bash
uv run indoeuropop review-target-residuals \
  --target-residuals results/real-aadr-comparison/target-residuals.csv \
  --target-diagnostics-json results/real-aadr-comparison/aadr-target-diagnostics.json \
  --target-review-md results/real-aadr-comparison/target-residual-review.md
```

In the pre-decision comparison, the largest residual was
`Germany_StkrStraubing_BellBeaker`, where the target mean was much lower than
the smooth central-Europe trajectory. That target is now decision-deferred as
`rerun_qpadm`.
