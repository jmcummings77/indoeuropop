"""Reports for targeted model-structure candidate diagnostics."""

from __future__ import annotations

from io import StringIO
from pathlib import Path

from indoeuropop.analysis.posterior_predictive import (
    PosteriorPredictiveDiagnostics,
    PosteriorPredictiveObservation,
)
from indoeuropop.analysis.structural_candidates import (
    MigrationPulseCandidate,
    PosteriorPredictiveMetricDelta,
)
from indoeuropop.data.target_notes import target_note_metadata


def migration_pulse_candidate_markdown(
    candidate: MigrationPulseCandidate,
    baseline: PosteriorPredictiveDiagnostics,
    candidate_diagnostics: PosteriorPredictiveDiagnostics,
    delta: PosteriorPredictiveMetricDelta,
) -> str:
    """Return a Markdown report comparing baseline and pulse-candidate fit."""
    baseline_focus = baseline.observations[delta.focus_observation_index]
    candidate_focus = candidate_diagnostics.observations[delta.focus_observation_index]
    output = StringIO()
    output.write(f"# Migration Pulse Candidate: {candidate.name}\n\n")
    output.write(
        "This report compares posterior predictive diagnostics before and after "
        "adding one time-localized migration pulse. It is a structural model "
        "check, not evidence that the candidate pulse occurred historically.\n\n"
    )
    output.write("## Candidate\n\n")
    output.write(f"- region: {candidate.region}\n")
    output.write(f"- source: {candidate.source}\n")
    output.write(f"- start_bce: {candidate.start_bce:.6g}\n")
    output.write(f"- end_bce: {candidate.end_bce:.6g}\n")
    output.write(f"- annual_rate: {candidate.annual_rate:.6g}\n\n")
    output.write("## Aggregate Diagnostics\n\n")
    output.write(
        "| Metric | Baseline | Candidate | Candidate - baseline |\n"
        "| --- | ---: | ---: | ---: |\n"
    )
    output.write(
        _metric_row(
            "coverage_rate",
            baseline.coverage_rate,
            candidate_diagnostics.coverage_rate,
            delta.coverage_rate_delta,
        )
    )
    output.write(
        _metric_row(
            "mean_absolute_error",
            baseline.mean_absolute_error,
            candidate_diagnostics.mean_absolute_error,
            delta.mean_absolute_error_delta,
        )
    )
    output.write(
        _metric_row(
            "root_mean_squared_error",
            baseline.root_mean_squared_error,
            candidate_diagnostics.root_mean_squared_error,
            delta.root_mean_squared_error_delta,
        )
    )
    output.write(
        _metric_row(
            "max_abs_z_score",
            baseline.max_abs_z_score,
            candidate_diagnostics.max_abs_z_score,
            delta.max_abs_z_score_delta,
        )
    )
    output.write("\n## Focus Observation\n\n")
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
    output.write("## Interpretation Guardrail\n\n")
    output.write(
        "Prefer this candidate only if the aggregate diagnostic improves without "
        "hiding a new target-specific failure, and only after reviewing the "
        "target chronology, grouping, and qpAdm uncertainty that motivated the "
        "pulse test.\n"
    )
    return output.getvalue()


def write_migration_pulse_candidate_markdown(
    candidate: MigrationPulseCandidate,
    baseline: PosteriorPredictiveDiagnostics,
    candidate_diagnostics: PosteriorPredictiveDiagnostics,
    delta: PosteriorPredictiveMetricDelta,
    path: str | Path,
) -> Path:
    """Write a migration-pulse candidate Markdown report and return the path."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        migration_pulse_candidate_markdown(
            candidate,
            baseline,
            candidate_diagnostics,
            delta,
        ),
        encoding="utf-8",
    )
    return output_path


def _metric_row(
    name: str,
    baseline_value: float,
    candidate_value: float,
    delta_value: float,
) -> str:
    """Return one Markdown metric comparison row."""
    return (
        f"| {name} | {baseline_value:.6g} | {candidate_value:.6g} | "
        f"{delta_value:.6g} |\n"
    )


def _focus_metadata_lines(observation: PosteriorPredictiveObservation) -> str:
    """Return human-readable lines for focus target identity metadata."""
    target = observation.observation
    metadata = target_note_metadata(target.note)
    requested_group_id = metadata.get("requested_group_id", "")
    target_id = metadata.get("target_id", "")
    lines = [
        f"- region: {target.region}\n",
        f"- source: {target.source}\n",
        f"- time_bce: {target.time_bce:.6g}\n",
    ]
    if requested_group_id:
        lines.append(f"- requested_group_id: {requested_group_id}\n")
    if target_id:
        lines.append(f"- target_id: {target_id}\n")
    return "".join(lines)
