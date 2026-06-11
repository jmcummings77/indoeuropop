# Parameter Sweeps

Phase 4 begins with deterministic parameter sweeps before introducing heavier
inference machinery. Sweeps are meant to answer a modest question first: which
regions of parameter space produce trajectories worth investigating further?

## Latin-Hypercube Sampling

`ParameterRange` names a `SimulationParameters` field and a closed numeric
interval. `latin_hypercube_samples` stratifies each range into equal bins and
shuffles them with a seed.

```python
from indoeuropop import ParameterRange, latin_hypercube_samples

samples = latin_hypercube_samples(
    (
        ParameterRange("migration_rate", 0.0, 0.01),
        ParameterRange("epidemic_mortality_rate", 0.0, 0.02),
    ),
    sample_count=8,
    seed=7,
)
```

## Sweep Execution

`SweepSpec` combines an initial state, base parameters, sampling ranges,
timeline settings, and optional schedules/parameter tables. `run_parameter_sweep`
runs deterministic simulations and returns `SweepRun` records with sampled
values, resolved parameters, and a `TrajectorySummary`.

The summary currently includes initial/final ancestry, ancestry change, slope
per century, minimum total population, final total population, and extinction
status. These are intentionally simple summary statistics that can later feed
ABC-SMC or Bayesian optimization once target statistics are documented.
`trajectory_summary_vector` converts these fields into named, scaled values for
explicit distance comparisons.

## CSV Export

`sweep_runs_to_csv` and `write_sweep_runs_csv` export sampled parameter values
and trajectory summaries to stable rectangular tables. The export is meant for
inspection, debugging, and audit trails; it is not an inference result.
`run_sweep_workflow` can run a sweep, write sweep and sensitivity CSVs, and
emit a manifest with a sweep-collection fingerprint.
`load_sweep_spec` loads the same sweep shape from TOML for CLI and script use.

## Guardrail

Sweep outputs are simulated sensitivity probes, not inferred historical results.
Do not report sampled parameter combinations as posterior estimates.
