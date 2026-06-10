# Data Source Catalog

The data-source catalog records where target files or future sample metadata
inputs come from before any ingestion or aggregation happens. It is metadata
only: catalog entries do not imply that a source has been downloaded, curated,
or used as evidence in a model run.

## TOML Shape

Catalog files use `[[data_sources]]` tables. Each record includes:

- `dataset_id`: stable local identifier.
- `kind`: `target_csv`, `sample_metadata_csv`, `aadr`, or `poseidon`.
- `status`: `planned`, `local`, or `external`.
- `citation_key` and `citation`: required source attribution.
- `uri`: required for `local` and `external` records.
- `checksum_sha256`: optional integrity check for local files.
- `license_note` and `notes`: optional review metadata.

The example manifest is `examples/data-sources.example.toml`. Its bundled target
entry is synthetic and must not be treated as historical evidence.

## Checksum Verification

`verify_record_checksum` verifies only local files with registered SHA-256
digests. Planned AADR and Poseidon entries remain placeholders until a later
ingestion phase chooses exact releases, citations, and licensing constraints.
