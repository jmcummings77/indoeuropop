# AADR Target Input Preparation

The AADR target-input command prepares real sample metadata and target-curation
CSV files from a local AADR annotation release plus a reviewed list of AADR
groups. It does not invent ancestry estimates.

## Group Selection File

Use a two-column TSV or CSV file:

```text
region	aadr_group_id
britain	England_BellBeaker
britain	England_EBA
central_europe	Germany_BellBeaker
central_europe	Czech_BellBeaker
iberia	Iberia_BellBeaker
iberia	Iberia_EBA
```

The `region` column is the modeled project region to assign to selected
samples. The `aadr_group_id` column is matched against the AADR `Group ID`
field. Use `--aadr-group-match prefix` when the reviewed label intentionally
covers AADR release variants such as `England_EBA_C`.

You can create a first-pass review file from local AADR annotation geography,
dates, and group labels:

```bash
uv run indoeuropop suggest-aadr-groups \
  --aadr-dir /Users/jmcummings/Claude/Projects/indoeuropop_claude/data/aadr/orig \
  --aadr-groups-out results/aadr-group-suggestions.tsv
```

The suggestion file should still be reviewed before it is used for target
preparation.

The repository also includes a committed western-Europe qpAdm target seed:

```text
curation/aadr-v66-western-europe-qpadm-targets.tsv
```

It loads with the same `--aadr-groups` argument and is intended for the external
qpAdm workflow documented in `docs/qpadm-workflow.md`.

## CLI

```bash
uv run indoeuropop prepare-aadr-target-inputs \
  --aadr-dir /Users/jmcummings/Claude/Projects/indoeuropop_claude/data/aadr/orig \
  --aadr-groups curation/aadr-v66-western-europe-qpadm-targets.tsv \
  --ancestry-method qpadm_steppe \
  --sample-metadata-out results/aadr-target-sample-metadata.csv \
  --target-curation-out results/aadr-target-curation.csv
```

The command writes sample metadata filtered to the selected groups and remaps
each sample into the modeled region from the group file. It also writes one
target-curation row per group selection with the real selected sample IDs and
date range.

`--allow-missing-aadr-groups` is useful when a reviewed group-selection file was
written for another AADR release. Unmatched rows are printed and skipped; at
least one group must still match.

## Next Required Input

The target builder still requires sample-level ancestry estimates:

```bash
uv run indoeuropop filter-target-inputs \
  --sample-metadata results/aadr-target-sample-metadata.csv \
  --target-curation results/aadr-target-curation.csv \
  --ancestry-estimates path/to/sample-ancestry-estimates.csv \
  --sample-metadata-out results/filtered-aadr-target-sample-metadata.csv \
  --target-curation-out results/filtered-aadr-target-curation.csv

uv run indoeuropop build-targets \
  --sample-metadata results/filtered-aadr-target-sample-metadata.csv \
  --target-curation results/filtered-aadr-target-curation.csv \
  --ancestry-estimates path/to/sample-ancestry-estimates.csv \
  --target-output results/aadr-target-observations.csv
```

Those estimates must come from a documented external method such as qpAdm,
published tables, or another reviewed ancestry-estimation workflow. AADR `.anno`
metadata alone is not enough to build autosomal ancestry targets.
