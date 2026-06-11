"""CLI tests for validation-guided target-parameter refinement."""

import json
from pathlib import Path

from pytest import CaptureFixture

from indoeuropop.orchestration.cli import main


def test_cli_refine_target_parameters_writes_outputs(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    """The refinement command should write summary, range, report, and manifest."""
    config_path = tmp_path / "sweep.toml"
    target_path = tmp_path / "targets.csv"
    output_dir = tmp_path / "outputs"
    summary_path = output_dir / "refinement-summary.csv"
    ranges_path = output_dir / "refinement-ranges.csv"
    report_path = output_dir / "refinement.md"
    manifest_path = output_dir / "refinement-manifest.json"
    _write_refinement_config(config_path)
    _write_refinement_targets(target_path)

    exit_code = main(
        [
            "refine-target-parameters",
            "--config",
            str(config_path),
            "--targets",
            str(target_path),
            "--priority-validation-value",
            "central_europe",
            "--protected-validation-value",
            "britain",
            "--refinement-summary-csv",
            str(summary_path),
            "--refinement-ranges-csv",
            str(ranges_path),
            "--refinement-report-md",
            str(report_path),
            "--manifest-json",
            str(manifest_path),
            "--fit-metric",
            "root_mean_squared_error",
        ]
    )
    captured = capsys.readouterr()
    manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert "refinement_candidate_count=3" in captured.out
    assert "refinement_candidate=baseline" in captured.out
    assert "priority_mean_delta" in summary_path.read_text(encoding="utf-8")
    assert "migration_rate" in ranges_path.read_text(encoding="utf-8")
    assert "Validation-Guided" in report_path.read_text(encoding="utf-8")
    assert manifest_payload["name"] == "cli-target-parameter-refinement"


def _write_refinement_config(path: Path) -> None:
    """Write a tiny two-region sweep config for CLI refinement tests."""
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
                "elite_reproductive_advantage = 1.02",
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
                "",
                "[[parameter_ranges]]",
                'name = "elite_reproductive_advantage"',
                "low = 1.0",
                "high = 1.08",
            )
        )
        + "\n",
        encoding="utf-8",
    )


def _write_refinement_targets(path: Path) -> None:
    """Write a tiny two-region target CSV for CLI refinement tests."""
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
