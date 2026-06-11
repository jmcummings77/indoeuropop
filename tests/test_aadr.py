"""Tests for loading local Allen Ancient DNA Resource metadata."""

from pathlib import Path

import pytest

from indoeuropop.data.aadr import (
    AADRDataFiles,
    discover_aadr_files,
    load_aadr_sample_metadata,
    write_aadr_sample_metadata_csv,
)
from indoeuropop.data.sample_metadata import load_sample_metadata

GENETIC_ID_COLUMN = "Genetic ID (suffices)"
FIRST_PUBLICATION_COLUMN = (
    "First publication: Abbreviation for earliest paper that reported data"
)
DATE_MEAN_COLUMN = "Date mean in BP in years before 1950 CE"
DATE_SD_COLUMN = "Date standard deviation in BP"
FULL_DATE_COLUMN = "Full Date One of two formats"

AADR_COLUMNS = (
    GENETIC_ID_COLUMN,
    "Persistent Genetic ID",
    "Individual ID",
    FIRST_PUBLICATION_COLUMN,
    "Publication abbreviation",
    "doi for publication of this representation of the data",
    "Link to the most permanent repository hosting these data",
    DATE_MEAN_COLUMN,
    DATE_SD_COLUMN,
    FULL_DATE_COLUMN,
    "Group ID",
    "Locality",
    "Political Entity",
    "Molecular Sex",
    "ASSESSMENT",
)


def _aadr_dir(tmp_path: Path, *rows: tuple[str, ...]) -> Path:
    """Create a tiny AADR-like directory for loader tests."""
    root = tmp_path / "aadr"
    root.mkdir(parents=True)
    (root / "tiny.anno").write_text(_anno_text(*rows), encoding="utf-8")
    (root / "tiny.ind").write_text("I001 M Group\n", encoding="utf-8")
    (root / "tiny.snp").write_text("rs1 1 0.0 1 A G\n", encoding="utf-8")
    (root / "tiny.geno").write_text("0\n", encoding="utf-8")
    return root


def _anno_text(*rows: tuple[str, ...]) -> str:
    """Return minimal tab-separated AADR annotation text."""
    return "\n".join(("\t".join(AADR_COLUMNS), *("\t".join(row) for row in rows)))


def _row(
    *,
    genetic_id: str = "I001.SG",
    persistent_id: str = "123",
    publication: str = "PublicationKey",
    doi: str = "https://doi.org/example",
    date_mean_bp: str = "4250",
    date_sd_bp: str = "173",
    sex: str = "F",
    assessment: str = "Pass",
    political_entity: str = "Greece",
) -> tuple[str, ...]:
    """Return one minimal AADR annotation row."""
    return (
        genetic_id,
        persistent_id,
        "I001",
        "FirstPublication",
        publication,
        doi,
        "ENA:PRJEB00000",
        date_mean_bp,
        date_sd_bp,
        "2600-2000 BCE",
        "Greece_EBA",
        "Example Site",
        political_entity,
        sex,
        assessment,
    )


def test_discover_aadr_files_finds_quartet(tmp_path: Path) -> None:
    """AADR discovery should return the expected local file quartet."""
    root = _aadr_dir(tmp_path, _row())

    files = discover_aadr_files(root)

    assert isinstance(files, AADRDataFiles)
    assert files.annotation_path.name == "tiny.anno"
    assert files.individual_path.name == "tiny.ind"
    assert files.snp_path.name == "tiny.snp"
    assert files.genotype_path.name == "tiny.geno"


def test_load_aadr_sample_metadata_converts_annotations(tmp_path: Path) -> None:
    """AADR annotation rows should normalize to sample metadata records."""
    root = _aadr_dir(tmp_path, _row(), _row(genetic_id="I002.SG", sex="M"))

    dataset = load_aadr_sample_metadata(root, dataset_id="aadr-test", limit=1)
    record = dataset.records[0]

    assert dataset.sample_count == 1
    assert record.status == "published"
    assert record.dataset_id == "aadr-test"
    assert record.sample_id == "I001.SG"
    assert record.accession_id == "123"
    assert record.publication_key == "PublicationKey"
    assert record.publication == "https://doi.org/example"
    assert record.region == "Greece"
    assert record.site == "Example Site"
    assert record.time_bce == 2300
    assert record.date_uncertainty == 173
    assert record.sex == "female"
    assert record.method == "aadr_v66_annotation"
    assert "assessment=Pass" in record.note


def test_load_aadr_sample_metadata_uses_fallback_text(tmp_path: Path) -> None:
    """AADR placeholder text should fall back to stable alternatives."""
    root = _aadr_dir(
        tmp_path,
        _row(
            persistent_id="..",
            publication="..",
            doi="..",
            political_entity="..",
            sex="U",
            assessment="..",
        ),
    )

    record = load_aadr_sample_metadata(root).records[0]

    assert record.accession_id == "I001.SG"
    assert record.publication_key == "FirstPublication"
    assert record.publication == "ENA:PRJEB00000"
    assert record.region == "Greece_EBA"
    assert record.sex == "unknown"
    assert "assessment=unreported" in record.note


@pytest.mark.parametrize(
    ("aadr_label", "expected_sex"),
    [
        ("F (XXX)", "female"),
        ("M (XYY)", "male"),
        ("U (XXY)", "unknown"),
    ],
)
def test_load_aadr_sample_metadata_accepts_annotated_sex_labels(
    tmp_path: Path,
    aadr_label: str,
    expected_sex: str,
) -> None:
    """AADR karyotype annotations should preserve the leading sex code."""
    root = _aadr_dir(tmp_path, _row(sex=aadr_label))

    record = load_aadr_sample_metadata(root).records[0]

    assert record.sex == expected_sex


def test_load_aadr_sample_metadata_uses_unreported_when_all_text_is_blank(
    tmp_path: Path,
) -> None:
    """All-placeholder AADR text should fall back to explicit unreported labels."""
    root = _aadr_dir(
        tmp_path,
        _row(
            publication="..",
            doi="..",
            political_entity="..",
        ),
    )
    rows = (root / "tiny.anno").read_text(encoding="utf-8").splitlines()
    cells = rows[1].split("\t")
    cells[AADR_COLUMNS.index(FIRST_PUBLICATION_COLUMN)] = ".."
    cells[
        AADR_COLUMNS.index("Link to the most permanent repository hosting these data")
    ] = ".."
    cells[AADR_COLUMNS.index("Group ID")] = ".."
    cells[AADR_COLUMNS.index("Locality")] = ".."
    (root / "tiny.anno").write_text(
        "\n".join((rows[0], "\t".join(cells))) + "\n",
        encoding="utf-8",
    )

    record = load_aadr_sample_metadata(root).records[0]

    assert record.publication_key == "unreported"
    assert record.publication == "unreported"
    assert record.region == "unassigned"
    assert record.site == "unassigned"


def test_write_aadr_sample_metadata_csv_round_trips(tmp_path: Path) -> None:
    """AADR exports should write the project sample metadata schema."""
    root = _aadr_dir(tmp_path, _row())
    output_path = tmp_path / "outputs" / "sample-metadata.csv"

    returned_path = write_aadr_sample_metadata_csv(root, output_path)
    loaded = load_sample_metadata(output_path)

    assert returned_path == output_path
    assert loaded.records[0].sample_id == "I001.SG"


def test_discover_aadr_files_rejects_missing_directory(tmp_path: Path) -> None:
    """Missing AADR directories should fail clearly."""
    with pytest.raises(FileNotFoundError, match="does not exist"):
        discover_aadr_files(tmp_path / "missing")


def test_discover_aadr_files_rejects_missing_or_duplicate_files(
    tmp_path: Path,
) -> None:
    """AADR discovery should require exactly one file per suffix."""
    missing_root = tmp_path / "missing-file"
    missing_root.mkdir()
    with pytest.raises(FileNotFoundError, match="exactly one"):
        discover_aadr_files(missing_root)

    duplicate_root = _aadr_dir(tmp_path / "dupe", _row())
    (duplicate_root / "other.anno").write_text("extra\n", encoding="utf-8")
    with pytest.raises(FileNotFoundError, match="found 2"):
        discover_aadr_files(duplicate_root)


def test_load_aadr_sample_metadata_rejects_invalid_limit(tmp_path: Path) -> None:
    """AADR row limits should be positive when provided."""
    root = _aadr_dir(tmp_path, _row())

    with pytest.raises(ValueError, match="limit"):
        load_aadr_sample_metadata(root, limit=0)


def test_load_aadr_sample_metadata_rejects_empty_annotations(tmp_path: Path) -> None:
    """AADR annotation files must contain at least one data row."""
    root = _aadr_dir(tmp_path)

    with pytest.raises(ValueError, match="at least one"):
        load_aadr_sample_metadata(root)


def test_load_aadr_sample_metadata_rejects_empty_annotation_file(
    tmp_path: Path,
) -> None:
    """AADR annotation files without headers should fail clearly."""
    root = _aadr_dir(tmp_path, _row())
    (root / "tiny.anno").write_text("", encoding="utf-8")

    with pytest.raises(ValueError, match="header"):
        load_aadr_sample_metadata(root)


def test_load_aadr_sample_metadata_rejects_missing_columns(tmp_path: Path) -> None:
    """AADR annotation files missing required columns should fail clearly."""
    root = _aadr_dir(tmp_path, _row())
    (root / "tiny.anno").write_text("Genetic ID (suffices)\nI001\n", encoding="utf-8")

    with pytest.raises(ValueError, match="missing column"):
        load_aadr_sample_metadata(root)


def test_load_aadr_sample_metadata_rejects_missing_exact_columns(
    tmp_path: Path,
) -> None:
    """AADR annotations missing exact metadata columns should fail clearly."""
    root = _aadr_dir(tmp_path, _row())
    kept_columns = tuple(column for column in AADR_COLUMNS if column != "ASSESSMENT")
    kept_values = tuple(_row()[AADR_COLUMNS.index(column)] for column in kept_columns)
    (root / "tiny.anno").write_text(
        "\n".join(("\t".join(kept_columns), "\t".join(kept_values))) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="ASSESSMENT"):
        load_aadr_sample_metadata(root)


def test_load_aadr_sample_metadata_rejects_unsupported_sex(tmp_path: Path) -> None:
    """Unexpected AADR molecular sex labels should fail before export."""
    root = _aadr_dir(tmp_path, _row(sex="ambiguous"))

    with pytest.raises(ValueError, match="unsupported"):
        load_aadr_sample_metadata(root)
