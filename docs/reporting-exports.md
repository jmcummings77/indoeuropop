# Reporting Exports

Reporting helpers turn provenance and diagnostic records into simple CSV tables.
They are intended for reproducible review artifacts, not for presenting fitted
scientific conclusions.

## Provenance CSV

`provenance_records_to_csv` serializes records to CSV text. `write_provenance_csv`
writes the same content to disk and creates parent directories when needed.
The CLI exposes the same path with:

```bash
uv run indoeuropop demo --provenance-csv results/provenance.csv
```

The first four columns are always:

- `kind`
- `name`
- `value`
- `unit`

Record metadata becomes `metadata_*` columns in first-seen order. Missing
metadata cells are written as blanks so rows remain rectangular.

## Diagnostics

`diagnostic_issue_records` converts `DiagnosticIssue` objects into derived
provenance records. This lets a report contain simulation values and sanity
checks while still labeling diagnostics as derived software checks.
