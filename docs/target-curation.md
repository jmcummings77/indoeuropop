# Target Curation Metadata

Target curation files document how sample selections and methods produce target
observation rows when combined with sample metadata and sample ancestry
estimates. They do not contain ancestry estimates by themselves.

## Columns

Each target curation CSV must include:

- `status`: `synthetic` or `published`.
- `target_id`: stable target identifier.
- `region` and `source`: modeled labels for the future target row.
- `start_bce` and `end_bce`: inclusive curation time window in BCE.
- `sample_ids`: semicolon-delimited sample IDs used for the target.
- `sample_count`: number of listed sample IDs.
- `ancestry_method`: how sample-level ancestry estimates were produced.
- `aggregation_method`: how sample-level estimates were summarized.
- `citation_key` and `citation`: source attribution.
- `note`: row-level context.

The example file at `examples/target-curation.example.csv` is synthetic and must
not be cited as historical evidence.

## Guardrail

A curation row is a provenance bridge, not a result. Published target
observations should be written only after genotype-derived estimates,
uncertainty calculations, and regional aggregation rules are documented in the
target data pipeline inputs.
