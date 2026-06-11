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

After `build-aadr-qpadm-targets` has written
`results/real-aadr-comparison/aadr-target-observations.csv`, run:

```bash
uv run indoeuropop compare-targets \
  --config curation/aadr-v66-western-europe-comparison.toml \
  --targets results/real-aadr-comparison/aadr-target-observations.csv \
  --sweep-runs-csv results/real-aadr-comparison/sweep-runs.csv \
  --sensitivity-csv results/real-aadr-comparison/sensitivity.csv \
  --target-fit-csv results/real-aadr-comparison/target-fit.csv \
  --target-residuals-csv results/real-aadr-comparison/target-residuals.csv \
  --plot results/real-aadr-comparison/target-comparison.png \
  --manifest-json results/real-aadr-comparison/target-comparison-manifest.json \
  --fit-metric root_mean_squared_error
```

In the local AADR v66.1 run, this comparison evaluated 24 deterministic sweep
samples against 12 retained target observations. The best exploratory run had
RMSE `0.280595`, reduced chi-square `1.886537`, and maximum absolute z-score
`4.269364`. Treat those as review diagnostics only; they are not calibrated
inference.
