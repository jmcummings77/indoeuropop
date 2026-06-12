"""Reports for structural SMC fit-metric sensitivity runs."""

from __future__ import annotations

import csv
from io import StringIO
from pathlib import Path

from indoeuropop.orchestration.structural_smc_metric_sensitivity_models import (
    StructuralSMCFitMetricRunResult,
    StructuralSMCFitMetricSensitivityResult,
)

STRUCTURAL_SMC_FIT_METRIC_SENSITIVITY_FIELDS = (
    "fit_metric",
    "validation_fold_count",
    "preference_disagreement_count",
    "calibration_child_preferred_count",
    "holdout_child_preferred_count",
    "uncertainty_target_count",
    "uncertainty_tie_target_count",
    "uncertainty_structured_pulse_target_count",
    "uncertainty_child_override_target_count",
    "validation_summary_csv",
    "validation_report_md",
    "uncertainty_csv",
    "uncertainty_report_md",
)


def structural_smc_fit_metric_sensitivity_rows(
    result: StructuralSMCFitMetricSensitivityResult,
) -> tuple[dict[str, str], ...]:
    """Return metric-level sensitivity rows as CSV-ready dictionaries."""
    return tuple(_metric_row(run) for run in result.runs)


def structural_smc_fit_metric_sensitivity_to_csv(
    result: StructuralSMCFitMetricSensitivityResult,
) -> str:
    """Return metric-level sensitivity rows serialized as CSV text."""
    output = StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=STRUCTURAL_SMC_FIT_METRIC_SENSITIVITY_FIELDS,
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerows(structural_smc_fit_metric_sensitivity_rows(result))
    return output.getvalue()


def write_structural_smc_fit_metric_sensitivity_csv(
    result: StructuralSMCFitMetricSensitivityResult,
    path: str | Path,
) -> Path:
    """Write metric-level sensitivity rows to CSV and return the path."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        structural_smc_fit_metric_sensitivity_to_csv(result), encoding="utf-8"
    )
    return output_path


def structural_smc_fit_metric_sensitivity_markdown(
    result: StructuralSMCFitMetricSensitivityResult,
) -> str:
    """Return a Markdown report for fit-metric sensitivity validation."""
    output = StringIO()
    output.write("# Structural SMC Fit-Metric Sensitivity\n\n")
    output.write(
        "This report reruns the same fragility-filtered validation folds under "
        "multiple objective functions. It checks whether candidate preferences "
        "are stable across raw and uncertainty-weighted scoring choices.\n\n"
    )
    output.write(_summary_markdown(result))
    output.write(_metric_table(result))
    output.write(_fold_stability_table(result))
    output.write("## Interpretation Guardrail\n\n")
    output.write(
        "Metric-sensitive preferences should be treated as diagnostic pressure, "
        "not direct evidence for a revised population model. They usually point "
        "to target uncertainty, source choice, or likelihood-model issues that "
        "need more explicit modeling.\n"
    )
    return output.getvalue()


def write_structural_smc_fit_metric_sensitivity_markdown(
    result: StructuralSMCFitMetricSensitivityResult,
    path: str | Path,
) -> Path:
    """Write a fit-metric sensitivity Markdown report and return the path."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        structural_smc_fit_metric_sensitivity_markdown(result), encoding="utf-8"
    )
    return output_path


def _metric_row(run: StructuralSMCFitMetricRunResult) -> dict[str, str]:
    """Return one metric run as a string-only CSV row."""
    validation = run.validation_result
    report = run.uncertainty_report
    return {
        "fit_metric": run.fit_metric,
        "validation_fold_count": str(len(validation.folds)),
        "preference_disagreement_count": str(validation.preference_disagreement_count),
        "calibration_child_preferred_count": str(
            _candidate_count(run, "calibration", "child_override")
        ),
        "holdout_child_preferred_count": str(
            _candidate_count(run, "holdout", "child_override")
        ),
        "uncertainty_target_count": str(report.target_count),
        "uncertainty_tie_target_count": str(report.uncertainty_tie_target_count),
        "uncertainty_structured_pulse_target_count": str(
            report.structured_pulse_target_count
        ),
        "uncertainty_child_override_target_count": str(
            report.child_override_target_count
        ),
        "validation_summary_csv": _optional_path(validation.summary_csv_path),
        "validation_report_md": _optional_path(validation.report_md_path),
        "uncertainty_csv": str(run.uncertainty_csv_path),
        "uncertainty_report_md": str(run.uncertainty_report_md_path),
    }


def _summary_markdown(result: StructuralSMCFitMetricSensitivityResult) -> str:
    """Return aggregate sensitivity summary bullets."""
    return (
        "## Summary\n\n"
        f"- original_target_count: {result.original_target_count}\n"
        f"- retained_target_count: {result.filtered_target_count}\n"
        f"- excluded_target_count: {result.excluded_target_count}\n"
        f"- skipped_fold_count: {result.skipped_fold_count}\n"
        f"- fit_metric_count: {len(result.runs)}\n"
        f"- unstable_holdout_fold_count: "
        f"{result.unstable_holdout_fold_count}\n\n"
    )


def _metric_table(result: StructuralSMCFitMetricSensitivityResult) -> str:
    """Return a Markdown table summarizing each fit metric."""
    output = StringIO()
    output.write("## Metric Summary\n\n")
    output.write(
        "| Fit metric | Folds | Preference disagreements | "
        "Uncertainty targets | Uncertainty ties |\n"
    )
    output.write("| --- | ---: | ---: | ---: | ---: |\n")
    for run in result.runs:
        output.write(
            f"| {run.fit_metric} | {len(run.validation_result.folds)} | "
            f"{run.preference_disagreement_count} | "
            f"{run.uncertainty_report.target_count} | "
            f"{run.uncertainty_tie_target_count} |\n"
        )
    output.write("\n")
    return output.getvalue()


def _fold_stability_table(result: StructuralSMCFitMetricSensitivityResult) -> str:
    """Return a Markdown table comparing fold preferences across metrics."""
    output = StringIO()
    output.write("## Holdout Preference Stability\n\n")
    output.write("| Fold | Stable | Preferences by metric |\n")
    output.write("| --- | --- | --- |\n")
    for fold_name in result.fold_names():
        preferences = _fold_preferences(result, fold_name)
        stable = "yes" if len(set(preferences.values())) <= 1 else "no"
        output.write(
            f"| {fold_name} | {stable} | " f"{_preference_summary(preferences)} |\n"
        )
    output.write("\n")
    return output.getvalue()


def _fold_preferences(
    result: StructuralSMCFitMetricSensitivityResult,
    fold_name: str,
) -> dict[str, str]:
    """Return one fold's holdout preferences keyed by fit metric."""
    preferences: dict[str, str] = {}
    for run in result.runs:
        by_fold = run.holdout_preferences()
        if fold_name in by_fold:
            preferences[run.fit_metric] = by_fold[fold_name]
    return preferences


def _preference_summary(preferences: dict[str, str]) -> str:
    """Return a compact preference summary for a Markdown table cell."""
    return "; ".join(
        f"{fit_metric}: {candidate}" for fit_metric, candidate in preferences.items()
    )


def _candidate_count(
    run: StructuralSMCFitMetricRunResult,
    split: str,
    candidate: str,
) -> int:
    """Return how often one candidate is preferred in one split."""
    if split == "calibration":
        return sum(
            fold.calibration_preferred_candidate == candidate
            for fold in run.validation_result.folds
        )
    return sum(
        fold.holdout_preferred_candidate == candidate
        for fold in run.validation_result.folds
    )


def _optional_path(path: Path | None) -> str:
    """Return a path string, or an empty string when no path was written."""
    return "" if path is None else str(path)
