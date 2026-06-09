# IndoEuroPop Project Plan

## Summary

IndoEuroPop will become a reproducible modeling toolkit for evaluating possible
drivers of observed ancient-DNA ancestry changes during Indo-European language
and population dispersal debates. The first version is a tested scaffold, not a
publication model.

The core design principle is simple: ancestry is derived from modeled population
state. If steppe-related ancestry rises, the model must show which transitions
in counts, survival, fertility, migration, or elite-biased reproduction caused
the rise.

## V1 Model Shape

- Represent each region as source counts, such as `local` and `steppe`.
- Compute ancestry as:

  ```latex
  a_{r,s,t} = \frac{N_{r,s,t}}{\sum_k N_{r,k,t}}
  ```

- Keep time internally as elapsed years while reporting BCE labels for plots and
  summaries.
- Use a deterministic mean-field simulator for transparent debugging.
- Use a seeded tau-leap simulator for inexpensive stochastic smoke tests.
- Treat climate, epidemic, violence, and elite effects as independent model
  components that can later become region-specific.

## Implementation Roadmap

Phase 1: Bootstrap and verify.

- Maintain the Python package with `uv`.
- Keep runtime dependencies limited to NumPy and Matplotlib.
- Enforce Black, Ruff, mypy, pytest, and 100% coverage.
- Provide a CLI demo and plotting path so changes remain easy to inspect.

Phase 2: Scientific input layer.

- Add curated target files for broad regional ancestry trajectories.
- Add explicit citation metadata for every target.
- Keep all target values separate from simulator code.
- Design later AADR or Poseidon ingestion around published metadata fields.
- Compare model output to targets through a validated observation interface,
  never by hard-coding target values inside simulator functions.

Phase 3: Model expansion.

- Replace global parameters with region- and source-specific parameter tables.
- Add migration pulses rather than relying only on smooth migration pressure.
- Add age or generation structure when it changes testable behavior.
- Add sex-biased reproduction only after the neutral source-count model is stable.
- Add epidemic compartments if plague is modeled as transmission rather than as
  an exogenous hazard.

Phase 4: Inference and validation.

- Begin with Latin-hypercube parameter sweeps and sensitivity analysis.
- Use ABC-SMC or Bayesian optimization only once the summary statistics are
  documented.
- Add emulator code only after full simulator outputs are reproducible.
- Revalidate emulator and posterior results against the explicit simulator.

## Visualization And Debugging

Visualization is part of the modeling workflow, not a reporting afterthought.
Every simulator should support quick plots for:

- steppe-source ancestry by region;
- total population by region;
- extinction or runaway-growth checks;
- comparison of deterministic and stochastic runs using the same parameters.

Plots should be generated through package functions so tests can verify that
figures build in headless environments.

## Scientific Guardrails

- Do not encode example posterior values as facts.
- Do not equate archaeological cultures directly with language branches inside
  the model.
- Treat plague as a hypothesis that needs direct evidence, not as a default
  explanation for genetic turnover.
- Keep language-shift variables separate from genetic ancestry when they are
  eventually added.
- Record which outputs are simulated, inferred, or observed.

## Acceptance Criteria

- `uv sync --all-extras --dev` creates a working environment.
- `uv run pytest --cov=indoeuropop --cov-report=term-missing --cov-fail-under=100`
  passes.
- `uv run black --check .`, `uv run ruff check .`, and `uv run mypy src tests`
  pass.
- The CLI demo runs and can write a plot.
- Each code file remains under 400 lines.
