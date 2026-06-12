"""Multi-fold structural SMC validation workflows."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from indoeuropop.analysis.abc_smc import ABCSMCOptions
from indoeuropop.analysis.structural_head_to_head import StructuredPulseCandidate
from indoeuropop.analysis.validation import (
    TargetSplit,
    split_targets_by_holdout_value,
)
from indoeuropop.data.targets import (
    TargetDataset,
    TargetObservation,
    write_target_dataset_csv,
)
from indoeuropop.orchestration.child_region_overrides import ChildRegionOverrideSet
from indoeuropop.orchestration.experiments import (
    ExperimentArtifact,
    ExperimentManifest,
    write_experiment_manifest_json,
)
from indoeuropop.orchestration.structural_smc import (
    run_structural_smc_head_to_head_workflow,
)
from indoeuropop.orchestration.structural_smc_outputs import (
    StructuralSMCOutputPaths,
    structural_smc_output_paths_from_dir,
)
from indoeuropop.orchestration.structural_smc_validation_models import (
    DEFAULT_STRUCTURAL_SMC_CHRONOLOGY_WINDOWS,
    StructuralSMCMultiFoldValidationResult,
    StructuralSMCValidationFoldResult,
    StructuralSMCValidationFoldSpec,
    StructuralSMCValidationOutputPaths,
    merge_structural_smc_validation_folds,
)
from indoeuropop.orchestration.structural_smc_validation_outputs import (
    structural_smc_validation_artifacts,
    structural_smc_validation_manifest,
)
from indoeuropop.orchestration.sweeps import SweepSpec
from indoeuropop.reporting.structural_smc_validation import (
    write_structural_smc_validation_csv,
    write_structural_smc_validation_markdown,
)


def default_structural_smc_validation_folds(
    targets: TargetDataset,
    *,
    region_prefix: str = "central_europe__",
    protected_values: Iterable[str] = (),
    priority_values: Iterable[str] = (),
    include_chronology: bool = True,
) -> tuple[StructuralSMCValidationFoldSpec, ...]:
    """Return default protected, priority, child-region, and chronology folds."""
    target_dataset = targets.require_observations()
    fold_specs: list[StructuralSMCValidationFoldSpec] = []
    regions = target_dataset.regions()
    for value in protected_values:
        _append_field_fold(fold_specs, value, "protected", "region", value)
    if "britain" in regions:
        _append_field_fold(fold_specs, "britain", "britain_anchor", "region", "britain")
    for value in priority_values:
        _append_field_fold(fold_specs, value, "priority", "region", value)
    for region in regions:
        if region.startswith(region_prefix):
            _append_field_fold(
                fold_specs, region, "central_europe_child", "region", region
            )
    if include_chronology:
        fold_specs.extend(_usable_chronology_folds(target_dataset))
    return merge_structural_smc_validation_folds(fold_specs)


def split_targets_by_structural_smc_fold(
    targets: TargetDataset,
    fold: StructuralSMCValidationFoldSpec,
) -> TargetSplit:
    """Split targets into calibration and holdout sets for one fold."""
    if not fold.is_time_window:
        return split_targets_by_holdout_value(
            targets, fold.holdout_field, fold.holdout_value
        )
    calibration: list[TargetObservation] = []
    validation: list[TargetObservation] = []
    for observation in targets.require_observations().observations:
        destination = (
            validation
            if _time_in_window(observation.time_bce, fold.start_bce, fold.end_bce)
            else calibration
        )
        destination.append(observation)
    return TargetSplit(
        calibration=TargetDataset.from_rows(calibration),
        validation=TargetDataset.from_rows(validation),
    )


def run_structural_smc_multifold_validation_workflow(
    spec: SweepSpec,
    targets: TargetDataset,
    overrides: ChildRegionOverrideSet,
    structured_pulse_candidate: StructuredPulseCandidate,
    *,
    folds: Iterable[StructuralSMCValidationFoldSpec],
    child_candidate_name: str = "child-region-candidate",
    options: ABCSMCOptions | None = None,
    paths: StructuralSMCValidationOutputPaths | None = None,
    interval_probability: float = 0.9,
    command: str = "programmatic-validate-structured-candidates-smc",
    manifest_metadata: Mapping[str, str] | None = None,
) -> StructuralSMCMultiFoldValidationResult:
    """Run structural SMC comparisons across several holdout folds."""
    fold_specs = tuple(folds)
    if not fold_specs:
        raise ValueError("folds must contain at least one validation fold")
    output_paths = StructuralSMCValidationOutputPaths() if paths is None else paths
    smc_options = ABCSMCOptions() if options is None else options
    results = tuple(
        _run_fold(
            spec,
            targets,
            overrides,
            structured_pulse_candidate,
            fold,
            child_candidate_name,
            smc_options,
            output_paths,
            interval_probability,
            command,
        )
        for fold in fold_specs
    )
    _write_outputs(results, output_paths)
    artifacts = structural_smc_validation_artifacts(output_paths, results)
    manifest = _write_manifest(
        results, artifacts, output_paths, command, manifest_metadata
    )
    return StructuralSMCMultiFoldValidationResult(
        folds=results,
        artifacts=artifacts,
        manifest=manifest,
        summary_csv_path=output_paths.summary_csv,
        report_md_path=output_paths.report_md,
        manifest_json_path=output_paths.manifest_json,
    )


def _run_fold(
    spec: SweepSpec,
    targets: TargetDataset,
    overrides: ChildRegionOverrideSet,
    candidate: StructuredPulseCandidate,
    fold: StructuralSMCValidationFoldSpec,
    child_candidate_name: str,
    options: ABCSMCOptions,
    paths: StructuralSMCValidationOutputPaths,
    interval_probability: float,
    command: str,
) -> StructuralSMCValidationFoldResult:
    """Run one validation fold through the single-fold structural SMC workflow."""
    split = split_targets_by_structural_smc_fold(targets, fold)
    fold_paths = _fold_paths(paths, fold, split)
    comparison = run_structural_smc_head_to_head_workflow(
        spec,
        split.calibration,
        overrides,
        candidate,
        child_candidate_name=child_candidate_name,
        options=options,
        paths=fold_paths,
        interval_probability=interval_probability,
        holdout_targets=split.validation,
        command=f"{command}:{fold.name}",
        manifest_name=f"structured-smc-validation-{fold.name}",
        manifest_metadata={"validation_fold": fold.name},
    )
    return StructuralSMCValidationFoldResult(
        spec=fold,
        calibration_target_count=len(split.calibration.observations),
        holdout_target_count=len(split.validation.observations),
        comparison=comparison,
    )


def _fold_paths(
    paths: StructuralSMCValidationOutputPaths,
    fold: StructuralSMCValidationFoldSpec,
    split: TargetSplit,
) -> StructuralSMCOutputPaths | None:
    """Return structural SMC paths for one fold, writing split target CSVs."""
    if paths.output_dir is None:
        return None
    fold_dir = paths.output_dir / fold.name
    calibration_path = write_target_dataset_csv(
        split.calibration, fold_dir / "calibration-targets.csv"
    )
    holdout_path = write_target_dataset_csv(
        split.validation, fold_dir / "holdout-targets.csv"
    )
    return structural_smc_output_paths_from_dir(
        fold_dir,
        config=paths.config,
        targets=calibration_path,
        holdout_targets=holdout_path,
        child_region_overrides=paths.child_region_overrides,
    )


def _write_outputs(
    results: tuple[StructuralSMCValidationFoldResult, ...],
    paths: StructuralSMCValidationOutputPaths,
) -> None:
    """Write optional top-level CSV and Markdown outputs."""
    if paths.summary_csv is not None:
        write_structural_smc_validation_csv(results, paths.summary_csv)
    if paths.report_md is not None:
        write_structural_smc_validation_markdown(results, paths.report_md)


def _write_manifest(
    results: tuple[StructuralSMCValidationFoldResult, ...],
    artifacts: tuple[ExperimentArtifact, ...],
    paths: StructuralSMCValidationOutputPaths,
    command: str,
    metadata: Mapping[str, str] | None,
) -> ExperimentManifest | None:
    """Write an optional manifest for the multi-fold validation run."""
    if paths.manifest_json is None:
        return None
    manifest = structural_smc_validation_manifest(
        results,
        artifacts=artifacts,
        command=command,
        metadata=metadata,
    )
    write_experiment_manifest_json(manifest, paths.manifest_json)
    return manifest


def _usable_chronology_folds(
    targets: TargetDataset,
) -> tuple[StructuralSMCValidationFoldSpec, ...]:
    """Return chronology folds that leave both calibration and validation rows."""
    folds: list[StructuralSMCValidationFoldSpec] = []
    for name, start_bce, end_bce in DEFAULT_STRUCTURAL_SMC_CHRONOLOGY_WINDOWS:
        fold = StructuralSMCValidationFoldSpec(
            name=name,
            categories=("priority_chronology",),
            holdout_field="time_bce",
            start_bce=start_bce,
            end_bce=end_bce,
        )
        if _has_usable_split(targets, fold):
            folds.append(fold)
    return tuple(folds)


def _append_field_fold(
    folds: list[StructuralSMCValidationFoldSpec],
    name: str,
    category: str,
    field: str,
    value: str,
) -> None:
    """Append one field fold if the value is non-empty."""
    if value.strip():
        folds.append(
            StructuralSMCValidationFoldSpec(
                name=name,
                categories=(category,),
                holdout_field=field,
                holdout_value=value,
            )
        )


def _has_usable_split(
    targets: TargetDataset, fold: StructuralSMCValidationFoldSpec
) -> bool:
    """Return whether a fold leaves non-empty calibration and holdout sets."""
    calibration_count = validation_count = 0
    for observation in targets.observations:
        if _time_in_window(observation.time_bce, fold.start_bce, fold.end_bce):
            validation_count += 1
        else:
            calibration_count += 1
    return calibration_count > 0 and validation_count > 0


def _time_in_window(
    time_bce: float, start_bce: float | None, end_bce: float | None
) -> bool:
    """Return whether a BCE time falls inside an inclusive old-to-young window."""
    assert start_bce is not None
    assert end_bce is not None
    return end_bce <= time_bce <= start_bce
