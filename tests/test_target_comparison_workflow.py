"""Tests for deterministic sweep-to-target comparison workflows."""

import json
from pathlib import Path

from indoeuropop.data.targets import TargetDataset, TargetObservation
from indoeuropop.models import PopulationState, SimulationParameters
from indoeuropop.orchestration.sweeps import ParameterRange, SweepSpec
from indoeuropop.orchestration.target_comparison import (
    TargetComparisonOutputPaths,
    run_sweep_run_simulation,
    run_target_comparison_workflow,
    target_comparison_artifacts,
    target_comparison_experiment_manifest,
)


def _spec(sample_count: int = 3) -> SweepSpec:
    """Return one small sweep spec for target-comparison workflow tests."""
    return SweepSpec(
        initial_state=PopulationState({"britain": {"local": 1000, "steppe": 25}}),
        base_parameters=SimulationParameters(migration_rate=0.0),
        parameter_ranges=(ParameterRange("migration_rate", 0.001, 0.003),),
        start_bce=3000,
        end_bce=2900,
        step_years=50,
        sample_count=sample_count,
        seed=17,
        source="steppe",
        region="britain",
    )


def _targets() -> TargetDataset:
    """Return synthetic targets compatible with the workflow test spec."""
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
                citation="Synthetic workflow target",
            ),
            TargetObservation(
                status="synthetic",
                region="britain",
                source="steppe",
                time_bce=2900,
                mean=0.06,
                uncertainty=0.04,
                citation_key="synthetic",
                citation="Synthetic workflow target",
            ),
        ]
    )


def test_run_target_comparison_workflow_writes_outputs_and_manifest(
    tmp_path: Path,
) -> None:
    """The comparison workflow should write fit, residual, plot, and manifest files."""
    config_path = tmp_path / "sweep.toml"
    target_path = tmp_path / "targets.csv"
    output_dir = tmp_path / "outputs"
    config_path.write_text("[sweep]\nsample_count = 3\n", encoding="utf-8")
    target_path.write_text("targets\n", encoding="utf-8")

    result = run_target_comparison_workflow(
        _spec(),
        _targets(),
        paths=TargetComparisonOutputPaths(
            config=config_path,
            targets=target_path,
            sweep_runs_csv=output_dir / "sweep-runs.csv",
            sensitivity_csv=output_dir / "sensitivity.csv",
            target_fit_csv=output_dir / "target-fit.csv",
            target_residuals_csv=output_dir / "target-residuals.csv",
            plot=output_dir / "target-comparison.png",
            manifest_json=output_dir / "manifest.json",
        ),
        fit_metric="root_mean_squared_error",
        manifest_metadata={"scenario": "synthetic"},
    )
    manifest_payload = json.loads((output_dir / "manifest.json").read_text())

    assert len(result.sweep.runs) == 3
    assert result.best_run.fit.observation_count == 2
    assert len(result.best_comparisons) == 2
    assert result.target_residuals_csv_path == output_dir / "target-residuals.csv"
    assert result.plot_path == output_dir / "target-comparison.png"
    assert result.manifest is not None
    assert (
        (output_dir / "target-fit.csv")
        .read_text(encoding="utf-8")
        .startswith("rank,run_index")
    )
    assert "observed_mean" in (output_dir / "target-residuals.csv").read_text(
        encoding="utf-8"
    )
    assert (output_dir / "target-comparison.png").exists()
    assert manifest_payload["metadata"]["best_fit_metric"] == (
        "root_mean_squared_error"
    )
    assert manifest_payload["metadata"]["target_observation_count"] == "2"
    assert manifest_payload["metadata"]["scenario"] == "synthetic"
    assert {artifact["name"] for artifact in manifest_payload["artifacts"]} == {
        "config",
        "targets",
        "sweep_runs_csv",
        "sensitivity_csv",
        "target_fit_csv",
        "target_residuals_csv",
        "target_comparison_plot",
    }


def test_run_sweep_run_simulation_replays_best_parameters() -> None:
    """Best-run replay should return a full trajectory for plotting."""
    result = run_target_comparison_workflow(_spec(sample_count=2), _targets())

    replay = run_sweep_run_simulation(_spec(sample_count=2), result.best_run)

    assert replay.times_bce == result.best_result.times_bce
    assert replay.final_state.ancestry_proportion("steppe", "britain") == (
        result.best_result.final_state.ancestry_proportion("steppe", "britain")
    )


def test_target_comparison_artifacts_can_be_empty() -> None:
    """Artifact collection should support in-memory workflows."""
    assert target_comparison_artifacts(TargetComparisonOutputPaths()) == ()


def test_target_comparison_manifest_records_best_run_metadata() -> None:
    """Programmatic manifests should expose the selected best fit."""
    result = run_target_comparison_workflow(_spec(sample_count=2), _targets())

    manifest = target_comparison_experiment_manifest(
        result.sweep.runs,
        best_run=result.best_run,
        target_count=len(result.best_comparisons),
        fit_metric="chi_square",
        metadata={"note": "review"},
    )

    assert manifest.name == "target-comparison"
    assert manifest.metadata["best_run_index"] == str(result.best_run.run.index)
    assert manifest.metadata["target_observation_count"] == "2"
    assert manifest.metadata["note"] == "review"
