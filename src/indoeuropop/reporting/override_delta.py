"""Reports comparing baseline and overridden validation fit artifacts."""

from __future__ import annotations

import csv
from collections.abc import Iterable
from dataclasses import dataclass
from io import StringIO
from math import isfinite
from pathlib import Path

from indoeuropop.analysis.fitting import FIT_METRICS

OVERRIDE_DELTA_FIELDS = (
    "holdout_field",
    "holdout_value",
    "baseline_run_index",
    "override_run_index",
    "baseline_calibration_metric",
    "override_calibration_metric",
    "calibration_delta",
    "baseline_validation_metric",
    "override_validation_metric",
    "validation_delta",
    "baseline_gap",
    "override_gap",
    "gap_delta",
    "priority",
    "protected",
    "improved",
    "protected_degraded",
)


@dataclass(frozen=True)
class ValidationBestFit:
    """Calibration-best validation fit values for one holdout fold."""

    holdout_field: str
    holdout_value: str
    run_index: int
    calibration_metric: float
    validation_metric: float
    generalization_gap: float

    def __post_init__(self) -> None:
        """Validate fold labels and finite metric values."""
        if not self.holdout_field:
            raise ValueError("holdout_field must be non-empty")
        if not self.holdout_value:
            raise ValueError("holdout_value must be non-empty")
        if self.run_index < 0:
            raise ValueError("run_index must be non-negative")
        for field_name in (
            "calibration_metric",
            "validation_metric",
            "generalization_gap",
        ):
            if not isfinite(getattr(self, field_name)):
                raise ValueError(f"{field_name} must be finite")


@dataclass(frozen=True)
class OverrideDeltaRow:
    """One holdout fold compared between baseline and override validations."""

    baseline: ValidationBestFit
    override: ValidationBestFit
    priority: bool = False
    protected: bool = False
    tolerance: float = 0.0

    def __post_init__(self) -> None:
        """Require matching folds and a non-negative comparison tolerance."""
        if self.baseline.holdout_field != self.override.holdout_field:
            raise ValueError("baseline and override holdout fields must match")
        if self.baseline.holdout_value != self.override.holdout_value:
            raise ValueError("baseline and override holdout values must match")
        if self.tolerance < 0:
            raise ValueError("tolerance must be non-negative")

    @property
    def holdout_field(self) -> str:
        """Return the compared holdout field."""
        return self.baseline.holdout_field

    @property
    def holdout_value(self) -> str:
        """Return the compared holdout value."""
        return self.baseline.holdout_value

    @property
    def calibration_delta(self) -> float:
        """Return override minus baseline calibration metric."""
        return self.override.calibration_metric - self.baseline.calibration_metric

    @property
    def validation_delta(self) -> float:
        """Return override minus baseline validation metric."""
        return self.override.validation_metric - self.baseline.validation_metric

    @property
    def gap_delta(self) -> float:
        """Return override minus baseline generalization gap."""
        return self.override.generalization_gap - self.baseline.generalization_gap

    @property
    def improved(self) -> bool:
        """Return whether validation fit improved beyond tolerance."""
        return self.validation_delta < -self.tolerance

    @property
    def protected_degraded(self) -> bool:
        """Return whether a protected fold degraded beyond tolerance."""
        return self.protected and self.validation_delta > self.tolerance


@dataclass(frozen=True)
class OverrideDeltaReport:
    """Override validation comparison rows and review selectors."""

    metric: str
    rows: tuple[OverrideDeltaRow, ...]
    priority_values: tuple[str, ...] = ()
    protected_values: tuple[str, ...] = ()
    tolerance: float = 0.0

    def __post_init__(self) -> None:
        """Validate report shape and metric identity."""
        if self.metric not in FIT_METRICS:
            raise ValueError(f"unsupported fit metric: {self.metric}")
        if not self.rows:
            raise ValueError("override delta report must contain at least one row")
        if self.tolerance < 0:
            raise ValueError("tolerance must be non-negative")
        holdout_fields = {row.holdout_field for row in self.rows}
        if len(holdout_fields) != 1:
            raise ValueError("override delta rows must use one holdout field")

    @property
    def holdout_field(self) -> str:
        """Return the common holdout field for this report."""
        return self.rows[0].holdout_field

    @property
    def mean_validation_delta(self) -> float:
        """Return mean override-minus-baseline validation delta."""
        return sum(row.validation_delta for row in self.rows) / len(self.rows)

    @property
    def worst_validation_delta(self) -> float:
        """Return the largest validation degradation across rows."""
        return max(row.validation_delta for row in self.rows)

    @property
    def priority_mean_delta(self) -> float:
        """Return mean validation delta for selected priority rows."""
        rows = tuple(row for row in self.rows if row.priority)
        if not rows:
            return 0.0
        return sum(row.validation_delta for row in rows) / len(rows)

    @property
    def protected_max_delta(self) -> float:
        """Return the largest validation delta among protected rows."""
        rows = tuple(row for row in self.rows if row.protected)
        if not rows:
            return 0.0
        return max(row.validation_delta for row in rows)

    @property
    def protected_degraded(self) -> bool:
        """Return whether any protected row degraded beyond tolerance."""
        return any(row.protected_degraded for row in self.rows)


def load_override_delta_report(
    baseline_validation_csv: str | Path,
    override_validation_csv: str | Path,
    *,
    metric: str = "root_mean_squared_error",
    priority_values: Iterable[str] = (),
    protected_values: Iterable[str] = (),
    tolerance: float = 0.0,
) -> OverrideDeltaReport:
    """Load two validation CSV files and return a fold-level delta report."""
    baseline = _best_fits_by_holdout(baseline_validation_csv, metric)
    override = _best_fits_by_holdout(override_validation_csv, metric)
    priority_tuple = _normalized_values(priority_values)
    protected_tuple = _normalized_values(protected_values)
    if baseline.keys() != override.keys():
        raise ValueError("baseline and override validation holdouts must match")
    rows = tuple(
        OverrideDeltaRow(
            baseline=baseline[key],
            override=override[key],
            priority=key[1] in priority_tuple,
            protected=key[1] in protected_tuple,
            tolerance=tolerance,
        )
        for key in baseline
    )
    return OverrideDeltaReport(
        metric=metric,
        rows=rows,
        priority_values=priority_tuple,
        protected_values=protected_tuple,
        tolerance=tolerance,
    )


def override_delta_rows(report: OverrideDeltaReport) -> tuple[dict[str, str], ...]:
    """Return override-delta rows as CSV-ready dictionaries."""
    return tuple(_delta_row(row) for row in report.rows)


def override_delta_to_csv(report: OverrideDeltaReport) -> str:
    """Return override-delta rows serialized as CSV text."""
    output = StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=OVERRIDE_DELTA_FIELDS,
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerows(override_delta_rows(report))
    return output.getvalue()


def write_override_delta_csv(report: OverrideDeltaReport, path: str | Path) -> Path:
    """Write override-delta CSV rows and return the output path."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(override_delta_to_csv(report), encoding="utf-8")
    return output_path


def override_delta_markdown(report: OverrideDeltaReport) -> str:
    """Return a Markdown review for validation deltas."""
    output = StringIO()
    output.write("# Override Validation Delta Review\n\n")
    output.write("This report compares calibration-best validation rows before ")
    output.write("and after applying child-region overrides. Negative validation ")
    output.write("deltas indicate improved fit.\n\n")
    output.write(f"- holdout_field: `{report.holdout_field}`\n")
    output.write(f"- metric: `{report.metric}`\n")
    output.write(f"- fold_count: {len(report.rows)}\n")
    output.write(f"- priority_values: `{_joined(report.priority_values)}`\n")
    output.write(f"- protected_values: `{_joined(report.protected_values)}`\n")
    output.write(
        f"- mean_validation_delta: {_value_text(report.mean_validation_delta)}\n"
    )
    output.write(f"- priority_mean_delta: {_value_text(report.priority_mean_delta)}\n")
    output.write(f"- protected_max_delta: {_value_text(report.protected_max_delta)}\n")
    output.write(f"- protected_degraded: {_bool_text(report.protected_degraded)}\n\n")
    output.write("| holdout_value | baseline | override | delta | priority | ")
    output.write("protected | protected_degraded |\n")
    output.write("| --- | ---: | ---: | ---: | --- | --- | --- |\n")
    for row in report.rows:
        output.write(
            f"| {row.holdout_value} | "
            f"{_value_text(row.baseline.validation_metric)} | "
            f"{_value_text(row.override.validation_metric)} | "
            f"{_value_text(row.validation_delta)} | "
            f"{_bool_text(row.priority)} | "
            f"{_bool_text(row.protected)} | "
            f"{_bool_text(row.protected_degraded)} |\n"
        )
    return output.getvalue()


def write_override_delta_markdown(
    report: OverrideDeltaReport, path: str | Path
) -> Path:
    """Write override-delta Markdown and return the output path."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(override_delta_markdown(report), encoding="utf-8")
    return output_path


def _best_fits_by_holdout(
    path: str | Path, metric: str
) -> dict[tuple[str, str], ValidationBestFit]:
    """Return rank-one validation fits keyed by holdout field and value."""
    if metric not in FIT_METRICS:
        raise ValueError(f"unsupported fit metric: {metric}")
    rows = _read_validation_rows(path)
    best_rows: dict[tuple[str, str], ValidationBestFit] = {}
    for row in rows:
        if _int_cell(row, "rank") != 1:
            continue
        best_fit = _best_fit_from_row(row, metric)
        key = (best_fit.holdout_field, best_fit.holdout_value)
        if key in best_rows:
            raise ValueError("validation CSV contains duplicate rank-one holdouts")
        best_rows[key] = best_fit
    if not best_rows:
        raise ValueError("validation CSV must contain rank-one rows")
    return best_rows


def _read_validation_rows(path: str | Path) -> tuple[dict[str, str], ...]:
    """Read validation CSV rows with a header."""
    csv_path = Path(path)
    with csv_path.open(newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        if reader.fieldnames is None:
            raise ValueError("validation CSV must include a header row")
        return tuple(dict(row) for row in reader)


def _best_fit_from_row(row: dict[str, str], metric: str) -> ValidationBestFit:
    """Return one rank-one validation fit from a CSV row."""
    return ValidationBestFit(
        holdout_field=_required_cell(row, "holdout_field"),
        holdout_value=_required_cell(row, "holdout_value"),
        run_index=_int_cell(row, "run_index"),
        calibration_metric=_float_cell(row, f"calibration_{metric}"),
        validation_metric=_float_cell(row, f"validation_{metric}"),
        generalization_gap=_float_cell(row, f"generalization_gap_{metric}"),
    )


def _delta_row(row: OverrideDeltaRow) -> dict[str, str]:
    """Return one override delta as a string-only CSV row."""
    return {
        "holdout_field": row.holdout_field,
        "holdout_value": row.holdout_value,
        "baseline_run_index": str(row.baseline.run_index),
        "override_run_index": str(row.override.run_index),
        "baseline_calibration_metric": _value_text(row.baseline.calibration_metric),
        "override_calibration_metric": _value_text(row.override.calibration_metric),
        "calibration_delta": _value_text(row.calibration_delta),
        "baseline_validation_metric": _value_text(row.baseline.validation_metric),
        "override_validation_metric": _value_text(row.override.validation_metric),
        "validation_delta": _value_text(row.validation_delta),
        "baseline_gap": _value_text(row.baseline.generalization_gap),
        "override_gap": _value_text(row.override.generalization_gap),
        "gap_delta": _value_text(row.gap_delta),
        "priority": _bool_text(row.priority),
        "protected": _bool_text(row.protected),
        "improved": _bool_text(row.improved),
        "protected_degraded": _bool_text(row.protected_degraded),
    }


def _required_cell(row: dict[str, str], field: str) -> str:
    """Return a stripped non-empty CSV cell."""
    value = row.get(field, "").strip()
    if not value:
        raise ValueError(f"validation CSV missing required field: {field}")
    return value


def _float_cell(row: dict[str, str], field: str) -> float:
    """Return one finite numeric CSV cell."""
    try:
        value = float(_required_cell(row, field))
    except ValueError as error:
        raise ValueError(f"validation CSV field must be numeric: {field}") from error
    if not isfinite(value):
        raise ValueError(f"validation CSV field must be finite: {field}")
    return value


def _int_cell(row: dict[str, str], field: str) -> int:
    """Return one non-negative integer CSV cell."""
    try:
        value = int(_required_cell(row, field))
    except ValueError as error:
        raise ValueError(f"validation CSV field must be an integer: {field}") from error
    if value < 0:
        raise ValueError(f"validation CSV field must be non-negative: {field}")
    return value


def _normalized_values(values: Iterable[str]) -> tuple[str, ...]:
    """Return stripped selector values in input order."""
    return tuple(value.strip() for value in values if value.strip())


def _joined(values: Iterable[str]) -> str:
    """Return a compact pipe-delimited selector string."""
    return "|".join(values)


def _bool_text(value: bool) -> str:
    """Return a lower-case boolean string."""
    return "true" if value else "false"


def _value_text(value: float) -> str:
    """Return a stable numeric string for reports."""
    return f"{value:.12g}"
