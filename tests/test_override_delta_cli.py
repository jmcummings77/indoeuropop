"""CLI tests for override validation delta reports."""

from pathlib import Path

import pytest
from pytest import CaptureFixture

from indoeuropop.orchestration.cli import main


def test_cli_review_override_deltas_writes_reports(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    """The CLI should write delta CSV, Markdown, and manifest artifacts."""
    baseline_path = tmp_path / "baseline-validation.csv"
    override_path = tmp_path / "override-validation.csv"
    output_dir = tmp_path / "outputs"
    delta_csv = output_dir / "override-delta.csv"
    report_md = output_dir / "override-delta.md"
    manifest_json = output_dir / "manifest.json"
    baseline_path.write_text(_validation_csv((("britain", 0.12), ("tiefbrunn", 0.63))))
    override_path.write_text(_validation_csv((("britain", 0.15), ("tiefbrunn", 0.20))))

    exit_code = main(
        [
            "review-override-deltas",
            "--baseline-validation-fit-csv",
            str(baseline_path),
            "--override-validation-fit-csv",
            str(override_path),
            "--priority-validation-value",
            "tiefbrunn",
            "--protected-validation-value",
            "britain",
            "--override-delta-csv",
            str(delta_csv),
            "--override-delta-report-md",
            str(report_md),
            "--manifest-json",
            str(manifest_json),
            "--fit-metric",
            "root_mean_squared_error",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert f"override_delta_report={report_md}" in captured.out
    assert f"override_delta_csv={delta_csv}" in captured.out
    assert f"manifest_json={manifest_json}" in captured.out
    assert "priority_mean_delta=-0.430000" in captured.out
    assert "protected_degraded=true" in captured.out
    assert "tiefbrunn" in delta_csv.read_text(encoding="utf-8")
    assert "Override Validation Delta Review" in report_md.read_text(encoding="utf-8")


def test_cli_review_override_deltas_can_print_markdown(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    """The CLI should print Markdown when no report path is supplied."""
    baseline_path = tmp_path / "baseline-validation.csv"
    override_path = tmp_path / "override-validation.csv"
    baseline_path.write_text(_validation_csv((("britain", 0.12),)))
    override_path.write_text(_validation_csv((("britain", 0.10),)))

    exit_code = main(
        [
            "review-override-deltas",
            "--baseline-validation-fit-csv",
            str(baseline_path),
            "--override-validation-fit-csv",
            str(override_path),
            "--fit-metric",
            "root_mean_squared_error",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "# Override Validation Delta Review" in captured.out
    assert "override_delta_fold_count=1" in captured.out


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        (["review-override-deltas"], "requires --baseline-validation-fit-csv"),
        (
            [
                "review-override-deltas",
                "--baseline-validation-fit-csv",
                "baseline.csv",
            ],
            "requires --override-validation-fit-csv",
        ),
    ],
)
def test_cli_review_override_deltas_requires_inputs(
    arguments: list[str],
    message: str,
    capsys: CaptureFixture[str],
) -> None:
    """The CLI should reject missing override-delta inputs."""
    with pytest.raises(SystemExit, match="2"):
        main(arguments)
    captured = capsys.readouterr()

    assert message in captured.err


def _validation_csv(values: tuple[tuple[str, float], ...]) -> str:
    """Return minimal validation CSV text for CLI tests."""
    lines = [
        "holdout_field,holdout_value,rank,run_index,"
        "calibration_root_mean_squared_error,"
        "validation_root_mean_squared_error,"
        "generalization_gap_root_mean_squared_error"
    ]
    for index, (holdout_value, validation_metric) in enumerate(values, start=1):
        lines.append(
            "region,"
            f"{holdout_value},"
            "1,"
            f"{index},"
            "0.1,"
            f"{validation_metric},"
            f"{validation_metric - 0.1}"
        )
    return "\n".join(lines) + "\n"
