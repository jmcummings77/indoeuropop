# Source Downloads

Catalog-driven source downloads materialize reviewed data-source records before
target curation or ingestion. The downloader does not choose an AADR/Poseidon
release automatically; exact releases, URLs, citations, licenses, and optional
checksums belong in a versioned data-source catalog.

## CLI

```bash
uv run indoeuropop download-sources \
  --data-sources examples/data-sources.example.toml \
  --output-dir data/raw \
  --download-manifest-csv results/downloads.csv
```

Use `--dataset-id` repeatedly to download only selected records:

```bash
uv run indoeuropop download-sources \
  --data-sources data/data-sources.toml \
  --dataset-id aadr-v66 \
  --output-dir data/raw \
  --overwrite
```

## Catalog Fields

Downloadable records use `status = "local"` or `status = "external"`.
`status = "planned"` records are placeholders and are skipped unless explicitly
selected, in which case the command fails.

Useful fields:

- `uri`: local path, `file://` URI, `http://` URL, or `https://` URL.
- `download_filename`: optional cache filename for API URLs.
- `checksum_sha256`: optional integrity check.
- `citation` and `license_note`: source attribution and use constraints.

For Dataverse-hosted releases, use the Dataverse dataset or file-access URL in
`uri` and set `download_filename` to a reviewed release filename. For Poseidon
archives or packages, use the archive/API download URL for the selected package.

## Guardrail

Downloaded archives are raw source artifacts. They are not target observations
until reviewed metadata, sample ancestry estimates, and curation records pass
through the target data pipeline.
