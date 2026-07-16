"""Checksummed evidence packages for structural SMC robustness decisions."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from indoeuropop.orchestration.experiments import (
    ArtifactRole,
    ExperimentManifest,
    artifact_from_path,
    write_experiment_manifest_json,
)
from indoeuropop.orchestration.structural_smc_robustness_models import (
    StructuralSMCRobustnessDecision,
)


@dataclass(frozen=True)
class StructuralSMCRobustnessEvidencePaths:
    """Files that define and report one frozen robustness decision surface."""

    candidate_config: Path
    decision_record_md: Path
    target_fragility_decisions_csv: Path
    target_fragility_report_md: Path
    fit_metric_summary_csv: Path
    fit_metric_report_md: Path
    source_model_summary_csv: Path
    source_model_report_md: Path
    caveat_drilldown_csv: Path
    caveat_drilldown_report_md: Path
    caveat_dispositions_csv: Path
    caveat_disposition_report_md: Path
    robustness_summary_csv: Path
    robustness_report_md: Path


def structural_smc_robustness_evidence_manifest(
    decision: StructuralSMCRobustnessDecision,
    paths: StructuralSMCRobustnessEvidencePaths,
    *,
    command: str = "validate-structured-smc-robustness",
) -> ExperimentManifest:
    """Build a checksummed manifest for a fully reviewed robustness decision.

    The package records the exact decision surface and compact gate outputs. It
    deliberately does not bundle downloaded AADR data or claim that the
    engineering robustness decision is a historical inference result.
    """
    _require_fully_reviewed_dispositions(decision)
    artifacts = tuple(
        artifact_from_path(name, role, path)
        for name, role, path in _artifact_specs(paths)
    )
    dispositions = decision.caveat_dispositions
    assert dispositions is not None
    return ExperimentManifest(
        name="structural-smc-robustness-evidence",
        description="Checksummed structural SMC robustness decision evidence",
        artifacts=artifacts,
        metadata={
            "command": command,
            "candidate_name": decision.candidate_name,
            "status": decision.status,
            "recommendation": decision.recommendation,
            "blocker_count": str(decision.blocker_count),
            "caution_count": str(decision.caution_count),
            "reviewed_disposition_count": str(dispositions.reviewed_count),
            "unresolved_disposition_count": str(dispositions.unresolved_count),
            "blocking_disposition_count": str(dispositions.blocking_count),
            "scientific_scope": "robustness review evidence; not historical proof",
        },
    )


def write_structural_smc_robustness_evidence_manifest(
    decision: StructuralSMCRobustnessDecision,
    paths: StructuralSMCRobustnessEvidencePaths,
    output_path: str | Path,
    *,
    command: str = "validate-structured-smc-robustness",
) -> Path:
    """Build and write a checksummed structural SMC evidence manifest."""
    manifest = structural_smc_robustness_evidence_manifest(
        decision,
        paths,
        command=command,
    )
    return write_experiment_manifest_json(manifest, output_path)


def _require_fully_reviewed_dispositions(
    decision: StructuralSMCRobustnessDecision,
) -> None:
    """Reject evidence freezing without a valid and complete human review."""
    report = decision.caveat_dispositions
    if report is None:
        raise ValueError("evidence package requires caveat dispositions")
    if not report.valid:
        raise ValueError("evidence package requires valid caveat dispositions")
    if report.unresolved_count:
        raise ValueError("evidence package requires fully reviewed caveat dispositions")


def _artifact_specs(
    paths: StructuralSMCRobustnessEvidencePaths,
) -> tuple[tuple[str, ArtifactRole, Path], ...]:
    """Return stable names, roles, and paths for package artifacts."""
    return (
        ("candidate_config", "config", paths.candidate_config),
        ("decision_record_md", "other", paths.decision_record_md),
        (
            "target_fragility_decisions_csv",
            "other",
            paths.target_fragility_decisions_csv,
        ),
        ("target_fragility_report_md", "other", paths.target_fragility_report_md),
        ("fit_metric_summary_csv", "target_fit", paths.fit_metric_summary_csv),
        ("fit_metric_report_md", "other", paths.fit_metric_report_md),
        ("source_model_summary_csv", "target_fit", paths.source_model_summary_csv),
        ("source_model_report_md", "other", paths.source_model_report_md),
        ("caveat_drilldown_csv", "other", paths.caveat_drilldown_csv),
        ("caveat_drilldown_report_md", "other", paths.caveat_drilldown_report_md),
        ("caveat_dispositions_csv", "config", paths.caveat_dispositions_csv),
        (
            "caveat_disposition_report_md",
            "other",
            paths.caveat_disposition_report_md,
        ),
        ("robustness_summary_csv", "target_fit", paths.robustness_summary_csv),
        ("robustness_report_md", "other", paths.robustness_report_md),
    )
