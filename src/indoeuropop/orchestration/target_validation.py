"""Workflow helpers for held-out target validation."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from indoeuropop.analysis.validation import (
    TargetValidationFold,
    run_validated_parameter_sweep,
    split_targets_by_holdout_value,
    target_holdout_values,
)
from indoeuropop.data.targets import TargetDataset
from indoeuropop.orchestration.experiments import (
    ExperimentArtifact,
    ExperimentManifest,
    artifact_from_path,
    write_experiment_manifest_json,
)
from indoeuropop.orchestration.sweeps import SweepRun, SweepSpec
from indoeuropop.reporting.reproducibility import fingerprint_sweep_collection
from indoeuropop.reporting.target_validation import (
    write_target_validation_csv,
    write_target_validation_markdown,
)


@dataclass(frozen=True)
class TargetValidationOutputPaths:
    """Optional input and output paths for validation artifacts."""

    config: Path | None = None
    targets: Path | None = None
    validation_fit_csv: Path | None = None
    validation_report_md: Path | None = None
    manifest_json: Path | None = None


@dataclass(frozen=True)
class TargetValidationWorkflowResult:
    """Held-out validation folds and materialized workflow artifacts."""

    folds: tuple[TargetValidationFold, ...]
    artifacts: tuple[ExperimentArtifact, ...] = ()
    manifest: ExperimentManifest | None = None
    validation_fit_csv_path: Path | None = None
    validation_report_md_path: Path | None = None
    manifest_json_path: Path | None = None

    @property
    def best_fold(self) -> TargetValidationFold:
        """Return the fold with the smallest validation fit among best runs."""
        return min(
            self.folds,
            key=lambda fold: fold.best_run.fit.validation.root_mean_squared_error,
        )


def run_target_validation_workflow(
    spec: SweepSpec,
    targets: TargetDataset,
    *,
    holdout_field: str = "region",
    holdout_values: Iterable[str] | None = None,
    paths: TargetValidationOutputPaths | None = None,
    fit_metric: str = "chi_square",
    command: str = "programmatic-validate-targets",
    manifest_name: str = "target-validation",
    manifest_description: str = "Held-out target-validation manifest",
    manifest_metadata: Mapping[str, str] | None = None,
) -> TargetValidationWorkflowResult:
    """Run calibration-ranked sweeps for one or more held-out target folds."""
    target_dataset = targets.require_observations()
    fold_values = (
        target_holdout_values(target_dataset, holdout_field)
        if holdout_values is None
        else _non_empty_values(holdout_values)
    )
    folds = tuple(
        _run_validation_fold(
            spec,
            target_dataset,
            holdout_field=holdout_field,
            holdout_value=holdout_value,
            fit_metric=fit_metric,
        )
        for holdout_value in fold_values
    )
    output_paths = TargetValidationOutputPaths() if paths is None else paths
    if output_paths.validation_fit_csv is not None:
        write_target_validation_csv(folds, output_paths.validation_fit_csv)
    if output_paths.validation_report_md is not None:
        write_target_validation_markdown(
            folds,
            output_paths.validation_report_md,
            metric=fit_metric,
        )

    artifacts = target_validation_artifacts(output_paths)
    manifest: ExperimentManifest | None = None
    if output_paths.manifest_json is not None:
        manifest = target_validation_experiment_manifest(
            folds,
            artifacts=artifacts,
            fit_metric=fit_metric,
            command=command,
            name=manifest_name,
            description=manifest_description,
            metadata=manifest_metadata,
        )
        write_experiment_manifest_json(manifest, output_paths.manifest_json)

    return TargetValidationWorkflowResult(
        folds=folds,
        artifacts=artifacts,
        manifest=manifest,
        validation_fit_csv_path=output_paths.validation_fit_csv,
        validation_report_md_path=output_paths.validation_report_md,
        manifest_json_path=output_paths.manifest_json,
    )


def target_validation_artifacts(
    paths: TargetValidationOutputPaths,
) -> tuple[ExperimentArtifact, ...]:
    """Return checksum-bearing artifacts for requested validation paths."""
    artifacts: list[ExperimentArtifact] = []
    if paths.config is not None:
        artifacts.append(artifact_from_path("config", "config", paths.config))
    if paths.targets is not None:
        artifacts.append(artifact_from_path("targets", "targets", paths.targets))
    if paths.validation_fit_csv is not None:
        artifacts.append(
            artifact_from_path(
                "validation_fit_csv", "target_fit", paths.validation_fit_csv
            )
        )
    if paths.validation_report_md is not None:
        artifacts.append(
            artifact_from_path(
                "validation_report_md", "other", paths.validation_report_md
            )
        )
    return tuple(artifacts)


def target_validation_experiment_manifest(
    folds: Iterable[TargetValidationFold],
    *,
    artifacts: Iterable[ExperimentArtifact] = (),
    fit_metric: str = "chi_square",
    command: str = "programmatic-validate-targets",
    name: str = "target-validation",
    description: str = "Held-out target-validation manifest",
    metadata: Mapping[str, str] | None = None,
) -> ExperimentManifest:
    """Return a manifest for a held-out target-validation workflow."""
    fold_tuple = _non_empty_folds(folds)
    manifest_metadata = {
        "command": command,
        "holdout_field": fold_tuple[0].holdout_field,
        "holdout_values": "|".join(fold.holdout_value for fold in fold_tuple),
        "fold_count": str(len(fold_tuple)),
        "fit_metric": fit_metric,
    }
    manifest_metadata.update({} if metadata is None else metadata)
    return ExperimentManifest(
        name=name,
        description=description,
        artifacts=tuple(artifacts),
        fingerprints=(fingerprint_sweep_collection(_all_runs(fold_tuple)),),
        metadata=manifest_metadata,
    )


def _run_validation_fold(
    spec: SweepSpec,
    targets: TargetDataset,
    *,
    holdout_field: str,
    holdout_value: str,
    fit_metric: str,
) -> TargetValidationFold:
    """Run one held-out validation fold."""
    target_split = split_targets_by_holdout_value(
        targets,
        holdout_field,
        holdout_value,
    )
    return TargetValidationFold(
        holdout_field=holdout_field,
        holdout_value=holdout_value,
        target_split=target_split,
        runs=run_validated_parameter_sweep(
            spec,
            target_split,
            metric=fit_metric,
        ),
    )


def _non_empty_values(values: Iterable[str]) -> tuple[str, ...]:
    """Return stripped holdout values after requiring at least one value."""
    normalized_values = tuple(value.strip() for value in values if value.strip())
    if not normalized_values:
        raise ValueError("holdout_values must contain at least one value")
    return normalized_values


def _non_empty_folds(
    folds: Iterable[TargetValidationFold],
) -> tuple[TargetValidationFold, ...]:
    """Return a non-empty validation-fold tuple."""
    fold_tuple = tuple(folds)
    if not fold_tuple:
        raise ValueError("folds must contain at least one validation fold")
    return fold_tuple


def _all_runs(folds: tuple[TargetValidationFold, ...]) -> tuple[SweepRun, ...]:
    """Return all sweep runs represented by validation folds."""
    return tuple(validated_run.run for fold in folds for validated_run in fold.runs)
