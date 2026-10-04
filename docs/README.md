# Documentation

Start with the [one-minute introduction](../README.md#one-minute-introduction),
then choose a guide for the task at hand. Commands run from the repository
root; paths under `data/` and `results/` refer to local, Git-ignored files.

## Guides

| I want to… | Read |
| --- | --- |
| Run a simulation and inspect its outputs | [Getting started](getting-started.md) |
| Understand the model, engineering decisions, and current limits | [Architecture and capabilities](architecture.md) |
| Understand the research motivation | [Research background](research-background.md) |
| Prepare ancient-DNA target evidence | [External qpAdm workflow](qpadm-workflow.md), then [real target workflow](real-target-workflow.md) |
| Compare runs, hold out targets, or refine parameter ranges | [Target comparison workflow](target-comparison-workflow.md) |
| Evaluate regional structure and child-region overrides | [Structural candidate workflow](structural-candidate-workflow.md) |
| Run exploratory rejection or sequential calibration | [Inference workflow](inference-workflow.md) |
| Check structural candidates across folds and robustness gates | [Structural SMC validation](structural-smc-validation.md) |
| Change the code and run verification | [Development](development.md) |

The synthetic examples need no external data. The real-data route requires
local Allen Ancient DNA Resource (AADR) files, externally computed qpAdm
estimates, and reviewed target decisions. Start with the
[ordered preparation steps](getting-started.md#working-with-real-data) before
running commands that consume generated `results/` files.

## Model reference

- [Age structure](age-structure.md), [sex-biased reproduction](sex-biased-reproduction.md),
  and [epidemic compartments](epidemic-compartments.md) describe the population
  state helpers and their limits.
- [Event schedules](event-schedules.md) and [parameter tables](parameter-tables.md)
  describe migration pulses, forcing windows, and region/source overrides.
- [Workflow API](workflow-api.md) covers reusable Python execution and output
  helpers; [debugging comparisons](debugging-comparisons.md) compares
  deterministic and stochastic trajectories.

## Data and curation reference

| Stage | Reference |
| --- | --- |
| Catalog and acquire inputs | [Data source catalog](data-source-catalog.md), [source downloads](source-downloads.md) |
| Load and select AADR samples | [AADR loading](aadr-loading.md), [group suggestions](aadr-group-suggestions.md), [target input preparation](aadr-target-inputs.md) |
| Describe sample-level evidence | [Sample metadata schema](sample-metadata-schema.md), [sample ancestry estimates](sample-ancestry-estimates.md), [qpAdm estimate conversion](qpadm-estimates.md) |
| Curate and build observations | [Target curation](target-curation.md), [target decisions](target-decisions.md), [target data pipeline](target-data-pipeline.md), [target data schema](target-data-schema.md) |
| Investigate a poor fit | [Target residual review](target-residual-review.md), [target curation audit](target-curation-audit.md) |

A buildable observation is not automatically accepted evidence for comparison.
The [real target workflow](real-target-workflow.md) explains the accepted-target
file and the review boundaries.

## Analysis and reporting reference

- [Parameter sweeps](parameter-sweeps.md) and [sweep workflows](sweep-workflows.md)
  cover sampling, execution, and CLI exports.
- [Target fit scoring](target-fit-scoring.md), [validation splits](validation-splits.md),
  [summary statistics](summary-statistics.md), and
  [sensitivity analysis](sensitivity-analysis.md) describe diagnostics and metrics.
- [Simulation diagnostics](simulation-diagnostics.md) checks trajectory integrity.
- [Output provenance](output-provenance.md), [reporting exports](reporting-exports.md),
  [reproducibility fingerprints](reproducibility-fingerprints.md), and
  [experiment manifests](experiment-manifests.md) explain how artifacts are labeled
  and traced back to runs.
- [Emulator training data](emulator-training.md) and
  [emulator validation](emulator-validation.md) describe the preparatory interfaces;
  a predictive emulator is not yet integrated.

## Research plans and decision records

- [Project plan](project-plan.md): modeling scope, staged roadmap, and scientific
  guardrails; use [architecture and capabilities](architecture.md) for current
  implementation boundaries.
- [Alternative implementation evaluation](alternative-implementation-evaluation.md):
  prior design comparisons and deferred integrations.
- [Central Europe child-override decision](central-europe-override-decision.md):
  recorded evidence and follow-up rules for one reviewed candidate.
- [Structural SMC caveat disposition decision](structural-smc-caveat-disposition-decision.md):
  reviewed caveats, frozen evidence, and commands to rebuild the decision.

Numerical findings in workflow and decision documents describe recorded local
runs. Regenerate their artifacts and review the associated uncertainty before
using them to guide a new comparison.
