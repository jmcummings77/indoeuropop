"""Readiness reports for local real-data pipeline artifacts."""

from __future__ import annotations

from collections.abc import Iterable
from io import StringIO
from pathlib import Path

from indoeuropop.reporting.readiness_checks import inspect_real_pipeline_artifacts
from indoeuropop.reporting.readiness_models import (
    DEFAULT_DATA_SOURCE_CATALOG,
    DEFAULT_PIPELINE_ARTIFACTS,
    PipelineArtifactRequirement,
    RealPipelineReadinessReport,
)


def load_real_pipeline_readiness(
    project_root: str | Path = ".",
    *,
    curation_decision_files: Iterable[str | Path] | None = None,
    data_source_catalog: str | Path | None = DEFAULT_DATA_SOURCE_CATALOG,
    required_artifacts: Iterable[PipelineArtifactRequirement] = (
        DEFAULT_PIPELINE_ARTIFACTS
    ),
    require_curation_artifacts: bool = True,
) -> RealPipelineReadinessReport:
    """Inspect local real-data artifacts and return a readiness report.

    The report is intentionally read-only. It verifies that expected source-data
    files, generated results, and curation-decision metadata are present before
    heavier inference work consumes the accepted target set.
    """
    artifacts, metrics, issues, curation_report = inspect_real_pipeline_artifacts(
        project_root,
        curation_decision_files=curation_decision_files,
        data_source_catalog=data_source_catalog,
        required_artifacts=required_artifacts,
        require_curation_artifacts=require_curation_artifacts,
    )
    return RealPipelineReadinessReport(
        artifacts=artifacts,
        metrics=metrics,
        issues=issues,
        curation_decisions=curation_report,
    )


def real_pipeline_readiness_markdown(report: RealPipelineReadinessReport) -> str:
    """Return a Markdown summary for a real-pipeline readiness report."""
    output = StringIO()
    output.write("# Real Pipeline Readiness\n\n")
    output.write(f"Status: {'ready' if report.ready else 'blocked'}\n\n")
    output.write("## Metrics\n\n")
    output.write("| Metric | Value | Source |\n")
    output.write("| --- | ---: | --- |\n")
    for metric in report.metrics:
        output.write(f"| {metric.name} | {metric.value} | {metric.source} |\n")
    output.write("\n## Artifacts\n\n")
    output.write("| Status | Role | Path | Size bytes |\n")
    output.write("| --- | --- | --- | ---: |\n")
    for artifact in report.artifacts:
        size_text = "" if artifact.size_bytes is None else str(artifact.size_bytes)
        output.write(
            "| "
            f"{artifact.status} | "
            f"{artifact.role} | "
            f"`{artifact.relative_path}` | "
            f"{size_text} |\n"
        )
    output.write("\n## Curation Decisions\n\n")
    output.write(
        "- valid: "
        f"{str(report.curation_decisions.valid).lower()}\n"
        f"- records: {len(report.curation_decisions.records)}\n"
        f"- issues: {len(report.curation_decisions.issues)}\n"
    )
    output.write("\n## Issues\n\n")
    if report.issues:
        for issue in report.issues:
            output.write(f"- {issue}\n")
    else:
        output.write("- No readiness blockers detected.\n")
    output.write("\n## Recommended Next Step\n\n")
    if report.ready:
        output.write(
            "Begin the next modeling increment with a small inference scaffold "
            "over the accepted targets, keeping the current validation and "
            "curation-decision gates fixed as regression checks.\n"
        )
    else:
        output.write(
            "Refresh the missing or stale artifacts listed above before using "
            "the accepted target set for heavier inference.\n"
        )
    return output.getvalue()


def write_real_pipeline_readiness_markdown(
    report: RealPipelineReadinessReport, path: str | Path
) -> Path:
    """Write a real-pipeline readiness Markdown report and return its path."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(real_pipeline_readiness_markdown(report), encoding="utf-8")
    return output_path
