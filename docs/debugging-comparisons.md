# Debugging Comparisons

Deterministic and tau-leap simulations should be easy to inspect side by side.
The comparison helpers are for debugging simulator behavior, not for estimating
historical uncertainty.

## Ancestry Comparison

`compare_ancestry_trajectories` compares two `SimulationResult` objects with
identical time labels. It returns an `AncestryComparison` containing the two
ancestry series, pointwise differences, maximum absolute difference, final
difference, and root-mean-squared difference.

`compare_deterministic_and_tau_leap` runs both simulators from the same initial
state, parameters, timeline, optional schedule, and optional parameter table,
then returns the same comparison summary.

## Plotting

`plot_ancestry_comparison` overlays the two ancestry trajectories in a
Matplotlib figure. This is meant for quick checks of stochastic spread,
unexpected drift, or schedule/parameter-table effects before running larger
sweeps.

## Guardrail

A tau-leap trajectory is a seeded stochastic smoke path. A difference between it
and the deterministic trajectory is not an inferred confidence interval or a
posterior uncertainty estimate.
