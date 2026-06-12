"""SMC-based same-baseline structural candidate comparison workflows."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path

from indoeuropop.analysis.abc_smc import ABCSMCOptions
from indoeuropop.analysis.child_region_candidates import ChildRegionCandidate
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
from indoeuropop.orchestration.abc_smc import (
    ABCSMCOutputPaths,
    ABCSMCWorkflowResult,
    run_abc_smc_workflow,
)
from indoeuropop.orchestration.child_region_overrides import (
    ChildRegionOverrideSet,
    apply_child_region_overrides,
)
from indoeuropop.orchestration.experiments import (
    ExperimentArtifact,
    ExperimentManifest,
    write_experiment_manifest_json,
)
from indoeuropop.orchestration.structural_smc_outputs import (
    StructuralSMCComparisonResult,
    StructuralSMCOutputPaths,
    structural_smc_artifacts,
    structural_smc_manifest,
    structural_smc_scored_runs,
)
from indoeuropop.orchestration.sweep_config_export import write_sweep_spec_toml
from indoeuropop.orchestration.sweeps import SweepSpec
from indoeuropop.reporting.structural_smc import write_structural_smc_markdown


def run_structural_smc_head_to_head_workflow(
    spec: SweepSpec,
    targets: TargetDataset,
    overrides: ChildRegionOverrideSet,
    structured_pulse_candidate: StructuredPulseCandidate,
    *,
    child_candidate_name: str = "child-region-candidate",
    options: ABCSMCOptions | None = None,
    paths: StructuralSMCOutputPaths | None = None,
    interval_probability: float = 0.9,
    focus_observation_index: int | None = None,
    holdout_targets: TargetDataset | None = None,
    command: str = "programmatic-compare-structured-candidates-smc",
    manifest_name: str = "structured-smc-head-to-head",
    manifest_description: str = "SMC same-baseline structural comparison manifest",
    manifest_metadata: Mapping[str, str] | None = None,
) -> StructuralSMCComparisonResult:
    """Compare structural candidates using the same SMC calibration controls."""
    output_paths = StructuralSMCOutputPaths() if paths is None else paths
    smc_options = ABCSMCOptions() if options is None else options
    pulse_regions = structured_pulse_regions(spec, structured_pulse_candidate)
    pulse_spec = apply_structured_pulse_candidate(spec, structured_pulse_candidate)
    child_spec = apply_child_region_overrides(spec, overrides)
    child_candidate = _child_candidate(child_candidate_name, overrides, output_paths)
    _write_candidate_configs(pulse_spec, child_spec, output_paths)

    baseline = _run_named_smc(
        spec,
        targets,
        holdout_targets,
        smc_options,
        _workflow_paths(output_paths.baseline, output_paths, output_paths.config),
        interval_probability,
        f"{command}:baseline",
        f"{manifest_name}-baseline",
    )
    structured_pulse = _run_named_smc(
        pulse_spec,
        targets,
        holdout_targets,
        smc_options,
        _workflow_paths(
            output_paths.structured_pulse,
            output_paths,
            output_paths.structured_pulse_config_toml,
        ),
        interval_probability,
        f"{command}:structured-pulse",
        f"{manifest_name}-structured-pulse",
    )
    child = _run_named_smc(
        child_spec,
        targets,
        holdout_targets,
        smc_options,
        _workflow_paths(
            output_paths.child,
            output_paths,
            output_paths.child_candidate_config_toml,
        ),
        interval_probability,
        f"{command}:child",
        f"{manifest_name}-child",
    )
    pulse_delta, child_delta = _calibration_deltas(
        baseline, structured_pulse, child, focus_observation_index
    )
    pulse_holdout_delta, child_holdout_delta = _holdout_deltas(
        baseline, structured_pulse, child
    )
    _write_report(
        structured_pulse_candidate,
        len(pulse_regions),
        child_candidate,
        baseline,
        structured_pulse,
        child,
        pulse_delta,
        child_delta,
        pulse_holdout_delta,
        child_holdout_delta,
        output_paths,
    )
    artifacts = structural_smc_artifacts(output_paths)
    manifest = _maybe_write_manifest(
        structured_pulse_candidate,
        len(pulse_regions),
        child_candidate,
        (baseline, structured_pulse, child),
        pulse_delta,
        child_delta,
        pulse_holdout_delta,
        child_holdout_delta,
        artifacts,
        output_paths,
        command,
        manifest_name,
        manifest_description,
        manifest_metadata,
    )
    return StructuralSMCComparisonResult(
        structured_pulse_candidate=structured_pulse_candidate,
        structured_pulse_region_count=len(pulse_regions),
        child_candidate=child_candidate,
        baseline=baseline,
        structured_pulse_result=structured_pulse,
        child_result=child,
        structured_pulse_delta=pulse_delta,
        child_delta=child_delta,
        structured_pulse_holdout_delta=pulse_holdout_delta,
        child_holdout_delta=child_holdout_delta,
        artifacts=artifacts,
        manifest=manifest,
        structured_pulse_config_toml_path=output_paths.structured_pulse_config_toml,
        child_candidate_config_toml_path=output_paths.child_candidate_config_toml,
        head_to_head_report_md_path=output_paths.head_to_head_report_md,
        manifest_json_path=output_paths.manifest_json,
    )


def _workflow_paths(
    paths: ABCSMCOutputPaths,
    parent: StructuralSMCOutputPaths,
    config: Path | None,
) -> ABCSMCOutputPaths:
    """Return nested SMC paths with shared input artifacts attached."""
    return replace(
        paths,
        config=config,
        targets=parent.targets,
        holdout_targets=parent.holdout_targets,
    )


def _child_candidate(
    name: str,
    overrides: ChildRegionOverrideSet,
    paths: StructuralSMCOutputPaths,
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
    pulse_spec: SweepSpec,
    child_spec: SweepSpec,
    paths: StructuralSMCOutputPaths,
) -> None:
    """Write optional candidate config artifacts."""
    if paths.structured_pulse_config_toml is not None:
        write_sweep_spec_toml(pulse_spec, paths.structured_pulse_config_toml)
    if paths.child_candidate_config_toml is not None:
        write_sweep_spec_toml(child_spec, paths.child_candidate_config_toml)


def _run_named_smc(
    spec: SweepSpec,
    targets: TargetDataset,
    holdout_targets: TargetDataset | None,
    options: ABCSMCOptions,
    paths: ABCSMCOutputPaths,
    interval_probability: float,
    command: str,
    manifest_name: str,
) -> ABCSMCWorkflowResult:
    """Run one named SMC calibration workflow."""
    return run_abc_smc_workflow(
        spec,
        targets,
        options=options,
        paths=paths,
        command=command,
        manifest_name=manifest_name,
        interval_probability=interval_probability,
        holdout_targets=holdout_targets,
    )


def _calibration_deltas(
    baseline: ABCSMCWorkflowResult,
    pulse: ABCSMCWorkflowResult,
    child: ABCSMCWorkflowResult,
    focus_observation_index: int | None,
) -> tuple[PosteriorPredictiveMetricDelta, PosteriorPredictiveMetricDelta]:
    """Return calibration posterior predictive deltas for both candidates."""
    assert baseline.posterior_predictive is not None
    assert pulse.posterior_predictive is not None
    assert child.posterior_predictive is not None
    return (
        posterior_predictive_metric_delta(
            baseline.posterior_predictive,
            pulse.posterior_predictive,
            focus_observation_index=focus_observation_index,
            candidate_label="structured_pulse",
        ),
        posterior_predictive_metric_delta(
            baseline.posterior_predictive,
            child.posterior_predictive,
            focus_observation_index=focus_observation_index,
            candidate_label="child_override",
        ),
    )


def _holdout_deltas(
    baseline: ABCSMCWorkflowResult,
    pulse: ABCSMCWorkflowResult,
    child: ABCSMCWorkflowResult,
) -> tuple[
    PosteriorPredictiveMetricDelta | None, PosteriorPredictiveMetricDelta | None
]:
    """Return optional holdout deltas when every workflow has holdout diagnostics."""
    if (
        baseline.holdout_posterior_predictive is None
        or pulse.holdout_posterior_predictive is None
        or child.holdout_posterior_predictive is None
    ):
        return None, None
    return (
        posterior_predictive_metric_delta(
            baseline.holdout_posterior_predictive,
            pulse.holdout_posterior_predictive,
            candidate_label="structured_pulse_holdout",
        ),
        posterior_predictive_metric_delta(
            baseline.holdout_posterior_predictive,
            child.holdout_posterior_predictive,
            candidate_label="child_override_holdout",
        ),
    )


def _write_report(
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
    paths: StructuralSMCOutputPaths,
) -> None:
    """Write an optional structural SMC comparison report."""
    if paths.head_to_head_report_md is None:
        return
    write_structural_smc_markdown(
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
        paths.head_to_head_report_md,
    )


def _maybe_write_manifest(
    pulse_candidate: StructuredPulseCandidate,
    pulse_region_count: int,
    child_candidate: ChildRegionCandidate,
    workflows: tuple[ABCSMCWorkflowResult, ...],
    pulse_delta: PosteriorPredictiveMetricDelta,
    child_delta: PosteriorPredictiveMetricDelta,
    pulse_holdout_delta: PosteriorPredictiveMetricDelta | None,
    child_holdout_delta: PosteriorPredictiveMetricDelta | None,
    artifacts: tuple[ExperimentArtifact, ...],
    paths: StructuralSMCOutputPaths,
    command: str,
    manifest_name: str,
    description: str,
    metadata: Mapping[str, str] | None,
) -> ExperimentManifest | None:
    """Write and return a structural SMC manifest when requested."""
    if paths.manifest_json is None:
        return None
    result = StructuralSMCComparisonResult(
        structured_pulse_candidate=pulse_candidate,
        structured_pulse_region_count=pulse_region_count,
        child_candidate=child_candidate,
        baseline=workflows[0],
        structured_pulse_result=workflows[1],
        child_result=workflows[2],
        structured_pulse_delta=pulse_delta,
        child_delta=child_delta,
        structured_pulse_holdout_delta=pulse_holdout_delta,
        child_holdout_delta=child_holdout_delta,
    )
    manifest = structural_smc_manifest(
        result,
        runs=structural_smc_scored_runs(workflows),
        artifacts=artifacts,
        command=command,
        name=manifest_name,
        description=description,
        metadata=metadata,
    )
    write_experiment_manifest_json(manifest, paths.manifest_json)
    return manifest
