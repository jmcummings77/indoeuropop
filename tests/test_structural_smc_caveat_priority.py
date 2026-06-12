"""Tests for prioritized structural SMC caveat review queues."""

from __future__ import annotations

from pathlib import Path

import pytest

from indoeuropop.orchestration.cli import main
from indoeuropop.orchestration.structural_smc_caveat_priority import (
    run_structural_smc_caveat_prioritization,
    structural_smc_caveat_priority_paths_from_dir,
)
from indoeuropop.orchestration.structural_smc_caveat_priority_models import (
    StructuralSMCCaveatPriorityPaths,
    StructuralSMCCaveatPriorityReport,
    StructuralSMCCaveatPriorityRow,
)
from indoeuropop.reporting.structural_smc_caveat_priority import (
    structural_smc_caveat_priority_markdown,
    structural_smc_caveat_priority_rows,
    structural_smc_caveat_priority_to_csv,
)


def test_caveat_prioritization_ranks_unresolved_actionable_rows(
    tmp_path: Path,
) -> None:
    """Priority scoring should surface unresolved high-impact caveats first."""
    drilldown = _write_drilldown(tmp_path)
    dispositions = _write_dispositions(tmp_path)

    report = run_structural_smc_caveat_prioritization(
        caveat_drilldown_csv=drilldown,
        caveat_dispositions_csv=dispositions,
        paths=structural_smc_caveat_priority_paths_from_dir(tmp_path / "priority"),
    )
    rows = structural_smc_caveat_priority_rows(report)
    markdown = structural_smc_caveat_priority_markdown(report)

    assert report.row_count == 6
    assert report.unresolved_count == 4
    assert report.reviewed_count == 2
    assert report.blocking_count == 1
    assert report.rows[0].caveat_type == "requires_manual_review"
    assert report.rows[0].review_status == "blocking"
    assert report.rows[1].caveat_type == "missing_override_regions"
    assert report.rows[1].priority_band == "critical"
    assert rows[1]["recommended_disposition"] == "configuration_gap"
    assert any(
        row["diagnostic_value"] == "sample_flag:high_se"
        and row["recommended_disposition"] == "accepted_caveat"
        for row in rows
    )
    assert "requires_qpadm_rerun" in structural_smc_caveat_priority_to_csv(report)
    assert "Highest Priority Rows" in markdown
    assert report.paths.priority_csv.exists()
    assert report.paths.report_md.exists()


def test_caveat_prioritization_defaults_to_unresolved_without_dispositions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A drilldown-only run should rank every caveat as unresolved."""
    monkeypatch.chdir(tmp_path)
    drilldown = _write_drilldown(tmp_path)

    report = run_structural_smc_caveat_prioritization(
        caveat_drilldown_csv=drilldown,
    )

    assert report.unresolved_count == 6
    assert report.reviewed_count == 0
    assert report.paths.priority_csv == Path(
        "structural-smc-caveat-priorities/structural-smc-caveat-priorities.csv"
    )
    assert any(row.priority_band == "medium" for row in report.rows)
    assert all(row.priority_band != "low" for row in report.rows)


def test_caveat_prioritization_cli_writes_outputs(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The top-level CLI should expose caveat prioritization."""
    drilldown = _write_drilldown(tmp_path)
    dispositions = _write_dispositions(tmp_path)
    output_dir = tmp_path / "priority-cli"

    exit_code = main(
        [
            "prioritize-structural-smc-caveat-dispositions",
            "--caveat-drilldown-csv",
            str(drilldown),
            "--caveat-dispositions-csv",
            str(dispositions),
            "--caveat-priority-output-dir",
            str(output_dir),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "structural_smc_caveat_prioritization=true" in captured.out
    assert "structural_smc_caveat_priority_top=rank=1" in captured.out
    assert (output_dir / "structural-smc-caveat-priorities.csv").exists()


def test_caveat_prioritization_reports_edge_cases(tmp_path: Path) -> None:
    """Malformed inputs should fail with clear validation errors."""
    drilldown = _write_drilldown(tmp_path)
    bad_dispositions = tmp_path / "bad-dispositions.csv"
    bad_dispositions.write_text(
        _disposition_header()
        + "fit_metric,other,uncertainty_tie,fold-a,target-a,GroupA,"
        "accepted_caveat,reviewed,,,\n",
        encoding="utf-8",
    )
    missing_column = tmp_path / "missing-column.csv"
    missing_column.write_text("gate,run_label\nfit_metric,rmse\n", encoding="utf-8")
    empty = tmp_path / "empty.csv"
    empty.write_text(_drilldown_header(), encoding="utf-8")
    no_header = tmp_path / "no-header.csv"
    no_header.write_text("", encoding="utf-8")

    with pytest.raises(ValueError, match="structural issues"):
        run_structural_smc_caveat_prioritization(
            caveat_drilldown_csv=drilldown,
            caveat_dispositions_csv=bad_dispositions,
        )
    with pytest.raises(ValueError, match="missing columns"):
        run_structural_smc_caveat_prioritization(caveat_drilldown_csv=missing_column)
    with pytest.raises(ValueError, match="data row"):
        run_structural_smc_caveat_prioritization(caveat_drilldown_csv=empty)
    with pytest.raises(ValueError, match="header row"):
        run_structural_smc_caveat_prioritization(caveat_drilldown_csv=no_header)


def test_caveat_priority_models_validate_direct_construction() -> None:
    """Priority model construction should reject impossible direct values."""
    paths = StructuralSMCCaveatPriorityPaths(
        output_dir=Path("out"),
        priority_csv=Path("out/priority.csv"),
        report_md=Path("out/priority.md"),
    )
    with pytest.raises(ValueError, match="positive"):
        _priority_row(review_rank=0)
    with pytest.raises(ValueError, match="non-negative"):
        _priority_row(priority_score=-1.0)
    with pytest.raises(ValueError, match="priority_band"):
        _priority_row(priority_band="")

    blocking = _priority_row(review_status="blocking")
    report = StructuralSMCCaveatPriorityReport(rows=(blocking,), paths=paths)
    assert blocking.blocks_promotion is True
    assert report.blocking_count == 1
    assert report.top_rows(1) == (blocking,)
    with pytest.raises(ValueError, match="positive"):
        report.top_rows(0)

    empty_report = StructuralSMCCaveatPriorityReport(rows=(), paths=paths)
    assert "No caveat rows" in structural_smc_caveat_priority_markdown(empty_report)


def test_caveat_prioritization_cli_requires_inputs(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The CLI should report missing caveat priority inputs."""
    drilldown = _write_drilldown(tmp_path)

    with pytest.raises(SystemExit):
        main(["prioritize-structural-smc-caveat-dispositions"])
    with pytest.raises(SystemExit):
        main(
            [
                "prioritize-structural-smc-caveat-dispositions",
                "--caveat-drilldown-csv",
                str(drilldown),
            ]
        )

    captured = capsys.readouterr()
    assert "requires --caveat-drilldown-csv" in captured.err
    assert "requires --caveat-priority-output-dir" in captured.err


def _write_drilldown(root: Path) -> Path:
    """Write a small caveat drilldown CSV."""
    path = root / "drilldown.csv"
    path.write_text(
        _drilldown_header()
        + "source_model,reviewed_blocker,requires_manual_review,fold-z,target-z,"
        "GroupZ,,,,,not-a-number,not-a-number,,Manual review.,source.csv\n"
        + "source_model,baseline,missing_override_regions,,,,,,,,,2,"
        "Resolve missing child regions.,source.csv\n"
        + "target_fragility,target_fragility,excluded_target,,target-critical,"
        "GroupCritical,,,,,,,sample_flag:critical;repeated_identical_estimates,"
        "Review critical target.,fragility.csv\n"
        + "target_fragility,target_fragility,excluded_target,,target-high-se,"
        "GroupHighSE,,,,,,,sample_flag:high_se,Review noisy target.,fragility.csv\n"
        + "fit_metric,rmse,preference_disagreement,fold-a,,,,child,structured,"
        ",,0.2,,Inspect fold.,validation.csv\n"
        + "fit_metric,rmse,uncertainty_tie,fold-b,target-b,GroupB,,,"
        "structured,uncertainty_tie,,0.1,,Inspect uncertainty.,uncertainty.csv\n",
        encoding="utf-8",
    )
    return path


def _write_dispositions(root: Path) -> Path:
    """Write a small reviewed disposition CSV."""
    path = root / "dispositions.csv"
    path.write_text(
        _disposition_header()
        + "source_model,reviewed_blocker,requires_manual_review,fold-z,target-z,"
        "GroupZ,blocks_promotion,manual blocker,,,\n"
        + "source_model,baseline,missing_override_regions,,,,undecided,,,,\n"
        + "target_fragility,target_fragility,excluded_target,,target-critical,"
        "GroupCritical,undecided,,,,\n"
        + "target_fragility,target_fragility,excluded_target,,target-high-se,"
        "GroupHighSE,undecided,,,,\n"
        + "fit_metric,rmse,preference_disagreement,fold-a,,,undecided,,,,\n"
        + "fit_metric,rmse,uncertainty_tie,fold-b,target-b,GroupB,"
        "accepted_caveat,weak evidence,,,\n",
        encoding="utf-8",
    )
    return path


def _drilldown_header() -> str:
    """Return the caveat drilldown CSV header."""
    return (
        "gate,run_label,caveat_type,fold_name,target_id,requested_group_id,"
        "calibration_preferred_candidate,holdout_preferred_candidate,"
        "raw_residual_preferred_candidate,uncertainty_weighted_preferred_candidate,"
        "rmse_delta,chi_square_delta,diagnostic_value,next_action,source_path\n"
    )


def _disposition_header() -> str:
    """Return the caveat disposition CSV header."""
    return (
        "gate,run_label,caveat_type,fold_name,target_id,requested_group_id,"
        "disposition,reason,reviewer,decision_date,note\n"
    )


def _priority_row(
    *,
    review_rank: int = 1,
    priority_band: str = "high",
    priority_score: float = 1.0,
    review_status: str = "unresolved",
) -> StructuralSMCCaveatPriorityRow:
    """Return a directly constructed priority test row."""
    return StructuralSMCCaveatPriorityRow(
        review_rank=review_rank,
        priority_band=priority_band,
        priority_score=priority_score,
        review_status=review_status,
        disposition="undecided",
        recommended_disposition="accepted_caveat",
        rationale="test rationale",
        gate="fit_metric",
        run_label="rmse",
        caveat_type="uncertainty_tie",
        next_action="review",
    )
