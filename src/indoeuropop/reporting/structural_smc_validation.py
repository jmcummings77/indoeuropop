"""Reports for multi-fold structural SMC validation runs."""

from __future__ import annotations

import csv
from collections.abc import Iterable
from io import StringIO
from pathlib import Path

from indoeuropop.orchestration.abc_smc import ABCSMCWorkflowResult
from indoeuropop.orchestration.structural_smc_validation_models import (
    StructuralSMCValidationFoldResult,
)

STRUCTURAL_SMC_VALIDATION_FIELDS = (
    "fold_name",
    "categories",
    "holdout_field",
    "holdout_value",
    "start_bce",
    "end_bce",
    "calibration_target_count",
    "holdout_target_count",
    "calibration_preferred_candidate",
    "holdout_preferred_candidate",
    "preference_disagreement",
    "baseline_rmse",
    "structured_pulse_rmse",
    "child_override_rmse",
    "calibration_child_minus_structured_pulse_rmse_delta",
    "holdout_child_minus_structured_pulse_rmse_delta",
)


def structural_smc_validation_rows(
    folds: Iterable[StructuralSMCValidationFoldResult],
) -> tuple[dict[str, str], ...]:
    """Return CSV-ready rows for structural SMC validation folds."""
    return tuple(_fold_row(fold) for fold in folds)


def structural_smc_validation_to_csv(
    folds: Iterable[StructuralSMCValidationFoldResult],
) -> str:
    """Return structural SMC validation rows serialized as CSV text."""
    output = StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=STRUCTURAL_SMC_VALIDATION_FIELDS,
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerows(structural_smc_validation_rows(folds))
    return output.getvalue()


def write_structural_smc_validation_csv(
    folds: Iterable[StructuralSMCValidationFoldResult],
    path: str | Path,
) -> Path:
    """Write structural SMC validation rows to CSV and return the path."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(structural_smc_validation_to_csv(folds), encoding="utf-8")
    return output_path


def structural_smc_validation_markdown(
    folds: Iterable[StructuralSMCValidationFoldResult],
) -> str:
    """Return a Markdown report for multi-fold structural SMC validation."""
    fold_tuple = tuple(folds)
    output = StringIO()
    output.write("# Structural SMC Multi-Fold Validation\n\n")
    output.write(
        "This report repeats the same structural SMC comparison across "
        "pre-registered holdout folds. It is a validation diagnostic, not a "
        "claim that any structural candidate is historically final.\n\n"
    )
    output.write(_summary_section(fold_tuple))
    output.write(_fold_table(fold_tuple))
    output.write("## Interpretation Guardrail\n\n")
    output.write(
        "A candidate that wins calibration but loses protected or chronological "
        "holdouts should remain a local-fit hypothesis until additional folds "
        "and source-model checks agree.\n"
    )
    return output.getvalue()


def write_structural_smc_validation_markdown(
    folds: Iterable[StructuralSMCValidationFoldResult],
    path: str | Path,
) -> Path:
    """Write a structural SMC validation Markdown report and return the path."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        structural_smc_validation_markdown(folds),
        encoding="utf-8",
    )
    return output_path


def _fold_row(fold: StructuralSMCValidationFoldResult) -> dict[str, str]:
    """Return one validation fold as string-only CSV fields."""
    comparison = fold.comparison
    holdout_delta = comparison.child_minus_structured_pulse_holdout_rmse_delta
    assert holdout_delta is not None
    return {
        "fold_name": fold.spec.name,
        "categories": fold.spec.category_text,
        "holdout_field": fold.spec.holdout_field,
        "holdout_value": fold.spec.holdout_value,
        "start_bce": _optional_float(fold.spec.start_bce),
        "end_bce": _optional_float(fold.spec.end_bce),
        "calibration_target_count": str(fold.calibration_target_count),
        "holdout_target_count": str(fold.holdout_target_count),
        "calibration_preferred_candidate": fold.calibration_preferred_candidate,
        "holdout_preferred_candidate": fold.holdout_preferred_candidate,
        "preference_disagreement": str(fold.has_preference_disagreement).lower(),
        "baseline_rmse": _rmse(fold.comparison.baseline),
        "structured_pulse_rmse": _rmse(comparison.structured_pulse_result),
        "child_override_rmse": _rmse(comparison.child_result),
        "calibration_child_minus_structured_pulse_rmse_delta": (
            f"{comparison.child_minus_structured_pulse_rmse_delta:.12g}"
        ),
        "holdout_child_minus_structured_pulse_rmse_delta": f"{holdout_delta:.12g}",
    }


def _summary_section(folds: tuple[StructuralSMCValidationFoldResult, ...]) -> str:
    """Return aggregate validation counts as Markdown bullets."""
    return (
        "## Summary\n\n"
        f"- fold_count: {len(folds)}\n"
        f"- calibration_child_preferred_count: "
        f"{_preferred_count(folds, 'calibration', 'child_override')}\n"
        f"- holdout_child_preferred_count: "
        f"{_preferred_count(folds, 'holdout', 'child_override')}\n"
        f"- preference_disagreement_count: "
        f"{sum(fold.has_preference_disagreement for fold in folds)}\n\n"
    )


def _fold_table(folds: tuple[StructuralSMCValidationFoldResult, ...]) -> str:
    """Return the per-fold Markdown table."""
    output = StringIO()
    output.write("## Fold Results\n\n")
    output.write(
        "| Fold | Categories | Holdout n | Calibration preference | "
        "Holdout preference | Calibration delta | Holdout delta |\n"
    )
    output.write("| --- | --- | ---: | --- | --- | ---: | ---: |\n")
    for fold in folds:
        row = _fold_row(fold)
        output.write(
            f"| {row['fold_name']} | {row['categories']} | "
            f"{row['holdout_target_count']} | "
            f"{row['calibration_preferred_candidate']} | "
            f"{row['holdout_preferred_candidate']} | "
            f"{row['calibration_child_minus_structured_pulse_rmse_delta']} | "
            f"{row['holdout_child_minus_structured_pulse_rmse_delta']} |\n"
        )
    output.write("\n")
    return output.getvalue()


def _preferred_count(
    folds: tuple[StructuralSMCValidationFoldResult, ...],
    split: str,
    candidate: str,
) -> int:
    """Return how often one candidate is preferred by one split."""
    if split == "calibration":
        return sum(fold.calibration_preferred_candidate == candidate for fold in folds)
    return sum(fold.holdout_preferred_candidate == candidate for fold in folds)


def _rmse(result: ABCSMCWorkflowResult) -> str:
    """Return posterior predictive RMSE for one workflow result."""
    posterior_predictive = result.posterior_predictive
    assert posterior_predictive is not None
    return f"{posterior_predictive.root_mean_squared_error:.12g}"


def _optional_float(value: float | None) -> str:
    """Return a stable optional float string for reports."""
    return "" if value is None else f"{value:.12g}"
