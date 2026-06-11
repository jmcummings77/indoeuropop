# Epidemic Compartments

Epidemic compartments are a model-expansion scaffold for testing explicit
transmission dynamics. They are not wired into the main source-count simulator
by default, which still treats epidemic stress as an exogenous mortality hazard.

## State

`EpidemicState` stores counts by region, source, and compartment:

- `susceptible`
- `infected`
- `recovered`
- `deceased`

The helper can derive infection prevalence among living people and can collapse
living counts back to `PopulationState` so existing plotting, diagnostics, and
target comparison code can still be reused.

## Projection

`EpidemicParameters` stores a transmission rate, recovery rate, disease
mortality rate, background mortality rate, and optional source-specific
susceptibility multipliers. `advance_epidemic` applies one deterministic
region-level mixing step with capped infections and removals so compartment
counts remain non-negative.

## Guardrail

This module is a transparent SIRD-style scaffold. It does not identify a
pathogen, infer plague prevalence, model pathogen evolution, encode burial
evidence, or calibrate transmission from ancient DNA. Those choices require
explicit evidence and validation before a compartmental epidemic model replaces
the main simulator's simpler exogenous hazard.
