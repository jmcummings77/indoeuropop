"""Reports for unified structural SMC robustness decisions."""

from __future__ import annotations

import csv
from io import StringIO
from pathlib import Path

from indoeuropop.orchestration.structural_smc_robustness_models import (
    StructuralSMCRobustnessDecision,
    StructuralSMCRobustnessIssue,
)

STRUCTURAL_SMC_ROBUSTNESS_DECISION_FIELDS = (
    "candidate_name",
    "status",
    "recommendation",
    "blocker_count",
    "caution_count",
    "audited_target_count",
    "excluded_target_count",
    "retained_audited_target_count",
    "fit_metric_count",
    "fit_metric_unstable_holdout_fold_count",
    "fit_metric_max_preference_disagreement_count",
    "fit_metric_max_uncertainty_tie_target_count",
    "source_model_count",
    "source_model_unstable_holdout_fold_count",
    "source_model_max_preference_disagreement_count",
    "source_model_max_uncertainty_tie_target_count",
    "source_model_max_missing_override_region_count",
    "source_model_max_skipped_fold_count",
    "caveat_disposition_reviewed_count",
    "caveat_disposition_unresolved_count",
    "caveat_disposition_blocking_count",
    "caveat_disposition_issue_count",
)


def structural_smc_robustness_decision_row(
    decision: StructuralSMCRobustnessDecision,
) -> dict[str, str]:
    """Return the unified decision as a string-only CSV row."""
    target_fragility = decision.target_fragility
    fit_metric = decision.fit_metric
    source_model = decision.source_model
    return {
        "candidate_name": decision.candidate_name,
        "status": decision.status,
        "recommendation": decision.recommendation,
        "blocker_count": str(decision.blocker_count),
        "caution_count": str(decision.caution_count),
        "audited_target_count": str(target_fragility.audited_target_count),
        "excluded_target_count": str(target_fragility.excluded_target_count),
        "retained_audited_target_count": str(
            target_fragility.retained_audited_target_count
        ),
        "fit_metric_count": str(fit_metric.metric_count),
        "fit_metric_unstable_holdout_fold_count": str(
            fit_metric.unstable_holdout_fold_count
        ),
        "fit_metric_max_preference_disagreement_count": str(
            fit_metric.max_preference_disagreement_count
        ),
        "fit_metric_max_uncertainty_tie_target_count": str(
            fit_metric.max_uncertainty_tie_target_count
        ),
        "source_model_count": str(source_model.source_model_count),
        "source_model_unstable_holdout_fold_count": str(
            source_model.unstable_holdout_fold_count
        ),
        "source_model_max_preference_disagreement_count": str(
            source_model.max_preference_disagreement_count
        ),
        "source_model_max_uncertainty_tie_target_count": str(
            source_model.max_uncertainty_tie_target_count
        ),
        "source_model_max_missing_override_region_count": str(
            source_model.max_missing_override_region_count
        ),
        "source_model_max_skipped_fold_count": str(source_model.max_skipped_fold_count),
        "caveat_disposition_reviewed_count": _optional_disposition_count(
            decision, "reviewed_count"
        ),
        "caveat_disposition_unresolved_count": _optional_disposition_count(
            decision, "unresolved_count"
        ),
        "caveat_disposition_blocking_count": _optional_disposition_count(
            decision, "blocking_count"
        ),
        "caveat_disposition_issue_count": (
            ""
            if decision.caveat_dispositions is None
            else str(len(decision.caveat_dispositions.issues))
        ),
    }


def structural_smc_robustness_decision_to_csv(
    decision: StructuralSMCRobustnessDecision,
) -> str:
    """Return the unified robustness decision serialized as CSV text."""
    output = StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=STRUCTURAL_SMC_ROBUSTNESS_DECISION_FIELDS,
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerow(structural_smc_robustness_decision_row(decision))
    return output.getvalue()


def write_structural_smc_robustness_decision_csv(
    decision: StructuralSMCRobustnessDecision,
    path: str | Path,
) -> Path:
    """Write the unified robustness decision CSV and return the path."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        structural_smc_robustness_decision_to_csv(decision), encoding="utf-8"
    )
    return output_path


def structural_smc_robustness_decision_markdown(
    decision: StructuralSMCRobustnessDecision,
) -> str:
    """Return a Markdown report for a unified robustness decision."""
    output = StringIO()
    output.write("# Structural SMC Robustness Decision\n\n")
    output.write(
        "This report combines target-fragility, fit-metric sensitivity, and "
        "source-model sensitivity gates into one promotion decision. It does "
        "not rerun inference; it summarizes already generated gate artifacts.\n\n"
    )
    output.write(_decision_summary(decision))
    output.write(_gate_table(decision))
    output.write(_disposition_summary(decision))
    output.write(_issues_table(decision.issues))
    output.write("## Interpretation Guardrail\n\n")
    output.write(
        "A non-blocked status is not a scientific acceptance claim. It means "
        "the configured robustness screens did not find preference instability "
        "that would block candidate promotion.\n"
    )
    return output.getvalue()


def write_structural_smc_robustness_decision_markdown(
    decision: StructuralSMCRobustnessDecision,
    path: str | Path,
) -> Path:
    """Write a unified robustness Markdown report and return the path."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        structural_smc_robustness_decision_markdown(decision), encoding="utf-8"
    )
    return output_path


def _decision_summary(decision: StructuralSMCRobustnessDecision) -> str:
    """Return headline decision bullets."""
    return (
        "## Decision\n\n"
        f"- candidate_name: {decision.candidate_name}\n"
        f"- status: {decision.status}\n"
        f"- recommendation: {decision.recommendation}\n"
        f"- blocker_count: {decision.blocker_count}\n"
        f"- caution_count: {decision.caution_count}\n\n"
    )


def _gate_table(decision: StructuralSMCRobustnessDecision) -> str:
    """Return a Markdown table with gate-level counts."""
    target_fragility = decision.target_fragility
    fit_metric = decision.fit_metric
    source_model = decision.source_model
    return (
        "## Gate Summary\n\n"
        "| Gate | Primary count | Stability count | Diagnostic count |\n"
        "| --- | ---: | ---: | ---: |\n"
        f"| target_fragility | {target_fragility.audited_target_count} |  | "
        f"{target_fragility.excluded_target_count} excluded |\n"
        f"| fit_metric | {fit_metric.metric_count} | "
        f"{fit_metric.unstable_holdout_fold_count} unstable folds | "
        f"{fit_metric.max_uncertainty_tie_target_count} max ties |\n"
        f"| source_model | {source_model.source_model_count} | "
        f"{source_model.unstable_holdout_fold_count} unstable folds | "
        f"{source_model.max_missing_override_region_count} max missing overrides |\n\n"
    )


def _disposition_summary(decision: StructuralSMCRobustnessDecision) -> str:
    """Return reviewed caveat-disposition summary Markdown."""
    report = decision.caveat_dispositions
    if report is None:
        return ""
    return (
        "## Caveat Dispositions\n\n"
        f"- reviewed_disposition_count: {report.reviewed_count}\n"
        f"- unresolved_caveat_count: {report.unresolved_count}\n"
        f"- blocking_disposition_count: {report.blocking_count}\n"
        f"- disposition_issue_count: {len(report.issues)}\n\n"
    )


def _issues_table(issues: tuple[StructuralSMCRobustnessIssue, ...]) -> str:
    """Return a Markdown table of blockers and caveats."""
    output = StringIO()
    output.write("## Issues\n\n")
    if not issues:
        output.write("No blockers or caveats were detected.\n\n")
        return output.getvalue()
    output.write("| Severity | Gate | Message |\n")
    output.write("| --- | --- | --- |\n")
    for issue in issues:
        output.write(f"| {issue.severity} | {issue.gate} | {issue.message} |\n")
    output.write("\n")
    return output.getvalue()


def _optional_disposition_count(
    decision: StructuralSMCRobustnessDecision,
    field_name: str,
) -> str:
    """Return an optional disposition count as text."""
    if decision.caveat_dispositions is None:
        return ""
    return str(getattr(decision.caveat_dispositions, field_name))
