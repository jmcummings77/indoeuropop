# Real Target Workflow

The real target workflow rebuilds reviewed target observations from local AADR
files and an externally produced qpAdm estimate table. It does not download
AADR data and does not run ADMIXTOOLS. The expected local AADR quartet is
described in `curation/local-aadr-v66-data-sources.toml` and should remain in
root-level `data/`, which is intentionally ignored by Git.

## Command

```bash
uv run indoeuropop build-aadr-qpadm-targets \
  --aadr-dir data \
  --aadr-groups curation/aadr-v66-western-europe-qpadm-targets.tsv \
  --qpadm-estimates data/qpadm/steppe-estimates.csv \
  --sample-metadata-out results/aadr-target-sample-metadata.csv \
  --target-curation-out results/aadr-target-curation.csv \
  --ancestry-estimates-out results/sample-ancestry-estimates.csv \
  --target-output results/aadr-target-observations.csv \
  --target-diagnostics-json results/aadr-target-diagnostics.json
```

The workflow performs these steps:

- load reviewed AADR group selections;
- prepare selected AADR sample metadata and target curation rows;
- parse the qpAdm table and drop rows without usable in-range estimates and
  standard errors;
- drop whole target rows when any curated sample lacks a retained estimate;
- aggregate retained sample estimates into target observations;
- write JSON diagnostics with selected, retained, and dropped counts.

## Diagnostics

The diagnostics JSON includes:

- requested target count;
- selected AADR sample count;
- raw and parsed qpAdm row counts;
- retained sample-estimate count;
- retained sample and target counts;
- dropped target IDs;
- target-observation counts by region.

These diagnostics are review evidence, not final scientific validation. A
target row being retained only means the local metadata, curation, and qpAdm
table are internally complete enough to build an observation.
