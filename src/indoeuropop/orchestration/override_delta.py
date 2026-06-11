"""Workflow helpers for override validation delta reports."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from indoeuropop.orchestration.experiments import (
    ExperimentArtifact,
    ExperimentManifest,
    artifact_from_path,
    write_experiment_manifest_json,
)
from indoeuropop.reporting.override_delta import (
    OverrideDeltaReport,
    load_override_delta_report,
    write_override_delta_csv,
    write_override_delta_markdown,
)


@dataclass(frozen=True)
class OverrideDeltaOutputPaths:
    """Input and output paths for override-delta reporting."""

    baseline_validation_fit_csv: Path | None = None
    override_validation_fit_csv: Path | None = None
    override_delta_csv: Path | None = None
    override_delta_report_md: Path | None = None
    manifest_json: Path | None = None


@dataclass(frozen=True)
class OverrideDeltaWorkflowResult:
    """Override-delta report and materialized workflow artifacts."""

    report: OverrideDeltaReport
    artifacts: tuple[ExperimentArtifact, ...] = ()
    manifest: ExperimentManifest | None = None
    override_delta_csv_path: Path | None = None
    override_delta_report_md_path: Path | None = None
    manifest_json_path: Path | None = None


def run_override_delta_workflow(
    baseline_validation_csv: str | Path,
    override_validation_csv: str | Path,
    *,
    metric: str = "root_mean_squared_error",
    priority_values: Iterable[str] = (),
    protected_values: Iterable[str] = (),
    tolerance: float = 0.0,
    paths: OverrideDeltaOutputPaths | None = None,
    command: str = "programmatic-review-override-deltas",
    manifest_name: str = "override-validation-delta",
    manifest_description: str = "Override validation delta manifest",
    manifest_metadata: Mapping[str, str] | None = None,
) -> OverrideDeltaWorkflowResult:
    """Compare two validation CSV artifacts and optionally write reports."""
    report = load_override_delta_report(
        baseline_validation_csv,
        override_validation_csv,
        metric=metric,
        priority_values=priority_values,
        protected_values=protected_values,
        tolerance=tolerance,
    )
    output_paths = OverrideDeltaOutputPaths() if paths is None else paths
    if output_paths.override_delta_csv is not None:
        write_override_delta_csv(report, output_paths.override_delta_csv)
    if output_paths.override_delta_report_md is not None:
        write_override_delta_markdown(report, output_paths.override_delta_report_md)

    artifacts = override_delta_artifacts(output_paths)
    manifest: ExperimentManifest | None = None
    if output_paths.manifest_json is not None:
        manifest = override_delta_experiment_manifest(
            report,
            artifacts=artifacts,
            command=command,
            name=manifest_name,
            description=manifest_description,
            metadata=manifest_metadata,
        )
        write_experiment_manifest_json(manifest, output_paths.manifest_json)

    return OverrideDeltaWorkflowResult(
        report=report,
        artifacts=artifacts,
        manifest=manifest,
        override_delta_csv_path=output_paths.override_delta_csv,
        override_delta_report_md_path=output_paths.override_delta_report_md,
        manifest_json_path=output_paths.manifest_json,
    )


def override_delta_artifacts(
    paths: OverrideDeltaOutputPaths,
) -> tuple[ExperimentArtifact, ...]:
    """Return checksum-bearing artifacts for requested delta-report paths."""
    artifacts: list[ExperimentArtifact] = []
    if paths.baseline_validation_fit_csv is not None:
        artifacts.append(
            artifact_from_path(
                "baseline_validation_fit_csv",
                "target_fit",
                paths.baseline_validation_fit_csv,
            )
        )
    if paths.override_validation_fit_csv is not None:
        artifacts.append(
            artifact_from_path(
                "override_validation_fit_csv",
                "target_fit",
                paths.override_validation_fit_csv,
            )
        )
    if paths.override_delta_csv is not None:
        artifacts.append(
            artifact_from_path("override_delta_csv", "other", paths.override_delta_csv)
        )
    if paths.override_delta_report_md is not None:
        artifacts.append(
            artifact_from_path(
                "override_delta_report_md",
                "other",
                paths.override_delta_report_md,
            )
        )
    return tuple(artifacts)


def override_delta_experiment_manifest(
    report: OverrideDeltaReport,
    *,
    artifacts: Iterable[ExperimentArtifact] = (),
    command: str = "programmatic-review-override-deltas",
    name: str = "override-validation-delta",
    description: str = "Override validation delta manifest",
    metadata: Mapping[str, str] | None = None,
) -> ExperimentManifest:
    """Return a manifest for an override-delta report workflow."""
    manifest_metadata = {
        "command": command,
        "fit_metric": report.metric,
        "holdout_field": report.holdout_field,
        "fold_count": str(len(report.rows)),
        "priority_values": "|".join(report.priority_values),
        "protected_values": "|".join(report.protected_values),
        "protected_degraded": str(report.protected_degraded).lower(),
    }
    manifest_metadata.update({} if metadata is None else metadata)
    return ExperimentManifest(
        name=name,
        description=description,
        artifacts=tuple(artifacts),
        metadata=manifest_metadata,
    )
