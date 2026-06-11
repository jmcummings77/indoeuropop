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
  --target-diagnostics-json results/aadr-target-diagnostics.json
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
- Run an exploratory multi-region comparison sweep against retained AADR v66
  western-Europe qpAdm target observations.
- Audit residual outliers against curation rows, sample metadata, and qpAdm
  estimate evidence before changing simulator parameters.
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
