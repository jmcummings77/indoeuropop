"""Tests for preparing AADR-derived target-pipeline inputs."""

from pathlib import Path
from typing import Any

import pytest

from indoeuropop.aadr_curation import (
    AADRGroupSelection,
    AADRTargetInputOptions,
    build_aadr_target_inputs,
    load_aadr_group_selections,
    prepare_aadr_target_inputs,
    write_aadr_target_inputs,
)
from indoeuropop.sample_metadata import (
    SampleMetadataDataset,
    SampleMetadataRecord,
    load_sample_metadata,
)
from indoeuropop.target_curation import load_target_curation


def _record(
    sample_id: str,
    group_id: str,
    *,
    time_bce: float = 2300,
    publication_key: str = "PublicationKey",
) -> SampleMetadataRecord:
    """Build one AADR-like sample metadata record for target-input tests."""
    return SampleMetadataRecord(
        status="published",
        dataset_id="aadr-test",
        sample_id=sample_id,
        accession_id=f"accession-{sample_id}",
        publication_key=publication_key,
        publication="https://doi.org/example",
        region="raw-political-entity",
        site="Example Site",
        time_bce=time_bce,
        date_uncertainty=50,
        sex="unknown",
        method="aadr_v66_annotation",
        note=f"group_id={group_id}; full_date=2600-2000 BCE; assessment=Pass",
    )


def _metadata() -> SampleMetadataDataset:
    """Return sample metadata with exact and prefix-matchable AADR groups."""
    return SampleMetadataDataset.from_rows(
        (
            _record("I001", "England_BellBeaker", time_bce=2400),
            _record(
                "I002",
                "England_BellBeaker-olowEEF",
                time_bce=2200,
                publication_key="OtherPublication",
            ),
            _record("I003", "Iberia_EBA", time_bce=1800),
        )
    )


def _tiny_aadr_dir(tmp_path: Path) -> Path:
    """Create a tiny AADR quartet for prepare-aadr tests."""
    root = tmp_path / "aadr"
    root.mkdir()
    header = "\t".join(
        (
            "Genetic ID (suffices)",
            "Persistent Genetic ID",
            "Individual ID",
            "First publication: Abbreviation for earliest paper",
            "Publication abbreviation",
            "doi for publication of this representation of the data",
            "Link to the most permanent repository hosting these data",
            "Date mean in BP in years before 1950 CE",
            "Date standard deviation in BP",
            "Full Date One of two formats",
            "Group ID",
            "Locality",
            "Political Entity",
            "Molecular Sex",
            "ASSESSMENT",
        )
    )
    row = "\t".join(
        (
            "I001.SG",
            "123",
            "I001",
            "FirstPublication",
            "PublicationKey",
            "https://doi.org/example",
            "ENA:PRJEB00000",
            "4250",
            "173",
            "2600-2000 BCE",
            "Greece_EBA",
            "Example Site",
            "Greece",
            "F",
            "Pass",
        )
    )
    (root / "tiny.anno").write_text(f"{header}\n{row}\n", encoding="utf-8")
    (root / "tiny.ind").write_text("I001.SG F Greece_EBA\n", encoding="utf-8")
    (root / "tiny.snp").write_text("rs1 1 0.0 1 A G\n", encoding="utf-8")
    (root / "tiny.geno").write_text("0\n", encoding="utf-8")
    return root


def test_load_aadr_group_selections_reads_tsv_with_header(tmp_path: Path) -> None:
    """Group selections should load from comment-friendly TSV files."""
    selection_path = tmp_path / "groups.tsv"
    selection_path.write_text(
        "# region\taadr_group_id\nregion\taadr_group_id\nbritain\tEngland_EBA\n",
        encoding="utf-8",
    )

    selections = load_aadr_group_selections(selection_path)

    assert selections == (AADRGroupSelection("britain", "England_EBA"),)


def test_load_aadr_group_selections_reads_csv_without_header(tmp_path: Path) -> None:
    """Group selections should also support simple comma-separated rows."""
    selection_path = tmp_path / "groups.csv"
    selection_path.write_text("iberia,Iberia_EBA\n", encoding="utf-8")

    selections = load_aadr_group_selections(selection_path)

    assert selections == (AADRGroupSelection("iberia", "Iberia_EBA"),)


@pytest.mark.parametrize("contents", ["", "region,aadr_group_id\n"])
def test_load_aadr_group_selections_rejects_empty_inputs(
    tmp_path: Path,
    contents: str,
) -> None:
    """Empty selection files should fail before data preparation."""
    selection_path = tmp_path / "groups.csv"
    selection_path.write_text(contents, encoding="utf-8")

    with pytest.raises(ValueError, match=r"at least one|data rows"):
        load_aadr_group_selections(selection_path)


def test_load_aadr_group_selections_rejects_short_rows(tmp_path: Path) -> None:
    """Group selection rows need region and group columns."""
    selection_path = tmp_path / "groups.csv"
    selection_path.write_text("region-only\n", encoding="utf-8")

    with pytest.raises(ValueError, match="two columns"):
        load_aadr_group_selections(selection_path)


def test_build_aadr_target_inputs_remaps_regions_and_builds_curation() -> None:
    """AADR selections should produce compatible metadata and curation rows."""
    inputs = build_aadr_target_inputs(
        _metadata(),
        (
            AADRGroupSelection("britain", "England_BellBeaker"),
            AADRGroupSelection("iberia", "Iberia_EBA"),
        ),
        options=AADRTargetInputOptions(group_match_mode="prefix"),
    )

    assert inputs.sample_metadata.sample_count == 3
    assert inputs.sample_metadata.regions() == ("britain", "iberia")
    first_curation = inputs.curation.records[0]
    assert first_curation.target_id == "aadr-britain-steppe-england-bellbeaker"
    assert first_curation.sample_ids == ("I001", "I002")
    assert first_curation.start_bce == 2400
    assert first_curation.end_bce == 2200
    assert first_curation.ancestry_method == "external_autosomal_steppe_required"
    assert "matched_group_ids=England_BellBeaker|England_BellBeaker-olowEEF" in (
        first_curation.note
    )


def test_prepare_and_write_aadr_target_inputs_round_trips(tmp_path: Path) -> None:
    """Prepared AADR inputs should write loadable sample and curation CSVs."""
    aadr_dir = _tiny_aadr_dir(tmp_path)
    sample_path = tmp_path / "outputs" / "sample-metadata.csv"
    curation_path = tmp_path / "outputs" / "target-curation.csv"
    inputs = prepare_aadr_target_inputs(
        aadr_dir,
        (AADRGroupSelection("greece", "Greece"),),
        options=AADRTargetInputOptions(
            dataset_id="aadr-test",
            source="steppe",
            ancestry_method="qpAdm_pending",
            aggregation_method="unweighted_mean",
            group_match_mode="prefix",
            citation_key="aadr-test",
            citation="AADR test citation",
        ),
    )

    paths = write_aadr_target_inputs(
        inputs,
        sample_metadata_path=sample_path,
        target_curation_path=curation_path,
    )
    loaded_metadata = load_sample_metadata(paths.sample_metadata_path)
    loaded_curation = load_target_curation(paths.target_curation_path)

    assert loaded_metadata.records[0].region == "greece"
    assert loaded_curation.records[0].ancestry_method == "qpAdm_pending"
    assert loaded_curation.records[0].citation == "AADR test citation"


def test_build_aadr_target_inputs_rejects_empty_selections() -> None:
    """At least one reviewed group selection is required."""
    with pytest.raises(ValueError, match="at least one"):
        build_aadr_target_inputs(_metadata(), ())


def test_prepare_aadr_target_inputs_rejects_empty_selections(tmp_path: Path) -> None:
    """Directory-backed preparation should also require selections."""
    with pytest.raises(ValueError, match="at least one"):
        prepare_aadr_target_inputs(_tiny_aadr_dir(tmp_path), ())


def test_build_aadr_target_inputs_rejects_unmatched_groups() -> None:
    """Selections that match no AADR rows should fail clearly."""
    with pytest.raises(ValueError, match="matched no samples"):
        build_aadr_target_inputs(
            _metadata(),
            (AADRGroupSelection("gaul", "Gaul_EBA"),),
        )


def test_build_aadr_target_inputs_can_report_unmatched_groups() -> None:
    """Allowed unmatched selections should be reported while matches are kept."""
    inputs = build_aadr_target_inputs(
        _metadata(),
        (
            AADRGroupSelection("britain", "England_BellBeaker"),
            AADRGroupSelection("gaul", "Gaul_EBA"),
        ),
        options=AADRTargetInputOptions(allow_missing_groups=True),
    )

    assert inputs.sample_metadata.sample_count == 1
    assert inputs.unmatched_selections == (AADRGroupSelection("gaul", "Gaul_EBA"),)


def test_build_aadr_target_inputs_rejects_all_unmatched_groups() -> None:
    """Allowing missing groups should still require at least one matched group."""
    with pytest.raises(ValueError, match="matched no samples"):
        build_aadr_target_inputs(
            _metadata(),
            (AADRGroupSelection("gaul", "Gaul_EBA"),),
            options=AADRTargetInputOptions(allow_missing_groups=True),
        )


def test_build_aadr_target_inputs_rejects_conflicting_region_maps() -> None:
    """One selected sample should not map to multiple modeled regions."""
    with pytest.raises(ValueError, match="multiple modeled regions"):
        build_aadr_target_inputs(
            _metadata(),
            (
                AADRGroupSelection("britain", "England_BellBeaker"),
                AADRGroupSelection("other", "England_BellBeaker"),
            ),
        )


def test_build_aadr_target_inputs_rejects_missing_group_notes() -> None:
    """AADR-derived curation requires group IDs preserved in metadata notes."""
    metadata = SampleMetadataDataset.from_rows(
        (_record("I001", "England_BellBeaker", time_bce=2400),)
    )
    broken = SampleMetadataDataset.from_rows((replace_note(metadata.records[0], ""),))

    with pytest.raises(ValueError, match="missing an AADR group_id"):
        build_aadr_target_inputs(
            broken,
            (AADRGroupSelection("britain", "England_BellBeaker"),),
        )


@pytest.mark.parametrize(
    "selection_kwargs",
    [
        {"region": "", "group_id": "Greece_EBA"},
        {"region": "greece", "group_id": ""},
    ],
)
def test_aadr_group_selection_rejects_blank_fields(
    selection_kwargs: dict[str, str],
) -> None:
    """Group selections should require both modeled region and AADR group."""
    with pytest.raises(ValueError, match="non-empty"):
        AADRGroupSelection(**selection_kwargs)


@pytest.mark.parametrize(
    "option_kwargs",
    [
        {"dataset_id": ""},
        {"source": ""},
        {"ancestry_method": ""},
        {"aggregation_method": ""},
        {"citation_key": ""},
        {"citation": ""},
        {"group_match_mode": "contains"},
    ],
)
def test_aadr_target_input_options_reject_invalid_fields(
    option_kwargs: dict[str, Any],
) -> None:
    """Target-input options should reject blank fields and unknown match modes."""
    with pytest.raises(ValueError):
        AADRTargetInputOptions(**option_kwargs)


def test_build_aadr_target_inputs_summarizes_long_value_lists() -> None:
    """Long note summaries should stay compact for broad AADR selections."""
    records = tuple(
        _record(
            f"I{index:03d}",
            f"Group_Variant_{index:03d}",
            publication_key=f"Publication{index:03d}",
        )
        for index in range(10)
    )
    metadata = SampleMetadataDataset.from_rows(records)

    inputs = build_aadr_target_inputs(
        metadata,
        (AADRGroupSelection("region", "Group"),),
        options=AADRTargetInputOptions(group_match_mode="prefix"),
    )

    assert "matched_group_ids=Group_Variant_000|Group_Variant_001" in (
        inputs.curation.records[0].note
    )
    assert "|+2" in inputs.curation.records[0].note


def replace_note(
    record: SampleMetadataRecord,
    note: str,
) -> SampleMetadataRecord:
    """Return a sample metadata record with a replacement note."""
    return SampleMetadataRecord(
        status=record.status,
        dataset_id=record.dataset_id,
        sample_id=record.sample_id,
        accession_id=record.accession_id,
        publication_key=record.publication_key,
        publication=record.publication,
        region=record.region,
        site=record.site,
        time_bce=record.time_bce,
        date_uncertainty=record.date_uncertainty,
        sex=record.sex,
        method=record.method,
        note=note,
    )
