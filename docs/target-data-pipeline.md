# Target Data Pipeline

The target data pipeline turns curated sample-level ancestry estimates into the
`TargetDataset` interface used by fitting, validation, and sweep workflows.

## Inputs

The builder requires three CSV files:

- sample metadata, documented in `docs/sample-metadata-schema.md`;
- target curation records, documented in `docs/target-curation.md`;
- sample ancestry estimates, documented in `docs/sample-ancestry-estimates.md`.

Every curation row names the sample IDs, source label, ancestry-estimation
method, aggregation method, citation, and BCE window for one target row.

## Aggregation

`build_target_dataset` supports:

- `mean`, `synthetic_mean`, and `unweighted_mean`;
- `inverse_variance_weighted_mean` and `precision_weighted_mean`.

Target means are aggregated from the selected sample-level estimates. Target
uncertainty combines propagated sample standard errors with between-sample
dispersion. The target time is the arithmetic mean of the included sample dates.

## CLI

```bash
uv run indoeuropop build-targets \
  --sample-metadata path/to/sample-metadata.csv \
  --target-curation path/to/target-curation.csv \
  --ancestry-estimates path/to/sample-ancestry-estimates.csv \
  --target-output results/target-observations.csv
```

The resulting CSV can be loaded with `load_target_dataset` and used by the demo,
sweep scoring, and validation helpers.

## Guardrails

By default, the pipeline requires:

- every curation sample ID to exist in sample metadata;
- every curation sample ID to have a matching ancestry estimate for the curated
  source and method;
- metadata, curation, and ancestry estimates to share the same status;
- sample metadata regions to match the curation region;
- sample dates to fall inside the curation window.

The package does not bundle published target values. Real target files should be
committed only after source licensing, citation text, sample selection, ancestry
method, and uncertainty treatment are reviewed.
