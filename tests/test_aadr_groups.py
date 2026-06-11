"""Tests for suggesting AADR target group selections."""

from pathlib import Path

import pytest

from indoeuropop.aadr_curation import AADRGroupSelection, load_aadr_group_selections
from indoeuropop.aadr_groups import (
    AADRGroupRecord,
    AADRGroupSuggestionOptions,
    AADRRegionBox,
    aadr_group_selections_to_tsv,
    assign_aadr_region,
    load_aadr_group_suggestions,
    load_aadr_individual_groups,
    parse_aadr_group_records,
    suggest_aadr_group_selections,
    write_aadr_group_selections_tsv,
)

_HEADER = "\t".join(
    ("Genetic ID", "Group ID", "Latitude", "Longitude", "Date mean in BP")
)


def _row(sample_id: str, group_id: str, lat: float, lon: float, bp: float) -> str:
    """Return one minimal AADR group-suggestion row."""
    return "\t".join((sample_id, group_id, str(lat), str(lon), str(bp)))


def _anno_lines() -> tuple[str, ...]:
    """Return minimal AADR annotation lines for group suggestion tests."""
    return (
        _HEADER,
        _row("I1", "England_Beaker", 51.5, -0.1, 4000),
        _row("I2", "England_Beaker", 52.0, -1.0, 4100),
        _row("I3", "England_Beaker", 53.0, -2.0, 4050),
        _row("I4", "Iberia_BA", 40.4, -3.7, 3800),
        _row("I5", "Iberia_Neolithic", 41.0, -4.0, 6000),
        _row("I6", "Sardinia_Beaker", 40.0, 9.0, 4000),
        _row("I7", "England_Neolithic", 51.0, -0.1, 4000),
    )


def _aadr_dir(tmp_path: Path) -> Path:
    """Create a tiny AADR quartet for group suggestion tests."""
    root = tmp_path / "aadr"
    root.mkdir()
    (root / "tiny.anno").write_text("\n".join(_anno_lines()) + "\n", encoding="utf-8")
    (root / "tiny.ind").write_text(
        "\n".join(
            (
                "I1 M England_Beaker",
                "I2 F England_Beaker",
                "I3 M England_Beaker",
                "I4 F Iberia_BA",
            )
        )
        + "\n",
        encoding="utf-8",
    )
    (root / "tiny.snp").write_text("rs1 1 0.0 1 A G\n", encoding="utf-8")
    (root / "tiny.geno").write_text("0\n", encoding="utf-8")
    return root


def test_parse_aadr_group_records_extracts_reduced_rows() -> None:
    """AADR annotation rows should parse into group-date-coordinate records."""
    records = parse_aadr_group_records(_anno_lines())

    assert records[0] == AADRGroupRecord(
        group_id="England_Beaker",
        latitude=51.5,
        longitude=-0.1,
        time_bce=2050,
    )
    assert len(records) == 7


def test_parse_aadr_group_records_handles_quoted_aadr_headers() -> None:
    """Official AADR date headers may be wrapped in quote characters."""
    lines = (
        "\t".join(
            (
                "Genetic ID",
                "Group ID",
                "Latitude",
                "Longitude",
                '"Date mean in BP in years before 1950 CE"',
            )
        ),
        _row("I1", "England_Beaker", 51.5, -0.1, 4000),
    )

    assert parse_aadr_group_records(lines)[0].time_bce == pytest.approx(2050)


def test_parse_aadr_group_records_handles_empty_and_missing_headers() -> None:
    """Missing group-suggestion columns should fail clearly."""
    assert parse_aadr_group_records(()) == ()
    with pytest.raises(ValueError, match="missing group-suggestion columns"):
        parse_aadr_group_records(["Genetic ID\tLatitude"])


def test_parse_aadr_group_records_skips_incomplete_rows() -> None:
    """Blank, short, and unparseable rows should be skipped."""
    lines = (
        _HEADER,
        "",
        "short",
        _row("I1", "", 51.0, -0.1, 4000),
        "\t".join(("I2", "England_Beaker", "bad", "-0.1", "4000")),
        "\t".join(("I4", "England_Beaker", "..", "-0.1", "4000")),
        _row("I3", "England_Beaker", 51.0, -0.1, 4000),
    )

    assert len(parse_aadr_group_records(lines)) == 1


def test_assign_aadr_region_uses_default_and_custom_boxes() -> None:
    """Coordinates should map to coarse modeled region boxes."""
    assert assign_aadr_region(51.5, -0.1) == "britain"
    assert assign_aadr_region(40.4, -3.7) == "iberia"
    assert assign_aadr_region(0.0, 0.0) is None
    assert (
        assign_aadr_region(
            10.0,
            10.0,
            (AADRRegionBox("custom", 9.0, 11.0, 9.0, 11.0),),
        )
        == "custom"
    )


def test_suggest_aadr_group_selections_filters_and_assigns() -> None:
    """Group suggestions should use date, geography, keywords, and count."""
    selections = suggest_aadr_group_selections(_anno_lines())

    assert selections == (AADRGroupSelection("britain", "England_Beaker"),)


def test_suggest_aadr_group_selections_can_keep_singletons() -> None:
    """Lowering min_count should keep one-sample candidate groups."""
    selections = suggest_aadr_group_selections(
        _anno_lines(),
        options=AADRGroupSuggestionOptions(min_count=1),
    )

    assert AADRGroupSelection("iberia", "Iberia_BA") in selections


def test_suggest_aadr_group_selections_restricts_to_ind_groups() -> None:
    """Valid group filtering should drop labels absent from a genotype .ind."""
    selections = suggest_aadr_group_selections(
        _anno_lines(),
        options=AADRGroupSuggestionOptions(min_count=1),
        valid_groups=frozenset({"England_Beaker"}),
    )

    assert selections == (AADRGroupSelection("britain", "England_Beaker"),)


def test_suggest_aadr_group_selections_assigns_group_to_majority_region() -> None:
    """A group spanning boxes should be assigned to its majority region."""
    lines = (
        _HEADER,
        _row("A", "Shared_Beaker", 51.5, -0.1, 4000),
        _row("B", "Shared_Beaker", 52.0, -1.0, 4000),
        _row("C", "Shared_Beaker", 40.4, -3.7, 4000),
    )

    selections = suggest_aadr_group_selections(
        lines, options=AADRGroupSuggestionOptions(min_count=2)
    )

    assert selections == (AADRGroupSelection("britain", "Shared_Beaker"),)


def test_aadr_group_suggestion_options_validate() -> None:
    """Invalid group-suggestion options should fail at construction."""
    with pytest.raises(ValueError):
        AADRGroupSuggestionOptions(min_count=0)
    with pytest.raises(ValueError):
        AADRGroupSuggestionOptions(date_min_bce=3000, date_max_bce=1000)
    with pytest.raises(ValueError):
        AADRGroupSuggestionOptions(keywords=())
    with pytest.raises(ValueError):
        AADRGroupSuggestionOptions(region_boxes=())


def test_load_aadr_individual_groups_reads_group_column(tmp_path: Path) -> None:
    """AADR `.ind` files should provide the valid qpAdm population labels."""
    path = tmp_path / "tiny.ind"
    path.write_text("I1 M England_Beaker\nshort\nI2 F Iberia_BA\n", encoding="utf-8")

    assert load_aadr_individual_groups(path) == frozenset(
        {"England_Beaker", "Iberia_BA"}
    )


def test_load_aadr_group_suggestions_reads_local_quartet(tmp_path: Path) -> None:
    """Local AADR quartets should produce reviewable group selections."""
    selections = load_aadr_group_suggestions(
        _aadr_dir(tmp_path),
        options=AADRGroupSuggestionOptions(min_count=1),
    )

    assert selections == (
        AADRGroupSelection("britain", "England_Beaker"),
        AADRGroupSelection("iberia", "Iberia_BA"),
    )


def test_load_aadr_group_suggestions_can_skip_ind_restriction(tmp_path: Path) -> None:
    """The .ind restriction can be disabled for annotation-only review."""
    selections = load_aadr_group_suggestions(
        _aadr_dir(tmp_path),
        options=AADRGroupSuggestionOptions(min_count=1),
        restrict_to_individual_file=False,
    )

    assert AADRGroupSelection("britain", "England_Beaker") in selections
    assert AADRGroupSelection("iberia", "Iberia_BA") in selections


def test_aadr_group_selection_tsv_round_trips(tmp_path: Path) -> None:
    """Suggested selections should write and reload as reviewable TSV."""
    output_path = tmp_path / "outputs" / "groups.tsv"
    selections = (
        AADRGroupSelection("britain", "England_Beaker"),
        AADRGroupSelection("iberia", "Iberia_BA"),
    )

    returned_path = write_aadr_group_selections_tsv(selections, output_path)
    output_text = aadr_group_selections_to_tsv(selections)
    loaded = load_aadr_group_selections(output_path)

    assert returned_path == output_path
    assert output_text.startswith("# Auto-generated")
    assert loaded == selections
