# Sample Metadata Schema

Sample metadata files preserve row-level ancient-DNA sample context before any
regional aggregation or target construction. This layer is a typed staging area
for later AADR or Poseidon ingestion, not an ancestry-estimation method.

## Columns

Each sample metadata CSV must include:

- `status`: `synthetic` or `published`.
- `dataset_id`: data-source catalog identifier.
- `sample_id`: stable sample identifier within the dataset.
- `accession_id`: external accession or package sample identifier.
- `publication_key` and `publication`: citation metadata.
- `region`: modeled region label.
- `site`: archaeological site or source location label.
- `time_bce`: sample date in BCE.
- `date_uncertainty`: non-negative date uncertainty in years.
- `sex`: `female`, `male`, `unknown`, or `not_reported`.
- `method`: dating, grouping, or metadata extraction method note.
- `note`: row-level context.

The example file at `examples/sample-metadata.example.csv` is synthetic and must
not be cited as historical evidence.

## Guardrail

Sample metadata records do not contain ancestry proportions and do not create
target observations. A later curation step must document how sample-level
metadata, genotype-derived estimates, and regional aggregation rules produce any
published target row.
