"""Ingest qpAdm rerun outputs and compare target availability changes."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path

from indoeuropop.data.aadr_curation import (
    AADRTargetInputOptions,
    AADRTargetInputs,
    load_aadr_group_selections,
    prepare_aadr_target_inputs,
    write_aadr_target_inputs,
)
from indoeuropop.data.ancestry_estimates import (
    SampleAncestryEstimate,
    SampleAncestryEstimateDataset,
    write_sample_ancestry_estimates_csv,
)
from indoeuropop.data.qpadm_estimates import (
    load_qpadm_estimate_table,
    qpadm_estimates_to_sample_ancestry_dataset,
)
from indoeuropop.data.qpadm_rerun_models import (
    QpAdmRerunIngestionConfig,
    QpAdmRerunIngestionDiagnostics,
    QpAdmRerunIngestionResult,
    QpAdmRerunTargetComparison,
    TargetAvailability,
    TargetAvailabilityChange,
    TargetBuildSnapshot,
)
from indoeuropop.data.real_targets import (
    qpadm_table_data_row_count,
    target_counts_by_region,
)
from indoeuropop.data.sample_metadata import SampleMetadataDataset
from indoeuropop.data.target_curation import TargetCurationDataset, TargetCurationRecord
from indoeuropop.data.target_decisions import (
    apply_target_decisions,
    load_target_decisions,
)
from indoeuropop.data.target_pipeline import (
    build_target_dataset,
    filter_target_inputs_for_estimates,
)
from indoeuropop.data.targets import (
    TargetDataset,
    TargetObservation,
    write_target_dataset_csv,
)
from indoeuropop.reporting.qpadm_rerun_report import (
    write_qpadm_rerun_comparison_csv,
    write_qpadm_rerun_ingestion_diagnostics_json,
    write_qpadm_rerun_report_markdown,
)


def run_qpadm_rerun_ingestion_workflow(
    config: QpAdmRerunIngestionConfig,
) -> QpAdmRerunIngestionResult:
    """Merge rerun qpAdm estimates and compare target availability changes."""
    selections = load_aadr_group_selections(config.aadr_groups_path)
    inputs = prepare_aadr_target_inputs(
        config.aadr_dir,
        selections,
        options=AADRTargetInputOptions(
            dataset_id=config.dataset_id,
            source=config.source,
            ancestry_method=config.qpadm_method,
            aggregation_method=config.aggregation_method,
            group_match_mode=config.group_match_mode,
            citation_key=config.dataset_id,
            allow_missing_groups=config.allow_missing_groups,
        ),
    )
    write_aadr_target_inputs(
        inputs,
        sample_metadata_path=config.sample_metadata_path,
        target_curation_path=config.target_curation_path,
    )

    baseline_qpadm = load_qpadm_estimate_table(config.baseline_qpadm_estimates_path)
    rerun_qpadm = load_qpadm_estimate_table(config.rerun_qpadm_estimates_path)
    baseline_estimates = qpadm_estimates_to_sample_ancestry_dataset(
        baseline_qpadm,
        source=config.source,
        method=config.qpadm_method,
        default_standard_error=config.default_standard_error,
        skip_missing_standard_error=config.skip_missing_standard_error,
    )
    rerun_estimates = qpadm_estimates_to_sample_ancestry_dataset(
        rerun_qpadm,
        source=config.source,
        method=config.qpadm_method,
        default_standard_error=config.default_standard_error,
        skip_missing_standard_error=config.skip_missing_standard_error,
    )
    merged_estimates = merge_sample_ancestry_estimate_datasets(
        baseline_estimates,
        rerun_estimates,
    )
    write_sample_ancestry_estimates_csv(
        merged_estimates, config.merged_ancestry_estimates_path
    )

    baseline_snapshot = _target_snapshot(
        inputs.sample_metadata, inputs.curation.records, baseline_estimates
    )
    post_snapshot = _target_snapshot(
        inputs.sample_metadata, inputs.curation.records, merged_estimates
    )
    if config.baseline_target_output_path is not None:
        write_target_dataset_csv(
            baseline_snapshot.targets, config.baseline_target_output_path
        )
    write_target_dataset_csv(post_snapshot.targets, config.post_target_output_path)
    accepted_targets = _accepted_targets(config, inputs, merged_estimates)

    decision_by_target = _decision_by_target(config.target_decisions_path)
    comparisons = compare_qpadm_rerun_targets(
        inputs.curation.records,
        baseline_snapshot.target_by_id,
        post_snapshot.target_by_id,
        decision_by_target=decision_by_target,
    )
    diagnostics = _diagnostics(
        config,
        inputs.curation.records,
        baseline_qpadm_count=len(baseline_qpadm),
        rerun_qpadm_count=len(rerun_qpadm),
        baseline_estimates=baseline_estimates,
        rerun_estimates=rerun_estimates,
        merged_estimates=merged_estimates,
        baseline_snapshot=baseline_snapshot,
        post_snapshot=post_snapshot,
        accepted_targets=accepted_targets,
        comparisons=comparisons,
        decision_by_target=decision_by_target,
    )
    write_qpadm_rerun_comparison_csv(comparisons, config.comparison_csv_path)
    write_qpadm_rerun_report_markdown(
        diagnostics,
        comparisons,
        config.report_markdown_path,
    )
    if config.diagnostics_json_path is not None:
        write_qpadm_rerun_ingestion_diagnostics_json(
            diagnostics, config.diagnostics_json_path
        )
    return QpAdmRerunIngestionResult(
        baseline_targets=baseline_snapshot.targets,
        post_targets=post_snapshot.targets,
        accepted_targets=accepted_targets,
        merged_ancestry_estimates=merged_estimates,
        comparisons=comparisons,
        diagnostics=diagnostics,
    )


def merge_sample_ancestry_estimate_datasets(
    baseline: SampleAncestryEstimateDataset,
    rerun: SampleAncestryEstimateDataset,
) -> SampleAncestryEstimateDataset:
    """Merge sample estimates, preferring validated rerun rows by identity."""
    rerun_by_key = {_estimate_key(estimate): estimate for estimate in rerun.estimates}
    merged: list[SampleAncestryEstimate] = []
    seen_keys: set[tuple[str, str, str]] = set()
    for estimate in baseline.estimates:
        key = _estimate_key(estimate)
        merged.append(rerun_by_key.get(key, estimate))
        seen_keys.add(key)
    for estimate in rerun.estimates:
        key = _estimate_key(estimate)
        if key not in seen_keys:
            merged.append(estimate)
    return SampleAncestryEstimateDataset.from_rows(merged).require_estimates()


def compare_qpadm_rerun_targets(
    curation_records: Iterable[TargetCurationRecord],
    baseline_target_by_id: Mapping[str, TargetObservation],
    post_target_by_id: Mapping[str, TargetObservation],
    *,
    decision_by_target: Mapping[str, str] | None = None,
) -> tuple[QpAdmRerunTargetComparison, ...]:
    """Compare target availability and values before and after rerun ingestion."""
    decisions = {} if decision_by_target is None else decision_by_target
    return tuple(
        _target_comparison(
            record,
            baseline_target_by_id.get(record.target_id),
            post_target_by_id.get(record.target_id),
            decision=decisions.get(record.target_id, ""),
        )
        for record in curation_records
    )


def _accepted_targets(
    config: QpAdmRerunIngestionConfig,
    inputs: AADRTargetInputs,
    merged_estimates: SampleAncestryEstimateDataset,
) -> TargetDataset | None:
    """Build and optionally write decision-filtered accepted targets."""
    if config.accepted_target_output_path is None:
        return None
    if config.target_decisions_path is None:
        raise ValueError("accepted_target_output_path requires target_decisions_path")
    decisions = load_target_decisions(config.target_decisions_path)
    accepted_inputs = apply_target_decisions(
        inputs.sample_metadata,
        inputs.curation,
        decisions,
    )
    accepted_snapshot = _target_snapshot(
        accepted_inputs.sample_metadata,
        accepted_inputs.curation.records,
        merged_estimates,
    )
    write_target_dataset_csv(
        accepted_snapshot.targets,
        config.accepted_target_output_path,
    )
    return accepted_snapshot.targets


def _target_snapshot(
    sample_metadata: SampleMetadataDataset,
    curation_records: tuple[TargetCurationRecord, ...],
    estimates: SampleAncestryEstimateDataset,
) -> TargetBuildSnapshot:
    """Build target outputs and a target-ID lookup for one estimate dataset."""
    curation = TargetCurationDataset.from_rows(curation_records).require_records()
    filtered = filter_target_inputs_for_estimates(sample_metadata, curation, estimates)
    targets = build_target_dataset(
        filtered.sample_metadata, filtered.curation, estimates
    )
    return TargetBuildSnapshot(
        filtered=filtered,
        targets=targets,
        target_by_id={
            record.target_id: observation
            for record, observation in zip(
                filtered.curation.records,
                targets.observations,
                strict=True,
            )
        },
    )


def _decision_by_target(path: Path | None) -> dict[str, str]:
    """Return target decisions keyed by target ID, or an empty mapping."""
    if path is None:
        return {}
    return {
        record.target_id: record.decision
        for record in load_target_decisions(path).records
    }


def _diagnostics(
    config: QpAdmRerunIngestionConfig,
    curation_records: tuple[TargetCurationRecord, ...],
    *,
    baseline_qpadm_count: int,
    rerun_qpadm_count: int,
    baseline_estimates: SampleAncestryEstimateDataset,
    rerun_estimates: SampleAncestryEstimateDataset,
    merged_estimates: SampleAncestryEstimateDataset,
    baseline_snapshot: TargetBuildSnapshot,
    post_snapshot: TargetBuildSnapshot,
    accepted_targets: TargetDataset | None,
    comparisons: tuple[QpAdmRerunTargetComparison, ...],
    decision_by_target: Mapping[str, str],
) -> QpAdmRerunIngestionDiagnostics:
    """Return summary counts for a completed rerun-ingestion workflow."""
    rescued = _target_ids_for_change(comparisons, "rescued")
    lost = _target_ids_for_change(comparisons, "lost")
    reviewed_rerun_ids = {
        target_id
        for target_id, decision in decision_by_target.items()
        if decision == "rerun_qpadm"
    }
    return QpAdmRerunIngestionDiagnostics(
        requested_target_count=len(curation_records),
        baseline_raw_qpadm_row_count=qpadm_table_data_row_count(
            config.baseline_qpadm_estimates_path
        ),
        rerun_raw_qpadm_row_count=qpadm_table_data_row_count(
            config.rerun_qpadm_estimates_path
        ),
        baseline_parsed_qpadm_estimate_count=baseline_qpadm_count,
        rerun_parsed_qpadm_estimate_count=rerun_qpadm_count,
        baseline_sample_estimate_count=baseline_estimates.estimate_count,
        rerun_sample_estimate_count=rerun_estimates.estimate_count,
        merged_sample_estimate_count=merged_estimates.estimate_count,
        baseline_target_observation_count=len(baseline_snapshot.targets.observations),
        post_target_observation_count=len(post_snapshot.targets.observations),
        accepted_target_observation_count=(
            None if accepted_targets is None else len(accepted_targets.observations)
        ),
        rescued_target_count=len(rescued),
        lost_target_count=len(lost),
        unchanged_retained_target_count=_change_count(
            comparisons, "unchanged_retained"
        ),
        unchanged_dropped_target_count=_change_count(comparisons, "unchanged_dropped"),
        reviewed_rerun_target_count=len(reviewed_rerun_ids),
        rescued_reviewed_rerun_target_count=len(set(rescued) & reviewed_rerun_ids),
        rescued_target_ids=rescued,
        lost_target_ids=lost,
        post_target_counts_by_region=target_counts_by_region(post_snapshot.targets),
    )


def _target_comparison(
    record: TargetCurationRecord,
    baseline: TargetObservation | None,
    post: TargetObservation | None,
    *,
    decision: str,
) -> QpAdmRerunTargetComparison:
    """Return one target-level pre/post comparison."""
    baseline_status = _availability(baseline)
    post_status = _availability(post)
    return QpAdmRerunTargetComparison(
        target_id=record.target_id,
        region=record.region,
        source=record.source,
        decision=decision,
        baseline_status=baseline_status,
        post_status=post_status,
        change=_availability_change(baseline_status, post_status),
        baseline_mean=None if baseline is None else baseline.mean,
        post_mean=None if post is None else post.mean,
        mean_delta=_mean_delta(baseline, post),
        baseline_uncertainty=None if baseline is None else baseline.uncertainty,
        post_uncertainty=None if post is None else post.uncertainty,
    )


def _availability(observation: TargetObservation | None) -> TargetAvailability:
    """Return the target availability label for an optional observation."""
    return "dropped" if observation is None else "retained"


def _availability_change(
    baseline_status: TargetAvailability, post_status: TargetAvailability
) -> TargetAvailabilityChange:
    """Return the categorical availability change between two states."""
    if baseline_status == "dropped" and post_status == "retained":
        return "rescued"
    if baseline_status == "retained" and post_status == "dropped":
        return "lost"
    if baseline_status == "retained":
        return "unchanged_retained"
    return "unchanged_dropped"


def _mean_delta(
    baseline: TargetObservation | None, post: TargetObservation | None
) -> float | None:
    """Return post-rerun minus baseline mean when both observations exist."""
    if baseline is None or post is None:
        return None
    return post.mean - baseline.mean


def _target_ids_for_change(
    comparisons: Iterable[QpAdmRerunTargetComparison],
    change: TargetAvailabilityChange,
) -> tuple[str, ...]:
    """Return target IDs with one availability-change label."""
    return tuple(
        comparison.target_id
        for comparison in comparisons
        if comparison.change == change
    )


def _change_count(
    comparisons: Iterable[QpAdmRerunTargetComparison],
    change: TargetAvailabilityChange,
) -> int:
    """Return the number of comparisons with one availability-change label."""
    return sum(1 for comparison in comparisons if comparison.change == change)


def _estimate_key(estimate: SampleAncestryEstimate) -> tuple[str, str, str]:
    """Return the merge identity for one sample ancestry estimate."""
    return (estimate.sample_id, estimate.source, estimate.method)
