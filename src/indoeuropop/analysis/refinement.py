"""Validation-guided parameter-range refinement helpers."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from statistics import fmean
from typing import Literal

from indoeuropop.analysis.validation import TargetValidationFold
from indoeuropop.orchestration.sweeps import ParameterRange, SweepSpec

RefinementKind = Literal["baseline", "narrowed", "expanded"]

PROBABILITY_PARAMETER_NAMES = frozenset(
    {
        "fertility_rate",
        "local_mortality_rate",
        "steppe_mortality_rate",
        "migration_rate",
        "epidemic_mortality_rate",
        "local_epidemic_risk",
        "steppe_epidemic_risk",
        "violence_mortality_rate",
        "climate_stress",
    }
)


@dataclass(frozen=True)
class ParameterRangeChange:
    """A proposed range for one sampled simulation parameter."""

    candidate_name: str
    parameter: str
    original_low: float
    original_high: float
    refined_low: float
    refined_high: float
    center: float
    scale: float

    @property
    def original_width(self) -> float:
        """Return the original parameter interval width."""
        return self.original_high - self.original_low

    @property
    def refined_width(self) -> float:
        """Return the refined parameter interval width."""
        return self.refined_high - self.refined_low


@dataclass(frozen=True)
class ParameterRefinementCandidate:
    """One candidate sweep-grid refinement."""

    name: str
    kind: RefinementKind
    spec: SweepSpec
    range_changes: tuple[ParameterRangeChange, ...]


@dataclass(frozen=True)
class TargetRefinementScenario:
    """One candidate sweep grid with held-out validation diagnostics."""

    candidate: ParameterRefinementCandidate
    folds: tuple[TargetValidationFold, ...]
    metric: str
    priority_values: tuple[str, ...] = ()
    protected_values: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Require at least one validation fold."""
        if not self.folds:
            raise ValueError("folds must contain at least one validation fold")

    @property
    def name(self) -> str:
        """Return the candidate scenario name."""
        return self.candidate.name

    def mean_calibration_metric(self) -> float:
        """Return the mean calibration fit across best fold runs."""
        return fmean(
            fold.best_run.metric_value(self.metric, "calibration")
            for fold in self.folds
        )

    def mean_validation_metric(self) -> float:
        """Return the mean held-out validation fit across best fold runs."""
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
        return _single_fold(self.folds, holdout_value).best_run.metric_value(
            self.metric, "validation"
        )

    def mean_delta_for(
        self, baseline: TargetRefinementScenario, values: Iterable[str]
    ) -> float:
        """Return mean validation delta versus baseline for selected values."""
        selected_values = tuple(values)
        if not selected_values:
            return 0.0
        return fmean(self.delta_for(baseline, value) for value in selected_values)

    def delta_for(
        self, baseline: TargetRefinementScenario, holdout_value: str
    ) -> float:
        """Return validation metric delta versus baseline for one holdout."""
        return self.validation_metric_for(
            holdout_value
        ) - baseline.validation_metric_for(holdout_value)

    def protected_degraded(
        self, baseline: TargetRefinementScenario, *, tolerance: float = 0.0
    ) -> bool:
        """Return whether any protected holdout worsened beyond tolerance."""
        _require_non_negative_tolerance(tolerance)
        return any(
            self.delta_for(baseline, value) > tolerance
            for value in self.protected_values
        )

    def priority_improved(
        self, baseline: TargetRefinementScenario, *, tolerance: float = 0.0
    ) -> bool:
        """Return whether every priority holdout improved beyond tolerance."""
        _require_non_negative_tolerance(tolerance)
        return bool(self.priority_values) and all(
            self.delta_for(baseline, value) < -tolerance
            for value in self.priority_values
        )


def baseline_refinement_candidate(spec: SweepSpec) -> ParameterRefinementCandidate:
    """Return the unmodified sweep grid as a refinement candidate."""
    return ParameterRefinementCandidate(
        name="baseline",
        kind="baseline",
        spec=spec,
        range_changes=_range_changes("baseline", spec.parameter_ranges, 1.0),
    )


def centered_refinement_candidate(
    spec: SweepSpec,
    *,
    name: str,
    kind: RefinementKind,
    center_values: Mapping[str, float],
    scale: float,
) -> ParameterRefinementCandidate:
    """Return a sweep candidate centered on validation-best parameter values."""
    if kind == "baseline":
        raise ValueError("centered refinement candidates cannot use baseline kind")
    if scale <= 0:
        raise ValueError("scale must be positive")
    ranges = tuple(
        _centered_range(parameter_range, center_values, scale)
        for parameter_range in spec.parameter_ranges
    )
    return ParameterRefinementCandidate(
        name=name,
        kind=kind,
        spec=replace(spec, parameter_ranges=ranges),
        range_changes=_range_changes(name, spec.parameter_ranges, scale, ranges),
    )


def mean_best_sampled_values(
    folds: Iterable[TargetValidationFold],
) -> dict[str, float]:
    """Return mean sampled values from calibration-best validation runs."""
    fold_tuple = tuple(folds)
    if not fold_tuple:
        raise ValueError("folds must contain at least one validation fold")
    parameter_names = tuple(sorted(fold_tuple[0].best_run.run.sampled_values))
    if not parameter_names:
        raise ValueError("validation runs must contain sampled parameter values")
    for fold in fold_tuple:
        if set(fold.best_run.run.sampled_values) != set(parameter_names):
            raise ValueError("validation folds must share sampled parameter names")
    return {
        parameter_name: fmean(
            fold.best_run.run.sampled_values[parameter_name] for fold in fold_tuple
        )
        for parameter_name in parameter_names
    }


def _centered_range(
    parameter_range: ParameterRange,
    center_values: Mapping[str, float],
    scale: float,
) -> ParameterRange:
    """Return one range centered on a selected parameter value."""
    center = float(center_values[parameter_range.name])
    half_width = (parameter_range.high - parameter_range.low) * scale / 2
    low = center - half_width
    high = center + half_width
    clipped_low, clipped_high = _clip_parameter_bounds(
        parameter_range.name,
        low,
        high,
    )
    return ParameterRange(parameter_range.name, clipped_low, clipped_high)


def _clip_parameter_bounds(
    parameter_name: str, low: float, high: float
) -> tuple[float, float]:
    """Clip refined ranges to scalar parameter validation bounds."""
    lower_bound = 1.0 if parameter_name == "elite_reproductive_advantage" else 0.0
    clipped_low = max(lower_bound, low)
    clipped_high = max(clipped_low, high)
    if parameter_name in PROBABILITY_PARAMETER_NAMES:
        clipped_high = min(1.0, clipped_high)
        clipped_low = min(clipped_low, clipped_high)
    return clipped_low, clipped_high


def _range_changes(
    candidate_name: str,
    original_ranges: tuple[ParameterRange, ...],
    scale: float,
    refined_ranges: tuple[ParameterRange, ...] | None = None,
) -> tuple[ParameterRangeChange, ...]:
    """Return range-change rows for a candidate."""
    selected_ranges = original_ranges if refined_ranges is None else refined_ranges
    return tuple(
        ParameterRangeChange(
            candidate_name=candidate_name,
            parameter=original.name,
            original_low=original.low,
            original_high=original.high,
            refined_low=refined.low,
            refined_high=refined.high,
            center=(refined.low + refined.high) / 2,
            scale=scale,
        )
        for original, refined in zip(original_ranges, selected_ranges, strict=True)
    )


def _single_fold(
    folds: tuple[TargetValidationFold, ...], holdout_value: str
) -> TargetValidationFold:
    """Return exactly one fold matching a holdout value."""
    matches = tuple(fold for fold in folds if fold.holdout_value == holdout_value)
    if not matches:
        raise ValueError(f"unknown holdout value: {holdout_value}")
    if len(matches) > 1:
        raise ValueError(f"duplicate holdout value: {holdout_value}")
    return matches[0]


def _require_non_negative_tolerance(tolerance: float) -> None:
    """Validate a non-negative metric tolerance."""
    if tolerance < 0:
        raise ValueError("tolerance must be non-negative")
