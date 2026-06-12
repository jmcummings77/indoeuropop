"""Tests for ABC rejection inference orchestration."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from indoeuropop.analysis.inference import ABCRejectionOptions
from indoeuropop.data.targets import TargetDataset, TargetObservation
from indoeuropop.models import PopulationState, SimulationParameters
from indoeuropop.orchestration.inference import (
    ABCRejectionOutputPaths,
    abc_rejection_artifacts,
    abc_rejection_experiment_manifest,
    run_abc_rejection_workflow,
    score_accepted_runs_against_targets,
)
from indoeuropop.orchestration.sweeps import ParameterRange, SweepSpec


def test_abc_rejection_workflow_writes_outputs_and_manifest(tmp_path: Path) -> None:
    """The inference workflow should materialize CSV, Markdown, and manifest files."""
    config_path = tmp_path / "sweep.toml"
    targets_path = tmp_path / "targets.csv"
    output_dir = tmp_path / "outputs"
    config_path.write_text("[sweep]\nsample_count = 3\n", encoding="utf-8")
    targets_path.write_text("targets\n", encoding="utf-8")

    result = run_abc_rejection_workflow(
        _spec(),
        _targets(),
        options=ABCRejectionOptions(acceptance_count=2),
        paths=ABCRejectionOutputPaths(
            config=config_path,
            targets=targets_path,
            accepted_samples_csv=output_dir / "accepted.csv",
            posterior_summary_csv=output_dir / "summary.csv",
            inference_report_md=output_dir / "report.md",
            manifest_json=output_dir / "manifest.json",
        ),
        manifest_metadata={"scenario": "synthetic"},
    )
    manifest_payload = json.loads((output_dir / "manifest.json").read_text())

    assert result.inference.accepted_count == 2
    assert result.accepted_samples_csv_path == output_dir / "accepted.csv"
    assert result.posterior_summary_csv_path == output_dir / "summary.csv"
    assert result.inference_report_md_path == output_dir / "report.md"
    assert result.manifest is not None
    assert "accepted_rank" in (output_dir / "accepted.csv").read_text(encoding="utf-8")
    assert "migration_rate" in (output_dir / "summary.csv").read_text(encoding="utf-8")
    assert "# ABC Rejection Inference" in (output_dir / "report.md").read_text(
        encoding="utf-8"
    )
    assert manifest_payload["metadata"]["accepted_count"] == "2"
    assert manifest_payload["metadata"]["scenario"] == "synthetic"
    assert {artifact["name"] for artifact in manifest_payload["artifacts"]} == {
        "config",
        "targets",
        "accepted_samples_csv",
        "posterior_summary_csv",
        "inference_report_md",
    }


def test_abc_rejection_workflow_supports_in_memory_execution() -> None:
    """Programmatic inference should not require output paths."""
    result = run_abc_rejection_workflow(_spec(sample_count=2), _targets())

    assert result.inference.candidate_count == 2
    assert result.posterior_predictive is not None
    assert result.posterior_predictive.observation_count == 1
    assert result.artifacts == ()
    assert result.manifest is None


def test_abc_rejection_workflow_writes_posterior_predictive_outputs(
    tmp_path: Path,
) -> None:
    """Inference workflows should materialize calibration and holdout diagnostics."""
    config_path = tmp_path / "sweep.toml"
    targets_path = tmp_path / "targets.csv"
    holdout_path = tmp_path / "holdout.csv"
    output_dir = tmp_path / "outputs"
    config_path.write_text("[sweep]\nsample_count = 3\n", encoding="utf-8")
    targets_path.write_text("targets\n", encoding="utf-8")
    holdout_path.write_text("holdout\n", encoding="utf-8")

    result = run_abc_rejection_workflow(
        _spec(),
        _targets(),
        options=ABCRejectionOptions(acceptance_count=2),
        paths=ABCRejectionOutputPaths(
            config=config_path,
            targets=targets_path,
            posterior_predictive_csv=output_dir / "posterior.csv",
            posterior_predictive_report_md=output_dir / "posterior.md",
            posterior_predictive_plot=output_dir / "posterior.png",
            holdout_targets=holdout_path,
            holdout_posterior_predictive_csv=output_dir / "holdout.csv",
            holdout_posterior_predictive_report_md=output_dir / "holdout.md",
            holdout_posterior_predictive_plot=output_dir / "holdout.png",
            manifest_json=output_dir / "manifest.json",
        ),
        holdout_targets=_holdout_targets(),
    )
    manifest_payload = json.loads((output_dir / "manifest.json").read_text())

    assert result.posterior_predictive is not None
    assert result.holdout_posterior_predictive is not None
    assert result.posterior_predictive_csv_path == output_dir / "posterior.csv"
    assert result.holdout_posterior_predictive_csv_path == output_dir / "holdout.csv"
    assert "prediction_mean" in (output_dir / "posterior.csv").read_text(
        encoding="utf-8"
    )
    assert "# Holdout Posterior Predictive Diagnostics" in (
        output_dir / "holdout.md"
    ).read_text(encoding="utf-8")
    assert (output_dir / "posterior.png").exists()
    assert (output_dir / "holdout.png").exists()
    assert manifest_payload["metadata"]["posterior_predictive_observation_count"] == "1"
    assert (
        manifest_payload["metadata"]["holdout_posterior_predictive_observation_count"]
        == "1"
    )
    assert {artifact["name"] for artifact in manifest_payload["artifacts"]} == {
        "config",
        "targets",
        "posterior_predictive_csv",
        "posterior_predictive_report_md",
        "posterior_predictive_plot",
        "holdout_targets",
        "holdout_posterior_predictive_csv",
        "holdout_posterior_predictive_report_md",
        "holdout_posterior_predictive_plot",
    }


def test_abc_rejection_artifacts_can_be_empty() -> None:
    """Artifact collection should support in-memory inference."""
    assert abc_rejection_artifacts(ABCRejectionOutputPaths()) == ()


def test_abc_rejection_manifest_records_acceptance_metadata() -> None:
    """Programmatic manifests should expose acceptance and best-run metadata."""
    result = run_abc_rejection_workflow(
        _spec(sample_count=2),
        _targets(),
        options=ABCRejectionOptions(acceptance_count=1),
    )

    manifest = abc_rejection_experiment_manifest(
        result.inference,
        runs=tuple(scored.run for scored in result.inference.ranked_runs),
        metadata={"note": "review"},
    )

    assert manifest.name == "abc-rejection-inference"
    assert manifest.metadata["accepted_count"] == "1"
    assert manifest.metadata["candidate_count"] == "2"
    assert manifest.metadata["note"] == "review"


def test_score_accepted_runs_against_targets_rejects_empty_runs() -> None:
    """Holdout re-scoring requires at least one accepted run."""
    with pytest.raises(ValueError, match="accepted_runs"):
        score_accepted_runs_against_targets(_spec(), (), _targets())


def _spec(sample_count: int = 3) -> SweepSpec:
    """Return one small sweep spec for inference workflow tests."""
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
            )
        ]
    )


def _holdout_targets() -> TargetDataset:
    """Return synthetic holdout targets compatible with the workflow test spec."""
    return TargetDataset.from_rows(
        [
            TargetObservation(
                status="synthetic",
                region="britain",
                source="steppe",
                time_bce=2900,
                mean=0.07,
                uncertainty=0.04,
                citation_key="synthetic-holdout",
                citation="Synthetic holdout target",
            )
        ]
    )
