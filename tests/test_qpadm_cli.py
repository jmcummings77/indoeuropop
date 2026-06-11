"""Tests for qpAdm-specific CLI planning commands."""

import json
from pathlib import Path

import pytest

from indoeuropop.orchestration.cli import main


def test_cli_plan_qpadm_reruns_writes_manifest_and_groups(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The CLI should write reviewed qpAdm rerun artifacts."""
    curation_path = tmp_path / "target-curation.csv"
    decisions_path = tmp_path / "target-decisions.csv"
    manifest_path = tmp_path / "qpadm-reruns.json"
    groups_path = tmp_path / "qpadm-reruns.tsv"
    curation_path.write_text(
        "\n".join(
            (
                "status,target_id,region,source,start_bce,end_bce,sample_ids,"
                "sample_count,ancestry_method,aggregation_method,citation_key,"
                "citation,note",
                "published,target-drop,britain,steppe,2500,2400,S1,1,"
                "qpadm_steppe,unweighted_mean,key,Citation,"
                "requested_group_id=England_BellBeaker",
            )
        )
        + "\n",
        encoding="utf-8",
    )
    decisions_path.write_text(
        "\n".join(
            (
                "target_id,decision,reason,requested_group_id,reviewer,"
                "decision_date,note",
                "target-drop,rerun_qpadm,"
                "All selected samples have steppe fractions outside 0-1,"
                "England_BellBeaker,Codex,2026-06-11,",
            )
        )
        + "\n",
        encoding="utf-8",
    )

    exit_code = main(
        [
            "plan-qpadm-reruns",
            "--target-curation",
            str(curation_path),
            "--target-decisions",
            str(decisions_path),
            "--qpadm-rerun-manifest-json",
            str(manifest_path),
            "--qpadm-rerun-groups-out",
            str(groups_path),
        ]
    )
    captured = capsys.readouterr()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert f"qpadm_rerun_manifest={manifest_path}" in captured.out
    assert "qpadm_rerun_group=invalid_steppe_fraction,target_count=1" in captured.out
    assert f"qpadm_rerun_groups={groups_path}" in captured.out
    assert manifest["target_count"] == 1
    assert "England_BellBeaker" in groups_path.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "argv",
    [
        ["plan-qpadm-reruns"],
        ["plan-qpadm-reruns", "--target-curation", "curation.csv"],
        [
            "plan-qpadm-reruns",
            "--target-curation",
            "curation.csv",
            "--target-decisions",
            "decisions.csv",
        ],
    ],
)
def test_cli_plan_qpadm_reruns_requires_paths(argv: list[str]) -> None:
    """The qpAdm rerun planning command should reject incomplete paths."""
    with pytest.raises(SystemExit) as exc_info:
        main(argv)
    assert exc_info.value.code == 2
