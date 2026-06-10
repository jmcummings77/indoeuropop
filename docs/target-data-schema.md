# Target Data Schema

Target files keep observed or illustrative ancestry summaries outside simulator
code. The current loader accepts CSV so early model checks remain transparent and
diff-friendly.

## Columns

Each target CSV must include these columns:

- `status`: `synthetic` or `published`.
- `region`: modeled region label, such as `britain`.
- `source`: modeled source label, such as `steppe`.
- `time_bce`: observation time in BCE.
- `mean`: ancestry proportion, from `0` to `1`.
- `uncertainty`: positive one-sigma uncertainty as a proportion.
- `citation_key`: short stable citation identifier.
- `citation`: human-readable citation or source note.
- `note`: row-level context.

The example file at `examples/target-observations.example.csv` is synthetic and
must not be cited as historical evidence.

## Comparison Behavior

`TargetDataset.compare(result)` linearly interpolates simulated ancestry to each
target time and returns predicted value, residual, and z-score. It raises if a
target time falls outside the simulation range. This is intentional: inference
code should make time-window mismatches explicit rather than silently
extrapolating.

## Later Data Ingestion

AADR or Poseidon ingestion should translate published sample metadata into this
same target-observation interface. That later layer should preserve accession
IDs, publication metadata, sample counts, and method notes before any regional
aggregation happens.

The data-source catalog in `examples/data-sources.example.toml` is the current
place to register planned AADR/Poseidon inputs and local target files before
implementing that ingestion layer.

Sample-level metadata belongs in the sample metadata schema first. Target CSV
rows should be created only after a documented curation and aggregation step.
That intermediate curation manifest is documented in `docs/target-curation.md`.
