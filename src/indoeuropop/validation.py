"""Validation-split helpers for target-fit robustness checks."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

from indoeuropop.fitting import FIT_METRICS, TargetFit, score_result_against_targets
from indoeuropop.models import SimulationResult
from indoeuropop.simulation import run_deterministic
from indoeuropop.summary import summarize_trajectory
from indoeuropop.sweeps import (
    SweepRun,
    SweepSpec,
    latin_hypercube_samples,
    parameters_with_overrides,
)
from indoeuropop.targets import TargetDataset, TargetObservation

ValidationSplitName = Literal["calibration", "validation"]


@dataclass(frozen=True)
class TargetSplit:
    """Calibration and validation target datasets for robustness checks."""

    calibration: TargetDataset
    validation: TargetDataset

    def __post_init__(self) -> None:
        """Require both split halves to contain at least one observation."""
        self.calibration.require_observations()
        self.validation.require_observations()


@dataclass(frozen=True)
class ValidationFit:
    """Fit statistics for one simulation on calibration and validation targets."""

    calibration: TargetFit
    validation: TargetFit

    def metric_value(self, metric: str, split: ValidationSplitName) -> float:
        """Return one fit metric from the requested split."""
        return _target_fit_metric_value(_fit_for_split(self, split), metric)

    def generalization_gap(self, metric: str) -> float:
        """Return validation minus calibration fit for a supported metric."""
        if metric not in FIT_METRICS:
            raise ValueError(f"unsupported fit metric: {metric}")
        return self.metric_value(metric, "validation") - self.metric_value(
            metric, "calibration"
        )


@dataclass(frozen=True)
class ValidatedSweepRun:
    """A sweep run with calibration and held-out validation fit statistics."""

    run: SweepRun
    fit: ValidationFit

    def metric_value(self, metric: str, split: ValidationSplitName) -> float:
        """Return one supported fit metric from a selected split."""
        return self.fit.metric_value(metric, split)

    def generalization_gap(self, metric: str) -> float:
        """Return validation minus calibration fit for one metric."""
        return self.fit.generalization_gap(metric)


def split_targets_by_region(
    targets: TargetDataset, validation_regions: Iterable[str]
) -> TargetSplit:
    """Split target observations into calibration and validation region sets."""
    validation_region_set = set(validation_regions)
    if not validation_region_set:
        raise ValueError("validation_regions must contain at least one region")

    calibration: list[TargetObservation] = []
    validation: list[TargetObservation] = []
    for observation in targets.observations:
        if observation.region in validation_region_set:
            validation.append(observation)
        else:
            calibration.append(observation)

    return TargetSplit(
        calibration=TargetDataset.from_rows(calibration),
        validation=TargetDataset.from_rows(validation),
    )


def score_result_on_split(
    result: SimulationResult, target_split: TargetSplit
) -> ValidationFit:
    """Score one simulation result against calibration and validation targets."""
    return ValidationFit(
        calibration=score_result_against_targets(result, target_split.calibration),
        validation=score_result_against_targets(result, target_split.validation),
    )


def rank_validated_runs(
    runs: Iterable[ValidatedSweepRun],
    *,
    metric: str = "chi_square",
    split: ValidationSplitName = "calibration",
) -> tuple[ValidatedSweepRun, ...]:
    """Return validated runs sorted from best to worst by a selected fit metric."""
    if metric not in FIT_METRICS:
        raise ValueError(f"unsupported fit metric: {metric}")
    _require_split(split)
    return tuple(sorted(runs, key=lambda run: run.metric_value(metric, split)))


def run_validated_parameter_sweep(
    spec: SweepSpec,
    target_split: TargetSplit,
    *,
    metric: str = "chi_square",
) -> tuple[ValidatedSweepRun, ...]:
    """Run a deterministic sweep ranked on calibration targets with validation fit."""
    if metric not in FIT_METRICS:
        raise ValueError(f"unsupported fit metric: {metric}")

    sampled_values = latin_hypercube_samples(
        spec.parameter_ranges, sample_count=spec.sample_count, seed=spec.seed
    )
    validated_runs: list[ValidatedSweepRun] = []
    for index, values in enumerate(sampled_values):
        parameters = parameters_with_overrides(spec.base_parameters, values)
        result = run_deterministic(
            spec.initial_state,
            parameters,
            start_bce=spec.start_bce,
            end_bce=spec.end_bce,
            step_years=spec.step_years,
            schedule=spec.schedule,
            parameter_set=spec.parameter_set,
        )
        sweep_run = SweepRun(
            index=index,
            sampled_values=values,
            parameters=parameters,
            summary=summarize_trajectory(
                result, source=spec.source, region=spec.region
            ),
        )
        validated_runs.append(
            ValidatedSweepRun(
                run=sweep_run,
                fit=score_result_on_split(result, target_split),
            )
        )

    return rank_validated_runs(validated_runs, metric=metric, split="calibration")


def _fit_for_split(
    validation_fit: ValidationFit, split: ValidationSplitName
) -> TargetFit:
    """Return fit statistics for the named split."""
    if split == "calibration":
        return validation_fit.calibration
    if split == "validation":
        return validation_fit.validation
    raise ValueError(f"unsupported validation split: {split}")


def _target_fit_metric_value(fit: TargetFit, metric: str) -> float:
    """Return one supported fit metric from aggregate target-fit statistics."""
    if metric not in FIT_METRICS:
        raise ValueError(f"unsupported fit metric: {metric}")
    return float(getattr(fit, metric))


def _require_split(split: ValidationSplitName) -> None:
    """Validate a split selector."""
    if split not in ("calibration", "validation"):
        raise ValueError(f"unsupported validation split: {split}")
