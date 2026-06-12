# Real Target Workflow

The real target workflow rebuilds reviewed target observations from local AADR
files and an externally produced qpAdm estimate table. It does not download
AADR data and does not run ADMIXTOOLS. The expected local AADR quartet is
described in `curation/local-aadr-v66-data-sources.toml` and should remain in
root-level `data/`, which is intentionally ignored by Git.

## Command

```bash
uv run indoeuropop build-aadr-qpadm-targets \
  --aadr-dir data \
  --aadr-groups curation/aadr-v66-western-europe-qpadm-targets.tsv \
  --qpadm-estimates data/qpadm/steppe-estimates.csv \
  --sample-metadata-out results/aadr-target-sample-metadata.csv \
  --target-curation-out results/aadr-target-curation.csv \
  --ancestry-estimates-out results/sample-ancestry-estimates.csv \
  --target-output results/aadr-target-observations.csv \
  --target-decisions curation/aadr-v66-western-europe-target-decisions.csv \
  --target-diagnostics-json results/aadr-target-diagnostics.json
```

The workflow performs these steps:

- load reviewed AADR group selections;
- prepare selected AADR sample metadata and target curation rows;
- apply reviewed target decisions, deferring rows marked `exclude`, `split`, or
  `rerun_qpadm`;
- parse the qpAdm table and drop rows without usable in-range estimates and
  standard errors;
- drop whole target rows when any curated sample lacks a retained estimate;
- aggregate retained sample estimates into target observations;
- write JSON diagnostics with selected, retained, and dropped counts.

## Diagnostics

The diagnostics JSON includes:

- requested target count;
- selected AADR sample count;
- raw and parsed qpAdm row counts;
- retained sample-estimate count;
- retained sample and target counts;
- dropped target IDs;
- target-decision retained, deferred, and undecided counts;
- target-observation counts by region.

These diagnostics are review evidence, not final scientific validation. A
target row being retained only means the local metadata, curation, and qpAdm
table are internally complete enough to build an observation.

After reviewing the retained target observations, use
`indoeuropop compare-targets` to rank deterministic sweep outputs against the
target CSV and write best-run residual and overlay-plot diagnostics.

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

In the current local decision-aware run, the baseline path produced 11 retained
target observations from 301 selected AADR samples and 301 baseline qpAdm
individual rows. A focused qpAdm rerun wrote 250 individual rows across 27
rerun groups; strict conversion kept 4 rerun sample estimates, rescuing
`Scotland_BellBeaker` and `Germany_ManchingOberstimm_BellBeaker` as
high-uncertainty caveated targets. The reviewed decision file now marks all 38
requested targets: 13 as `retain_with_caveat` and 25 as `rerun_qpadm`, leaving
zero undecided targets. The accepted post-rerun comparison sweep evaluated 24
deterministic samples; the best row had RMSE `0.273952` against the 13 retained
target observations, with zero z-score outliers in the residual review.

Run held-out validation before expanding the inference surface:

```bash
uv run indoeuropop validate-targets \
  --config curation/aadr-v66-western-europe-comparison.toml \
  --targets results/qpadm-rerun/accepted-target-observations.csv \
  --validation-fit-csv results/qpadm-rerun/accepted-validation-fit.csv \
  --validation-report-md results/qpadm-rerun/accepted-validation-report.md \
  --manifest-json results/qpadm-rerun/accepted-validation-manifest.json \
  --fit-metric root_mean_squared_error
```

The current leave-one-region-out pass selected run `9` for both folds. Holding
out Britain gave validation RMSE `0.122664`; holding out central Europe gave
validation RMSE `0.305043`. A leave-one-requested-group-out pass using
`--validation-field note:requested_group_id` again selected run `9` for every
fold and found the largest held-out RMSE on `Germany_Tiefbrunn_CordedWare-1`
(`0.630451`).

Run validation-guided parameter refinement to compare the current sweep grid
with narrowed and expanded grids centered on the validation-best sampled
parameters:

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

The current refinement diagnostics do not identify a no-regret parameter-grid
change. Narrowing improves the central-Europe held-out RMSE by `0.010448` but
degrades Britain by `0.019410`; expanding improves central Europe by `0.007753`
but degrades Britain by `0.061346`. A group-level pass focused on
`Germany_Tiefbrunn_CordedWare-1` improves that target by up to `0.031027` while
degrading protected Britain groups by up to `0.168369`.

For the next structural diagnostic, split the broad central-Europe model region
into target-note child regions and rerun comparison or validation against the
generated artifacts:

```bash
uv run indoeuropop structure-target-regions \
  --config curation/aadr-v66-western-europe-comparison.toml \
  --targets results/qpadm-rerun/accepted-target-observations.csv \
  --structure-region central_europe \
  --structured-targets-out results/qpadm-rerun/central-europe-structured-targets.csv \
  --structured-config-out results/qpadm-rerun/central-europe-structured-comparison.toml
```

This projection is intentionally conservative. It preserves the accepted target
observations while creating a loadable config whose child regions inherit the
parent region's starting counts, migration pulses, and parameter overrides.
Curated child-specific priors should come before interpreting any improved fit
as evidence for distinct local dynamics.

Apply a reviewed child-region override TOML after the structural projection:

```bash
uv run indoeuropop apply-child-region-overrides \
  --config results/qpadm-rerun/central-europe-structured-comparison.toml \
  --child-region-overrides curation/aadr-v66-central-europe-child-overrides.toml \
  --overridden-config-out results/qpadm-rerun/central-europe-curated-comparison.toml
```

The override file is intentionally partial: include only the child-region count
tables, migration pulses, region parameters, or source parameters that have a
reviewed rationale. When a child region appears in `[[migration_pulses]]`, its
inherited pulse is replaced unless `[options] replace_migration_pulses = false`
is set.

The committed central-Europe file is a review candidate with Britain protected
and a `0.03` RMSE protected-fold tolerance. Rerun validation with the curated
config before the delta review:

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

Compare structured and overridden validation outputs before promoting an
override file:

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

After the curated override passes that gate, run the one-factor sensitivity
sweep to inspect nearby alternatives:

```bash
uv run indoeuropop sweep-child-overrides \
  --config results/qpadm-rerun/central-europe-structured-comparison.toml \
  --targets results/qpadm-rerun/central-europe-structured-targets.csv \
  --child-region-overrides curation/aadr-v66-central-europe-child-overrides.toml \
  --priority-validation-value central_europe__germany_tiefbrunn_cordedware_1 \
  --priority-validation-value central_europe__germany_manchingoberstimm_bellbeaker \
  --protected-validation-value britain \
  --refinement-tolerance 0.03 \
  --override-sensitivity-csv results/qpadm-rerun/central-europe-child-override-sensitivity.csv \
  --override-sensitivity-report-md results/qpadm-rerun/central-europe-child-override-sensitivity.md \
  --manifest-json results/qpadm-rerun/central-europe-child-override-sensitivity-manifest.json \
  --fit-metric root_mean_squared_error
```

When the one-factor sweep points to Steppe reproductive multiplier changes,
run the focused interaction grid:

```bash
uv run indoeuropop sweep-child-override-interactions \
  --config results/qpadm-rerun/central-europe-structured-comparison.toml \
  --targets results/qpadm-rerun/central-europe-structured-targets.csv \
  --child-region-overrides curation/aadr-v66-central-europe-child-overrides.toml \
  --priority-validation-value central_europe__germany_tiefbrunn_cordedware_1 \
  --priority-validation-value central_europe__germany_manchingoberstimm_bellbeaker \
  --protected-validation-value britain \
  --refinement-tolerance 0.03 \
  --override-sensitivity-csv results/qpadm-rerun/central-europe-child-override-interactions.csv \
  --override-sensitivity-report-md results/qpadm-rerun/central-europe-child-override-interactions.md \
  --manifest-json results/qpadm-rerun/central-europe-child-override-interactions-manifest.json \
  --fit-metric root_mean_squared_error
```

The interaction-best file is the active review candidate after direct
comparison with the superseded first curated candidate. Validate it and rerun
the same comparison whenever upstream targets or estimates change:

```bash
uv run indoeuropop apply-child-region-overrides \
  --config results/qpadm-rerun/central-europe-structured-comparison.toml \
  --child-region-overrides curation/aadr-v66-central-europe-child-overrides-interaction-best.toml \
  --overridden-config-out results/qpadm-rerun/central-europe-interaction-best-comparison.toml

uv run indoeuropop validate-targets \
  --config results/qpadm-rerun/central-europe-interaction-best-comparison.toml \
  --targets results/qpadm-rerun/central-europe-structured-targets.csv \
  --validation-field region \
  --validation-fit-csv results/qpadm-rerun/central-europe-interaction-best-validation-fit.csv \
  --validation-report-md results/qpadm-rerun/central-europe-interaction-best-validation-report.md \
  --manifest-json results/qpadm-rerun/central-europe-interaction-best-validation-manifest.json \
  --fit-metric root_mean_squared_error

uv run indoeuropop review-override-deltas \
  --baseline-validation-fit-csv results/qpadm-rerun/central-europe-curated-validation-fit.csv \
  --override-validation-fit-csv results/qpadm-rerun/central-europe-interaction-best-validation-fit.csv \
  --priority-validation-value central_europe__germany_tiefbrunn_cordedware_1 \
  --priority-validation-value central_europe__germany_manchingoberstimm_bellbeaker \
  --protected-validation-value britain \
  --refinement-tolerance 0 \
  --override-delta-csv results/qpadm-rerun/central-europe-curated-vs-interaction-best-delta.csv \
  --override-delta-report-md results/qpadm-rerun/central-europe-curated-vs-interaction-best-delta.md \
  --manifest-json results/qpadm-rerun/central-europe-curated-vs-interaction-best-delta-manifest.json \
  --fit-metric root_mean_squared_error
```

Run a read-only readiness review once the real-data artifacts and override
decision files have been regenerated:

```bash
uv run indoeuropop review-pipeline-readiness \
  --readiness-report-md results/qpadm-rerun/real-pipeline-readiness.md
```

This command checks for the local AADR source files declared by the data-source
catalog, verifies required result artifacts exist, extracts diagnostics and
row-count metrics, checks diagnostics counts against generated target CSVs, and
reuses strict curation-decision artifact validation. The strict curation check
also verifies the active same-baseline head-to-head report and every artifact in
its manifest, so stale structural-comparison outputs block readiness. Treat a
ready report as an engineering gate for inference work, not as scientific
confirmation of any specific demographic mechanism.

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
and posterior predictive regression checks. It still lacks particle weights,
formal priors beyond the configured ranges, and external qpAdm uncertainty
propagation, so treat it as an engineering inference layer rather than final
population-history evidence.

Refresh the standard accepted-target structural outputs, same-baseline
head-to-head comparison, and readiness report with one command:

```bash
uv run indoeuropop refresh-real-pipeline
```

This command is the preferred reproducibility route after target, curation, or
override metadata changes. It reruns the `structure-target-regions` and
`compare-structured-candidates` equivalents using the standard Central Europe
paths, then writes `results/qpadm-rerun/real-pipeline-readiness.md`.

Evaluate the current early-pulse structural candidate against the accepted
targets:

```bash
uv run indoeuropop evaluate-migration-pulse-candidate \
  --config curation/aadr-v66-western-europe-comparison.toml \
  --targets results/qpadm-rerun/accepted-target-observations.csv \
  --fit-metric root_mean_squared_error \
  --acceptance-count 6 \
  --pulse-candidate-name central-europe-early-pulse \
  --pulse-region central_europe \
  --pulse-start-bce 3000 \
  --pulse-end-bce 2600 \
  --pulse-annual-rate 0.00005 \
  --candidate-config-out results/qpadm-rerun/central-europe-early-pulse-comparison.toml \
  --posterior-predictive-report-md results/qpadm-rerun/central-europe-early-pulse-baseline.md \
  --posterior-predictive-plot results/qpadm-rerun/central-europe-early-pulse-baseline.png \
  --candidate-posterior-predictive-report-md results/qpadm-rerun/central-europe-early-pulse-candidate.md \
  --candidate-posterior-predictive-plot results/qpadm-rerun/central-europe-early-pulse-candidate.png \
  --candidate-comparison-report-md results/qpadm-rerun/central-europe-early-pulse-comparison.md \
  --manifest-json results/qpadm-rerun/central-europe-early-pulse-manifest.json
```

The candidate appends a modest extra Central Europe migration pulse during
3000-2600 BCE. It directly tests whether the high Tiefbrunn Corded Ware target
looks more like a transition-timing problem than a global parameter-range
problem. Promote it only if later archaeology/chronology and qpAdm review
support the structural assumption.

Compare the promoted child-region override candidate against the broad-pulse
diagnostic:

```bash
uv run indoeuropop evaluate-child-region-candidate \
  --config results/qpadm-rerun/central-europe-structured-comparison.toml \
  --targets results/qpadm-rerun/central-europe-structured-targets.csv \
  --child-region-overrides curation/aadr-v66-central-europe-child-overrides-interaction-best.toml \
  --fit-metric root_mean_squared_error \
  --acceptance-count 6 \
  --child-region-candidate-name central-europe-child-interaction-best \
  --candidate-config-out results/qpadm-rerun/central-europe-child-interaction-best-posterior-comparison.toml \
  --posterior-predictive-report-md results/qpadm-rerun/central-europe-child-interaction-best-baseline.md \
  --posterior-predictive-plot results/qpadm-rerun/central-europe-child-interaction-best-baseline.png \
  --candidate-posterior-predictive-report-md results/qpadm-rerun/central-europe-child-interaction-best-candidate.md \
  --candidate-posterior-predictive-plot results/qpadm-rerun/central-europe-child-interaction-best-candidate.png \
  --candidate-comparison-report-md results/qpadm-rerun/central-europe-child-interaction-best-vs-broad-pulse.md \
  --reference-comparison-manifest results/qpadm-rerun/central-europe-early-pulse-manifest.json \
  --focus-observation-index 9 \
  --manifest-json results/qpadm-rerun/central-europe-child-interaction-best-manifest.json
```

This path tests whether the residual is better represented by target-aligned
Central Europe structure than by one parent-region pulse. The reference manifest
comparison is diagnostic only because the broad-pulse and child-region runs use
different baselines.

For a direct promotion gate, compare a structured broad-pulse candidate and the
child-region override candidate against the same structured baseline:

```bash
uv run indoeuropop compare-structured-candidates \
  --config results/qpadm-rerun/central-europe-structured-comparison.toml \
  --targets results/qpadm-rerun/central-europe-structured-targets.csv \
  --child-region-overrides curation/aadr-v66-central-europe-child-overrides-interaction-best.toml \
  --fit-metric root_mean_squared_error \
  --acceptance-count 6 \
  --structured-pulse-candidate-name central-europe-structured-broad-pulse \
  --structured-pulse-region-prefix central_europe__ \
  --structured-pulse-start-bce 3000 \
  --structured-pulse-end-bce 2600 \
  --structured-pulse-annual-rate 0.00005 \
  --child-region-candidate-name central-europe-child-interaction-best \
  --structured-pulse-config-out results/qpadm-rerun/central-europe-structured-broad-pulse-comparison.toml \
  --child-candidate-config-out results/qpadm-rerun/central-europe-child-interaction-best-head-to-head.toml \
  --posterior-predictive-report-md results/qpadm-rerun/central-europe-head-to-head-baseline.md \
  --posterior-predictive-plot results/qpadm-rerun/central-europe-head-to-head-baseline.png \
  --structured-pulse-posterior-predictive-report-md results/qpadm-rerun/central-europe-structured-broad-pulse.md \
  --structured-pulse-posterior-predictive-plot results/qpadm-rerun/central-europe-structured-broad-pulse.png \
  --child-posterior-predictive-report-md results/qpadm-rerun/central-europe-child-interaction-best-head-to-head.md \
  --child-posterior-predictive-plot results/qpadm-rerun/central-europe-child-interaction-best-head-to-head.png \
  --head-to-head-report-md results/qpadm-rerun/central-europe-structured-pulse-vs-child-head-to-head.md \
  --focus-observation-index 9 \
  --manifest-json results/qpadm-rerun/central-europe-structured-pulse-vs-child-head-to-head-manifest.json
```

This command keeps the baseline fixed, copies the broad pulse across matching
`central_europe__*` child regions, and compares that candidate directly with the
curated child-region override. Prefer this report over cross-baseline manifest
deltas when deciding which structural hypothesis to promote.

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
deltas. With the default materiality threshold, deltas below `1.0` are reported
as `uncertainty_tie` rather than evidence for either structural candidate.

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

Combine the robustness gates into one promotion decision after the
target-fragility, fit-metric, and source-model reports exist:

```bash
uv run indoeuropop validate-structured-smc-robustness \
  --robustness-candidate-name central-europe-child-interaction-best \
  --target-fragility-decisions-csv results/qpadm-rerun/structured-smc-fragility-gate/target-fragility-decisions.csv \
  --fit-metric-sensitivity-summary-csv results/qpadm-rerun/structured-smc-fit-metric-sensitivity/fit-metric-sensitivity-summary.csv \
  --fit-metric-sensitivity-report-md results/qpadm-rerun/structured-smc-fit-metric-sensitivity/fit-metric-sensitivity.md \
  --source-model-sensitivity-summary-csv results/qpadm-rerun/structured-smc-source-model-sensitivity/source-model-sensitivity-summary.csv \
  --source-model-sensitivity-report-md results/qpadm-rerun/structured-smc-source-model-sensitivity/source-model-sensitivity.md \
  --robustness-output-dir results/qpadm-rerun/structural-smc-robustness-decision
```

The unified report blocks promotion when configured robustness screens disagree
on holdout preferences. Positive target exclusions, uncertainty ties,
preference disagreements, skipped folds, or missing override regions are
preserved as caveats when they do not cause instability.

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
  --caveat-dispositions-csv results/qpadm-rerun/structural-smc-caveat-dispositions.csv \
  --caveat-disposition-report-md results/qpadm-rerun/structural-smc-caveat-dispositions.md
```

Prioritize the disposition queue before review:

```bash
uv run indoeuropop prioritize-structural-smc-caveat-dispositions \
  --caveat-drilldown-csv results/qpadm-rerun/structural-smc-caveat-drilldown/structural-smc-caveat-drilldown.csv \
  --caveat-dispositions-csv results/qpadm-rerun/structural-smc-caveat-dispositions.csv \
  --caveat-priority-output-dir results/qpadm-rerun/structural-smc-caveat-priorities
```

The priority report is a triage aid. It scores rows using disposition status,
caveat type, gate, numeric diagnostic deltas, and target flags; reviewers still
need evidence-backed reasons before accepting the suggested disposition hints.

Pass reviewed dispositions into `validate-structured-smc-robustness` with
`--caveat-drilldown-csv` and `--caveat-dispositions-csv`. Dispositions marked
`requires_qpadm_rerun`, `configuration_gap`, or `blocks_promotion` add blockers
to the unified robustness decision.

Apply reviewed decisions to already prepared target inputs when you want to
inspect the filtered curation CSVs directly:

```bash
uv run indoeuropop apply-target-decisions \
  --sample-metadata results/real-aadr-comparison/aadr-target-sample-metadata.csv \
  --target-curation results/real-aadr-comparison/aadr-target-curation.csv \
  --target-decisions curation/aadr-v66-western-europe-target-decisions.csv \
  --sample-metadata-out results/real-aadr-comparison/decision-filtered-sample-metadata.csv \
  --target-curation-out results/real-aadr-comparison/decision-filtered-target-curation.csv
```

Generate an outlier-focused Markdown review after the comparison step:

```bash
uv run indoeuropop review-target-residuals \
  --target-residuals results/real-aadr-comparison/target-residuals.csv \
  --target-diagnostics-json results/real-aadr-comparison/aadr-target-diagnostics.json \
  --target-review-md results/real-aadr-comparison/target-residual-review.md
```

Audit the top residual's target curation and qpAdm estimate evidence before
changing simulator parameters:

```bash
uv run indoeuropop audit-target-curation \
  --target-residuals results/real-aadr-comparison/target-residuals.csv \
  --target-curation results/real-aadr-comparison/aadr-target-curation.csv \
  --sample-metadata results/real-aadr-comparison/aadr-target-sample-metadata.csv \
  --ancestry-estimates results/real-aadr-comparison/sample-ancestry-estimates.csv \
  --target-audit-md results/real-aadr-comparison/stkr-straubing-curation-audit.md
```
