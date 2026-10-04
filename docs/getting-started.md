# Getting started

Run the synthetic examples first to see how a simulation becomes reviewable
outputs. They use committed example inputs and require no ancient-DNA download
or external qpAdm installation. Run every command below from the repository
root.

## Set up and run the demo

Install Python **3.11 or newer** and `uv`, then synchronize the environment:

```bash
uv sync --all-extras --dev
uv run indoeuropop demo
```

The default demo runs a deterministic simulation and prints:

```text
final_steppe_ancestry=0.440321
```

This is the final steppe-related ancestry fraction derived from simulated
population counts. It is a synthetic demonstration, not an estimate of
historical ancestry.

For the complete CLI option list, run `uv run indoeuropop --help`. For the
package layout and contributor checks, see [Development](development.md).

## Save artifacts and compare a target

A single demo run can write a plot, provenance records, and an experiment
manifest:

```bash
uv run indoeuropop demo \
  --plot results/demo-ancestry.png \
  --provenance-csv results/provenance.csv \
  --manifest-json results/demo-manifest.json
```

Each output flag is optional. The plot shows the simulated ancestry trajectory;
the [provenance CSV](output-provenance.md) labels outputs by evidence kind; the
[manifest](experiment-manifests.md) records the run and its artifacts.
Root-level `results/` is ignored by Git.

Compare the same demo with a committed synthetic target file:

```bash
uv run indoeuropop demo --targets examples/target-observations.example.csv
```

This also prints each target's predicted value, supplied value, and z-score.
See the [target schema](target-data-schema.md) for required fields and the
[target-fit guide](target-fit-scoring.md) for scoring conventions.

## Build synthetic targets

Target observations are assembled from sample metadata, curation records, and
sample-level ancestry estimates. Try the complete build with example inputs:

```bash
uv run indoeuropop build-targets \
  --sample-metadata examples/sample-metadata.example.csv \
  --target-curation examples/target-curation.example.csv \
  --ancestry-estimates examples/sample-ancestry-estimates.example.csv \
  --target-output results/built-targets.csv
```

The [target data pipeline](target-data-pipeline.md) explains aggregation,
uncertainty, and validation. The example estimates remain synthetic after
aggregation.

## Sweep parameters and inspect fit

Run a reproducible deterministic sweep from the example TOML configuration:

```bash
uv run indoeuropop sweep \
  --config examples/sweep.example.toml \
  --sweep-runs-csv results/sweep-runs.csv \
  --sensitivity-csv results/sensitivity.csv \
  --manifest-json results/sweep-manifest.json
```

To rank the same sweep against its matching synthetic targets, add target and
fit-output arguments:

```bash
uv run indoeuropop sweep \
  --config examples/sweep.example.toml \
  --targets examples/sweep-targets.example.csv \
  --target-fit-csv results/target-fit.csv \
  --fit-metric root_mean_squared_error
```

For best-run residuals and a trajectory-versus-target plot, use the comparison
workflow:

```bash
uv run indoeuropop compare-targets \
  --config examples/sweep.example.toml \
  --targets examples/sweep-targets.example.csv \
  --target-fit-csv results/target-fit.csv \
  --target-residuals-csv results/target-residuals.csv \
  --plot results/target-comparison.png \
  --manifest-json results/target-comparison-manifest.json \
  --fit-metric root_mean_squared_error
```

These rankings are diagnostics for the configured simulator and supplied
targets. Continue with [sweep workflows](sweep-workflows.md) for the Python API,
[target comparison](target-comparison-workflow.md) for residuals and held-out
checks, and [debugging comparisons](debugging-comparisons.md) when a comparison
fails or gives an unexpected result.

## Working with real data

Real-data workflows require local AADR `.anno`, `.ind`, `.snp`, and `.geno`
files from a reviewed release. The committed
[local source catalog](../curation/local-aadr-v66-data-sources.toml) records the
expected AADR v66.1 files and checksums; it does not bundle the data. Producing
new qpAdm estimates also requires system R, ADMIXTOOLS 2, and its compiled
dependencies. The Python workflow plans that external run and ingests its
output.

Follow the guides in this order:

1. **Materialize and inspect sources.** [Source downloads](source-downloads.md)
   covers `download-sources`, cache reuse, and explicit overwrite behavior.
   [AADR loading](aadr-loading.md) covers `load-aadr` for metadata export.
2. **Review group selections.** [Group suggestions](aadr-group-suggestions.md)
   covers `suggest-aadr-groups`; review its output before using it.
   [Target input preparation](aadr-target-inputs.md) covers
   `prepare-aadr-target-inputs` and the committed western-Europe group seed.
3. **Compute ancestry estimates externally.** [The qpAdm workflow](qpadm-workflow.md)
   covers `plan-qpadm-run`, the R runner, `load-qpadm-estimates`, and
   `filter-target-inputs`. Annotation metadata alone cannot supply ancestry
   estimates.
4. **Build observations with reviewed decisions.** [Real target workflow](real-target-workflow.md)
   covers `build-aadr-qpadm-targets` and build diagnostics.
   [Target decisions](target-decisions.md) covers `apply-target-decisions` when
   applying decisions to already prepared inputs.
5. **Review reruns and accepted targets.** [qpAdm rerun ingestion](qpadm-workflow.md#ingest-rerun-estimates)
   covers `ingest-qpadm-reruns`, its pre/post review, and the accepted target
   file. Use `results/qpadm-rerun/accepted-target-observations.csv` for the
   post-rerun model comparison; the broader build output can include targets
   still awaiting review.
6. **Compare and validate.** [Target comparison](target-comparison-workflow.md#aadr-v66-review-config)
   gives the real-data comparison command and held-out checks. Return to the
   [real target workflow](real-target-workflow.md) for structural review,
   readiness checks, and the later inference workflows.

Keep downloaded data, f2 caches, and generated results in the ignored root-level
`data/` and `results/` directories. A complete build establishes that inputs
can be joined and aggregated; scientific interpretation still depends on
curation, source-model choices, uncertainty, and validation.

[Back to the README](../README.md)
