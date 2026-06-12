"""Tests for structural SMC disagreement diagnostics."""

from __future__ import annotations

import argparse
from math import inf
from pathlib import Path

import pytest
from pytest import CaptureFixture

from indoeuropop.data.targets import TargetObservation
from indoeuropop.orchestration.cli import main
from indoeuropop.orchestration.report_cli import run_report_command
from indoeuropop.reporting.structural_smc_disagreement_models import (
    StructuralSMCDisagreementRow,
    required_cell,
)
from indoeuropop.reporting.structural_smc_disagreements import (
    load_structural_smc_disagreement_report,
    structural_smc_disagreement_markdown,
    structural_smc_disagreement_rows,
    structural_smc_disagreement_to_csv,
    write_structural_smc_disagreement_csv,
    write_structural_smc_disagreement_markdown,
)


def test_structural_smc_disagreement_report_joins_metadata_and_residuals(
    tmp_path: Path,
) -> None:
    """Disagreement reports should join fold, target, and predictive rows."""
    summary_path, output_dir = _write_disagreement_inputs(tmp_path)

    report = load_structural_smc_disagreement_report(summary_path, output_dir)
    rows = structural_smc_disagreement_rows(report)
    csv_text = structural_smc_disagreement_to_csv(report)
    markdown = structural_smc_disagreement_markdown(report)

    assert report.disagreement_fold_count == 1
    assert report.target_count == 2
    assert report.structured_pulse_target_count == 1
    assert report.child_override_target_count == 1
    assert report.ranked_rows[0].requested_group_id == "GroupA"
    assert rows[0]["target_id"] == "target-a"
    assert rows[0]["sample_count"] == "2"
    assert rows[1]["sample_count"] == ""
    assert rows[0]["target_preferred_candidate"] == "structured_pulse"
    assert rows[1]["target_preferred_candidate"] == "child_override"
    assert "child_minus_structured_pulse_abs_residual_delta" in csv_text
    assert "Structural SMC Disagreement Diagnostics" in markdown
    assert "GroupA" in markdown


def test_structural_smc_disagreement_report_writes_files(tmp_path: Path) -> None:
    """Disagreement reports should write CSV and Markdown artifacts."""
    summary_path, output_dir = _write_disagreement_inputs(tmp_path)
    report = load_structural_smc_disagreement_report(summary_path, output_dir)
    csv_path = tmp_path / "reports" / "disagreements.csv"
    markdown_path = tmp_path / "reports" / "disagreements.md"

    assert write_structural_smc_disagreement_csv(report, csv_path) == csv_path
    assert (
        write_structural_smc_disagreement_markdown(report, markdown_path)
        == markdown_path
    )
    assert csv_path.read_text(encoding="utf-8") == structural_smc_disagreement_to_csv(
        report
    )
    assert markdown_path.read_text(
        encoding="utf-8"
    ) == structural_smc_disagreement_markdown(report)


def test_structural_smc_disagreement_report_allows_no_disagreements(
    tmp_path: Path,
) -> None:
    """Reports should serialize cleanly when no folds disagree."""
    summary_path = tmp_path / "summary.csv"
    summary_path.write_text(_summary_csv(disagreement="false"), encoding="utf-8")

    report = load_structural_smc_disagreement_report(summary_path, tmp_path)

    assert report.disagreement_fold_count == 0
    assert report.target_count == 0
    assert "joined_target_count: 0" in structural_smc_disagreement_markdown(report)


def test_structural_smc_disagreement_models_validate_values() -> None:
    """Disagreement model rows should reject ambiguous or invalid values."""
    valid_row = _model_row(sample_count=1)
    tie_row = _model_row(
        pulse=_predictive_row(abs_residual="0.1"),
        child=_predictive_row(abs_residual="0.1"),
    )

    assert valid_row.baseline_prediction_mean == pytest.approx(0.2)
    assert valid_row.target_preferred_candidate == "structured_pulse"
    assert tie_row.target_preferred_candidate == "tie"
    with pytest.raises(ValueError, match="fold_name"):
        _model_row(fold_name="")
    with pytest.raises(ValueError, match="target_index"):
        _model_row(target_index=-1)
    with pytest.raises(ValueError, match="fold_holdout_delta"):
        _model_row(fold_holdout_delta=inf)
    with pytest.raises(ValueError, match="sample_count"):
        _model_row(sample_count=-1)
    with pytest.raises(ValueError, match="prediction_mean"):
        invalid_prediction = _model_row(baseline={"prediction_mean": "nan"})
        _ = invalid_prediction.baseline_prediction_mean


@pytest.mark.parametrize("value", [None, ""])
def test_required_cell_rejects_missing_values(value: str | None) -> None:
    """Required CSV cells should reject missing or blank values."""
    with pytest.raises(ValueError, match="fold_name is required"):
        required_cell({"fold_name": value}, "fold_name")


@pytest.mark.parametrize(
    ("writer", "expected"),
    [
        (lambda path: path.write_text("", encoding="utf-8"), "header row"),
        (
            lambda path: path.write_text(
                "fold_name,preference_disagreement\nfold,true\n", encoding="utf-8"
            ),
            "missing columns",
        ),
    ],
)
def test_structural_smc_disagreement_summary_loader_rejects_bad_csv(
    tmp_path: Path,
    writer: object,
    expected: str,
) -> None:
    """Validation summary loading should reject missing headers or columns."""
    summary_path = tmp_path / "summary.csv"
    assert callable(writer)
    writer(summary_path)

    with pytest.raises(ValueError, match=expected):
        load_structural_smc_disagreement_report(summary_path, tmp_path)


@pytest.mark.parametrize(
    ("file_name", "contents", "expected"),
    [
        ("smc-baseline-holdout-posterior-predictive.csv", "", "header row"),
        (
            "smc-structured-pulse-holdout-posterior-predictive.csv",
            "observation_index,prediction_mean\n0,0.1\n",
            "missing columns",
        ),
    ],
)
def test_structural_smc_disagreement_predictive_loader_rejects_bad_csv(
    tmp_path: Path,
    file_name: str,
    contents: str,
    expected: str,
) -> None:
    """Posterior-predictive loading should reject malformed model CSVs."""
    summary_path, output_dir = _write_disagreement_inputs(tmp_path)
    (output_dir / "fold_a" / file_name).write_text(contents, encoding="utf-8")

    with pytest.raises(ValueError, match=expected):
        load_structural_smc_disagreement_report(summary_path, output_dir)


def test_cli_review_structural_smc_disagreements_writes_outputs(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    """The CLI should write disagreement CSV and Markdown outputs."""
    summary_path, output_dir = _write_disagreement_inputs(tmp_path)
    csv_path = tmp_path / "diagnostics.csv"
    markdown_path = tmp_path / "diagnostics.md"

    exit_code = main(
        [
            "review-structured-smc-disagreements",
            "--smc-validation-summary-csv",
            str(summary_path),
            "--smc-validation-output-dir",
            str(output_dir),
            "--smc-disagreement-csv",
            str(csv_path),
            "--smc-disagreement-report-md",
            str(markdown_path),
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert f"smc_disagreement_csv={csv_path}" in captured.out
    assert f"smc_disagreement_report={markdown_path}" in captured.out
    assert "smc_disagreement_fold_count=1" in captured.out
    assert "smc_disagreement_structured_pulse_target_count=1" in captured.out
    assert csv_path.exists()
    assert "GroupA" in markdown_path.read_text(encoding="utf-8")


def test_cli_review_structural_smc_disagreements_can_print_markdown(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    """The CLI should print Markdown when no report path is supplied."""
    summary_path, output_dir = _write_disagreement_inputs(tmp_path)

    exit_code = main(
        [
            "review-structured-smc-disagreements",
            "--smc-validation-summary-csv",
            str(summary_path),
            "--smc-validation-output-dir",
            str(output_dir),
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "# Structural SMC Disagreement Diagnostics" in captured.out
    assert "smc_disagreement_target_count=2" in captured.out


def test_cli_review_structural_smc_disagreements_requires_inputs() -> None:
    """The CLI should reject missing disagreement-review inputs."""
    with pytest.raises(SystemExit, match="2"):
        main(["review-structured-smc-disagreements"])
    with pytest.raises(SystemExit, match="2"):
        main(
            [
                "review-structured-smc-disagreements",
                "--smc-validation-summary-csv",
                "summary.csv",
            ]
        )


def test_report_handler_ignores_unrelated_commands() -> None:
    """The delegated report handler should ignore unrelated commands."""
    assert (
        run_report_command(
            argparse.Namespace(command="demo"), argparse.ArgumentParser()
        )
        is None
    )


def _write_disagreement_inputs(tmp_path: Path) -> tuple[Path, Path]:
    """Write compact validation summary and fold artifacts."""
    output_dir = tmp_path / "validation"
    fold_dir = output_dir / "fold_a"
    fold_dir.mkdir(parents=True)
    summary_path = output_dir / "summary.csv"
    summary_path.write_text(_summary_csv(), encoding="utf-8")
    (fold_dir / "holdout-targets.csv").write_text(_target_csv(), encoding="utf-8")
    (fold_dir / "smc-baseline-holdout-posterior-predictive.csv").write_text(
        _predictive_csv(("0.2", "0.2"), ("0.4", "0.1")),
        encoding="utf-8",
    )
    (fold_dir / "smc-structured-pulse-holdout-posterior-predictive.csv").write_text(
        _predictive_csv(("0.55", "0.05"), ("0.7", "0.3")),
        encoding="utf-8",
    )
    (fold_dir / "smc-child-override-holdout-posterior-predictive.csv").write_text(
        _predictive_csv(("0.3", "0.2"), ("0.5", "0.1")),
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
        "fold_b,child,child_override,child_override,false,-0.02\n"
    )


def _target_csv() -> str:
    """Return two held-out target observations with note metadata."""
    header = "status,region,source,time_bce,mean,uncertainty,citation_key,citation,note"
    first_note = (
        "target_id=target-a; requested_group_id=GroupA; matched_group_ids=GroupA; "
        "publication_keys=PubA|PubB; sample_count=2; window_bce=2400-2200; "
        "aggregation_method=unweighted_mean; group_match_mode=exact"
    )
    second_note = (
        "target_id=target-b; requested_group_id=GroupB; matched_group_ids=GroupB; "
        "publication_keys=PubC"
    )
    return "\n".join(
        (
            header,
            f"published,fold_a,steppe,2300,0.5,0.1,key,Citation,{first_note}",
            f"published,fold_a,steppe,2200,0.6,0.2,key,Citation,{second_note}",
            "",
        )
    )


def _predictive_csv(first: tuple[str, str], second: tuple[str, str]) -> str:
    """Return posterior-predictive rows from prediction and absolute residuals."""
    return "\n".join(
        (
            "observation_index,prediction_mean,mean_residual,"
            "absolute_mean_residual,observed_inside_interval",
            f"0,{first[0]},0.01,{first[1]},true",
            f"1,{second[0]},-0.02,{second[1]},false",
            "",
        )
    )


def _model_row(
    *,
    fold_name: str = "fold",
    target_index: int = 0,
    fold_holdout_delta: float = 0.1,
    sample_count: int | None = 1,
    baseline: dict[str, str] | None = None,
    pulse: dict[str, str] | None = None,
    child: dict[str, str] | None = None,
) -> StructuralSMCDisagreementRow:
    """Return a directly constructed disagreement row."""
    return StructuralSMCDisagreementRow(
        fold_name=fold_name,
        categories="test",
        calibration_preferred_candidate="child_override",
        holdout_preferred_candidate="structured_pulse",
        fold_holdout_delta=fold_holdout_delta,
        target_index=target_index,
        target_id="target",
        requested_group_id="group",
        matched_group_ids="group",
        publication_keys="Pub",
        sample_count=sample_count,
        window_bce="2400-2200",
        aggregation_method="mean",
        group_match_mode="exact",
        observation=TargetObservation(
            status="synthetic",
            region="fold",
            source="steppe",
            time_bce=2300,
            mean=0.5,
            uncertainty=0.1,
            citation_key="key",
            citation="Citation",
        ),
        baseline=baseline or _predictive_row(prediction="0.2", abs_residual="0.3"),
        structured_pulse=pulse
        or _predictive_row(prediction="0.55", abs_residual="0.05"),
        child_override=child or _predictive_row(prediction="0.3", abs_residual="0.2"),
    )


def _predictive_row(
    *,
    prediction: str = "0.5",
    abs_residual: str = "0.1",
) -> dict[str, str]:
    """Return one posterior-predictive row mapping."""
    return {
        "prediction_mean": prediction,
        "mean_residual": "0.01",
        "absolute_mean_residual": abs_residual,
        "observed_inside_interval": "true",
    }
