"""Reports for prioritized structural SMC caveat review queues."""

from __future__ import annotations

import csv
from io import StringIO
from pathlib import Path

from indoeuropop.orchestration.structural_smc_caveat_priority_models import (
    StructuralSMCCaveatPriorityReport,
    StructuralSMCCaveatPriorityRow,
)

STRUCTURAL_SMC_CAVEAT_PRIORITY_SOURCE_FIELDS = (
    "gate",
    "run_label",
    "caveat_type",
    "fold_name",
    "target_id",
    "requested_group_id",
    "calibration_preferred_candidate",
    "holdout_preferred_candidate",
    "raw_residual_preferred_candidate",
    "uncertainty_weighted_preferred_candidate",
    "rmse_delta",
    "chi_square_delta",
    "diagnostic_value",
    "next_action",
    "source_path",
)
STRUCTURAL_SMC_CAVEAT_PRIORITY_FIELDS = (
    "review_rank",
    "priority_band",
    "priority_score",
    "review_status",
    "disposition",
    "recommended_disposition",
    "rationale",
    *STRUCTURAL_SMC_CAVEAT_PRIORITY_SOURCE_FIELDS,
)


def structural_smc_caveat_priority_rows(
    report: StructuralSMCCaveatPriorityReport,
) -> tuple[dict[str, str], ...]:
    """Return priority rows as CSV-ready dictionaries."""
    return tuple(_row(row) for row in report.rows)


def structural_smc_caveat_priority_to_csv(
    report: StructuralSMCCaveatPriorityReport,
) -> str:
    """Return prioritized caveat rows serialized as CSV text."""
    output = StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=STRUCTURAL_SMC_CAVEAT_PRIORITY_FIELDS,
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerows(structural_smc_caveat_priority_rows(report))
    return output.getvalue()


def write_structural_smc_caveat_priority_csv(
    report: StructuralSMCCaveatPriorityReport,
    path: str | Path,
) -> Path:
    """Write prioritized caveat rows to CSV and return the path."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        structural_smc_caveat_priority_to_csv(report), encoding="utf-8"
    )
    return output_path


def structural_smc_caveat_priority_markdown(
    report: StructuralSMCCaveatPriorityReport,
) -> str:
    """Return a Markdown prioritized caveat review report."""
    output = StringIO()
    output.write("# Structural SMC Caveat Priority Queue\n\n")
    output.write(
        "This report ranks caveat drilldown rows for human disposition review. "
        "Scores are triage aids, not scientific acceptance claims.\n\n"
    )
    output.write(_summary_markdown(report))
    output.write(_top_rows_markdown(report))
    output.write("## Interpretation Guardrail\n\n")
    output.write(
        "Recommended dispositions are starting points. Reviewers should edit the "
        "disposition CSV with evidence-backed reasons before promotion.\n"
    )
    return output.getvalue()


def write_structural_smc_caveat_priority_markdown(
    report: StructuralSMCCaveatPriorityReport,
    path: str | Path,
) -> Path:
    """Write a Markdown caveat priority report and return the path."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        structural_smc_caveat_priority_markdown(report), encoding="utf-8"
    )
    return output_path


def _row(row: StructuralSMCCaveatPriorityRow) -> dict[str, str]:
    """Return one priority row as a string-only mapping."""
    return {
        field: _cell(getattr(row, field))
        for field in STRUCTURAL_SMC_CAVEAT_PRIORITY_FIELDS
    }


def _cell(value: object) -> str:
    """Return one value as a stable CSV cell."""
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)


def _summary_markdown(report: StructuralSMCCaveatPriorityReport) -> str:
    """Return summary bullets for a priority report."""
    output = StringIO()
    output.write("## Summary\n\n")
    output.write(f"- caveat_row_count: {report.row_count}\n")
    output.write(f"- unresolved_caveat_count: {report.unresolved_count}\n")
    output.write(f"- reviewed_caveat_count: {report.reviewed_count}\n")
    output.write(f"- blocking_caveat_count: {report.blocking_count}\n\n")
    return output.getvalue()


def _top_rows_markdown(report: StructuralSMCCaveatPriorityReport) -> str:
    """Return a compact table of the highest-priority rows."""
    output = StringIO()
    output.write("## Highest Priority Rows\n\n")
    if not report.rows:
        output.write("No caveat rows were available.\n\n")
        return output.getvalue()
    output.write(
        "| Rank | Band | Status | Gate | Type | Target/Fold | Score | Hint |\n"
    )
    output.write("| ---: | --- | --- | --- | --- | --- | ---: | --- |\n")
    for row in report.top_rows(15):
        output.write(
            f"| {row.review_rank} | {row.priority_band} | {row.review_status} | "
            f"{row.gate} | {row.caveat_type} | {_target_or_fold(row)} | "
            f"{row.priority_score:.6g} | {row.recommended_disposition} |\n"
        )
    output.write("\n")
    return output.getvalue()


def _target_or_fold(row: StructuralSMCCaveatPriorityRow) -> str:
    """Return the most useful compact identifier for a priority row."""
    return row.target_id or row.requested_group_id or row.fold_name or row.run_label
