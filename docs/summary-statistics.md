# Summary Statistics

Summary statistics are the compact model-output features that later inference
or emulator workflows can compare. They are deterministic model summaries, not
posterior probabilities or evidence for a historical conclusion.

## Trajectory Vectors

`trajectory_summary_vector` converts a `TrajectorySummary` into a named
`SummaryVector` with these statistics:

- `initial_ancestry`
- `final_ancestry`
- `ancestry_delta`
- `ancestry_slope_per_century`
- `min_total_population`
- `final_total_population`
- `is_extinct`, optionally encoded as `0.0` or `1.0`

Each `SummaryStatistic` may include a positive scale. Distances divide by the
scale stored on the left vector, making the weighting explicit.

## Distance

`SummaryVector.root_mean_square_distance` compares selected named statistics
between two vectors. The default selection is the full left vector, and all
selected names must exist in both vectors.

This distance is a debugging and ranking utility. It is not a likelihood,
Bayes factor, posterior score, or calibrated archaeological metric.

## Guardrail

Any future ABC-SMC, Bayesian optimization, or emulator code should declare
which summary statistics it uses, which scales or weights are applied, and how
the selected statistics were validated against held-out targets.
