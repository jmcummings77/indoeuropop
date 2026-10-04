# IndoEuroPop

## One-minute introduction

Ancient-DNA ancestry patterns alone do not tell us which combination of
migration, disease, fertility, and other pressures produced them. IndoEuroPop
is a Python research package for making those assumptions explicit, simulating
population change, and comparing the resulting ancestry with reviewed targets.

For example, the built-in deterministic demo prints:

```text
final_steppe_ancestry=0.440321
```

That is a **simulated** final ancestry proportion in the demo's Britain region,
not an estimate of historical ancestry.

Two engineering decisions shape the project:

1. **Derive ancestry from population counts.** Births, deaths, and migration
   change the underlying populations before ancestry proportions change.
2. **Keep comparisons auditable.** Targets carry citations and uncertainty;
   explicit holdouts and checksummed manifests make comparisons reviewable.

With Python 3.11+ and `uv` installed, run:

```bash
git clone https://github.com/jmcummings77/indoeuropop.git
cd indoeuropop
uv sync --all-extras --dev
uv run indoeuropop demo
```

The demo needs no external data. See [getting started](docs/getting-started.md)
for plots, provenance exports, and synthetic target comparisons.

## Where to go next

| Goal | Guide |
| --- | --- |
| Understand the model and its current limits | [Architecture and capabilities](docs/architecture.md) |
| Read the historical motivation and research questions | [Research background](docs/research-background.md) |
| Prepare reviewed ancient-DNA observations | [Real-data preparation](docs/getting-started.md#working-with-real-data) |
| Compare simulations and validate held-out targets | [Target comparison workflow](docs/target-comparison-workflow.md) |
| Explore regional models and calibration | [Structural candidates](docs/structural-candidate-workflow.md), [inference](docs/inference-workflow.md), and [SMC validation](docs/structural-smc-validation.md) |
| Develop and test the package | [Development](docs/development.md) |

The [documentation index](docs/README.md) links to command recipes, data
schemas, model components, and research decision records.

This is a research scaffold with exploratory calibration tools. Outputs are
diagnostics, not established historical explanations; real-data workflows
require local AADR files, external qpAdm estimates, and curation review.
