# IndoEuroPop

IndoEuroPop is a research-engineering scaffold for mechanistic models of
Late Neolithic and Early Bronze Age population dynamics in western Eurasia. The
initial focus is on building reproducible code that can later compare migration,
epidemic, climate, violence, fertility, subsistence, and elite-reproduction
hypotheses against ancient-DNA observations.

This repository does **not** yet contain a fitted scientific model,
ancient-DNA genotype processing, or inferred historical results. The first
milestone is a small, tested Python package that makes the modeling assumptions
explicit and easy to replace.

## Modeling Philosophy

The project treats steppe-related ancestry as an observable derived from modeled
population counts rather than as a value that is manually adjusted. This keeps
the code honest: births, deaths, migration, and epidemic stress must change the
underlying state before ancestry changes.

The scaffold is intentionally cautious about archaeology and genetics. Major
steppe-related ancestry shifts in Corded Ware and Bell Beaker contexts are a
starting motivation, but the package does not assume that any one mechanism
explains all regions. Plague, elite dominance, climate stress, and violence are
implemented as model components to test, not conclusions to smuggle in.

## Quick Start

```bash
uv sync --all-extras --dev
uv run indoeuropop demo
uv run indoeuropop demo --plot results/demo-ancestry.png
uv run indoeuropop demo --provenance-csv results/provenance.csv
uv run indoeuropop demo --manifest-json results/demo-manifest.json
```

Run the full verification suite:

```bash
uv run pytest --cov=indoeuropop --cov-report=term-missing --cov-fail-under=100
uv run black --check .
uv run ruff check .
uv run mypy src tests
```

Compare a demo run against the synthetic target example:

```bash
uv run indoeuropop demo --targets examples/target-observations.example.csv
```

Download or materialize cataloged source files:

```bash
uv run indoeuropop download-sources \
  --data-sources examples/data-sources.example.toml \
  --output-dir data/raw \
  --download-manifest-csv results/downloads.csv
```

The downloader checks root `/data/` first for an artifact with the expected
filename. Existing files are reused by default and are not replaced unless
`--overwrite` is supplied explicitly.

Export local AADR annotations as sample metadata:

```bash
uv run indoeuropop load-aadr \
  --aadr-dir data \
  --sample-metadata-out data/aadr-sample-metadata.csv
```

Suggest reviewable AADR group selections from local annotation geography,
chronology, and group labels:

```bash
uv run indoeuropop suggest-aadr-groups \
  --aadr-dir data \
  --aadr-groups-out results/aadr-group-suggestions.tsv
```

Prepare real AADR sample metadata and curation inputs for later target
building:

```bash
uv run indoeuropop prepare-aadr-target-inputs \
  --aadr-dir data \
  --aadr-groups results/aadr-group-suggestions.tsv \
  --sample-metadata-out results/aadr-target-sample-metadata.csv \
  --target-curation-out results/aadr-target-curation.csv
```

Plan an external ADMIXTOOLS qpAdm run from the committed western-Europe target
seed:

```bash
uv run indoeuropop plan-qpadm-run \
  --genotype-prefix data \
  --aadr-groups curation/aadr-v66-western-europe-qpadm-targets.tsv \
  --qpadm-estimates data/qpadm/steppe-estimates.csv \
  --qpadm-f2-dir data/qpadm/f2 \
  --qpadm-manifest-json results/qpadm-run.json
```

Convert externally computed qpAdm-style steppe estimates into sample-level
ancestry estimates:

```bash
uv run indoeuropop load-qpadm-estimates \
  --qpadm-estimates data/qpadm/steppe-estimates.csv \
  --ancestry-estimates-out results/sample-ancestry-estimates.csv \
  --skip-missing-standard-error
```

Filter curation rows to those with complete valid estimates:

```bash
uv run indoeuropop filter-target-inputs \
  --sample-metadata results/aadr-target-sample-metadata.csv \
  --target-curation results/aadr-target-curation.csv \
  --ancestry-estimates results/sample-ancestry-estimates.csv \
  --sample-metadata-out results/filtered-aadr-target-sample-metadata.csv \
  --target-curation-out results/filtered-aadr-target-curation.csv
```

Build the reviewed real AADR/qpAdm target observations and diagnostics in one
workflow:

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

After running the focused external qpAdm rerun, merge the rerun table with the
baseline estimates and write a pre/post target-availability review:

```bash
uv run indoeuropop ingest-qpadm-reruns \
  --aadr-dir data \
  --aadr-groups curation/aadr-v66-western-europe-qpadm-targets.tsv \
  --qpadm-estimates data/qpadm/steppe-estimates.csv \
  --qpadm-rerun-estimates data/qpadm/steppe-rerun-estimates.csv \
  --sample-metadata-out results/qpadm-rerun/aadr-target-sample-metadata.csv \
  --target-curation-out results/qpadm-rerun/aadr-target-curation.csv \
  --ancestry-estimates-out results/qpadm-rerun/merged-sample-ancestry-estimates.csv \
  --target-output results/qpadm-rerun/aadr-target-observations.csv \
  --baseline-target-output results/qpadm-rerun/baseline-target-observations.csv \
  --accepted-target-output results/qpadm-rerun/accepted-target-observations.csv \
  --qpadm-rerun-comparison-csv results/qpadm-rerun/qpadm-rerun-comparison.csv \
  --qpadm-rerun-report-md results/qpadm-rerun/qpadm-rerun-report.md \
  --target-decisions curation/aadr-v66-western-europe-target-decisions.csv \
  --target-diagnostics-json results/qpadm-rerun/qpadm-rerun-diagnostics.json
```

Use `results/qpadm-rerun/accepted-target-observations.csv` for model
comparison; the broader `aadr-target-observations.csv` is a buildability review
surface that can still include targets awaiting a reviewed decision.

Apply reviewed target decisions to already prepared target inputs:

```bash
uv run indoeuropop apply-target-decisions \
  --sample-metadata results/real-aadr-comparison/aadr-target-sample-metadata.csv \
  --target-curation results/real-aadr-comparison/aadr-target-curation.csv \
  --target-decisions curation/aadr-v66-western-europe-target-decisions.csv \
  --sample-metadata-out results/real-aadr-comparison/decision-filtered-sample-metadata.csv \
  --target-curation-out results/real-aadr-comparison/decision-filtered-target-curation.csv
```

Build target observations from curated sample-level inputs:

```bash
uv run indoeuropop build-targets \
  --sample-metadata examples/sample-metadata.example.csv \
  --target-curation examples/target-curation.example.csv \
  --ancestry-estimates examples/sample-ancestry-estimates.example.csv \
  --target-output results/built-targets.csv
```

Run a deterministic sweep from TOML:

```bash
uv run indoeuropop sweep \
  --config examples/sweep.example.toml \
  --sweep-runs-csv results/sweep-runs.csv \
  --sensitivity-csv results/sensitivity.csv \
  --manifest-json results/sweep-manifest.json
```

Rank deterministic sweep runs against a target CSV:

```bash
uv run indoeuropop sweep \
  --config examples/sweep.example.toml \
  --targets path/to/matching-targets.csv \
  --target-fit-csv results/target-fit.csv \
  --fit-metric root_mean_squared_error
```

Run a first-class target comparison workflow with best-run residuals and a
diagnostic overlay plot:

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

Compare the committed real-data review config against regenerated AADR/qpAdm
targets:

```bash
uv run indoeuropop compare-targets \
  --config curation/aadr-v66-western-europe-comparison.toml \
  --targets results/real-aadr-comparison/aadr-target-observations.csv \
  --target-fit-csv results/real-aadr-comparison/target-fit.csv \
  --target-residuals-csv results/real-aadr-comparison/target-residuals.csv \
  --plot results/real-aadr-comparison/target-comparison.png \
  --manifest-json results/real-aadr-comparison/target-comparison-manifest.json \
  --fit-metric root_mean_squared_error
```

Run held-out validation on accepted post-rerun targets:

```bash
uv run indoeuropop validate-targets \
  --config curation/aadr-v66-western-europe-comparison.toml \
  --targets results/qpadm-rerun/accepted-target-observations.csv \
  --validation-fit-csv results/qpadm-rerun/accepted-validation-fit.csv \
  --validation-report-md results/qpadm-rerun/accepted-validation-report.md \
  --manifest-json results/qpadm-rerun/accepted-validation-manifest.json \
  --fit-metric root_mean_squared_error
```

For a more granular leave-one-target-group-out diagnostic, use the target-note
metadata key written by the AADR/qpAdm target builder:

```bash
uv run indoeuropop validate-targets \
  --config curation/aadr-v66-western-europe-comparison.toml \
  --targets results/qpadm-rerun/accepted-target-observations.csv \
  --validation-field note:requested_group_id \
  --validation-fit-csv results/qpadm-rerun/accepted-group-validation-fit.csv \
  --validation-report-md results/qpadm-rerun/accepted-group-validation-report.md \
  --manifest-json results/qpadm-rerun/accepted-group-validation-manifest.json \
  --fit-metric root_mean_squared_error
```

In the current local accepted-target validation, both leave-one-region-out folds
selected run `9`. Holding out Britain gave validation RMSE `0.122664`; holding
out central Europe gave validation RMSE `0.305043`. Leave-one-requested-group
validation again selected run `9` for every fold, with the largest validation
RMSE on `Germany_Tiefbrunn_CordedWare-1` (`0.630451`).

Project target-note groups into explicit child model regions when a broad
region is too coarse for the validation question:

```bash
uv run indoeuropop structure-target-regions \
  --config curation/aadr-v66-western-europe-comparison.toml \
  --targets results/qpadm-rerun/accepted-target-observations.csv \
  --structure-region central_europe \
  --structured-targets-out results/qpadm-rerun/central-europe-structured-targets.csv \
  --structured-config-out results/qpadm-rerun/central-europe-structured-comparison.toml
```

The generated config splits selected parent initial counts evenly across the
target-aligned child regions and copies parent pulses and parameter overrides
to those children. That is an infrastructure scaffold for reviewing structure;
it is not evidence that those child regions have distinct historical dynamics
until child-specific priors or overrides are curated.

Apply reviewed child-region overrides before rerunning comparison or
validation:

```bash
uv run indoeuropop apply-child-region-overrides \
  --config results/qpadm-rerun/central-europe-structured-comparison.toml \
  --child-region-overrides curation/aadr-v66-central-europe-child-overrides.toml \
  --overridden-config-out results/qpadm-rerun/central-europe-curated-comparison.toml
```

Override TOML files can replace a child region's starting counts, migration
pulses, and parameter tables:

```toml
[counts.central_europe__germany_tiefbrunn_cordedware_1]
local = 760
steppe = 42

[[migration_pulses]]
region = "central_europe__germany_tiefbrunn_cordedware_1"
start_bce = 2980
end_bce = 2450
annual_rate = 0.00014

[region_parameters.central_europe__germany_tiefbrunn_cordedware_1]
migration_rate = 0.0002

[source_parameters.central_europe__germany_tiefbrunn_cordedware_1.steppe]
reproductive_multiplier = 1.18
```

Migration pulses in the override file replace inherited pulses for the same
regions by default. Add `[options] replace_migration_pulses = false` to append
them instead.

The checked-in central-Europe override is a review candidate, not a final
historical prior. Its metadata sets Britain as the protected holdout and
records an explicit protected-fold tolerance of `0.03` RMSE for the current
validation gate.

Rerun validation after applying the curated override:

```bash
uv run indoeuropop validate-targets \
  --config results/qpadm-rerun/central-europe-curated-comparison.toml \
  --targets results/qpadm-rerun/central-europe-structured-targets.csv \
  --validation-field region \
  --validation-fit-csv results/qpadm-rerun/central-europe-curated-validation-fit.csv \
  --validation-report-md results/qpadm-rerun/central-europe-curated-validation-report.md \
  --manifest-json results/qpadm-rerun/central-europe-curated-validation-manifest.json \
  --fit-metric root_mean_squared_error
```

Review whether an override improved priority folds without degrading protected
folds beyond the committed tolerance:

```bash
uv run indoeuropop review-override-deltas \
  --baseline-validation-fit-csv results/qpadm-rerun/central-europe-structured-validation-fit.csv \
  --override-validation-fit-csv results/qpadm-rerun/central-europe-curated-validation-fit.csv \
  --priority-validation-value central_europe__germany_tiefbrunn_cordedware_1 \
  --priority-validation-value central_europe__germany_manchingoberstimm_bellbeaker \
  --protected-validation-value britain \
  --refinement-tolerance 0.03 \
  --override-delta-csv results/qpadm-rerun/central-europe-curated-override-delta.csv \
  --override-delta-report-md results/qpadm-rerun/central-europe-curated-override-delta.md \
  --manifest-json results/qpadm-rerun/central-europe-curated-override-delta-manifest.json \
  --fit-metric root_mean_squared_error
```

Compare validation-guided narrowed and expanded parameter ranges against the
current grid:

```bash
uv run indoeuropop refine-target-parameters \
  --config curation/aadr-v66-western-europe-comparison.toml \
  --targets results/qpadm-rerun/accepted-target-observations.csv \
  --priority-validation-value central_europe \
  --protected-validation-value britain \
  --refinement-summary-csv results/qpadm-rerun/accepted-region-refinement-summary.csv \
  --refinement-ranges-csv results/qpadm-rerun/accepted-region-refinement-ranges.csv \
  --refinement-report-md results/qpadm-rerun/accepted-region-refinement-report.md \
  --manifest-json results/qpadm-rerun/accepted-region-refinement-manifest.json \
  --fit-metric root_mean_squared_error
```

For the current accepted targets, the narrowed grid improves central Europe by
RMSE `0.010448` but degrades Britain by `0.019410`; the expanded grid improves
central Europe by `0.007753` but degrades Britain by `0.061346`. A
leave-one-requested-group refinement focused on
`Germany_Tiefbrunn_CordedWare-1` reduces that group's RMSE by `0.031027` in the
expanded grid, but degrades the protected Britain groups by up to `0.168369`.

Review the best-run residuals:

```bash
uv run indoeuropop review-target-residuals \
  --target-residuals results/real-aadr-comparison/target-residuals.csv \
  --target-diagnostics-json results/real-aadr-comparison/aadr-target-diagnostics.json \
  --target-review-md results/real-aadr-comparison/target-residual-review.md
```

Audit the top residual's curation and qpAdm estimate evidence:

```bash
uv run indoeuropop audit-target-curation \
  --target-residuals results/real-aadr-comparison/target-residuals.csv \
  --target-curation results/real-aadr-comparison/aadr-target-curation.csv \
  --sample-metadata results/real-aadr-comparison/aadr-target-sample-metadata.csv \
  --ancestry-estimates results/real-aadr-comparison/sample-ancestry-estimates.csv \
  --target-audit-md results/real-aadr-comparison/stkr-straubing-curation-audit.md
```

## Package Layout

```text
src/indoeuropop/
  __init__.py        public exports and legacy module import aliases
  _api.py            top-level `from indoeuropop import ...` export surface
  analysis/          diagnostics, fitting, validation, summaries, emulators
  data/              AADR loading, source catalogs, estimates, target building
  models/            shared state types plus age and sex structure helpers
  orchestration/     CLI commands, experiment manifests, sweeps, workflows
  reporting/         provenance, reproducibility, CSV exports, plots
  simulation/        config loading, event schedules, epidemic and run engines
docs/
  aadr-group-suggestions.md
  aadr-loading.md
  aadr-target-inputs.md
  alternative-implementation-evaluation.md
  experiment-manifests.md
  project-plan.md    implementation roadmap and scientific guardrails
  qpadm-estimates.md
  qpadm-workflow.md
  real-target-workflow.md
  source-downloads.md
  sweep-workflows.md
  target-comparison-workflow.md
  target-data-schema.md
  target-residual-review.md
  workflow-api.md
examples/
  sample-ancestry-estimates.example.csv
  sweep.example.toml
  sweep-targets.example.csv
  target-observations.example.csv
curation/
  aadr-v66-western-europe-comparison.toml
  aadr-v66-western-europe-qpadm-targets.tsv
scripts/
  run_qpadm.R        external ADMIXTOOLS 2 runner
tests/
  test_*.py          100% coverage tests for logic-bearing modules
```

Root-level `/data/` and `/results/` are ignored for local raw data, f2 caches,
and generated artifacts. The package code under `src/indoeuropop/data/` is
tracked normally.

## Current Capabilities

- Construct validated population states with region/source counts.
- Derive ancestry proportions from source counts.
- Represent and project age-structured counts, then collapse them back to
  source-count states for existing diagnostics and plots.
- Represent sex-structured counts and estimate expected newborn source
  contributions under explicit sex-specific reproductive weights.
- Represent susceptible, infected, recovered, and deceased counts for explicit
  epidemic transmission experiments.
- Run a small deterministic mean-field scenario.
- Run a seeded tau-leap stochastic scenario for smoke testing.
- Load the same inputs from TOML.
- Run configured deterministic or tau-leap scenarios through reusable workflow
  helpers outside the CLI.
- Materialize optional plot, provenance CSV, and manifest JSON outputs through
  reusable workflow helpers.
- Layer time-bounded migration pulses and climate/epidemic forcing windows over
  base parameters.
- Override shared region rates and source-specific rates through parameter
  tables.
- Run seeded Latin-hypercube parameter sweeps and summarize trajectories.
- Export sweep summaries and sensitivity diagnostics to stable CSV tables.
- Load deterministic sweep specifications from TOML and run them from the CLI.
- Run deterministic sweep workflows that can write sweep CSVs, sensitivity CSVs,
  target-fit CSVs, and manifest JSON files.
- Convert trajectory summaries into named, scaled summary-statistic vectors.
- Analyze sweep sensitivity with lightweight correlation diagnostics.
- Score simulations and deterministic sweeps against target observations.
- Run a target-comparison workflow that writes ranked fits, best-run residuals,
  overlay plots, and a checksummed manifest.
- Run held-out target-validation workflows by region or target-note metadata
  key, with ranked validation rows, Markdown summaries, and manifests.
- Compare baseline, narrowed, and expanded validation-guided parameter grids
  while tracking priority improvements and protected holdout degradation.
- Generate Markdown target-residual review reports from comparison artifacts.
- Split targets into calibration and validation sets for held-out fit checks.
- Compare deterministic and tau-leap ancestry trajectories for debugging.
- Validate simulation outputs for time-order, label, extinction, and growth
  diagnostics.
- Label output values as simulated, observed, synthetic, derived, or future
  inferred records for reporting.
- Export provenance and diagnostic records to rectangular CSV tables.
- Fingerprint simulation results and sweep outputs with canonical SHA-256
  digests.
- Bundle run artifacts and fingerprints into experiment manifests that can be
  converted to provenance records.
- Prepare sweep runs as parameter and summary matrices for future emulator
  experiments.
- Compare future emulator predictions against explicit simulator summaries.
- Write CLI provenance reports for demo simulations.
- Write CLI experiment manifests with artifact checksums and simulation
  fingerprints.
- Load synthetic or published target-observation CSV files.
- Build target-observation CSVs from sample metadata, curation records, and
  sample ancestry estimates.
- Filter target-pipeline inputs to rows with complete valid ancestry estimates
  before aggregation.
- Register local and planned external data sources with citations and optional
  SHA-256 checksums.
- Download or copy cataloged source files into a raw-data cache with optional
  checksum verification and a manifest CSV.
- Load local AADR annotation files into the project sample metadata schema.
- Suggest reviewable AADR group-selection files from local annotation
  coordinates, dates, and group labels.
- Prepare AADR group selections as modeled-region sample metadata and
  target-curation inputs for later ancestry-estimate aggregation.
- Load synthetic or published sample metadata rows without aggregating them into
  ancestry targets.
- Load sample-level ancestry estimates before target aggregation.
- Convert externally computed qpAdm-style estimate tables into the sample
  ancestry estimate schema.
- Plan external ADMIXTOOLS qpAdm runs with resolved genotype prefixes, a
  committed target seed, and an auditable JSON manifest.
- Plan qpAdm reruns from reviewed target decisions, grouped by failure reason
  with JSON and annotated AADR group-selection TSV outputs.
- Merge external qpAdm rerun outputs with baseline estimates and compare
  target availability before updating reviewed target decisions.
- Run an exploratory multi-region comparison sweep against retained AADR v66
  western-Europe qpAdm target observations.
- Audit residual outliers against curation rows, sample metadata, and qpAdm
  estimate evidence before changing simulator parameters.
- Apply reviewed target-decision files to defer excluded, split, or rerun-pending
  targets from observation builds without deleting their curation evidence.
- Document target curation windows, sample selections, and methods before
  creating target observations.
- Compare simulated ancestry trajectories to target observations.
- Plot ancestry and population-total trajectories without requiring a display.

## Not Yet Included

- Automated ancient-DNA genotype processing.
- Poseidon, SLiM, msprime, ABC-SMC, or predictive emulator integration.
- Regionally calibrated parameter priors.
- Scholarly claims about fitted causal mechanisms.

Those pieces belong in later phases after the state model, tests, and
documentation are stable.
