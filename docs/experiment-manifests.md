# Experiment Manifests

Experiment manifests bundle reproducibility metadata for one workflow run. They
are not scientific results and do not imply that a model has been fitted.

The first manifest scaffold records:

- input or output artifacts, such as config files, target files, plots, and
  provenance CSV exports;
- optional SHA-256 checksums for those artifacts;
- simulation-result fingerprints generated from canonical model output;
- small metadata fields describing the CLI command and simulator path.

## CLI Export

The smoke CLI can write a manifest:

```bash
uv run indoeuropop demo \
  --plot results/demo-ancestry.png \
  --provenance-csv results/provenance.csv \
  --manifest-json results/demo-manifest.json
```

When plot or provenance paths are provided, those files are generated before the
manifest is written so their checksums can be included. If no file artifacts are
provided, the manifest still records the simulation fingerprint.

## JSON Shape

The manifest JSON contains:

- `schema_version`;
- `name` and `description`;
- `metadata`;
- `artifacts`;
- `fingerprints`.

The JSON format is intended for audit trails and later orchestration. It is not
a replacement for provenance CSV reports, target curation records, or published
data-source catalogs.
