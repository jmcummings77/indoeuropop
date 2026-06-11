"""Tests for deterministic sweep workflow helpers."""

import json
from pathlib import Path

import pytest

from indoeuropop.models import PopulationState, SimulationParameters
from indoeuropop.sensitivity import SensitivityResult
from indoeuropop.sweep_workflows import (
    SweepOutputPaths,
    run_sweep_workflow,
    sweep_experiment_manifest,
    write_sweep_outputs,
)
from indoeuropop.sweeps import ParameterRange, SweepSpec, run_parameter_sweep
from indoeuropop.targets import TargetDataset, TargetObservation


def _spec(sample_count: int = 3) -> SweepSpec:
    """Return one small sweep spec for workflow tests."""
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
    """Return one synthetic target compatible with the workflow test spec."""
    return TargetDataset.from_rows(
        [
            TargetObservation(
                status="synthetic",
                region="britain",
                source="steppe",
                time_bce=2900,
                mean=0.05,
                uncertainty=0.03,
                citation_key="synthetic",
                citation="Synthetic workflow target",
            )
        ]
    )


def test_run_sweep_workflow_writes_outputs_and_manifest(tmp_path: Path) -> None:
    """Sweep workflows should write CSV artifacts before manifest checksums."""
    config_path = tmp_path / "sweep.toml"
    sweep_csv = tmp_path / "outputs" / "sweep-runs.csv"
    sensitivity_csv = tmp_path / "outputs" / "sensitivity.csv"
    manifest_json = tmp_path / "outputs" / "manifest.json"
    config_path.write_text("[sweep]\nsample_count = 3\n", encoding="utf-8")

    result = run_sweep_workflow(
        _spec(),
        paths=SweepOutputPaths(
            config=config_path,
            sweep_runs_csv=sweep_csv,
            sensitivity_csv=sensitivity_csv,
            manifest_json=manifest_json,
        ),
        command="test-sweep",
        manifest_name="test-sweep-manifest",
        manifest_metadata={"scenario": "synthetic"},
    )
    manifest_payload = json.loads(manifest_json.read_text(encoding="utf-8"))

    assert len(result.runs) == 3
    assert len(result.sensitivity_results) == 1
    assert result.sweep_runs_csv_path == sweep_csv
    assert result.sensitivity_csv_path == sensitivity_csv
    assert result.manifest_json_path == manifest_json
    assert "summary_final_ancestry" in sweep_csv.read_text(encoding="utf-8")
    assert sensitivity_csv.read_text(encoding="utf-8").startswith("parameter,outcome")
    assert result.manifest is not None
    assert result.manifest.name == "test-sweep-manifest"
    assert {artifact.role for artifact in result.artifacts} == {
        "config",
        "sweep_runs",
        "sensitivity",
    }
    assert manifest_payload["fingerprints"][0]["kind"] == "sweep_collection"
    assert manifest_payload["metadata"]["sample_count"] == "3"
    assert manifest_payload["metadata"]["scenario"] == "synthetic"


def test_run_sweep_workflow_can_score_targets_and_write_fit_csv(
    tmp_path: Path,
) -> None:
    """Sweep workflows should materialize ranked target-fit diagnostics."""
    target_path = tmp_path / "targets.csv"
    target_fit_csv = tmp_path / "outputs" / "target-fit.csv"
    manifest_json = tmp_path / "outputs" / "manifest.json"
    target_path.write_text(
        "\n".join(
            [
                "status,region,source,time_bce,mean,uncertainty,citation_key,citation,note",
                'synthetic,britain,steppe,2900,0.05,0.03,key,"Synthetic",Example',
            ]
        ),
        encoding="utf-8",
    )

    result = run_sweep_workflow(
        _spec(sample_count=2),
        targets=_targets(),
        paths=SweepOutputPaths(
            targets=target_path,
            target_fit_csv=target_fit_csv,
            manifest_json=manifest_json,
        ),
        fit_metric="root_mean_squared_error",
    )
    manifest_payload = json.loads(manifest_json.read_text(encoding="utf-8"))

    assert len(result.scored_runs) == 2
    assert result.target_fit_csv_path == target_fit_csv
    assert target_fit_csv.read_text(encoding="utf-8").startswith(
        "rank,run_index,sampled_migration_rate"
    )
    assert {artifact.role for artifact in result.artifacts} == {
        "targets",
        "target_fit",
    }
    assert manifest_payload["metadata"]["target_fit_metric"] == (
        "root_mean_squared_error"
    )


def test_write_sweep_outputs_can_use_precomputed_sensitivity_results(
    tmp_path: Path,
) -> None:
    """Existing sweep runs and diagnostics should be reusable."""
    runs = run_parameter_sweep(_spec(sample_count=2))
    sensitivity = (
        SensitivityResult(
            parameter="migration_rate",
            outcome="final_ancestry",
            pearson_correlation=0.0,
            spearman_correlation=0.0,
            linear_slope=0.0,
        ),
    )
    sensitivity_csv = tmp_path / "sensitivity.csv"

    result = write_sweep_outputs(
        runs,
        sensitivity_results=sensitivity,
        paths=SweepOutputPaths(sensitivity_csv=sensitivity_csv),
    )

    assert result.runs == runs
    assert result.sensitivity_results == sensitivity
    assert len(result.artifacts) == 1
    assert result.artifacts[0].role == "sensitivity"
    assert result.manifest is None
    assert "migration_rate" in sensitivity_csv.read_text(encoding="utf-8")


def test_write_sweep_outputs_requires_scored_runs_for_fit_csv(
    tmp_path: Path,
) -> None:
    """A target-fit CSV path is invalid without scored sweep runs."""
    runs = run_parameter_sweep(_spec(sample_count=2))

    with pytest.raises(ValueError, match="target_fit_csv"):
        write_sweep_outputs(
            runs,
            paths=SweepOutputPaths(target_fit_csv=tmp_path / "target-fit.csv"),
        )


def test_sweep_workflow_can_write_manifest_without_csv_artifacts(
    tmp_path: Path,
) -> None:
    """Manifest-only sweep exports should still carry a collection fingerprint."""
    manifest_json = tmp_path / "manifest.json"

    result = run_sweep_workflow(
        _spec(sample_count=2),
        paths=SweepOutputPaths(manifest_json=manifest_json),
    )
    manifest_payload = json.loads(manifest_json.read_text(encoding="utf-8"))

    assert result.artifacts == ()
    assert result.manifest is not None
    assert result.manifest.fingerprints[0].kind == "sweep_collection"
    assert manifest_payload["artifacts"] == []


def test_sweep_experiment_manifest_records_metadata() -> None:
    """Sweep manifests should record source, region, and sensitivity outcome."""
    runs = run_parameter_sweep(_spec(sample_count=2))

    manifest = sweep_experiment_manifest(
        runs,
        sensitivity_outcome="final_total_population",
        command="manual-sweep",
        name="manual",
    )

    assert manifest.name == "manual"
    assert manifest.fingerprints[0].kind == "sweep_collection"
    assert manifest.metadata == {
        "command": "manual-sweep",
        "sample_count": "2",
        "sensitivity_outcome": "final_total_population",
        "source": "steppe",
        "region": "britain",
    }


def test_write_sweep_outputs_can_return_in_memory_results() -> None:
    """Sweep output writing should work without requested files."""
    runs = run_parameter_sweep(_spec(sample_count=2))

    result = write_sweep_outputs(runs)

    assert result.runs == runs
    assert len(result.sensitivity_results) == 1
    assert result.artifacts == ()
    assert result.manifest is None
    assert result.sweep_runs_csv_path is None
    assert result.sensitivity_csv_path is None
    assert result.manifest_json_path is None


def test_sweep_workflows_reject_empty_runs() -> None:
    """Sweep workflow helpers should fail clearly for empty run collections."""
    with pytest.raises(ValueError, match="at least one"):
        write_sweep_outputs(())
    with pytest.raises(ValueError, match="at least one"):
        sweep_experiment_manifest(())
