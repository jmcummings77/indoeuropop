"""Tests for sweep and sensitivity CSV exports."""

from pathlib import Path

import pytest

from indoeuropop.analysis.fitting import ScoredSweepRun, score_target_fit
from indoeuropop.analysis.sensitivity import SensitivityResult
from indoeuropop.analysis.summary import TrajectorySummary
from indoeuropop.data.targets import TargetComparison, TargetObservation
from indoeuropop.models import SimulationParameters
from indoeuropop.orchestration.sweeps import SweepRun
from indoeuropop.reporting.sweep_reporting import (
    scored_sweep_run_fieldnames,
    scored_sweep_run_rows,
    scored_sweep_runs_to_csv,
    sensitivity_result_rows,
    sensitivity_results_to_csv,
    sweep_run_fieldnames,
    sweep_run_rows,
    sweep_runs_to_csv,
    write_scored_sweep_runs_csv,
    write_sensitivity_csv,
    write_sweep_runs_csv,
)


def _run(
    index: int,
    sampled_values: dict[str, float],
    *,
    final_ancestry: float = 0.25,
    is_extinct: bool = False,
) -> SweepRun:
    """Return one sweep run for reporting tests."""
    return SweepRun(
        index=index,
        sampled_values=sampled_values,
        parameters=SimulationParameters(),
        summary=TrajectorySummary(
            source="steppe",
            region="britain",
            start_bce=3000,
            end_bce=2900,
            initial_ancestry=0.1,
            final_ancestry=final_ancestry,
            ancestry_delta=final_ancestry - 0.1,
            ancestry_slope_per_century=final_ancestry - 0.1,
            min_total_population=0.0 if is_extinct else 90.0,
            final_total_population=0.0 if is_extinct else 100.0,
            is_extinct=is_extinct,
        ),
    )


def _scored_run(
    index: int,
    sampled_values: dict[str, float],
    *,
    predicted: float = 0.2,
) -> ScoredSweepRun:
    """Return one scored sweep run for reporting tests."""
    observation = TargetObservation(
        status="synthetic",
        region="britain",
        source="steppe",
        time_bce=2900,
        mean=0.1,
        uncertainty=0.05,
        citation_key="synthetic",
        citation="Synthetic target",
    )
    return ScoredSweepRun(
        run=_run(index, sampled_values, final_ancestry=predicted),
        fit=score_target_fit((TargetComparison(observation, predicted),)),
    )


def test_sweep_run_rows_and_csv_use_stable_schema() -> None:
    """Sweep runs should serialize with sorted sampled parameter fields."""
    runs = (
        _run(0, {"migration_rate": 0.002, "climate_stress": 0.1}),
        _run(
            1,
            {"migration_rate": 0.003, "climate_stress": 0.2},
            is_extinct=True,
        ),
    )

    fieldnames = sweep_run_fieldnames(runs)
    rows = sweep_run_rows(runs)
    csv_text = sweep_runs_to_csv(runs)

    assert fieldnames[:3] == (
        "index",
        "sampled_climate_stress",
        "sampled_migration_rate",
    )
    assert rows[0]["sampled_climate_stress"] == "0.1"
    assert rows[0]["summary_region"] == "britain"
    assert rows[1]["summary_is_extinct"] == "true"
    assert csv_text.startswith("index,sampled_climate_stress,sampled_migration_rate,")
    assert "steppe,britain" in csv_text


def test_write_sweep_runs_csv_creates_parent_directory(tmp_path: Path) -> None:
    """Sweep CSV writers should create parent directories."""
    output_path = tmp_path / "sweeps" / "runs.csv"

    returned_path = write_sweep_runs_csv(
        (_run(0, {"migration_rate": 0.002}),),
        output_path,
    )

    assert returned_path == output_path
    assert output_path.read_text(encoding="utf-8").startswith(
        "index,sampled_migration_rate"
    )


def test_scored_sweep_run_rows_and_csv_use_stable_schema() -> None:
    """Ranked target-fit rows should include parameters, fit, and summaries."""
    scored_runs = (
        _scored_run(4, {"migration_rate": 0.002, "climate_stress": 0.1}),
        _scored_run(2, {"migration_rate": 0.003, "climate_stress": 0.2}),
    )

    fieldnames = scored_sweep_run_fieldnames(scored_runs)
    rows = scored_sweep_run_rows(scored_runs)
    csv_text = scored_sweep_runs_to_csv(scored_runs)

    assert fieldnames[:4] == (
        "rank",
        "run_index",
        "sampled_climate_stress",
        "sampled_migration_rate",
    )
    assert rows[0]["rank"] == "1"
    assert rows[0]["run_index"] == "4"
    assert rows[0]["fit_observation_count"] == "1"
    assert rows[0]["fit_chi_square"] == "4"
    assert rows[0]["summary_final_ancestry"] == "0.2"
    assert csv_text.startswith("rank,run_index,sampled_climate_stress,")


def test_write_scored_sweep_runs_csv_creates_parent_directory(
    tmp_path: Path,
) -> None:
    """Target-fit CSV writers should create parent directories."""
    output_path = tmp_path / "sweeps" / "target-fit.csv"

    returned_path = write_scored_sweep_runs_csv(
        (_scored_run(0, {"migration_rate": 0.002}),),
        output_path,
    )

    assert returned_path == output_path
    assert output_path.read_text(encoding="utf-8").startswith(
        "rank,run_index,sampled_migration_rate"
    )


@pytest.mark.parametrize(
    "runs,match",
    [
        ((), "at least one"),
        ((_run(0, {}),), "sampled parameter"),
        (
            (
                _run(0, {"migration_rate": 0.002}),
                _run(1, {"climate_stress": 0.2}),
            ),
            "same sampled",
        ),
    ],
)
def test_sweep_run_exports_reject_malformed_runs(
    runs: tuple[SweepRun, ...],
    match: str,
) -> None:
    """Malformed sweep collections should fail before CSV export."""
    with pytest.raises(ValueError, match=match):
        sweep_runs_to_csv(runs)


def test_scored_sweep_run_exports_reject_empty_runs() -> None:
    """Target-fit CSV export requires at least one scored run."""
    with pytest.raises(ValueError, match="at least one"):
        scored_sweep_runs_to_csv(())


def test_sensitivity_result_rows_and_csv_use_fixed_schema() -> None:
    """Sensitivity diagnostics should serialize to a fixed CSV schema."""
    results = (
        SensitivityResult(
            parameter="migration_rate",
            outcome="final_ancestry",
            pearson_correlation=0.5,
            spearman_correlation=-0.25,
            linear_slope=2.0,
        ),
    )

    rows = sensitivity_result_rows(results)
    csv_text = sensitivity_results_to_csv(results)

    assert rows == (
        {
            "parameter": "migration_rate",
            "outcome": "final_ancestry",
            "pearson_correlation": "0.5",
            "spearman_correlation": "-0.25",
            "absolute_spearman": "0.25",
            "linear_slope": "2",
        },
    )
    assert csv_text.splitlines()[0] == (
        "parameter,outcome,pearson_correlation,spearman_correlation,"
        "absolute_spearman,linear_slope"
    )


def test_sensitivity_results_to_csv_allows_empty_results() -> None:
    """Sensitivity CSV can still emit a header for empty result collections."""
    assert sensitivity_results_to_csv(()) == (
        "parameter,outcome,pearson_correlation,spearman_correlation,"
        "absolute_spearman,linear_slope\n"
    )


def test_write_sensitivity_csv_creates_parent_directory(tmp_path: Path) -> None:
    """Sensitivity CSV writers should create parent directories."""
    output_path = tmp_path / "sweeps" / "sensitivity.csv"

    returned_path = write_sensitivity_csv((), output_path)

    assert returned_path == output_path
    assert output_path.read_text(encoding="utf-8").startswith("parameter,outcome")
