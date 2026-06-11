"""CSV exports for parameter sweep and sensitivity outputs."""

from __future__ import annotations

import csv
from collections.abc import Iterable
from io import StringIO
from pathlib import Path

from indoeuropop.sensitivity import SensitivityResult
from indoeuropop.summary import TrajectorySummary
from indoeuropop.sweeps import SweepRun

SWEEP_SUMMARY_FIELDS = (
    "source",
    "region",
    "start_bce",
    "end_bce",
    "initial_ancestry",
    "final_ancestry",
    "ancestry_delta",
    "ancestry_slope_per_century",
    "min_total_population",
    "final_total_population",
    "is_extinct",
)

SENSITIVITY_FIELDS = (
    "parameter",
    "outcome",
    "pearson_correlation",
    "spearman_correlation",
    "absolute_spearman",
    "linear_slope",
)


def sweep_run_fieldnames(runs: Iterable[SweepRun]) -> tuple[str, ...]:
    """Return stable CSV field names for sweep-run rows."""
    run_tuple = _validated_sweep_runs(runs)
    parameter_names = _sampled_parameter_names(run_tuple)
    return (
        "index",
        *(f"sampled_{parameter_name}" for parameter_name in parameter_names),
        *(f"summary_{field_name}" for field_name in SWEEP_SUMMARY_FIELDS),
    )


def sweep_run_rows(runs: Iterable[SweepRun]) -> tuple[dict[str, str], ...]:
    """Return sweep runs as string-only rows with stable keys."""
    run_tuple = _validated_sweep_runs(runs)
    parameter_names = _sampled_parameter_names(run_tuple)
    return tuple(_sweep_run_row(run, parameter_names) for run in run_tuple)


def sweep_runs_to_csv(runs: Iterable[SweepRun]) -> str:
    """Return sweep runs serialized as CSV text."""
    run_tuple = _validated_sweep_runs(runs)
    return _rows_to_csv(sweep_run_fieldnames(run_tuple), sweep_run_rows(run_tuple))


def write_sweep_runs_csv(runs: Iterable[SweepRun], path: str | Path) -> Path:
    """Write sweep-run rows to a CSV file and return the path."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(sweep_runs_to_csv(runs), encoding="utf-8")
    return output_path


def sensitivity_result_rows(
    results: Iterable[SensitivityResult],
) -> tuple[dict[str, str], ...]:
    """Return sensitivity results as string-only rows with stable keys."""
    return tuple(_sensitivity_result_row(result) for result in results)


def sensitivity_results_to_csv(results: Iterable[SensitivityResult]) -> str:
    """Return sensitivity results serialized as CSV text."""
    return _rows_to_csv(SENSITIVITY_FIELDS, sensitivity_result_rows(results))


def write_sensitivity_csv(
    results: Iterable[SensitivityResult], path: str | Path
) -> Path:
    """Write sensitivity results to a CSV file and return the path."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(sensitivity_results_to_csv(results), encoding="utf-8")
    return output_path


def _validated_sweep_runs(runs: Iterable[SweepRun]) -> tuple[SweepRun, ...]:
    """Return sweep runs after validating shape consistency."""
    run_tuple = tuple(runs)
    if not run_tuple:
        raise ValueError("runs must contain at least one sweep run")
    parameter_names = _sampled_parameter_names(run_tuple)
    expected = set(parameter_names)
    for run in run_tuple:
        if set(run.sampled_values) != expected:
            raise ValueError("all sweep runs must contain the same sampled parameters")
    return run_tuple


def _sampled_parameter_names(runs: tuple[SweepRun, ...]) -> tuple[str, ...]:
    """Return sorted sampled parameter names for a non-empty run collection."""
    parameter_names = tuple(sorted(runs[0].sampled_values))
    if not parameter_names:
        raise ValueError("sweep runs must contain sampled parameter values")
    return parameter_names


def _sweep_run_row(
    run: SweepRun,
    parameter_names: tuple[str, ...],
) -> dict[str, str]:
    """Return one sweep-run CSV row."""
    row = {"index": str(run.index)}
    for parameter_name in parameter_names:
        row[f"sampled_{parameter_name}"] = _value_text(
            run.sampled_values[parameter_name]
        )
    row.update(_summary_row(run.summary))
    return row


def _summary_row(summary: TrajectorySummary) -> dict[str, str]:
    """Return summary fields with a stable prefix for CSV rows."""
    return {
        "summary_source": summary.source,
        "summary_region": summary.region or "all",
        "summary_start_bce": _value_text(summary.start_bce),
        "summary_end_bce": _value_text(summary.end_bce),
        "summary_initial_ancestry": _value_text(summary.initial_ancestry),
        "summary_final_ancestry": _value_text(summary.final_ancestry),
        "summary_ancestry_delta": _value_text(summary.ancestry_delta),
        "summary_ancestry_slope_per_century": _value_text(
            summary.ancestry_slope_per_century
        ),
        "summary_min_total_population": _value_text(summary.min_total_population),
        "summary_final_total_population": _value_text(summary.final_total_population),
        "summary_is_extinct": _value_text(summary.is_extinct),
    }


def _sensitivity_result_row(result: SensitivityResult) -> dict[str, str]:
    """Return one sensitivity-result CSV row."""
    return {
        "parameter": result.parameter,
        "outcome": result.outcome,
        "pearson_correlation": _value_text(result.pearson_correlation),
        "spearman_correlation": _value_text(result.spearman_correlation),
        "absolute_spearman": _value_text(result.absolute_spearman),
        "linear_slope": _value_text(result.linear_slope),
    }


def _rows_to_csv(fieldnames: tuple[str, ...], rows: Iterable[dict[str, str]]) -> str:
    """Return rows as CSV text with stable line endings."""
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def _value_text(value: bool | float) -> str:
    """Return a stable string representation for numeric and boolean values."""
    if isinstance(value, bool):
        return "true" if value else "false"
    return f"{value:.12g}"
