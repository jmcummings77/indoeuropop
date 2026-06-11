# Sample Ancestry Estimates

Sample ancestry estimate files hold source-specific ancestry estimates before
regional target aggregation. They are inputs to the target-building pipeline,
not simulator outputs.

## Columns

Each sample ancestry CSV must include:

- `status`: `synthetic` or `published`.
- `sample_id`: sample identifier matching sample metadata and curation files.
- `source`: modeled ancestry source, such as `steppe`.
- `estimate`: sample-level ancestry proportion from `0` to `1`.
- `standard_error`: positive one-sigma uncertainty as a proportion.
- `method`: ancestry-estimation method label.
- `note`: row-level context.

The example file at `examples/sample-ancestry-estimates.example.csv` is
synthetic and must not be cited as historical evidence.

## Guardrail

Published target rows should be built only from published metadata, published
curation rows, and published sample ancestry estimates using the same method
label. Mixed synthetic/published inputs fail in the target-building pipeline.
