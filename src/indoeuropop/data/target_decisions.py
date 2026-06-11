"""Reviewed target-level decisions applied before target observation builds."""

from __future__ import annotations

import csv
from collections.abc import Iterable
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Literal, cast

from indoeuropop.data.sample_metadata import (
    SampleMetadataDataset,
    write_sample_metadata_csv,
)
from indoeuropop.data.target_curation import (
    TargetCurationDataset,
    TargetCurationRecord,
    write_target_curation_csv,
)

TargetDecision = Literal[
    "retain", "retain_with_caveat", "exclude", "split", "rerun_qpadm"
]

TARGET_DECISIONS = frozenset(
    {"retain", "retain_with_caveat", "exclude", "split", "rerun_qpadm"}
)
TARGET_INCLUDE_DECISIONS = frozenset({"retain", "retain_with_caveat"})
TARGET_DEFER_DECISIONS = TARGET_DECISIONS - TARGET_INCLUDE_DECISIONS

TARGET_DECISION_COLUMNS = (
    "target_id",
    "decision",
    "reason",
    "requested_group_id",
    "reviewer",
    "decision_date",
    "note",
)
REQUIRED_TARGET_DECISION_COLUMNS = frozenset(TARGET_DECISION_COLUMNS)


@dataclass(frozen=True)
class TargetDecisionRecord:
    """One reviewed decision about whether a curated target enters a build."""

    target_id: str
    decision: TargetDecision
    reason: str
    requested_group_id: str = ""
    reviewer: str = ""
    decision_date: str = ""
    note: str = ""

    def __post_init__(self) -> None:
        """Validate target-decision fields."""
        if not self.target_id:
            raise ValueError("target_id must be non-empty")
        if self.decision not in TARGET_DECISIONS:
            raise ValueError("decision is not supported")
        if not self.reason:
            raise ValueError("reason must be non-empty")

    @property
    def keeps_target(self) -> bool:
        """Return whether this decision keeps the target in observation builds."""
        return self.decision in TARGET_INCLUDE_DECISIONS


@dataclass(frozen=True)
class TargetDecisionDataset:
    """A validated collection of reviewed target decisions."""

    records: tuple[TargetDecisionRecord, ...]

    @classmethod
    def from_rows(cls, rows: Iterable[TargetDecisionRecord]) -> TargetDecisionDataset:
        """Build a target-decision dataset from validated records."""
        return cls(tuple(rows))

    def __post_init__(self) -> None:
        """Validate dataset-level uniqueness."""
        target_ids = [record.target_id for record in self.records]
        if len(set(target_ids)) != len(target_ids):
            raise ValueError("target_id values must be unique")

    def require_records(self) -> TargetDecisionDataset:
        """Return this dataset after checking it has at least one decision."""
        if not self.records:
            raise ValueError("target decision dataset must contain at least one row")
        return self

    def target_ids(self) -> tuple[str, ...]:
        """Return target IDs in decision-file order."""
        return tuple(record.target_id for record in self.records)

    def decision_for(self, target_id: str) -> TargetDecisionRecord | None:
        """Return the decision record for one target, when present."""
        for record in self.records:
            if record.target_id == target_id:
                return record
        return None


@dataclass(frozen=True)
class TargetDecisionApplicationResult:
    """Target inputs retained or deferred after applying reviewed decisions."""

    sample_metadata: SampleMetadataDataset
    curation: TargetCurationDataset
    retained_target_ids: tuple[str, ...]
    deferred_target_ids: tuple[str, ...]
    undecided_target_ids: tuple[str, ...]


def load_target_decisions(path: str | Path) -> TargetDecisionDataset:
    """Load a reviewed target-decision CSV file."""
    decision_path = Path(path)
    with decision_path.open(newline="", encoding="utf-8") as decision_file:
        reader = csv.DictReader(decision_file)
        if reader.fieldnames is None:
            raise ValueError("target decision CSV must include a header row")
        missing_columns = REQUIRED_TARGET_DECISION_COLUMNS.difference(reader.fieldnames)
        if missing_columns:
            missing_text = ", ".join(sorted(missing_columns))
            raise ValueError(f"target decision CSV missing columns: {missing_text}")
        records = [
            _decision_from_row(row, line_number)
            for line_number, row in enumerate(reader, start=2)
        ]
    return TargetDecisionDataset.from_rows(records).require_records()


def apply_target_decisions(
    sample_metadata: SampleMetadataDataset,
    curation: TargetCurationDataset,
    decisions: TargetDecisionDataset,
    *,
    retain_undecided: bool = True,
) -> TargetDecisionApplicationResult:
    """Apply reviewed decisions to target curation and sample metadata.

    Targets with `retain` or `retain_with_caveat` decisions are kept. Targets
    with `exclude`, `split`, or `rerun_qpadm` decisions are deferred. Undecided
    targets are kept by default so a decision file can document one audited
    outlier without forcing every target row to be reviewed immediately.
    """
    curation_records = curation.require_records().records
    _validate_decision_targets(decisions.require_records(), curation_records)
    kept_records: list[TargetCurationRecord] = []
    retained_target_ids: list[str] = []
    deferred_target_ids: list[str] = []
    undecided_target_ids: list[str] = []
    for record in curation_records:
        decision = decisions.decision_for(record.target_id)
        if decision is None:
            undecided_target_ids.append(record.target_id)
            if retain_undecided:
                kept_records.append(record)
                retained_target_ids.append(record.target_id)
            else:
                deferred_target_ids.append(record.target_id)
        elif decision.keeps_target:
            kept_records.append(record)
            retained_target_ids.append(record.target_id)
        else:
            deferred_target_ids.append(record.target_id)
    kept_curation = TargetCurationDataset.from_rows(kept_records).require_records()
    kept_sample_ids = {
        sample_id for record in kept_curation.records for sample_id in record.sample_ids
    }
    kept_metadata = SampleMetadataDataset.from_rows(
        record
        for record in sample_metadata.require_records().records
        if record.sample_id in kept_sample_ids
    ).require_records()
    return TargetDecisionApplicationResult(
        sample_metadata=kept_metadata,
        curation=kept_curation,
        retained_target_ids=tuple(retained_target_ids),
        deferred_target_ids=tuple(deferred_target_ids),
        undecided_target_ids=tuple(undecided_target_ids),
    )


def target_decision_rows(dataset: TargetDecisionDataset) -> tuple[dict[str, str], ...]:
    """Return target decisions as CSV-ready rows."""
    return tuple(_decision_row(record) for record in dataset.records)


def target_decisions_to_csv(dataset: TargetDecisionDataset) -> str:
    """Return target decisions serialized as CSV text."""
    dataset.require_records()
    output = StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=TARGET_DECISION_COLUMNS,
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerows(target_decision_rows(dataset))
    return output.getvalue()


def write_target_decisions_csv(
    dataset: TargetDecisionDataset, path: str | Path
) -> Path:
    """Write target decisions to CSV and return the output path."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(target_decisions_to_csv(dataset), encoding="utf-8")
    return output_path


def write_decision_filtered_target_inputs(
    result: TargetDecisionApplicationResult,
    *,
    sample_metadata_path: str | Path,
    target_curation_path: str | Path,
) -> tuple[Path, Path]:
    """Write decision-filtered sample metadata and target curation CSVs."""
    return (
        write_sample_metadata_csv(result.sample_metadata, sample_metadata_path),
        write_target_curation_csv(result.curation, target_curation_path),
    )


def _decision_from_row(
    row: dict[str, str | None], line_number: int
) -> TargetDecisionRecord:
    """Convert one CSV row into a target-decision record."""
    try:
        return TargetDecisionRecord(
            target_id=_cell(row, "target_id"),
            decision=_decision(_cell(row, "decision")),
            reason=_cell(row, "reason"),
            requested_group_id=_optional_cell(row, "requested_group_id"),
            reviewer=_optional_cell(row, "reviewer"),
            decision_date=_optional_cell(row, "decision_date"),
            note=_optional_cell(row, "note"),
        )
    except ValueError as error:
        raise ValueError(
            f"invalid target decision CSV row {line_number}: {error}"
        ) from error


def _decision_row(record: TargetDecisionRecord) -> dict[str, str]:
    """Return one target-decision record as a string-only row."""
    return {
        "target_id": record.target_id,
        "decision": record.decision,
        "reason": record.reason,
        "requested_group_id": record.requested_group_id,
        "reviewer": record.reviewer,
        "decision_date": record.decision_date,
        "note": record.note,
    }


def _validate_decision_targets(
    decisions: TargetDecisionDataset,
    curation_records: tuple[TargetCurationRecord, ...],
) -> None:
    """Raise when a decision references a target absent from curation."""
    known_target_ids = {record.target_id for record in curation_records}
    unknown_target_ids = [
        target_id
        for target_id in decisions.target_ids()
        if target_id not in known_target_ids
    ]
    if unknown_target_ids:
        unknown_text = ", ".join(unknown_target_ids)
        raise ValueError(
            f"target decisions reference unknown target IDs: {unknown_text}"
        )


def _cell(row: dict[str, str | None], column: str) -> str:
    """Return a stripped required cell."""
    value = row.get(column)
    if value is None or value.strip() == "":
        raise ValueError(f"{column} is required")
    return value.strip()


def _optional_cell(row: dict[str, str | None], column: str) -> str:
    """Return a stripped optional cell."""
    value = row.get(column)
    return "" if value is None else value.strip()


def _decision(value: str) -> TargetDecision:
    """Validate and return a target decision label."""
    if value not in TARGET_DECISIONS:
        raise ValueError("decision is not supported")
    return cast(TargetDecision, value)
