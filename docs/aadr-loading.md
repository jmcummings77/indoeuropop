# AADR Loading

The AADR loader normalizes a local Allen Ancient DNA Resource annotation table
into the project sample metadata schema. It discovers one `.anno`, `.ind`,
`.snp`, and `.geno` file in a directory, but it reads only the `.anno` file for
metadata export. Genotype parsing remains a later phase.

## CLI

```bash
uv run indoeuropop load-aadr \
  --aadr-dir /Users/jmcummings/Claude/Projects/indoeuropop_claude/data/aadr/orig \
  --sample-metadata-out data/aadr-sample-metadata.csv
```

For a small smoke run:

```bash
uv run indoeuropop load-aadr \
  --aadr-dir /Users/jmcummings/Claude/Projects/indoeuropop_claude/data/aadr/orig \
  --sample-metadata-out results/aadr-sample-metadata-head.csv \
  --aadr-limit 10
```

## Mapping

The loader maps:

- AADR genetic ID to `sample_id`;
- persistent genetic ID to `accession_id`;
- publication abbreviation and DOI/repository fields to publication metadata;
- political entity to the initial modeled `region`;
- locality to `site`;
- BP date mean to BCE with `time_bce = date_mean_bp - 1950`;
- AADR molecular sex labels to `female`, `male`, or `unknown`.

The exported rows use `method = "aadr_v66_annotation"` and preserve group ID,
full date text, and assessment in the note field.

## Guardrail

AADR sample metadata is not yet a target observation file. It still needs
sample-level ancestry estimates, curation windows, modeled-region review, and
aggregation through the target data pipeline before it can be used for fit
scoring.

For the next real-data preparation step, see
`docs/aadr-target-inputs.md`. That command filters AADR samples by reviewed group
IDs and writes modeled-region sample metadata plus target-curation rows, while
still requiring external ancestry estimates before target observations are
built.
