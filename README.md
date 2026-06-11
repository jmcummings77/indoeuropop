# IndoEuroPop

IndoEuroPop is a research-engineering scaffold for mechanistic models of
Late Neolithic and Early Bronze Age population dynamics in western Eurasia. The
initial focus is on building reproducible code that can later compare migration,
epidemic, climate, violence, fertility, subsistence, and elite-reproduction
hypotheses against ancient-DNA observations.

This repository does **not** yet contain a fitted scientific model, ancient-DNA
data ingestion, or inferred historical results. The first milestone is a small,
tested Python package that makes the modeling assumptions explicit and easy to
replace.

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

Export local AADR annotations as sample metadata:

```bash
uv run indoeuropop load-aadr \
  --aadr-dir /Users/jmcummings/Claude/Projects/indoeuropop_claude/data/aadr/orig \
  --sample-metadata-out data/aadr-sample-metadata.csv
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

## Package Layout

```text
src/indoeuropop/
  aadr.py            local AADR annotation loading and metadata export
  age_structure.py   deterministic age-class scaffold for model expansion
  ancestry_estimates.py sample ancestry estimates before target aggregation
  cli.py             argparse entry point for smoke/demo runs
  config.py          simple TOML config loading
  data_sources.py    metadata catalog for target and future sample inputs
  debugging.py       trajectory comparison helpers for simulation debugging
  diagnostics.py     sanity checks for simulation output quality
  emulator_training.py matrix-ready sweep outputs for future emulators
  emulator_validation.py compare future emulator predictions to simulator runs
  epidemics.py       compartmental epidemic scaffold
  experiments.py     experiment manifests for reproducible output bundles
  models.py          typed state, parameter, and result dataclasses
  provenance.py      explicit simulated/observed/derived output records
  reporting.py       CSV export helpers for provenance and diagnostics
  reproducibility.py canonical output fingerprints for audit trails
  sample_metadata.py typed sample metadata staging for later ingestion
  simulation.py      deterministic and tau-leap simulation skeletons
  source_downloader.py catalog-driven raw source downloads
  sex_bias.py        sex-structured reproduction scaffold
  summary_statistics.py named summary vectors for future inference inputs
  sweep_reporting.py CSV exports for sweep and sensitivity diagnostics
  sweep_workflows.py reusable deterministic sweep output workflow helpers
  target_curation.py target derivation metadata before ancestry outputs
  target_pipeline.py build target rows from curated sample-level inputs
  targets.py         target observation CSV loading and comparison helpers
  validation.py      calibration and validation target-split helpers
  visualization.py   Matplotlib helpers for outputs and debugging
  workflows.py       reusable configured-run and reporting assembly helpers
docs/
  aadr-loading.md
  experiment-manifests.md
  project-plan.md    implementation roadmap and scientific guardrails
  source-downloads.md
  sweep-workflows.md
  target-data-schema.md
  workflow-api.md
examples/
  sample-ancestry-estimates.example.csv
  sweep.example.toml
  target-observations.example.csv
tests/
  test_*.py          100% coverage tests for logic-bearing modules
```

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
- Register local and planned external data sources with citations and optional
  SHA-256 checksums.
- Download or copy cataloged source files into a raw-data cache with optional
  checksum verification and a manifest CSV.
- Load local AADR annotation files into the project sample metadata schema.
- Load synthetic or published sample metadata rows without aggregating them into
  ancestry targets.
- Load sample-level ancestry estimates before target aggregation.
- Document target curation windows, sample selections, and methods before
  creating target observations.
- Compare simulated ancestry trajectories to target observations.
- Plot ancestry and population-total trajectories without requiring a display.

## Not Yet Included

- Automated ancient-DNA genotype or external metadata ingestion.
- AADR, Poseidon, SLiM, msprime, ABC-SMC, or predictive emulator integration.
- Regionally calibrated parameter priors.
- Scholarly claims about fitted causal mechanisms.

Those pieces belong in later phases after the state model, tests, and
documentation are stable.
