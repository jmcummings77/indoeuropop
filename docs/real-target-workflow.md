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
