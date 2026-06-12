"""Reports for sequential ABC-style calibration results."""

from __future__ import annotations

import csv
from io import StringIO
from pathlib import Path

from indoeuropop.analysis.abc_smc import ABCSMCGeneration, ABCSMCResult

ABC_SMC_GENERATION_FIELDS = (
    "generation",
    "seed",
    "candidate_count",
    "accepted_count",
    "acceptance_rate",
    "acceptance_threshold",
    "best_run_index",
    "best_metric_value",
    "fit_metric",
)


def abc_smc_generation_rows(result: ABCSMCResult) -> tuple[dict[str, str], ...]:
    """Return generation-level calibration rows as CSV-ready dictionaries."""
    return tuple(_generation_row(generation) for generation in result.generations)


def abc_smc_generations_to_csv(result: ABCSMCResult) -> str:
    """Return generation-level calibration diagnostics as CSV text."""
    output = StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=ABC_SMC_GENERATION_FIELDS,
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerows(abc_smc_generation_rows(result))
    return output.getvalue()


def write_abc_smc_generations_csv(result: ABCSMCResult, path: str | Path) -> Path:
    """Write generation-level calibration diagnostics and return the path."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(abc_smc_generations_to_csv(result), encoding="utf-8")
    return output_path


def abc_smc_markdown(result: ABCSMCResult) -> str:
    """Return a cautious Markdown report for sequential ABC calibration."""
    output = StringIO()
    output.write("# ABC-SMC Calibration\n\n")
    output.write(
        "This report summarizes a deterministic ABC-SMC-style calibration. "
        "It progressively narrows sampled parameter ranges from accepted "
        "target-fit samples; it is not a fully weighted demographic posterior.\n\n"
    )
    output.write("## Controls\n\n")
    output.write(f"- fit_metric: {result.options.fit_metric}\n")
    output.write(f"- generation_count: {len(result.generations)}\n")
    output.write(f"- total_candidate_count: {result.total_candidate_count}\n")
    output.write(f"- final_accepted_count: {result.final_inference.accepted_count}\n")
    output.write(
        f"- final_acceptance_threshold: "
        f"{result.final_inference.acceptance_threshold:.6g}\n\n"
    )
    output.write("## Generation Thresholds\n\n")
    output.write(
        "| Generation | Seed | Candidates | Accepted | Threshold | Best metric |\n"
    )
    output.write("| ---: | ---: | ---: | ---: | ---: | ---: |\n")
    for generation in result.generations:
        output.write(
            "| "
            f"{generation.generation_index} | "
            f"{generation.spec.seed} | "
            f"{generation.inference.candidate_count} | "
            f"{generation.inference.accepted_count} | "
            f"{generation.acceptance_threshold:.6g} | "
            f"{generation.best_metric_value:.6g} |\n"
        )
    output.write("\n## Final Parameter Summaries\n\n")
    output.write("| Parameter | Mean | Median | 5% interval | 95% interval |\n")
    output.write("| --- | ---: | ---: | ---: | ---: |\n")
    for summary in result.final_inference.parameter_summaries:
        output.write(
            "| "
            f"{summary.parameter} | "
            f"{summary.mean:.6g} | "
            f"{summary.median:.6g} | "
            f"{summary.lower_interval:.6g} | "
            f"{summary.upper_interval:.6g} |\n"
        )
    output.write("\n## Recommended Use\n\n")
    output.write(
        "Use this as a reproducible calibration layer before promoting stronger "
        "claims, adding particle weights, or training an emulator on expanded "
        "proposal regions.\n"
    )
    return output.getvalue()


def write_abc_smc_markdown(result: ABCSMCResult, path: str | Path) -> Path:
    """Write a sequential ABC calibration Markdown report and return the path."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(abc_smc_markdown(result), encoding="utf-8")
    return output_path


def _generation_row(generation: ABCSMCGeneration) -> dict[str, str]:
    """Return one generation-level CSV row."""
    inference = generation.inference
    fit_metric = inference.options.fit_metric
    return {
        "generation": str(generation.generation_index),
        "seed": str(generation.spec.seed),
        "candidate_count": str(inference.candidate_count),
        "accepted_count": str(inference.accepted_count),
        "acceptance_rate": _value_text(inference.acceptance_rate),
        "acceptance_threshold": _value_text(inference.acceptance_threshold),
        "best_run_index": str(inference.best_run.run.index),
        "best_metric_value": _value_text(generation.best_metric_value),
        "fit_metric": fit_metric,
    }


def _value_text(value: float) -> str:
    """Return a stable compact text representation for scalar values."""
    return f"{value:.12g}"
