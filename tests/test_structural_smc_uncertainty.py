"""Tests for uncertainty-aware structural SMC disagreement review."""

from __future__ import annotations

from math import inf
from pathlib import Path

import pytest
from pytest import CaptureFixture

from indoeuropop.orchestration.cli import main
from indoeuropop.reporting.structural_smc_uncertainty import (
    StructuralSMCUncertaintyReport,
    load_structural_smc_uncertainty_report,
    structural_smc_uncertainty_markdown,
    structural_smc_uncertainty_rows,
    structural_smc_uncertainty_to_csv,
    write_structural_smc_uncertainty_csv,
    write_structural_smc_uncertainty_markdown,
)


def test_structural_smc_uncertainty_report_scores_targets(
    tmp_path: Path,
) -> None:
    """Uncertainty review should rescale residuals by target uncertainty."""
    summary_path, output_dir = _write_uncertainty_inputs(tmp_path)
    report = load_structural_smc_uncertainty_report(
        summary_path,
        output_dir,
        material_chi_square_delta=1.0,
    )
    rows = structural_smc_uncertainty_rows(report)
    csv_text = structural_smc_uncertainty_to_csv(report)
    markdown = structural_smc_uncertainty_markdown(report)

    assert report.fold_count == 1
    assert report.target_count == 3
    assert report.structured_pulse_target_count == 1
    assert report.child_override_target_count == 1
    assert report.uncertainty_tie_target_count == 1
    assert report.ranked_rows[0].disagreement.requested_group_id == "GroupA"
    assert rows[0]["structured_pulse_z_score"] == "0.5"
    assert rows[0]["child_override_z_score"] == "-2"
    assert rows[0]["uncertainty_weighted_preferred_candidate"] == "structured_pulse"
    assert rows[2]["uncertainty_weighted_preferred_candidate"] == "uncertainty_tie"
    assert "child_minus_structured_pulse_chi_square_delta" in csv_text
    assert "Structural SMC Uncertainty-Aware" in markdown
    assert "uncertainty_tie_target_count: 1" in markdown


def test_structural_smc_uncertainty_report_writes_files(tmp_path: Path) -> None:
    """Uncertainty reports should write CSV and Markdown artifacts."""
    summary_path, output_dir = _write_uncertainty_inputs(tmp_path)
    report = load_structural_smc_uncertainty_report(summary_path, output_dir)
    csv_path = tmp_path / "reports" / "uncertainty.csv"
    markdown_path = tmp_path / "reports" / "uncertainty.md"

    assert write_structural_smc_uncertainty_csv(report, csv_path) == csv_path
    assert (
        write_structural_smc_uncertainty_markdown(report, markdown_path)
        == markdown_path
    )
    assert csv_path.read_text(encoding="utf-8") == structural_smc_uncertainty_to_csv(
        report
    )
    assert markdown_path.read_text(
        encoding="utf-8"
    ) == structural_smc_uncertainty_markdown(report)


def test_structural_smc_uncertainty_handles_empty_reports(tmp_path: Path) -> None:
    """Uncertainty reports should serialize cleanly when no folds disagree."""
    summary_path = tmp_path / "summary.csv"
    summary_path.write_text(_summary_csv(disagreement="false"), encoding="utf-8")
    report = load_structural_smc_uncertainty_report(summary_path, tmp_path)

    assert report.fold_count == 0
    assert report.target_count == 0
    assert "target_count: 0" in structural_smc_uncertainty_markdown(report)


def test_structural_smc_uncertainty_rejects_bad_threshold() -> None:
    """Material chi-square thresholds should be finite and non-negative."""
    with pytest.raises(ValueError, match="material_chi_square_delta"):
        StructuralSMCUncertaintyReport((), material_chi_square_delta=-1.0)
    with pytest.raises(ValueError, match="material_chi_square_delta"):
        StructuralSMCUncertaintyReport((), material_chi_square_delta=inf)


def test_cli_review_structural_smc_uncertainty_writes_outputs(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    """The CLI should write uncertainty-aware disagreement outputs."""
    summary_path, output_dir = _write_uncertainty_inputs(tmp_path)
    csv_path = tmp_path / "uncertainty.csv"
    markdown_path = tmp_path / "uncertainty.md"

    exit_code = main(
        [
            "review-structured-smc-uncertainty",
            "--smc-validation-summary-csv",
            str(summary_path),
            "--smc-validation-output-dir",
            str(output_dir),
            "--smc-uncertainty-csv",
            str(csv_path),
            "--smc-uncertainty-report-md",
            str(markdown_path),
            "--smc-material-chi-square-delta",
            "1.0",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert f"smc_uncertainty_csv={csv_path}" in captured.out
    assert f"smc_uncertainty_report={markdown_path}" in captured.out
    assert "smc_uncertainty_fold_count=1" in captured.out
    assert "smc_uncertainty_tie_target_count=1" in captured.out
    assert "GroupC" in markdown_path.read_text(encoding="utf-8")


def test_cli_review_structural_smc_uncertainty_can_print_markdown(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    """The CLI should print uncertainty Markdown when no report path is supplied."""
    summary_path, output_dir = _write_uncertainty_inputs(tmp_path)

    exit_code = main(
        [
            "review-structured-smc-uncertainty",
            "--smc-validation-summary-csv",
            str(summary_path),
            "--smc-validation-output-dir",
            str(output_dir),
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "# Structural SMC Uncertainty-Aware" in captured.out
    assert "smc_uncertainty_target_count=3" in captured.out


def test_cli_review_structural_smc_uncertainty_requires_inputs() -> None:
    """The CLI should reject missing uncertainty-review inputs."""
    with pytest.raises(SystemExit, match="2"):
        main(["review-structured-smc-uncertainty"])
    with pytest.raises(SystemExit, match="2"):
        main(
            [
                "review-structured-smc-uncertainty",
                "--smc-validation-summary-csv",
                "summary.csv",
            ]
        )


def _write_uncertainty_inputs(tmp_path: Path) -> tuple[Path, Path]:
    """Write compact validation summary and posterior-predictive artifacts."""
    output_dir = tmp_path / "validation"
    fold_dir = output_dir / "fold_a"
    fold_dir.mkdir(parents=True)
    summary_path = output_dir / "summary.csv"
    summary_path.write_text(_summary_csv(), encoding="utf-8")
    (fold_dir / "holdout-targets.csv").write_text(_target_csv(), encoding="utf-8")
    (fold_dir / "smc-baseline-holdout-posterior-predictive.csv").write_text(
        _predictive_csv(
            ("0.45", "-0.05", "0.05"),
            ("0.65", "0.05", "0.05"),
            ("0.72", "0.02", "0.02"),
        ),
        encoding="utf-8",
    )
    (fold_dir / "smc-structured-pulse-holdout-posterior-predictive.csv").write_text(
        _predictive_csv(
            ("0.55", "0.05", "0.05"),
            ("0.9", "0.3", "0.3"),
            ("0.73", "0.03", "0.03"),
        ),
        encoding="utf-8",
    )
    (fold_dir / "smc-child-override-holdout-posterior-predictive.csv").write_text(
        _predictive_csv(
            ("0.3", "-0.2", "0.2"),
            ("0.5", "-0.1", "0.1"),
            ("0.67", "-0.03", "0.03"),
        ),
        encoding="utf-8",
    )
    return summary_path, output_dir


def _summary_csv(disagreement: str = "true") -> str:
    """Return a compact structural validation summary CSV."""
    return (
        "fold_name,categories,calibration_preferred_candidate,"
        "holdout_preferred_candidate,preference_disagreement,"
        "holdout_child_minus_structured_pulse_rmse_delta\n"
        f"fold_a,protected,child_override,structured_pulse,{disagreement},0.03\n"
    )


def _target_csv() -> str:
    """Return held-out target observations with note metadata."""
    header = "status,region,source,time_bce,mean,uncertainty,citation_key,citation,note"
    notes = (
        "target_id=target-a; requested_group_id=GroupA; sample_count=2",
        "target_id=target-b; requested_group_id=GroupB; sample_count=2",
        "target_id=target-c; requested_group_id=GroupC; sample_count=1",
    )
    return "\n".join(
        (
            header,
            f"published,fold_a,steppe,2300,0.5,0.1,key,Citation,{notes[0]}",
            f"published,fold_a,steppe,2200,0.6,0.2,key,Citation,{notes[1]}",
            f"published,fold_a,steppe,2100,0.7,0.3,key,Citation,{notes[2]}",
            "",
        )
    )


def _predictive_csv(
    first: tuple[str, str, str],
    second: tuple[str, str, str],
    third: tuple[str, str, str],
) -> str:
    """Return posterior-predictive rows from prediction, residual, and abs."""
    return "\n".join(
        (
            "observation_index,prediction_mean,mean_residual,"
            "absolute_mean_residual,observed_inside_interval",
            f"0,{first[0]},{first[1]},{first[2]},true",
            f"1,{second[0]},{second[1]},{second[2]},false",
            f"2,{third[0]},{third[1]},{third[2]},true",
            "",
        )
    )
