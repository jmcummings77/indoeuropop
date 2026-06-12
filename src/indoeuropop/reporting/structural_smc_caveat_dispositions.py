"""Reports for reviewed structural SMC caveat dispositions."""

from __future__ import annotations

from io import StringIO
from pathlib import Path

from indoeuropop.data.structural_smc_caveat_dispositions import (
    StructuralSMCCaveatDispositionValidationReport,
)


def structural_smc_caveat_disposition_validation_markdown(
    report: StructuralSMCCaveatDispositionValidationReport,
) -> str:
    """Return a Markdown validation report for caveat dispositions."""
    output = StringIO()
    output.write("# Structural SMC Caveat Disposition Validation\n\n")
    output.write(
        "This report validates reviewed caveat dispositions against the current "
        "structural SMC caveat drilldown queue.\n\n"
    )
    output.write(
        "## Summary\n\n"
        f"- valid: {str(report.valid).lower()}\n"
        f"- drilldown_caveat_count: {report.drilldown_caveat_count}\n"
        f"- disposition_row_count: {len(report.dispositions.records)}\n"
        f"- reviewed_disposition_count: {report.reviewed_count}\n"
        f"- unresolved_caveat_count: {report.unresolved_count}\n"
        f"- blocking_disposition_count: {report.blocking_count}\n"
        f"- issue_count: {len(report.issues)}\n\n"
    )
    output.write(_issues_markdown(report))
    output.write(_blocking_markdown(report))
    output.write("## Interpretation Guardrail\n\n")
    output.write(
        "Blocking dispositions should prevent promotion until the cited caveats "
        "are resolved or explicitly re-reviewed.\n"
    )
    return output.getvalue()


def write_structural_smc_caveat_disposition_validation_markdown(
    report: StructuralSMCCaveatDispositionValidationReport,
    path: str | Path,
) -> Path:
    """Write caveat disposition validation Markdown and return the path."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        structural_smc_caveat_disposition_validation_markdown(report),
        encoding="utf-8",
    )
    return output_path


def _issues_markdown(report: StructuralSMCCaveatDispositionValidationReport) -> str:
    """Return structural validation issues as Markdown."""
    output = StringIO()
    output.write("## Issues\n\n")
    if not report.issues:
        output.write("No structural disposition-file issues were detected.\n\n")
        return output.getvalue()
    for issue in report.issues:
        output.write(f"- {issue}\n")
    output.write("\n")
    return output.getvalue()


def _blocking_markdown(report: StructuralSMCCaveatDispositionValidationReport) -> str:
    """Return blocking reviewed dispositions as Markdown."""
    blocking = tuple(
        record for record in report.dispositions.records if record.blocks_promotion
    )
    output = StringIO()
    output.write("## Blocking Dispositions\n\n")
    if not blocking:
        output.write("No reviewed dispositions currently block promotion.\n\n")
        return output.getvalue()
    output.write("| Gate | Run | Type | Fold | Target | Disposition | Reason |\n")
    output.write("| --- | --- | --- | --- | --- | --- | --- |\n")
    for record in blocking:
        output.write(
            f"| {record.gate} | {record.run_label} | {record.caveat_type} | "
            f"{record.fold_name} | {record.target_id} | "
            f"{record.disposition} | {record.reason} |\n"
        )
    output.write("\n")
    return output.getvalue()
