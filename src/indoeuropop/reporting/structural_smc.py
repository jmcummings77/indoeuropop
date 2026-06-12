"""Reports for SMC-based structural candidate comparisons."""

from __future__ import annotations

from io import StringIO
from pathlib import Path

from indoeuropop.analysis.child_region_candidates import ChildRegionCandidate
from indoeuropop.analysis.structural_candidates import PosteriorPredictiveMetricDelta
from indoeuropop.analysis.structural_head_to_head import (
    StructuredPulseCandidate,
    better_root_mean_squared_error_delta,
)
from indoeuropop.orchestration.abc_smc import ABCSMCWorkflowResult


def structural_smc_markdown(
    pulse_candidate: StructuredPulseCandidate,
    pulse_region_count: int,
    child_candidate: ChildRegionCandidate,
    baseline: ABCSMCWorkflowResult,
    pulse: ABCSMCWorkflowResult,
    child: ABCSMCWorkflowResult,
    pulse_delta: PosteriorPredictiveMetricDelta,
    child_delta: PosteriorPredictiveMetricDelta,
    pulse_holdout_delta: PosteriorPredictiveMetricDelta | None = None,
    child_holdout_delta: PosteriorPredictiveMetricDelta | None = None,
) -> str:
    """Return a Markdown report for a structural SMC comparison."""
    output = StringIO()
    output.write("# Structural ABC-SMC Head-To-Head\n\n")
    output.write(
        "This report compares structured broad-pulse and child-region override "
        "hypotheses after calibrating each model with the same SMC controls. "
        "It is an engineering diagnostic, not a final historical claim.\n\n"
    )
    output.write(
        _candidate_section(pulse_candidate, pulse_region_count, child_candidate)
    )
    output.write(_smc_table(baseline, pulse, child))
    output.write(_calibration_metric_table(baseline, pulse, child))
    output.write(_delta_section("Calibration Deltas", pulse_delta, child_delta))
    if pulse_holdout_delta is not None and child_holdout_delta is not None:
        output.write(_holdout_metric_table(baseline, pulse, child))
        output.write(
            _delta_section("Holdout Deltas", pulse_holdout_delta, child_holdout_delta)
        )
    output.write("## Gate Interpretation\n\n")
    output.write(
        "- calibration_rmse_preferred_candidate: "
        f"{_preferred(pulse_delta, child_delta)}\n"
    )
    if pulse_holdout_delta is not None and child_holdout_delta is not None:
        output.write(
            "- holdout_rmse_preferred_candidate: "
            f"{_preferred(pulse_holdout_delta, child_holdout_delta)}\n"
        )
    output.write(
        "- guardrail: compare this with target chronology, qpAdm review, and "
        "protected-region validation before promoting a structural hypothesis.\n"
    )
    return output.getvalue()


def write_structural_smc_markdown(
    pulse_candidate: StructuredPulseCandidate,
    pulse_region_count: int,
    child_candidate: ChildRegionCandidate,
    baseline: ABCSMCWorkflowResult,
    pulse: ABCSMCWorkflowResult,
    child: ABCSMCWorkflowResult,
    pulse_delta: PosteriorPredictiveMetricDelta,
    child_delta: PosteriorPredictiveMetricDelta,
    pulse_holdout_delta: PosteriorPredictiveMetricDelta | None,
    child_holdout_delta: PosteriorPredictiveMetricDelta | None,
    path: str | Path,
) -> Path:
    """Write a structural SMC comparison report and return the path."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        structural_smc_markdown(
            pulse_candidate,
            pulse_region_count,
            child_candidate,
            baseline,
            pulse,
            child,
            pulse_delta,
            child_delta,
            pulse_holdout_delta,
            child_holdout_delta,
        ),
        encoding="utf-8",
    )
    return output_path


def _candidate_section(
    pulse_candidate: StructuredPulseCandidate,
    pulse_region_count: int,
    child_candidate: ChildRegionCandidate,
) -> str:
    """Return Markdown describing compared structural candidates."""
    return (
        "## Candidates\n\n"
        f"- structured_pulse_name: {pulse_candidate.name}\n"
        f"- structured_pulse_region_prefix: {pulse_candidate.region_prefix}\n"
        f"- structured_pulse_region_count: {pulse_region_count}\n"
        f"- structured_pulse_start_bce: {pulse_candidate.start_bce:.6g}\n"
        f"- structured_pulse_end_bce: {pulse_candidate.end_bce:.6g}\n"
        f"- structured_pulse_annual_rate: {pulse_candidate.annual_rate:.6g}\n"
        f"- child_candidate_name: {child_candidate.name}\n"
        f"- child_override_path: {child_candidate.override_path}\n"
        f"- child_overridden_region_count: {child_candidate.overridden_region_count}\n"
        f"- child_migration_pulse_count: {child_candidate.migration_pulse_count}\n\n"
    )


def _smc_table(
    baseline: ABCSMCWorkflowResult,
    pulse: ABCSMCWorkflowResult,
    child: ABCSMCWorkflowResult,
) -> str:
    """Return a table of SMC generation thresholds."""
    output = StringIO()
    output.write("## SMC Calibration\n\n")
    output.write(
        "| Model | Generations | Candidates | Accepted | Threshold schedule |\n"
    )
    output.write("| --- | ---: | ---: | ---: | --- |\n")
    output.write(_smc_row("baseline", baseline))
    output.write(_smc_row("structured_pulse", pulse))
    output.write(_smc_row("child_override", child))
    output.write("\n")
    return output.getvalue()


def _calibration_metric_table(
    baseline: ABCSMCWorkflowResult,
    pulse: ABCSMCWorkflowResult,
    child: ABCSMCWorkflowResult,
) -> str:
    """Return calibration posterior predictive aggregate metrics."""
    assert baseline.posterior_predictive is not None
    assert pulse.posterior_predictive is not None
    assert child.posterior_predictive is not None
    return _metric_table(
        "Calibration Posterior Predictive",
        baseline.posterior_predictive,
        pulse.posterior_predictive,
        child.posterior_predictive,
    )


def _holdout_metric_table(
    baseline: ABCSMCWorkflowResult,
    pulse: ABCSMCWorkflowResult,
    child: ABCSMCWorkflowResult,
) -> str:
    """Return holdout posterior predictive aggregate metrics."""
    assert baseline.holdout_posterior_predictive is not None
    assert pulse.holdout_posterior_predictive is not None
    assert child.holdout_posterior_predictive is not None
    return _metric_table(
        "Holdout Posterior Predictive",
        baseline.holdout_posterior_predictive,
        pulse.holdout_posterior_predictive,
        child.holdout_posterior_predictive,
    )


def _metric_table(title: str, baseline: object, pulse: object, child: object) -> str:
    """Return a posterior predictive aggregate metric table."""
    output = StringIO()
    output.write(f"## {title}\n\n")
    output.write("| Metric | Baseline | Structured pulse | Child override |\n")
    output.write("| --- | ---: | ---: | ---: |\n")
    for metric in (
        "coverage_rate",
        "mean_absolute_error",
        "root_mean_squared_error",
        "max_abs_z_score",
    ):
        output.write(
            f"| {metric} | {getattr(baseline, metric):.6g} | "
            f"{getattr(pulse, metric):.6g} | {getattr(child, metric):.6g} |\n"
        )
    output.write("\n")
    return output.getvalue()


def _delta_section(
    title: str,
    pulse_delta: PosteriorPredictiveMetricDelta,
    child_delta: PosteriorPredictiveMetricDelta,
) -> str:
    """Return direct candidate-minus-baseline deltas."""
    rmse_delta_gap = (
        child_delta.root_mean_squared_error_delta
        - pulse_delta.root_mean_squared_error_delta
    )
    return (
        f"## {title}\n\n"
        "- structured_pulse_rmse_delta: "
        f"{pulse_delta.root_mean_squared_error_delta:.6g}\n"
        "- child_override_rmse_delta: "
        f"{child_delta.root_mean_squared_error_delta:.6g}\n"
        f"- child_minus_pulse_rmse_delta: {rmse_delta_gap:.6g}\n"
        f"- structured_pulse_coverage_delta: {pulse_delta.coverage_rate_delta:.6g}\n"
        f"- child_override_coverage_delta: {child_delta.coverage_rate_delta:.6g}\n\n"
    )


def _smc_row(label: str, result: ABCSMCWorkflowResult) -> str:
    """Return one SMC table row."""
    inference = result.inference
    thresholds = ", ".join(f"{value:.6g}" for value in inference.threshold_schedule)
    return (
        f"| {label} | {len(inference.generations)} | "
        f"{inference.total_candidate_count} | "
        f"{inference.final_inference.accepted_count} | {thresholds} |\n"
    )


def _preferred(
    pulse_delta: PosteriorPredictiveMetricDelta,
    child_delta: PosteriorPredictiveMetricDelta,
) -> str:
    """Return the label with the stronger RMSE-improvement signal."""
    winner = better_root_mean_squared_error_delta(
        pulse_delta.root_mean_squared_error_delta,
        child_delta.root_mean_squared_error_delta,
    )
    if winner == "left":
        return "structured_pulse"
    if winner == "right":
        return "child_override"
    return "tie"
