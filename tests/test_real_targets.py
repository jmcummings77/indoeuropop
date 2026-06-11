"""Tests for real-data target-build workflow plumbing."""

import argparse
import json
from pathlib import Path

import pytest
from pytest import CaptureFixture

from indoeuropop.data.real_targets import (
    AADRQpAdmTargetDiagnostics,
    AADRQpAdmTargetWorkflowConfig,
    aadr_qpadm_target_diagnostics_payload,
    qpadm_table_data_row_count,
    run_aadr_qpadm_target_workflow,
    target_counts_by_region,
    write_aadr_qpadm_target_diagnostics_json,
)
from indoeuropop.data.targets import TargetDataset, TargetObservation
from indoeuropop.orchestration.real_target_cli import (
    run_build_aadr_qpadm_targets_command,
)


def test_run_aadr_qpadm_target_workflow_writes_outputs(tmp_path: Path) -> None:
    """The workflow should build targets and diagnostics from local inputs."""
    aadr_dir = _tiny_aadr_dir(tmp_path)
    groups_path = tmp_path / "groups.tsv"
    qpadm_path = tmp_path / "qpadm.csv"
    groups_path.write_text(
        "\n".join(
            (
                "region\taadr_group_id",
                "britain\tEngland_BellBeaker",
                "central_europe\tGermany_CordedWare",
            )
        )
        + "\n",
        encoding="utf-8",
    )
    qpadm_path.write_text(
        "\n".join(
            (
                "Genetic ID,steppe_fraction,stderr,qpadm_pvalue",
                "I001,0.25,0.05,0.5",
                "I002,0.9,,0.1",
                "BAD,1.2,0.1,0.2",
            )
        )
        + "\n",
        encoding="utf-8",
    )
    config = AADRQpAdmTargetWorkflowConfig(
        aadr_dir=aadr_dir,
        aadr_groups_path=groups_path,
        qpadm_estimates_path=qpadm_path,
        sample_metadata_path=tmp_path / "out" / "sample-metadata.csv",
        target_curation_path=tmp_path / "out" / "target-curation.csv",
        ancestry_estimates_path=tmp_path / "out" / "sample-ancestry.csv",
        target_output_path=tmp_path / "out" / "targets.csv",
        diagnostics_json_path=tmp_path / "out" / "diagnostics.json",
    )
    diagnostics_json_path = tmp_path / "out" / "diagnostics.json"

    result = run_aadr_qpadm_target_workflow(config)
    diagnostics_payload = json.loads(diagnostics_json_path.read_text(encoding="utf-8"))

    assert len(result.target_dataset.observations) == 1
    assert result.target_dataset.observations[0].region == "britain"
    assert result.diagnostics.requested_target_count == 2
    assert result.diagnostics.selected_sample_count == 2
    assert result.diagnostics.raw_qpadm_row_count == 3
    assert result.diagnostics.parsed_qpadm_estimate_count == 2
    assert result.diagnostics.retained_sample_estimate_count == 1
    assert result.diagnostics.retained_sample_count == 1
    assert result.diagnostics.retained_target_count == 1
    assert result.diagnostics.dropped_target_count == 1
    assert result.diagnostics.dropped_target_ids == (
        "aadr-central-europe-steppe-germany-cordedware",
    )
    assert result.diagnostics.target_counts_by_region == (("britain", 1),)
    assert diagnostics_payload["target_counts_by_region"] == {"britain": 1}
    assert config.sample_metadata_path.exists()
    assert config.target_curation_path.exists()
    assert config.ancestry_estimates_path.exists()
    assert config.target_output_path.read_text(encoding="utf-8").startswith(
        "status,region,source,time_bce"
    )


def test_qpadm_table_data_row_count_handles_empty_file(tmp_path: Path) -> None:
    """Raw qpAdm row counting should be defensive for empty files."""
    path = tmp_path / "empty.csv"
    path.write_text("", encoding="utf-8")

    assert qpadm_table_data_row_count(path) == 0


def test_target_counts_by_region_preserves_first_seen_order() -> None:
    """Target count summaries should be stable and human-readable."""
    dataset = TargetDataset.from_rows(
        (
            _observation("britain"),
            _observation("central_europe"),
            _observation("britain"),
        )
    )

    assert target_counts_by_region(dataset) == (
        ("britain", 2),
        ("central_europe", 1),
    )


def test_write_aadr_qpadm_target_diagnostics_json_round_trips(
    tmp_path: Path,
) -> None:
    """Diagnostics helpers should produce JSON-ready payloads."""
    diagnostics = AADRQpAdmTargetDiagnostics(
        requested_target_count=2,
        selected_sample_count=3,
        raw_qpadm_row_count=4,
        parsed_qpadm_estimate_count=3,
        retained_sample_estimate_count=2,
        retained_sample_count=2,
        retained_target_count=1,
        dropped_target_count=1,
        target_observation_count=1,
        dropped_target_ids=("target-drop",),
        target_counts_by_region=(("britain", 1),),
    )
    path = tmp_path / "nested" / "diagnostics.json"

    returned_path = write_aadr_qpadm_target_diagnostics_json(diagnostics, path)
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert returned_path == path
    assert aadr_qpadm_target_diagnostics_payload(diagnostics)["dropped_target_ids"] == [
        "target-drop"
    ]
    assert payload["dropped_target_count"] == 1
    assert payload["target_counts_by_region"] == {"britain": 1}


def test_run_aadr_qpadm_target_workflow_requires_estimates(
    tmp_path: Path,
) -> None:
    """A workflow with no retained estimates should fail before targets exist."""
    aadr_dir = _tiny_aadr_dir(tmp_path)
    groups_path = tmp_path / "groups.tsv"
    qpadm_path = tmp_path / "qpadm.csv"
    groups_path.write_text("britain\tEngland_BellBeaker\n", encoding="utf-8")
    qpadm_path.write_text(
        "Genetic ID,steppe_fraction,stderr\nI001,0.25,\n",
        encoding="utf-8",
    )
    config = AADRQpAdmTargetWorkflowConfig(
        aadr_dir=aadr_dir,
        aadr_groups_path=groups_path,
        qpadm_estimates_path=qpadm_path,
        sample_metadata_path=tmp_path / "sample-metadata.csv",
        target_curation_path=tmp_path / "target-curation.csv",
        ancestry_estimates_path=tmp_path / "sample-ancestry.csv",
        target_output_path=tmp_path / "targets.csv",
    )

    with pytest.raises(ValueError, match="sample ancestry dataset"):
        run_aadr_qpadm_target_workflow(config)


def test_real_target_cli_reports_dropped_targets(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    """The real target CLI wrapper should print dropped target IDs."""
    aadr_dir = _tiny_aadr_dir(tmp_path)
    groups_path = tmp_path / "groups.tsv"
    qpadm_path = tmp_path / "qpadm.csv"
    output_dir = tmp_path / "outputs"
    groups_path.write_text(
        "region\taadr_group_id\nbritain\tEngland_BellBeaker\n"
        "central_europe\tGermany_CordedWare\n",
        encoding="utf-8",
    )
    qpadm_path.write_text(
        "Genetic ID,steppe_fraction,stderr\nI001,0.25,0.05\n",
        encoding="utf-8",
    )
    args = argparse.Namespace(
        aadr_dir=aadr_dir,
        aadr_groups=groups_path,
        qpadm_estimates=qpadm_path,
        sample_metadata_out=output_dir / "sample-metadata.csv",
        target_curation_out=output_dir / "target-curation.csv",
        ancestry_estimates_out=output_dir / "sample-ancestry.csv",
        target_output=output_dir / "targets.csv",
        target_diagnostics_json=None,
        aadr_dataset_id="aadr-v66-p1-1240k",
        source="steppe",
        qpadm_method="qpadm_steppe",
        aggregation_method="unweighted_mean",
        aadr_group_match="exact",
        allow_missing_aadr_groups=False,
        default_standard_error=None,
    )

    exit_code = run_build_aadr_qpadm_targets_command(
        args,
        argparse.ArgumentParser(),
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "dropped_target=aadr-central-europe-steppe-germany-cordedware" in (
        captured.out
    )


def _observation(region: str) -> TargetObservation:
    """Return one target observation for count-summary tests."""
    return TargetObservation(
        status="published",
        region=region,
        source="steppe",
        time_bce=2500,
        mean=0.2,
        uncertainty=0.05,
        citation_key="citation",
        citation="Citation",
    )


def _tiny_aadr_dir(tmp_path: Path) -> Path:
    """Create a tiny two-sample AADR quartet."""
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
    rows = (
        (
            "I001",
            "123",
            "I001",
            "FirstPublication",
            "PublicationKey",
            "https://doi.org/example",
            "ENA:PRJEB00000",
            "4300",
            "80",
            "2500-2300 BCE",
            "England_BellBeaker",
            "Example Site",
            "England",
            "M",
            "Pass",
        ),
        (
            "I002",
            "124",
            "I002",
            "FirstPublication",
            "PublicationKey",
            "https://doi.org/example",
            "ENA:PRJEB00000",
            "4200",
            "70",
            "2400-2200 BCE",
            "Germany_CordedWare",
            "Example Site",
            "Germany",
            "F",
            "Pass",
        ),
    )
    body = "\n".join("\t".join(row) for row in rows)
    (root / "tiny.anno").write_text(f"{header}\n{body}\n", encoding="utf-8")
    (root / "tiny.ind").write_text(
        "I001 M England_BellBeaker\nI002 F Germany_CordedWare\n",
        encoding="utf-8",
    )
    (root / "tiny.snp").write_text("rs1 1 0.0 1 A G\n", encoding="utf-8")
    (root / "tiny.geno").write_text("00\n", encoding="utf-8")
    return root
