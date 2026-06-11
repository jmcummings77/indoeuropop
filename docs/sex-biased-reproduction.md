# Sex-Biased Reproduction

Sex-biased reproduction is a model-expansion scaffold for testing how
sex-specific reproductive weights could change expected autosomal ancestry
contributions. It is not wired into the main source-count simulator by default.

## State

`SexStructuredState` stores counts by region, source, and sex label:

- `female`
- `male`

The helper can derive source proportions within a sex label and can collapse
back to `PopulationState` so existing plotting, diagnostics, and target
comparison code can still be reused.

## Projection

`SexBiasParameters` stores an annual birth rate, an autosomal maternal share,
and optional source-specific female or male reproductive multipliers.
`expected_births_by_source` returns deterministic expected newborn source
contributions. Female reproductive weight sets the total number of births, and
maternal and paternal source weights determine source contributions.

## Guardrail

This module is a transparent demographic scaffold. It does not infer historical
sex bias, Y-chromosome turnover, mitochondrial continuity, household structure,
social status, or calibrated fertility values. Those choices need explicit
evidence, validation, and probably separate uniparental-marker or pedigree
models before being integrated into the main simulator.
