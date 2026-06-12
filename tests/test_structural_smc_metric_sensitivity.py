"""Tests for structural SMC fit-metric sensitivity workflows."""

from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path

import pytest
from pytest import CaptureFixture, MonkeyPatch

from indoeuropop.analysis.abc_smc import ABCSMCOptions
from indoeuropop.analysis.structural_head_to_head import StructuredPulseCandidate
from indoeuropop.data.targets import TargetDataset, TargetObservation
from indoeuropop.models import PopulationState, SimulationParameters
from indoeuropop.orchestration.child_region_overrides import ChildRegionOverrideSet
from indoeuropop.orchestration.cli import main
from indoeuropop.orchestration.structural_smc_metric_sensitivity import (
    _fit_metric_names,
    _summary_path,
    run_structural_smc_fit_metric_sensitivity,
    structural_smc_fit_metric_sensitivity_paths_from_dir,
)
from indoeuropop.orchestration.structural_smc_metric_sensitivity_cli import (
    run_structural_smc_metric_sensitivity_command,
)
from indoeuropop.orchestration.structural_smc_metric_sensitivity_models import (
    DEFAULT_STRUCTURAL_SMC_FIT_METRICS,
    StructuralSMCFitMetricSensitivityResult,
)
from indoeuropop.orchestration.structural_smc_validation_models import (
    StructuralSMCValidationFoldSpec,
)
from indoeuropop.orchestration.sweep_config_export import write_sweep_spec_toml
from indoeuropop.orchestration.sweeps import ParameterRange, SweepSpec
from indoeuropop.reporting.structural_smc_metric_sensitivity import (
    structural_smc_fit_metric_sensitivity_markdown,
    structural_smc_fit_metric_sensitivity_rows,
    structural_smc_fit_metric_sensitivity_to_csv,
)


def test_fit_metric_sensitivity_workflow_writes_reports(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """The workflow should rerun retained folds under each requested metric."""
    monkeypatch.chdir(tmp_path)
    audit_path = tmp_path / "audit.csv"
    audit_path.write_text(_sample_audit_csv(include_critical=False), encoding="utf-8")

    result = run_structural_smc_fit_metric_sensitivity(
        _spec(),
        _targets(),
        _overrides(),
        _structured_pulse_candidate(),
        sample_audit_csv=audit_path,
        folds=_folds(),
        options=ABCSMCOptions(generation_count=1, sample_count=2, acceptance_count=1),
    )
    rows = structural_smc_fit_metric_sensitivity_rows(result)
    csv_text = structural_smc_fit_metric_sensitivity_to_csv(result)
    markdown = structural_smc_fit_metric_sensitivity_markdown(result)

    assert [run.fit_metric for run in result.runs] == list(
        DEFAULT_STRUCTURAL_SMC_FIT_METRICS
    )
    assert result.excluded_target_count == 1
    assert result.filtered_target_count == 2
    assert result.skipped_fold_count == 1
    assert len(result.runs[0].validation_result.folds) == 2
    assert rows[0]["fit_metric"] == "root_mean_squared_error"
    assert "fit_metric,validation_fold_count" in csv_text
    assert "Structural SMC Fit-Metric Sensitivity" in markdown
    assert result.paths.summary_csv.exists()
    assert result.paths.report_md.exists()
    assert (
        result.paths.metrics_output_dir
        / "root_mean_squared_error"
        / "structural-smc-uncertainty.csv"
    ).exists()
    with pytest.raises(ValueError, match="fit_metric"):
        replace(result.runs[0], fit_metric="")


def test_cli_fit_metric_sensitivity_writes_outputs(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    """The CLI should expose fragility-filtered fit-metric sensitivity."""
    config_path, targets_path, overrides_path, audit_path = _write_cli_inputs(tmp_path)
    output_dir = tmp_path / "metric-sensitivity"

    exit_code = main(
        [
            "validate-structured-smc-fit-metric-sensitivity",
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
            "--validation-value",
            "central_europe__c",
            "--child-region-overrides",
            str(overrides_path),
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
            "--target-fragility-audit-csv",
            str(audit_path),
            "--fit-metric-sensitivity-output-dir",
            str(output_dir),
            "--fit-metric-sensitivity-metric",
            "root_mean_squared_error",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "fit_metric_sensitivity=true" in captured.out
    assert "fit_metric_sensitivity_metric_count=1" in captured.out
    assert "fit_metric_sensitivity_skipped_fold_count=1" in captured.out
    assert (output_dir / "fit-metric-sensitivity-summary.csv").exists()
    assert (output_dir / "fit-metric-sensitivity.md").exists()


def test_fit_metric_sensitivity_rejects_bad_inputs(tmp_path: Path) -> None:
    """The workflow and CLI should fail clearly on incomplete inputs."""
    config_path, targets_path, overrides_path, _ = _write_cli_inputs(tmp_path)
    audit_path = tmp_path / "audit.csv"
    audit_path.write_text(_sample_audit_csv(include_critical=True), encoding="utf-8")
    with pytest.raises(ValueError, match="fit_metrics"):
        _fit_metric_names(("", " "))
    with pytest.raises(ValueError, match="summary CSV"):
        _summary_path(None)
    with pytest.raises(ValueError, match="at least one run"):
        StructuralSMCFitMetricSensitivityResult(
            decisions=(),
            original_targets=_targets(),
            filtered_targets=_targets(),
            skipped_folds=(),
            runs=(),
            paths=structural_smc_fit_metric_sensitivity_paths_from_dir(
                tmp_path / "result"
            ),
        )
    assert (
        run_structural_smc_metric_sensitivity_command(
            argparse.Namespace(command="demo"), argparse.ArgumentParser()
        )
        is None
    )
    with pytest.raises(ValueError, match="no usable validation folds"):
        run_structural_smc_fit_metric_sensitivity(
            _spec(),
            _targets(),
            _overrides(),
            _structured_pulse_candidate(),
            sample_audit_csv=audit_path,
            folds=_folds(),
            options=ABCSMCOptions(
                generation_count=1, sample_count=2, acceptance_count=1
            ),
            paths=structural_smc_fit_metric_sensitivity_paths_from_dir(
                tmp_path / "empty"
            ),
        )
    with pytest.raises(SystemExit, match="2"):
        main(["validate-structured-smc-fit-metric-sensitivity"])
    base_command = [
        "validate-structured-smc-fit-metric-sensitivity",
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
        "--validation-value",
        "central_europe__a",
    ]
    with pytest.raises(SystemExit, match="2"):
        main([*base_command, "--fit-metric-sensitivity-output-dir", str(tmp_path)])
    with pytest.raises(SystemExit, match="2"):
        main([*base_command, "--target-fragility-audit-csv", str(audit_path)])


def _write_cli_inputs(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    """Write tiny config, targets, overrides, and sample audit CSV files."""
    config_path = tmp_path / "structured.toml"
    targets_path = tmp_path / "targets.csv"
    overrides_path = tmp_path / "overrides.toml"
    audit_path = tmp_path / "audit.csv"
    write_sweep_spec_toml(_spec(), config_path)
    targets_path.write_text(_targets_csv(), encoding="utf-8")
    overrides_path.write_text(_overrides_toml(), encoding="utf-8")
    audit_path.write_text(_sample_audit_csv(include_critical=False), encoding="utf-8")
    return config_path, targets_path, overrides_path, audit_path


def _spec() -> SweepSpec:
    """Return a tiny structured central-Europe sweep spec."""
    return SweepSpec(
        initial_state=PopulationState(
            {
                "central_europe__a": {"local": 1000, "steppe": 5},
                "central_europe__b": {"local": 900, "steppe": 10},
                "central_europe__c": {"local": 950, "steppe": 8},
            }
        ),
        base_parameters=SimulationParameters(migration_rate=0.0),
        parameter_ranges=(ParameterRange("migration_rate", 0.0, 0.001),),
        start_bce=3100,
        end_bce=2900,
        step_years=50,
        sample_count=2,
        seed=37,
        source="steppe",
        region="central_europe__a",
    )


def _targets() -> TargetDataset:
    """Return three target rows with target IDs encoded in notes."""
    rows = (
        ("central_europe__a", "target-a", "GroupA", 0.2),
        ("central_europe__b", "target-b", "GroupB", 0.1),
        ("central_europe__c", "target-c", "GroupC", 0.15),
    )
    return TargetDataset.from_rows(
        TargetObservation(
            status="synthetic",
            region=region,
            source="steppe",
            time_bce=2950,
            mean=mean,
            uncertainty=0.1,
            citation_key="synthetic",
            citation="Synthetic target",
            note=f"target_id={target_id}; requested_group_id={group_id}",
        )
        for region, target_id, group_id, mean in rows
    )


def _folds() -> tuple[StructuralSMCValidationFoldSpec, ...]:
    """Return one explicit fold per target region."""
    return tuple(
        StructuralSMCValidationFoldSpec(
            name=region,
            categories=("explicit",),
            holdout_value=region,
        )
        for region in ("central_europe__a", "central_europe__b", "central_europe__c")
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


def _overrides() -> ChildRegionOverrideSet:
    """Return a tiny child-region override set for validation tests."""
    return ChildRegionOverrideSet(
        counts={"central_europe__b": {"local": 820, "steppe": 32}},
    )


def _targets_csv() -> str:
    """Return a CSV serialization of the synthetic targets."""
    return (
        "status,region,source,time_bce,mean,uncertainty,citation_key,citation,note\n"
        "synthetic,central_europe__a,steppe,2950,0.2,0.1,synthetic,"
        "Synthetic target,target_id=target-a; requested_group_id=GroupA\n"
        "synthetic,central_europe__b,steppe,2950,0.1,0.1,synthetic,"
        "Synthetic target,target_id=target-b; requested_group_id=GroupB\n"
        "synthetic,central_europe__c,steppe,2950,0.15,0.1,synthetic,"
        "Synthetic target,target_id=target-c; requested_group_id=GroupC\n"
    )


def _sample_audit_csv(*, include_critical: bool) -> str:
    """Return sample-audit rows with one repeated/high-SE target."""
    critical_row = (
        "target-c,GroupC,0.15,,true,true,assessment=CRITICAL\n"
        if include_critical
        else "target-c,GroupC,0.15,,true,true,\n"
    )
    return (
        "target_id,requested_group_id,estimate,sample_flags,has_metadata,"
        "has_estimate,sample_metadata_note\n"
        "target-a,GroupA,0.2,high_se,true,true,\n"
        "target-a,GroupA,0.2,high_se,true,true,\n"
        "target-b,GroupB,0.1,,true,true,\n"
        f"{critical_row}"
    )


def _overrides_toml() -> str:
    """Return a tiny child-region override TOML file."""
    return "[review]\n\n" "[counts.central_europe__b]\n" "local = 820\n" "steppe = 32\n"
