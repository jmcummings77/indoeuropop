# AADR Group Suggestions

The `suggest-aadr-groups` command scans a local AADR quartet and writes a
reviewable region/group file for `prepare-aadr-target-inputs`. It is a curation
aid, not a scientific decision rule.

## Inputs

The command expects the same local AADR directory used by `load-aadr`, including
matching `.anno`, `.ind`, `.snp`, and `.geno` files. It reads only annotation
and individual-label metadata. Genotypes are not parsed.

Suggestions are filtered by:

- A broad BCE date window, defaulting to 3000-1000 BCE.
- Coarse modeled-region bounding boxes for Britain, central Europe, and Iberia.
- Group-label keywords such as `beaker`, `corded`, `bronze`, `_eba`, and `_ba`.
- A minimum count per suggested group, defaulting to three samples.
- Group labels observed in the `.ind` file, so annotation-only labels do not
  silently become target selections.

## CLI

```bash
uv run indoeuropop suggest-aadr-groups \
  --aadr-dir /Users/jmcummings/Claude/Projects/indoeuropop_claude/data/aadr/orig \
  --aadr-groups-out results/aadr-group-suggestions.tsv
```

Loosen the count threshold for exploratory review:

```bash
uv run indoeuropop suggest-aadr-groups \
  --aadr-dir /Users/jmcummings/Claude/Projects/indoeuropop_claude/data/aadr/orig \
  --aadr-groups-out results/aadr-group-suggestions.tsv \
  --min-group-samples 1
```

The output format is the same two-column TSV consumed by
`prepare-aadr-target-inputs`:

```text
region	aadr_group_id
britain	England_BellBeaker
iberia	Iberia_EBA
```

Review and edit the file before using it downstream. Bounding boxes and label
keywords are intentionally conservative heuristics; they cannot replace
archaeological, chronological, and qpAdm-model review.

