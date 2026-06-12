"""Unified structural SMC robustness decision workflow."""

from __future__ import annotations

import csv
from pathlib import Path

from indoeuropop.data.structural_smc_caveat_dispositions import (
    StructuralSMCCaveatDispositionValidationReport,
    validate_structural_smc_caveat_dispositions,
)
from indoeuropop.orchestration.structural_smc_robustness_models import (
    FitMetricRobustnessSummary,
    SourceModelRobustnessSummary,
    StructuralSMCRobustnessDecision,
    StructuralSMCRobustnessDecisionPaths,
    StructuralSMCRobustnessIssue,
    TargetFragilityRobustnessSummary,
)
from indoeuropop.reporting.structural_smc_robustness import (
    write_structural_smc_robustness_decision_csv,
    write_structural_smc_robustness_decision_markdown,
)

TARGET_FRAGILITY_ROBUSTNESS_COLUMNS = frozenset(("target_id", "excluded"))
FIT_METRIC_ROBUSTNESS_COLUMNS = frozenset(
    (
        "fit_metric",
        "preference_disagreement_count",
        "uncertainty_tie_target_count",
    )
)
SOURCE_MODEL_ROBUSTNESS_COLUMNS = frozenset(
    (
        "source_model",
        "preference_disagreement_count",
        "uncertainty_tie_target_count",
        "missing_override_region_count",
        "skipped_fold_count",
    )
)


def structural_smc_robustness_decision_paths_from_dir(
    output_dir: str | Path,
) -> StructuralSMCRobustnessDecisionPaths:
    """Return conventional output paths for a robustness decision report."""
    root = Path(output_dir)
    return StructuralSMCRobustnessDecisionPaths(
        output_dir=root,
        summary_csv=root / "structural-smc-robustness-decision.csv",
        report_md=root / "structural-smc-robustness-decision.md",
    )


def run_structural_smc_robustness_decision(
    *,
    candidate_name: str,
    target_fragility_decisions_csv: str | Path,
    fit_metric_summary_csv: str | Path,
    fit_metric_report_md: str | Path,
    source_model_summary_csv: str | Path,
    source_model_report_md: str | Path,
    caveat_drilldown_csv: str | Path | None = None,
    caveat_dispositions_csv: str | Path | None = None,
    paths: StructuralSMCRobustnessDecisionPaths | None = None,
    max_unstable_holdout_folds: int = 0,
) -> StructuralSMCRobustnessDecision:
    """Load existing robustness gates and write one promotion decision report."""
    if max_unstable_holdout_folds < 0:
        raise ValueError("max_unstable_holdout_folds must be non-negative")
    output_paths = (
        structural_smc_robustness_decision_paths_from_dir("structural-smc-robustness")
        if paths is None
        else paths
    )
    target_fragility = load_target_fragility_robustness_summary(
        target_fragility_decisions_csv
    )
    fit_metric = load_fit_metric_robustness_summary(
        fit_metric_summary_csv, fit_metric_report_md
    )
    source_model = load_source_model_robustness_summary(
        source_model_summary_csv, source_model_report_md
    )
    caveat_dispositions = _optional_caveat_dispositions(
        caveat_drilldown_csv, caveat_dispositions_csv
    )
    decision = StructuralSMCRobustnessDecision(
        candidate_name=candidate_name,
        target_fragility=target_fragility,
        fit_metric=fit_metric,
        source_model=source_model,
        issues=_decision_issues(
            target_fragility,
            fit_metric,
            source_model,
            caveat_dispositions,
            max_unstable_holdout_folds=max_unstable_holdout_folds,
        ),
        paths=output_paths,
        caveat_dispositions=caveat_dispositions,
    )
    write_structural_smc_robustness_decision_csv(decision, output_paths.summary_csv)
    write_structural_smc_robustness_decision_markdown(decision, output_paths.report_md)
    return decision


def load_target_fragility_robustness_summary(
    decisions_csv: str | Path,
) -> TargetFragilityRobustnessSummary:
    """Load target-fragility counts from a decisions CSV."""
    rows = _read_rows(decisions_csv, TARGET_FRAGILITY_ROBUSTNESS_COLUMNS)
    return TargetFragilityRobustnessSummary(
        audited_target_count=len(rows),
        excluded_target_count=sum(_bool(row["excluded"]) for row in rows),
    )


def load_fit_metric_robustness_summary(
    summary_csv: str | Path,
    report_md: str | Path,
) -> FitMetricRobustnessSummary:
    """Load fit-metric robustness counts from summary CSV and Markdown."""
    rows = _read_rows(summary_csv, FIT_METRIC_ROBUSTNESS_COLUMNS)
    return FitMetricRobustnessSummary(
        metric_count=len(rows),
        unstable_holdout_fold_count=_summary_int(
            report_md, "unstable_holdout_fold_count"
        ),
        max_preference_disagreement_count=_max_int(
            rows, "preference_disagreement_count"
        ),
        max_uncertainty_tie_target_count=_max_int(rows, "uncertainty_tie_target_count"),
    )


def load_source_model_robustness_summary(
    summary_csv: str | Path,
    report_md: str | Path,
) -> SourceModelRobustnessSummary:
    """Load source-model robustness counts from summary CSV and Markdown."""
    rows = _read_rows(summary_csv, SOURCE_MODEL_ROBUSTNESS_COLUMNS)
    return SourceModelRobustnessSummary(
        source_model_count=len(rows),
        unstable_holdout_fold_count=_summary_int(
            report_md, "unstable_holdout_fold_count"
        ),
        max_preference_disagreement_count=_max_int(
            rows, "preference_disagreement_count"
        ),
        max_uncertainty_tie_target_count=_max_int(rows, "uncertainty_tie_target_count"),
        max_missing_override_region_count=_max_int(
            rows, "missing_override_region_count"
        ),
        max_skipped_fold_count=_max_int(rows, "skipped_fold_count"),
    )


def _decision_issues(
    target_fragility: TargetFragilityRobustnessSummary,
    fit_metric: FitMetricRobustnessSummary,
    source_model: SourceModelRobustnessSummary,
    caveat_dispositions: StructuralSMCCaveatDispositionValidationReport | None = None,
    *,
    max_unstable_holdout_folds: int,
) -> tuple[StructuralSMCRobustnessIssue, ...]:
    """Return blockers and caveats for a combined robustness decision."""
    issues: list[StructuralSMCRobustnessIssue] = []
    _add_target_fragility_issues(issues, target_fragility)
    _add_fit_metric_issues(issues, fit_metric, max_unstable_holdout_folds)
    _add_source_model_issues(issues, source_model, max_unstable_holdout_folds)
    _add_caveat_disposition_issues(issues, caveat_dispositions)
    return tuple(issues)


def _optional_caveat_dispositions(
    caveat_drilldown_csv: str | Path | None,
    caveat_dispositions_csv: str | Path | None,
) -> StructuralSMCCaveatDispositionValidationReport | None:
    """Return optional reviewed caveat dispositions."""
    if caveat_dispositions_csv is None:
        return None
    if caveat_drilldown_csv is None:
        raise ValueError("caveat_drilldown_csv is required with dispositions")
    return validate_structural_smc_caveat_dispositions(
        drilldown_csv=caveat_drilldown_csv,
        dispositions_csv=caveat_dispositions_csv,
    )


def _add_caveat_disposition_issues(
    issues: list[StructuralSMCRobustnessIssue],
    report: StructuralSMCCaveatDispositionValidationReport | None,
) -> None:
    """Add promotion issues from reviewed caveat dispositions."""
    if report is None:
        return
    if report.issues:
        issues.append(
            StructuralSMCRobustnessIssue(
                "caveat_disposition",
                "blocker",
                f"{len(report.issues)} structural disposition-file issues",
            )
        )
    if report.blocking_count:
        issues.append(
            StructuralSMCRobustnessIssue(
                "caveat_disposition",
                "blocker",
                f"{report.blocking_count} reviewed caveats block promotion",
            )
        )
    if report.unresolved_count:
        issues.append(
            StructuralSMCRobustnessIssue(
                "caveat_disposition",
                "caution",
                f"{report.unresolved_count} caveats still await disposition",
            )
        )


def _add_target_fragility_issues(
    issues: list[StructuralSMCRobustnessIssue],
    target_fragility: TargetFragilityRobustnessSummary,
) -> None:
    """Add target-fragility caveats or blockers."""
    if target_fragility.audited_target_count == 0:
        issues.append(
            StructuralSMCRobustnessIssue(
                "target_fragility", "blocker", "no target-fragility decisions found"
            )
        )
    if target_fragility.excluded_target_count:
        issues.append(
            StructuralSMCRobustnessIssue(
                "target_fragility",
                "caution",
                f"{target_fragility.excluded_target_count} audited targets excluded",
            )
        )


def _add_fit_metric_issues(
    issues: list[StructuralSMCRobustnessIssue],
    fit_metric: FitMetricRobustnessSummary,
    max_unstable_holdout_folds: int,
) -> None:
    """Add fit-metric robustness caveats or blockers."""
    if fit_metric.metric_count < 2:
        issues.append(
            StructuralSMCRobustnessIssue(
                "fit_metric", "blocker", "fewer than two fit metrics evaluated"
            )
        )
    if fit_metric.unstable_holdout_fold_count > max_unstable_holdout_folds:
        issues.append(
            StructuralSMCRobustnessIssue(
                "fit_metric",
                "blocker",
                f"{fit_metric.unstable_holdout_fold_count} unstable holdout folds",
            )
        )
    _add_count_caution(
        issues,
        "fit_metric",
        fit_metric.max_preference_disagreement_count,
        "maximum preference disagreements",
    )
    _add_count_caution(
        issues,
        "fit_metric",
        fit_metric.max_uncertainty_tie_target_count,
        "maximum uncertainty-tie targets",
    )


def _add_source_model_issues(
    issues: list[StructuralSMCRobustnessIssue],
    source_model: SourceModelRobustnessSummary,
    max_unstable_holdout_folds: int,
) -> None:
    """Add source-model robustness caveats or blockers."""
    if source_model.source_model_count < 2:
        issues.append(
            StructuralSMCRobustnessIssue(
                "source_model", "blocker", "fewer than two source models evaluated"
            )
        )
    if source_model.unstable_holdout_fold_count > max_unstable_holdout_folds:
        issues.append(
            StructuralSMCRobustnessIssue(
                "source_model",
                "blocker",
                f"{source_model.unstable_holdout_fold_count} unstable holdout folds",
            )
        )
    _add_count_caution(
        issues,
        "source_model",
        source_model.max_preference_disagreement_count,
        "maximum preference disagreements",
    )
    _add_count_caution(
        issues,
        "source_model",
        source_model.max_uncertainty_tie_target_count,
        "maximum uncertainty-tie targets",
    )
    _add_count_caution(
        issues,
        "source_model",
        source_model.max_missing_override_region_count,
        "maximum missing override regions",
    )
    _add_count_caution(
        issues,
        "source_model",
        source_model.max_skipped_fold_count,
        "maximum skipped folds",
    )


def _add_count_caution(
    issues: list[StructuralSMCRobustnessIssue],
    gate: str,
    count: int,
    label: str,
) -> None:
    """Add a caveat when a non-blocking diagnostic count is positive."""
    if count:
        issues.append(StructuralSMCRobustnessIssue(gate, "caution", f"{count} {label}"))


def _read_rows(
    path: str | Path, required_columns: frozenset[str]
) -> list[dict[str, str]]:
    """Read a CSV file and require named columns plus at least one row."""
    input_path = Path(path)
    with input_path.open(newline="", encoding="utf-8") as input_file:
        reader = csv.DictReader(input_file)
        if reader.fieldnames is None:
            raise ValueError(f"{input_path} must include a header row")
        missing = required_columns.difference(reader.fieldnames)
        if missing:
            raise ValueError(
                f"{input_path} missing columns: " + ", ".join(sorted(missing))
            )
        rows = [{key: value or "" for key, value in row.items()} for row in reader]
    if not rows:
        raise ValueError(f"{input_path} must contain at least one data row")
    return rows


def _summary_int(report_md: str | Path, key: str) -> int:
    """Return an integer summary bullet from a Markdown report."""
    summaries = _summary_bullets(report_md)
    if key not in summaries:
        raise ValueError(f"{Path(report_md)} missing summary key: {key}")
    return _int_cell(summaries[key], key)


def _summary_bullets(path: str | Path) -> dict[str, str]:
    """Return simple `- key: value` bullets from a Markdown report."""
    summaries: dict[str, str] = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.startswith("- ") and ":" in line:
            key, value = line[2:].split(":", 1)
            summaries[key.strip()] = value.strip()
    return summaries


def _max_int(rows: list[dict[str, str]], field_name: str) -> int:
    """Return the maximum integer value for a CSV field."""
    return max(_int_cell(row[field_name], field_name) for row in rows)


def _int_cell(value: str, field_name: str) -> int:
    """Parse a non-negative integer cell."""
    try:
        parsed = int(value)
    except ValueError as error:
        raise ValueError(f"{field_name} must be an integer") from error
    if parsed < 0:
        raise ValueError(f"{field_name} must be non-negative")
    return parsed


def _bool(value: str) -> bool:
    """Parse a lowercase CSV boolean cell."""
    normalized = value.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise ValueError("excluded must be true or false")
