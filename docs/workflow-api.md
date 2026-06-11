# Workflow API

The workflow API keeps configured simulation execution reusable outside the CLI.
It is a thin orchestration layer around existing model, provenance, and
manifest helpers, not a new inference engine.

The first workflow scaffold supports:

- deterministic runs from a `SimulationConfig`;
- seeded tau-leap runs from the same config;
- final ancestry access through `SimulationRun`;
- simulation-result fingerprints;
- provenance records for summaries, diagnostics, optional targets, and fit
  metrics;
- experiment manifests for programmatic or CLI runs;
- one-call materialization of optional plot, provenance CSV, and manifest JSON
  outputs.

Example:

```python
from pathlib import Path

from indoeuropop import (
    default_config,
    SimulationOutputPaths,
    run_configured_simulation,
    simulation_experiment_manifest,
    simulation_provenance_records,
    write_simulation_outputs,
)

run = run_configured_simulation(default_config(), simulator="deterministic")
records = simulation_provenance_records(run, source="steppe", region="britain")
manifest = simulation_experiment_manifest(
    run,
    source="steppe",
    region="britain",
    command="notebook-smoke-run",
)
bundle = write_simulation_outputs(
    run,
    source="steppe",
    region="britain",
    paths=SimulationOutputPaths(
        plot=Path("results/ancestry.png"),
        provenance_csv=Path("results/provenance.csv"),
        manifest_json=Path("results/manifest.json"),
    ),
)
```

The workflow layer should stay small. Future orchestration for ABC-SMC,
Bayesian optimization, SLiM/msprime, or emulator training should call these
helpers rather than embedding output provenance or manifest logic in notebooks
or ad hoc scripts.
