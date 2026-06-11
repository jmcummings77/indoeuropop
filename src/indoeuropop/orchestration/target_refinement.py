"""Workflow helpers for validation-guided parameter refinement."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from indoeuropop.analysis.refinement import (
    ParameterRefinementCandidate,
    TargetRefinementScenario,
    baseline_refinement_candidate,
    centered_refinement_candidate,
    mean_best_sampled_values,
)
from indoeuropop.data.targets import TargetDataset
from indoeuropop.orchestration.experiments import (
    ExperimentArtifact,
    ExperimentManifest,
    artifact_from_path,
    write_experiment_manifest_json,
)
from indoeuropop.orchestration.sweeps import SweepRun, SweepSpec
from indoeuropop.orchestration.target_validation import run_target_validation_workflow
from indoeuropop.reporting.reproducibility import fingerprint_sweep_collection
from indoeuropop.reporting.target_refinement import (
    write_target_refinement_markdown,
    write_target_refinement_ranges_csv,
    write_target_refinement_summary_csv,
)


@dataclass(frozen=True)
class TargetRefinementOutputPaths:
    """Optional input and output paths for refinement artifacts."""

    config: Path | None = None
    targets: Path | None = None
    refinement_summary_csv: Path | None = None
    refinement_ranges_csv: Path | None = None
    refinement_report_md: Path | None = None
    manifest_json: Path | None = None


@dataclass(frozen=True)
class TargetRefinementWorkflowResult:
    """Generated refinement scenarios and materialized artifacts."""

    scenarios: tuple[TargetRefinementScenario, ...]
    artifacts: tuple[ExperimentArtifact, ...] = ()
    manifest: ExperimentManifest | None = None
    refinement_summary_csv_path: Path | None = None
    refinement_ranges_csv_path: Path | None = None
    refinement_report_md_path: Path | None = None
    manifest_json_path: Path | None = None


def run_target_refinement_workflow(
    spec: SweepSpec,
    targets: TargetDataset,
    *,
    holdout_field: str = "region",
    holdout_values: Iterable[str] | None = None,
    priority_values: Iterable[str] = (),
    protected_values: Iterable[str] = (),
    narrow_fraction: float = 0.5,
    expand_factor: float = 1.5,
    tolerance: float = 0.0,
    paths: TargetRefinementOutputPaths | None = None,
    fit_metric: str = "chi_square",
    command: str = "programmatic-refine-target-parameters",
    manifest_name: str = "target-parameter-refinement",
    manifest_description: str = "Validation-guided parameter-refinement manifest",
    manifest_metadata: Mapping[str, str] | None = None,
) -> TargetRefinementWorkflowResult:
    """Compare baseline, narrowed, and expanded validation-guided sweep grids."""
    _validate_refinement_scalars(narrow_fraction, expand_factor, tolerance)
    target_dataset = targets.require_observations()
    priority_tuple = _non_empty_text_tuple(priority_values)
    protected_tuple = _non_empty_text_tuple(protected_values)
    baseline_candidate = baseline_refinement_candidate(spec)
    baseline_scenario = _candidate_scenario(
        baseline_candidate,
        target_dataset,
        holdout_field=holdout_field,
        holdout_values=holdout_values,
        priority_values=priority_tuple,
        protected_values=protected_tuple,
        fit_metric=fit_metric,
    )
    center_values = mean_best_sampled_values(baseline_scenario.folds)
    candidates = (
        baseline_candidate,
        centered_refinement_candidate(
            spec,
            name="narrowed",
            kind="narrowed",
            center_values=center_values,
            scale=narrow_fraction,
        ),
        centered_refinement_candidate(
            spec,
            name="expanded",
            kind="expanded",
            center_values=center_values,
            scale=expand_factor,
        ),
    )
    scenarios = (
        baseline_scenario,
        *(
            _candidate_scenario(
                candidate,
                target_dataset,
                holdout_field=holdout_field,
                holdout_values=holdout_values,
                priority_values=priority_tuple,
                protected_values=protected_tuple,
                fit_metric=fit_metric,
            )
            for candidate in candidates[1:]
        ),
    )
    return _write_refinement_outputs(
        scenarios,
        paths=TargetRefinementOutputPaths() if paths is None else paths,
        fit_metric=fit_metric,
        tolerance=tolerance,
        command=command,
        manifest_name=manifest_name,
        manifest_description=manifest_description,
        manifest_metadata=manifest_metadata,
    )


def target_refinement_artifacts(
    paths: TargetRefinementOutputPaths,
) -> tuple[ExperimentArtifact, ...]:
    """Return checksum-bearing artifacts for requested refinement paths."""
    artifacts: list[ExperimentArtifact] = []
    if paths.config is not None:
        artifacts.append(artifact_from_path("config", "config", paths.config))
    if paths.targets is not None:
        artifacts.append(artifact_from_path("targets", "targets", paths.targets))
    if paths.refinement_summary_csv is not None:
        artifacts.append(
            artifact_from_path(
                "refinement_summary_csv", "target_fit", paths.refinement_summary_csv
            )
        )
    if paths.refinement_ranges_csv is not None:
        artifacts.append(
            artifact_from_path(
                "refinement_ranges_csv", "other", paths.refinement_ranges_csv
            )
        )
    if paths.refinement_report_md is not None:
        artifacts.append(
            artifact_from_path(
                "refinement_report_md", "other", paths.refinement_report_md
            )
        )
    return tuple(artifacts)


def target_refinement_experiment_manifest(
    scenarios: Iterable[TargetRefinementScenario],
    *,
    artifacts: Iterable[ExperimentArtifact] = (),
    fit_metric: str = "chi_square",
    command: str = "programmatic-refine-target-parameters",
    name: str = "target-parameter-refinement",
    description: str = "Validation-guided parameter-refinement manifest",
    metadata: Mapping[str, str] | None = None,
) -> ExperimentManifest:
    """Return a manifest for a target-refinement workflow."""
    scenario_tuple = _non_empty_scenarios(scenarios)
    manifest_metadata = {
        "command": command,
        "candidate_count": str(len(scenario_tuple)),
        "candidate_names": "|".join(scenario.name for scenario in scenario_tuple),
        "holdout_field": scenario_tuple[0].folds[0].holdout_field,
        "fit_metric": fit_metric,
    }
    manifest_metadata.update({} if metadata is None else metadata)
    return ExperimentManifest(
        name=name,
        description=description,
        artifacts=tuple(artifacts),
        fingerprints=(fingerprint_sweep_collection(_all_runs(scenario_tuple)),),
        metadata=manifest_metadata,
    )


def _candidate_scenario(
    candidate: ParameterRefinementCandidate,
    targets: TargetDataset,
    *,
    holdout_field: str,
    holdout_values: Iterable[str] | None,
    priority_values: tuple[str, ...],
    protected_values: tuple[str, ...],
    fit_metric: str,
) -> TargetRefinementScenario:
    """Run validation for one candidate sweep grid."""
    validation = run_target_validation_workflow(
        candidate.spec,
        targets,
        holdout_field=holdout_field,
        holdout_values=holdout_values,
        fit_metric=fit_metric,
    )
    return TargetRefinementScenario(
        candidate=candidate,
        folds=validation.folds,
        metric=fit_metric,
        priority_values=priority_values,
        protected_values=protected_values,
    )


def _write_refinement_outputs(
    scenarios: tuple[TargetRefinementScenario, ...],
    *,
    paths: TargetRefinementOutputPaths,
    fit_metric: str,
    tolerance: float,
    command: str,
    manifest_name: str,
    manifest_description: str,
    manifest_metadata: Mapping[str, str] | None,
) -> TargetRefinementWorkflowResult:
    """Write requested refinement artifacts and return workflow outputs."""
    if paths.refinement_summary_csv is not None:
        write_target_refinement_summary_csv(
            scenarios, paths.refinement_summary_csv, tolerance=tolerance
        )
    if paths.refinement_ranges_csv is not None:
        write_target_refinement_ranges_csv(scenarios, paths.refinement_ranges_csv)
    if paths.refinement_report_md is not None:
        write_target_refinement_markdown(
            scenarios, paths.refinement_report_md, tolerance=tolerance
        )
    artifacts = target_refinement_artifacts(paths)
    manifest: ExperimentManifest | None = None
    if paths.manifest_json is not None:
        manifest = target_refinement_experiment_manifest(
            scenarios,
            artifacts=artifacts,
            fit_metric=fit_metric,
            command=command,
            name=manifest_name,
            description=manifest_description,
            metadata=manifest_metadata,
        )
        write_experiment_manifest_json(manifest, paths.manifest_json)
    return TargetRefinementWorkflowResult(
        scenarios=scenarios,
        artifacts=artifacts,
        manifest=manifest,
        refinement_summary_csv_path=paths.refinement_summary_csv,
        refinement_ranges_csv_path=paths.refinement_ranges_csv,
        refinement_report_md_path=paths.refinement_report_md,
        manifest_json_path=paths.manifest_json,
    )


def _all_runs(scenarios: tuple[TargetRefinementScenario, ...]) -> tuple[SweepRun, ...]:
    """Return every sweep run represented by refinement scenarios."""
    return tuple(
        validated_run.run
        for scenario in scenarios
        for fold in scenario.folds
        for validated_run in fold.runs
    )


def _non_empty_scenarios(
    scenarios: Iterable[TargetRefinementScenario],
) -> tuple[TargetRefinementScenario, ...]:
    """Return a non-empty scenario tuple."""
    scenario_tuple = tuple(scenarios)
    if not scenario_tuple:
        raise ValueError("scenarios must contain at least one refinement scenario")
    return scenario_tuple


def _non_empty_text_tuple(values: Iterable[str]) -> tuple[str, ...]:
    """Return stripped non-empty text values."""
    return tuple(value.strip() for value in values if value.strip())


def _validate_refinement_scalars(
    narrow_fraction: float, expand_factor: float, tolerance: float
) -> None:
    """Validate refinement scalar arguments."""
    if not 0 < narrow_fraction <= 1:
        raise ValueError("narrow_fraction must be greater than 0 and at most 1")
    if expand_factor < 1:
        raise ValueError("expand_factor must be at least 1")
    if tolerance < 0:
        raise ValueError("tolerance must be non-negative")
