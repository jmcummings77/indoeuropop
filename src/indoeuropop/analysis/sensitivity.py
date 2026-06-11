"""Lightweight sensitivity diagnostics for parameter sweep outputs."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from math import isfinite

import numpy as np
from numpy.typing import NDArray

from indoeuropop.orchestration.sweeps import SweepRun

NUMERIC_OUTCOMES = frozenset(
    {
        "initial_ancestry",
        "final_ancestry",
        "ancestry_delta",
        "ancestry_slope_per_century",
        "min_total_population",
        "final_total_population",
    }
)


@dataclass(frozen=True)
class SensitivityResult:
    """Association metrics for one sampled parameter against one outcome."""

    parameter: str
    outcome: str
    pearson_correlation: float
    spearman_correlation: float
    linear_slope: float

    @property
    def absolute_spearman(self) -> float:
        """Return absolute rank correlation for sorting and reporting."""
        return abs(self.spearman_correlation)


def analyze_sensitivity(
    runs: Iterable[SweepRun], *, outcome: str = "final_ancestry"
) -> tuple[SensitivityResult, ...]:
    """Analyze sweep sensitivity using correlation and linear slope metrics.

    Results are sorted by absolute Spearman correlation so the strongest
    monotonic associations appear first. These diagnostics are exploratory; they
    are not posterior probabilities or formal Sobol indices.
    """
    run_tuple = tuple(runs)
    if not run_tuple:
        raise ValueError("runs must contain at least one sweep run")
    if outcome not in NUMERIC_OUTCOMES:
        raise ValueError(f"unsupported numeric outcome: {outcome}")

    parameter_names = tuple(run_tuple[0].sampled_values)
    if not parameter_names:
        raise ValueError("sweep runs must contain sampled parameter values")
    _require_matching_parameters(run_tuple, parameter_names)

    outcome_values = _outcome_values(run_tuple, outcome)
    results = tuple(
        SensitivityResult(
            parameter=parameter_name,
            outcome=outcome,
            pearson_correlation=_correlation(
                _parameter_values(run_tuple, parameter_name), outcome_values
            ),
            spearman_correlation=_correlation(
                _ranks(_parameter_values(run_tuple, parameter_name)),
                _ranks(outcome_values),
            ),
            linear_slope=_linear_slope(
                _parameter_values(run_tuple, parameter_name), outcome_values
            ),
        )
        for parameter_name in parameter_names
    )
    return tuple(
        sorted(results, key=lambda result: result.absolute_spearman, reverse=True)
    )


def _require_matching_parameters(
    runs: tuple[SweepRun, ...], parameter_names: tuple[str, ...]
) -> None:
    """Raise if sweep runs were produced from different parameter sets."""
    expected = set(parameter_names)
    for run in runs:
        if set(run.sampled_values) != expected:
            raise ValueError("all sweep runs must contain the same sampled parameters")


def _parameter_values(
    runs: tuple[SweepRun, ...], parameter_name: str
) -> NDArray[np.float64]:
    """Return sampled values for one parameter."""
    return np.array(
        [run.sampled_values[parameter_name] for run in runs], dtype=np.float64
    )


def _outcome_values(runs: tuple[SweepRun, ...], outcome: str) -> NDArray[np.float64]:
    """Return numeric summary values for one outcome field."""
    values = np.array([getattr(run.summary, outcome) for run in runs], dtype=np.float64)
    if not all(isfinite(value) for value in values):
        raise ValueError("outcome values must be finite")
    return values


def _correlation(left: NDArray[np.float64], right: NDArray[np.float64]) -> float:
    """Return Pearson correlation, or zero when either vector is constant."""
    if np.allclose(left, left[0]) or np.allclose(right, right[0]):
        return 0.0
    left_centered = left - float(np.mean(left))
    right_centered = right - float(np.mean(right))
    denominator = float(np.linalg.norm(left_centered) * np.linalg.norm(right_centered))
    return float(np.dot(left_centered, right_centered) / denominator)


def _linear_slope(
    x_values: NDArray[np.float64], y_values: NDArray[np.float64]
) -> float:
    """Return the least-squares slope of y on x, or zero for constant x."""
    if np.allclose(x_values, x_values[0]):
        return 0.0
    x_centered = x_values - float(np.mean(x_values))
    y_centered = y_values - float(np.mean(y_values))
    denominator = float(np.dot(x_centered, x_centered))
    return float(np.dot(x_centered, y_centered) / denominator)


def _ranks(values: NDArray[np.float64]) -> NDArray[np.float64]:
    """Return average ranks for numeric values, preserving tie behavior."""
    order = np.argsort(values, kind="mergesort")
    ranks = np.empty(len(values), dtype=np.float64)
    index = 0
    while index < len(values):
        tie_end = index + 1
        while tie_end < len(values) and values[order[tie_end]] == values[order[index]]:
            tie_end += 1
        average_rank = (index + tie_end - 1) / 2
        ranks[order[index:tie_end]] = average_rank
        index = tie_end
    return ranks
