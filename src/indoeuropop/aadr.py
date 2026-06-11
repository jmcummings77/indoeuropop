"""Load local Allen Ancient DNA Resource metadata files."""

from __future__ import annotations

import csv
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from indoeuropop.sample_metadata import (
    SampleMetadataDataset,
    SampleMetadataRecord,
    SampleSex,
    write_sample_metadata_csv,
)

DEFAULT_AADR_DATASET_ID = "aadr-v66-p1-1240k"
DEFAULT_AADR_METHOD = "aadr_v66_annotation"

GENETIC_ID_COLUMN_PREFIX = "Genetic ID"
DATE_MEAN_BP_COLUMN_PREFIX = "Date mean in BP"
DATE_SD_BP_COLUMN_PREFIX = "Date standard deviation in BP"
FULL_DATE_COLUMN_PREFIX = "Full Date"
FIRST_PUBLICATION_COLUMN_PREFIX = "First publication"

AADR_SEX_MAP: dict[str, SampleSex] = {
    "F": "female",
    "M": "male",
    "U": "unknown",
    "..": "unknown",
    "": "unknown",
}


@dataclass(frozen=True)
class AADRDataFiles:
    """Resolved paths for one local AADR dataset quartet."""

    annotation_path: Path
    individual_path: Path
    snp_path: Path
    genotype_path: Path


def discover_aadr_files(directory: str | Path) -> AADRDataFiles:
    """Discover AADR `.anno`, `.ind`, `.snp`, and `.geno` files in a directory."""
    root = Path(directory)
    if not root.is_dir():
        raise FileNotFoundError(f"AADR directory does not exist: {root}")
    return AADRDataFiles(
        annotation_path=_single_file(root, "*.anno"),
        individual_path=_single_file(root, "*.ind"),
        snp_path=_single_file(root, "*.snp"),
        genotype_path=_single_file(root, "*.geno"),
    )


def load_aadr_sample_metadata(
    directory: str | Path,
    *,
    dataset_id: str = DEFAULT_AADR_DATASET_ID,
    limit: int | None = None,
) -> SampleMetadataDataset:
    """Load AADR annotation metadata as normalized sample metadata records."""
    files = discover_aadr_files(directory)
    records = tuple(
        _sample_metadata_from_aadr_row(row, dataset_id=dataset_id)
        for row in _aadr_annotation_rows(files.annotation_path, limit=limit)
    )
    return SampleMetadataDataset.from_rows(records).require_records()


def write_aadr_sample_metadata_csv(
    directory: str | Path,
    output_path: str | Path,
    *,
    dataset_id: str = DEFAULT_AADR_DATASET_ID,
    limit: int | None = None,
) -> Path:
    """Load local AADR annotations and write normalized sample metadata CSV."""
    return write_sample_metadata_csv(
        load_aadr_sample_metadata(directory, dataset_id=dataset_id, limit=limit),
        output_path,
    )


def _aadr_annotation_rows(
    annotation_path: Path,
    *,
    limit: int | None,
) -> tuple[dict[str, str], ...]:
    """Return raw AADR annotation rows from a tab-separated `.anno` file."""
    if limit is not None and limit <= 0:
        raise ValueError("limit must be positive")
    with annotation_path.open(newline="", encoding="utf-8") as annotation_file:
        reader = csv.DictReader(annotation_file, delimiter="\t")
        if reader.fieldnames is None:
            raise ValueError("AADR annotation file must include a header row")
        _required_columns(reader.fieldnames)
        rows: list[dict[str, str]] = []
        for index, row in enumerate(reader):
            if limit is not None and index >= limit:
                break
            rows.append(
                {key: "" if value is None else value for key, value in row.items()}
            )
    if not rows:
        raise ValueError("AADR annotation file must contain at least one row")
    return tuple(rows)


def _sample_metadata_from_aadr_row(
    row: dict[str, str],
    *,
    dataset_id: str,
) -> SampleMetadataRecord:
    """Convert one AADR annotation row into project sample metadata."""
    genetic_id = _clean(_column_value(row, GENETIC_ID_COLUMN_PREFIX))
    persistent_id = _fallback_text(
        _clean(row.get("Persistent Genetic ID", "")), genetic_id
    )
    publication_key = _publication_key(row)
    group_id = _fallback_text(_clean(row.get("Group ID", "")), "unassigned")
    locality = _fallback_text(_clean(row.get("Locality", "")), group_id)
    political_entity = _fallback_text(_clean(row.get("Political Entity", "")), group_id)
    date_mean_bp = float(_column_value(row, DATE_MEAN_BP_COLUMN_PREFIX))
    date_sd_bp = float(_column_value(row, DATE_SD_BP_COLUMN_PREFIX))
    return SampleMetadataRecord(
        status="published",
        dataset_id=dataset_id,
        sample_id=genetic_id,
        accession_id=persistent_id,
        publication_key=publication_key,
        publication=_publication_text(row, publication_key),
        region=political_entity,
        site=locality,
        time_bce=date_mean_bp - 1950.0,
        date_uncertainty=date_sd_bp,
        sex=_sample_sex(_clean(row.get("Molecular Sex", ""))),
        method=DEFAULT_AADR_METHOD,
        note=_aadr_note(row, group_id),
    )


def _required_columns(fieldnames: Iterable[str]) -> None:
    """Validate that required AADR annotation columns are present."""
    fields = tuple(fieldnames)
    for prefix in (
        GENETIC_ID_COLUMN_PREFIX,
        DATE_MEAN_BP_COLUMN_PREFIX,
        DATE_SD_BP_COLUMN_PREFIX,
        FULL_DATE_COLUMN_PREFIX,
        FIRST_PUBLICATION_COLUMN_PREFIX,
    ):
        _column_name(fields, prefix)
    for name in (
        "Persistent Genetic ID",
        "Publication abbreviation",
        "Group ID",
        "Locality",
        "Political Entity",
        "Molecular Sex",
        "ASSESSMENT",
    ):
        if name not in fields:
            raise ValueError(f"AADR annotation missing column: {name}")


def _column_value(row: dict[str, str], prefix: str) -> str:
    """Return a value from the first AADR column matching a prefix."""
    return row[_column_name(tuple(row), prefix)].strip()


def _column_name(fieldnames: tuple[str, ...], prefix: str) -> str:
    """Return the first AADR column name matching a prefix."""
    for fieldname in fieldnames:
        if fieldname.startswith(prefix):
            return fieldname
    raise ValueError(f"AADR annotation missing column prefix: {prefix}")


def _publication_key(row: dict[str, str]) -> str:
    """Return a stable publication key for one AADR row."""
    publication = _clean(row.get("Publication abbreviation", ""))
    first_publication = _clean(_column_value(row, FIRST_PUBLICATION_COLUMN_PREFIX))
    return _fallback_text(publication, first_publication)


def _publication_text(row: dict[str, str], publication_key: str) -> str:
    """Return human-readable publication text for one AADR row."""
    doi = _clean(row.get("doi for publication of this representation of the data", ""))
    repository = _clean(
        row.get("Link to the most permanent repository hosting these data", "")
    )
    return _fallback_text(doi, repository, publication_key)


def _aadr_note(row: dict[str, str], group_id: str) -> str:
    """Return a compact note preserving AADR curation fields."""
    full_date = _clean(_column_value(row, FULL_DATE_COLUMN_PREFIX))
    assessment = _fallback_text(_clean(row.get("ASSESSMENT", "")), "unreported")
    return f"group_id={group_id}; full_date={full_date}; assessment={assessment}"


def _sample_sex(value: str) -> SampleSex:
    """Map AADR molecular sex labels to project sample sex labels."""
    base_value = value.split(maxsplit=1)[0] if value else value
    if base_value not in AADR_SEX_MAP:
        raise ValueError(f"unsupported AADR molecular sex label: {value}")
    return AADR_SEX_MAP[base_value]


def _single_file(root: Path, pattern: str) -> Path:
    """Return exactly one file matching a pattern in a directory."""
    matches = tuple(sorted(root.glob(pattern)))
    if len(matches) != 1:
        raise FileNotFoundError(
            f"expected exactly one AADR {pattern} file in {root}, found {len(matches)}"
        )
    return matches[0]


def _fallback_text(*values: str) -> str:
    """Return the first non-placeholder text value."""
    for value in values:
        cleaned = _clean(value)
        if cleaned:
            return cleaned
    return "unreported"


def _clean(value: str) -> str:
    """Normalize AADR placeholder text."""
    cleaned = value.strip()
    if cleaned in {"", "..", "n/a"}:
        return ""
    return cleaned
