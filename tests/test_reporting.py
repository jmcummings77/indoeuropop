"""Tests for reporting helpers."""

from pathlib import Path

from indoeuropop.analysis.diagnostics import DiagnosticIssue
from indoeuropop.reporting import (
    diagnostic_issue_records,
    provenance_fieldnames,
    provenance_records_to_csv,
    provenance_rows,
    write_provenance_csv,
)
from indoeuropop.reporting.provenance import ProvenanceRecord


def test_diagnostic_issue_records_preserve_issue_context() -> None:
    """Diagnostic issues should become derived provenance records."""
    records = diagnostic_issue_records(
        (
            DiagnosticIssue(
                code="extinction",
                severity="warning",
                message="region is extinct",
                time_bce=2900,
                region="britain",
                source="steppe",
            ),
        )
    )

    record = records[0]

    assert record.name == "diagnostic_extinction"
    assert record.kind == "derived"
    assert record.value == "warning"
    assert record.unit == "severity"
    assert record.metadata == {
        "message": "region is extinct",
        "time_bce": "2900",
        "region": "britain",
        "source": "steppe",
    }


def test_diagnostic_issue_records_handles_minimal_issue() -> None:
    """Diagnostic records should allow issues without optional location labels."""
    records = diagnostic_issue_records(
        (
            DiagnosticIssue(
                code="non_decreasing_time",
                severity="error",
                message="bad time",
            ),
        )
    )

    assert records[0].metadata == {"message": "bad time"}


def test_provenance_fieldnames_and_rows_use_stable_metadata_columns() -> None:
    """Provenance tables should include all metadata columns in first-seen order."""
    records = (
        ProvenanceRecord(
            name="final_ancestry",
            kind="simulated",
            value=0.25,
            unit="proportion",
            metadata={"region": "britain"},
        ),
        ProvenanceRecord(
            name="chi_square",
            kind="derived",
            value=2.5,
            unit="score",
            metadata={"observation_count": "3", "region": "britain"},
        ),
    )

    assert provenance_fieldnames(records) == (
        "kind",
        "name",
        "value",
        "unit",
        "metadata_region",
        "metadata_observation_count",
    )
    assert provenance_rows(records) == (
        {
            "kind": "simulated",
            "name": "final_ancestry",
            "value": "0.25",
            "unit": "proportion",
            "metadata_region": "britain",
            "metadata_observation_count": "",
        },
        {
            "kind": "derived",
            "name": "chi_square",
            "value": "2.5",
            "unit": "score",
            "metadata_region": "britain",
            "metadata_observation_count": "3",
        },
    )


def test_provenance_records_to_csv_writes_header_for_empty_records() -> None:
    """CSV output should remain valid even when no records are present."""
    assert provenance_records_to_csv(()) == "kind,name,value,unit\n"


def test_write_provenance_csv_creates_parent_directories(tmp_path: Path) -> None:
    """CSV writer should create parent folders and return the output path."""
    output_path = tmp_path / "reports" / "provenance.csv"
    returned_path = write_provenance_csv(
        (
            ProvenanceRecord(
                name="note",
                kind="derived",
                value="ready",
                metadata={"phase": "smoke"},
            ),
        ),
        output_path,
    )

    assert returned_path == output_path
    assert output_path.read_text(encoding="utf-8") == (
        "kind,name,value,unit,metadata_phase\n" "derived,note,ready,,smoke\n"
    )
