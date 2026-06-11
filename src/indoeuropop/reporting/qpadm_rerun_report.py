"""Reports and exports for qpAdm rerun-ingestion comparisons."""

from __future__ import annotations

import csv
import json
from collections.abc import Iterable
from io import StringIO
from pathlib import Path

from indoeuropop.data.qpadm_rerun_models import (
    QPADM_RERUN_COMPARISON_COLUMNS,
    QpAdmRerunIngestionDiagnostics,
    QpAdmRerunTargetComparison,
)


def qpadm_rerun_comparison_rows(
    comparisons: Iterable[QpAdmRerunTargetComparison],
) -> tuple[dict[str, str], ...]:
    """Return rerun target comparisons as CSV-ready dictionaries."""
    return tuple(_comparison_row(comparison) for comparison in comparisons)


def qpadm_rerun_comparison_to_csv(
    comparisons: Iterable[QpAdmRerunTargetComparison],
) -> str:
    """Return target comparisons serialized as CSV text."""
    output = StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=QPADM_RERUN_COMPARISON_COLUMNS,
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerows(qpadm_rerun_comparison_rows(comparisons))
    return output.getvalue()


def write_qpadm_rerun_comparison_csv(
    comparisons: Iterable[QpAdmRerunTargetComparison], path: str | Path
) -> Path:
    """Write target comparisons as CSV and return the output path."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(qpadm_rerun_comparison_to_csv(comparisons), encoding="utf-8")
    return output_path


def qpadm_rerun_report_markdown(
    diagnostics: QpAdmRerunIngestionDiagnostics,
    comparisons: Iterable[QpAdmRerunTargetComparison],
) -> str:
    """Return a Markdown report summarizing pre/post qpAdm target changes."""
    rescued = tuple(
        comparison for comparison in comparisons if comparison.change == "rescued"
    )
    lines = [
        "# qpAdm Rerun Ingestion Report",
        "",
        "This report compares target availability before and after adding a "
        "validated qpAdm rerun estimate table. It is a curation aid, not a "
        "scientific acceptance decision.",
        "",
        "## Summary",
        "",
        f"- requested targets: `{diagnostics.requested_target_count}`",
        "- baseline target observations: "
        f"`{diagnostics.baseline_target_observation_count}`",
        "- post-rerun target observations: "
        f"`{diagnostics.post_target_observation_count}`",
        "- accepted target observations: "
        f"`{_optional_int(diagnostics.accepted_target_observation_count)}`",
        f"- rescued targets: `{diagnostics.rescued_target_count}`",
        f"- lost targets: `{diagnostics.lost_target_count}`",
        "- reviewed rerun targets rescued: "
        f"`{diagnostics.rescued_reviewed_rerun_target_count}` of "
        f"`{diagnostics.reviewed_rerun_target_count}`",
        "",
        "## Rescued Targets",
        "",
    ]
    if rescued:
        lines.extend(
            [
                "| target_id | region | decision | post_mean | post_uncertainty |",
                "| --- | --- | --- | ---: | ---: |",
            ]
        )
        lines.extend(_rescued_row(comparison) for comparison in rescued)
    else:
        lines.append("No targets became newly buildable after rerun ingestion.")
    lines.extend(("", "## Recommendation", "", _rerun_recommendation(diagnostics), ""))
    return "\n".join(lines)


def write_qpadm_rerun_report_markdown(
    diagnostics: QpAdmRerunIngestionDiagnostics,
    comparisons: Iterable[QpAdmRerunTargetComparison],
    path: str | Path,
) -> Path:
    """Write a qpAdm rerun-ingestion Markdown report and return the path."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        qpadm_rerun_report_markdown(diagnostics, comparisons),
        encoding="utf-8",
    )
    return output_path


def qpadm_rerun_ingestion_diagnostics_payload(
    diagnostics: QpAdmRerunIngestionDiagnostics,
) -> dict[str, object]:
    """Return JSON-ready qpAdm rerun-ingestion diagnostics."""
    return {
        "requested_target_count": diagnostics.requested_target_count,
        "baseline_raw_qpadm_row_count": diagnostics.baseline_raw_qpadm_row_count,
        "rerun_raw_qpadm_row_count": diagnostics.rerun_raw_qpadm_row_count,
        "baseline_parsed_qpadm_estimate_count": (
            diagnostics.baseline_parsed_qpadm_estimate_count
        ),
        "rerun_parsed_qpadm_estimate_count": (
            diagnostics.rerun_parsed_qpadm_estimate_count
        ),
        "baseline_sample_estimate_count": diagnostics.baseline_sample_estimate_count,
        "rerun_sample_estimate_count": diagnostics.rerun_sample_estimate_count,
        "merged_sample_estimate_count": diagnostics.merged_sample_estimate_count,
        "baseline_target_observation_count": (
            diagnostics.baseline_target_observation_count
        ),
        "post_target_observation_count": diagnostics.post_target_observation_count,
        "accepted_target_observation_count": (
            diagnostics.accepted_target_observation_count
        ),
        "rescued_target_count": diagnostics.rescued_target_count,
        "lost_target_count": diagnostics.lost_target_count,
        "unchanged_retained_target_count": (
            diagnostics.unchanged_retained_target_count
        ),
        "unchanged_dropped_target_count": diagnostics.unchanged_dropped_target_count,
        "reviewed_rerun_target_count": diagnostics.reviewed_rerun_target_count,
        "rescued_reviewed_rerun_target_count": (
            diagnostics.rescued_reviewed_rerun_target_count
        ),
        "rescued_target_ids": list(diagnostics.rescued_target_ids),
        "lost_target_ids": list(diagnostics.lost_target_ids),
        "post_target_counts_by_region": dict(diagnostics.post_target_counts_by_region),
    }


def write_qpadm_rerun_ingestion_diagnostics_json(
    diagnostics: QpAdmRerunIngestionDiagnostics, path: str | Path
) -> Path:
    """Write qpAdm rerun-ingestion diagnostics as JSON and return the path."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(qpadm_rerun_ingestion_diagnostics_payload(diagnostics), indent=2)
        + "\n",
        encoding="utf-8",
    )
    return output_path


def _comparison_row(comparison: QpAdmRerunTargetComparison) -> dict[str, str]:
    """Return one comparison as a string-only CSV row."""
    return {
        "target_id": comparison.target_id,
        "region": comparison.region,
        "source": comparison.source,
        "decision": comparison.decision,
        "baseline_status": comparison.baseline_status,
        "post_status": comparison.post_status,
        "change": comparison.change,
        "baseline_mean": _optional_value(comparison.baseline_mean),
        "post_mean": _optional_value(comparison.post_mean),
        "mean_delta": _optional_value(comparison.mean_delta),
        "baseline_uncertainty": _optional_value(comparison.baseline_uncertainty),
        "post_uncertainty": _optional_value(comparison.post_uncertainty),
    }


def _rescued_row(comparison: QpAdmRerunTargetComparison) -> str:
    """Return one Markdown table row for a rescued target."""
    return (
        f"| `{comparison.target_id}` | {comparison.region} | "
        f"{comparison.decision or 'unreviewed'} | "
        f"{_optional_value(comparison.post_mean)} | "
        f"{_optional_value(comparison.post_uncertainty)} |"
    )


def _rerun_recommendation(diagnostics: QpAdmRerunIngestionDiagnostics) -> str:
    """Return a cautious next-step recommendation for rerun outputs."""
    if diagnostics.lost_target_count:
        return (
            "Investigate lost target rows before replacing baseline target "
            "observations with rerun-enhanced outputs."
        )
    if diagnostics.rescued_target_count:
        return (
            "Review the rescued qpAdm rows and source/outgroup choices, then "
            "update target decisions only for rows accepted by domain review."
        )
    return (
        "No target availability changed; inspect the external qpAdm rerun table "
        "before changing curation decisions or simulator parameters."
    )


def _optional_value(value: float | None) -> str:
    """Return a stable CSV/Markdown value or a blank for missing observations."""
    return "" if value is None else f"{value:.12g}"


def _optional_int(value: int | None) -> str:
    """Return an optional integer as Markdown text."""
    return "not_written" if value is None else str(value)
