"""Reports for structural SMC caveat drilldowns."""

from __future__ import annotations

import csv
from io import StringIO
from pathlib import Path

from indoeuropop.orchestration.structural_smc_caveat_drilldown_models import (
    StructuralSMCCaveatDrilldownReport,
    StructuralSMCCaveatDrilldownRow,
)

STRUCTURAL_SMC_CAVEAT_DRILLDOWN_FIELDS = (
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


def structural_smc_caveat_drilldown_rows(
    report: StructuralSMCCaveatDrilldownReport,
) -> tuple[dict[str, str], ...]:
    """Return caveat drilldown rows as CSV-ready dictionaries."""
    return tuple(_row(row) for row in report.rows)


def structural_smc_caveat_drilldown_to_csv(
    report: StructuralSMCCaveatDrilldownReport,
) -> str:
    """Return caveat drilldown rows serialized as CSV text."""
    output = StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=STRUCTURAL_SMC_CAVEAT_DRILLDOWN_FIELDS,
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerows(structural_smc_caveat_drilldown_rows(report))
    return output.getvalue()


def write_structural_smc_caveat_drilldown_csv(
    report: StructuralSMCCaveatDrilldownReport,
    path: str | Path,
) -> Path:
    """Write caveat drilldown CSV rows and return the path."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        structural_smc_caveat_drilldown_to_csv(report), encoding="utf-8"
    )
    return output_path


def structural_smc_caveat_drilldown_markdown(
    report: StructuralSMCCaveatDrilldownReport,
) -> str:
    """Return a Markdown caveat drilldown report."""
    output = StringIO()
    output.write("# Structural SMC Caveat Drilldown\n\n")
    output.write(
        "This report expands the unified robustness decision into target, fold, "
        "and run-level review rows. It is a review queue, not a rerun of SMC.\n\n"
    )
    output.write(_summary_markdown(report))
    output.write(_row_table(report))
    output.write("## Interpretation Guardrail\n\n")
    output.write(
        "Rows with empty fold or target fields are run-level caveats where the "
        "upstream summary did not preserve exact member identities.\n"
    )
    return output.getvalue()


def write_structural_smc_caveat_drilldown_markdown(
    report: StructuralSMCCaveatDrilldownReport,
    path: str | Path,
) -> Path:
    """Write a Markdown caveat drilldown report and return the path."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        structural_smc_caveat_drilldown_markdown(report), encoding="utf-8"
    )
    return output_path


def _row(row: StructuralSMCCaveatDrilldownRow) -> dict[str, str]:
    """Return one caveat drilldown row as a string-only mapping."""
    return {
        field: getattr(row, field) for field in STRUCTURAL_SMC_CAVEAT_DRILLDOWN_FIELDS
    }


def _summary_markdown(report: StructuralSMCCaveatDrilldownReport) -> str:
    """Return caveat count bullets."""
    output = StringIO()
    output.write("## Summary\n\n")
    output.write(f"- caveat_row_count: {report.row_count}\n")
    for caveat_type in report.caveat_types:
        output.write(f"- {caveat_type}_count: {report.count_by_type(caveat_type)}\n")
    output.write("\n")
    return output.getvalue()


def _row_table(report: StructuralSMCCaveatDrilldownReport) -> str:
    """Return the actionable caveat row table."""
    output = StringIO()
    output.write("## Review Rows\n\n")
    if not report.rows:
        output.write("No caveats were detected.\n\n")
        return output.getvalue()
    output.write(
        "| Gate | Run | Type | Fold | Target | Preference | Diagnostic | "
        "Next action |\n"
    )
    output.write("| --- | --- | --- | --- | --- | --- | --- | --- |\n")
    for row in report.rows:
        output.write(
            f"| {row.gate} | {row.run_label} | {row.caveat_type} | "
            f"{row.fold_name} | {row.target_id or row.requested_group_id} | "
            f"{_preference_text(row)} | {_diagnostic_text(row)} | "
            f"{row.next_action} |\n"
        )
    output.write("\n")
    return output.getvalue()


def _preference_text(row: StructuralSMCCaveatDrilldownRow) -> str:
    """Return compact preference context for a row."""
    values = tuple(
        value
        for value in (
            row.calibration_preferred_candidate,
            row.holdout_preferred_candidate,
            row.raw_residual_preferred_candidate,
            row.uncertainty_weighted_preferred_candidate,
        )
        if value
    )
    return " -> ".join(values)


def _diagnostic_text(row: StructuralSMCCaveatDrilldownRow) -> str:
    """Return compact numeric or textual diagnostic context."""
    values = tuple(
        value
        for value in (row.rmse_delta, row.chi_square_delta, row.diagnostic_value)
        if value
    )
    return "; ".join(values)
