"""Suggest AADR group selections from annotation geography and dates."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from indoeuropop.data.aadr import discover_aadr_files
from indoeuropop.data.aadr_curation import AADRGroupSelection

DEFAULT_AADR_TARGET_KEYWORDS = (
    "beaker",
    "corded",
    "bronze",
    "_eba",
    "_ba",
    "_lba",
    "_mba",
)

_GROUP_KEYS = ("group id", "group", "population id", "population")
_LATITUDE_KEYS = ("latitude", "lat")
_LONGITUDE_KEYS = ("longitude", "long")
_DATE_KEYS = ("date mean in bp", "mean in bp", "bp in years")
_BP_REFERENCE_YEAR = 1950.0


@dataclass(frozen=True)
class AADRRegionBox:
    """A coarse geographic box used for first-pass AADR group suggestions."""

    region: str
    lat_min: float
    lat_max: float
    lon_min: float
    lon_max: float

    def contains(self, latitude: float, longitude: float) -> bool:
        """Return whether a coordinate falls inside this box."""
        return (
            self.lat_min <= latitude <= self.lat_max
            and self.lon_min <= longitude <= self.lon_max
        )


@dataclass(frozen=True)
class AADRGroupRecord:
    """A reduced AADR annotation row used for group suggestion."""

    group_id: str
    latitude: float
    longitude: float
    time_bce: float


@dataclass(frozen=True)
class AADRGroupSuggestionOptions:
    """Controls for suggesting AADR region/group selections."""

    min_count: int = 3
    date_min_bce: float = 1000.0
    date_max_bce: float = 3000.0
    keywords: tuple[str, ...] = DEFAULT_AADR_TARGET_KEYWORDS
    region_boxes: tuple[AADRRegionBox, ...] = (
        AADRRegionBox("britain", 49.5, 59.5, -8.5, 2.0),
        AADRRegionBox("central_europe", 47.0, 54.5, 6.0, 19.0),
        AADRRegionBox("iberia", 36.0, 44.0, -9.5, 3.5),
    )

    def __post_init__(self) -> None:
        """Validate group-suggestion options."""
        if self.min_count < 1:
            raise ValueError("min_count must be at least 1")
        if self.date_min_bce > self.date_max_bce:
            raise ValueError("date_min_bce must be less than or equal to date_max_bce")
        if not self.keywords:
            raise ValueError("keywords must contain at least one value")
        if not self.region_boxes:
            raise ValueError("region_boxes must contain at least one box")


def load_aadr_group_suggestions(
    directory: str | Path,
    *,
    options: AADRGroupSuggestionOptions | None = None,
    restrict_to_individual_file: bool = True,
) -> tuple[AADRGroupSelection, ...]:
    """Suggest target group selections from a local AADR quartet."""
    files = discover_aadr_files(directory)
    valid_groups = (
        load_aadr_individual_groups(files.individual_path)
        if restrict_to_individual_file
        else None
    )
    with files.annotation_path.open(encoding="utf-8") as annotation_file:
        return suggest_aadr_group_selections(
            annotation_file,
            options=options,
            valid_groups=valid_groups,
        )


def load_aadr_individual_groups(path: str | Path) -> frozenset[str]:
    """Return population/group labels from an AADR `.ind` file."""
    groups: set[str] = set()
    with Path(path).open(encoding="utf-8") as individual_file:
        for line in individual_file:
            parts = line.split()
            if len(parts) >= 3:
                groups.add(parts[2])
    return frozenset(groups)


def suggest_aadr_group_selections(
    lines: Iterable[str],
    *,
    options: AADRGroupSuggestionOptions | None = None,
    valid_groups: frozenset[str] | None = None,
) -> tuple[AADRGroupSelection, ...]:
    """Suggest modeled-region/group rows from AADR annotation lines."""
    group_options = AADRGroupSuggestionOptions() if options is None else options
    pair_counts: dict[tuple[str, str], int] = defaultdict(int)
    for record in parse_aadr_group_records(lines):
        if (
            not group_options.date_min_bce
            <= record.time_bce
            <= group_options.date_max_bce
        ):
            continue
        region = assign_aadr_region(
            record.latitude,
            record.longitude,
            group_options.region_boxes,
        )
        if region is None:
            continue
        if not _contains_keyword(record.group_id, group_options.keywords):
            continue
        if valid_groups is not None and record.group_id not in valid_groups:
            continue
        pair_counts[(region, record.group_id)] += 1
    return _best_group_selections(pair_counts, group_options.min_count)


def parse_aadr_group_records(lines: Iterable[str]) -> tuple[AADRGroupRecord, ...]:
    """Parse reduced group, coordinate, and date rows from AADR annotations."""
    iterator = iter(lines)
    header_line = next((line for line in iterator if line.strip()), None)
    if header_line is None:
        return ()
    header = header_line.rstrip("\n").split("\t")
    columns = _aadr_group_columns(header)
    records: list[AADRGroupRecord] = []
    for raw in iterator:
        if not raw.strip():
            continue
        fields = raw.rstrip("\n").split("\t")
        if len(fields) <= max(columns.values()):
            continue
        record = _record_from_fields(fields, columns)
        if record is not None:
            records.append(record)
    return tuple(records)


def assign_aadr_region(
    latitude: float,
    longitude: float,
    boxes: Iterable[AADRRegionBox] | None = None,
) -> str | None:
    """Return the first modeled region box containing a coordinate."""
    box_tuple = AADRGroupSuggestionOptions().region_boxes if boxes is None else boxes
    for box in box_tuple:
        if box.contains(latitude, longitude):
            return box.region
    return None


def aadr_group_selections_to_tsv(
    selections: Iterable[AADRGroupSelection],
) -> str:
    """Return group selections as a reviewable TSV file."""
    header = (
        "# Auto-generated AADR group selections.\n"
        "# Review these before running qpAdm or target aggregation.\n"
        "region\taadr_group_id\n"
    )
    body = "".join(
        f"{selection.region}\t{selection.group_id}\n" for selection in selections
    )
    return header + body


def write_aadr_group_selections_tsv(
    selections: Iterable[AADRGroupSelection],
    path: str | Path,
) -> Path:
    """Write AADR group selections to a TSV file and return the path."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(aadr_group_selections_to_tsv(selections), encoding="utf-8")
    return output_path


def _aadr_group_columns(header: list[str]) -> dict[str, int]:
    """Resolve required AADR columns for group suggestion."""
    columns = {
        "group": _column_index(header, _GROUP_KEYS),
        "latitude": _column_index(header, _LATITUDE_KEYS),
        "longitude": _column_index(header, _LONGITUDE_KEYS),
        "date_bp": _column_index(header, _DATE_KEYS),
    }
    missing = tuple(key for key, index in columns.items() if index is None)
    if missing:
        raise ValueError(f"AADR annotation missing group-suggestion columns: {missing}")
    return {key: int(index) for key, index in columns.items() if index is not None}


def _column_index(header: list[str], needles: tuple[str, ...]) -> int | None:
    """Return the first header index matching one of several prefixes."""
    lowered = tuple(value.strip().strip('"').lower() for value in header)
    for needle in needles:
        for index, name in enumerate(lowered):
            if name.startswith(needle):
                return index
    return None


def _record_from_fields(
    fields: list[str],
    columns: Mapping[str, int],
) -> AADRGroupRecord | None:
    """Convert split annotation fields to a reduced record if complete."""
    group_id = fields[columns["group"]].strip()
    latitude = _parse_float(fields[columns["latitude"]])
    longitude = _parse_float(fields[columns["longitude"]])
    date_bp = _parse_float(fields[columns["date_bp"]])
    if not group_id or latitude is None or longitude is None or date_bp is None:
        return None
    return AADRGroupRecord(
        group_id=group_id,
        latitude=latitude,
        longitude=longitude,
        time_bce=date_bp - _BP_REFERENCE_YEAR,
    )


def _best_group_selections(
    pair_counts: Mapping[tuple[str, str], int],
    min_count: int,
) -> tuple[AADRGroupSelection, ...]:
    """Return each group assigned to its strongest represented region."""
    best_regions: dict[str, tuple[str, int]] = {}
    for (region, group_id), count in pair_counts.items():
        if group_id not in best_regions or count > best_regions[group_id][1]:
            best_regions[group_id] = (region, count)
    selections = tuple(
        AADRGroupSelection(region, group_id)
        for group_id, (region, count) in best_regions.items()
        if count >= min_count
    )
    return tuple(
        sorted(selections, key=lambda selection: (selection.region, selection.group_id))
    )


def _contains_keyword(group_id: str, keywords: tuple[str, ...]) -> bool:
    """Return whether a group label contains one of the target keywords."""
    lowered = group_id.lower()
    return any(keyword.lower() in lowered for keyword in keywords)


def _parse_float(text: str) -> float | None:
    """Parse a float, returning `None` for AADR placeholders."""
    cleaned = text.strip()
    if cleaned in {"", ".."} or cleaned.lower() in {"n/a", "na"}:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None
