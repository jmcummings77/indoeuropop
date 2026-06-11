"""Shared qpAdm rerun-ingestion data types."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from math import isfinite
from pathlib import Path
from typing import Literal

from indoeuropop.data.aadr import DEFAULT_AADR_DATASET_ID
from indoeuropop.data.aadr_curation import (
    DEFAULT_AADR_AGGREGATION_METHOD,
    AADRGroupMatchMode,
)
from indoeuropop.data.ancestry_estimates import SampleAncestryEstimateDataset
from indoeuropop.data.qpadm_estimates import (
    DEFAULT_QPADM_METHOD,
    DEFAULT_QPADM_SOURCE,
)
from indoeuropop.data.target_pipeline import TargetInputFilterResult
from indoeuropop.data.targets import TargetDataset, TargetObservation

TargetAvailability = Literal["retained", "dropped"]
TargetAvailabilityChange = Literal[
    "rescued", "lost", "unchanged_retained", "unchanged_dropped"
]

QPADM_RERUN_COMPARISON_COLUMNS = (
    "target_id",
    "region",
    "source",
    "decision",
    "baseline_status",
    "post_status",
    "change",
    "baseline_mean",
    "post_mean",
    "mean_delta",
    "baseline_uncertainty",
    "post_uncertainty",
)


@dataclass(frozen=True)
class QpAdmRerunIngestionConfig:
    """Paths and options for comparing baseline and rerun qpAdm outputs."""

    aadr_dir: Path
    aadr_groups_path: Path
    baseline_qpadm_estimates_path: Path
    rerun_qpadm_estimates_path: Path
    sample_metadata_path: Path
    target_curation_path: Path
    merged_ancestry_estimates_path: Path
    post_target_output_path: Path
    comparison_csv_path: Path
    report_markdown_path: Path
    diagnostics_json_path: Path | None = None
    baseline_target_output_path: Path | None = None
    accepted_target_output_path: Path | None = None
    target_decisions_path: Path | None = None
    dataset_id: str = DEFAULT_AADR_DATASET_ID
    source: str = DEFAULT_QPADM_SOURCE
    qpadm_method: str = DEFAULT_QPADM_METHOD
    aggregation_method: str = DEFAULT_AADR_AGGREGATION_METHOD
    group_match_mode: AADRGroupMatchMode = "exact"
    allow_missing_groups: bool = False
    default_standard_error: float | None = None
    skip_missing_standard_error: bool = True


@dataclass(frozen=True)
class QpAdmRerunTargetComparison:
    """One target's availability and observed value before and after a rerun."""

    target_id: str
    region: str
    source: str
    decision: str
    baseline_status: TargetAvailability
    post_status: TargetAvailability
    change: TargetAvailabilityChange
    baseline_mean: float | None
    post_mean: float | None
    mean_delta: float | None
    baseline_uncertainty: float | None
    post_uncertainty: float | None

    def __post_init__(self) -> None:
        """Validate comparison labels and optional numeric fields."""
        for field_name in ("target_id", "region", "source"):
            if not getattr(self, field_name):
                raise ValueError(f"{field_name} must be non-empty")
        if self.baseline_status not in ("retained", "dropped"):
            raise ValueError("baseline_status is not supported")
        if self.post_status not in ("retained", "dropped"):
            raise ValueError("post_status is not supported")
        if self.change not in (
            "rescued",
            "lost",
            "unchanged_retained",
            "unchanged_dropped",
        ):
            raise ValueError("change is not supported")
        for value in (
            self.baseline_mean,
            self.post_mean,
            self.mean_delta,
            self.baseline_uncertainty,
            self.post_uncertainty,
        ):
            if value is not None and not isfinite(value):
                raise ValueError("numeric comparison fields must be finite")


@dataclass(frozen=True)
class QpAdmRerunIngestionDiagnostics:
    """Summary counts for one qpAdm rerun-ingestion comparison."""

    requested_target_count: int
    baseline_raw_qpadm_row_count: int
    rerun_raw_qpadm_row_count: int
    baseline_parsed_qpadm_estimate_count: int
    rerun_parsed_qpadm_estimate_count: int
    baseline_sample_estimate_count: int
    rerun_sample_estimate_count: int
    merged_sample_estimate_count: int
    baseline_target_observation_count: int
    post_target_observation_count: int
    accepted_target_observation_count: int | None
    rescued_target_count: int
    lost_target_count: int
    unchanged_retained_target_count: int
    unchanged_dropped_target_count: int
    reviewed_rerun_target_count: int
    rescued_reviewed_rerun_target_count: int
    rescued_target_ids: tuple[str, ...]
    lost_target_ids: tuple[str, ...]
    post_target_counts_by_region: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class QpAdmRerunIngestionResult:
    """Outputs from comparing baseline qpAdm estimates with rerun estimates."""

    baseline_targets: TargetDataset
    post_targets: TargetDataset
    accepted_targets: TargetDataset | None
    merged_ancestry_estimates: SampleAncestryEstimateDataset
    comparisons: tuple[QpAdmRerunTargetComparison, ...]
    diagnostics: QpAdmRerunIngestionDiagnostics


@dataclass(frozen=True)
class TargetBuildSnapshot:
    """Target-building outputs keyed by target curation identity."""

    filtered: TargetInputFilterResult
    targets: TargetDataset
    target_by_id: Mapping[str, TargetObservation]
