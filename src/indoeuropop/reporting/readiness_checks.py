"""Artifact and metric checks for real-pipeline readiness reports."""

from __future__ import annotations

import csv
import json
from collections.abc import Iterable, MutableSequence
from pathlib import Path

from indoeuropop.data.curation_decisions import (
    CurationDecisionValidationReport,
    validate_curation_decision_files,
)
from indoeuropop.data.data_sources import load_data_source_catalog
from indoeuropop.reporting.readiness_models import (
    DEFAULT_CURATION_DECISION_FILES,
    PipelineArtifactRequirement,
    PipelineArtifactStatus,
    ReadinessMetric,
)


def inspect_real_pipeline_artifacts(
    project_root: str | Path,
    *,
    curation_decision_files: Iterable[str | Path] | None,
    data_source_catalog: str | Path | None,
    required_artifacts: Iterable[PipelineArtifactRequirement],
    require_curation_artifacts: bool,
) -> tuple[
    tuple[PipelineArtifactStatus, ...],
    tuple[ReadinessMetric, ...],
    tuple[str, ...],
    CurationDecisionValidationReport,
]:
    """Return checked artifacts, extracted metrics, issues, and curation status."""
    root = Path(project_root).resolve()
    artifact_statuses = [
        _artifact_status(requirement, root) for requirement in tuple(required_artifacts)
    ]
    issue_collector = _missing_artifact_issues(artifact_statuses)
    metrics: list[ReadinessMetric] = []

    _extend_data_source_statuses(
        artifact_statuses,
        metrics,
        issue_collector,
        root,
        data_source_catalog,
    )
    _collect_standard_metrics(root, metrics, issue_collector)
    curation_report = _load_curation_decision_report(
        (
            DEFAULT_CURATION_DECISION_FILES
            if curation_decision_files is None
            else curation_decision_files
        ),
        root,
        require_curation_artifacts,
    )
    for issue in curation_report.issues:
        issue_collector.append(f"curation decision issue: {issue}")
    issue_collector.extend(_consistency_issues(metrics))
    return (
        tuple(artifact_statuses),
        tuple(metrics),
        tuple(issue_collector),
        curation_report,
    )


def _collect_standard_metrics(
    root: Path,
    metrics: MutableSequence[ReadinessMetric],
    issues: MutableSequence[str],
) -> None:
    """Collect diagnostics and row-count metrics from conventional outputs."""
    _collect_json_metrics(
        root / "results/real-aadr-comparison/aadr-target-diagnostics.json",
        source="real AADR diagnostics",
        prefix="real_aadr",
        keys=(
            "selected_sample_count",
            "retained_target_count",
            "target_observation_count",
            "decision_deferred_target_count",
        ),
        metrics=metrics,
        issues=issues,
    )
    _collect_json_metrics(
        root / "results/qpadm-rerun/qpadm-rerun-diagnostics.json",
        source="qpAdm rerun diagnostics",
        prefix="qpadm_rerun",
        keys=(
            "baseline_target_observation_count",
            "post_target_observation_count",
            "accepted_target_observation_count",
            "rescued_target_count",
        ),
        metrics=metrics,
        issues=issues,
    )
    _collect_csv_row_metric(
        root / "results/real-aadr-comparison/aadr-target-observations.csv",
        "real_target_row_count",
        "real AADR target observations",
        metrics,
        issues,
    )
    _collect_csv_row_metric(
        root / "results/qpadm-rerun/accepted-target-observations.csv",
        "accepted_target_row_count",
        "accepted qpAdm target observations",
        metrics,
        issues,
    )
    _collect_csv_row_metric(
        root / "results/qpadm-rerun/central-europe-structured-targets.csv",
        "structured_target_row_count",
        "central-Europe structured targets",
        metrics,
        issues,
    )
    _collect_override_delta_metrics(
        root
        / "results/qpadm-rerun/central-europe-curated-vs-interaction-best-delta.csv",
        metrics,
        issues,
    )


def _artifact_status(
    requirement: PipelineArtifactRequirement, root: Path
) -> PipelineArtifactStatus:
    """Return existence status for one artifact requirement."""
    path = (
        root / requirement.path
        if not requirement.path.is_absolute()
        else requirement.path
    )
    exists = path.exists()
    return PipelineArtifactStatus(
        label=requirement.label,
        relative_path=_relative_path(path, root),
        role=requirement.role,
        required=requirement.required,
        exists=exists,
        size_bytes=path.stat().st_size if exists and path.is_file() else None,
    )


def _extend_data_source_statuses(
    artifact_statuses: MutableSequence[PipelineArtifactStatus],
    metrics: MutableSequence[ReadinessMetric],
    issues: MutableSequence[str],
    root: Path,
    catalog_path: str | Path | None,
) -> None:
    """Append source-data file statuses from the local data-source catalog."""
    if catalog_path is None:
        return
    raw_catalog_path = Path(catalog_path)
    resolved_catalog = (
        raw_catalog_path if raw_catalog_path.is_absolute() else root / raw_catalog_path
    )
    if not resolved_catalog.exists():
        return
    try:
        catalog = load_data_source_catalog(resolved_catalog)
    except ValueError as exc:
        issues.append(f"data source catalog invalid: {exc}")
        return
    local_records = tuple(
        record for record in catalog.records if record.status == "local"
    )
    present_count = 0
    for record in local_records:
        status = _artifact_status(
            PipelineArtifactRequirement(
                f"local data source {record.dataset_id}",
                Path(record.uri),
                "source_data",
            ),
            root,
        )
        artifact_statuses.append(status)
        present_count += int(status.exists)
        if not status.exists:
            issues.append(f"missing local data source: {status.relative_path}")
    metrics.append(
        ReadinessMetric(
            "local_data_source_count",
            str(len(local_records)),
            "data source catalog",
        )
    )
    metrics.append(
        ReadinessMetric(
            "present_local_data_source_count",
            str(present_count),
            "data source catalog",
        )
    )


def _missing_artifact_issues(
    artifact_statuses: Iterable[PipelineArtifactStatus],
) -> list[str]:
    """Return missing-artifact readiness issues."""
    return [
        f"missing required artifact: {status.relative_path}"
        for status in artifact_statuses
        if status.required and not status.exists
    ]


def _collect_json_metrics(
    path: Path,
    *,
    source: str,
    prefix: str,
    keys: Iterable[str],
    metrics: MutableSequence[ReadinessMetric],
    issues: MutableSequence[str],
) -> None:
    """Append selected scalar metrics from a JSON diagnostics artifact."""
    if not path.exists():
        return
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        issues.append(f"invalid JSON diagnostics: {_path_text(path)} ({exc.msg})")
        return
    if not isinstance(payload, dict):
        issues.append(f"invalid JSON diagnostics: {_path_text(path)} is not an object")
        return
    for key in keys:
        value = payload.get(key)
        if isinstance(value, int | float | str):
            metrics.append(ReadinessMetric(f"{prefix}_{key}", str(value), source))


def _collect_csv_row_metric(
    path: Path,
    metric_name: str,
    source: str,
    metrics: MutableSequence[ReadinessMetric],
    issues: MutableSequence[str],
) -> None:
    """Append one row-count metric from a CSV artifact."""
    if not path.exists():
        return
    try:
        row_count = len(_csv_rows(path))
    except ValueError as exc:
        issues.append(f"invalid CSV artifact: {_path_text(path)} ({exc})")
        return
    metrics.append(ReadinessMetric(metric_name, str(row_count), source))


def _collect_override_delta_metrics(
    path: Path,
    metrics: MutableSequence[ReadinessMetric],
    issues: MutableSequence[str],
) -> None:
    """Append summary metrics from an override-delta CSV artifact."""
    if not path.exists():
        return
    try:
        rows = _csv_rows(path)
        deltas = tuple(float(row["validation_delta"]) for row in rows)
    except (KeyError, ValueError) as exc:
        issues.append(f"invalid override delta CSV: {_path_text(path)} ({exc})")
        return
    if not rows:
        issues.append(f"invalid override delta CSV: {_path_text(path)} has no rows")
        return
    priority_deltas = tuple(
        float(row["validation_delta"]) for row in rows if row.get("priority") == "true"
    )
    protected_deltas = tuple(
        float(row["validation_delta"]) for row in rows if row.get("protected") == "true"
    )
    protected_degraded = any(row.get("protected_degraded") == "true" for row in rows)
    source = "interaction-best override delta"
    metrics.extend(
        (
            ReadinessMetric("override_delta_row_count", str(len(rows)), source),
            ReadinessMetric(
                "override_mean_validation_delta", _mean_text(deltas), source
            ),
            ReadinessMetric(
                "override_priority_mean_delta",
                _mean_text(priority_deltas),
                source,
            ),
            ReadinessMetric(
                "override_protected_max_delta",
                _max_text(protected_deltas),
                source,
            ),
            ReadinessMetric(
                "override_protected_degraded",
                str(protected_degraded).lower(),
                source,
            ),
        )
    )


def _load_curation_decision_report(
    paths: Iterable[str | Path],
    root: Path,
    require_artifacts: bool,
) -> CurationDecisionValidationReport:
    """Return curation-decision validation, converting load errors to issues."""
    try:
        return validate_curation_decision_files(
            paths,
            project_root=root,
            require_artifacts=require_artifacts,
        )
    except (OSError, ValueError) as exc:
        return CurationDecisionValidationReport((), (str(exc),))


def _consistency_issues(metrics: Iterable[ReadinessMetric]) -> tuple[str, ...]:
    """Return issues when diagnostics counts disagree with generated CSV rows."""
    metric_map = {metric.name: metric.value for metric in metrics}
    checks = (
        (
            "real_aadr_target_observation_count",
            "real_target_row_count",
            "real AADR diagnostics target_observation_count",
        ),
        (
            "qpadm_rerun_accepted_target_observation_count",
            "accepted_target_row_count",
            "qpAdm rerun diagnostics accepted_target_observation_count",
        ),
    )
    issues: list[str] = []
    for expected_name, actual_name, label in checks:
        expected = _optional_int(metric_map.get(expected_name))
        actual = _optional_int(metric_map.get(actual_name))
        if expected is not None and actual is not None and expected != actual:
            issues.append(
                f"{label} ({expected}) does not match {actual_name} ({actual})"
            )
    return tuple(issues)


def _csv_rows(path: Path) -> tuple[dict[str, str], ...]:
    """Return CSV rows after requiring a header."""
    with path.open(newline="", encoding="utf-8") as input_file:
        reader = csv.DictReader(input_file)
        if reader.fieldnames is None:
            raise ValueError("missing header")
        return tuple(dict(row) for row in reader)


def _mean_text(values: Iterable[float]) -> str:
    """Return a six-decimal mean or zero for an empty collection."""
    value_tuple = tuple(values)
    if not value_tuple:
        return "0.000000"
    return f"{sum(value_tuple) / len(value_tuple):.6f}"


def _max_text(values: Iterable[float]) -> str:
    """Return a six-decimal maximum or zero for an empty collection."""
    value_tuple = tuple(values)
    if not value_tuple:
        return "0.000000"
    return f"{max(value_tuple):.6f}"


def _optional_int(value: str | None) -> int | None:
    """Return an integer parsed from text, or `None` when unavailable."""
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _relative_path(path: Path, root: Path) -> str:
    """Return a POSIX path relative to root when possible."""
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _path_text(path: Path) -> str:
    """Return a compact path string for error messages."""
    return path.as_posix()
