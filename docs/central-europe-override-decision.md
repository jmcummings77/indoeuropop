# Central Europe Child-Override Decision

Date: 2026-06-11

Status: promote `curation/aadr-v66-central-europe-child-overrides-interaction-best.toml`
to the active review candidate. Keep
`curation/aadr-v66-central-europe-child-overrides.toml` as the superseded first
candidate and benchmark.

## Context

The central-Europe structured comparison splits selected AADR v66 qpAdm rerun
targets into child regions so high-residual requested groups can receive local
priors instead of inheriting one broad parent trajectory. The first review
candidate adjusted Tiefbrunn and Manching/Oberstimm, then a second-stage
interaction sweep tested whether Tiefbrunn's Steppe reproductive-multiplier
signal remained stable under nearby Steppe count assumptions.

## Evidence

The accepted head-to-head report is
`results/qpadm-rerun/central-europe-curated-vs-interaction-best-delta.md`.
Negative deltas indicate better validation fit for the interaction-best
candidate relative to the superseded first candidate.

The same-baseline structural report is
`results/qpadm-rerun/central-europe-structured-pulse-vs-child-head-to-head.md`.
It compares the active child-region override with a broad-pulse candidate on
the same structured baseline. The active curation metadata points at this
report so strict readiness validation can catch stale report-manifest checksums.

- mean validation delta: `-0.022506`
- priority mean delta: `-0.098945`
- protected Britain delta: `-0.029487`
- protected degraded: `false`
- Tiefbrunn validation RMSE: `0.002625`
- Manching/Oberstimm validation RMSE: `0.021732`
- Britain validation RMSE: `0.122664`

The promoted candidate changes only Tiefbrunn's Steppe starting count and Steppe
reproductive multiplier relative to the superseded file. Manching/Oberstimm is
left unchanged, which keeps the head-to-head interpretation narrow.

## Rationale

The promoted Tiefbrunn setting uses a lower initial Steppe count and a lower
Steppe reproductive multiplier than the first candidate. That is defensible as a
more conservative local prior: it keeps the same broad migration timing, local
count, and region-level migration assumption while reducing the amount of
population growth attributed to Steppe ancestry. In the current validation
surface, this also avoids a Britain degradation under a zero-tolerance protected
fold gate.

This is still a model-selection decision, not an archaeological estimate. The
fit is guided by a small number of held-out target rows, qpAdm target values
depend on grouping and source/outgroup choices, and the interaction sweep is a
local grid rather than a full posterior search. Treat the promoted file as the
current reproducible candidate for continued review, not as final evidence for
Tiefbrunn demography.

## Follow-Up Rules

- Rerun the validation and override-delta reports whenever accepted targets,
  qpAdm estimates, or child-region structure change.
- Keep `validate_curation_decision_files(..., require_artifacts=True)` passing
  for the promoted and superseded override files. The strict mode checks linked
  decision records, reciprocal promotion metadata, generated validation CSVs,
  and delta-manifest checksums so stale local artifacts are caught by tests.
  The equivalent local command is `uv run indoeuropop validate-curation-decisions
  --curation-decision-file curation/aadr-v66-central-europe-child-overrides.toml
  --curation-decision-file
  curation/aadr-v66-central-europe-child-overrides-interaction-best.toml
  --require-artifacts`.
- Compare future candidates against this promoted file and against the broader
  structured baseline before changing default curation again.
- Use `indoeuropop compare-structured-candidates` when comparing this file with
  a broad structural pulse, because it keeps both candidate deltas on the same
  structured baseline.
- Keep archaeological interpretation separate from the validation score until
  target grouping, chronology, and uncertainty assumptions have been reviewed.
