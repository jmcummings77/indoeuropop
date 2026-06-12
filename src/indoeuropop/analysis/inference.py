"""Lightweight ABC-style rejection inference over scored sweep samples."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from math import ceil, isfinite

import numpy as np

from indoeuropop.analysis.fitting import FIT_METRICS, ScoredSweepRun, rank_scored_runs


@dataclass(frozen=True)
class ABCRejectionOptions:
    """Configuration for a bounded rejection step over deterministic sweep fits."""

    fit_metric: str = "root_mean_squared_error"
    acceptance_quantile: float = 0.25
    acceptance_count: int | None = None
    acceptance_threshold: float | None = None

    def __post_init__(self) -> None:
        """Validate metric and acceptance controls."""
        if self.fit_metric not in FIT_METRICS:
            raise ValueError(f"unsupported fit metric: {self.fit_metric}")
        if self.acceptance_count is not None and self.acceptance_count <= 0:
            raise ValueError("acceptance_count must be positive")
        if self.acceptance_threshold is not None:
            if not isfinite(self.acceptance_threshold):
                raise ValueError("acceptance_threshold must be finite")
            if self.acceptance_threshold < 0:
                raise ValueError("acceptance_threshold must be non-negative")
        if (
            self.acceptance_count is None
            and self.acceptance_threshold is None
            and (self.acceptance_quantile <= 0 or self.acceptance_quantile > 1)
        ):
            raise ValueError("acceptance_quantile must be in (0, 1]")

    @property
    def criterion(self) -> str:
        """Return the active acceptance criterion label."""
        if self.acceptance_threshold is not None:
            return "threshold"
        if self.acceptance_count is not None:
            return "count"
        return "quantile"


@dataclass(frozen=True)
class PosteriorParameterSummary:
    """Summary statistics for one parameter among accepted samples."""

    parameter: str
    accepted_count: int
    mean: float
    median: float
    minimum: float
    maximum: float
    lower_interval: float
    upper_interval: float

    def __post_init__(self) -> None:
        """Validate summary shape and finite values."""
        if not self.parameter:
            raise ValueError("parameter must be non-empty")
        if self.accepted_count <= 0:
            raise ValueError("accepted_count must be positive")
        values = (
            self.mean,
            self.median,
            self.minimum,
            self.maximum,
            self.lower_interval,
            self.upper_interval,
        )
        if any(not isfinite(value) for value in values):
            raise ValueError("posterior summary values must be finite")
        if self.minimum > self.maximum:
            raise ValueError("minimum must be less than or equal to maximum")
        if self.lower_interval > self.upper_interval:
            raise ValueError(
                "lower_interval must be less than or equal to upper_interval"
            )


@dataclass(frozen=True)
class ABCRejectionResult:
    """Rejected and accepted target-fit samples plus parameter summaries."""

    options: ABCRejectionOptions
    ranked_runs: tuple[ScoredSweepRun, ...]
    accepted_runs: tuple[ScoredSweepRun, ...]
    parameter_summaries: tuple[PosteriorParameterSummary, ...]
    acceptance_threshold: float

    def __post_init__(self) -> None:
        """Validate result consistency."""
        if not self.ranked_runs:
            raise ValueError("ranked_runs must contain at least one run")
        if not self.accepted_runs:
            raise ValueError("accepted_runs must contain at least one run")
        if len(self.accepted_runs) > len(self.ranked_runs):
            raise ValueError("accepted_runs cannot exceed ranked_runs")
        if not isfinite(self.acceptance_threshold) or self.acceptance_threshold < 0:
            raise ValueError("acceptance_threshold must be finite and non-negative")
        if not self.parameter_summaries:
            raise ValueError("parameter_summaries must not be empty")

    @property
    def candidate_count(self) -> int:
        """Return the total number of scored samples considered."""
        return len(self.ranked_runs)

    @property
    def accepted_count(self) -> int:
        """Return the number of accepted samples."""
        return len(self.accepted_runs)

    @property
    def acceptance_rate(self) -> float:
        """Return accepted samples divided by all candidate samples."""
        return self.accepted_count / self.candidate_count

    @property
    def best_run(self) -> ScoredSweepRun:
        """Return the best-ranked accepted run."""
        return self.accepted_runs[0]


def run_abc_rejection_inference(
    scored_runs: Iterable[ScoredSweepRun],
    options: ABCRejectionOptions | None = None,
) -> ABCRejectionResult:
    """Return accepted samples and posterior summaries from scored sweep runs."""
    inference_options = ABCRejectionOptions() if options is None else options
    ranked = rank_scored_runs(tuple(scored_runs), metric=inference_options.fit_metric)
    if not ranked:
        raise ValueError("scored_runs must contain at least one run")
    accepted = _accepted_runs(ranked, inference_options)
    threshold = accepted[-1].metric_value(inference_options.fit_metric)
    return ABCRejectionResult(
        options=inference_options,
        ranked_runs=ranked,
        accepted_runs=accepted,
        parameter_summaries=posterior_parameter_summaries(accepted),
        acceptance_threshold=threshold,
    )


def posterior_parameter_summaries(
    accepted_runs: Iterable[ScoredSweepRun],
) -> tuple[PosteriorParameterSummary, ...]:
    """Return summary statistics for accepted sampled parameter values."""
    accepted_tuple = tuple(accepted_runs)
    if not accepted_tuple:
        raise ValueError("accepted_runs must contain at least one run")
    parameter_names = _sampled_parameter_names(accepted_tuple)
    return tuple(
        _parameter_summary(parameter_name, accepted_tuple)
        for parameter_name in parameter_names
    )


def _accepted_runs(
    ranked_runs: tuple[ScoredSweepRun, ...],
    options: ABCRejectionOptions,
) -> tuple[ScoredSweepRun, ...]:
    """Return accepted scored runs according to the configured criterion."""
    if options.acceptance_threshold is not None:
        accepted = tuple(
            run
            for run in ranked_runs
            if run.metric_value(options.fit_metric) <= options.acceptance_threshold
        )
        if not accepted:
            raise ValueError("acceptance_threshold accepted no runs")
        return accepted
    if options.acceptance_count is not None:
        if options.acceptance_count > len(ranked_runs):
            raise ValueError("acceptance_count cannot exceed candidate count")
        return ranked_runs[: options.acceptance_count]
    accepted_count = max(1, ceil(len(ranked_runs) * options.acceptance_quantile))
    return ranked_runs[:accepted_count]


def _sampled_parameter_names(
    accepted_runs: tuple[ScoredSweepRun, ...],
) -> tuple[str, ...]:
    """Return sorted sampled parameter names after validating shape consistency."""
    parameter_names = tuple(sorted(accepted_runs[0].run.sampled_values))
    if not parameter_names:
        raise ValueError("accepted runs must contain sampled parameter values")
    expected = set(parameter_names)
    for scored_run in accepted_runs:
        if set(scored_run.run.sampled_values) != expected:
            raise ValueError("accepted runs must contain the same sampled parameters")
    return parameter_names


def _parameter_summary(
    parameter_name: str, accepted_runs: tuple[ScoredSweepRun, ...]
) -> PosteriorParameterSummary:
    """Return one posterior-style summary for a sampled parameter."""
    values = np.array(
        [run.run.sampled_values[parameter_name] for run in accepted_runs],
        dtype=np.float64,
    )
    lower_interval, upper_interval = np.quantile(values, [0.05, 0.95])
    return PosteriorParameterSummary(
        parameter=parameter_name,
        accepted_count=len(accepted_runs),
        mean=float(np.mean(values)),
        median=float(np.median(values)),
        minimum=float(np.min(values)),
        maximum=float(np.max(values)),
        lower_interval=float(lower_interval),
        upper_interval=float(upper_interval),
    )
