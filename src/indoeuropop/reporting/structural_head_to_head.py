"""Reports for same-baseline structural candidate comparisons."""

from __future__ import annotations

from io import StringIO
from pathlib import Path

from indoeuropop.analysis.child_region_candidates import ChildRegionCandidate
from indoeuropop.analysis.posterior_predictive import (
    PosteriorPredictiveDiagnostics,
    PosteriorPredictiveObservation,
)
from indoeuropop.analysis.structural_candidates import PosteriorPredictiveMetricDelta
from indoeuropop.analysis.structural_head_to_head import (
    StructuredPulseCandidate,
    better_root_mean_squared_error_delta,
)
from indoeuropop.data.target_notes import target_note_metadata


def structured_head_to_head_markdown(
    pulse_candidate: StructuredPulseCandidate,
    pulse_region_count: int,
    child_candidate: ChildRegionCandidate,
    baseline: PosteriorPredictiveDiagnostics,
    pulse_diagnostics: PosteriorPredictiveDiagnostics,
    child_diagnostics: PosteriorPredictiveDiagnostics,
    pulse_delta: PosteriorPredictiveMetricDelta,
    child_delta: PosteriorPredictiveMetricDelta,
) -> str:
    """Return a Markdown report for a same-baseline structural comparison."""
    focus_index = pulse_delta.focus_observation_index
    baseline_focus = baseline.observations[focus_index]
    pulse_focus = pulse_diagnostics.observations[focus_index]
    child_focus = child_diagnostics.observations[focus_index]
    output = StringIO()
    output.write("# Structured Candidate Head-To-Head\n\n")
    output.write(
        "This report compares a structured broad-pulse candidate and a "
        "child-region override candidate against the same structured baseline. "
        "It is a diagnostic promotion gate, not a historical conclusion.\n\n"
    )
    output.write(
        _candidate_section(pulse_candidate, pulse_region_count, child_candidate)
    )
    output.write(_metric_table(baseline, pulse_diagnostics, child_diagnostics))
    output.write(_delta_section(pulse_delta, child_delta))
    output.write(_focus_section(baseline_focus, pulse_focus, child_focus, child_delta))
    output.write("## Gate Interpretation\n\n")
    preferred_candidate = _preferred_candidate(pulse_delta, child_delta)
    output.write(f"- rmse_preferred_candidate: {preferred_candidate}\n")
    output.write(
        "- same_baseline: true\n"
        "- guardrail: promote only after reviewing target grouping, chronology, "
        "qpAdm uncertainty, and protected-region validation behavior.\n"
    )
    return output.getvalue()


def write_structured_head_to_head_markdown(
    pulse_candidate: StructuredPulseCandidate,
    pulse_region_count: int,
    child_candidate: ChildRegionCandidate,
    baseline: PosteriorPredictiveDiagnostics,
    pulse_diagnostics: PosteriorPredictiveDiagnostics,
    child_diagnostics: PosteriorPredictiveDiagnostics,
    pulse_delta: PosteriorPredictiveMetricDelta,
    child_delta: PosteriorPredictiveMetricDelta,
    path: str | Path,
) -> Path:
    """Write a same-baseline structural comparison report and return the path."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        structured_head_to_head_markdown(
            pulse_candidate,
            pulse_region_count,
            child_candidate,
            baseline,
            pulse_diagnostics,
            child_diagnostics,
            pulse_delta,
            child_delta,
        ),
        encoding="utf-8",
    )
    return output_path


def _candidate_section(
    pulse_candidate: StructuredPulseCandidate,
    pulse_region_count: int,
    child_candidate: ChildRegionCandidate,
) -> str:
    """Return Markdown describing both structural candidates."""
    output = StringIO()
    output.write("## Candidates\n\n")
    output.write(f"- structured_pulse_name: {pulse_candidate.name}\n")
    output.write(f"- structured_pulse_region_prefix: {pulse_candidate.region_prefix}\n")
    output.write(f"- structured_pulse_region_count: {pulse_region_count}\n")
    output.write(f"- structured_pulse_start_bce: {pulse_candidate.start_bce:.6g}\n")
    output.write(f"- structured_pulse_end_bce: {pulse_candidate.end_bce:.6g}\n")
    output.write(f"- structured_pulse_annual_rate: {pulse_candidate.annual_rate:.6g}\n")
    output.write(f"- child_candidate_name: {child_candidate.name}\n")
    output.write(f"- child_override_path: {child_candidate.override_path}\n")
    output.write(
        f"- child_overridden_region_count: {child_candidate.overridden_region_count}\n"
    )
    output.write(
        f"- child_migration_pulse_count: {child_candidate.migration_pulse_count}\n\n"
    )
    return output.getvalue()


def _metric_table(
    baseline: PosteriorPredictiveDiagnostics,
    pulse: PosteriorPredictiveDiagnostics,
    child: PosteriorPredictiveDiagnostics,
) -> str:
    """Return the same-baseline aggregate diagnostics table."""
    output = StringIO()
    output.write("## Aggregate Diagnostics\n\n")
    output.write(
        "| Metric | Baseline | Structured pulse | Child override | "
        "Pulse - baseline | Child - baseline |\n"
        "| --- | ---: | ---: | ---: | ---: | ---: |\n"
    )
    output.write(
        _metric_row(
            "coverage_rate",
            baseline.coverage_rate,
            pulse.coverage_rate,
            child.coverage_rate,
        )
    )
    output.write(
        _metric_row(
            "mean_absolute_error",
            baseline.mean_absolute_error,
            pulse.mean_absolute_error,
            child.mean_absolute_error,
        )
    )
    output.write(
        _metric_row(
            "root_mean_squared_error",
            baseline.root_mean_squared_error,
            pulse.root_mean_squared_error,
            child.root_mean_squared_error,
        )
    )
    output.write(
        _metric_row(
            "max_abs_z_score",
            baseline.max_abs_z_score,
            pulse.max_abs_z_score,
            child.max_abs_z_score,
        )
    )
    output.write("\n")
    return output.getvalue()


def _delta_section(
    pulse_delta: PosteriorPredictiveMetricDelta,
    child_delta: PosteriorPredictiveMetricDelta,
) -> str:
    """Return direct candidate-minus-baseline deltas."""
    output = StringIO()
    rmse_delta_gap = (
        child_delta.root_mean_squared_error_delta
        - pulse_delta.root_mean_squared_error_delta
    )
    output.write("## Candidate Deltas\n\n")
    output.write(
        "- structured_pulse_rmse_delta: "
        f"{pulse_delta.root_mean_squared_error_delta:.6g}\n"
    )
    output.write(
        "- child_override_rmse_delta: "
        f"{child_delta.root_mean_squared_error_delta:.6g}\n"
    )
    output.write(f"- child_minus_pulse_rmse_delta: {rmse_delta_gap:.6g}\n")
    output.write(
        f"- structured_pulse_coverage_delta: {pulse_delta.coverage_rate_delta:.6g}\n"
    )
    output.write(
        f"- child_override_coverage_delta: {child_delta.coverage_rate_delta:.6g}\n"
    )
    output.write(
        "- structured_pulse_focus_residual_delta: "
        f"{pulse_delta.focus_residual_delta:.6g}\n"
    )
    output.write(
        "- child_override_focus_residual_delta: "
        f"{child_delta.focus_residual_delta:.6g}\n\n"
    )
    return output.getvalue()


def _focus_section(
    baseline: PosteriorPredictiveObservation,
    pulse: PosteriorPredictiveObservation,
    child: PosteriorPredictiveObservation,
    child_delta: PosteriorPredictiveMetricDelta,
) -> str:
    """Return the focus-target side-by-side section."""
    output = StringIO()
    output.write("## Focus Observation\n\n")
    output.write(f"- observation_index: {child_delta.focus_observation_index}\n")
    output.write(_focus_metadata_lines(baseline))
    output.write(f"- observed_mean: {baseline.observation.mean:.6g}\n")
    output.write(f"- baseline_prediction_mean: {baseline.prediction_mean:.6g}\n")
    output.write(f"- structured_pulse_prediction_mean: {pulse.prediction_mean:.6g}\n")
    output.write(f"- child_override_prediction_mean: {child.prediction_mean:.6g}\n")
    output.write(f"- baseline_residual: {baseline.mean_residual:.6g}\n")
    output.write(f"- structured_pulse_residual: {pulse.mean_residual:.6g}\n")
    output.write(f"- child_override_residual: {child.mean_residual:.6g}\n\n")
    return output.getvalue()


def _metric_row(name: str, baseline: float, pulse: float, child: float) -> str:
    """Return one aggregate metric row."""
    return (
        f"| {name} | {baseline:.6g} | {pulse:.6g} | {child:.6g} | "
        f"{pulse - baseline:.6g} | {child - baseline:.6g} |\n"
    )


def _preferred_candidate(
    pulse_delta: PosteriorPredictiveMetricDelta,
    child_delta: PosteriorPredictiveMetricDelta,
) -> str:
    """Return the report label for the stronger RMSE-improvement signal."""
    winner = better_root_mean_squared_error_delta(
        pulse_delta.root_mean_squared_error_delta,
        child_delta.root_mean_squared_error_delta,
    )
    if winner == "left":
        return "structured_pulse"
    if winner == "right":
        return "child_override"
    return "tie"


def _focus_metadata_lines(observation: PosteriorPredictiveObservation) -> str:
    """Return human-readable lines for focus target identity metadata."""
    target = observation.observation
    metadata = target_note_metadata(target.note)
    lines = [
        f"- region: {target.region}\n",
        f"- source: {target.source}\n",
        f"- time_bce: {target.time_bce:.6g}\n",
    ]
    for key in ("requested_group_id", "target_id", "parent_region"):
        value = metadata.get(key, "")
        if value:
            lines.append(f"- {key}: {value}\n")
    return "".join(lines)
