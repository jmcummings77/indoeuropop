# Inference Workflow

Use the bounded rejection and sequential calibration commands to screen
parameter ranges against reviewed target observations. Both are engineering
scaffolds: accepted samples and posterior-style diagnostics do not constitute
a calibrated demographic posterior.

## Prerequisites and outputs

Run commands from the repository root after [installation](../README.md).
Prepare accepted target observations through the
[real target workflow](real-target-workflow.md), inspect
[held-out validation](target-comparison-workflow.md#held-out-validation), and
refresh [pipeline readiness](real-target-workflow.md#refresh-and-readiness).
The optional baseline target file below is produced by the
[qpAdm rerun workflow](qpadm-workflow.md).

Both commands write accepted samples, parameter summaries, predictive CSVs,
Markdown reports, plots, and a checksum manifest under `results/qpadm-rerun/`.
These generated files remain local; they require the reviewed data inputs and
are not supplied by a fresh checkout.

## Bounded rejection baseline

Run the first bounded inference scaffold over the accepted target set:

```bash
uv run indoeuropop infer-target-parameters \
  --config curation/aadr-v66-western-europe-comparison.toml \
  --targets results/qpadm-rerun/accepted-target-observations.csv \
  --fit-metric root_mean_squared_error \
  --acceptance-count 6 \
  --posterior-samples-csv results/qpadm-rerun/abc-accepted-samples.csv \
  --posterior-summary-csv results/qpadm-rerun/abc-posterior-summary.csv \
  --inference-report-md results/qpadm-rerun/abc-inference-report.md \
  --posterior-predictive-csv results/qpadm-rerun/abc-posterior-predictive.csv \
  --posterior-predictive-report-md results/qpadm-rerun/abc-posterior-predictive.md \
  --posterior-predictive-plot results/qpadm-rerun/abc-posterior-predictive.png \
  --holdout-targets results/qpadm-rerun/baseline-target-observations.csv \
  --holdout-posterior-predictive-csv results/qpadm-rerun/abc-holdout-posterior-predictive.csv \
  --holdout-posterior-predictive-report-md results/qpadm-rerun/abc-holdout-posterior-predictive.md \
  --holdout-posterior-predictive-plot results/qpadm-rerun/abc-holdout-posterior-predictive.png \
  --manifest-json results/qpadm-rerun/abc-inference-manifest.json
```

The command implements a deliberately modest ABC-style rejection baseline. It
uses the existing deterministic sweep and target-fit scoring path, then retains
samples by `--acceptance-count`, `--acceptance-threshold`, or
`--acceptance-quantile`. It can also write posterior predictive diagnostics for
the calibration targets and an optional holdout-style target file. The holdout
comparison is only as strong as the split design; use it as an engineering
model check unless the holdout targets were selected before inspecting results.
The output is useful for regression-checked parameter screening before ABC-SMC
or emulator-guided proposals, but it is not a standalone demographic posterior.

## Sequential calibration

Run a sequential ABC-SMC-style calibration over the accepted targets when the
readiness and same-baseline structural gates are clean:

```bash
uv run indoeuropop infer-target-parameters-smc \
  --config curation/aadr-v66-western-europe-comparison.toml \
  --targets results/qpadm-rerun/accepted-target-observations.csv \
  --fit-metric root_mean_squared_error \
  --acceptance-count 6 \
  --smc-generations 3 \
  --smc-sample-count 30 \
  --smc-generations-csv results/qpadm-rerun/abc-smc-generations.csv \
  --posterior-samples-csv results/qpadm-rerun/abc-smc-final-samples.csv \
  --posterior-summary-csv results/qpadm-rerun/abc-smc-final-summary.csv \
  --inference-report-md results/qpadm-rerun/abc-smc-report.md \
  --posterior-predictive-csv results/qpadm-rerun/abc-smc-posterior-predictive.csv \
  --posterior-predictive-report-md results/qpadm-rerun/abc-smc-posterior-predictive.md \
  --posterior-predictive-plot results/qpadm-rerun/abc-smc-posterior-predictive.png \
  --manifest-json results/qpadm-rerun/abc-smc-manifest.json
```

The SMC scaffold performs repeated deterministic sweeps, accepts the best target
fits by count or quantile, and narrows the next generation's parameter ranges
from accepted-sample quantiles. It is useful for calibrated proposal narrowing
and posterior predictive regression checks. Target construction propagates
sample estimate standard errors, and chi-square scoring can use that target
uncertainty. Predictive intervals summarize the accepted simulator runs; the
scaffold does not jointly model the ancestry-estimation process. It also lacks
particle weights and formal priors beyond the configured ranges, so treat it
as an engineering inference layer rather than final population-history evidence.

## Next steps

Use the [structural candidate workflow](structural-candidate-workflow.md) to
compare explicit structural hypotheses on a shared baseline, then run
[structural SMC validation](structural-smc-validation.md) for holdout,
uncertainty, and source-model sensitivity checks. See
[emulator training](emulator-training.md) and
[emulator validation](emulator-validation.md) for the separate surrogate path.
