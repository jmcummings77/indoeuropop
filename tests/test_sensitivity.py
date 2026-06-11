"""Tests for sensitivity diagnostics over sweep outputs."""

import pytest

from indoeuropop.analysis.sensitivity import analyze_sensitivity
from indoeuropop.analysis.summary import TrajectorySummary
from indoeuropop.models import SimulationParameters
from indoeuropop.orchestration.sweeps import SweepRun


def _run(
    index: int,
    sampled_values: dict[str, float],
    *,
    final_ancestry: float,
    final_total_population: float = 100.0,
) -> SweepRun:
    """Build a minimal SweepRun for sensitivity tests."""
    return SweepRun(
        index=index,
        sampled_values=sampled_values,
        parameters=SimulationParameters(),
        summary=TrajectorySummary(
            source="steppe",
            region="britain",
            start_bce=3000,
            end_bce=2900,
            initial_ancestry=0.0,
            final_ancestry=final_ancestry,
            ancestry_delta=final_ancestry,
            ancestry_slope_per_century=final_ancestry,
            min_total_population=min(100.0, final_total_population),
            final_total_population=final_total_population,
            is_extinct=final_total_population == 0,
        ),
    )


def test_analyze_sensitivity_ranks_parameter_associations() -> None:
    """Sensitivity analysis should report signed linear and rank associations."""
    runs = (
        _run(
            0,
            {"migration_rate": 0.1, "epidemic_mortality_rate": 0.4},
            final_ancestry=0.1,
        ),
        _run(
            1,
            {"migration_rate": 0.2, "epidemic_mortality_rate": 0.3},
            final_ancestry=0.2,
        ),
        _run(
            2,
            {"migration_rate": 0.3, "epidemic_mortality_rate": 0.2},
            final_ancestry=0.3,
        ),
        _run(
            3,
            {"migration_rate": 0.4, "epidemic_mortality_rate": 0.1},
            final_ancestry=0.4,
        ),
    )

    results = analyze_sensitivity(runs, outcome="final_ancestry")
    by_parameter = {result.parameter: result for result in results}

    assert tuple(result.parameter for result in results) == (
        "migration_rate",
        "epidemic_mortality_rate",
    )
    assert by_parameter["migration_rate"].outcome == "final_ancestry"
    assert by_parameter["migration_rate"].pearson_correlation == pytest.approx(1.0)
    assert by_parameter["migration_rate"].spearman_correlation == pytest.approx(1.0)
    assert by_parameter["migration_rate"].linear_slope == pytest.approx(1.0)
    assert by_parameter["migration_rate"].absolute_spearman == pytest.approx(1.0)
    assert by_parameter["epidemic_mortality_rate"].pearson_correlation == pytest.approx(
        -1.0
    )
    assert by_parameter[
        "epidemic_mortality_rate"
    ].spearman_correlation == pytest.approx(-1.0)
    assert by_parameter["epidemic_mortality_rate"].linear_slope == pytest.approx(-1.0)


def test_analyze_sensitivity_handles_constant_and_tied_values() -> None:
    """Constant sampled parameters or tied outcomes should produce finite zeros."""
    runs = (
        _run(0, {"migration_rate": 0.1, "climate_stress": 0.2}, final_ancestry=0.1),
        _run(1, {"migration_rate": 0.1, "climate_stress": 0.3}, final_ancestry=0.1),
        _run(2, {"migration_rate": 0.1, "climate_stress": 0.4}, final_ancestry=0.2),
    )

    results = analyze_sensitivity(runs)
    by_parameter = {result.parameter: result for result in results}

    assert by_parameter["migration_rate"].pearson_correlation == 0
    assert by_parameter["migration_rate"].spearman_correlation == 0
    assert by_parameter["migration_rate"].linear_slope == 0
    assert by_parameter["climate_stress"].spearman_correlation > 0


def test_analyze_sensitivity_supports_population_outcomes() -> None:
    """Sensitivity can target supported non-ancestry summary fields."""
    runs = (
        _run(0, {"migration_rate": 0.1}, final_ancestry=0.1, final_total_population=90),
        _run(1, {"migration_rate": 0.2}, final_ancestry=0.1, final_total_population=80),
    )

    (result,) = analyze_sensitivity(runs, outcome="final_total_population")

    assert result.parameter == "migration_rate"
    assert result.outcome == "final_total_population"
    assert result.pearson_correlation == pytest.approx(-1.0)


@pytest.mark.parametrize(
    "runs,match",
    [
        ((), "at least one"),
        ((_run(0, {}, final_ancestry=0.1),), "sampled parameter"),
        (
            (
                _run(0, {"migration_rate": 0.1}, final_ancestry=0.1),
                _run(1, {"climate_stress": 0.2}, final_ancestry=0.2),
            ),
            "same sampled",
        ),
    ],
)
def test_analyze_sensitivity_rejects_bad_runs(
    runs: tuple[SweepRun, ...], match: str
) -> None:
    """Malformed sweep run collections should fail clearly."""
    with pytest.raises(ValueError, match=match):
        analyze_sensitivity(runs)


def test_analyze_sensitivity_rejects_unsupported_outcome() -> None:
    """Only documented numeric summary outcomes should be accepted."""
    with pytest.raises(ValueError, match="unsupported"):
        analyze_sensitivity(
            (_run(0, {"migration_rate": 0.1}, final_ancestry=0.1),),
            outcome="is_extinct",
        )


def test_analyze_sensitivity_rejects_non_finite_outcomes() -> None:
    """Non-finite outcome values should fail before metrics are computed."""
    with pytest.raises(ValueError, match="finite"):
        analyze_sensitivity(
            (_run(0, {"migration_rate": 0.1}, final_ancestry=float("nan")),)
        )
