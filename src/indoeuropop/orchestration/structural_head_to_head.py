"""Same-baseline structural candidate comparison workflows."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from indoeuropop.analysis.child_region_candidates import ChildRegionCandidate
from indoeuropop.analysis.inference import ABCRejectionOptions
from indoeuropop.analysis.structural_candidates import (
    PosteriorPredictiveMetricDelta,
    posterior_predictive_metric_delta,
)
from indoeuropop.analysis.structural_head_to_head import (
    StructuredPulseCandidate,
    apply_structured_pulse_candidate,
    structured_pulse_regions,
)
from indoeuropop.data.targets import TargetDataset
from indoeuropop.orchestration.child_region_overrides import (
    ChildRegionOverrideSet,
    apply_child_region_overrides,
)
from indoeuropop.orchestration.experiments import (
    ExperimentArtifact,
    ExperimentManifest,
    write_experiment_manifest_json,
)
from indoeuropop.orchestration.inference import (
    ABCRejectionOutputPaths,
    ABCRejectionWorkflowResult,
    run_abc_rejection_workflow,
)
from indoeuropop.orchestration.structural_head_to_head_outputs import (
    StructuredHeadToHeadOutputPaths,
    head_to_head_baseline_paths,
    head_to_head_child_paths,
    head_to_head_structured_pulse_paths,
    structured_head_to_head_artifacts,
    structured_head_to_head_manifest,
)
from indoeuropop.orchestration.sweep_config_export import write_sweep_spec_toml
from indoeuropop.orchestration.sweeps import SweepRun, SweepSpec
from indoeuropop.reporting.structural_head_to_head import (
    write_structured_head_to_head_markdown,
)


@dataclass(frozen=True)
class StructuredHeadToHeadWorkflowResult:
    """Result for a same-baseline pulse-vs-child structural comparison."""

    structured_pulse_candidate: StructuredPulseCandidate
    structured_pulse_region_count: int
    child_candidate: ChildRegionCandidate
    baseline: ABCRejectionWorkflowResult
    structured_pulse_result: ABCRejectionWorkflowResult
    child_result: ABCRejectionWorkflowResult
    structured_pulse_delta: PosteriorPredictiveMetricDelta
    child_delta: PosteriorPredictiveMetricDelta
    artifacts: tuple[ExperimentArtifact, ...] = ()
    manifest: ExperimentManifest | None = None
    structured_pulse_config_toml_path: Path | None = None
    child_candidate_config_toml_path: Path | None = None
    head_to_head_report_md_path: Path | None = None
    manifest_json_path: Path | None = None

    @property
    def child_minus_structured_pulse_rmse_delta(self) -> float:
        """Return child RMSE delta minus structured-pulse RMSE delta."""
        return (
            self.child_delta.root_mean_squared_error_delta
            - self.structured_pulse_delta.root_mean_squared_error_delta
        )


def run_structured_head_to_head_workflow(
    spec: SweepSpec,
    targets: TargetDataset,
    overrides: ChildRegionOverrideSet,
    structured_pulse_candidate: StructuredPulseCandidate,
    *,
    child_candidate_name: str = "child-region-candidate",
    options: ABCRejectionOptions | None = None,
    paths: StructuredHeadToHeadOutputPaths | None = None,
    interval_probability: float = 0.9,
    focus_observation_index: int | None = None,
    command: str = "programmatic-compare-structured-candidates",
    manifest_name: str = "structured-candidate-head-to-head",
    manifest_description: str = "Same-baseline structural comparison manifest",
    manifest_metadata: Mapping[str, str] | None = None,
) -> StructuredHeadToHeadWorkflowResult:
    """Compare structured-pulse and child-override candidates on one baseline."""
    output_paths = StructuredHeadToHeadOutputPaths() if paths is None else paths
    inference_options = ABCRejectionOptions() if options is None else options
    structured_pulse_regions_tuple = structured_pulse_regions(
        spec, structured_pulse_candidate
    )
    structured_pulse_spec = apply_structured_pulse_candidate(
        spec, structured_pulse_candidate
    )
    child_spec = apply_child_region_overrides(spec, overrides)
    child_candidate = _child_candidate(child_candidate_name, overrides, output_paths)
    _write_candidate_configs(structured_pulse_spec, child_spec, output_paths)

    baseline = _run_named_inference(
        spec,
        targets,
        inference_options,
        head_to_head_baseline_paths(output_paths),
        interval_probability,
        f"{command}:baseline",
        f"{manifest_name}-baseline",
    )
    structured_pulse_result = _run_named_inference(
        structured_pulse_spec,
        targets,
        inference_options,
        head_to_head_structured_pulse_paths(output_paths),
        interval_probability,
        f"{command}:structured-pulse",
        f"{manifest_name}-structured-pulse",
    )
    child_result = _run_named_inference(
        child_spec,
        targets,
        inference_options,
        head_to_head_child_paths(output_paths),
        interval_probability,
        f"{command}:child",
        f"{manifest_name}-child",
    )
    structured_pulse_delta, child_delta = _deltas(
        baseline,
        structured_pulse_result,
        child_result,
        focus_observation_index,
        structured_pulse_candidate.name,
        child_candidate.name,
    )
    _write_report(
        structured_pulse_candidate,
        len(structured_pulse_regions_tuple),
        child_candidate,
        baseline,
        structured_pulse_result,
        child_result,
        structured_pulse_delta,
        child_delta,
        output_paths,
    )

    artifacts = structured_head_to_head_artifacts(output_paths)
    manifest = _maybe_write_manifest(
        structured_pulse_candidate,
        len(structured_pulse_regions_tuple),
        child_candidate,
        structured_pulse_delta,
        child_delta,
        (baseline, structured_pulse_result, child_result),
        artifacts,
        output_paths,
        command,
        manifest_name,
        manifest_description,
        manifest_metadata,
    )
    return StructuredHeadToHeadWorkflowResult(
        structured_pulse_candidate=structured_pulse_candidate,
        structured_pulse_region_count=len(structured_pulse_regions_tuple),
        child_candidate=child_candidate,
        baseline=baseline,
        structured_pulse_result=structured_pulse_result,
        child_result=child_result,
        structured_pulse_delta=structured_pulse_delta,
        child_delta=child_delta,
        artifacts=artifacts,
        manifest=manifest,
        structured_pulse_config_toml_path=output_paths.structured_pulse_config_toml,
        child_candidate_config_toml_path=output_paths.child_candidate_config_toml,
        head_to_head_report_md_path=output_paths.head_to_head_report_md,
        manifest_json_path=output_paths.manifest_json,
    )


def _child_candidate(
    name: str,
    overrides: ChildRegionOverrideSet,
    paths: StructuredHeadToHeadOutputPaths,
) -> ChildRegionCandidate:
    """Build a child-candidate summary from override tables."""
    regions = set(overrides.counts)
    regions.update(pulse.region for pulse in overrides.migration_pulses)
    regions.update(overrides.region_parameters)
    regions.update(overrides.source_parameters)
    return ChildRegionCandidate(
        name=name,
        override_path=(
            ""
            if paths.child_region_overrides is None
            else str(paths.child_region_overrides)
        ),
        overridden_region_count=len(regions),
        migration_pulse_count=len(overrides.migration_pulses),
    )


def _write_candidate_configs(
    structured_pulse_spec: SweepSpec,
    child_spec: SweepSpec,
    paths: StructuredHeadToHeadOutputPaths,
) -> None:
    """Write optional candidate config artifacts."""
    if paths.structured_pulse_config_toml is not None:
        write_sweep_spec_toml(structured_pulse_spec, paths.structured_pulse_config_toml)
    if paths.child_candidate_config_toml is not None:
        write_sweep_spec_toml(child_spec, paths.child_candidate_config_toml)


def _run_named_inference(
    spec: SweepSpec,
    targets: TargetDataset,
    options: ABCRejectionOptions,
    paths: ABCRejectionOutputPaths,
    interval_probability: float,
    command: str,
    manifest_name: str,
) -> ABCRejectionWorkflowResult:
    """Run one named inference workflow."""
    return run_abc_rejection_workflow(
        spec,
        targets,
        options=options,
        paths=paths,
        interval_probability=interval_probability,
        command=command,
        manifest_name=manifest_name,
    )


def _deltas(
    baseline: ABCRejectionWorkflowResult,
    pulse: ABCRejectionWorkflowResult,
    child: ABCRejectionWorkflowResult,
    focus_observation_index: int | None,
    pulse_label: str,
    child_label: str,
) -> tuple[PosteriorPredictiveMetricDelta, PosteriorPredictiveMetricDelta]:
    """Return pulse and child deltas against the same baseline diagnostics."""
    assert baseline.posterior_predictive is not None
    assert pulse.posterior_predictive is not None
    assert child.posterior_predictive is not None
    return (
        posterior_predictive_metric_delta(
            baseline.posterior_predictive,
            pulse.posterior_predictive,
            focus_observation_index=focus_observation_index,
            candidate_label=pulse_label,
        ),
        posterior_predictive_metric_delta(
            baseline.posterior_predictive,
            child.posterior_predictive,
            focus_observation_index=focus_observation_index,
            candidate_label=child_label,
        ),
    )


def _write_report(
    pulse_candidate: StructuredPulseCandidate,
    pulse_region_count: int,
    child_candidate: ChildRegionCandidate,
    baseline: ABCRejectionWorkflowResult,
    pulse: ABCRejectionWorkflowResult,
    child: ABCRejectionWorkflowResult,
    pulse_delta: PosteriorPredictiveMetricDelta,
    child_delta: PosteriorPredictiveMetricDelta,
    paths: StructuredHeadToHeadOutputPaths,
) -> None:
    """Write an optional head-to-head Markdown report."""
    if paths.head_to_head_report_md is None:
        return
    assert baseline.posterior_predictive is not None
    assert pulse.posterior_predictive is not None
    assert child.posterior_predictive is not None
    write_structured_head_to_head_markdown(
        pulse_candidate,
        pulse_region_count,
        child_candidate,
        baseline.posterior_predictive,
        pulse.posterior_predictive,
        child.posterior_predictive,
        pulse_delta,
        child_delta,
        paths.head_to_head_report_md,
    )


def _maybe_write_manifest(
    pulse_candidate: StructuredPulseCandidate,
    pulse_region_count: int,
    child_candidate: ChildRegionCandidate,
    pulse_delta: PosteriorPredictiveMetricDelta,
    child_delta: PosteriorPredictiveMetricDelta,
    workflows: tuple[ABCRejectionWorkflowResult, ...],
    artifacts: tuple[ExperimentArtifact, ...],
    paths: StructuredHeadToHeadOutputPaths,
    command: str,
    manifest_name: str,
    description: str,
    metadata: Mapping[str, str] | None,
) -> ExperimentManifest | None:
    """Write and return a manifest when requested."""
    if paths.manifest_json is None:
        return None
    manifest = structured_head_to_head_manifest(
        pulse_candidate,
        pulse_region_count,
        child_candidate,
        pulse_delta,
        child_delta,
        runs=_workflow_runs(workflows),
        artifacts=artifacts,
        command=command,
        name=manifest_name,
        description=description,
        metadata=metadata,
    )
    write_experiment_manifest_json(manifest, paths.manifest_json)
    return manifest


def _workflow_runs(
    workflows: Iterable[ABCRejectionWorkflowResult],
) -> tuple[SweepRun, ...]:
    """Return all scored runs represented by the compared workflows."""
    runs: list[SweepRun] = []
    for workflow in workflows:
        runs.extend(scored.run for scored in workflow.inference.ranked_runs)
    return tuple(runs)
