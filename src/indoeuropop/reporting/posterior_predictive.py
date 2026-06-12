"""Reports and plots for posterior predictive diagnostics."""

from __future__ import annotations

import csv
from collections.abc import Iterable
from io import StringIO
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.figure import Figure

from indoeuropop.analysis.posterior_predictive import (
    PosteriorPredictiveDiagnostics,
    PosteriorPredictiveObservation,
)

POSTERIOR_PREDICTIVE_FIELDS = (
    "observation_index",
    "region",
    "source",
    "time_bce",
    "observed_mean",
    "observed_uncertainty",
    "prediction_mean",
    "prediction_median",
    "prediction_minimum",
    "prediction_maximum",
    "lower_interval",
    "upper_interval",
    "mean_residual",
    "absolute_mean_residual",
    "mean_z_score",
    "observed_inside_interval",
    "citation_key",
)


def posterior_predictive_rows(
    diagnostics: PosteriorPredictiveDiagnostics,
) -> tuple[dict[str, str], ...]:
    """Return posterior predictive diagnostics as CSV-ready rows."""
    return tuple(
        _posterior_predictive_row(observation)
        for observation in diagnostics.observations
    )


def posterior_predictive_to_csv(
    diagnostics: PosteriorPredictiveDiagnostics,
) -> str:
    """Return posterior predictive diagnostics serialized as CSV text."""
    return _rows_to_csv(
        POSTERIOR_PREDICTIVE_FIELDS, posterior_predictive_rows(diagnostics)
    )


def write_posterior_predictive_csv(
    diagnostics: PosteriorPredictiveDiagnostics,
    path: str | Path,
) -> Path:
    """Write posterior predictive diagnostic rows and return the output path."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(posterior_predictive_to_csv(diagnostics), encoding="utf-8")
    return output_path


def posterior_predictive_markdown(
    diagnostics: PosteriorPredictiveDiagnostics,
    *,
    title: str = "Posterior Predictive Diagnostics",
) -> str:
    """Return a Markdown report for posterior predictive diagnostics."""
    worst = diagnostics.worst_observation
    output = StringIO()
    output.write(f"# {title}\n\n")
    output.write(
        "This report compares target observations with the predictive envelope "
        "from accepted ABC rejection samples. It is a diagnostic summary, not a "
        "final demographic inference.\n\n"
    )
    output.write("## Summary\n\n")
    output.write(f"- observation_count: {diagnostics.observation_count}\n")
    output.write(f"- accepted_count: {diagnostics.accepted_count}\n")
    output.write(f"- interval_probability: {diagnostics.interval_probability:.6g}\n")
    output.write(f"- coverage_count: {diagnostics.coverage_count}\n")
    output.write(f"- coverage_rate: {diagnostics.coverage_rate:.6f}\n")
    output.write(f"- mean_absolute_error: {diagnostics.mean_absolute_error:.6g}\n")
    output.write(
        f"- root_mean_squared_error: {diagnostics.root_mean_squared_error:.6g}\n"
    )
    output.write(f"- max_abs_z_score: {diagnostics.max_abs_z_score:.6g}\n\n")
    output.write("## Worst Mean Residual\n\n")
    output.write(f"- observation_index: {worst.observation_index}\n")
    output.write(f"- region: {worst.observation.region}\n")
    output.write(f"- source: {worst.observation.source}\n")
    output.write(f"- time_bce: {worst.observation.time_bce:.6g}\n")
    output.write(f"- observed_mean: {worst.observation.mean:.6g}\n")
    output.write(f"- prediction_mean: {worst.prediction_mean:.6g}\n")
    output.write(f"- mean_residual: {worst.mean_residual:.6g}\n\n")
    interval_label = f"{diagnostics.interval_probability:.0%}"
    output.write("## Observation Diagnostics\n\n")
    output.write(
        "| Index | Region | Source | Time BCE | Observed | Predictive mean | "
        f"{interval_label} lower | {interval_label} upper | "
        "Mean residual | Inside interval |\n"
    )
    output.write(
        "| ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |\n"
    )
    for observation in diagnostics.observations:
        output.write(_markdown_observation_row(observation))
    return output.getvalue()


def write_posterior_predictive_markdown(
    diagnostics: PosteriorPredictiveDiagnostics,
    path: str | Path,
    *,
    title: str = "Posterior Predictive Diagnostics",
) -> Path:
    """Write a posterior predictive Markdown report and return the output path."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        posterior_predictive_markdown(diagnostics, title=title),
        encoding="utf-8",
    )
    return output_path


def plot_posterior_predictive_diagnostics(
    diagnostics: PosteriorPredictiveDiagnostics,
) -> Figure:
    """Create a posterior predictive envelope and residual diagnostic figure."""
    indexes = [
        observation.observation_index for observation in diagnostics.observations
    ]
    observed = [
        observation.observation.mean for observation in diagnostics.observations
    ]
    uncertainty = [
        observation.observation.uncertainty for observation in diagnostics.observations
    ]
    predicted = [
        observation.prediction_mean for observation in diagnostics.observations
    ]
    lower_errors = [
        observation.prediction_mean - observation.lower_interval
        for observation in diagnostics.observations
    ]
    upper_errors = [
        observation.upper_interval - observation.prediction_mean
        for observation in diagnostics.observations
    ]
    residuals = [observation.mean_residual for observation in diagnostics.observations]

    figure, (fit_axis, residual_axis) = plt.subplots(
        2,
        1,
        figsize=(10, 7),
        sharex=True,
        gridspec_kw={"height_ratios": [2, 1]},
    )
    fit_axis.errorbar(
        indexes,
        observed,
        yerr=uncertainty,
        fmt="s",
        capsize=3,
        label="observed target",
    )
    fit_axis.errorbar(
        indexes,
        predicted,
        yerr=[lower_errors, upper_errors],
        fmt="o",
        capsize=3,
        label="accepted predictive mean and interval",
    )
    fit_axis.set_ylabel("Ancestry proportion")
    fit_axis.set_ylim(0.0, 1.0)
    fit_axis.grid(alpha=0.3)
    fit_axis.legend()

    residual_axis.axhline(0.0, color="black", linewidth=1)
    residual_axis.bar(indexes, residuals)
    residual_axis.set_xlabel("Target observation index")
    residual_axis.set_ylabel("Mean residual")
    residual_axis.grid(alpha=0.3)
    figure.tight_layout()
    return figure


def write_posterior_predictive_plot(
    diagnostics: PosteriorPredictiveDiagnostics,
    path: str | Path,
) -> Path:
    """Write a posterior predictive diagnostic plot and return the path."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure = plot_posterior_predictive_diagnostics(diagnostics)
    figure.savefig(output_path)
    plt.close(figure)
    return output_path


def _posterior_predictive_row(
    observation: PosteriorPredictiveObservation,
) -> dict[str, str]:
    """Return one posterior predictive observation as string-only fields."""
    target = observation.observation
    return {
        "observation_index": str(observation.observation_index),
        "region": target.region,
        "source": target.source,
        "time_bce": _value_text(target.time_bce),
        "observed_mean": _value_text(target.mean),
        "observed_uncertainty": _value_text(target.uncertainty),
        "prediction_mean": _value_text(observation.prediction_mean),
        "prediction_median": _value_text(observation.prediction_median),
        "prediction_minimum": _value_text(observation.prediction_minimum),
        "prediction_maximum": _value_text(observation.prediction_maximum),
        "lower_interval": _value_text(observation.lower_interval),
        "upper_interval": _value_text(observation.upper_interval),
        "mean_residual": _value_text(observation.mean_residual),
        "absolute_mean_residual": _value_text(observation.absolute_mean_residual),
        "mean_z_score": _value_text(observation.mean_z_score),
        "observed_inside_interval": _value_text(observation.observed_inside_interval),
        "citation_key": target.citation_key,
    }


def _markdown_observation_row(
    observation: PosteriorPredictiveObservation,
) -> str:
    """Return one Markdown table row for a predictive observation."""
    target = observation.observation
    inside_text = "true" if observation.observed_inside_interval else "false"
    return (
        f"| {observation.observation_index} | {target.region} | {target.source} | "
        f"{target.time_bce:.6g} | {target.mean:.6g} | "
        f"{observation.prediction_mean:.6g} | {observation.lower_interval:.6g} | "
        f"{observation.upper_interval:.6g} | {observation.mean_residual:.6g} | "
        f"{inside_text} |\n"
    )


def _rows_to_csv(fieldnames: tuple[str, ...], rows: Iterable[dict[str, str]]) -> str:
    """Return CSV text for a fixed field list and string-only rows."""
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def _value_text(value: bool | float) -> str:
    """Return a stable scalar text representation."""
    if isinstance(value, bool):
        return str(value).lower()
    return f"{value:.12g}"
