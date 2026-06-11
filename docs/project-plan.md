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
  The first workflow API now exposes configured deterministic and tau-leap runs,
  provenance records, experiment manifests, and optional output-bundle writing
  outside the CLI.

Phase 2: Scientific input layer.

- Add curated target files for broad regional ancestry trajectories.
- Add explicit citation metadata for every target.
- Keep all target values separate from simulator code.
- Design later AADR or Poseidon ingestion around published metadata fields.
  The first data-source catalog records planned AADR/Poseidon inputs and local
  target files with citations and optional SHA-256 checksums, without
  downloading or aggregating ancient-DNA metadata.
  The first sample-metadata loader preserves accession IDs, publication fields,
  modeled regions, dates, sex labels, and method notes before any target
  construction.
  The first target-curation metadata layer documents sample selections, time
  windows, ancestry methods, and aggregation methods before any ancestry target
  values are written.
- Compare model output to targets through a validated observation interface,
  never by hard-coding target values inside simulator functions.

Phase 3: Model expansion.

- Replace global parameters with region- and source-specific parameter tables.
  The first implementation supports optional TOML tables for regional shared
  rates and source-specific fertility, mortality, epidemic risk, and
  reproductive multipliers.
- Add migration pulses rather than relying only on smooth migration pressure.
  The first implementation supports steppe-source pulses and climate/epidemic
  forcing windows through validated schedules.
- Add age or generation structure when it changes testable behavior.
  The first age-structure scaffold can represent juvenile/adult/elder counts,
  apply deterministic births/deaths/transitions, and collapse back to the
  source-count state without changing the main simulator yet.
- Add sex-biased reproduction only after the neutral source-count model is stable.
  The first sex-bias scaffold can represent female/male counts, validate
  source-specific reproductive multipliers, estimate expected newborn source
  contributions, and collapse back to the source-count state without changing
  the main simulator yet.
- Add epidemic compartments if plague is modeled as transmission rather than as
  an exogenous hazard.
  The first compartmental scaffold can represent susceptible/infected/recovered
  and deceased counts, project one deterministic region-level mixing step, and
  collapse living counts back to the source-count state without changing the
  main simulator yet.

Phase 4: Inference and validation.

- Begin with Latin-hypercube parameter sweeps and sensitivity analysis.
  The first implementation supports seeded Latin-hypercube sampling over
  `SimulationParameters` fields and compact trajectory summary statistics.
  Lightweight Pearson/Spearman sensitivity diagnostics are available for sweep
  outputs, with CSV exports for sweep summaries and sensitivity results; formal
  Sobol analysis remains a later dependency decision.
- Use ABC-SMC or Bayesian optimization only once the summary statistics are
  documented.
  Target-fit scoring now ranks deterministic sweep runs against curated targets;
  this ranking is exploratory and not a posterior.
  The first summary-statistics scaffold converts trajectory summaries into
  named, scaled vectors and deterministic root-mean-square distances for later
  inference inputs.
- Hold out explicit target subsets before heavier inference.
  The first validation-split scaffold can rank deterministic sweeps on
  calibration targets while retaining fit metrics on held-out validation
  targets.
- Add emulator code only after full simulator outputs are reproducible.
  The first reproducibility scaffold fingerprints simulation results and sweep
  outputs with canonical JSON and SHA-256 digests for future audit trails.
  The first emulator-training scaffold turns fingerprinted sweep runs into
  parameter and summary-statistic matrices without training a surrogate model.
- Bundle reproducible workflow outputs into experiment manifests before adding
  heavier orchestration.
  The first experiment-manifest scaffold records output artifacts, optional
  SHA-256 checksums, and reproducibility fingerprints as derived provenance
  records. The CLI demo can now write a manifest JSON file after generating
  plots and provenance CSV outputs.
- Revalidate emulator and posterior results against the explicit simulator.
  The first emulator-validation scaffold compares future emulator summary
  predictions against explicit simulator summaries by run fingerprint.

## Visualization And Debugging

Visualization is part of the modeling workflow, not a reporting afterthought.
Every simulator should support quick plots for:

- steppe-source ancestry by region;
- total population by region;
- extinction or runaway-growth checks;
  The first diagnostics helper reports extinction and runaway-growth warnings,
  plus time and label consistency errors.
- comparison of deterministic and stochastic runs using the same parameters.
  The first comparison helper reports pointwise ancestry differences and can
  generate overlay plots for deterministic versus seeded tau-leap runs.

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
  The first provenance helper labels simulated summaries, published or
  synthetic targets, and derived fit scores; inferred records are reserved for a
  later inference phase.
- Write simple CSV reporting artifacts from provenance and diagnostics before
  introducing richer report formats. The CLI demo can now write a provenance
  CSV containing simulated summaries, diagnostics, and optional target-fit
  records.

## Acceptance Criteria

- `uv sync --all-extras --dev` creates a working environment.
- `uv run pytest --cov=indoeuropop --cov-report=term-missing --cov-fail-under=100`
  passes.
- `uv run black --check .`, `uv run ruff check .`, and `uv run mypy src tests`
  pass.
- The CLI demo runs and can write a plot.
- Each code file remains under 400 lines.
