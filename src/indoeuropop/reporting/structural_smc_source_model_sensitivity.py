"""Reports for structural SMC source-model sensitivity runs."""

from __future__ import annotations

import csv
from io import StringIO
from pathlib import Path

from indoeuropop.orchestration.structural_smc_source_model_sensitivity_models import (
    StructuralSMCSourceModelRunResult,
    StructuralSMCSourceModelSensitivityResult,
)

STRUCTURAL_SMC_SOURCE_MODEL_SENSITIVITY_FIELDS = (
    "source_model",
    "original_target_count",
    "prepared_target_count",
    "validation_fold_count",
    "skipped_fold_count",
    "preference_disagreement_count",
    "holdout_child_preferred_count",
    "uncertainty_target_count",
    "uncertainty_tie_target_count",
    "missing_override_region_count",
    "prepared_targets_csv",
    "structured_config_toml",
    "validation_summary_csv",
    "validation_report_md",
    "uncertainty_csv",
    "uncertainty_report_md",
)


def structural_smc_source_model_sensitivity_rows(
    result: StructuralSMCSourceModelSensitivityResult,
) -> tuple[dict[str, str], ...]:
    """Return source-model sensitivity rows as CSV-ready dictionaries."""
    return tuple(_source_model_row(run) for run in result.runs)


def structural_smc_source_model_sensitivity_to_csv(
    result: StructuralSMCSourceModelSensitivityResult,
) -> str:
    """Return source-model sensitivity rows serialized as CSV text."""
    output = StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=STRUCTURAL_SMC_SOURCE_MODEL_SENSITIVITY_FIELDS,
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerows(structural_smc_source_model_sensitivity_rows(result))
    return output.getvalue()


def write_structural_smc_source_model_sensitivity_csv(
    result: StructuralSMCSourceModelSensitivityResult,
    path: str | Path,
) -> Path:
    """Write source-model sensitivity rows to CSV and return the path."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        structural_smc_source_model_sensitivity_to_csv(result), encoding="utf-8"
    )
    return output_path


def structural_smc_source_model_sensitivity_markdown(
    result: StructuralSMCSourceModelSensitivityResult,
) -> str:
    """Return a Markdown report for source-model sensitivity validation."""
    output = StringIO()
    output.write("# Structural SMC Source-Model Sensitivity\n\n")
    output.write(
        "This report aligns labeled target datasets by shared target IDs, "
        "optionally removes fragile targets, and reruns structural validation "
        "for each source-model target surface.\n\n"
    )
    output.write(_summary_markdown(result))
    output.write(_source_model_table(result))
    output.write(_fold_stability_table(result))
    output.write("## Interpretation Guardrail\n\n")
    output.write(
        "A source-model-sensitive preference is evidence that qpAdm target "
        "construction is still carrying the result. Resolve source/outgroup "
        "choices before promoting a new demographic mechanism.\n"
    )
    return output.getvalue()


def write_structural_smc_source_model_sensitivity_markdown(
    result: StructuralSMCSourceModelSensitivityResult,
    path: str | Path,
) -> Path:
    """Write a source-model sensitivity Markdown report and return the path."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        structural_smc_source_model_sensitivity_markdown(result), encoding="utf-8"
    )
    return output_path


def _source_model_row(run: StructuralSMCSourceModelRunResult) -> dict[str, str]:
    """Return one source-model run as a string-only CSV row."""
    validation = run.validation_result
    return {
        "source_model": run.label,
        "original_target_count": str(run.original_target_count),
        "prepared_target_count": str(run.prepared_target_count),
        "validation_fold_count": str(len(validation.folds)),
        "skipped_fold_count": str(run.skipped_fold_count),
        "preference_disagreement_count": str(validation.preference_disagreement_count),
        "holdout_child_preferred_count": str(_holdout_child_count(run)),
        "uncertainty_target_count": str(run.uncertainty_report.target_count),
        "uncertainty_tie_target_count": str(
            run.uncertainty_report.uncertainty_tie_target_count
        ),
        "missing_override_region_count": str(len(run.missing_override_regions)),
        "prepared_targets_csv": str(run.prepared_targets_csv_path),
        "structured_config_toml": str(run.structured_config_toml_path),
        "validation_summary_csv": _optional_path(validation.summary_csv_path),
        "validation_report_md": _optional_path(validation.report_md_path),
        "uncertainty_csv": str(run.uncertainty_csv_path),
        "uncertainty_report_md": str(run.uncertainty_report_md_path),
    }


def _summary_markdown(result: StructuralSMCSourceModelSensitivityResult) -> str:
    """Return aggregate source-model sensitivity summary bullets."""
    return (
        "## Summary\n\n"
        f"- source_model_count: {result.source_model_count}\n"
        f"- common_target_count: {len(result.common_target_ids)}\n"
        f"- excluded_fragile_common_target_count: "
        f"{len(result.excluded_fragile_target_ids)}\n"
        f"- retained_common_target_count: {result.retained_common_target_count}\n"
        f"- unstable_holdout_fold_count: "
        f"{result.unstable_holdout_fold_count}\n\n"
    )


def _source_model_table(result: StructuralSMCSourceModelSensitivityResult) -> str:
    """Return a Markdown table summarizing each source model."""
    output = StringIO()
    output.write("## Source-Model Summary\n\n")
    output.write(
        "| Source model | Targets | Folds | Disagreements | "
        "Uncertainty ties | Missing override regions |\n"
    )
    output.write("| --- | ---: | ---: | ---: | ---: | ---: |\n")
    for run in result.runs:
        output.write(
            f"| {run.label} | {run.prepared_target_count} | "
            f"{len(run.validation_result.folds)} | "
            f"{run.preference_disagreement_count} | "
            f"{run.uncertainty_report.uncertainty_tie_target_count} | "
            f"{len(run.missing_override_regions)} |\n"
        )
    output.write("\n")
    return output.getvalue()


def _fold_stability_table(result: StructuralSMCSourceModelSensitivityResult) -> str:
    """Return a Markdown table comparing fold preferences across sources."""
    output = StringIO()
    output.write("## Holdout Preference Stability\n\n")
    output.write("| Fold | Stable | Preferences by source model |\n")
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
    result: StructuralSMCSourceModelSensitivityResult,
    fold_name: str,
) -> dict[str, str]:
    """Return one fold's holdout preferences keyed by source-model label."""
    preferences: dict[str, str] = {}
    for run in result.runs:
        by_fold = run.holdout_preferences()
        if fold_name in by_fold:
            preferences[run.label] = by_fold[fold_name]
    return preferences


def _preference_summary(preferences: dict[str, str]) -> str:
    """Return a compact preference summary for a Markdown table cell."""
    return "; ".join(
        f"{source_model}: {candidate}"
        for source_model, candidate in preferences.items()
    )


def _holdout_child_count(run: StructuralSMCSourceModelRunResult) -> int:
    """Return how often the child override is preferred on holdouts."""
    return sum(
        fold.holdout_preferred_candidate == "child_override"
        for fold in run.validation_result.folds
    )


def _optional_path(path: Path | None) -> str:
    """Return a path string, or an empty string when no path was written."""
    return "" if path is None else str(path)
