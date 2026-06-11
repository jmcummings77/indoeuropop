"""Build target observations from curated sample-level ancestry estimates."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from math import isfinite, sqrt
from pathlib import Path

from indoeuropop.ancestry_estimates import (
    SampleAncestryEstimate,
    SampleAncestryEstimateDataset,
    load_sample_ancestry_estimates,
)
from indoeuropop.sample_metadata import (
    SampleMetadataDataset,
    SampleMetadataRecord,
    load_sample_metadata,
)
from indoeuropop.target_curation import (
    TargetCurationDataset,
    TargetCurationRecord,
    load_target_curation,
)
from indoeuropop.targets import TargetDataset, TargetObservation

UNWEIGHTED_MEAN_METHODS = frozenset({"mean", "synthetic_mean", "unweighted_mean"})
PRECISION_WEIGHTED_METHODS = frozenset(
    {"inverse_variance_weighted_mean", "precision_weighted_mean"}
)
SUPPORTED_AGGREGATION_METHODS = UNWEIGHTED_MEAN_METHODS | PRECISION_WEIGHTED_METHODS


@dataclass(frozen=True)
class TargetBuildOptions:
    """Validation and aggregation controls for target construction.

    `minimum_uncertainty` is a lower bound on the one-sigma target uncertainty.
    It should be used only when a project has documented a defensible reporting
    floor; sample-level standard errors are otherwise propagated directly.
    """

    minimum_uncertainty: float = 0.0
    require_region_match: bool = True
    require_time_window_match: bool = True

    def __post_init__(self) -> None:
        """Validate target-building options."""
        if (
            not isfinite(self.minimum_uncertainty)
            or self.minimum_uncertainty < 0
            or self.minimum_uncertainty > 1
        ):
            raise ValueError("minimum_uncertainty must be a finite proportion")


def build_target_dataset(
    sample_metadata: SampleMetadataDataset,
    curation: TargetCurationDataset,
    estimates: SampleAncestryEstimateDataset,
    *,
    options: TargetBuildOptions | None = None,
) -> TargetDataset:
    """Aggregate curated sample estimates into target observations.

    The builder preserves the existing guardrail that observed targets are
    derived outside simulator code. It requires every curation sample to have
    metadata and a matching sample-level ancestry estimate for the requested
    source and ancestry method.
    """
    build_options = TargetBuildOptions() if options is None else options
    metadata_by_id = _sample_metadata_by_id(sample_metadata.require_records().records)
    estimates.require_estimates()
    observations = tuple(
        _build_observation(record, metadata_by_id, estimates, build_options)
        for record in curation.require_records().records
    )
    return TargetDataset.from_rows(observations).require_observations()


def load_and_build_target_dataset(
    *,
    sample_metadata_path: str | Path,
    curation_path: str | Path,
    estimates_path: str | Path,
    options: TargetBuildOptions | None = None,
) -> TargetDataset:
    """Load target-pipeline inputs from CSV files and build target rows."""
    return build_target_dataset(
        load_sample_metadata(sample_metadata_path),
        load_target_curation(curation_path),
        load_sample_ancestry_estimates(estimates_path),
        options=options,
    )


def _build_observation(
    curation: TargetCurationRecord,
    metadata_by_id: Mapping[str, SampleMetadataRecord],
    estimates: SampleAncestryEstimateDataset,
    options: TargetBuildOptions,
) -> TargetObservation:
    """Build one target observation from one curation row."""
    sample_metadata = tuple(
        _metadata_for_sample(curation, metadata_by_id, sample_id)
        for sample_id in curation.sample_ids
    )
    sample_estimates = tuple(
        estimates.estimate_for(
            sample_id=sample_id,
            source=curation.source,
            method=curation.ancestry_method,
        )
        for sample_id in curation.sample_ids
    )
    _validate_curation_links(curation, sample_metadata, sample_estimates, options)
    weights = _aggregation_weights(curation.aggregation_method, sample_estimates)
    mean = sum(
        weight * estimate.estimate
        for weight, estimate in zip(weights, sample_estimates, strict=True)
    )
    uncertainty = _target_uncertainty(weights, sample_estimates, mean, options)
    return TargetObservation(
        status=curation.status,
        region=curation.region,
        source=curation.source,
        time_bce=_mean(record.time_bce for record in sample_metadata),
        mean=mean,
        uncertainty=uncertainty,
        citation_key=curation.citation_key,
        citation=curation.citation,
        note=_target_note(curation),
    )


def _sample_metadata_by_id(
    records: Iterable[SampleMetadataRecord],
) -> dict[str, SampleMetadataRecord]:
    """Return sample metadata keyed by sample ID, rejecting ambiguous IDs."""
    metadata_by_id: dict[str, SampleMetadataRecord] = {}
    for record in records:
        if record.sample_id in metadata_by_id:
            raise ValueError(f"ambiguous sample_id in metadata: {record.sample_id}")
        metadata_by_id[record.sample_id] = record
    return metadata_by_id


def _metadata_for_sample(
    curation: TargetCurationRecord,
    metadata_by_id: Mapping[str, SampleMetadataRecord],
    sample_id: str,
) -> SampleMetadataRecord:
    """Return metadata for one curated sample or fail with target context."""
    if sample_id not in metadata_by_id:
        raise ValueError(
            f"target {curation.target_id} references missing sample_id={sample_id}"
        )
    return metadata_by_id[sample_id]


def _validate_curation_links(
    curation: TargetCurationRecord,
    sample_metadata: tuple[SampleMetadataRecord, ...],
    estimates: tuple[SampleAncestryEstimate, ...],
    options: TargetBuildOptions,
) -> None:
    """Validate linked sample metadata and ancestry estimates for one target."""
    statuses = {
        curation.status,
        *(record.status for record in sample_metadata),
        *(estimate.status for estimate in estimates),
    }
    if len(statuses) != 1:
        raise ValueError(f"target {curation.target_id} mixes input statuses")
    for record in sample_metadata:
        if options.require_region_match and record.region != curation.region:
            raise ValueError(
                f"target {curation.target_id} sample {record.sample_id} "
                f"has region {record.region}, expected {curation.region}"
            )
        if options.require_time_window_match and not (
            curation.end_bce <= record.time_bce <= curation.start_bce
        ):
            raise ValueError(
                f"target {curation.target_id} sample {record.sample_id} "
                "falls outside the curation time window"
            )


def _aggregation_weights(
    aggregation_method: str,
    estimates: tuple[SampleAncestryEstimate, ...],
) -> tuple[float, ...]:
    """Return normalized sample weights for one supported aggregation method."""
    if aggregation_method in UNWEIGHTED_MEAN_METHODS:
        return tuple(1.0 / len(estimates) for _ in estimates)
    if aggregation_method in PRECISION_WEIGHTED_METHODS:
        inverse_variances = tuple(
            1.0 / (estimate.standard_error**2) for estimate in estimates
        )
        total_inverse_variance = sum(inverse_variances)
        return tuple(value / total_inverse_variance for value in inverse_variances)
    raise ValueError(f"unsupported aggregation_method: {aggregation_method}")


def _target_uncertainty(
    weights: tuple[float, ...],
    estimates: tuple[SampleAncestryEstimate, ...],
    mean: float,
    options: TargetBuildOptions,
) -> float:
    """Return propagated one-sigma uncertainty for an aggregated target."""
    measurement_variance = sum(
        (weight * estimate.standard_error) ** 2
        for weight, estimate in zip(weights, estimates, strict=True)
    )
    dispersion_variance = _dispersion_variance(weights, estimates, mean)
    uncertainty = sqrt(measurement_variance + dispersion_variance)
    uncertainty = max(uncertainty, options.minimum_uncertainty)
    if not isfinite(uncertainty) or uncertainty <= 0 or uncertainty > 1:
        raise ValueError("aggregated target uncertainty is outside (0, 1]")
    return uncertainty


def _dispersion_variance(
    weights: tuple[float, ...],
    estimates: tuple[SampleAncestryEstimate, ...],
    mean: float,
) -> float:
    """Return between-sample dispersion variance for a weighted mean."""
    if len(estimates) == 1:
        return 0.0
    effective_count = 1.0 / sum(weight**2 for weight in weights)
    weighted_dispersion = sum(
        weight * (estimate.estimate - mean) ** 2
        for weight, estimate in zip(weights, estimates, strict=True)
    )
    return weighted_dispersion / effective_count


def _mean(values: Iterable[float]) -> float:
    """Return the arithmetic mean of at least one numeric value."""
    value_tuple = tuple(values)
    if not value_tuple:
        raise ValueError("cannot average an empty collection")
    return sum(value_tuple) / len(value_tuple)


def _target_note(curation: TargetCurationRecord) -> str:
    """Return a target note preserving curation context."""
    generated_note = (
        f"target_id={curation.target_id}; "
        f"sample_count={curation.sample_count}; "
        f"window_bce={curation.start_bce:.12g}-{curation.end_bce:.12g}; "
        f"aggregation_method={curation.aggregation_method}"
    )
    if curation.note:
        return f"{curation.note}; {generated_note}"
    return generated_note
