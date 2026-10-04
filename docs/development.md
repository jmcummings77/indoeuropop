# Development

IndoEuroPop targets Python **3.11 or newer** and uses `uv` for dependencies and
virtual environments. Run commands from the repository root. See
[Getting started](getting-started.md) for the synthetic demo and output examples.

## Install dependencies

```bash
uv sync --all-extras --dev
```

Runtime dependencies are NumPy and Matplotlib. Development tools are Black,
Ruff, strict mypy, and pytest with coverage; their configuration lives in
[pyproject.toml](../pyproject.toml).

## Verify changes

During iteration, run the relevant tests and format/lint checks for the paths
you changed. Before handing off substantial code changes, run the full gate:

```bash
uv run pytest --cov=indoeuropop --cov-report=term-missing --cov-fail-under=100
uv run black --check .
uv run ruff check .
uv run mypy src tests
```

GitHub Actions runs these four checks on Python 3.11 and Ubuntu for pull
requests targeting `main`, pushes to `main`, and manual runs. CI installs the
committed `uv.lock` with `uv sync --locked --all-extras --dev` and enforces 100%
coverage. Public run logs are available from the README's CI badge.

The full suite runs in a fresh checkout using synthetic fixtures and committed
curation metadata, with no private datasets or repository secrets. Artifact
and checksum validation use temporary synthetic files. Validating local
research outputs with `validate-curation-decisions --require-artifacts` still
requires the generated reports, CSVs, and manifests under `results/`; see the
[real target workflow](real-target-workflow.md) for prerequisites and
regeneration commands.

The coverage target is 100% for logic-bearing package code. Preserve that
threshold and test public behavior, validation failures, and artifact
serialization. For documentation-only changes, check links, referenced files,
and runnable examples rather than treating Python coverage as proof of
correct documentation. [AGENTS.md](../AGENTS.md) contains the full repository
standards and agent workflow.

## Package layout

| Path | Responsibility |
| --- | --- |
| `src/indoeuropop/__init__.py` | Public exports and legacy module import aliases. |
| `src/indoeuropop/_api.py` | Top-level `from indoeuropop import ...` export surface. |
| `src/indoeuropop/analysis/` | Diagnostics, fit scoring, validation, summary statistics, and emulators. |
| `src/indoeuropop/data/` | Source catalogs, AADR loading, ancestry estimates, and target building. |
| `src/indoeuropop/models/` | Validated population state types and age/sex structure helpers. |
| `src/indoeuropop/orchestration/` | CLI commands, workflows, sweeps, and inference scaffolds. |
| `src/indoeuropop/reporting/` | Provenance, reproducibility, CSV/report exports, and plots. |
| `src/indoeuropop/simulation/` | Configuration loading, event schedules, epidemic and simulation engines. |
| `tests/` | Pytest coverage of the package's behavior and failure paths. |
| `examples/` | Small synthetic inputs for demos and smoke runs. |
| `curation/` | Reviewed target/model inputs and decision records. |
| `scripts/run_qpadm.R` | External ADMIXTOOLS 2 runner. |
| `docs/` | Guides, schemas, diagnostics, decision records, and the project plan. |

Root-level `data/` and `results/` are ignored for local source files, f2 caches,
and generated artifacts. The package directory `src/indoeuropop/data/` is
tracked normally. Keep real downloaded data and generated results out of
commits unless explicitly promoting a reviewed artifact.

## Change and review conventions

Use a feature branch such as `codex/<short-slug>`, target `main` with the pull
request, and squash merge feature changes. Keep public APIs and compatibility
exports intact when reorganizing modules. Prefer small functions, typed
dataclasses, and explicit validation; keep source modules below 400 lines and
hand-written tests/docs below 1,000 lines.

Changes to curation files are scientific decisions: preserve their rationale,
uncertainty, citations, and review status. Before tuning a simulator to improve
fit, inspect the target inputs and residual evidence. Synthetic examples and
simulation diagnostics must remain visibly distinct from observed or derived
evidence.

Useful references are the [workflow API](workflow-api.md),
[experiment manifests](experiment-manifests.md),
[reproducibility fingerprints](reproducibility-fingerprints.md), and
[project plan](project-plan.md).

[Back to the README](../README.md)
