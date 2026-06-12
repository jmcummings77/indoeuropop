"""Tests for multi-fold structural SMC validation."""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from pathlib import Path

import pytest
from pytest import CaptureFixture

from indoeuropop.analysis.abc_smc import ABCSMCOptions
from indoeuropop.analysis.structural_head_to_head import StructuredPulseCandidate
from indoeuropop.data.targets import TargetDataset, TargetObservation
from indoeuropop.models import PopulationState, SimulationParameters
from indoeuropop.orchestration.child_region_overrides import ChildRegionOverrideSet
from indoeuropop.orchestration.cli import main
from indoeuropop.orchestration.structural_smc_validation import (
    default_structural_smc_validation_folds,
    run_structural_smc_multifold_validation_workflow,
    split_targets_by_structural_smc_fold,
)
from indoeuropop.orchestration.structural_smc_validation_cli import (
    _review_holdout_values,
    _validation_folds,
    run_structural_smc_validation_command,
)
from indoeuropop.orchestration.structural_smc_validation_models import (
    StructuralSMCMultiFoldValidationResult,
    StructuralSMCValidationFoldSpec,
    StructuralSMCValidationOutputPaths,
    merge_structural_smc_validation_folds,
    structural_smc_preferred_candidate,
)
from indoeuropop.orchestration.structural_smc_validation_outputs import (
    structural_smc_validation_artifacts,
    structural_smc_validation_output_paths_from_dir,
)
from indoeuropop.orchestration.sweep_config_export import write_sweep_spec_toml
from indoeuropop.orchestration.sweeps import ParameterRange, SweepSpec
from indoeuropop.reporting.structural_smc_validation import (
    structural_smc_validation_markdown,
    structural_smc_validation_rows,
    structural_smc_validation_to_csv,
    write_structural_smc_validation_csv,
    write_structural_smc_validation_markdown,
)
from indoeuropop.simulation.events import MigrationPulse


def test_structural_smc_validation_fold_models_and_defaults() -> None:
    """Default validation folds should merge protected, priority, and child tags."""
    defaults = default_structural_smc_validation_folds(
        _default_fold_targets(),
        region_prefix="central_europe__",
        protected_values=("britain",),
        priority_values=("central_europe__a",),
    )
    by_name = {fold.name: fold for fold in defaults}
    merged = merge_structural_smc_validation_folds(
        (
            StructuralSMCValidationFoldSpec(
                name="Central Europe A",
                categories=("one",),
                holdout_value="central_europe__a",
            ),
            StructuralSMCValidationFoldSpec(
                name="central-europe-a",
                categories=("two",),
                holdout_value="central_europe__a",
            ),
        )
    )

    assert structural_smc_preferred_candidate(-0.1) == "child_override"
    assert structural_smc_preferred_candidate(0.1) == "structured_pulse"
    assert structural_smc_preferred_candidate(0.0) == "tie"
    assert by_name["britain"].categories == ("protected", "britain_anchor")
    assert by_name["central_europe__a"].categories == (
        "priority",
        "central_europe_child",
    )
    assert "early_steppe_transition_3000_2500_bce" in by_name
    assert merged[0].categories == ("one", "two")


def test_structural_smc_validation_splits_field_holdouts() -> None:
    """Validation fold specs should split field holdouts."""
    split = split_targets_by_structural_smc_fold(
        _targets(),
        StructuralSMCValidationFoldSpec(
            name="region-b",
            categories=("explicit",),
            holdout_value="central_europe__b",
        ),
    )

    assert split.calibration.observations[0].region == "central_europe__a"
    assert split.validation.observations[0].region == "central_europe__b"


def test_structural_smc_validation_splits_time_window_holdouts() -> None:
    """Validation fold specs should split BCE time-window holdouts."""
    split = split_targets_by_structural_smc_fold(
        _time_split_targets(),
        StructuralSMCValidationFoldSpec(
            name="early",
            categories=("time",),
            holdout_field="time_bce",
            start_bce=3000,
            end_bce=2900,
        ),
    )

    assert split.calibration.observations[0].region == "central_europe__b"
    assert split.validation.observations[0].region == "central_europe__a"


@pytest.mark.parametrize(
    "fold",
    [
        pytest.param(
            lambda: StructuralSMCValidationFoldSpec("", ("x",), holdout_value="a"),
            id="empty-name",
        ),
        pytest.param(
            lambda: StructuralSMCValidationFoldSpec("x", (), holdout_value="a"),
            id="empty-categories",
        ),
        pytest.param(
            lambda: StructuralSMCValidationFoldSpec("x", ("c",)),
            id="missing-field-value",
        ),
        pytest.param(
            lambda: StructuralSMCValidationFoldSpec(
                "x",
                ("time",),
                holdout_field="time_bce",
                start_bce=2000,
                end_bce=3000,
            ),
            id="invalid-time-window",
        ),
    ],
)
def test_structural_smc_validation_fold_specs_reject_invalid_inputs(
    fold: Callable[[], StructuralSMCValidationFoldSpec],
) -> None:
    """Validation fold specs should reject ambiguous definitions."""
    with pytest.raises(ValueError):
        fold()


def test_structural_smc_multifold_workflow_writes_artifacts(tmp_path: Path) -> None:
    """Multi-fold validation should write top-level and per-fold artifacts."""
    config_path, targets_path, overrides_path = _write_cli_inputs(tmp_path)
    output_dir = tmp_path / "validation"
    paths = structural_smc_validation_output_paths_from_dir(
        output_dir,
        config=config_path,
        targets=targets_path,
        child_region_overrides=overrides_path,
    )
    result = run_structural_smc_multifold_validation_workflow(
        _spec(),
        _targets(),
        _overrides(),
        _structured_pulse_candidate(),
        folds=_explicit_region_folds(),
        child_candidate_name="child-best",
        options=ABCSMCOptions(generation_count=1, acceptance_count=1),
        paths=paths,
        manifest_metadata={"scenario": "synthetic-multifold"},
    )
    assert paths.summary_csv is not None
    assert paths.report_md is not None
    assert paths.manifest_json is not None
    payload = json.loads(paths.manifest_json.read_text(encoding="utf-8"))

    assert len(result.folds) == 2
    assert result.preference_disagreement_count >= 0
    assert result.summary_csv_path == paths.summary_csv
    assert result.report_md_path == paths.report_md
    assert result.manifest is not None
    assert paths.summary_csv.exists()
    assert paths.report_md.exists()
    assert (output_dir / "central_europe__a" / "calibration-targets.csv").exists()
    assert (output_dir / "central_europe__a" / "holdout-targets.csv").exists()
    assert (output_dir / "central_europe__b" / "smc-baseline-generations.csv").exists()
    assert payload["metadata"]["scenario"] == "synthetic-multifold"
    assert payload["metadata"]["fold_count"] == "2"
    assert "central_europe__a_report_md" in {
        artifact["name"] for artifact in payload["artifacts"]
    }


def test_structural_smc_multifold_workflow_supports_in_memory_execution() -> None:
    """Programmatic multi-fold validation should not require output paths."""
    result = run_structural_smc_multifold_validation_workflow(
        _spec(sample_count=2),
        _targets(),
        _overrides(),
        _structured_pulse_candidate(),
        folds=_explicit_region_folds()[:1],
        options=ABCSMCOptions(generation_count=1, acceptance_count=1),
    )

    assert result.artifacts == ()
    assert result.manifest is None
    assert result.summary_csv_path is None
    assert (
        structural_smc_validation_artifacts(StructuralSMCValidationOutputPaths(), ())
        == ()
    )
    with pytest.raises(ValueError, match="at least one"):
        StructuralSMCMultiFoldValidationResult(())
    with pytest.raises(ValueError, match="folds must contain"):
        run_structural_smc_multifold_validation_workflow(
            _spec(),
            _targets(),
            _overrides(),
            _structured_pulse_candidate(),
            folds=(),
        )


def test_structural_smc_validation_reporting_writes_csv_and_markdown(
    tmp_path: Path,
) -> None:
    """Validation reporters should serialize fold rows and summaries."""
    result = run_structural_smc_multifold_validation_workflow(
        _spec(sample_count=2),
        _targets(),
        _overrides(),
        _structured_pulse_candidate(),
        folds=_explicit_region_folds()[:1],
        options=ABCSMCOptions(generation_count=1, acceptance_count=1),
    )
    csv_path = tmp_path / "summary.csv"
    markdown_path = tmp_path / "report.md"

    rows = structural_smc_validation_rows(result.folds)
    csv_text = structural_smc_validation_to_csv(result.folds)
    markdown = structural_smc_validation_markdown(result.folds)

    assert rows[0]["fold_name"] == "central_europe__a"
    assert "preference_disagreement" in csv_text
    assert "Structural SMC Multi-Fold Validation" in markdown
    assert write_structural_smc_validation_csv(result.folds, csv_path) == csv_path
    assert (
        write_structural_smc_validation_markdown(result.folds, markdown_path)
        == markdown_path
    )
    assert csv_path.read_text(encoding="utf-8") == csv_text
    assert markdown_path.read_text(encoding="utf-8") == markdown


def test_cli_validate_structured_candidates_smc_writes_outputs(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    """The CLI should run explicit multi-fold structural SMC validation."""
    config_path, targets_path, overrides_path = _write_cli_inputs(tmp_path)
    output_dir = tmp_path / "cli-validation"

    exit_code = main(
        [
            "validate-structured-candidates-smc",
            "--config",
            str(config_path),
            "--targets",
            str(targets_path),
            "--validation-field",
            "region",
            "--validation-value",
            "central_europe__a",
            "--validation-value",
            "central_europe__b",
            "--child-region-overrides",
            str(overrides_path),
            "--fit-metric",
            "root_mean_squared_error",
            "--acceptance-count",
            "1",
            "--smc-generations",
            "1",
            "--smc-sample-count",
            "2",
            "--structured-pulse-candidate-name",
            "structured-pulse",
            "--structured-pulse-region-prefix",
            "central_europe__",
            "--structured-pulse-start-bce",
            "3050",
            "--structured-pulse-end-bce",
            "2925",
            "--structured-pulse-annual-rate",
            "0.0002",
            "--child-region-candidate-name",
            "child-best",
            "--smc-validation-no-default-folds",
            "--smc-validation-output-dir",
            str(output_dir),
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "structural_smc_validation=true" in captured.out
    assert "structural_smc_validation_fold_count=2" in captured.out
    assert "structural_smc_validation_calibration_child_preferred_count=" in (
        captured.out
    )
    assert (output_dir / "structural-smc-validation-summary.csv").exists()
    assert (output_dir / "structural-smc-validation.md").exists()
    assert (output_dir / "structural-smc-validation-manifest.json").exists()


def test_cli_validate_structured_candidates_smc_requires_inputs(
    capsys: CaptureFixture[str],
) -> None:
    """Structural SMC validation CLI should reject missing required inputs."""
    with pytest.raises(SystemExit, match="2"):
        main(["validate-structured-candidates-smc"])
    captured = capsys.readouterr()

    assert "requires --config" in captured.err


def test_cli_validate_structured_candidates_smc_requires_a_fold(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    """Validation CLI should reject empty explicit-fold requests."""
    config_path, targets_path, overrides_path = _write_cli_inputs(tmp_path)
    with pytest.raises(SystemExit, match="2"):
        main(
            [
                "validate-structured-candidates-smc",
                "--config",
                str(config_path),
                "--targets",
                str(targets_path),
                "--child-region-overrides",
                str(overrides_path),
                "--structured-pulse-region-prefix",
                "central_europe__",
                "--structured-pulse-start-bce",
                "3050",
                "--structured-pulse-end-bce",
                "2925",
                "--structured-pulse-annual-rate",
                "0.0002",
                "--smc-validation-no-default-folds",
                "--smc-validation-output-dir",
                str(tmp_path / "empty"),
            ]
        )
    captured = capsys.readouterr()

    assert "requires at least one fold" in captured.err


def test_structural_smc_validation_handler_ignores_unrelated_commands() -> None:
    """The delegated structural SMC validation handler should ignore other commands."""
    args = argparse.Namespace(command="demo")
    parser = argparse.ArgumentParser()

    assert run_structural_smc_validation_command(args, parser) is None


def test_review_holdout_loader_supports_scalar_values(tmp_path: Path) -> None:
    """Review holdout parsing should accept scalar TOML values too."""
    path = tmp_path / "overrides.toml"
    path.write_text('[review]\nprotected_holdouts = "britain"\n', encoding="utf-8")

    assert _review_holdout_values(path, "protected_holdouts") == ("britain",)
    assert _review_holdout_values(path, "priority_holdouts") == ()


def test_cli_validation_fold_helper_builds_default_folds(tmp_path: Path) -> None:
    """CLI fold construction should use default review and child-region folds."""
    _, _, overrides_path = _write_cli_inputs(tmp_path)
    folds = _validation_folds(
        argparse.Namespace(
            child_region_overrides=overrides_path,
            protected_validation_value=None,
            priority_validation_value=None,
            smc_validation_no_default_folds=False,
            smc_validation_no_chronology=True,
            structured_pulse_region_prefix="central_europe__",
            validation_field="region",
            validation_value=None,
        ),
        argparse.ArgumentParser(),
        _targets(),
    )

    assert {fold.name for fold in folds} == {
        "central_europe__a",
        "central_europe__b",
    }
    by_name = {fold.name: fold for fold in folds}

    assert by_name["central_europe__a"].categories == (
        "priority",
        "central_europe_child",
    )
    assert by_name["central_europe__b"].categories == (
        "protected",
        "central_europe_child",
    )


def _write_cli_inputs(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Write a tiny config, target CSV, and override TOML for CLI tests."""
    config_path = tmp_path / "structured.toml"
    targets_path = tmp_path / "targets.csv"
    overrides_path = tmp_path / "overrides.toml"
    write_sweep_spec_toml(_spec(), config_path)
    targets_path.write_text(_targets_csv(), encoding="utf-8")
    overrides_path.write_text(_overrides_toml(), encoding="utf-8")
    return config_path, targets_path, overrides_path


def _explicit_region_folds() -> tuple[StructuralSMCValidationFoldSpec, ...]:
    """Return two explicit child-region holdout folds."""
    return (
        StructuralSMCValidationFoldSpec(
            name="central_europe__a",
            categories=("explicit",),
            holdout_value="central_europe__a",
        ),
        StructuralSMCValidationFoldSpec(
            name="central_europe__b",
            categories=("explicit",),
            holdout_value="central_europe__b",
        ),
    )


def _spec(sample_count: int = 2) -> SweepSpec:
    """Return one small structured central-Europe sweep spec."""
    return SweepSpec(
        initial_state=PopulationState(
            {
                "central_europe__a": {"local": 1000, "steppe": 5},
                "central_europe__b": {"local": 900, "steppe": 10},
            }
        ),
        base_parameters=SimulationParameters(migration_rate=0.0),
        parameter_ranges=(ParameterRange("migration_rate", 0.0, 0.001),),
        start_bce=3100,
        end_bce=2900,
        step_years=50,
        sample_count=sample_count,
        seed=37,
        source="steppe",
        region="central_europe__a",
    )


def _targets() -> TargetDataset:
    """Return synthetic targets compatible with the workflow test spec."""
    return TargetDataset.from_rows(
        [
            TargetObservation(
                status="synthetic",
                region="central_europe__a",
                source="steppe",
                time_bce=2950,
                mean=0.2,
                uncertainty=0.1,
                citation_key="synthetic",
                citation="Synthetic child-region target",
            ),
            TargetObservation(
                status="synthetic",
                region="central_europe__b",
                source="steppe",
                time_bce=2950,
                mean=0.1,
                uncertainty=0.1,
                citation_key="synthetic",
                citation="Synthetic child-region target",
            ),
        ]
    )


def _default_fold_targets() -> TargetDataset:
    """Return targets that exercise default fold generation."""
    return TargetDataset.from_rows(
        [
            *_targets().observations,
            TargetObservation(
                status="synthetic",
                region="britain",
                source="steppe",
                time_bce=2200,
                mean=0.3,
                uncertainty=0.1,
                citation_key="synthetic",
                citation="Synthetic Britain target",
            ),
        ]
    )


def _time_split_targets() -> TargetDataset:
    """Return targets with one row inside and one row outside an early window."""
    return TargetDataset.from_rows(
        [
            TargetObservation(
                status="synthetic",
                region="central_europe__a",
                source="steppe",
                time_bce=2950,
                mean=0.2,
                uncertainty=0.1,
                citation_key="synthetic",
                citation="Synthetic early target",
            ),
            TargetObservation(
                status="synthetic",
                region="central_europe__b",
                source="steppe",
                time_bce=2800,
                mean=0.1,
                uncertainty=0.1,
                citation_key="synthetic",
                citation="Synthetic late target",
            ),
        ]
    )


def _overrides() -> ChildRegionOverrideSet:
    """Return a synthetic child-region override set."""
    return ChildRegionOverrideSet(
        counts={"central_europe__a": {"local": 760, "steppe": 38}},
        migration_pulses=(
            MigrationPulse(
                region="central_europe__a",
                start_bce=3050,
                end_bce=2925,
                annual_rate=0.0002,
            ),
        ),
    )


def _structured_pulse_candidate() -> StructuredPulseCandidate:
    """Return a structured pulse copied across child regions."""
    return StructuredPulseCandidate(
        name="structured-pulse",
        region_prefix="central_europe__",
        start_bce=3050,
        end_bce=2925,
        annual_rate=0.0002,
    )


def _targets_csv() -> str:
    """Return a target CSV compatible with the CLI config."""
    return (
        "status,region,source,time_bce,mean,uncertainty,citation_key,citation,note\n"
        "synthetic,central_europe__a,steppe,2950,0.2,0.1,synthetic,"
        "Synthetic target,requested_group_id=A\n"
        "synthetic,central_europe__b,steppe,2950,0.1,0.1,synthetic,"
        "Synthetic target,requested_group_id=B\n"
    )


def _overrides_toml() -> str:
    """Return a child-region override TOML with review metadata."""
    return (
        "[review]\n"
        'protected_holdouts = ["central_europe__b"]\n'
        'priority_holdouts = ["central_europe__a"]\n\n'
        "[counts.central_europe__a]\n"
        "local = 760\n"
        "steppe = 38\n\n"
        "[[migration_pulses]]\n"
        'region = "central_europe__a"\n'
        "start_bce = 3050\n"
        "end_bce = 2925\n"
        "annual_rate = 0.0002\n"
    )
