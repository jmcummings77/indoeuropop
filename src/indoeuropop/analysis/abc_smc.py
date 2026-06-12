"""Sequential ABC-style calibration over deterministic sweep generations."""

from __future__ import annotations

from dataclasses import dataclass, replace
from math import isfinite

import numpy as np

from indoeuropop.analysis.fitting import FIT_METRICS, run_scored_parameter_sweep
from indoeuropop.analysis.inference import (
    ABCRejectionOptions,
    ABCRejectionResult,
    run_abc_rejection_inference,
)
from indoeuropop.data.targets import TargetDataset
from indoeuropop.orchestration.sweeps import ParameterRange, SweepSpec


@dataclass(frozen=True)
class ABCSMCOptions:
    """Controls for a bounded ABC-SMC-style sequential calibration run."""

    fit_metric: str = "root_mean_squared_error"
    generation_count: int = 3
    sample_count: int | None = None
    acceptance_quantile: float = 0.25
    acceptance_count: int | None = None
    seed_stride: int = 1009
    range_quantile_low: float = 0.05
    range_quantile_high: float = 0.95
    range_padding_fraction: float = 0.1

    def __post_init__(self) -> None:
        """Validate sequential calibration controls."""
        if self.fit_metric not in FIT_METRICS:
            raise ValueError(f"unsupported fit metric: {self.fit_metric}")
        if self.generation_count <= 0:
            raise ValueError("generation_count must be positive")
        if self.sample_count is not None and self.sample_count <= 0:
            raise ValueError("sample_count must be positive")
        if self.acceptance_count is not None and self.acceptance_count <= 0:
            raise ValueError("acceptance_count must be positive")
        if self.acceptance_count is None and (
            self.acceptance_quantile <= 0 or self.acceptance_quantile > 1
        ):
            raise ValueError("acceptance_quantile must be in (0, 1]")
        if self.seed_stride <= 0:
            raise ValueError("seed_stride must be positive")
        _validate_probability(self.range_quantile_low, "range_quantile_low")
        _validate_probability(self.range_quantile_high, "range_quantile_high")
        if self.range_quantile_low > self.range_quantile_high:
            raise ValueError(
                "range_quantile_low must be less than or equal to "
                "range_quantile_high"
            )
        if not isfinite(self.range_padding_fraction) or self.range_padding_fraction < 0:
            raise ValueError("range_padding_fraction must be finite and non-negative")


@dataclass(frozen=True)
class ABCSMCGeneration:
    """One sequential ABC generation and the ranges used to sample it."""

    generation_index: int
    spec: SweepSpec
    inference: ABCRejectionResult
    parameter_ranges: tuple[ParameterRange, ...]

    def __post_init__(self) -> None:
        """Validate generation metadata and sampled ranges."""
        if self.generation_index < 0:
            raise ValueError("generation_index must be non-negative")
        if not self.parameter_ranges:
            raise ValueError("parameter_ranges must not be empty")

    @property
    def acceptance_threshold(self) -> float:
        """Return the accepted fit threshold for this generation."""
        return self.inference.acceptance_threshold

    @property
    def best_metric_value(self) -> float:
        """Return the best fit-metric value in this generation."""
        return self.inference.best_run.metric_value(self.inference.options.fit_metric)


@dataclass(frozen=True)
class ABCSMCResult:
    """Sequential ABC calibration result across one or more generations."""

    options: ABCSMCOptions
    generations: tuple[ABCSMCGeneration, ...]

    def __post_init__(self) -> None:
        """Require at least one completed generation."""
        if not self.generations:
            raise ValueError("generations must not be empty")

    @property
    def final_generation(self) -> ABCSMCGeneration:
        """Return the last completed calibration generation."""
        return self.generations[-1]

    @property
    def final_inference(self) -> ABCRejectionResult:
        """Return the final generation's rejection result."""
        return self.final_generation.inference

    @property
    def threshold_schedule(self) -> tuple[float, ...]:
        """Return accepted thresholds in generation order."""
        return tuple(generation.acceptance_threshold for generation in self.generations)

    @property
    def total_candidate_count(self) -> int:
        """Return the total scored candidate count across all generations."""
        return sum(
            generation.inference.candidate_count for generation in self.generations
        )


def run_abc_smc_inference(
    spec: SweepSpec,
    targets: TargetDataset,
    options: ABCSMCOptions | None = None,
) -> ABCSMCResult:
    """Run sequential ABC-style calibration against a target dataset."""
    smc_options = ABCSMCOptions() if options is None else options
    target_dataset = targets.require_observations()
    generation_spec = _initial_generation_spec(spec, smc_options)
    original_ranges = generation_spec.parameter_ranges
    generations: list[ABCSMCGeneration] = []
    for generation_index in range(smc_options.generation_count):
        generation_spec = replace(
            generation_spec,
            seed=spec.seed + generation_index * smc_options.seed_stride,
        )
        scored_runs = run_scored_parameter_sweep(
            generation_spec,
            target_dataset,
            metric=smc_options.fit_metric,
        )
        inference = run_abc_rejection_inference(
            scored_runs,
            _generation_rejection_options(smc_options),
        )
        generation = ABCSMCGeneration(
            generation_index=generation_index,
            spec=generation_spec,
            inference=inference,
            parameter_ranges=generation_spec.parameter_ranges,
        )
        generations.append(generation)
        if generation_index + 1 < smc_options.generation_count:
            generation_spec = replace(
                generation_spec,
                parameter_ranges=_narrow_parameter_ranges(
                    original_ranges,
                    inference,
                    smc_options,
                ),
            )
    return ABCSMCResult(options=smc_options, generations=tuple(generations))


def _initial_generation_spec(spec: SweepSpec, options: ABCSMCOptions) -> SweepSpec:
    """Return the first generation spec with optional sample-count override."""
    if options.sample_count is None:
        return spec
    return replace(spec, sample_count=options.sample_count)


def _generation_rejection_options(options: ABCSMCOptions) -> ABCRejectionOptions:
    """Return the rejection options applied independently to each generation."""
    return ABCRejectionOptions(
        fit_metric=options.fit_metric,
        acceptance_quantile=options.acceptance_quantile,
        acceptance_count=options.acceptance_count,
    )


def _narrow_parameter_ranges(
    original_ranges: tuple[ParameterRange, ...],
    inference: ABCRejectionResult,
    options: ABCSMCOptions,
) -> tuple[ParameterRange, ...]:
    """Return next-generation ranges from accepted parameter quantiles."""
    return tuple(
        _narrow_parameter_range(parameter_range, inference, options)
        for parameter_range in original_ranges
    )


def _narrow_parameter_range(
    parameter_range: ParameterRange,
    inference: ABCRejectionResult,
    options: ABCSMCOptions,
) -> ParameterRange:
    """Return one quantile-narrowed range clipped to the original bounds."""
    values = np.array(
        [
            scored_run.run.sampled_values[parameter_range.name]
            for scored_run in inference.accepted_runs
        ],
        dtype=np.float64,
    )
    low = float(np.quantile(values, options.range_quantile_low))
    high = float(np.quantile(values, options.range_quantile_high))
    spread = high - low
    original_width = parameter_range.high - parameter_range.low
    padding_basis = spread if spread > 0 else original_width
    padding = padding_basis * options.range_padding_fraction
    return ParameterRange(
        parameter_range.name,
        max(parameter_range.low, low - padding),
        min(parameter_range.high, high + padding),
    )


def _validate_probability(value: float, name: str) -> None:
    """Require a finite probability in the closed unit interval."""
    if not isfinite(value) or value < 0 or value > 1:
        raise ValueError(f"{name} must be in [0, 1]")
