"""CLI tests for target residual review reports."""

from pathlib import Path

from pytest import CaptureFixture, raises

from indoeuropop.orchestration.cli import main


def _residual_csv() -> str:
    """Return target residual CSV text for CLI tests."""
    return "\n".join(
        (
            "target_index,status,region,source,time_bce,observed_mean,uncertainty,"
            "predicted,residual,z_score,citation_key,citation,note",
            "1,published,central_europe,steppe,2235,0.02,0.1,0.5,0.48,4.8,key,"
            "Citation,requested_group_id=Germany_StkrStraubing_BellBeaker",
        )
    )


def test_cli_review_target_residuals_writes_markdown(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    """The CLI should write a target residual review report."""
    residuals_path = tmp_path / "target-residuals.csv"
    diagnostics_path = tmp_path / "diagnostics.json"
    report_path = tmp_path / "reports" / "target-review.md"
    residuals_path.write_text(_residual_csv(), encoding="utf-8")
    diagnostics_path.write_text('{"dropped_target_count": 26}', encoding="utf-8")

    exit_code = main(
        [
            "review-target-residuals",
            "--target-residuals",
            str(residuals_path),
            "--target-diagnostics-json",
            str(diagnostics_path),
            "--target-review-md",
            str(report_path),
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert f"target_review={report_path}" in captured.out
    assert "outlier_count=1" in captured.out
    assert "Germany_StkrStraubing_BellBeaker" in report_path.read_text(encoding="utf-8")


def test_cli_review_target_residuals_can_print_markdown(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    """The CLI should print Markdown when no report path is supplied."""
    residuals_path = tmp_path / "target-residuals.csv"
    residuals_path.write_text(_residual_csv(), encoding="utf-8")

    exit_code = main(
        ["review-target-residuals", "--target-residuals", str(residuals_path)]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "# Target Residual Review" in captured.out
    assert "residual_count=1" in captured.out


def test_cli_review_target_residuals_requires_input() -> None:
    """The CLI should reject missing residual CSV input."""
    with raises(SystemExit) as exc_info:
        main(["review-target-residuals"])
    assert exc_info.value.code == 2
