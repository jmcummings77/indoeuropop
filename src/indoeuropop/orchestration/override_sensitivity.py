"""Workflow helpers for child-override sensitivity sweeps."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from indoeuropop.analysis.override_sensitivity import (
    OverrideSensitivityCandidate,
    OverrideSensitivityScenario,
    rank_override_sensitivity_scenarios,
)
from indoeuropop.analysis.override_sensitivity_candidates import (
    child_override_count_reproduction_interaction_candidates,
    child_override_sensitivity_candidates,
)
from indoeuropop.analysis.validation import TargetValidationFold
from indoeuropop.data.targets import TargetDataset
from indoeuropop.orchestration.child_region_overrides import (
    ChildRegionOverrideSet,
    apply_child_region_overrides,
)
from indoeuropop.orchestration.experiments import (
    ExperimentArtifact,
    ExperimentManifest,
    artifact_from_path,
    write_experiment_manifest_json,
)
from indoeuropop.orchestration.sweeps import SweepRun, SweepSpec
from indoeuropop.orchestration.target_validation import run_target_validation_workflow
from indoeuropop.reporting.override_sensitivity import (
    write_override_sensitivity_markdown,
    write_override_sensitivity_summary_csv,
)
from indoeuropop.reporting.reproducibility import fingerprint_sweep_collection


@dataclass(frozen=True)
class OverrideSensitivityOutputPaths:
    """Input and output paths for child-override sensitivity artifacts."""

    config: Path | None = None
    targets: Path | None = None
    child_region_overrides: Path | None = None
    sensitivity_summary_csv: Path | None = None
    sensitivity_report_md: Path | None = None
    manifest_json: Path | None = None


@dataclass(frozen=True)
class OverrideSensitivityWorkflowResult:
    """Result from a child-override sensitivity workflow."""

    baseline_folds: tuple[TargetValidationFold, ...]
    scenarios: tuple[OverrideSensitivityScenario, ...]
    artifacts: tuple[ExperimentArtifact, ...] = ()
    manifest: ExperimentManifest | None = None
    sensitivity_summary_csv_path: Path | None = None
    sensitivity_report_md_path: Path | None = None
    manifest_json_path: Path | None = None

    def best_scenario(self, *, tolerance: float) -> OverrideSensitivityScenario:
        """Return the highest-ranked candidate under a protected-fold tolerance."""
        return rank_override_sensitivity_scenarios(
            self.scenarios,
            self.baseline_folds,
            tolerance=tolerance,
        )[0]


def run_child_override_sensitivity_workflow(
    spec: SweepSpec,
    targets: TargetDataset,
    overrides: ChildRegionOverrideSet,
    *,
    holdout_field: str = "region",
    holdout_values: Iterable[str] | None = None,
    priority_values: Iterable[str] = (),
    protected_values: Iterable[str] = (),
    tolerance: float = 0.0,
    fit_metric: str = "root_mean_squared_error",
    count_factors: Iterable[float] = (0.9, 1.1),
    pulse_rate_factors: Iterable[float] = (0.85, 1.15),
    pulse_window_shifts: Iterable[float] = (-50.0, 50.0),
    reproductive_multiplier_factors: Iterable[float] = (0.95, 1.05),
    candidate_mode: str = "one_factor",
    interaction_regions: Iterable[str] = (),
    paths: OverrideSensitivityOutputPaths | None = None,
    command: str = "programmatic-sweep-child-overrides",
    manifest_name: str = "child-override-sensitivity",
    manifest_description: str = "Child-override sensitivity manifest",
    manifest_metadata: Mapping[str, str] | None = None,
) -> OverrideSensitivityWorkflowResult:
    """Run child-override sensitivity candidates through held-out validation."""
    priority_tuple = _normalized_values(priority_values)
    protected_tuple = _normalized_values(protected_values)
    baseline_folds = run_target_validation_workflow(
        spec,
        targets,
        holdout_field=holdout_field,
        holdout_values=holdout_values,
        fit_metric=fit_metric,
    ).folds
    scenarios = tuple(
        _candidate_scenario(
            spec,
            targets,
            candidate,
            holdout_field=holdout_field,
            holdout_values=holdout_values,
            fit_metric=fit_metric,
            priority_values=priority_tuple,
            protected_values=protected_tuple,
        )
        for candidate in _override_candidates(
            overrides,
            candidate_mode=candidate_mode,
            count_factors=count_factors,
            pulse_rate_factors=pulse_rate_factors,
            pulse_window_shifts=pulse_window_shifts,
            reproductive_multiplier_factors=reproductive_multiplier_factors,
            interaction_regions=interaction_regions,
        )
    )
    output_paths = OverrideSensitivityOutputPaths() if paths is None else paths
    _write_sensitivity_outputs(
        scenarios,
        baseline_folds,
        output_paths,
        tolerance=tolerance,
    )
    artifacts = override_sensitivity_artifacts(output_paths)
    manifest = _write_manifest(
        baseline_folds,
        scenarios,
        artifacts,
        output_paths,
        tolerance=tolerance,
        command=command,
        name=manifest_name,
        description=manifest_description,
        metadata=_manifest_metadata(candidate_mode, manifest_metadata),
    )
    return OverrideSensitivityWorkflowResult(
        baseline_folds=baseline_folds,
        scenarios=scenarios,
        artifacts=artifacts,
        manifest=manifest,
        sensitivity_summary_csv_path=output_paths.sensitivity_summary_csv,
        sensitivity_report_md_path=output_paths.sensitivity_report_md,
        manifest_json_path=output_paths.manifest_json,
    )


def override_sensitivity_artifacts(
    paths: OverrideSensitivityOutputPaths,
) -> tuple[ExperimentArtifact, ...]:
    """Return checksum-bearing artifacts for requested sensitivity paths."""
    artifacts: list[ExperimentArtifact] = []
    for name, path in (
        ("config", paths.config),
        ("targets", paths.targets),
        ("child_region_overrides", paths.child_region_overrides),
    ):
        if path is not None:
            artifacts.append(artifact_from_path(name, "config", path))
    if paths.sensitivity_summary_csv is not None:
        artifacts.append(
            artifact_from_path(
                "sensitivity_summary_csv",
                "sensitivity",
                paths.sensitivity_summary_csv,
            )
        )
    if paths.sensitivity_report_md is not None:
        artifacts.append(
            artifact_from_path(
                "sensitivity_report_md",
                "other",
                paths.sensitivity_report_md,
            )
        )
    return tuple(artifacts)


def override_sensitivity_experiment_manifest(
    baseline_folds: tuple[TargetValidationFold, ...],
    scenarios: tuple[OverrideSensitivityScenario, ...],
    *,
    artifacts: Iterable[ExperimentArtifact] = (),
    tolerance: float = 0.0,
    command: str = "programmatic-sweep-child-overrides",
    name: str = "child-override-sensitivity",
    description: str = "Child-override sensitivity manifest",
    metadata: Mapping[str, str] | None = None,
) -> ExperimentManifest:
    """Return a manifest for a child-override sensitivity workflow."""
    ranked = rank_override_sensitivity_scenarios(
        scenarios,
        baseline_folds,
        tolerance=tolerance,
    )
    top = ranked[0]
    manifest_metadata = {
        "command": command,
        "candidate_count": str(len(scenarios)),
        "accepted_count": str(
            sum(
                scenario.accepted(baseline_folds, tolerance=tolerance)
                for scenario in scenarios
            )
        ),
        "fit_metric": top.metric,
        "top_candidate": top.name,
        "top_priority_mean_delta": f"{top.priority_mean_delta(baseline_folds):.12g}",
        "top_protected_max_delta": f"{top.protected_max_delta(baseline_folds):.12g}",
        "protected_tolerance": f"{tolerance:.12g}",
    }
    manifest_metadata.update({} if metadata is None else metadata)
    return ExperimentManifest(
        name=name,
        description=description,
        artifacts=tuple(artifacts),
        fingerprints=(
            fingerprint_sweep_collection(_all_runs(baseline_folds, scenarios)),
        ),
        metadata=manifest_metadata,
    )


def _candidate_scenario(
    spec: SweepSpec,
    targets: TargetDataset,
    candidate: OverrideSensitivityCandidate,
    *,
    holdout_field: str,
    holdout_values: Iterable[str] | None,
    fit_metric: str,
    priority_values: tuple[str, ...],
    protected_values: tuple[str, ...],
) -> OverrideSensitivityScenario:
    """Run validation for one child-override candidate."""
    overridden_spec = apply_child_region_overrides(spec, candidate.overrides)
    folds = run_target_validation_workflow(
        overridden_spec,
        targets,
        holdout_field=holdout_field,
        holdout_values=holdout_values,
        fit_metric=fit_metric,
    ).folds
    return OverrideSensitivityScenario(
        candidate=candidate,
        folds=folds,
        metric=fit_metric,
        priority_values=priority_values,
        protected_values=protected_values,
    )


def _override_candidates(
    overrides: ChildRegionOverrideSet,
    *,
    candidate_mode: str,
    count_factors: Iterable[float],
    pulse_rate_factors: Iterable[float],
    pulse_window_shifts: Iterable[float],
    reproductive_multiplier_factors: Iterable[float],
    interaction_regions: Iterable[str],
) -> tuple[OverrideSensitivityCandidate, ...]:
    """Return candidates for the requested child-override sensitivity mode."""
    if candidate_mode == "one_factor":
        return child_override_sensitivity_candidates(
            overrides,
            count_factors=count_factors,
            pulse_rate_factors=pulse_rate_factors,
            pulse_window_shifts=pulse_window_shifts,
            reproductive_multiplier_factors=reproductive_multiplier_factors,
        )
    if candidate_mode == "count_reproduction_interaction":
        return child_override_count_reproduction_interaction_candidates(
            overrides,
            regions=interaction_regions,
            count_factors=count_factors,
            reproductive_multiplier_factors=reproductive_multiplier_factors,
        )
    raise ValueError(f"unsupported child-override sensitivity mode: {candidate_mode}")


def _write_sensitivity_outputs(
    scenarios: tuple[OverrideSensitivityScenario, ...],
    baseline_folds: tuple[TargetValidationFold, ...],
    paths: OverrideSensitivityOutputPaths,
    *,
    tolerance: float,
) -> None:
    """Write requested sensitivity CSV and Markdown reports."""
    if paths.sensitivity_summary_csv is not None:
        write_override_sensitivity_summary_csv(
            scenarios,
            baseline_folds,
            paths.sensitivity_summary_csv,
            tolerance=tolerance,
        )
    if paths.sensitivity_report_md is not None:
        write_override_sensitivity_markdown(
            scenarios,
            baseline_folds,
            paths.sensitivity_report_md,
            tolerance=tolerance,
        )


def _write_manifest(
    baseline_folds: tuple[TargetValidationFold, ...],
    scenarios: tuple[OverrideSensitivityScenario, ...],
    artifacts: tuple[ExperimentArtifact, ...],
    paths: OverrideSensitivityOutputPaths,
    *,
    tolerance: float,
    command: str,
    name: str,
    description: str,
    metadata: Mapping[str, str] | None,
) -> ExperimentManifest | None:
    """Write a manifest when requested and return it."""
    if paths.manifest_json is None:
        return None
    manifest = override_sensitivity_experiment_manifest(
        baseline_folds,
        scenarios,
        artifacts=artifacts,
        tolerance=tolerance,
        command=command,
        name=name,
        description=description,
        metadata=metadata,
    )
    write_experiment_manifest_json(manifest, paths.manifest_json)
    return manifest


def _all_runs(
    baseline_folds: tuple[TargetValidationFold, ...],
    scenarios: tuple[OverrideSensitivityScenario, ...],
) -> tuple[SweepRun, ...]:
    """Return all sweep runs represented by baseline and scenario folds."""
    return tuple(run.run for fold in baseline_folds for run in fold.runs) + tuple(
        run.run
        for scenario in scenarios
        for fold in scenario.folds
        for run in fold.runs
    )


def _normalized_values(values: Iterable[str]) -> tuple[str, ...]:
    """Return stripped selector values in input order."""
    return tuple(value.strip() for value in values if value.strip())


def _manifest_metadata(
    candidate_mode: str, metadata: Mapping[str, str] | None
) -> dict[str, str]:
    """Return manifest metadata annotated with the candidate mode."""
    merged = {"candidate_mode": candidate_mode}
    merged.update({} if metadata is None else metadata)
    return merged
