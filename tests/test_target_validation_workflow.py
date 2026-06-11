"""Tests for held-out target-validation workflows and reports."""

import json
from dataclasses import replace
from pathlib import Path

import pytest

from indoeuropop.analysis.validation import TargetValidationFold
from indoeuropop.data.targets import TargetDataset, TargetObservation
from indoeuropop.models import PopulationState, SimulationParameters
from indoeuropop.orchestration.sweeps import ParameterRange, SweepSpec
from indoeuropop.orchestration.target_validation import (
    TargetValidationOutputPaths,
    run_target_validation_workflow,
    target_validation_artifacts,
    target_validation_experiment_manifest,
)
from indoeuropop.reporting.target_validation import (
    target_validation_fieldnames,
    target_validation_markdown,
    target_validation_rows,
    target_validation_to_csv,
)


def _spec(sample_count: int = 3) -> SweepSpec:
    """Return one small sweep spec for validation workflow tests."""
    return SweepSpec(
        initial_state=PopulationState(
            {
                "britain": {"local": 1000, "steppe": 20},
                "central_europe": {"local": 1000, "steppe": 40},
            }
        ),
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


def _target(region: str, mean: float) -> TargetObservation:
    """Return a synthetic target with a note-based group label."""
    return TargetObservation(
        status="synthetic",
        region=region,
        source="steppe",
        time_bce=2900,
        mean=mean,
        uncertainty=0.05,
        citation_key="synthetic",
        citation="Synthetic validation workflow target",
        note=f"requested_group_id={region}_group",
    )


def _targets() -> TargetDataset:
    """Return targets with two holdout regions."""
    return TargetDataset.from_rows(
        [
            _target("britain", 0.05),
            _target("central_europe", 0.06),
            _target("central_europe", 0.07),
        ]
    )


def test_run_target_validation_workflow_writes_outputs_and_manifest(
    tmp_path: Path,
) -> None:
    """The workflow should write validation CSV, report, and manifest artifacts."""
    config_path = tmp_path / "sweep.toml"
    target_path = tmp_path / "targets.csv"
    output_dir = tmp_path / "outputs"
    config_path.write_text("[sweep]\nsample_count = 3\n", encoding="utf-8")
    target_path.write_text("targets\n", encoding="utf-8")

    result = run_target_validation_workflow(
        _spec(),
        _targets(),
        paths=TargetValidationOutputPaths(
            config=config_path,
            targets=target_path,
            validation_fit_csv=output_dir / "validation-fit.csv",
            validation_report_md=output_dir / "validation.md",
            manifest_json=output_dir / "validation-manifest.json",
        ),
        fit_metric="root_mean_squared_error",
        manifest_metadata={"scenario": "synthetic"},
    )
    manifest_payload = json.loads(
        (output_dir / "validation-manifest.json").read_text(encoding="utf-8")
    )

    assert len(result.folds) == 2
    assert result.best_fold.holdout_field == "region"
    assert result.validation_fit_csv_path == output_dir / "validation-fit.csv"
    assert result.validation_report_md_path == output_dir / "validation.md"
    assert "validation_root_mean_squared_error" in (
        output_dir / "validation-fit.csv"
    ).read_text(encoding="utf-8")
    assert "| holdout_value |" in (output_dir / "validation.md").read_text(
        encoding="utf-8"
    )
    assert manifest_payload["name"] == "target-validation"
    assert manifest_payload["metadata"]["scenario"] == "synthetic"
    assert manifest_payload["metadata"]["fold_count"] == "2"
    assert {artifact["name"] for artifact in manifest_payload["artifacts"]} == {
        "config",
        "targets",
        "validation_fit_csv",
        "validation_report_md",
    }


def test_target_validation_report_helpers_return_stable_rows() -> None:
    """Reporting helpers should serialize validation folds consistently."""
    result = run_target_validation_workflow(
        _spec(sample_count=2),
        _targets(),
        holdout_values=("britain",),
    )
    rows = target_validation_rows(result.folds)
    csv_text = target_validation_to_csv(result.folds)
    markdown = target_validation_markdown(
        result.folds,
        metric="root_mean_squared_error",
    )

    assert target_validation_fieldnames(result.folds)[:4] == (
        "holdout_field",
        "holdout_value",
        "rank",
        "run_index",
    )
    assert rows[0]["holdout_value"] == "britain"
    assert "sampled_migration_rate" in rows[0]
    assert csv_text.startswith("holdout_field,holdout_value,rank")
    assert "ranking_metric: `root_mean_squared_error`" in markdown


def test_target_validation_workflow_supports_note_holdout_values() -> None:
    """The workflow should support leave-one-target-group-out validation."""
    result = run_target_validation_workflow(
        _spec(sample_count=2),
        _targets(),
        holdout_field="note:requested_group_id",
        holdout_values=("britain_group",),
    )

    assert result.folds[0].holdout_value == "britain_group"
    assert result.folds[0].best_run.fit.validation.observation_count == 1


def test_target_validation_workflow_rejects_blank_explicit_holdouts() -> None:
    """Explicit validation values should not be blank-only selectors."""
    with pytest.raises(ValueError, match="holdout_values"):
        run_target_validation_workflow(
            _spec(sample_count=2),
            _targets(),
            holdout_values=(" ",),
        )


def test_target_validation_artifacts_can_be_empty() -> None:
    """Artifact collection should support in-memory validation workflows."""
    assert target_validation_artifacts(TargetValidationOutputPaths()) == ()


def test_target_validation_manifest_validates_non_empty_folds() -> None:
    """Programmatic manifest construction should require validation folds."""
    result = run_target_validation_workflow(_spec(sample_count=2), _targets())
    manifest = target_validation_experiment_manifest(
        result.folds,
        fit_metric="chi_square",
        metadata={"note": "review"},
    )

    assert manifest.metadata["holdout_field"] == "region"
    assert manifest.metadata["note"] == "review"
    with pytest.raises(ValueError, match="at least one validation fold"):
        target_validation_experiment_manifest(())


def test_target_validation_report_helpers_validate_inputs() -> None:
    """Reporting helpers should reject unsupported metrics and empty folds."""
    with pytest.raises(ValueError, match="at least one"):
        target_validation_to_csv(())
    with pytest.raises(ValueError, match="unsupported fit metric"):
        target_validation_markdown(
            run_target_validation_workflow(
                _spec(sample_count=2),
                _targets(),
                holdout_values=("britain",),
            ).folds,
            metric="unknown",
        )


def test_target_validation_report_helpers_reject_inconsistent_folds() -> None:
    """Reporting should reject folds with incompatible holdout fields or samples."""
    fold = run_target_validation_workflow(
        _spec(sample_count=2),
        _targets(),
        holdout_values=("britain",),
    ).folds[0]
    mismatched_field = TargetValidationFold(
        "source",
        "steppe",
        fold.target_split,
        fold.runs,
    )
    empty_sample_run = replace(
        fold.best_run,
        run=replace(fold.best_run.run, sampled_values={}),
    )
    mismatched_sample_run = replace(
        fold.best_run,
        run=replace(fold.best_run.run, sampled_values={"other_rate": 0.1}),
    )

    with pytest.raises(ValueError, match="same holdout field"):
        target_validation_to_csv((fold, mismatched_field))
    with pytest.raises(ValueError, match="sampled parameters"):
        target_validation_to_csv(
            (
                TargetValidationFold(
                    "region",
                    "britain",
                    fold.target_split,
                    (empty_sample_run,),
                ),
            )
        )
    with pytest.raises(ValueError, match="same parameters"):
        target_validation_to_csv(
            (
                fold,
                TargetValidationFold(
                    "region",
                    "central_europe",
                    fold.target_split,
                    (mismatched_sample_run,),
                ),
            )
        )
