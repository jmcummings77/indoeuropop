"""Source-model sensitivity workflows for structural SMC validation."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from indoeuropop.analysis.abc_smc import ABCSMCOptions
from indoeuropop.analysis.structural_head_to_head import StructuredPulseCandidate
from indoeuropop.data.targets import TargetDataset, write_target_dataset_csv
from indoeuropop.orchestration.child_region_overrides import (
    ChildRegionOverrideSet,
)
from indoeuropop.orchestration.structural_smc_source_model_sensitivity_inputs import (
    common_target_ids,
    filter_targets_by_ids,
    fragile_target_ids,
    restrict_child_region_overrides,
    source_model_tuple,
)
from indoeuropop.orchestration.structural_smc_source_model_sensitivity_models import (
    StructuralSMCSourceModel,
    StructuralSMCSourceModelRunResult,
    StructuralSMCSourceModelSensitivityPaths,
    StructuralSMCSourceModelSensitivityResult,
)
from indoeuropop.orchestration.structural_smc_validation import (
    default_structural_smc_validation_folds,
    run_structural_smc_multifold_validation_workflow,
)
from indoeuropop.orchestration.structural_smc_validation_models import (
    StructuralSMCValidationFoldSpec,
    merge_structural_smc_validation_folds,
    structural_smc_validation_slug,
)
from indoeuropop.orchestration.structural_smc_validation_outputs import (
    structural_smc_validation_output_paths_from_dir,
)
from indoeuropop.orchestration.sweep_config_export import write_sweep_spec_toml
from indoeuropop.orchestration.sweeps import SweepSpec
from indoeuropop.orchestration.target_fragility import (
    usable_structural_smc_validation_folds,
)
from indoeuropop.orchestration.target_fragility_models import (
    DEFAULT_REPEATED_ESTIMATE_TOLERANCE,
    DEFAULT_TARGET_FRAGILITY_FLAGS,
)
from indoeuropop.orchestration.target_structure import (
    structure_sweep_spec,
    structure_target_dataset,
)
from indoeuropop.reporting.structural_smc_source_model_sensitivity import (
    write_structural_smc_source_model_sensitivity_csv,
    write_structural_smc_source_model_sensitivity_markdown,
)
from indoeuropop.reporting.structural_smc_uncertainty import (
    DEFAULT_MATERIAL_CHI_SQUARE_DELTA,
    load_structural_smc_uncertainty_report,
    write_structural_smc_uncertainty_csv,
    write_structural_smc_uncertainty_markdown,
)


def structural_smc_source_model_sensitivity_paths_from_dir(
    output_dir: str | Path,
) -> StructuralSMCSourceModelSensitivityPaths:
    """Return conventional paths for source-model sensitivity artifacts."""
    root = Path(output_dir)
    return StructuralSMCSourceModelSensitivityPaths(
        output_dir=root,
        summary_csv=root / "source-model-sensitivity-summary.csv",
        report_md=root / "source-model-sensitivity.md",
        source_models_output_dir=root / "source_models",
    )


def run_structural_smc_source_model_sensitivity(
    spec: SweepSpec,
    source_models: Iterable[StructuralSMCSourceModel],
    overrides: ChildRegionOverrideSet,
    structured_pulse_candidate: StructuredPulseCandidate,
    *,
    sample_audit_csv: str | Path | None = None,
    structure_field: str = "note:requested_group_id",
    structure_regions: Iterable[str] = (),
    align_common_targets: bool = True,
    require_all_child_overrides: bool = False,
    include_default_folds: bool = True,
    include_chronology: bool = True,
    region_prefix: str = "central_europe__",
    protected_values: Iterable[str] = (),
    priority_values: Iterable[str] = (),
    explicit_folds: Iterable[StructuralSMCValidationFoldSpec] = (),
    child_candidate_name: str = "child-region-candidate",
    options: ABCSMCOptions | None = None,
    paths: StructuralSMCSourceModelSensitivityPaths | None = None,
    interval_probability: float = 0.9,
    excluded_flags: Iterable[str] = DEFAULT_TARGET_FRAGILITY_FLAGS,
    exclude_repeated_estimates: bool = True,
    repeated_estimate_tolerance: float = DEFAULT_REPEATED_ESTIMATE_TOLERANCE,
    material_chi_square_delta: float = DEFAULT_MATERIAL_CHI_SQUARE_DELTA,
    child_region_overrides_path: Path | None = None,
    command: str = "programmatic-validate-structured-smc-source-model-sensitivity",
) -> StructuralSMCSourceModelSensitivityResult:
    """Run structural validation across aligned source-model target surfaces."""
    output_paths = (
        structural_smc_source_model_sensitivity_paths_from_dir(
            "source-model-sensitivity"
        )
        if paths is None
        else paths
    )
    source_model_tuple_value = source_model_tuple(source_models)
    common_ids = common_target_ids(source_model_tuple_value, align_common_targets)
    fragile_ids = fragile_target_ids(
        sample_audit_csv,
        excluded_flags=excluded_flags,
        exclude_repeated_estimates=exclude_repeated_estimates,
        repeated_estimate_tolerance=repeated_estimate_tolerance,
    )
    retained_ids = tuple(
        target_id for target_id in common_ids if target_id not in fragile_ids
    )
    if not retained_ids:
        raise ValueError("source-model sensitivity retained no common target IDs")
    runs: list[StructuralSMCSourceModelRunResult] = []
    for source_model in source_model_tuple_value:
        prepared = _prepare_source_model_targets(
            spec,
            source_model,
            retained_ids,
            overrides,
            structured_pulse_candidate,
            structure_field=structure_field,
            structure_regions=structure_regions,
            require_all_child_overrides=require_all_child_overrides,
            include_default_folds=include_default_folds,
            include_chronology=include_chronology,
            region_prefix=region_prefix,
            protected_values=protected_values,
            priority_values=priority_values,
            explicit_folds=explicit_folds,
            child_candidate_name=child_candidate_name,
            options=options,
            paths=output_paths,
            interval_probability=interval_probability,
            material_chi_square_delta=material_chi_square_delta,
            child_region_overrides_path=child_region_overrides_path,
            command=command,
        )
        runs.append(prepared)
    result = StructuralSMCSourceModelSensitivityResult(
        runs=tuple(runs),
        common_target_ids=common_ids,
        excluded_fragile_target_ids=tuple(
            target_id for target_id in common_ids if target_id in fragile_ids
        ),
        paths=output_paths,
    )
    write_structural_smc_source_model_sensitivity_csv(result, output_paths.summary_csv)
    write_structural_smc_source_model_sensitivity_markdown(
        result, output_paths.report_md
    )
    return result


def _prepare_source_model_targets(
    spec: SweepSpec,
    source_model: StructuralSMCSourceModel,
    retained_ids: tuple[str, ...],
    overrides: ChildRegionOverrideSet,
    candidate: StructuredPulseCandidate,
    *,
    structure_field: str,
    structure_regions: Iterable[str],
    require_all_child_overrides: bool,
    include_default_folds: bool,
    include_chronology: bool,
    region_prefix: str,
    protected_values: Iterable[str],
    priority_values: Iterable[str],
    explicit_folds: Iterable[StructuralSMCValidationFoldSpec],
    child_candidate_name: str,
    options: ABCSMCOptions | None,
    paths: StructuralSMCSourceModelSensitivityPaths,
    interval_probability: float,
    material_chi_square_delta: float,
    child_region_overrides_path: Path | None,
    command: str,
) -> StructuralSMCSourceModelRunResult:
    """Prepare and validate one source-model target surface."""
    source_dir = paths.source_models_output_dir / structural_smc_validation_slug(
        source_model.label
    )
    aligned_targets = filter_targets_by_ids(source_model.targets, retained_ids)
    structured_targets, mappings = structure_target_dataset(
        aligned_targets,
        structure_field=structure_field,
        structure_regions=structure_regions,
    )
    structured_spec = structure_sweep_spec(spec, mappings)
    prepared_targets_csv = source_dir / "prepared-targets.csv"
    structured_config_toml = source_dir / "structured-config.toml"
    write_target_dataset_csv(structured_targets, prepared_targets_csv)
    write_sweep_spec_toml(structured_spec, structured_config_toml)
    filtered_overrides, missing_regions = restrict_child_region_overrides(
        overrides,
        structured_spec.initial_state.regions(),
        require_all=require_all_child_overrides,
    )
    folds = _validation_folds(
        structured_targets,
        include_default_folds=include_default_folds,
        include_chronology=include_chronology,
        region_prefix=region_prefix,
        protected_values=protected_values,
        priority_values=priority_values,
        explicit_folds=explicit_folds,
    )
    usable_folds = usable_structural_smc_validation_folds(structured_targets, folds)
    skipped_folds = tuple(fold for fold in folds if fold not in usable_folds)
    if not usable_folds:
        raise ValueError(f"{source_model.label} left no usable validation folds")
    validation_paths = structural_smc_validation_output_paths_from_dir(
        source_dir / "validation",
        config=structured_config_toml,
        targets=prepared_targets_csv,
        child_region_overrides=child_region_overrides_path,
    )
    validation = run_structural_smc_multifold_validation_workflow(
        structured_spec,
        structured_targets,
        filtered_overrides,
        candidate,
        folds=usable_folds,
        child_candidate_name=child_candidate_name,
        options=options,
        paths=validation_paths,
        interval_probability=interval_probability,
        command=f"{command}:{source_model.label}",
        manifest_metadata={
            "source_model_sensitivity": "true",
            "source_model": source_model.label,
            "missing_child_override_region_count": str(len(missing_regions)),
            "skipped_fold_count": str(len(skipped_folds)),
        },
    )
    uncertainty = load_structural_smc_uncertainty_report(
        _summary_path(validation.summary_csv_path),
        validation_paths.output_dir or source_dir / "validation",
        material_chi_square_delta=material_chi_square_delta,
    )
    uncertainty_csv = write_structural_smc_uncertainty_csv(
        uncertainty, source_dir / "structural-smc-uncertainty.csv"
    )
    uncertainty_md = write_structural_smc_uncertainty_markdown(
        uncertainty, source_dir / "structural-smc-uncertainty.md"
    )
    return StructuralSMCSourceModelRunResult(
        source_model=source_model,
        prepared_targets=structured_targets,
        validation_result=validation,
        uncertainty_report=uncertainty,
        skipped_folds=skipped_folds,
        missing_override_regions=missing_regions,
        output_dir=source_dir,
        prepared_targets_csv_path=prepared_targets_csv,
        structured_config_toml_path=structured_config_toml,
        uncertainty_csv_path=uncertainty_csv,
        uncertainty_report_md_path=uncertainty_md,
    )


def _validation_folds(
    targets: TargetDataset,
    *,
    include_default_folds: bool,
    include_chronology: bool,
    region_prefix: str,
    protected_values: Iterable[str],
    priority_values: Iterable[str],
    explicit_folds: Iterable[StructuralSMCValidationFoldSpec],
) -> tuple[StructuralSMCValidationFoldSpec, ...]:
    """Return source-model validation folds."""
    folds: list[StructuralSMCValidationFoldSpec] = []
    if include_default_folds:
        folds.extend(
            default_structural_smc_validation_folds(
                targets,
                region_prefix=region_prefix,
                protected_values=protected_values,
                priority_values=priority_values,
                include_chronology=include_chronology,
            )
        )
    folds.extend(explicit_folds)
    merged = merge_structural_smc_validation_folds(folds)
    if not merged:
        raise ValueError("source-model sensitivity requires at least one fold")
    return merged


def _summary_path(path: Path | None) -> Path:
    """Return a required validation summary path."""
    if path is None:
        raise ValueError("validation summary CSV path was not written")
    return path
