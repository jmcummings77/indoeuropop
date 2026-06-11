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

In the local AADR v66 western-Europe comparison, the largest residual is:

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

## Recommended Next Step

Review the qpAdm source/outgroup model and target grouping for
`Germany_StkrStraubing_BellBeaker`, then review whether the central Europe
targets should be split into finer regions or culture/site-level trajectories
before adding heavier inference.
