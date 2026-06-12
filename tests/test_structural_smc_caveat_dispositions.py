"""Tests for reviewed structural SMC caveat dispositions."""

from __future__ import annotations

from pathlib import Path

import pytest

from indoeuropop.data.structural_smc_caveat_dispositions import (
    StructuralSMCCaveatDispositionDataset,
    StructuralSMCCaveatDispositionRecord,
    initialize_structural_smc_caveat_disposition_template,
    load_structural_smc_caveat_dispositions,
    structural_smc_caveat_disposition_rows,
    structural_smc_caveat_dispositions_to_csv,
    validate_structural_smc_caveat_dispositions,
    write_structural_smc_caveat_dispositions_csv,
)
from indoeuropop.orchestration.cli import main
from indoeuropop.reporting.structural_smc_caveat_dispositions import (
    structural_smc_caveat_disposition_validation_markdown,
)


def test_initialize_and_validate_caveat_disposition_template(
    tmp_path: Path,
) -> None:
    """A drilldown CSV should initialize an undecided disposition template."""
    drilldown = _write_drilldown(tmp_path)
    template = initialize_structural_smc_caveat_disposition_template(drilldown)
    output = tmp_path / "template.csv"

    write_structural_smc_caveat_dispositions_csv(template, output)
    loaded = load_structural_smc_caveat_dispositions(output)
    report = validate_structural_smc_caveat_dispositions(
        drilldown_csv=drilldown,
        dispositions_csv=output,
    )

    assert len(template.records) == 2
    assert loaded.records[0].disposition == "undecided"
    assert report.valid is True
    assert report.reviewed_count == 0
    assert report.unresolved_count == 2
    assert report.blocking_count == 0
    assert "undecided" in structural_smc_caveat_dispositions_to_csv(template)


def test_reviewed_caveat_dispositions_report_blockers(tmp_path: Path) -> None:
    """Reviewed blocking dispositions should be counted for promotion gates."""
    drilldown = _write_drilldown(tmp_path)
    dispositions = StructuralSMCCaveatDispositionDataset.from_rows(
        (
            _disposition("accepted_caveat", reason="weak but expected"),
            _disposition(
                "blocks_promotion",
                run_label="rmse",
                caveat_type="uncertainty_tie",
                fold_name="fold-b",
                target_id="target-b",
                requested_group_id="GroupB",
                reason="needs source review",
            ),
        )
    )
    disposition_path = write_structural_smc_caveat_dispositions_csv(
        dispositions, tmp_path / "reviewed.csv"
    )

    report = validate_structural_smc_caveat_dispositions(
        drilldown_csv=drilldown,
        dispositions_csv=disposition_path,
    )
    markdown = structural_smc_caveat_disposition_validation_markdown(report)

    assert report.reviewed_count == 2
    assert report.blocking_count == 1
    assert report.unresolved_count == 0
    assert "blocks_promotion" in markdown
    assert structural_smc_caveat_disposition_rows(dispositions)[1]["reason"] == (
        "needs source review"
    )


def test_caveat_disposition_cli_initializes_and_validates(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """CLI commands should initialize and validate disposition files."""
    drilldown = _write_drilldown(tmp_path)
    disposition_path = tmp_path / "template.csv"
    report_path = tmp_path / "validation.md"

    init_exit = main(
        [
            "initialize-structural-smc-caveat-dispositions",
            "--caveat-drilldown-csv",
            str(drilldown),
            "--caveat-dispositions-out",
            str(disposition_path),
        ]
    )
    validate_exit = main(
        [
            "validate-structural-smc-caveat-dispositions",
            "--caveat-drilldown-csv",
            str(drilldown),
            "--caveat-dispositions-csv",
            str(disposition_path),
            "--caveat-disposition-report-md",
            str(report_path),
        ]
    )

    captured = capsys.readouterr()
    assert init_exit == 0
    assert validate_exit == 0
    assert "structural_smc_caveat_disposition_row_count=2" in captured.out
    assert "structural_smc_caveat_disposition_unresolved_count=2" in captured.out
    assert report_path.exists()


def test_caveat_dispositions_validate_edge_cases(tmp_path: Path) -> None:
    """Malformed disposition files should fail clearly."""
    drilldown = _write_drilldown(tmp_path)
    missing_column = tmp_path / "missing-column.csv"
    missing_column.write_text("gate,run_label\nfit,rmse\n", encoding="utf-8")
    empty_rows = tmp_path / "empty.csv"
    empty_rows.write_text(_disposition_header(), encoding="utf-8")
    no_header = tmp_path / "no-header.csv"
    no_header.write_text("", encoding="utf-8")
    invalid_disposition = tmp_path / "invalid.csv"
    invalid_disposition.write_text(
        _disposition_header()
        + "fit_metric,rmse,preference_disagreement,fold-a,,,maybe,bad,,,\n",
        encoding="utf-8",
    )
    missing_reason = tmp_path / "missing-reason.csv"
    missing_reason.write_text(
        _disposition_header()
        + "fit_metric,rmse,preference_disagreement,fold-a,,,accepted_caveat,,,,\n",
        encoding="utf-8",
    )
    duplicate = tmp_path / "duplicate.csv"
    duplicate.write_text(
        _disposition_header()
        + "fit_metric,rmse,preference_disagreement,fold-a,,,undecided,,,,\n"
        + "fit_metric,rmse,preference_disagreement,fold-a,,,undecided,,,,\n",
        encoding="utf-8",
    )
    unknown = tmp_path / "unknown.csv"
    unknown.write_text(
        _disposition_header()
        + "fit_metric,other,preference_disagreement,fold-x,,,accepted_caveat,"
        "reviewed,,,\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="missing columns"):
        load_structural_smc_caveat_dispositions(missing_column)
    with pytest.raises(ValueError, match="at least one row"):
        load_structural_smc_caveat_dispositions(empty_rows)
    with pytest.raises(ValueError, match="header row"):
        load_structural_smc_caveat_dispositions(no_header)
    with pytest.raises(ValueError, match="not supported"):
        load_structural_smc_caveat_dispositions(invalid_disposition)
    with pytest.raises(ValueError, match="reason"):
        load_structural_smc_caveat_dispositions(missing_reason)
    with pytest.raises(ValueError, match="unique"):
        load_structural_smc_caveat_dispositions(duplicate)

    report = validate_structural_smc_caveat_dispositions(
        drilldown_csv=drilldown,
        dispositions_csv=unknown,
    )
    assert report.valid is False
    assert report.issues[0].startswith("unknown caveat disposition key")
    assert "unknown caveat disposition key" in (
        structural_smc_caveat_disposition_validation_markdown(report)
    )


def test_caveat_disposition_models_validate_direct_construction() -> None:
    """Direct disposition model construction should reject invalid records."""
    with pytest.raises(ValueError, match="gate"):
        StructuralSMCCaveatDispositionRecord("", "run", "type")
    with pytest.raises(ValueError, match="run_label"):
        StructuralSMCCaveatDispositionRecord("gate", "", "type")
    with pytest.raises(ValueError, match="caveat_type"):
        StructuralSMCCaveatDispositionRecord("gate", "run", "")
    with pytest.raises(ValueError, match="reason"):
        StructuralSMCCaveatDispositionRecord(
            "gate",
            "run",
            "type",
            disposition="configuration_gap",
        )
    with pytest.raises(ValueError, match="not supported"):
        StructuralSMCCaveatDispositionRecord(
            "gate",
            "run",
            "type",
            disposition="maybe",  # type: ignore[arg-type]
        )
    with pytest.raises(ValueError, match="at least one row"):
        StructuralSMCCaveatDispositionDataset.from_rows(()).require_records()

    dataset = StructuralSMCCaveatDispositionDataset.from_rows(
        (_disposition("requires_qpadm_rerun", reason="rerun needed"),)
    )
    assert dataset.reviewed_count == 1
    assert dataset.blocking_count == 1


def test_caveat_disposition_cli_requires_inputs(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Disposition CLI commands should report missing required inputs."""
    drilldown = _write_drilldown(tmp_path)

    with pytest.raises(SystemExit):
        main(["initialize-structural-smc-caveat-dispositions"])
    with pytest.raises(SystemExit):
        main(
            [
                "initialize-structural-smc-caveat-dispositions",
                "--caveat-drilldown-csv",
                str(drilldown),
            ]
        )
    with pytest.raises(SystemExit):
        main(["validate-structural-smc-caveat-dispositions"])
    with pytest.raises(SystemExit):
        main(
            [
                "validate-structural-smc-caveat-dispositions",
                "--caveat-drilldown-csv",
                str(drilldown),
            ]
        )

    captured = capsys.readouterr()
    assert "requires --caveat-drilldown-csv" in captured.err
    assert "requires --caveat-dispositions-out" in captured.err
    assert "requires --caveat-dispositions-csv" in captured.err


def _write_drilldown(root: Path) -> Path:
    """Write a small caveat drilldown CSV."""
    path = root / "drilldown.csv"
    path.write_text(
        "gate,run_label,caveat_type,fold_name,target_id,requested_group_id,"
        "next_action\n"
        "fit_metric,rmse,preference_disagreement,fold-a,,,inspect\n"
        "fit_metric,rmse,uncertainty_tie,fold-b,target-b,GroupB,inspect\n",
        encoding="utf-8",
    )
    return path


def _disposition(
    disposition: str,
    *,
    run_label: str = "rmse",
    caveat_type: str = "preference_disagreement",
    fold_name: str = "fold-a",
    target_id: str = "",
    requested_group_id: str = "",
    reason: str = "",
) -> StructuralSMCCaveatDispositionRecord:
    """Return one disposition test record."""
    return StructuralSMCCaveatDispositionRecord(
        gate="fit_metric",
        run_label=run_label,
        caveat_type=caveat_type,
        fold_name=fold_name,
        target_id=target_id,
        requested_group_id=requested_group_id,
        disposition=disposition,  # type: ignore[arg-type]
        reason=reason,
    )


def _disposition_header() -> str:
    """Return the caveat disposition CSV header."""
    return (
        "gate,run_label,caveat_type,fold_name,target_id,requested_group_id,"
        "disposition,reason,reviewer,decision_date,note\n"
    )
