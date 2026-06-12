"""CSV and Markdown reports for ABC-style rejection inference."""

from __future__ import annotations

import csv
from collections.abc import Iterable
from io import StringIO
from pathlib import Path

from indoeuropop.analysis.inference import (
    ABCRejectionResult,
    PosteriorParameterSummary,
)

POSTERIOR_SUMMARY_FIELDS = (
    "parameter",
    "accepted_count",
    "mean",
    "median",
    "minimum",
    "maximum",
    "lower_interval",
    "upper_interval",
)


def accepted_sample_fieldnames(result: ABCRejectionResult) -> tuple[str, ...]:
    """Return stable CSV field names for accepted inference samples."""
    return (
        "accepted_rank",
        "run_index",
        "fit_metric",
        "fit_metric_value",
        "fit_observation_count",
        *(f"sampled_{name}" for name in _parameter_names(result)),
    )


def accepted_sample_rows(result: ABCRejectionResult) -> tuple[dict[str, str], ...]:
    """Return accepted inference samples as CSV-ready rows."""
    parameter_names = _parameter_names(result)
    return tuple(
        _accepted_sample_row(rank, result, parameter_names)
        for rank, _ in enumerate(result.accepted_runs, start=1)
    )


def accepted_samples_to_csv(result: ABCRejectionResult) -> str:
    """Return accepted inference samples serialized as CSV text."""
    return _rows_to_csv(
        accepted_sample_fieldnames(result), accepted_sample_rows(result)
    )


def write_accepted_samples_csv(result: ABCRejectionResult, path: str | Path) -> Path:
    """Write accepted inference sample rows and return the output path."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(accepted_samples_to_csv(result), encoding="utf-8")
    return output_path


def posterior_summary_rows(
    summaries: Iterable[PosteriorParameterSummary],
) -> tuple[dict[str, str], ...]:
    """Return posterior parameter summaries as CSV-ready rows."""
    return tuple(_summary_row(summary) for summary in summaries)


def posterior_summaries_to_csv(
    summaries: Iterable[PosteriorParameterSummary],
) -> str:
    """Return posterior parameter summaries serialized as CSV text."""
    return _rows_to_csv(POSTERIOR_SUMMARY_FIELDS, posterior_summary_rows(summaries))


def write_posterior_summaries_csv(
    summaries: Iterable[PosteriorParameterSummary], path: str | Path
) -> Path:
    """Write posterior parameter summaries and return the output path."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(posterior_summaries_to_csv(summaries), encoding="utf-8")
    return output_path


def abc_rejection_markdown(result: ABCRejectionResult) -> str:
    """Return a cautious Markdown report for ABC-style rejection inference."""
    output = StringIO()
    output.write("# ABC Rejection Inference\n\n")
    output.write(
        "This report summarizes accepted deterministic sweep samples. It is an "
        "engineering inference scaffold, not a final demographic claim.\n\n"
    )
    output.write("## Acceptance\n\n")
    output.write(f"- fit_metric: {result.options.fit_metric}\n")
    output.write(f"- criterion: {result.options.criterion}\n")
    output.write(f"- candidate_count: {result.candidate_count}\n")
    output.write(f"- accepted_count: {result.accepted_count}\n")
    output.write(f"- acceptance_rate: {result.acceptance_rate:.6f}\n")
    output.write(f"- acceptance_threshold: {result.acceptance_threshold:.6g}\n")
    output.write(f"- best_run_index: {result.best_run.run.index}\n")
    output.write(
        f"- best_{result.options.fit_metric}: "
        f"{result.best_run.metric_value(result.options.fit_metric):.6g}\n\n"
    )
    output.write("## Parameter Summaries\n\n")
    output.write(
        "| Parameter | Mean | Median | Min | Max | 5% interval | 95% interval |\n"
    )
    output.write("| --- | ---: | ---: | ---: | ---: | ---: | ---: |\n")
    for summary in result.parameter_summaries:
        output.write(
            "| "
            f"{summary.parameter} | "
            f"{summary.mean:.6g} | "
            f"{summary.median:.6g} | "
            f"{summary.minimum:.6g} | "
            f"{summary.maximum:.6g} | "
            f"{summary.lower_interval:.6g} | "
            f"{summary.upper_interval:.6g} |\n"
        )
    output.write("\n## Recommended Next Step\n\n")
    output.write(
        "Use this accepted sample set as a regression-checked baseline before "
        "adding sequential ABC rounds, emulator-assisted proposals, or richer "
        "summary statistics.\n"
    )
    return output.getvalue()


def write_abc_rejection_markdown(result: ABCRejectionResult, path: str | Path) -> Path:
    """Write an ABC rejection Markdown report and return the output path."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(abc_rejection_markdown(result), encoding="utf-8")
    return output_path


def _accepted_sample_row(
    accepted_rank: int,
    result: ABCRejectionResult,
    parameter_names: tuple[str, ...],
) -> dict[str, str]:
    """Return one accepted sample row."""
    scored_run = result.accepted_runs[accepted_rank - 1]
    row = {
        "accepted_rank": str(accepted_rank),
        "run_index": str(scored_run.run.index),
        "fit_metric": result.options.fit_metric,
        "fit_metric_value": _value_text(
            scored_run.metric_value(result.options.fit_metric)
        ),
        "fit_observation_count": str(scored_run.fit.observation_count),
    }
    for parameter_name in parameter_names:
        row[f"sampled_{parameter_name}"] = _value_text(
            scored_run.run.sampled_values[parameter_name]
        )
    return row


def _summary_row(summary: PosteriorParameterSummary) -> dict[str, str]:
    """Return one posterior summary row."""
    return {
        "parameter": summary.parameter,
        "accepted_count": str(summary.accepted_count),
        "mean": _value_text(summary.mean),
        "median": _value_text(summary.median),
        "minimum": _value_text(summary.minimum),
        "maximum": _value_text(summary.maximum),
        "lower_interval": _value_text(summary.lower_interval),
        "upper_interval": _value_text(summary.upper_interval),
    }


def _rows_to_csv(fieldnames: tuple[str, ...], rows: Iterable[dict[str, str]]) -> str:
    """Return CSV text for a fixed field list and string-only rows."""
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def _parameter_names(result: ABCRejectionResult) -> tuple[str, ...]:
    """Return sorted accepted sampled parameter names."""
    return tuple(sorted(result.accepted_runs[0].run.sampled_values))


def _value_text(value: float) -> str:
    """Return a stable compact text representation for scalar values."""
    return f"{value:.12g}"
