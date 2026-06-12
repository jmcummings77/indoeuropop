"""Fit-metric sensitivity workflows for structural SMC validation."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace
from pathlib import Path

from indoeuropop.analysis.abc_smc import ABCSMCOptions
from indoeuropop.analysis.structural_head_to_head import StructuredPulseCandidate
from indoeuropop.data.targets import TargetDataset, write_target_dataset_csv
from indoeuropop.orchestration.child_region_overrides import ChildRegionOverrideSet
from indoeuropop.orchestration.structural_smc_metric_sensitivity_models import (
    DEFAULT_STRUCTURAL_SMC_FIT_METRICS,
    StructuralSMCFitMetricRunResult,
    StructuralSMCFitMetricSensitivityPaths,
    StructuralSMCFitMetricSensitivityResult,
)
from indoeuropop.orchestration.structural_smc_validation import (
    run_structural_smc_multifold_validation_workflow,
)
from indoeuropop.orchestration.structural_smc_validation_models import (
    StructuralSMCValidationFoldSpec,
    structural_smc_validation_slug,
)
from indoeuropop.orchestration.structural_smc_validation_outputs import (
    structural_smc_validation_output_paths_from_dir,
)
from indoeuropop.orchestration.sweeps import SweepSpec
from indoeuropop.orchestration.target_fragility import (
    filter_targets_by_fragility,
    load_target_fragility_decisions,
    usable_structural_smc_validation_folds,
)
from indoeuropop.orchestration.target_fragility_models import (
    DEFAULT_REPEATED_ESTIMATE_TOLERANCE,
    DEFAULT_TARGET_FRAGILITY_FLAGS,
)
from indoeuropop.reporting.structural_smc_metric_sensitivity import (
    write_structural_smc_fit_metric_sensitivity_csv,
    write_structural_smc_fit_metric_sensitivity_markdown,
)
from indoeuropop.reporting.structural_smc_uncertainty import (
    DEFAULT_MATERIAL_CHI_SQUARE_DELTA,
    load_structural_smc_uncertainty_report,
    write_structural_smc_uncertainty_csv,
    write_structural_smc_uncertainty_markdown,
)
from indoeuropop.reporting.target_fragility import (
    write_target_fragility_decisions_csv,
)


def structural_smc_fit_metric_sensitivity_paths_from_dir(
    output_dir: str | Path,
) -> StructuralSMCFitMetricSensitivityPaths:
    """Return conventional output paths for fit-metric sensitivity artifacts."""
    root = Path(output_dir)
    return StructuralSMCFitMetricSensitivityPaths(
        output_dir=root,
        filtered_targets_csv=root / "filtered-targets.csv",
        decisions_csv=root / "target-fragility-decisions.csv",
        summary_csv=root / "fit-metric-sensitivity-summary.csv",
        report_md=root / "fit-metric-sensitivity.md",
        metrics_output_dir=root / "metrics",
    )


def run_structural_smc_fit_metric_sensitivity(
    spec: SweepSpec,
    targets: TargetDataset,
    overrides: ChildRegionOverrideSet,
    structured_pulse_candidate: StructuredPulseCandidate,
    *,
    sample_audit_csv: str | Path,
    folds: Iterable[StructuralSMCValidationFoldSpec],
    fit_metrics: Iterable[str] = DEFAULT_STRUCTURAL_SMC_FIT_METRICS,
    child_candidate_name: str = "child-region-candidate",
    options: ABCSMCOptions | None = None,
    paths: StructuralSMCFitMetricSensitivityPaths | None = None,
    interval_probability: float = 0.9,
    excluded_flags: Iterable[str] = DEFAULT_TARGET_FRAGILITY_FLAGS,
    exclude_repeated_estimates: bool = True,
    repeated_estimate_tolerance: float = DEFAULT_REPEATED_ESTIMATE_TOLERANCE,
    material_chi_square_delta: float = DEFAULT_MATERIAL_CHI_SQUARE_DELTA,
    config_path: Path | None = None,
    child_region_overrides_path: Path | None = None,
    command: str = "programmatic-validate-structured-smc-fit-metric-sensitivity",
) -> StructuralSMCFitMetricSensitivityResult:
    """Rerun fragility-filtered structural validation under fit metrics."""
    output_paths = (
        structural_smc_fit_metric_sensitivity_paths_from_dir("fit-metric-sensitivity")
        if paths is None
        else paths
    )
    metric_names = _fit_metric_names(fit_metrics)
    decisions = load_target_fragility_decisions(
        sample_audit_csv,
        excluded_flags=excluded_flags,
        exclude_repeated_estimates=exclude_repeated_estimates,
        repeated_estimate_tolerance=repeated_estimate_tolerance,
    )
    filtered_targets = filter_targets_by_fragility(targets, decisions)
    write_target_dataset_csv(filtered_targets, output_paths.filtered_targets_csv)
    write_target_fragility_decisions_csv(decisions, output_paths.decisions_csv)
    original_folds = tuple(folds)
    usable_folds = usable_structural_smc_validation_folds(
        filtered_targets, original_folds
    )
    skipped_folds = tuple(fold for fold in original_folds if fold not in usable_folds)
    if not usable_folds:
        raise ValueError("fit-metric sensitivity left no usable validation folds")
    runs = tuple(
        _run_metric(
            spec,
            filtered_targets,
            overrides,
            structured_pulse_candidate,
            metric_name,
            folds=usable_folds,
            child_candidate_name=child_candidate_name,
            options=options,
            paths=output_paths,
            interval_probability=interval_probability,
            material_chi_square_delta=material_chi_square_delta,
            config_path=config_path,
            child_region_overrides_path=child_region_overrides_path,
            command=command,
            excluded_target_count=sum(decision.excluded for decision in decisions),
            skipped_fold_count=len(skipped_folds),
        )
        for metric_name in metric_names
    )
    result = StructuralSMCFitMetricSensitivityResult(
        decisions=decisions,
        original_targets=targets,
        filtered_targets=filtered_targets,
        skipped_folds=skipped_folds,
        runs=runs,
        paths=output_paths,
    )
    write_structural_smc_fit_metric_sensitivity_csv(result, output_paths.summary_csv)
    write_structural_smc_fit_metric_sensitivity_markdown(result, output_paths.report_md)
    return result


def _run_metric(
    spec: SweepSpec,
    targets: TargetDataset,
    overrides: ChildRegionOverrideSet,
    candidate: StructuredPulseCandidate,
    fit_metric: str,
    *,
    folds: Iterable[StructuralSMCValidationFoldSpec],
    child_candidate_name: str,
    options: ABCSMCOptions | None,
    paths: StructuralSMCFitMetricSensitivityPaths,
    interval_probability: float,
    material_chi_square_delta: float,
    config_path: Path | None,
    child_region_overrides_path: Path | None,
    command: str,
    excluded_target_count: int,
    skipped_fold_count: int,
) -> StructuralSMCFitMetricRunResult:
    """Run one metric-specific validation and uncertainty review."""
    metric_dir = paths.metrics_output_dir / structural_smc_validation_slug(fit_metric)
    validation_paths = structural_smc_validation_output_paths_from_dir(
        metric_dir / "validation",
        config=config_path,
        targets=paths.filtered_targets_csv,
        child_region_overrides=child_region_overrides_path,
    )
    metric_options = replace(
        ABCSMCOptions() if options is None else options, fit_metric=fit_metric
    )
    validation_result = run_structural_smc_multifold_validation_workflow(
        spec,
        targets,
        overrides,
        candidate,
        folds=folds,
        child_candidate_name=child_candidate_name,
        options=metric_options,
        paths=validation_paths,
        interval_probability=interval_probability,
        command=f"{command}:{fit_metric}",
        manifest_metadata={
            "fit_metric_sensitivity": "true",
            "fit_metric": fit_metric,
            "target_fragility_excluded_target_count": str(excluded_target_count),
            "target_fragility_skipped_fold_count": str(skipped_fold_count),
        },
    )
    summary_path = _summary_path(validation_result.summary_csv_path)
    uncertainty = load_structural_smc_uncertainty_report(
        summary_path,
        validation_paths.output_dir or metric_dir / "validation",
        material_chi_square_delta=material_chi_square_delta,
    )
    uncertainty_csv = write_structural_smc_uncertainty_csv(
        uncertainty, metric_dir / "structural-smc-uncertainty.csv"
    )
    uncertainty_report_md = write_structural_smc_uncertainty_markdown(
        uncertainty, metric_dir / "structural-smc-uncertainty.md"
    )
    return StructuralSMCFitMetricRunResult(
        fit_metric=fit_metric,
        validation_result=validation_result,
        uncertainty_report=uncertainty,
        output_dir=metric_dir,
        uncertainty_csv_path=uncertainty_csv,
        uncertainty_report_md_path=uncertainty_report_md,
    )


def _fit_metric_names(fit_metrics: Iterable[str]) -> tuple[str, ...]:
    """Return unique non-empty fit-metric names in request order."""
    names: list[str] = []
    for fit_metric in fit_metrics:
        name = fit_metric.strip()
        if name and name not in names:
            names.append(name)
    if not names:
        raise ValueError("fit_metrics must contain at least one metric")
    return tuple(names)


def _summary_path(path: Path | None) -> Path:
    """Return a required validation summary path."""
    if path is None:
        raise ValueError("validation summary CSV path was not written")
    return path
