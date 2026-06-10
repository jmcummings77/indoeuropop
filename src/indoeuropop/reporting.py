"""Reporting helpers for provenance and diagnostics output."""

from __future__ import annotations

import csv
from collections.abc import Iterable
from io import StringIO
from pathlib import Path

from indoeuropop.diagnostics import DiagnosticIssue
from indoeuropop.provenance import ProvenanceRecord

BASE_PROVENANCE_FIELDS = ("kind", "name", "value", "unit")


def diagnostic_issue_records(
    issues: Iterable[DiagnosticIssue],
) -> tuple[ProvenanceRecord, ...]:
    """Convert diagnostic issues into derived provenance records."""
    return tuple(_diagnostic_issue_record(issue) for issue in issues)


def provenance_fieldnames(
    records: Iterable[ProvenanceRecord],
) -> tuple[str, ...]:
    """Return stable CSV field names for provenance records."""
    metadata_fields: list[str] = []
    for record in records:
        for fieldname in record.to_flat_row():
            if (
                fieldname not in BASE_PROVENANCE_FIELDS
                and fieldname not in metadata_fields
            ):
                metadata_fields.append(fieldname)
    return BASE_PROVENANCE_FIELDS + tuple(metadata_fields)


def provenance_rows(
    records: Iterable[ProvenanceRecord],
) -> tuple[dict[str, str], ...]:
    """Return provenance records as rows with consistent keys."""
    record_tuple = tuple(records)
    fieldnames = provenance_fieldnames(record_tuple)
    rows: list[dict[str, str]] = []
    for record in record_tuple:
        flat_row = record.to_flat_row()
        rows.append(
            {fieldname: flat_row.get(fieldname, "") for fieldname in fieldnames}
        )
    return tuple(rows)


def provenance_records_to_csv(records: Iterable[ProvenanceRecord]) -> str:
    """Return provenance records serialized as CSV text."""
    record_tuple = tuple(records)
    fieldnames = provenance_fieldnames(record_tuple)
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(provenance_rows(record_tuple))
    return output.getvalue()


def write_provenance_csv(records: Iterable[ProvenanceRecord], path: str | Path) -> Path:
    """Write provenance records to a CSV file and return the path."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(provenance_records_to_csv(records), encoding="utf-8")
    return output_path


def _diagnostic_issue_record(issue: DiagnosticIssue) -> ProvenanceRecord:
    """Convert one diagnostic issue to a provenance record."""
    metadata = {"message": issue.message}
    if issue.time_bce is not None:
        metadata["time_bce"] = f"{issue.time_bce:.12g}"
    if issue.region is not None:
        metadata["region"] = issue.region
    if issue.source is not None:
        metadata["source"] = issue.source
    return ProvenanceRecord(
        name=f"diagnostic_{issue.code}",
        kind="derived",
        value=issue.severity,
        unit="severity",
        metadata=metadata,
    )
