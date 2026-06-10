# Simulation Diagnostics

Simulation diagnostics are mechanical checks for model output quality. They are
intended to catch obviously suspicious runs before plotting, scoring, or using a
trajectory in a larger sweep.

## Checks

`validate_simulation_result` currently reports:

- `non_decreasing_time`: BCE time labels did not strictly decrease.
- `missing_region`: a region appears in some states but not others.
- `missing_source`: a source appears in some states but not every checked
  region.
- `extinction`: a region total is at or below the configured threshold.
- `runaway_growth`: a region total exceeds the configured multiplier relative
  to its initial total.

Each issue is a `DiagnosticIssue` with a severity, code, message, and optional
time, region, and source labels.

## Guardrail

Diagnostics are not scientific validation. A clean diagnostic report means only
that the time series passed basic software sanity checks. It does not mean the
parameters, mechanisms, or historical interpretation are plausible.
