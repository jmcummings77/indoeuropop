"""Tests for migration-pulse structural candidate workflows."""

from __future__ import annotations

import json
from pathlib import Path

from indoeuropop.analysis.inference import ABCRejectionOptions
from indoeuropop.analysis.structural_candidates import MigrationPulseCandidate
from indoeuropop.data.targets import TargetDataset, TargetObservation
from indoeuropop.models import PopulationState, SimulationParameters
from indoeuropop.orchestration.structural_candidates import (
    MigrationPulseCandidateOutputPaths,
    migration_pulse_candidate_artifacts,
    migration_pulse_candidate_manifest,
    run_migration_pulse_candidate_workflow,
)
from indoeuropop.orchestration.sweeps import ParameterRange, SweepSpec


def test_migration_pulse_candidate_workflow_writes_artifacts(
    tmp_path: Path,
) -> None:
    """Structural candidate workflows should write reports and a manifest."""
    config_path = tmp_path / "base.toml"
    targets_path = tmp_path / "targets.csv"
    output_dir = tmp_path / "outputs"
    config_path.write_text("[sweep]\nsample_count = 2\n", encoding="utf-8")
    targets_path.write_text("targets\n", encoding="utf-8")

    result = run_migration_pulse_candidate_workflow(
        _spec(),
        _targets(),
        _candidate(),
        options=ABCRejectionOptions(acceptance_count=1),
        paths=MigrationPulseCandidateOutputPaths(
            config=config_path,
            targets=targets_path,
            candidate_config_toml=output_dir / "candidate.toml",
            baseline_posterior_predictive_csv=output_dir / "baseline.csv",
            baseline_posterior_predictive_report_md=output_dir / "baseline.md",
            baseline_posterior_predictive_plot=output_dir / "baseline.png",
            candidate_posterior_predictive_csv=output_dir / "candidate.csv",
            candidate_posterior_predictive_report_md=output_dir / "candidate.md",
            candidate_posterior_predictive_plot=output_dir / "candidate.png",
            comparison_report_md=output_dir / "comparison.md",
            manifest_json=output_dir / "manifest.json",
        ),
        manifest_metadata={"scenario": "synthetic"},
    )
    manifest_payload = json.loads((output_dir / "manifest.json").read_text())

    assert result.candidate.name == "early-central-europe"
    assert result.baseline.inference.accepted_count == 1
    assert result.candidate_result.inference.accepted_count == 1
    assert result.metric_delta.focus_observation_index == 0
    assert result.candidate_config_toml_path == output_dir / "candidate.toml"
    assert result.comparison_report_md_path == output_dir / "comparison.md"
    assert "central_europe" in (output_dir / "candidate.toml").read_text(
        encoding="utf-8"
    )
    assert "prediction_mean" in (output_dir / "baseline.csv").read_text(
        encoding="utf-8"
    )
    assert "# Posterior Predictive Diagnostics" in (
        output_dir / "candidate.md"
    ).read_text(encoding="utf-8")
    assert "# Migration Pulse Candidate" in (output_dir / "comparison.md").read_text(
        encoding="utf-8"
    )
    assert (output_dir / "baseline.png").exists()
    assert (output_dir / "candidate.png").exists()
    assert result.manifest is not None
    assert manifest_payload["metadata"]["candidate_name"] == "early-central-europe"
    assert manifest_payload["metadata"]["scenario"] == "synthetic"
    assert {artifact["name"] for artifact in manifest_payload["artifacts"]} == {
        "config",
        "targets",
        "candidate_config_toml",
        "baseline_posterior_predictive_csv",
        "baseline_posterior_predictive_report_md",
        "baseline_posterior_predictive_plot",
        "candidate_posterior_predictive_csv",
        "candidate_posterior_predictive_report_md",
        "candidate_posterior_predictive_plot",
        "comparison_report_md",
    }


def test_migration_pulse_candidate_workflow_supports_in_memory_execution() -> None:
    """Candidate comparison should not require output paths."""
    result = run_migration_pulse_candidate_workflow(
        _spec(sample_count=2),
        _targets(),
        _candidate(),
        options=ABCRejectionOptions(acceptance_count=1),
    )

    assert result.artifacts == ()
    assert result.manifest is None
    assert result.candidate_config_toml_path is None
    assert result.baseline.posterior_predictive is not None
    assert result.candidate_result.posterior_predictive is not None


def test_migration_pulse_candidate_artifacts_can_be_empty() -> None:
    """Artifact collection should support in-memory candidate checks."""
    assert (
        migration_pulse_candidate_artifacts(MigrationPulseCandidateOutputPaths()) == ()
    )


def test_migration_pulse_candidate_manifest_records_candidate_metadata() -> None:
    """Programmatic manifests should expose candidate and delta metadata."""
    result = run_migration_pulse_candidate_workflow(
        _spec(sample_count=2),
        _targets(),
        _candidate(),
        options=ABCRejectionOptions(acceptance_count=1),
    )

    manifest = migration_pulse_candidate_manifest(
        _candidate(),
        result.metric_delta,
        runs=tuple(scored.run for scored in result.baseline.inference.ranked_runs),
        metadata={"note": "manual"},
    )

    assert manifest.name == "migration-pulse-candidate"
    assert manifest.metadata["candidate_region"] == "central_europe"
    assert manifest.metadata["note"] == "manual"


def _spec(sample_count: int = 3) -> SweepSpec:
    """Return one small central-Europe sweep spec."""
    return SweepSpec(
        initial_state=PopulationState({"central_europe": {"local": 1000, "steppe": 5}}),
        base_parameters=SimulationParameters(migration_rate=0.0),
        parameter_ranges=(ParameterRange("migration_rate", 0.0, 0.001),),
        start_bce=3100,
        end_bce=2900,
        step_years=50,
        sample_count=sample_count,
        seed=19,
        source="steppe",
        region="central_europe",
    )


def _targets() -> TargetDataset:
    """Return a synthetic target compatible with the workflow test spec."""
    return TargetDataset.from_rows(
        [
            TargetObservation(
                status="synthetic",
                region="central_europe",
                source="steppe",
                time_bce=2950,
                mean=0.2,
                uncertainty=0.1,
                citation_key="synthetic",
                citation="Synthetic structural target",
                note="requested_group_id=Germany_Tiefbrunn_CordedWare-1",
            )
        ]
    )


def _candidate() -> MigrationPulseCandidate:
    """Return a small additive pulse candidate for tests."""
    return MigrationPulseCandidate(
        name="early-central-europe",
        region="central_europe",
        start_bce=3050,
        end_bce=2925,
        annual_rate=0.0002,
    )
