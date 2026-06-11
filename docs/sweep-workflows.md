# Sweep Workflows

Sweep workflows provide a small orchestration layer around deterministic
Latin-hypercube sweeps. They run the explicit simulator, compute lightweight
sensitivity diagnostics, and optionally write reviewable artifacts.

The first sweep workflow scaffold supports:

- loading a deterministic sweep from TOML with `load_sweep_spec`;
- running `indoeuropop sweep --config ...` from the CLI;
- running a `SweepSpec` through `run_sweep_workflow`;
- writing sweep-run CSV summaries;
- writing sensitivity-result CSV diagnostics;
- writing an experiment manifest with a sweep-collection fingerprint;
- returning all runs, diagnostics, artifacts, and output paths in a
  `SweepWorkflowResult`.

Example:

```python
from pathlib import Path

from indoeuropop import SweepOutputPaths, run_sweep_workflow

result = run_sweep_workflow(
    spec,
    paths=SweepOutputPaths(
        sweep_runs_csv=Path("results/sweep-runs.csv"),
        sensitivity_csv=Path("results/sensitivity.csv"),
        manifest_json=Path("results/sweep-manifest.json"),
    ),
)
```

This layer is still exploratory. It does not perform ABC-SMC, Bayesian
optimization, posterior ranking, or emulator training.

CLI example:

```bash
uv run indoeuropop sweep \
  --config examples/sweep.example.toml \
  --sweep-runs-csv results/sweep-runs.csv \
  --sensitivity-csv results/sensitivity.csv \
  --manifest-json results/sweep-manifest.json
```
