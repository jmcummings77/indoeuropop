"""Tests for sequential ABC-style calibration helpers."""

from __future__ import annotations

from typing import Any, cast

import pytest

from indoeuropop.analysis.abc_smc import (
    ABCSMCGeneration,
    ABCSMCOptions,
    ABCSMCResult,
    run_abc_smc_inference,
)
from indoeuropop.data.targets import TargetDataset, TargetObservation
from indoeuropop.models import PopulationState, SimulationParameters
from indoeuropop.orchestration.sweeps import ParameterRange, SweepSpec


def test_abc_smc_runs_multiple_generations_and_narrows_ranges() -> None:
    """SMC calibration should preserve generations and narrow proposals."""
    result = run_abc_smc_inference(
        _spec(sample_count=5),
        _targets(),
        ABCSMCOptions(generation_count=2, acceptance_count=2, seed_stride=11),
    )

    assert len(result.generations) == 2
    assert result.total_candidate_count == 10
    assert result.final_generation.generation_index == 1
    assert result.final_inference.accepted_count == 2
    assert len(result.threshold_schedule) == 2
    assert result.generations[0].spec.seed == 17
    assert result.generations[1].spec.seed == 28
    first_range = result.generations[0].parameter_ranges[0]
    second_range = result.generations[1].parameter_ranges[0]
    assert second_range.low >= first_range.low
    assert second_range.high <= first_range.high
    assert result.generations[0].best_metric_value >= 0


def test_abc_smc_supports_default_options_and_single_sample_padding() -> None:
    """Default sampling and one accepted sample should still produce next ranges."""
    result = run_abc_smc_inference(
        _spec(sample_count=3),
        _targets(),
        ABCSMCOptions(generation_count=2, acceptance_count=1),
    )

    assert result.options.sample_count is None
    assert result.generations[0].inference.accepted_count == 1
    assert result.generations[1].parameter_ranges[0].high > (
        result.generations[1].parameter_ranges[0].low
    )


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"fit_metric": "unknown"}, "unsupported"),
        ({"generation_count": 0}, "generation_count"),
        ({"sample_count": 0}, "sample_count"),
        ({"acceptance_count": 0}, "acceptance_count"),
        ({"acceptance_quantile": 0.0}, "acceptance_quantile"),
        ({"acceptance_quantile": 1.1}, "acceptance_quantile"),
        ({"seed_stride": 0}, "seed_stride"),
        ({"range_quantile_low": -0.1}, "range_quantile_low"),
        ({"range_quantile_high": 1.1}, "range_quantile_high"),
        (
            {"range_quantile_low": 0.8, "range_quantile_high": 0.2},
            "range_quantile_low",
        ),
        ({"range_padding_fraction": -0.1}, "range_padding_fraction"),
        ({"range_padding_fraction": float("nan")}, "range_padding_fraction"),
    ],
)
def test_abc_smc_options_validate_inputs(kwargs: dict[str, object], match: str) -> None:
    """Invalid SMC controls should fail at construction."""
    with pytest.raises(ValueError, match=match):
        ABCSMCOptions(**cast(Any, kwargs))


def test_abc_smc_generation_and_result_validate_manual_construction() -> None:
    """Manual SMC result objects should reject empty or impossible shapes."""
    result = run_abc_smc_inference(
        _spec(sample_count=2),
        _targets(),
        ABCSMCOptions(generation_count=1, acceptance_count=1),
    )
    generation = result.generations[0]

    with pytest.raises(ValueError, match="generation_index"):
        ABCSMCGeneration(
            -1,
            generation.spec,
            generation.inference,
            generation.parameter_ranges,
        )
    with pytest.raises(ValueError, match="parameter_ranges"):
        ABCSMCGeneration(0, generation.spec, generation.inference, ())
    with pytest.raises(ValueError, match="generations"):
        ABCSMCResult(result.options, ())


def _spec(sample_count: int = 4) -> SweepSpec:
    """Return one small sweep spec for SMC tests."""
    return SweepSpec(
        initial_state=PopulationState({"britain": {"local": 1000, "steppe": 20}}),
        base_parameters=SimulationParameters(migration_rate=0.0),
        parameter_ranges=(ParameterRange("migration_rate", 0.001, 0.004),),
        start_bce=3000,
        end_bce=2900,
        step_years=50,
        sample_count=sample_count,
        seed=17,
        source="steppe",
        region="britain",
    )


def _targets() -> TargetDataset:
    """Return synthetic targets compatible with the SMC test spec."""
    return TargetDataset.from_rows(
        [
            TargetObservation(
                status="synthetic",
                region="britain",
                source="steppe",
                time_bce=2950,
                mean=0.04,
                uncertainty=0.03,
                citation_key="synthetic",
                citation="Synthetic SMC target",
            )
        ]
    )
