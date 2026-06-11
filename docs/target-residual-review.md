# Target Residual Review

The residual-review command turns a `compare-targets` residual CSV into a
Markdown review report. It ranks targets by absolute z-score, summarizes each
modeled region, includes optional target-build diagnostics, and recommends
whether to review target curation/qpAdm choices before changing simulator
parameters.

## CLI

```bash
uv run indoeuropop review-target-residuals \
  --target-residuals results/real-aadr-comparison/target-residuals.csv \
  --target-diagnostics-json results/real-aadr-comparison/aadr-target-diagnostics.json \
  --target-review-md results/real-aadr-comparison/target-residual-review.md
```

Without `--target-review-md`, the Markdown report is printed to stdout.

## Current AADR V66 Finding

In the pre-decision AADR v66 western-Europe comparison, the largest residual
was:

- `Germany_StkrStraubing_BellBeaker`
- region: `central_europe`
- target time: about `2235.67` BCE
- observed qpAdm steppe mean: `0.018399`
- model prediction: `0.498621`
- residual: `0.480222`
- z-score: `4.269364`

The retained target row contains 12 Stkr-Straubing samples. The external qpAdm
runner assigns all 12 the same group-level steppe estimate of `0.018399` with
standard error `0.389645` and p-value `0.482103`. This pattern should be
reviewed as qpAdm model/target-curation evidence before widening simulator
parameter ranges. A smooth central-Europe trajectory cannot fit that very low
late Bell Beaker target and the high earlier Corded Ware targets at the same
time without more structured regional or group-specific modeling.

That finding is now recorded in
`curation/aadr-v66-western-europe-target-decisions.csv` as `rerun_qpadm`, so the
decision-aware target build defers Stkr-Straubing before target comparison. The
same decision file now also defers the other currently non-retained target rows
whose qpAdm point estimates or standard errors are outside accepted ranges. In
the current decision-aware comparison, the residual report contains 11 retained
targets, zero z-score outliers, and a top retained residual of about `-1.297`
for `Germany_Tiefbrunn_CordedWare-1`.

## Recommended Next Step

Rerun or revise the qpAdm source/outgroup setup for the 27 decision-deferred
targets before treating the 11 retained observations as representative. For
Stkr-Straubing, also review target grouping and decide whether the central
Europe targets should be split into finer regions or culture/site-level
trajectories before adding heavier inference.

Use the target-curation audit command to expand this residual into the exact
curation row, sample metadata rows, and qpAdm estimate rows that produced it.
This command should be run against a residual CSV generated before the
Stkr-Straubing decision is applied:

```bash
uv run indoeuropop audit-target-curation \
  --target-residuals results/real-aadr-comparison/target-residuals.csv \
  --target-curation results/real-aadr-comparison/aadr-target-curation.csv \
  --sample-metadata results/real-aadr-comparison/aadr-target-sample-metadata.csv \
  --ancestry-estimates results/real-aadr-comparison/sample-ancestry-estimates.csv \
  --target-audit-md results/real-aadr-comparison/stkr-straubing-curation-audit.md
```
