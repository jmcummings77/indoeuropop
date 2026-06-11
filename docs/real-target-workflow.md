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
  --target-diagnostics-json results/aadr-target-diagnostics.json
```

The workflow performs these steps:

- load reviewed AADR group selections;
- prepare selected AADR sample metadata and target curation rows;
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

In the current local run, the full path produced 12 retained target
observations from 301 selected AADR samples and 301 qpAdm individual rows. The
first comparison sweep evaluated 24 deterministic samples; the best row had
RMSE `0.280595` against the retained target observations.

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
