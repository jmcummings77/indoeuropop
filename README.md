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

## Package Layout

```text
src/indoeuropop/
  cli.py             argparse entry point for smoke/demo runs
  config.py          simple TOML config loading
  debugging.py       trajectory comparison helpers for simulation debugging
  diagnostics.py     sanity checks for simulation output quality
  models.py          typed state, parameter, and result dataclasses
  provenance.py      explicit simulated/observed/derived output records
  simulation.py      deterministic and tau-leap simulation skeletons
  targets.py         target observation CSV loading and comparison helpers
  visualization.py   Matplotlib helpers for outputs and debugging
docs/
  project-plan.md    implementation roadmap and scientific guardrails
  target-data-schema.md
examples/
  target-observations.example.csv
tests/
  test_*.py          100% coverage tests for logic-bearing modules
```

## Current Capabilities

- Construct validated population states with region/source counts.
- Derive ancestry proportions from source counts.
- Run a small deterministic mean-field scenario.
- Run a seeded tau-leap stochastic scenario for smoke testing.
- Load the same inputs from TOML.
- Layer time-bounded migration pulses and climate/epidemic forcing windows over
  base parameters.
- Override shared region rates and source-specific rates through parameter
  tables.
- Run seeded Latin-hypercube parameter sweeps and summarize trajectories.
- Analyze sweep sensitivity with lightweight correlation diagnostics.
- Score simulations and deterministic sweeps against target observations.
- Compare deterministic and tau-leap ancestry trajectories for debugging.
- Validate simulation outputs for time-order, label, extinction, and growth
  diagnostics.
- Label output values as simulated, observed, synthetic, derived, or future
  inferred records for reporting.
- Load synthetic or published target-observation CSV files.
- Compare simulated ancestry trajectories to target observations.
- Plot ancestry and population-total trajectories without requiring a display.

## Not Yet Included

- Ancient-DNA genotype or metadata ingestion.
- AADR, Poseidon, SLiM, msprime, ABC-SMC, or emulator integration.
- Regionally calibrated parameter priors.
- Scholarly claims about fitted causal mechanisms.

Those pieces belong in later phases after the state model, tests, and
documentation are stable.
