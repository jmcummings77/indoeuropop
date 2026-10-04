# Structural SMC Validation

Test whether a structural candidate remains useful across holdouts, uncertain
targets, fit metrics, and qpAdm source-model surfaces. These commands extend the
[SMC calibration scaffold](inference-workflow.md#sequential-calibration);
they do not produce a fully weighted particle posterior or establish historical
population dynamics.

## Prerequisites and sequence

Run commands from the repository root after [installation](../README.md).
Complete the [structural candidate workflow](structural-candidate-workflow.md)
to create the structured config and targets and compare candidates on one
baseline. Retain the accepted-target sample metadata, curation, and merged
qpAdm estimate files from the [real target workflow](real-target-workflow.md).
The source-model gate also needs baseline and accepted target CSVs from the
[qpAdm rerun workflow](qpadm-workflow.md).

1. [Compare with Britain held out](#compare-with-britain-held-out), then
   [validate multiple folds](#validate-multiple-folds).
2. [Review disagreements](#review-disagreements) and
   [audit their targets](#audit-disagreement-targets).
3. Check [target fragility](#check-target-fragility),
   [uncertainty](#review-uncertainty), [fit metrics](#check-fit-metric-sensitivity),
   and [source models](#check-source-model-sensitivity).
4. [Review caveat dispositions](#review-caveat-dispositions), then
   [rebuild the robustness decision](#rebuild-the-robustness-decision).

Each command writes the reports, CSVs, or nested validation bundles described
below to local `results/qpadm-rerun/`. A fresh checkout has no generated run
bundles; complete each producing step before using its outputs downstream.

## Compare with Britain held out

Run the SMC-calibrated structural comparison when the direct same-baseline gate
is clean:

```bash
uv run indoeuropop compare-structured-candidates-smc \
  --config results/qpadm-rerun/central-europe-structured-comparison.toml \
  --targets results/qpadm-rerun/central-europe-structured-targets.csv \
  --validation-field region \
  --validation-value britain \
  --child-region-overrides curation/aadr-v66-central-europe-child-overrides-interaction-best.toml \
  --fit-metric root_mean_squared_error \
  --acceptance-count 6 \
  --smc-generations 3 \
  --smc-sample-count 30 \
  --structured-pulse-candidate-name central-europe-structured-broad-pulse \
  --structured-pulse-region-prefix central_europe__ \
  --structured-pulse-start-bce 3000 \
  --structured-pulse-end-bce 2600 \
  --structured-pulse-annual-rate 0.00005 \
  --child-region-candidate-name central-europe-child-interaction-best \
  --smc-comparison-output-dir results/qpadm-rerun/structured-smc
```

This comparison holds Britain out from SMC calibration while fitting the
target-aligned Central Europe rows, then reports calibration and held-out
posterior predictive diagnostics for the structured baseline, broad pulse, and
child-override candidates. It is a robustness check for structural promotion,
not a replacement for qpAdm review or explicit archaeological chronology.

## Validate multiple folds

Run the multi-fold structural SMC validation before treating either structural
candidate as fold-stable:

```bash
uv run indoeuropop validate-structured-candidates-smc \
  --config results/qpadm-rerun/central-europe-structured-comparison.toml \
  --targets results/qpadm-rerun/central-europe-structured-targets.csv \
  --child-region-overrides curation/aadr-v66-central-europe-child-overrides-interaction-best.toml \
  --fit-metric root_mean_squared_error \
  --acceptance-count 6 \
  --smc-generations 3 \
  --smc-sample-count 30 \
  --structured-pulse-candidate-name central-europe-structured-broad-pulse \
  --structured-pulse-region-prefix central_europe__ \
  --structured-pulse-start-bce 3000 \
  --structured-pulse-end-bce 2600 \
  --structured-pulse-annual-rate 0.00005 \
  --child-region-candidate-name central-europe-child-interaction-best \
  --smc-validation-output-dir results/qpadm-rerun/structured-smc-validation
```

The default fold set combines review metadata and target-derived folds:
protected/Britain holdouts, priority child-region holdouts, every
`central_europe__*` child region, and coarse chronology bands. The top-level
report summarizes how often calibration and holdout folds prefer the same
candidate; disagreement is evidence that a candidate remains a local-fit
hypothesis rather than a promoted population-structure explanation.

## Review disagreements

Drill into those disagreement folds before revising either candidate:

```bash
uv run indoeuropop review-structured-smc-disagreements \
  --smc-validation-summary-csv results/qpadm-rerun/structured-smc-validation/structural-smc-validation-summary.csv \
  --smc-validation-output-dir results/qpadm-rerun/structured-smc-validation \
  --smc-disagreement-csv results/qpadm-rerun/structured-smc-validation/structural-smc-disagreement-diagnostics.csv \
  --smc-disagreement-report-md results/qpadm-rerun/structured-smc-validation/structural-smc-disagreement-diagnostics.md
```

The diagnostic report joins each disagreement fold to held-out target notes,
sample counts, publication keys, uncertainty, and model-level posterior
predictive residuals. Positive
`child_minus_structured_pulse_abs_residual_delta` values mean the child override
fit that target worse than the broad structured pulse; negative values mean the
child override fit it better.

## Audit disagreement targets

Batch-audit the disagreement targets against sample-level AADR metadata and
qpAdm estimates before revising curation or model structure:

```bash
uv run indoeuropop audit-structured-smc-disagreement-targets \
  --smc-disagreement-csv results/qpadm-rerun/structured-smc-validation/structural-smc-disagreement-diagnostics.csv \
  --target-curation results/qpadm-rerun/aadr-target-curation.csv \
  --sample-metadata results/qpadm-rerun/aadr-target-sample-metadata.csv \
  --ancestry-estimates results/qpadm-rerun/merged-sample-ancestry-estimates.csv \
  --disagreement-target-audit-csv results/qpadm-rerun/structured-smc-validation/structural-smc-disagreement-target-audit-samples.csv \
  --disagreement-target-audit-md results/qpadm-rerun/structured-smc-validation/structural-smc-disagreement-target-audit.md
```

The batch audit renders one Markdown section per disagreement target and a
long-form sample CSV. It carries target notes, sample metadata notes, qpAdm
estimate notes, publication keys, sample dates, standard errors, p-values, and
review flags into one place so target fragility can be separated from model
fragility.

## Check target fragility

Run the target-fragility sensitivity gate after the batch audit. It removes
disagreement targets with sample-level fragility flags or repeated identical
sample estimates, writes the filtered target set, and reruns only validation
folds that still have both calibration and holdout rows:

```bash
uv run indoeuropop validate-structured-smc-target-fragility \
  --config results/qpadm-rerun/central-europe-structured-comparison.toml \
  --targets results/qpadm-rerun/central-europe-structured-targets.csv \
  --child-region-overrides curation/aadr-v66-central-europe-child-overrides-interaction-best.toml \
  --fit-metric root_mean_squared_error \
  --acceptance-count 6 \
  --smc-generations 3 \
  --smc-sample-count 30 \
  --structured-pulse-candidate-name central-europe-structured-broad-pulse \
  --structured-pulse-region-prefix central_europe__ \
  --structured-pulse-start-bce 3000 \
  --structured-pulse-end-bce 2600 \
  --structured-pulse-annual-rate 0.00005 \
  --child-region-candidate-name central-europe-child-interaction-best \
  --target-fragility-audit-csv results/qpadm-rerun/structured-smc-validation/structural-smc-disagreement-target-audit-samples.csv \
  --target-fragility-output-dir results/qpadm-rerun/structured-smc-fragility-gate
```

Default exclusion reasons are `high_se`, `critical`, `missing_metadata`,
`missing_estimate`, `out_of_window`, and repeated identical estimates. Use
`--target-fragility-keep-repeated-estimates` when checking only explicit sample
flags, or pass `--target-fragility-flag` repeatedly for a narrower flag set.

## Review uncertainty

Review the remaining disagreement folds with uncertainty-aware scoring before
treating small raw residual differences as model evidence:

```bash
uv run indoeuropop review-structured-smc-uncertainty \
  --smc-validation-summary-csv results/qpadm-rerun/structured-smc-fragility-gate/validation/structural-smc-validation-summary.csv \
  --smc-validation-output-dir results/qpadm-rerun/structured-smc-fragility-gate/validation \
  --smc-uncertainty-csv results/qpadm-rerun/structured-smc-fragility-gate/structural-smc-uncertainty.csv \
  --smc-uncertainty-report-md results/qpadm-rerun/structured-smc-fragility-gate/structural-smc-uncertainty.md
```

This report writes target-level z-scores and child-minus-pulse chi-square
deltas. With the default materiality threshold, absolute deltas at or below
`1.0` are reported as `uncertainty_tie`; larger magnitudes favor the candidate
with the lower chi-square value.

## Check fit-metric sensitivity

Run the fit-metric sensitivity gate when you need to test whether the
fragility-filtered candidate preference is stable across raw RMSE-style scoring
and uncertainty-weighted chi-square scoring:

```bash
uv run indoeuropop validate-structured-smc-fit-metric-sensitivity \
  --config results/qpadm-rerun/central-europe-structured-comparison.toml \
  --targets results/qpadm-rerun/central-europe-structured-targets.csv \
  --child-region-overrides curation/aadr-v66-central-europe-child-overrides-interaction-best.toml \
  --acceptance-count 6 \
  --smc-generations 3 \
  --smc-sample-count 30 \
  --structured-pulse-candidate-name central-europe-structured-broad-pulse \
  --structured-pulse-region-prefix central_europe__ \
  --structured-pulse-start-bce 3000 \
  --structured-pulse-end-bce 2600 \
  --structured-pulse-annual-rate 0.00005 \
  --child-region-candidate-name central-europe-child-interaction-best \
  --target-fragility-audit-csv results/qpadm-rerun/structured-smc-validation/structural-smc-disagreement-target-audit-samples.csv \
  --fit-metric-sensitivity-output-dir results/qpadm-rerun/structured-smc-fit-metric-sensitivity
```

The command writes a shared `filtered-targets.csv`,
`target-fragility-decisions.csv`, `fit-metric-sensitivity-summary.csv`, and
`fit-metric-sensitivity.md`. Each objective gets a nested
`metrics/<fit_metric>/validation/` rerun plus
`metrics/<fit_metric>/structural-smc-uncertainty.md`, so raw preference changes
and uncertainty-aware ties can be reviewed together.

## Check source-model sensitivity

Run the source-model sensitivity gate to test whether the structural validation
depends on the qpAdm target surface rather than the demographic candidate. This
example compares the pre-rerun baseline targets with the accepted post-rerun
targets after aligning them to shared `target_id` values:

```bash
uv run indoeuropop validate-structured-smc-source-model-sensitivity \
  --config curation/aadr-v66-western-europe-comparison.toml \
  --source-model-targets baseline=results/qpadm-rerun/baseline-target-observations.csv \
  --source-model-targets accepted=results/qpadm-rerun/accepted-target-observations.csv \
  --child-region-overrides curation/aadr-v66-central-europe-child-overrides-interaction-best.toml \
  --acceptance-count 6 \
  --smc-generations 3 \
  --smc-sample-count 30 \
  --structured-pulse-candidate-name central-europe-structured-broad-pulse \
  --structured-pulse-region-prefix central_europe__ \
  --structured-pulse-start-bce 3000 \
  --structured-pulse-end-bce 2600 \
  --structured-pulse-annual-rate 0.00005 \
  --child-region-candidate-name central-europe-child-interaction-best \
  --source-model-structure-region central_europe \
  --target-fragility-audit-csv results/qpadm-rerun/structured-smc-validation/structural-smc-disagreement-target-audit-samples.csv \
  --source-model-sensitivity-output-dir results/qpadm-rerun/structured-smc-source-model-sensitivity
```

The command writes `source-model-sensitivity-summary.csv` and
`source-model-sensitivity.md`, plus `source_models/<label>/prepared-targets.csv`,
`source_models/<label>/structured-config.toml`, validation artifacts, and
source-specific uncertainty reviews. By default it filters child overrides to
regions that remain after source-model alignment, and the report records how
many override regions were unavailable for each source-model target surface.

## Review caveat dispositions

Expand the caveats into concrete fold, target, and run-level review rows:

```bash
uv run indoeuropop summarize-structural-smc-caveats \
  --target-fragility-decisions-csv results/qpadm-rerun/structured-smc-fragility-gate/target-fragility-decisions.csv \
  --fit-metric-sensitivity-summary-csv results/qpadm-rerun/structured-smc-fit-metric-sensitivity/fit-metric-sensitivity-summary.csv \
  --source-model-sensitivity-summary-csv results/qpadm-rerun/structured-smc-source-model-sensitivity/source-model-sensitivity-summary.csv \
  --robustness-drilldown-output-dir results/qpadm-rerun/structural-smc-caveat-drilldown
```

The drilldown CSV and Markdown report preserve exact fold names and target IDs
for preference-disagreement and uncertainty-tie caveats, plus run-level rows
for source-model skipped folds and missing override regions.

Initialize a reviewed caveat-disposition template from the drilldown queue:

```bash
uv run indoeuropop initialize-structural-smc-caveat-dispositions \
  --caveat-drilldown-csv results/qpadm-rerun/structural-smc-caveat-drilldown/structural-smc-caveat-drilldown.csv \
  --caveat-dispositions-out results/qpadm-rerun/structural-smc-caveat-dispositions.csv
```

Reviewers can mark each row as `accepted_caveat`, `requires_qpadm_rerun`,
`configuration_gap`, `not_applicable`, or `blocks_promotion`; blank or
`undecided` rows remain unresolved. Validate the reviewed file with:

```bash
uv run indoeuropop validate-structural-smc-caveat-dispositions \
  --caveat-drilldown-csv results/qpadm-rerun/structural-smc-caveat-drilldown/structural-smc-caveat-drilldown.csv \
  --caveat-dispositions-csv curation/aadr-v66-structural-smc-caveat-dispositions.csv \
  --caveat-disposition-report-md results/qpadm-rerun/structural-smc-caveat-dispositions.md
```

Prioritize the disposition queue before review:

```bash
uv run indoeuropop prioritize-structural-smc-caveat-dispositions \
  --caveat-drilldown-csv results/qpadm-rerun/structural-smc-caveat-drilldown/structural-smc-caveat-drilldown.csv \
  --caveat-dispositions-csv curation/aadr-v66-structural-smc-caveat-dispositions.csv \
  --caveat-priority-output-dir results/qpadm-rerun/structural-smc-caveat-priorities
```

The priority report is a triage aid. It scores rows using disposition status,
caveat type, gate, numeric diagnostic deltas, and target flags; reviewers still
need evidence-backed reasons before accepting the suggested disposition hints.

The reviewed table is tracked at
[curation/aadr-v66-structural-smc-caveat-dispositions.csv](../curation/aadr-v66-structural-smc-caveat-dispositions.csv);
its rationale is the [2026-07-15 decision record](structural-smc-caveat-disposition-decision.md).
The initialization command writes a local template; review it before updating
the tracked dispositions. The validation and prioritization examples above
use the existing tracked table. Dispositions marked
`requires_qpadm_rerun`, `configuration_gap`, or `blocks_promotion` add blockers
to the unified robustness decision.

## Rebuild the robustness decision

Once all three gate reports and reviewed dispositions exist, run
`validate-structured-smc-robustness` using the complete command in the
[decision record's rebuild section](structural-smc-caveat-disposition-decision.md#rebuild).
The command reads existing reports without rerunning SMC and writes one
promotion blocker/caveat decision.

The unified report blocks promotion when configured robustness screens disagree
on holdout preferences. Positive target exclusions, uncertainty ties,
preference disagreements, skipped folds, or missing override regions remain
caveats when they do not cause instability. Blocking dispositions feed back
into this decision.

Supplying `--manifest-json` requires the complete reviewed surface and freezes
SHA-256 checksums for the tracked decision inputs, gate summaries, and rebuilt
reports. Review new checksums before replacing the tracked evidence manifest.
It records review evidence without bundling AADR data or turning generated
outputs into scientific results.

The [recorded decision](structural-smc-caveat-disposition-decision.md#decision)
keeps the candidate at `review_with_caveats`, with the recommendation
`promote_only_with_documented_caveats`. Rerun the gates and evidence review when
targets, candidate parameters, or source estimates change; this snapshot is
not a promise about a future run.
