# Real Target Workflow

The real target workflow rebuilds reviewed target observations from local AADR
files and an externally produced qpAdm estimate table. It does not download
AADR data and does not run ADMIXTOOLS. The expected local AADR quartet is
described in `curation/local-aadr-v66-data-sources.toml` and should remain in
root-level `data/`, which is intentionally ignored by Git.

## Prerequisites

Run from the repository root after [installation](../README.md). Supply local
AADR files and a qpAdm estimate table using the
[qpAdm workflow](qpadm-workflow.md), and review the
[target decisions](target-decisions.md). The examples below write ignored
outputs under `results/real-aadr-comparison/`; they do not fetch external data.

## Build observations

```bash
uv run indoeuropop build-aadr-qpadm-targets \
  --aadr-dir data \
  --aadr-groups curation/aadr-v66-western-europe-qpadm-targets.tsv \
  --qpadm-estimates data/qpadm/steppe-estimates.csv \
  --sample-metadata-out results/real-aadr-comparison/aadr-target-sample-metadata.csv \
  --target-curation-out results/real-aadr-comparison/aadr-target-curation.csv \
  --ancestry-estimates-out results/real-aadr-comparison/sample-ancestry-estimates.csv \
  --target-output results/real-aadr-comparison/aadr-target-observations.csv \
  --target-decisions curation/aadr-v66-western-europe-target-decisions.csv \
  --target-diagnostics-json results/real-aadr-comparison/aadr-target-diagnostics.json
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

## Recorded local snapshot

In the recorded local decision-aware run, the baseline path produced 11 retained
target observations from 301 selected AADR samples and 301 baseline qpAdm
individual rows. A focused qpAdm rerun wrote 250 individual rows across 27
rerun groups; strict conversion kept 4 rerun sample estimates, rescuing
`Scotland_BellBeaker` and `Germany_ManchingOberstimm_BellBeaker` as
high-uncertainty caveated targets. The reviewed decision file marks all 38
requested targets: 13 as `retain_with_caveat` and 25 as `rerun_qpadm`, leaving
zero undecided targets. The accepted post-rerun comparison sweep evaluated 24
deterministic samples; the best row had RMSE `0.273952` against the 13 retained
target observations, with zero z-score outliers in the residual review.

These are exploratory snapshot diagnostics from the existing workflow, not a
new run or calibrated inference. The reviewed input is the
[target-decision table](../curation/aadr-v66-western-europe-target-decisions.csv);
reproduce the accepted comparison using the
[target comparison guide](target-comparison-workflow.md#aadr-v66-review-config)
and inspect its generated fit, residual, and manifest artifacts.

## Compare and inspect targets

Use the [target comparison workflow](target-comparison-workflow.md) for accepted
post-rerun comparison, region/group holdouts, and validation-guided refinement.
Audit residuals and curation evidence before expanding parameter ranges or
changing model structure.

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

## Refresh and readiness

Refresh the standard accepted-target structural outputs, same-baseline
head-to-head comparison, and readiness report with one command:

```bash
uv run indoeuropop refresh-real-pipeline
```

This command is the preferred reproducibility route after target, curation, or
override metadata changes. It reruns the `structure-target-regions` and
`compare-structured-candidates` equivalents using the standard Central Europe
paths, then writes `results/qpadm-rerun/real-pipeline-readiness.md`.

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

## Continue with a focused workflow

- [Target comparison](target-comparison-workflow.md): deterministic ranking,
  residuals, held-out validation, and parameter-grid refinement.
- [Structural candidates](structural-candidate-workflow.md): child-region
  projection, overrides, sensitivity, and comparisons on a shared baseline.
- [Inference](inference-workflow.md): bounded rejection and sequential
  calibration with predictive diagnostics.
- [Structural SMC validation](structural-smc-validation.md): holdout stability,
  target audits, robustness gates, caveat dispositions, and frozen evidence.

Review-candidate and readiness gates support reproducible engineering. They do
not replace archaeological review or establish demographic interpretations.
