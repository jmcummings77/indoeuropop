"""Tests for override validation delta reports."""

import json
from collections.abc import Callable
from math import inf
from pathlib import Path

import pytest

from indoeuropop.orchestration.override_delta import (
    OverrideDeltaOutputPaths,
    override_delta_artifacts,
    override_delta_experiment_manifest,
    run_override_delta_workflow,
)
from indoeuropop.reporting.override_delta import (
    OverrideDeltaReport,
    OverrideDeltaRow,
    ValidationBestFit,
    load_override_delta_report,
    override_delta_markdown,
    override_delta_rows,
    override_delta_to_csv,
    write_override_delta_csv,
    write_override_delta_markdown,
)


def _matching_delta_row(
    holdout_field: str = "region",
    holdout_value: str = "britain",
) -> OverrideDeltaRow:
    """Return one valid no-change delta row for dataclass tests."""
    best = ValidationBestFit(holdout_field, holdout_value, 1, 0.1, 0.2, 0.1)
    return OverrideDeltaRow(best, best)


def _validation_csv(
    values: tuple[tuple[str, float], ...],
    *,
    rank: str = "1",
) -> str:
    """Return minimal validation CSV text for report tests."""
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
            f"{rank},"
            f"{index},"
            "0.1,"
            f"{validation_metric},"
            f"{validation_metric - 0.1}"
        )
    return "\n".join(lines) + "\n"


def test_override_delta_report_summarizes_priority_and_protected_folds(
    tmp_path: Path,
) -> None:
    """The report should compare rank-one validation metrics by holdout."""
    baseline_path = tmp_path / "baseline.csv"
    override_path = tmp_path / "override.csv"
    delta_path = tmp_path / "delta.csv"
    report_path = tmp_path / "delta.md"
    baseline_path.write_text(_validation_csv((("britain", 0.12), ("tiefbrunn", 0.63))))
    override_path.write_text(_validation_csv((("britain", 0.15), ("tiefbrunn", 0.20))))

    report = load_override_delta_report(
        baseline_path,
        override_path,
        priority_values=("tiefbrunn",),
        protected_values=("britain",),
        tolerance=0.01,
    )
    rows = override_delta_rows(report)

    assert report.holdout_field == "region"
    assert report.mean_validation_delta == pytest.approx(-0.2)
    assert report.priority_mean_delta == pytest.approx(-0.43)
    assert report.protected_max_delta == pytest.approx(0.03)
    assert report.protected_degraded is True
    assert rows[0]["holdout_value"] == "britain"
    assert rows[0]["protected_degraded"] == "true"
    assert rows[1]["improved"] == "true"
    assert override_delta_to_csv(report).startswith("holdout_field,holdout_value")
    assert "Override Validation Delta Review" in override_delta_markdown(report)
    assert write_override_delta_csv(report, delta_path) == delta_path
    assert write_override_delta_markdown(report, report_path) == report_path
    assert "tiefbrunn" in report_path.read_text(encoding="utf-8")


def test_override_delta_report_without_selectors_has_zero_selector_deltas() -> None:
    """Selector summaries should be zero when no selectors are supplied."""
    best = ValidationBestFit("region", "britain", 1, 0.2, 0.3, 0.1)
    report = OverrideDeltaReport(
        metric="root_mean_squared_error",
        rows=(OverrideDeltaRow(best, best),),
    )

    assert report.priority_mean_delta == 0.0
    assert report.protected_max_delta == 0.0
    assert report.worst_validation_delta == 0.0
    assert report.protected_degraded is False


def test_override_delta_workflow_writes_outputs_and_manifest(tmp_path: Path) -> None:
    """The workflow should write CSV, Markdown, and checksummed manifest outputs."""
    baseline_path = tmp_path / "baseline.csv"
    override_path = tmp_path / "override.csv"
    output_dir = tmp_path / "outputs"
    baseline_path.write_text(_validation_csv((("britain", 0.12),)))
    override_path.write_text(_validation_csv((("britain", 0.10),)))

    result = run_override_delta_workflow(
        baseline_path,
        override_path,
        paths=OverrideDeltaOutputPaths(
            baseline_validation_fit_csv=baseline_path,
            override_validation_fit_csv=override_path,
            override_delta_csv=output_dir / "delta.csv",
            override_delta_report_md=output_dir / "delta.md",
            manifest_json=output_dir / "manifest.json",
        ),
        manifest_metadata={"scenario": "synthetic"},
    )
    payload = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))

    assert result.override_delta_csv_path == output_dir / "delta.csv"
    assert result.override_delta_report_md_path == output_dir / "delta.md"
    assert result.manifest_json_path == output_dir / "manifest.json"
    assert payload["name"] == "override-validation-delta"
    assert payload["metadata"]["scenario"] == "synthetic"
    assert payload["metadata"]["protected_degraded"] == "false"
    assert payload["artifacts"][0]["name"] == "baseline_validation_fit_csv"
    assert all(artifact.checksum_sha256 for artifact in result.artifacts)
    assert override_delta_experiment_manifest(
        result.report, artifacts=result.artifacts
    ).artifact_names() == (
        "baseline_validation_fit_csv",
        "override_validation_fit_csv",
        "override_delta_csv",
        "override_delta_report_md",
    )
    assert len(override_delta_artifacts(OverrideDeltaOutputPaths())) == 0


@pytest.mark.parametrize(
    ("factory", "match"),
    [
        (
            lambda: ValidationBestFit("", "britain", 1, 0.1, 0.2, 0.1),
            "holdout_field",
        ),
        (
            lambda: ValidationBestFit("region", "", 1, 0.1, 0.2, 0.1),
            "holdout_value",
        ),
        (
            lambda: ValidationBestFit("region", "britain", -1, 0.1, 0.2, 0.1),
            "run_index",
        ),
        (
            lambda: ValidationBestFit("region", "britain", 1, inf, 0.2, 0.1),
            "calibration_metric",
        ),
        (
            lambda: OverrideDeltaRow(
                ValidationBestFit("region", "britain", 1, 0.1, 0.2, 0.1),
                ValidationBestFit("source", "britain", 1, 0.1, 0.2, 0.1),
            ),
            "holdout fields",
        ),
        (
            lambda: OverrideDeltaRow(
                ValidationBestFit("region", "britain", 1, 0.1, 0.2, 0.1),
                ValidationBestFit("region", "gaul", 1, 0.1, 0.2, 0.1),
            ),
            "holdout values",
        ),
        (
            lambda: OverrideDeltaRow(
                ValidationBestFit("region", "britain", 1, 0.1, 0.2, 0.1),
                ValidationBestFit("region", "britain", 1, 0.1, 0.2, 0.1),
                tolerance=-0.1,
            ),
            "tolerance",
        ),
        (
            lambda: OverrideDeltaReport("unknown", (_matching_delta_row(),)),
            "unsupported fit metric",
        ),
        (
            lambda: OverrideDeltaReport("root_mean_squared_error", ()),
            "at least one",
        ),
        (
            lambda: OverrideDeltaReport(
                "root_mean_squared_error",
                (_matching_delta_row(),),
                tolerance=-0.1,
            ),
            "tolerance",
        ),
        (
            lambda: OverrideDeltaReport(
                "root_mean_squared_error",
                (
                    _matching_delta_row("region", "britain"),
                    _matching_delta_row("source", "steppe"),
                ),
            ),
            "one holdout field",
        ),
    ],
)
def test_override_delta_dataclasses_reject_invalid_values(
    factory: Callable[[], object],
    match: str,
) -> None:
    """Dataclass guards should fail clearly for invalid report values."""
    with pytest.raises(ValueError, match=match):
        factory()


@pytest.mark.parametrize(
    ("baseline_csv", "override_csv", "match"),
    [
        ("", _validation_csv((("britain", 0.1),)), "header"),
        (
            _validation_csv((("britain", 0.1),), rank="2"),
            _validation_csv((("britain", 0.1),)),
            "rank-one",
        ),
        (
            _validation_csv((("britain", 0.1), ("britain", 0.2))),
            _validation_csv((("britain", 0.1),)),
            "duplicate",
        ),
        (
            _validation_csv((("britain", 0.1),)),
            _validation_csv((("gaul", 0.1),)),
            "holdouts must match",
        ),
        (
            _validation_csv((("britain", 0.1),)).replace("holdout_field", "missing"),
            _validation_csv((("britain", 0.1),)),
            "missing required field",
        ),
        (
            _validation_csv((("britain", 0.1),)).replace(",1,", ",bad,"),
            _validation_csv((("britain", 0.1),)),
            "integer",
        ),
        (
            _validation_csv((("britain", 0.1),)).replace(",1,", ",-1,"),
            _validation_csv((("britain", 0.1),)),
            "non-negative",
        ),
        (
            _validation_csv((("britain", 0.1),)).replace(",0.1,", ",bad,"),
            _validation_csv((("britain", 0.1),)),
            "numeric",
        ),
        (
            _validation_csv((("britain", 0.1),)).replace(",0.1,", ",inf,"),
            _validation_csv((("britain", 0.1),)),
            "finite",
        ),
    ],
)
def test_load_override_delta_report_rejects_malformed_validation_csv(
    tmp_path: Path,
    baseline_csv: str,
    override_csv: str,
    match: str,
) -> None:
    """Malformed validation CSV inputs should produce clear errors."""
    baseline_path = tmp_path / "baseline.csv"
    override_path = tmp_path / "override.csv"
    baseline_path.write_text(baseline_csv, encoding="utf-8")
    override_path.write_text(override_csv, encoding="utf-8")

    with pytest.raises(ValueError, match=match):
        load_override_delta_report(baseline_path, override_path)


def test_load_override_delta_report_rejects_unsupported_metric(tmp_path: Path) -> None:
    """Validation delta loading should reject unknown metrics before parsing."""
    baseline_path = tmp_path / "baseline.csv"
    override_path = tmp_path / "override.csv"
    baseline_path.write_text(_validation_csv((("britain", 0.1),)), encoding="utf-8")
    override_path.write_text(_validation_csv((("britain", 0.1),)), encoding="utf-8")

    with pytest.raises(ValueError, match="unsupported fit metric"):
        load_override_delta_report(baseline_path, override_path, metric="unknown")
