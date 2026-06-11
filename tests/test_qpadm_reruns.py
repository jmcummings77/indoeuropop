"""Tests for reviewed qpAdm rerun manifests."""

import json
from pathlib import Path

import pytest

from indoeuropop.data.aadr_curation import load_aadr_group_selections
from indoeuropop.data.qpadm_reruns import (
    QpAdmRerunGroup,
    QpAdmRerunTarget,
    build_qpadm_rerun_manifest,
    load_qpadm_rerun_manifest_inputs,
    qpadm_rerun_groups_tsv,
    qpadm_rerun_manifest_payload,
    write_qpadm_rerun_groups_tsv,
    write_qpadm_rerun_manifest_json,
)
from indoeuropop.data.target_curation import (
    TargetCurationDataset,
    TargetCurationRecord,
    write_target_curation_csv,
)
from indoeuropop.data.target_decisions import (
    TargetDecisionDataset,
    TargetDecisionRecord,
    write_target_decisions_csv,
)


def test_build_qpadm_rerun_manifest_groups_failure_reasons(
    tmp_path: Path,
) -> None:
    """Rerun manifests should group targets by reviewed failure reason."""
    curation = TargetCurationDataset.from_rows(
        (
            _curation("target-steppe", "GroupSteppe", 3),
            _curation("target-se", "GroupSE", 2),
            _curation("target-replicated", "GroupReplicated", 4),
            _curation("target-other", "GroupOther", 1),
            _curation("target-retain", "GroupRetain", 5),
        )
    )
    decisions = TargetDecisionDataset.from_rows(
        (
            TargetDecisionRecord(
                "target-steppe",
                "rerun_qpadm",
                "All 3 selected samples have steppe fractions outside 0-1",
            ),
            TargetDecisionRecord(
                "target-se",
                "rerun_qpadm",
                "All 2 selected samples have standard errors outside 0-1",
                requested_group_id="GroupSE",
            ),
            TargetDecisionRecord(
                "target-replicated",
                "rerun_qpadm",
                "Audit found identical replicated qpAdm estimate rows",
                requested_group_id="GroupReplicated",
            ),
            TargetDecisionRecord(
                "target-other",
                "rerun_qpadm",
                "Current table lacks complete reviewed evidence",
                requested_group_id="GroupOther",
            ),
            TargetDecisionRecord(
                "target-retain",
                "retain_with_caveat",
                "usable for exploratory comparison",
                requested_group_id="GroupRetain",
            ),
        )
    )
    curation_path = write_target_curation_csv(curation, tmp_path / "curation.csv")
    decisions_path = write_target_decisions_csv(decisions, tmp_path / "decisions.csv")

    manifest = load_qpadm_rerun_manifest_inputs(
        curation_path=curation_path,
        decisions_path=decisions_path,
    )
    payload = qpadm_rerun_manifest_payload(manifest)
    json_path = write_qpadm_rerun_manifest_json(manifest, tmp_path / "reruns.json")
    groups_path = write_qpadm_rerun_groups_tsv(manifest, tmp_path / "reruns.tsv")

    assert manifest.targets[0].requested_group_id == "GroupSteppe"
    assert [group.failure_reason for group in manifest.groups] == [
        "invalid_steppe_fraction",
        "invalid_standard_error",
        "replicated_group_level_estimates",
        "incomplete_qpadm_evidence",
    ]
    assert payload["target_count"] == 4
    assert json.loads(json_path.read_text(encoding="utf-8")) == payload
    assert qpadm_rerun_groups_tsv(manifest).startswith(
        "region\taadr_group_id\tfailure_reason"
    )
    assert load_aadr_group_selections(groups_path)[0].group_id == "GroupSteppe"


def test_qpadm_rerun_manifest_validates_inputs() -> None:
    """Malformed rerun manifests should fail with clear errors."""
    curation = TargetCurationDataset.from_rows((_curation("target", "Group", 1),))

    with pytest.raises(ValueError, match="rerun manifest"):
        build_qpadm_rerun_manifest(
            curation,
            TargetDecisionDataset.from_rows(
                (
                    TargetDecisionRecord(
                        "target",
                        "retain",
                        "usable",
                        requested_group_id="Group",
                    ),
                )
            ),
        )
    with pytest.raises(ValueError, match="unknown target"):
        build_qpadm_rerun_manifest(
            curation,
            TargetDecisionDataset.from_rows(
                (
                    TargetDecisionRecord(
                        "missing",
                        "rerun_qpadm",
                        "missing evidence",
                        requested_group_id="Missing",
                    ),
                )
            ),
        )
    with pytest.raises(ValueError, match="requested_group_id"):
        build_qpadm_rerun_manifest(
            TargetCurationDataset.from_rows((_curation("target", "", 1, note=""),)),
            TargetDecisionDataset.from_rows(
                (TargetDecisionRecord("target", "rerun_qpadm", "missing evidence"),)
            ),
        )
    with pytest.raises(ValueError, match="target_id"):
        QpAdmRerunTarget("", "Group", "britain", 1, "incomplete_qpadm_evidence", "why")
    with pytest.raises(ValueError, match="sample_count"):
        QpAdmRerunTarget(
            "target", "Group", "britain", 0, "incomplete_qpadm_evidence", "why"
        )
    valid_target = QpAdmRerunTarget(
        "target", "Group", "britain", 1, "incomplete_qpadm_evidence", "why"
    )
    with pytest.raises(ValueError, match="at least one"):
        QpAdmRerunGroup("incomplete_qpadm_evidence", ())
    with pytest.raises(ValueError, match="failure reason"):
        QpAdmRerunGroup("invalid_steppe_fraction", (valid_target,))


def _curation(
    target_id: str,
    requested_group_id: str,
    sample_count: int,
    *,
    note: str | None = None,
) -> TargetCurationRecord:
    """Return one target curation record for rerun tests."""
    group_note = f"requested_group_id={requested_group_id}" if note is None else note
    return TargetCurationRecord(
        status="published",
        target_id=target_id,
        region="britain",
        source="steppe",
        start_bce=2500,
        end_bce=2400,
        sample_ids=tuple(f"S{i}" for i in range(sample_count)),
        sample_count=sample_count,
        ancestry_method="qpadm_steppe",
        aggregation_method="unweighted_mean",
        citation_key="citation",
        citation="Citation",
        note=group_note,
    )
