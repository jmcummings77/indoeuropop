"""CLI tests for held-out target-validation workflows."""

import json
from pathlib import Path

from pytest import CaptureFixture

from indoeuropop.orchestration.cli import main


def test_cli_validate_targets_writes_held_out_outputs(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    """The validate-targets command should write held-out fit artifacts."""
    config_path = tmp_path / "sweep.toml"
    target_path = tmp_path / "targets.csv"
    output_dir = tmp_path / "outputs"
    validation_fit_csv = output_dir / "validation-fit.csv"
    validation_report_md = output_dir / "validation.md"
    manifest_path = output_dir / "validation-manifest.json"
    _write_validation_config(config_path)
    _write_validation_targets(target_path)

    exit_code = main(
        [
            "validate-targets",
            "--config",
            str(config_path),
            "--targets",
            str(target_path),
            "--validation-fit-csv",
            str(validation_fit_csv),
            "--validation-report-md",
            str(validation_report_md),
            "--manifest-json",
            str(manifest_path),
            "--fit-metric",
            "root_mean_squared_error",
        ]
    )
    captured = capsys.readouterr()
    manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert "validation_fold_count=2" in captured.out
    assert "validation_fit_csv=" in captured.out
    assert "validation_root_mean_squared_error" in validation_fit_csv.read_text(
        encoding="utf-8"
    )
    assert "ranking_metric: `root_mean_squared_error`" in (
        validation_report_md.read_text(encoding="utf-8")
    )
    assert manifest_payload["name"] == "cli-target-validation"
    assert manifest_payload["metadata"]["holdout_field"] == "region"


def _write_validation_config(path: Path) -> None:
    """Write a tiny two-region sweep config for CLI validation tests."""
    path.write_text(
        "\n".join(
            (
                "[simulation]",
                "start_bce = 3000",
                "end_bce = 2900",
                "step_years = 50",
                "",
                "[parameters]",
                "migration_rate = 0.001",
                "",
                "[counts.britain]",
                "local = 1000",
                "steppe = 20",
                "",
                "[counts.central_europe]",
                "local = 1000",
                "steppe = 40",
                "",
                "[sweep]",
                "sample_count = 2",
                "seed = 23",
                'source = "steppe"',
                'region = "britain"',
                "",
                "[[parameter_ranges]]",
                'name = "migration_rate"',
                "low = 0.001",
                "high = 0.003",
            )
        )
        + "\n",
        encoding="utf-8",
    )


def _write_validation_targets(path: Path) -> None:
    """Write a tiny two-region target CSV for CLI validation tests."""
    path.write_text(
        "\n".join(
            (
                "status,region,source,time_bce,mean,uncertainty,citation_key,"
                "citation,note",
                "synthetic,britain,steppe,2900,0.05,0.03,synthetic,"
                "Synthetic target,requested_group_id=britain_group",
                "synthetic,central_europe,steppe,2900,0.08,0.04,synthetic,"
                "Synthetic target,requested_group_id=central_group",
            )
        )
        + "\n",
        encoding="utf-8",
    )
