"""Reviewed dispositions for structural SMC caveat drilldown rows."""

from __future__ import annotations

import csv
from collections.abc import Iterable
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Literal, cast

StructuralSMCCaveatDisposition = Literal[
    "undecided",
    "accepted_caveat",
    "requires_qpadm_rerun",
    "configuration_gap",
    "not_applicable",
    "blocks_promotion",
]

STRUCTURAL_SMC_CAVEAT_DISPOSITIONS = frozenset(
    {
        "undecided",
        "accepted_caveat",
        "requires_qpadm_rerun",
        "configuration_gap",
        "not_applicable",
        "blocks_promotion",
    }
)
STRUCTURAL_SMC_BLOCKING_CAVEAT_DISPOSITIONS = frozenset(
    {"requires_qpadm_rerun", "configuration_gap", "blocks_promotion"}
)
STRUCTURAL_SMC_CAVEAT_KEY_COLUMNS = (
    "gate",
    "run_label",
    "caveat_type",
    "fold_name",
    "target_id",
    "requested_group_id",
)
STRUCTURAL_SMC_CAVEAT_DISPOSITION_COLUMNS = (
    *STRUCTURAL_SMC_CAVEAT_KEY_COLUMNS,
    "disposition",
    "reason",
    "reviewer",
    "decision_date",
    "note",
)
REQUIRED_STRUCTURAL_SMC_CAVEAT_DISPOSITION_COLUMNS = frozenset(
    STRUCTURAL_SMC_CAVEAT_DISPOSITION_COLUMNS
)


@dataclass(frozen=True)
class StructuralSMCCaveatDispositionRecord:
    """One reviewed disposition for a caveat drilldown row."""

    gate: str
    run_label: str
    caveat_type: str
    fold_name: str = ""
    target_id: str = ""
    requested_group_id: str = ""
    disposition: StructuralSMCCaveatDisposition = "undecided"
    reason: str = ""
    reviewer: str = ""
    decision_date: str = ""
    note: str = ""

    def __post_init__(self) -> None:
        """Normalize fields and reject unsupported reviewed dispositions."""
        for field_name in STRUCTURAL_SMC_CAVEAT_KEY_COLUMNS:
            object.__setattr__(self, field_name, getattr(self, field_name).strip())
        for field_name in ("reason", "reviewer", "decision_date", "note"):
            object.__setattr__(self, field_name, getattr(self, field_name).strip())
        if not self.gate:
            raise ValueError("gate must be non-empty")
        if not self.run_label:
            raise ValueError("run_label must be non-empty")
        if not self.caveat_type:
            raise ValueError("caveat_type must be non-empty")
        if self.disposition not in STRUCTURAL_SMC_CAVEAT_DISPOSITIONS:
            raise ValueError("disposition is not supported")
        if self.reviewed and not self.reason:
            raise ValueError("reason must be non-empty for reviewed dispositions")

    @property
    def key(self) -> tuple[str, ...]:
        """Return the caveat key fields that match drilldown CSV rows."""
        return tuple(
            getattr(self, field) for field in STRUCTURAL_SMC_CAVEAT_KEY_COLUMNS
        )

    @property
    def reviewed(self) -> bool:
        """Return whether this row has a final disposition."""
        return self.disposition != "undecided"

    @property
    def blocks_promotion(self) -> bool:
        """Return whether this disposition should block candidate promotion."""
        return self.disposition in STRUCTURAL_SMC_BLOCKING_CAVEAT_DISPOSITIONS


@dataclass(frozen=True)
class StructuralSMCCaveatDispositionDataset:
    """A validated collection of caveat disposition records."""

    records: tuple[StructuralSMCCaveatDispositionRecord, ...]

    @classmethod
    def from_rows(
        cls,
        rows: Iterable[StructuralSMCCaveatDispositionRecord],
    ) -> StructuralSMCCaveatDispositionDataset:
        """Build a dataset from disposition records."""
        return cls(tuple(rows))

    def __post_init__(self) -> None:
        """Reject duplicate caveat keys."""
        keys = [record.key for record in self.records]
        if len(set(keys)) != len(keys):
            raise ValueError("caveat disposition keys must be unique")

    def require_records(self) -> StructuralSMCCaveatDispositionDataset:
        """Return this dataset after checking that it is non-empty."""
        if not self.records:
            raise ValueError("caveat disposition dataset must contain at least one row")
        return self

    @property
    def reviewed_count(self) -> int:
        """Return reviewed disposition count."""
        return sum(record.reviewed for record in self.records)

    @property
    def blocking_count(self) -> int:
        """Return promotion-blocking disposition count."""
        return sum(record.blocks_promotion for record in self.records)


@dataclass(frozen=True)
class StructuralSMCCaveatDispositionValidationReport:
    """Validation report comparing dispositions to a caveat drilldown queue."""

    drilldown_caveat_count: int
    dispositions: StructuralSMCCaveatDispositionDataset
    missing_caveat_keys: tuple[tuple[str, ...], ...] = ()
    unknown_disposition_keys: tuple[tuple[str, ...], ...] = ()
    issues: tuple[str, ...] = ()

    @property
    def valid(self) -> bool:
        """Return whether the disposition file is structurally valid."""
        return not self.issues

    @property
    def reviewed_count(self) -> int:
        """Return reviewed disposition count."""
        return self.dispositions.reviewed_count

    @property
    def blocking_count(self) -> int:
        """Return promotion-blocking disposition count."""
        return self.dispositions.blocking_count

    @property
    def unresolved_count(self) -> int:
        """Return caveat rows without a reviewed disposition."""
        undecided = sum(
            not record.reviewed
            for record in self.dispositions.records
            if record.key not in self.unknown_disposition_keys
        )
        return len(self.missing_caveat_keys) + undecided


def load_structural_smc_caveat_dispositions(
    path: str | Path,
) -> StructuralSMCCaveatDispositionDataset:
    """Load reviewed structural SMC caveat dispositions from CSV."""
    disposition_path = Path(path)
    rows = _read_rows(
        disposition_path,
        REQUIRED_STRUCTURAL_SMC_CAVEAT_DISPOSITION_COLUMNS,
        "caveat disposition CSV",
    )
    records = tuple(
        _record_from_row(row, line_number)
        for line_number, row in enumerate(rows, start=2)
    )
    return StructuralSMCCaveatDispositionDataset.from_rows(records).require_records()


def initialize_structural_smc_caveat_disposition_template(
    drilldown_csv: str | Path,
) -> StructuralSMCCaveatDispositionDataset:
    """Return an undecided disposition template for every drilldown caveat."""
    drilldown_rows = _read_drilldown_rows(drilldown_csv)
    records = tuple(
        StructuralSMCCaveatDispositionRecord(
            gate=row["gate"],
            run_label=row["run_label"],
            caveat_type=row["caveat_type"],
            fold_name=row["fold_name"],
            target_id=row["target_id"],
            requested_group_id=row["requested_group_id"],
        )
        for row in drilldown_rows
    )
    return StructuralSMCCaveatDispositionDataset.from_rows(records).require_records()


def validate_structural_smc_caveat_dispositions(
    *,
    drilldown_csv: str | Path,
    dispositions_csv: str | Path,
) -> StructuralSMCCaveatDispositionValidationReport:
    """Validate reviewed caveat dispositions against a drilldown CSV."""
    drilldown_keys = _drilldown_keys(drilldown_csv)
    dispositions = load_structural_smc_caveat_dispositions(dispositions_csv)
    disposition_keys = {record.key for record in dispositions.records}
    missing = tuple(key for key in drilldown_keys if key not in disposition_keys)
    unknown = tuple(key for key in disposition_keys if key not in drilldown_keys)
    issues = tuple(
        f"unknown caveat disposition key: {_key_text(key)}" for key in unknown
    )
    return StructuralSMCCaveatDispositionValidationReport(
        drilldown_caveat_count=len(drilldown_keys),
        dispositions=dispositions,
        missing_caveat_keys=missing,
        unknown_disposition_keys=unknown,
        issues=issues,
    )


def structural_smc_caveat_disposition_rows(
    dataset: StructuralSMCCaveatDispositionDataset,
) -> tuple[dict[str, str], ...]:
    """Return caveat dispositions as CSV-ready rows."""
    return tuple(_record_row(record) for record in dataset.records)


def structural_smc_caveat_dispositions_to_csv(
    dataset: StructuralSMCCaveatDispositionDataset,
) -> str:
    """Return caveat dispositions serialized as CSV text."""
    dataset.require_records()
    output = StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=STRUCTURAL_SMC_CAVEAT_DISPOSITION_COLUMNS,
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerows(structural_smc_caveat_disposition_rows(dataset))
    return output.getvalue()


def write_structural_smc_caveat_dispositions_csv(
    dataset: StructuralSMCCaveatDispositionDataset,
    path: str | Path,
) -> Path:
    """Write caveat dispositions to CSV and return the output path."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        structural_smc_caveat_dispositions_to_csv(dataset), encoding="utf-8"
    )
    return output_path


def _record_from_row(
    row: dict[str, str],
    line_number: int,
) -> StructuralSMCCaveatDispositionRecord:
    """Convert one CSV row into a disposition record."""
    try:
        return StructuralSMCCaveatDispositionRecord(
            gate=row["gate"],
            run_label=row["run_label"],
            caveat_type=row["caveat_type"],
            fold_name=row["fold_name"],
            target_id=row["target_id"],
            requested_group_id=row["requested_group_id"],
            disposition=_disposition(row["disposition"]),
            reason=row["reason"],
            reviewer=row["reviewer"],
            decision_date=row["decision_date"],
            note=row["note"],
        )
    except ValueError as error:
        raise ValueError(
            f"invalid caveat disposition CSV row {line_number}: {error}"
        ) from error


def _record_row(record: StructuralSMCCaveatDispositionRecord) -> dict[str, str]:
    """Return one disposition record as a string-only row."""
    return {
        "gate": record.gate,
        "run_label": record.run_label,
        "caveat_type": record.caveat_type,
        "fold_name": record.fold_name,
        "target_id": record.target_id,
        "requested_group_id": record.requested_group_id,
        "disposition": record.disposition,
        "reason": record.reason,
        "reviewer": record.reviewer,
        "decision_date": record.decision_date,
        "note": record.note,
    }


def _drilldown_keys(path: str | Path) -> tuple[tuple[str, ...], ...]:
    """Return caveat keys from a drilldown CSV."""
    return tuple(
        tuple(row[field] for field in STRUCTURAL_SMC_CAVEAT_KEY_COLUMNS)
        for row in _read_drilldown_rows(path)
    )


def _read_drilldown_rows(path: str | Path) -> list[dict[str, str]]:
    """Read caveat drilldown rows with required key columns."""
    return _read_rows(
        Path(path), frozenset(STRUCTURAL_SMC_CAVEAT_KEY_COLUMNS), "drilldown CSV"
    )


def _read_rows(
    path: Path,
    required_columns: frozenset[str],
    description: str,
) -> list[dict[str, str]]:
    """Read CSV rows and require named columns plus data."""
    with path.open(newline="", encoding="utf-8") as input_file:
        reader = csv.DictReader(input_file)
        if reader.fieldnames is None:
            raise ValueError(f"{description} must include a header row")
        missing_columns = required_columns.difference(reader.fieldnames)
        if missing_columns:
            missing_text = ", ".join(sorted(missing_columns))
            raise ValueError(f"{description} missing columns: {missing_text}")
        rows = [{key: value or "" for key, value in row.items()} for row in reader]
    if not rows:
        raise ValueError(f"{description} must contain at least one row")
    return rows


def _disposition(value: str) -> StructuralSMCCaveatDisposition:
    """Normalize a disposition cell."""
    normalized = value.strip() or "undecided"
    if normalized not in STRUCTURAL_SMC_CAVEAT_DISPOSITIONS:
        raise ValueError("disposition is not supported")
    return cast(StructuralSMCCaveatDisposition, normalized)


def _key_text(key: tuple[str, ...]) -> str:
    """Return a compact caveat key for validation messages."""
    return "|".join(key)
