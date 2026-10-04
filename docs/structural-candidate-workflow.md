# Structural Candidate Workflow

Use this workflow when target curation and held-out residual review motivate a
specific structural hypothesis. It builds target-aligned child regions,
reviews local overrides, and compares a broad migration pulse with the active
child-region candidate on the same baseline. These are exploratory diagnostics;
review-candidate promotion does not establish a historical explanation.

## Prerequisites and route

Run commands from the repository root after [installation](../README.md).
Start with the [real target workflow](real-target-workflow.md) and accepted
post-rerun target observations. Inspect
[held-out validation and refinement](target-comparison-workflow.md#held-out-validation)
and [curation audits](target-curation-audit.md) before changing model structure.
The candidate comparisons use the bounded acceptance method described in the
[inference workflow](inference-workflow.md).

1. [Project child regions](#project-child-regions) and retain a baseline.
2. [Apply and validate overrides](#apply-and-validate-overrides).
3. [Inspect local sensitivity](#inspect-local-sensitivity) and
   [reproduce the candidate decision](#reproduce-the-candidate-decision).
4. [Evaluate a broad pulse](#evaluate-a-broad-pulse) and inspect the
   [child-region diagnostic](#inspect-the-child-region-diagnostic).
5. [Compare on one baseline](#compare-on-one-baseline), validate the curation
   artifacts, then continue to
   [structural SMC validation](structural-smc-validation.md).

Outputs include generated sweep TOMLs, relabeled target CSVs, held-out fit and
delta tables, predictive reports and plots, and checksum manifests. They stay
under local `results/qpadm-rerun/`; the reviewed override inputs stay in
`curation/`.

## Project child regions

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

Save the structured baseline validation before reviewing override deltas:

```bash
uv run indoeuropop validate-targets \
  --config results/qpadm-rerun/central-europe-structured-comparison.toml \
  --targets results/qpadm-rerun/central-europe-structured-targets.csv \
  --validation-field region \
  --validation-fit-csv results/qpadm-rerun/central-europe-structured-validation-fit.csv \
  --validation-report-md results/qpadm-rerun/central-europe-structured-validation-report.md \
  --manifest-json results/qpadm-rerun/central-europe-structured-validation-manifest.json \
  --fit-metric root_mean_squared_error
```

## Apply and validate overrides

The first override file below is the superseded benchmark used to reproduce
the review sequence. The active candidate is the `interaction-best` file used
in the [candidate decision check](#reproduce-the-candidate-decision).
After reviewing priors for one or more child regions, apply them as a partial
override TOML:

```bash
uv run indoeuropop apply-child-region-overrides \
  --config results/qpadm-rerun/central-europe-structured-comparison.toml \
  --child-region-overrides curation/aadr-v66-central-europe-child-overrides.toml \
  --overridden-config-out results/qpadm-rerun/central-europe-curated-comparison.toml
```

Override TOML files can replace a child region's starting counts, migration
pulses, and parameter tables:

```toml
[counts.central_europe__germany_tiefbrunn_cordedware_1]
local = 760
steppe = 42

[[migration_pulses]]
region = "central_europe__germany_tiefbrunn_cordedware_1"
start_bce = 2980
end_bce = 2450
annual_rate = 0.00014

[region_parameters.central_europe__germany_tiefbrunn_cordedware_1]
migration_rate = 0.0002

[source_parameters.central_europe__germany_tiefbrunn_cordedware_1.steppe]
reproductive_multiplier = 1.18
```

Migration pulses in the override file replace inherited pulses for the same
regions by default. Add `[options] replace_migration_pulses = false` to append
them instead.

The first central-Europe override is a review benchmark with an explicit
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

## Inspect local sensitivity

Run a one-factor child-override sensitivity sweep when the curated candidate
passes the tolerance gate but still needs local robustness checks:

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

The default candidate set changes one value at a time around the override file:
counts (`0.9x`, `1.1x`), pulse rates (`0.85x`, `1.15x`), pulse windows (`-50`,
`+50` BCE years), and Steppe reproductive multipliers (`0.95x`, `1.05x`).
The report ranks accepted candidates first, then orders them by priority mean
delta while preserving the protected Britain tolerance.

If the one-factor report points to Steppe reproductive multipliers, run the
second-stage count-by-reproduction interaction grid:

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

This command varies Steppe counts (`0.9x`, `1.0x`, `1.1x`) and reproductive
multipliers (`0.9x`, `0.95x`, `1.0x`, `1.05x`) together for each child region,
while leaving the other child region at the curated candidate values.

## Reproduce the candidate decision

The [2026-06-11 decision](central-europe-override-decision.md) promotes
[the interaction-best override](../curation/aadr-v66-central-europe-child-overrides-interaction-best.toml)
as the active review candidate and keeps the first candidate as a superseded
benchmark. Rerun this head-to-head check whenever targets or source estimates
change:

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

## Evaluate a broad pulse

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

## Inspect the child-region diagnostic

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

## Compare on one baseline

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

Validate the promoted and superseded curation metadata directly from the CLI:

```bash
uv run indoeuropop validate-curation-decisions \
  --curation-decision-file curation/aadr-v66-central-europe-child-overrides.toml \
  --curation-decision-file curation/aadr-v66-central-europe-child-overrides-interaction-best.toml \
  --require-artifacts
```

This strict check also requires the shared-baseline comparison report and
manifest generated above; run it after those artifacts exist.

The example `--focus-observation-index 9` refers to the recorded target order.
Check the target CSV before reusing that index after any curation change.

## Continue and refresh

Run [structural SMC validation](structural-smc-validation.md) before treating a
candidate as stable across holdouts or source models. After target or override
metadata changes, [refresh the standard pipeline](real-target-workflow.md#refresh-and-readiness)
to regenerate the shared-baseline comparison and check readiness.
