"""Tests for ABC-SMC calibration orchestration."""

from __future__ import annotations

import json
from pathlib import Path

from indoeuropop.analysis.abc_smc import ABCSMCOptions
from indoeuropop.data.targets import TargetDataset, TargetObservation
from indoeuropop.models import PopulationState, SimulationParameters
from indoeuropop.orchestration.abc_smc import (
    ABCSMCOutputPaths,
    abc_smc_artifacts,
    abc_smc_experiment_manifest,
    abc_smc_scored_runs,
    run_abc_smc_workflow,
)
from indoeuropop.orchestration.sweeps import ParameterRange, SweepSpec


def test_abc_smc_workflow_writes_outputs_and_manifest(tmp_path: Path) -> None:
    """The SMC workflow should materialize outputs and provenance."""
    config_path = tmp_path / "sweep.toml"
    targets_path = tmp_path / "targets.csv"
    output_dir = tmp_path / "outputs"
    config_path.write_text("[sweep]\nsample_count = 3\n", encoding="utf-8")
    targets_path.write_text("targets\n", encoding="utf-8")

    result = run_abc_smc_workflow(
        _spec(),
        _targets(),
        options=ABCSMCOptions(generation_count=2, acceptance_count=1),
        paths=ABCSMCOutputPaths(
            config=config_path,
            targets=targets_path,
            generations_csv=output_dir / "generations.csv",
            final_samples_csv=output_dir / "samples.csv",
            final_summary_csv=output_dir / "summary.csv",
            inference_report_md=output_dir / "report.md",
            posterior_predictive_csv=output_dir / "posterior.csv",
            posterior_predictive_report_md=output_dir / "posterior.md",
            posterior_predictive_plot=output_dir / "posterior.png",
            holdout_targets=targets_path,
            holdout_posterior_predictive_csv=output_dir / "holdout.csv",
            holdout_posterior_predictive_report_md=output_dir / "holdout.md",
            holdout_posterior_predictive_plot=output_dir / "holdout.png",
            manifest_json=output_dir / "manifest.json",
        ),
        manifest_metadata={"scenario": "synthetic-smc"},
        holdout_targets=_holdout_targets(),
    )
    manifest_payload = json.loads((output_dir / "manifest.json").read_text())

    assert len(result.inference.generations) == 2
    assert result.posterior_predictive is not None
    assert result.holdout_posterior_predictive is not None
    assert result.generations_csv_path == output_dir / "generations.csv"
    assert result.final_samples_csv_path == output_dir / "samples.csv"
    assert result.final_summary_csv_path == output_dir / "summary.csv"
    assert result.inference_report_md_path == output_dir / "report.md"
    assert result.posterior_predictive_csv_path == output_dir / "posterior.csv"
    assert result.holdout_posterior_predictive_csv_path == output_dir / "holdout.csv"
    assert result.manifest_json_path == output_dir / "manifest.json"
    assert "generation" in (output_dir / "generations.csv").read_text(encoding="utf-8")
    assert "accepted_rank" in (output_dir / "samples.csv").read_text(encoding="utf-8")
    assert "# ABC-SMC Calibration" in (output_dir / "report.md").read_text(
        encoding="utf-8"
    )
    assert (output_dir / "posterior.png").exists()
    assert "# ABC-SMC Holdout" in (output_dir / "holdout.md").read_text(
        encoding="utf-8"
    )
    assert (output_dir / "holdout.png").exists()
    assert result.manifest is not None
    assert manifest_payload["metadata"]["generation_count"] == "2"
    assert manifest_payload["metadata"]["scenario"] == "synthetic-smc"
    assert manifest_payload["metadata"]["posterior_predictive_observation_count"] == "1"
    assert (
        manifest_payload["metadata"]["holdout_posterior_predictive_observation_count"]
        == "1"
    )
    assert {artifact["name"] for artifact in manifest_payload["artifacts"]} == {
        "config",
        "targets",
        "generations_csv",
        "final_samples_csv",
        "final_summary_csv",
        "inference_report_md",
        "posterior_predictive_csv",
        "posterior_predictive_report_md",
        "posterior_predictive_plot",
        "holdout_targets",
        "holdout_posterior_predictive_csv",
        "holdout_posterior_predictive_report_md",
        "holdout_posterior_predictive_plot",
    }


def test_abc_smc_workflow_supports_in_memory_execution() -> None:
    """Programmatic SMC calibration should not require output paths."""
    result = run_abc_smc_workflow(
        _spec(sample_count=2),
        _targets(),
        options=ABCSMCOptions(generation_count=1, acceptance_count=1),
    )

    assert result.inference.total_candidate_count == 2
    assert result.artifacts == ()
    assert result.manifest is None
    assert result.posterior_predictive is not None


def test_abc_smc_manifest_records_generation_metadata() -> None:
    """Programmatic manifests should include threshold-schedule metadata."""
    result = run_abc_smc_workflow(
        _spec(sample_count=2),
        _targets(),
        options=ABCSMCOptions(generation_count=1, acceptance_count=1),
    )
    manifest = abc_smc_experiment_manifest(
        result.inference,
        runs=abc_smc_scored_runs(result.inference),
        metadata={"note": "review"},
    )

    assert abc_smc_artifacts(ABCSMCOutputPaths()) == ()
    assert len(abc_smc_scored_runs(result.inference)) == 2
    assert manifest.name == "abc-smc-calibration"
    assert manifest.metadata["generation_count"] == "1"
    assert manifest.metadata["note"] == "review"


def _spec(sample_count: int = 3) -> SweepSpec:
    """Return one small sweep spec for SMC workflow tests."""
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
    """Return synthetic targets compatible with the SMC workflow spec."""
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
                citation="Synthetic SMC workflow target",
            )
        ]
    )


def _holdout_targets() -> TargetDataset:
    """Return synthetic holdout targets compatible with the SMC workflow spec."""
    return TargetDataset.from_rows(
        [
            TargetObservation(
                status="synthetic",
                region="britain",
                source="steppe",
                time_bce=2900,
                mean=0.06,
                uncertainty=0.04,
                citation_key="synthetic-holdout",
                citation="Synthetic SMC workflow holdout target",
            )
        ]
    )
