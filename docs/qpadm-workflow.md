# External qpAdm Workflow

The Python package does not run ADMIXTOOLS inside tests, but the repository now
contains the pieces needed to run qpAdm reproducibly on a local machine with R
and ADMIXTOOLS 2 installed.

## Committed Target Seed

The seed group-selection file is:

```text
curation/aadr-v66-western-europe-qpadm-targets.tsv
```

It contains 38 AADR v66.1 1240K target groups: Britain and central Europe Bell
Beaker or Corded Ware related labels imported from the alternate local
implementation and validated against the local AADR quartet. It is still a
curation artifact, not a publication claim; review labels before using output in
analysis.

## Plan The Run

Generate a manifest and the exact shell command:

```bash
uv run indoeuropop plan-qpadm-run \
  --genotype-prefix data \
  --aadr-groups curation/aadr-v66-western-europe-qpadm-targets.tsv \
  --qpadm-estimates data/qpadm/steppe-estimates.csv \
  --qpadm-f2-dir data/qpadm/f2 \
  --qpadm-manifest-json results/qpadm-run.json
```

The command resolves the AADR `.geno/.snp/.ind` prefix and validates that the
target file and `scripts/run_qpadm.R` exist. It does not run ADMIXTOOLS.

## Plan Reviewed Reruns

After a target build has been reviewed, generate a rerun manifest from the
target curation and reviewed decision CSV:

```bash
uv run indoeuropop plan-qpadm-reruns \
  --target-curation results/real-aadr-comparison/aadr-target-curation.csv \
  --target-decisions curation/aadr-v66-western-europe-target-decisions.csv \
  --qpadm-rerun-manifest-json curation/aadr-v66-western-europe-qpadm-rerun-manifest.json \
  --qpadm-rerun-groups-out curation/aadr-v66-western-europe-qpadm-rerun-targets.tsv
```

The current rerun manifest contains 27 targets grouped as 25 invalid steppe
fractions, one invalid standard-error target, and one replicated group-level
estimate target. The TSV is annotated but still starts with `region` and
`aadr_group_id`, so it can be passed back to `--aadr-groups` for a focused
external rerun.

## Run qpAdm

Install system R, ADMIXTOOLS 2, and its compiled dependencies, then run the
printed command. The runner:

- auto-picks steppe, farmer/EEF, and WHG source labels from the `.ind` file;
- uses deep outgroups present in the release;
- precomputes f2 statistics in the requested cache directory;
- runs one qpAdm model per target group;
- writes one row per individual with `Genetic ID`, `steppe_fraction`, `stderr`,
  and `qpadm_pvalue`.

If the auto-picked sources or outgroups are inappropriate for a release, edit
the override variables at the top of `scripts/run_qpadm.R`.

The runner writes raw qpAdm steppe weights. It does not clamp out-of-range
weights into proportions; invalid weights and unusable standard errors should
be filtered before target aggregation.

## Convert And Build Targets

Convert qpAdm estimates to the package schema:

```bash
uv run indoeuropop load-qpadm-estimates \
  --qpadm-estimates data/qpadm/steppe-estimates.csv \
  --ancestry-estimates-out results/sample-ancestry-estimates.csv \
  --skip-missing-standard-error
```

Prepare the matching AADR sample metadata and target curation:

```bash
uv run indoeuropop prepare-aadr-target-inputs \
  --aadr-dir data \
  --aadr-groups curation/aadr-v66-western-europe-qpadm-targets.tsv \
  --ancestry-method qpadm_steppe \
  --sample-metadata-out results/aadr-target-sample-metadata.csv \
  --target-curation-out results/aadr-target-curation.csv
```

Filter target rows to those with complete, valid sample estimates:

```bash
uv run indoeuropop filter-target-inputs \
  --sample-metadata results/aadr-target-sample-metadata.csv \
  --target-curation results/aadr-target-curation.csv \
  --ancestry-estimates results/sample-ancestry-estimates.csv \
  --sample-metadata-out results/filtered-aadr-target-sample-metadata.csv \
  --target-curation-out results/filtered-aadr-target-curation.csv
```

Aggregate target observations from the filtered inputs:

```bash
uv run indoeuropop build-targets \
  --sample-metadata results/filtered-aadr-target-sample-metadata.csv \
  --target-curation results/filtered-aadr-target-curation.csv \
  --ancestry-estimates results/sample-ancestry-estimates.csv \
  --target-output results/aadr-target-observations.csv
```

Or run the Python-side conversion, filtering, aggregation, and diagnostics as
one workflow:

```bash
uv run indoeuropop build-aadr-qpadm-targets \
  --aadr-dir data \
  --aadr-groups curation/aadr-v66-western-europe-qpadm-targets.tsv \
  --qpadm-estimates data/qpadm/steppe-estimates.csv \
  --sample-metadata-out results/aadr-target-sample-metadata.csv \
  --target-curation-out results/aadr-target-curation.csv \
  --ancestry-estimates-out results/sample-ancestry-estimates.csv \
  --target-output results/aadr-target-observations.csv \
  --target-decisions curation/aadr-v66-western-europe-target-decisions.csv \
  --target-diagnostics-json results/aadr-target-diagnostics.json
```

Keep `data/` and `results/` local. The source genotype release, f2 cache, qpAdm
output, and built target CSVs can be regenerated and are intentionally ignored
by Git.

In the current local smoke run against
`data`, qpAdm
wrote 301 individual rows across 38 target groups. Strict conversion kept 63
sample estimates with in-range steppe weights and usable standard errors. The
reviewed decision file retains 11 aggregate target observations with caveats,
defers 27 targets for qpAdm rerun, and leaves zero target decisions undecided.
Those counts are run evidence, not final scientific validation.
