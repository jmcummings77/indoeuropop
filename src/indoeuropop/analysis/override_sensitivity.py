"""Candidate generation and metrics for child-override sensitivity sweeps."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from math import isfinite
from statistics import fmean

from indoeuropop.analysis.fitting import FIT_METRICS
from indoeuropop.analysis.validation import TargetValidationFold
from indoeuropop.orchestration.child_region_overrides import ChildRegionOverrideSet


@dataclass(frozen=True)
class OverrideSensitivityCandidate:
    """One one-factor-at-a-time child-override candidate."""

    name: str
    overrides: ChildRegionOverrideSet
    region: str
    parameter: str
    base_value: float
    candidate_value: float

    def __post_init__(self) -> None:
        """Validate candidate labels and finite comparison values."""
        if not self.name:
            raise ValueError("candidate name must be non-empty")
        if not self.region:
            raise ValueError("candidate region must be non-empty")
        if not self.parameter:
            raise ValueError("candidate parameter must be non-empty")
        if not isfinite(self.base_value) or not isfinite(self.candidate_value):
            raise ValueError("candidate values must be finite")


@dataclass(frozen=True)
class OverrideSensitivityScenario:
    """One override candidate with held-out validation diagnostics."""

    candidate: OverrideSensitivityCandidate
    folds: tuple[TargetValidationFold, ...]
    metric: str
    priority_values: tuple[str, ...] = ()
    protected_values: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Require a supported metric and at least one validation fold."""
        if not self.folds:
            raise ValueError("folds must contain at least one validation fold")
        if self.metric not in FIT_METRICS:
            raise ValueError(f"unsupported fit metric: {self.metric}")

    @property
    def name(self) -> str:
        """Return the candidate name."""
        return self.candidate.name

    def mean_validation_metric(self) -> float:
        """Return mean held-out validation fit across best fold runs."""
        return fmean(
            fold.best_run.metric_value(self.metric, "validation") for fold in self.folds
        )

    def worst_validation_metric(self) -> float:
        """Return the largest held-out validation fit among best fold runs."""
        return max(
            fold.best_run.metric_value(self.metric, "validation") for fold in self.folds
        )

    def validation_metric_for(self, holdout_value: str) -> float:
        """Return validation fit for one held-out value."""
        return validation_metric_for(self.folds, self.metric, holdout_value)

    def delta_for(
        self, baseline_folds: tuple[TargetValidationFold, ...], holdout_value: str
    ) -> float:
        """Return validation metric delta versus baseline folds."""
        return self.validation_metric_for(holdout_value) - validation_metric_for(
            baseline_folds, self.metric, holdout_value
        )

    def priority_mean_delta(
        self, baseline_folds: tuple[TargetValidationFold, ...]
    ) -> float:
        """Return mean validation delta for priority holdouts."""
        if not self.priority_values:
            return 0.0
        return fmean(
            self.delta_for(baseline_folds, value) for value in self.priority_values
        )

    def protected_max_delta(
        self, baseline_folds: tuple[TargetValidationFold, ...]
    ) -> float:
        """Return largest validation delta among protected holdouts."""
        if not self.protected_values:
            return 0.0
        return max(
            self.delta_for(baseline_folds, value) for value in self.protected_values
        )

    def protected_degraded(
        self, baseline_folds: tuple[TargetValidationFold, ...], *, tolerance: float
    ) -> bool:
        """Return whether any protected holdout worsened beyond tolerance."""
        _require_non_negative_tolerance(tolerance)
        return any(
            self.delta_for(baseline_folds, value) > tolerance
            for value in self.protected_values
        )

    def accepted(
        self, baseline_folds: tuple[TargetValidationFold, ...], *, tolerance: float
    ) -> bool:
        """Return whether this scenario improves priorities within constraints."""
        return self.priority_mean_delta(
            baseline_folds
        ) < 0 and not self.protected_degraded(baseline_folds, tolerance=tolerance)


def rank_override_sensitivity_scenarios(
    scenarios: Iterable[OverrideSensitivityScenario],
    baseline_folds: tuple[TargetValidationFold, ...],
    *,
    tolerance: float,
) -> tuple[OverrideSensitivityScenario, ...]:
    """Return scenarios ranked by constrained priority improvement."""
    scenario_tuple = tuple(scenarios)
    if not scenario_tuple:
        raise ValueError("scenarios must contain at least one scenario")
    _require_non_negative_tolerance(tolerance)
    return tuple(
        sorted(
            scenario_tuple,
            key=lambda scenario: (
                not scenario.accepted(baseline_folds, tolerance=tolerance),
                scenario.priority_mean_delta(baseline_folds),
                scenario.protected_max_delta(baseline_folds),
                scenario.mean_validation_metric(),
                scenario.name,
            ),
        )
    )


def validation_metric_for(
    folds: tuple[TargetValidationFold, ...], metric: str, holdout_value: str
) -> float:
    """Return validation metric for exactly one holdout value."""
    matches = tuple(fold for fold in folds if fold.holdout_value == holdout_value)
    if not matches:
        raise ValueError(f"unknown holdout value: {holdout_value}")
    if len(matches) > 1:
        raise ValueError(f"duplicate holdout value: {holdout_value}")
    return matches[0].best_run.metric_value(metric, "validation")


def _require_non_negative_tolerance(tolerance: float) -> None:
    """Validate a non-negative metric tolerance."""
    if tolerance < 0:
        raise ValueError("tolerance must be non-negative")
