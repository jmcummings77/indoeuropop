# qpAdm Estimate Conversion

The `load-qpadm-estimates` command converts externally produced qpAdm-style
tables into the project sample-ancestry estimate CSV schema. It does not run
ADMIXTOOLS and does not fit qpAdm models.

For the repository's external ADMIXTOOLS runner and target seed, see
`docs/qpadm-workflow.md`.

## Accepted Columns

The parser accepts CSV or TSV input and tolerates common header spellings:

- Sample ID: `Genetic ID`, `sample_id`, `sample id`, or `id`.
- Steppe fraction: `steppe`, `steppe_fraction`, `steppe fraction`, or
  `steppe weight`.
- Standard error: `stderr`, `std_err`, `standard_error`, `se`, or related
  variants.
- qpAdm p-value: `qpadm_pvalue`, `p_value`, `p-value`, or related variants.

Sample ID and steppe fraction are required. Standard errors are optional during
raw parsing, but target-building inputs need uncertainty. If an input table
lacks row-level standard errors, provide a documented `--default-standard-error`
or add uncertainty values before conversion.

Rows with out-of-range steppe fractions are skipped during parsing. Rows with
missing, non-positive, or greater-than-one standard errors are treated as
missing uncertainty.

## CLI

```bash
uv run indoeuropop load-qpadm-estimates \
  --qpadm-estimates data/qpadm/steppe-estimates.csv \
  --ancestry-estimates-out results/sample-ancestry-estimates.csv \
  --skip-missing-standard-error
```

With a documented fallback uncertainty:

```bash
uv run indoeuropop load-qpadm-estimates \
  --qpadm-estimates data/qpadm/steppe-estimates.csv \
  --ancestry-estimates-out results/sample-ancestry-estimates.csv \
  --default-standard-error 0.05
```

The output can be passed into `build-targets` alongside sample metadata and
target curation rows. When strict conversion skipped rows, first filter target
inputs to rows with complete valid estimates:

```bash
uv run indoeuropop filter-target-inputs \
  --sample-metadata results/aadr-target-sample-metadata.csv \
  --target-curation results/aadr-target-curation.csv \
  --ancestry-estimates results/sample-ancestry-estimates.csv \
  --sample-metadata-out results/filtered-aadr-target-sample-metadata.csv \
  --target-curation-out results/filtered-aadr-target-curation.csv
```

```bash
uv run indoeuropop build-targets \
  --sample-metadata results/filtered-aadr-target-sample-metadata.csv \
  --target-curation results/filtered-aadr-target-curation.csv \
  --ancestry-estimates results/sample-ancestry-estimates.csv \
  --target-output results/aadr-target-observations.csv
```

Duplicate sample IDs keep the first valid occurrence, so sort or deduplicate
input tables before conversion when competing qpAdm models exist.
