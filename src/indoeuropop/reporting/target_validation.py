"""CSV and Markdown reports for held-out target validation folds."""

from __future__ import annotations

import csv
from collections.abc import Iterable
from io import StringIO
from pathlib import Path

from indoeuropop.analysis.fitting import FIT_METRICS, TargetFit
from indoeuropop.analysis.validation import TargetValidationFold, ValidatedSweepRun

VALIDATION_METRIC_FIELDS = (
    "mean_absolute_error",
    "root_mean_squared_error",
    "chi_square",
    "reduced_chi_square",
    "max_abs_z_score",
)


def target_validation_fieldnames(
    folds: Iterable[TargetValidationFold],
) -> tuple[str, ...]:
    """Return stable CSV field names for held-out validation rows."""
    fold_tuple = _validated_folds(folds)
    parameter_names = _sampled_parameter_names(fold_tuple)
    return (
        "holdout_field",
        "holdout_value",
        "rank",
        "run_index",
        *(f"sampled_{parameter_name}" for parameter_name in parameter_names),
        "calibration_observation_count",
        "validation_observation_count",
        *(f"calibration_{metric_name}" for metric_name in VALIDATION_METRIC_FIELDS),
        *(f"validation_{metric_name}" for metric_name in VALIDATION_METRIC_FIELDS),
        *(
            f"generalization_gap_{metric_name}"
            for metric_name in VALIDATION_METRIC_FIELDS
        ),
    )


def target_validation_rows(
    folds: Iterable[TargetValidationFold],
) -> tuple[dict[str, str], ...]:
    """Return held-out validation folds as string-only CSV rows."""
    fold_tuple = _validated_folds(folds)
    parameter_names = _sampled_parameter_names(fold_tuple)
    rows: list[dict[str, str]] = []
    for fold in fold_tuple:
        for rank, validated_run in enumerate(fold.runs, start=1):
            rows.append(_validation_row(fold, rank, validated_run, parameter_names))
    return tuple(rows)


def target_validation_to_csv(folds: Iterable[TargetValidationFold]) -> str:
    """Return held-out validation rows serialized as CSV text."""
    fold_tuple = _validated_folds(folds)
    return _rows_to_csv(
        target_validation_fieldnames(fold_tuple),
        target_validation_rows(fold_tuple),
    )


def write_target_validation_csv(
    folds: Iterable[TargetValidationFold], path: str | Path
) -> Path:
    """Write held-out validation rows to a CSV file and return the path."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(target_validation_to_csv(folds), encoding="utf-8")
    return output_path


def target_validation_markdown(
    folds: Iterable[TargetValidationFold],
    *,
    metric: str = "chi_square",
) -> str:
    """Return a compact Markdown summary for held-out validation folds."""
    if metric not in FIT_METRICS:
        raise ValueError(f"unsupported fit metric: {metric}")
    fold_tuple = _validated_folds(folds)
    output = StringIO()
    output.write("# Held-Out Target Validation\n\n")
    output.write("These diagnostics rank each fold on calibration targets and ")
    output.write("then report the held-out validation fit.\n\n")
    output.write(f"- holdout_field: `{fold_tuple[0].holdout_field}`\n")
    output.write(f"- fold_count: {len(fold_tuple)}\n")
    output.write(f"- ranking_metric: `{metric}`\n\n")
    output.write("| holdout_value | calibration_n | validation_n | ")
    output.write("best_run_index | calibration_fit | validation_fit | gap |\n")
    output.write("| --- | ---: | ---: | ---: | ---: | ---: | ---: |\n")
    for fold in fold_tuple:
        best_run = fold.best_run
        output.write(
            f"| {fold.holdout_value} | "
            f"{best_run.fit.calibration.observation_count} | "
            f"{best_run.fit.validation.observation_count} | "
            f"{best_run.run.index} | "
            f"{_value_text(best_run.metric_value(metric, 'calibration'))} | "
            f"{_value_text(best_run.metric_value(metric, 'validation'))} | "
            f"{_value_text(best_run.generalization_gap(metric))} |\n"
        )
    return output.getvalue()


def write_target_validation_markdown(
    folds: Iterable[TargetValidationFold],
    path: str | Path,
    *,
    metric: str = "chi_square",
) -> Path:
    """Write held-out validation Markdown and return the path."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        target_validation_markdown(folds, metric=metric),
        encoding="utf-8",
    )
    return output_path


def _validated_folds(
    folds: Iterable[TargetValidationFold],
) -> tuple[TargetValidationFold, ...]:
    """Return a non-empty fold tuple with consistent holdout fields."""
    fold_tuple = tuple(folds)
    if not fold_tuple:
        raise ValueError("folds must contain at least one validation fold")
    holdout_fields = {fold.holdout_field for fold in fold_tuple}
    if len(holdout_fields) != 1:
        raise ValueError("all validation folds must use the same holdout field")
    return fold_tuple


def _sampled_parameter_names(
    folds: tuple[TargetValidationFold, ...],
) -> tuple[str, ...]:
    """Return sorted sampled parameter names for validation runs."""
    expected = tuple(sorted(folds[0].best_run.run.sampled_values))
    if not expected:
        raise ValueError("validated sweep runs must contain sampled parameters")
    expected_set = set(expected)
    for fold in folds:
        for validated_run in fold.runs:
            if set(validated_run.run.sampled_values) != expected_set:
                raise ValueError("all validation runs must sample the same parameters")
    return expected


def _validation_row(
    fold: TargetValidationFold,
    rank: int,
    validated_run: ValidatedSweepRun,
    parameter_names: tuple[str, ...],
) -> dict[str, str]:
    """Return one held-out validation CSV row."""
    row = {
        "holdout_field": fold.holdout_field,
        "holdout_value": fold.holdout_value,
        "rank": str(rank),
        "run_index": str(validated_run.run.index),
    }
    for parameter_name in parameter_names:
        row[f"sampled_{parameter_name}"] = _value_text(
            validated_run.run.sampled_values[parameter_name]
        )
    row.update(_fit_row("calibration", validated_run.fit.calibration))
    row.update(_fit_row("validation", validated_run.fit.validation))
    for metric_name in VALIDATION_METRIC_FIELDS:
        row[f"generalization_gap_{metric_name}"] = _value_text(
            validated_run.generalization_gap(metric_name)
        )
    return row


def _fit_row(prefix: str, fit: TargetFit) -> dict[str, str]:
    """Return prefixed fit fields for one split."""
    return {
        f"{prefix}_observation_count": str(fit.observation_count),
        f"{prefix}_mean_absolute_error": _value_text(fit.mean_absolute_error),
        f"{prefix}_root_mean_squared_error": _value_text(fit.root_mean_squared_error),
        f"{prefix}_chi_square": _value_text(fit.chi_square),
        f"{prefix}_reduced_chi_square": _value_text(fit.reduced_chi_square),
        f"{prefix}_max_abs_z_score": _value_text(fit.max_abs_z_score),
    }


def _rows_to_csv(fieldnames: tuple[str, ...], rows: Iterable[dict[str, str]]) -> str:
    """Return rows as CSV text with stable line endings."""
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def _value_text(value: float) -> str:
    """Return a stable string representation for numeric values."""
    return f"{value:.12g}"
