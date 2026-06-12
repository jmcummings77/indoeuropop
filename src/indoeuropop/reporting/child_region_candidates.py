"""Reports for child-region structural candidate diagnostics."""

from __future__ import annotations

from io import StringIO
from pathlib import Path

from indoeuropop.analysis.child_region_candidates import (
    ChildRegionCandidate,
    StructuralComparisonReference,
    root_mean_squared_error_advantage,
)
from indoeuropop.analysis.posterior_predictive import (
    PosteriorPredictiveDiagnostics,
    PosteriorPredictiveObservation,
)
from indoeuropop.analysis.structural_candidates import PosteriorPredictiveMetricDelta
from indoeuropop.data.target_notes import target_note_metadata


def child_region_candidate_markdown(
    candidate: ChildRegionCandidate,
    baseline: PosteriorPredictiveDiagnostics,
    candidate_diagnostics: PosteriorPredictiveDiagnostics,
    delta: PosteriorPredictiveMetricDelta,
    *,
    reference: StructuralComparisonReference | None = None,
) -> str:
    """Return a Markdown report comparing child-region candidate fit."""
    baseline_focus = baseline.observations[delta.focus_observation_index]
    candidate_focus = candidate_diagnostics.observations[delta.focus_observation_index]
    output = StringIO()
    output.write(f"# Child-Region Candidate: {candidate.name}\n\n")
    output.write(
        "This report compares posterior predictive diagnostics before and after "
        "applying target-aligned child-region overrides. It is a model-structure "
        "diagnostic, not evidence that the override describes the true "
        "demographic process.\n\n"
    )
    output.write("## Candidate\n\n")
    output.write(f"- override_path: {candidate.override_path or 'in-memory'}\n")
    output.write(f"- overridden_region_count: {candidate.overridden_region_count}\n")
    output.write(f"- migration_pulse_count: {candidate.migration_pulse_count}\n\n")
    output.write(_aggregate_table(baseline, candidate_diagnostics, delta))
    output.write(_focus_section(baseline_focus, candidate_focus, delta))
    if reference is not None:
        output.write(_reference_section(delta, reference))
    output.write("## Interpretation Guardrail\n\n")
    output.write(
        "Prefer this candidate only if it improves the target-specific failure "
        "without merely moving error into protected regions. When compared with "
        "a broad-region pulse, remember that improvement deltas can use different "
        "baselines and should be followed by a direct head-to-head validation run.\n"
    )
    return output.getvalue()


def write_child_region_candidate_markdown(
    candidate: ChildRegionCandidate,
    baseline: PosteriorPredictiveDiagnostics,
    candidate_diagnostics: PosteriorPredictiveDiagnostics,
    delta: PosteriorPredictiveMetricDelta,
    path: str | Path,
    *,
    reference: StructuralComparisonReference | None = None,
) -> Path:
    """Write a child-region candidate Markdown report and return the path."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        child_region_candidate_markdown(
            candidate,
            baseline,
            candidate_diagnostics,
            delta,
            reference=reference,
        ),
        encoding="utf-8",
    )
    return output_path


def _aggregate_table(
    baseline: PosteriorPredictiveDiagnostics,
    candidate: PosteriorPredictiveDiagnostics,
    delta: PosteriorPredictiveMetricDelta,
) -> str:
    """Return the aggregate diagnostics Markdown table."""
    output = StringIO()
    output.write("## Aggregate Diagnostics\n\n")
    output.write(
        "| Metric | Baseline | Candidate | Candidate - baseline |\n"
        "| --- | ---: | ---: | ---: |\n"
    )
    output.write(
        _metric_row("coverage_rate", baseline.coverage_rate, candidate.coverage_rate)
    )
    output.write(
        _metric_row(
            "mean_absolute_error",
            baseline.mean_absolute_error,
            candidate.mean_absolute_error,
        )
    )
    output.write(
        _metric_row(
            "root_mean_squared_error",
            baseline.root_mean_squared_error,
            candidate.root_mean_squared_error,
        )
    )
    output.write(
        _metric_row(
            "max_abs_z_score", baseline.max_abs_z_score, candidate.max_abs_z_score
        )
    )
    output.write(
        f"\n- coverage_rate_delta: {delta.coverage_rate_delta:.6g}\n"
        f"- mean_absolute_error_delta: {delta.mean_absolute_error_delta:.6g}\n"
        f"- root_mean_squared_error_delta: "
        f"{delta.root_mean_squared_error_delta:.6g}\n"
        f"- max_abs_z_score_delta: {delta.max_abs_z_score_delta:.6g}\n\n"
    )
    return output.getvalue()


def _focus_section(
    baseline_focus: PosteriorPredictiveObservation,
    candidate_focus: PosteriorPredictiveObservation,
    delta: PosteriorPredictiveMetricDelta,
) -> str:
    """Return the focus observation report section."""
    output = StringIO()
    output.write("## Focus Observation\n\n")
    output.write(f"- observation_index: {delta.focus_observation_index}\n")
    output.write(_focus_metadata_lines(baseline_focus))
    output.write(f"- baseline_prediction_mean: {baseline_focus.prediction_mean:.6g}\n")
    output.write(
        f"- candidate_prediction_mean: {candidate_focus.prediction_mean:.6g}\n"
    )
    output.write(f"- observed_mean: {baseline_focus.observation.mean:.6g}\n")
    output.write(f"- baseline_residual: {baseline_focus.mean_residual:.6g}\n")
    output.write(f"- candidate_residual: {candidate_focus.mean_residual:.6g}\n")
    output.write(f"- absolute_residual_delta: {delta.focus_residual_delta:.6g}\n\n")
    return output.getvalue()


def _reference_section(
    delta: PosteriorPredictiveMetricDelta,
    reference: StructuralComparisonReference,
) -> str:
    """Return a broad-reference comparison section."""
    rmse_advantage = root_mean_squared_error_advantage(
        delta.root_mean_squared_error_delta, reference
    )
    output = StringIO()
    output.write("## Reference Candidate Comparison\n\n")
    output.write(f"- reference_name: {reference.name}\n")
    output.write(
        f"- reference_root_mean_squared_error_delta: "
        f"{reference.root_mean_squared_error_delta:.6g}\n"
    )
    output.write(
        f"- child_minus_reference_root_mean_squared_error_delta: "
        f"{rmse_advantage:.6g}\n"
    )
    output.write(f"- reference_coverage_delta: {reference.coverage_rate_delta:.6g}\n")
    output.write(f"- child_coverage_delta: {delta.coverage_rate_delta:.6g}\n")
    output.write(
        f"- reference_focus_residual_delta: {reference.focus_residual_delta:.6g}\n"
    )
    output.write(f"- child_focus_residual_delta: {delta.focus_residual_delta:.6g}\n\n")
    return output.getvalue()


def _metric_row(name: str, baseline_value: float, candidate_value: float) -> str:
    """Return one Markdown metric comparison row."""
    return (
        f"| {name} | {baseline_value:.6g} | {candidate_value:.6g} | "
        f"{candidate_value - baseline_value:.6g} |\n"
    )


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
