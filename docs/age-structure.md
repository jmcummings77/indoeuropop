# Age Structure

Age structure is a model-expansion scaffold for testing whether generation
composition changes simulated behavior. It is not wired into the main
source-count simulator by default.

## State

`AgeStructuredState` stores counts by region, source, and age class:

- `juvenile`
- `adult`
- `elder`

The helper can derive source ancestry across age classes and can collapse back
to `PopulationState` so existing plotting, diagnostics, and target comparison
code can still be reused.

## Projection

`AgeStructureParameters` stores birth, mortality, maturation, and aging rates.
`advance_age_structure` applies one deterministic step with capped deaths and
age-class transitions, keeping counts non-negative.

## Guardrail

This module is a transparent demographic scaffold. It does not define calibrated
generation lengths, sex-biased inheritance, household structure, or historical
fertility values. Those choices need explicit evidence and validation before
being integrated into the main simulator.
