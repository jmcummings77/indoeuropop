"""Tests for seeded parameter sweeps."""

from typing import Any, cast

import numpy as np
import pytest

from indoeuropop.models import PopulationState, SimulationParameters
from indoeuropop.models.parameterization import ParameterSet, RegionParameters
from indoeuropop.orchestration.sweeps import (
    ParameterRange,
    SweepSpec,
    latin_hypercube_samples,
    parameters_with_overrides,
    run_parameter_sweep,
)
from indoeuropop.simulation.events import MigrationPulse, SimulationSchedule


def test_parameter_range_scales_unit_values() -> None:
    """ParameterRange should map unit values onto closed numeric intervals."""
    parameter_range = ParameterRange("migration_rate", 0.1, 0.3)

    assert parameter_range.scale(0) == pytest.approx(0.1)
    assert parameter_range.scale(0.5) == pytest.approx(0.2)
    assert parameter_range.scale(1) == pytest.approx(0.3)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"name": "unknown"},
        {"low": float("nan")},
        {"high": float("inf")},
        {"low": 0.3, "high": 0.1},
    ],
)
def test_parameter_range_rejects_invalid_ranges(kwargs: dict[str, object]) -> None:
    """Invalid parameter range declarations should fail early."""
    valid_kwargs: dict[str, object] = {
        "name": "migration_rate",
        "low": 0.0,
        "high": 0.1,
    }
    valid_kwargs.update(kwargs)

    with pytest.raises(ValueError):
        ParameterRange(**cast(Any, valid_kwargs))


def test_parameter_range_rejects_invalid_unit_values() -> None:
    """Scaling should only accept unit interval inputs."""
    with pytest.raises(ValueError):
        ParameterRange("migration_rate", 0, 1).scale(1.1)


def test_latin_hypercube_samples_are_seeded_and_stratified() -> None:
    """Latin-hypercube samples should be reproducible and cover each bin."""
    ranges = (
        ParameterRange("migration_rate", 0.0, 1.0),
        ParameterRange("epidemic_mortality_rate", 0.0, 1.0),
    )

    first = latin_hypercube_samples(ranges, sample_count=4, seed=11)
    second = latin_hypercube_samples(ranges, sample_count=4, seed=11)

    assert first == second
    assert len(first) == 4
    for parameter_name in ("migration_rate", "epidemic_mortality_rate"):
        bins = sorted(int(sample[parameter_name] * 4) for sample in first)
        assert bins == [0, 1, 2, 3]


@pytest.mark.parametrize("sample_count", [0, -1])
def test_latin_hypercube_samples_rejects_bad_sample_counts(sample_count: int) -> None:
    """Sample count must be positive for direct sampling."""
    with pytest.raises(ValueError):
        latin_hypercube_samples(
            (ParameterRange("migration_rate", 0.0, 0.1),),
            sample_count=sample_count,
            seed=7,
        )


def test_latin_hypercube_samples_rejects_empty_ranges() -> None:
    """At least one parameter range is required for sampling."""
    with pytest.raises(ValueError):
        latin_hypercube_samples((), sample_count=2, seed=7)


def test_sweep_spec_rejects_bad_dimensions() -> None:
    """SweepSpec should reject empty ranges, duplicates, and bad sample counts."""
    state = PopulationState({"britain": {"local": 100, "steppe": 0}})
    parameters = SimulationParameters()

    with pytest.raises(ValueError, match="sample_count"):
        SweepSpec(
            state,
            parameters,
            (ParameterRange("migration_rate", 0, 1),),
            sample_count=0,
        )
    with pytest.raises(ValueError, match="must not be empty"):
        SweepSpec(state, parameters, ())
    with pytest.raises(ValueError, match="duplicate"):
        SweepSpec(
            state,
            parameters,
            (
                ParameterRange("migration_rate", 0, 0.1),
                ParameterRange("migration_rate", 0, 0.2),
            ),
        )


def test_run_parameter_sweep_returns_summaries() -> None:
    """A deterministic sweep should return sampled parameters and summaries."""
    spec = SweepSpec(
        initial_state=PopulationState({"britain": {"local": 1000, "steppe": 0}}),
        base_parameters=SimulationParameters(migration_rate=0),
        parameter_ranges=(ParameterRange("migration_rate", 0.001, 0.003),),
        start_bce=3000,
        end_bce=2900,
        step_years=50,
        sample_count=3,
        seed=19,
        region="britain",
        schedule=SimulationSchedule(
            migration_pulses=(
                MigrationPulse(
                    region="britain",
                    start_bce=3000,
                    end_bce=2900,
                    annual_rate=0.001,
                ),
            )
        ),
        parameter_set=ParameterSet(
            region_parameters={"britain": RegionParameters(violence_mortality_rate=0.0)}
        ),
    )

    runs = run_parameter_sweep(spec)

    assert tuple(run.index for run in runs) == (0, 1, 2)
    assert all("migration_rate" in run.sampled_values for run in runs)
    assert all(run.parameters.migration_rate >= 0.001 for run in runs)
    assert all(run.summary.final_ancestry > 0 for run in runs)
    np.testing.assert_allclose(
        [run.summary.start_bce for run in runs],
        [3000, 3000, 3000],
    )


def test_parameters_with_overrides_updates_parameter_bundle() -> None:
    """Sampled values should produce a validated SimulationParameters object."""
    parameters = parameters_with_overrides(
        SimulationParameters(migration_rate=0.001),
        {"migration_rate": 0.002, "climate_stress": 0.1},
    )

    assert parameters.migration_rate == 0.002
    assert parameters.climate_stress == 0.1
