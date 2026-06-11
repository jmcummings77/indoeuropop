"""Prepare target-pipeline inputs from local AADR metadata."""

from __future__ import annotations

import csv
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal

from indoeuropop.aadr import DEFAULT_AADR_DATASET_ID, load_aadr_sample_metadata
from indoeuropop.sample_metadata import (
    SampleMetadataDataset,
    SampleMetadataRecord,
    write_sample_metadata_csv,
)
from indoeuropop.target_curation import (
    TargetCurationDataset,
    TargetCurationRecord,
    write_target_curation_csv,
)

AADRGroupMatchMode = Literal["exact", "prefix"]

DEFAULT_AADR_TARGET_SOURCE = "steppe"
DEFAULT_AADR_ANCESTRY_METHOD = "external_autosomal_steppe_required"
DEFAULT_AADR_AGGREGATION_METHOD = "unweighted_mean"
DEFAULT_AADR_CURATION_CITATION = (
    "AADR v66.1 1240K public annotation metadata; sample-level ancestry "
    "estimates required separately"
)


@dataclass(frozen=True)
class AADRGroupSelection:
    """One reviewed AADR group selection for target-input preparation.

    `region` is the modeled project region to assign to matching samples, while
    `group_id` is an AADR group label or prefix depending on the match mode.
    """

    region: str
    group_id: str

    def __post_init__(self) -> None:
        """Validate the group-selection fields."""
        if not self.region:
            raise ValueError("region must be non-empty")
        if not self.group_id:
            raise ValueError("group_id must be non-empty")


@dataclass(frozen=True)
class AADRTargetInputOptions:
    """Controls for preparing AADR-derived target-pipeline inputs."""

    dataset_id: str = DEFAULT_AADR_DATASET_ID
    source: str = DEFAULT_AADR_TARGET_SOURCE
    ancestry_method: str = DEFAULT_AADR_ANCESTRY_METHOD
    aggregation_method: str = DEFAULT_AADR_AGGREGATION_METHOD
    group_match_mode: AADRGroupMatchMode = "exact"
    citation_key: str = DEFAULT_AADR_DATASET_ID
    citation: str = DEFAULT_AADR_CURATION_CITATION
    allow_missing_groups: bool = False

    def __post_init__(self) -> None:
        """Validate target-input preparation options."""
        for field_name in (
            "dataset_id",
            "source",
            "ancestry_method",
            "aggregation_method",
            "citation_key",
            "citation",
        ):
            if not getattr(self, field_name):
                raise ValueError(f"{field_name} must be non-empty")
        if self.group_match_mode not in ("exact", "prefix"):
            raise ValueError("group_match_mode must be 'exact' or 'prefix'")


@dataclass(frozen=True)
class AADRTargetInputs:
    """AADR-derived inputs ready for the target-building stage."""

    sample_metadata: SampleMetadataDataset
    curation: TargetCurationDataset
    unmatched_selections: tuple[AADRGroupSelection, ...] = ()


@dataclass(frozen=True)
class AADRTargetInputPaths:
    """Paths written by an AADR target-input export."""

    sample_metadata_path: Path
    target_curation_path: Path


def load_aadr_group_selections(path: str | Path) -> tuple[AADRGroupSelection, ...]:
    """Load region/group selections from a two-column TSV or CSV file.

    Blank lines and lines starting with `#` are ignored. A header row with
    `region` and `aadr_group_id` or `group_id` is optional.
    """
    selection_path = Path(path)
    lines = tuple(
        line
        for line in selection_path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )
    if not lines:
        raise ValueError("AADR group selection file must contain at least one row")
    delimiter = "\t" if "\t" in lines[0] else ","
    rows = tuple(csv.reader(lines, delimiter=delimiter))
    data_rows = rows[1:] if _is_group_header(rows[0]) else rows
    selections = tuple(
        _selection_from_row(row, index) for index, row in enumerate(data_rows, 1)
    )
    if not selections:
        raise ValueError("AADR group selection file must contain data rows")
    return selections


def prepare_aadr_target_inputs(
    aadr_directory: str | Path,
    selections: Iterable[AADRGroupSelection],
    *,
    options: AADRTargetInputOptions | None = None,
) -> AADRTargetInputs:
    """Prepare real AADR sample metadata and curation rows for target building.

    The returned sample metadata is filtered to selected AADR groups and remaps
    each selected sample's raw AADR political entity into the modeled region
    from the corresponding group-selection row.
    """
    target_options = AADRTargetInputOptions() if options is None else options
    selection_tuple = tuple(selections)
    if not selection_tuple:
        raise ValueError("at least one AADR group selection is required")
    metadata = load_aadr_sample_metadata(
        aadr_directory,
        dataset_id=target_options.dataset_id,
    )
    return build_aadr_target_inputs(metadata, selection_tuple, options=target_options)


def build_aadr_target_inputs(
    sample_metadata: SampleMetadataDataset,
    selections: Sequence[AADRGroupSelection],
    *,
    options: AADRTargetInputOptions | None = None,
) -> AADRTargetInputs:
    """Build target-pipeline inputs from normalized AADR sample metadata."""
    target_options = AADRTargetInputOptions() if options is None else options
    if not selections:
        raise ValueError("at least one AADR group selection is required")
    matches: list[tuple[AADRGroupSelection, tuple[SampleMetadataRecord, ...]]] = []
    unmatched_selections: list[AADRGroupSelection] = []
    for selection in selections:
        matched = _matching_records(sample_metadata.records, selection, target_options)
        if not matched:
            if target_options.allow_missing_groups:
                unmatched_selections.append(selection)
                continue
            raise ValueError(
                f"AADR group selection matched no samples: {selection.group_id}"
            )
        matches.append((selection, matched))
    match_tuple = tuple(matches)
    if not match_tuple:
        raise ValueError("AADR group selections matched no samples")
    remapped_metadata = _remapped_sample_metadata(sample_metadata.records, match_tuple)
    curation = TargetCurationDataset.from_rows(
        _curation_record(selection, records, target_options)
        for selection, records in match_tuple
    ).require_records()
    return AADRTargetInputs(
        remapped_metadata,
        curation,
        tuple(unmatched_selections),
    )


def write_aadr_target_inputs(
    inputs: AADRTargetInputs,
    *,
    sample_metadata_path: str | Path,
    target_curation_path: str | Path,
) -> AADRTargetInputPaths:
    """Write prepared AADR target inputs and return their paths."""
    return AADRTargetInputPaths(
        sample_metadata_path=write_sample_metadata_csv(
            inputs.sample_metadata,
            sample_metadata_path,
        ),
        target_curation_path=write_target_curation_csv(
            inputs.curation,
            target_curation_path,
        ),
    )


def _matching_records(
    records: tuple[SampleMetadataRecord, ...],
    selection: AADRGroupSelection,
    options: AADRTargetInputOptions,
) -> tuple[SampleMetadataRecord, ...]:
    """Return metadata rows matching one AADR group selection."""
    return tuple(
        record
        for record in records
        if _group_matches(
            _aadr_group_id(record),
            selection.group_id,
            options.group_match_mode,
        )
    )


def _remapped_sample_metadata(
    records: tuple[SampleMetadataRecord, ...],
    matches: tuple[tuple[AADRGroupSelection, tuple[SampleMetadataRecord, ...]], ...],
) -> SampleMetadataDataset:
    """Return selected sample metadata with group-reviewed modeled regions."""
    sample_regions: dict[str, str] = {}
    for selection, matched_records in matches:
        for record in matched_records:
            existing_region = sample_regions.get(record.sample_id)
            if existing_region is not None and existing_region != selection.region:
                raise ValueError(
                    f"sample {record.sample_id} maps to multiple modeled regions"
                )
            sample_regions[record.sample_id] = selection.region
    return SampleMetadataDataset.from_rows(
        replace(record, region=sample_regions[record.sample_id])
        for record in records
        if record.sample_id in sample_regions
    ).require_records()


def _curation_record(
    selection: AADRGroupSelection,
    records: tuple[SampleMetadataRecord, ...],
    options: AADRTargetInputOptions,
) -> TargetCurationRecord:
    """Build one target-curation row from selected AADR sample metadata."""
    times = tuple(record.time_bce for record in records)
    group_ids = tuple(_aadr_group_id(record) for record in records)
    publication_keys = tuple(record.publication_key for record in records)
    return TargetCurationRecord(
        status="published",
        target_id=_target_id(selection, options),
        region=selection.region,
        source=options.source,
        start_bce=max(times),
        end_bce=min(times),
        sample_ids=tuple(record.sample_id for record in records),
        sample_count=len(records),
        ancestry_method=options.ancestry_method,
        aggregation_method=options.aggregation_method,
        citation_key=options.citation_key,
        citation=options.citation,
        note=(
            f"requested_group_id={selection.group_id}; "
            f"group_match_mode={options.group_match_mode}; "
            f"matched_group_ids={_summarized_values(group_ids)}; "
            f"publication_keys={_summarized_values(publication_keys)}"
        ),
    )


def _selection_from_row(row: list[str], row_number: int) -> AADRGroupSelection:
    """Convert one group-selection CSV row into a validated selection."""
    if len(row) < 2:
        raise ValueError(f"AADR group selection row {row_number} needs two columns")
    return AADRGroupSelection(region=row[0].strip(), group_id=row[1].strip())


def _is_group_header(row: list[str]) -> bool:
    """Return whether a group-selection row looks like a header."""
    lowered = tuple(value.strip().lower() for value in row)
    return (
        len(lowered) >= 2
        and lowered[0] == "region"
        and lowered[1]
        in {
            "aadr_group_id",
            "group_id",
        }
    )


def _aadr_group_id(record: SampleMetadataRecord) -> str:
    """Extract the AADR group ID preserved in a sample-metadata note."""
    prefix = "group_id="
    for part in record.note.split(";"):
        cleaned = part.strip()
        if cleaned.startswith(prefix):
            return cleaned.removeprefix(prefix)
    raise ValueError(f"sample {record.sample_id} is missing an AADR group_id note")


def _group_matches(
    observed_group_id: str,
    requested_group_id: str,
    mode: AADRGroupMatchMode,
) -> bool:
    """Return whether an observed AADR group satisfies the selection."""
    if mode == "exact":
        return observed_group_id == requested_group_id
    return observed_group_id.startswith(requested_group_id)


def _target_id(
    selection: AADRGroupSelection,
    options: AADRTargetInputOptions,
) -> str:
    """Return a stable target identifier for one AADR group selection."""
    raw = f"aadr-{selection.region}-{options.source}-{selection.group_id}"
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", raw.lower())).strip("-")


def _summarized_values(values: Iterable[str], *, limit: int = 8) -> str:
    """Return a compact pipe-delimited summary of unique values."""
    unique_values: list[str] = []
    for value in values:
        if value not in unique_values:
            unique_values.append(value)
    shown = unique_values[:limit]
    suffix = "" if len(unique_values) <= limit else f"|+{len(unique_values) - limit}"
    return "|".join(shown) + suffix
