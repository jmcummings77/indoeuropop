"""Tests for reviewed target-decision files."""

from pathlib import Path

import pytest

from indoeuropop.data.sample_metadata import SampleMetadataDataset, SampleMetadataRecord
from indoeuropop.data.target_curation import TargetCurationDataset, TargetCurationRecord
from indoeuropop.data.target_decisions import (
    TARGET_DEFER_DECISIONS,
    TARGET_INCLUDE_DECISIONS,
    TargetDecisionDataset,
    TargetDecisionRecord,
    apply_target_decisions,
    load_target_decisions,
    target_decisions_to_csv,
    write_decision_filtered_target_inputs,
    write_target_decisions_csv,
)


def test_load_target_decisions_reads_reviewed_csv(tmp_path: Path) -> None:
    """Decision CSV files should load as typed decision records."""
    path = tmp_path / "target-decisions.csv"
    path.write_text(_decision_csv(), encoding="utf-8")

    dataset = load_target_decisions(path)
    keep_decision = dataset.decision_for("target-keep")
    rerun_decision = dataset.decision_for("target-rerun")

    assert dataset.target_ids() == ("target-keep", "target-rerun")
    assert keep_decision is not None
    assert keep_decision.keeps_target is True
    assert rerun_decision is not None
    assert rerun_decision.decision == "rerun_qpadm"
    assert frozenset({"retain", "retain_with_caveat"}) == TARGET_INCLUDE_DECISIONS
    assert "rerun_qpadm" in TARGET_DEFER_DECISIONS


def test_apply_target_decisions_filters_curation_and_metadata() -> None:
    """Deferred targets should be removed while undecided targets can remain."""
    result = apply_target_decisions(
        _metadata_dataset(_sample("S1"), _sample("S2"), _sample("S3")),
        TargetCurationDataset.from_rows(
            (
                _curation("target-keep", ("S1",)),
                _curation("target-rerun", ("S2",)),
                _curation("target-undecided", ("S3",)),
            )
        ),
        TargetDecisionDataset.from_rows(
            (
                TargetDecisionRecord("target-keep", "retain_with_caveat", "usable"),
                TargetDecisionRecord("target-rerun", "rerun_qpadm", "rerun needed"),
            )
        ),
    )

    assert result.curation.target_ids() == ("target-keep", "target-undecided")
    assert result.retained_target_ids == ("target-keep", "target-undecided")
    assert result.deferred_target_ids == ("target-rerun",)
    assert result.undecided_target_ids == ("target-undecided",)
    assert tuple(record.sample_id for record in result.sample_metadata.records) == (
        "S1",
        "S3",
    )


def test_apply_target_decisions_can_defer_undecided_targets() -> None:
    """Strict application can defer targets without explicit decisions."""
    result = apply_target_decisions(
        _metadata_dataset(_sample("S1"), _sample("S2")),
        TargetCurationDataset.from_rows(
            (_curation("target-keep", ("S1",)), _curation("target-other", ("S2",)))
        ),
        TargetDecisionDataset.from_rows(
            (TargetDecisionRecord("target-keep", "retain", "usable"),)
        ),
        retain_undecided=False,
    )

    assert result.curation.target_ids() == ("target-keep",)
    assert result.deferred_target_ids == ("target-other",)


def test_target_decisions_write_round_trips(tmp_path: Path) -> None:
    """Decision CSV serialization should be stable and writable."""
    dataset = TargetDecisionDataset.from_rows(
        (
            TargetDecisionRecord(
                "target-keep",
                "retain",
                "usable",
                requested_group_id="Group",
                reviewer="Reviewer",
                decision_date="2026-06-11",
                note="caveat",
            ),
        )
    )
    path = tmp_path / "decisions" / "target-decisions.csv"

    returned_path = write_target_decisions_csv(dataset, path)
    loaded = load_target_decisions(path)

    assert returned_path == path
    assert target_decisions_to_csv(dataset).startswith("target_id,decision")
    assert loaded.records == dataset.records


def test_write_decision_filtered_target_inputs(tmp_path: Path) -> None:
    """Decision-filtered inputs should be writable through one helper."""
    result = apply_target_decisions(
        _metadata_dataset(_sample("S1"), _sample("S2")),
        TargetCurationDataset.from_rows(
            (_curation("target-keep", ("S1",)), _curation("target-drop", ("S2",)))
        ),
        TargetDecisionDataset.from_rows(
            (
                TargetDecisionRecord("target-keep", "retain", "usable"),
                TargetDecisionRecord("target-drop", "exclude", "bad target"),
            )
        ),
    )

    sample_path, curation_path = write_decision_filtered_target_inputs(
        result,
        sample_metadata_path=tmp_path / "out" / "samples.csv",
        target_curation_path=tmp_path / "out" / "curation.csv",
    )

    assert sample_path.exists()
    assert curation_path.exists()
    assert "S2" not in sample_path.read_text(encoding="utf-8")
    assert "target-drop" not in curation_path.read_text(encoding="utf-8")


def test_target_decisions_validate_inputs(tmp_path: Path) -> None:
    """Malformed decisions should be rejected clearly."""
    missing_columns = tmp_path / "missing.csv"
    missing_columns.write_text("target_id,decision\n", encoding="utf-8")
    empty = tmp_path / "empty.csv"
    empty.write_text("", encoding="utf-8")
    header_only = tmp_path / "header-only.csv"
    header_only.write_text(_decision_csv().splitlines()[0] + "\n", encoding="utf-8")
    duplicate = tmp_path / "duplicate.csv"
    duplicate.write_text(
        _decision_csv() + _decision_csv().splitlines()[1] + "\n", encoding="utf-8"
    )
    invalid_row = tmp_path / "invalid-row.csv"
    invalid_row.write_text(
        _decision_csv().replace("target-keep,retain,usable", ",retain,usable", 1),
        encoding="utf-8",
    )
    invalid_decision = tmp_path / "invalid-decision.csv"
    invalid_decision.write_text(
        _decision_csv().replace("retain,usable", "maybe,usable", 1),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="missing columns"):
        load_target_decisions(missing_columns)
    with pytest.raises(ValueError, match="header row"):
        load_target_decisions(empty)
    with pytest.raises(ValueError, match="at least one row"):
        load_target_decisions(header_only)
    with pytest.raises(ValueError, match="unique"):
        load_target_decisions(duplicate)
    with pytest.raises(ValueError, match="invalid target decision"):
        load_target_decisions(invalid_row)
    with pytest.raises(ValueError, match="invalid target decision"):
        load_target_decisions(invalid_decision)
    with pytest.raises(ValueError, match="target_id"):
        TargetDecisionRecord("", "retain", "reason")
    with pytest.raises(ValueError, match="decision"):
        TargetDecisionRecord("target", "maybe", "reason")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="reason"):
        TargetDecisionRecord("target", "retain", "")
    with pytest.raises(ValueError, match="unknown target"):
        apply_target_decisions(
            _metadata_dataset(_sample("S1")),
            TargetCurationDataset.from_rows((_curation("target-keep", ("S1",)),)),
            TargetDecisionDataset.from_rows(
                (TargetDecisionRecord("target-missing", "exclude", "bad"),)
            ),
        )
    with pytest.raises(ValueError, match="at least one row"):
        apply_target_decisions(
            _metadata_dataset(_sample("S1")),
            TargetCurationDataset.from_rows((_curation("target-keep", ("S1",)),)),
            TargetDecisionDataset.from_rows(
                (TargetDecisionRecord("target-keep", "exclude", "bad"),)
            ),
        )


def _decision_csv() -> str:
    """Return a small reviewed target-decision CSV."""
    return (
        "\n".join(
            (
                "target_id,decision,reason,requested_group_id,reviewer,decision_date,note",
                "target-keep,retain,usable,Group,Reviewer,2026-06-11,",
                "target-rerun,rerun_qpadm,needs rerun,Other,Reviewer,2026-06-11,",
            )
        )
        + "\n"
    )


def _sample(sample_id: str) -> SampleMetadataRecord:
    """Return one sample metadata record for decision tests."""
    return SampleMetadataRecord(
        status="published",
        dataset_id="dataset",
        sample_id=sample_id,
        accession_id=f"accession-{sample_id}",
        publication_key="publication",
        publication="Publication",
        region="britain",
        site="Site",
        time_bce=2500,
        date_uncertainty=50,
        sex="unknown",
        method="metadata",
    )


def _metadata_dataset(*records: SampleMetadataRecord) -> SampleMetadataDataset:
    """Return a sample metadata dataset for decision tests."""
    return SampleMetadataDataset.from_rows(records)


def _curation(target_id: str, sample_ids: tuple[str, ...]) -> TargetCurationRecord:
    """Return one curation record for decision tests."""
    return TargetCurationRecord(
        status="published",
        target_id=target_id,
        region="britain",
        source="steppe",
        start_bce=2600,
        end_bce=2400,
        sample_ids=sample_ids,
        sample_count=len(sample_ids),
        ancestry_method="qpadm_steppe",
        aggregation_method="unweighted_mean",
        citation_key="citation",
        citation="Citation",
    )
