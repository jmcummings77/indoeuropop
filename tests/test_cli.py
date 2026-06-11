"""Tests for the command-line interface."""

import json
from pathlib import Path

import pytest
from pytest import CaptureFixture, raises

from indoeuropop.cli import main


def test_cli_demo_prints_summary(capsys: CaptureFixture[str]) -> None:
    """The default demo command should print a final ancestry summary."""
    exit_code = main(["demo"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "final_steppe_ancestry=" in captured.out


def test_cli_build_targets_writes_target_csv(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    """The CLI should build target observations from curated sample inputs."""
    output_path = tmp_path / "outputs" / "targets.csv"

    exit_code = main(
        [
            "build-targets",
            "--sample-metadata",
            "examples/sample-metadata.example.csv",
            "--target-curation",
            "examples/target-curation.example.csv",
            "--ancestry-estimates",
            "examples/sample-ancestry-estimates.example.csv",
            "--target-output",
            str(output_path),
        ]
    )
    captured = capsys.readouterr()
    output_text = output_path.read_text(encoding="utf-8")

    assert exit_code == 0
    assert "target_count=1" in captured.out
    assert f"target_output={output_path}" in captured.out
    assert output_text.startswith("status,region,source,time_bce")
    assert "synthetic,britain,steppe,2900,0.08,0.03" in output_text


def test_cli_filter_target_inputs_drops_incomplete_targets(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    """The CLI should drop target rows missing valid sample estimates."""
    sample_metadata = tmp_path / "sample-metadata.csv"
    target_curation = tmp_path / "target-curation.csv"
    ancestry_estimates = tmp_path / "sample-ancestry-estimates.csv"
    filtered_samples = tmp_path / "outputs" / "filtered-samples.csv"
    filtered_curation = tmp_path / "outputs" / "filtered-curation.csv"
    sample_metadata.write_text(
        "status,dataset_id,sample_id,accession_id,publication_key,publication,"
        "region,site,time_bce,date_uncertainty,sex,method,note\n"
        "synthetic,dataset,S1,A1,key,Publication,britain,Site,2900,50,unknown,method,\n"
        "synthetic,dataset,S2,A2,key,Publication,britain,Site,2900,50,unknown,method,\n",
        encoding="utf-8",
    )
    target_curation.write_text(
        "status,target_id,region,source,start_bce,end_bce,sample_ids,sample_count,"
        "ancestry_method,aggregation_method,citation_key,citation,note\n"
        "synthetic,target-keep,britain,steppe,3000,2800,S1,1,qpadm_steppe,"
        "unweighted_mean,key,Citation,\n"
        "synthetic,target-drop,britain,steppe,3000,2800,S2,1,qpadm_steppe,"
        "unweighted_mean,key,Citation,\n",
        encoding="utf-8",
    )
    ancestry_estimates.write_text(
        "status,sample_id,source,estimate,standard_error,method,note\n"
        "synthetic,S1,steppe,0.2,0.05,qpadm_steppe,\n",
        encoding="utf-8",
    )

    exit_code = main(
        [
            "filter-target-inputs",
            "--sample-metadata",
            str(sample_metadata),
            "--target-curation",
            str(target_curation),
            "--ancestry-estimates",
            str(ancestry_estimates),
            "--sample-metadata-out",
            str(filtered_samples),
            "--target-curation-out",
            str(filtered_curation),
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "filtered_sample_count=1" in captured.out
    assert "filtered_target_count=1" in captured.out
    assert "dropped_target=target-drop" in captured.out
    assert "S1" in filtered_samples.read_text(encoding="utf-8")
    assert "S2" not in filtered_samples.read_text(encoding="utf-8")
    assert "target-keep" in filtered_curation.read_text(encoding="utf-8")


def test_cli_download_sources_materializes_catalog_entries(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    """The CLI should download or copy cataloged data-source records."""
    output_dir = tmp_path / "sources"
    manifest_path = tmp_path / "manifests" / "downloads.csv"

    exit_code = main(
        [
            "download-sources",
            "--data-sources",
            "examples/data-sources.example.toml",
            "--output-dir",
            str(output_dir),
            "--download-manifest-csv",
            str(manifest_path),
        ]
    )
    captured = capsys.readouterr()
    downloaded_path = output_dir / "target-observations.example.csv"

    assert exit_code == 0
    assert downloaded_path.exists()
    assert "download_count=1" in captured.out
    assert "downloaded_source=synthetic-target-example" in captured.out
    assert manifest_path.read_text(encoding="utf-8").startswith(
        "dataset_id,kind,status,source_uri"
    )


def test_cli_load_aadr_writes_sample_metadata(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    """The CLI should normalize local AADR annotations to sample metadata."""
    aadr_dir = _tiny_aadr_dir(tmp_path)
    output_path = tmp_path / "outputs" / "aadr-sample-metadata.csv"

    exit_code = main(
        [
            "load-aadr",
            "--aadr-dir",
            str(aadr_dir),
            "--sample-metadata-out",
            str(output_path),
            "--aadr-limit",
            "1",
        ]
    )
    captured = capsys.readouterr()
    output_text = output_path.read_text(encoding="utf-8")

    assert exit_code == 0
    assert f"aadr_sample_metadata={output_path}" in captured.out
    assert output_text.startswith("status,dataset_id,sample_id")
    assert "published,aadr-v66-p1-1240k,I001.SG" in output_text


def test_cli_load_qpadm_estimates_writes_sample_ancestry_csv(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    """The CLI should convert qpAdm-style rows to sample ancestry estimates."""
    table_path = tmp_path / "qpadm.csv"
    output_path = tmp_path / "outputs" / "sample-ancestry-estimates.csv"
    table_path.write_text(
        "Genetic ID,steppe_fraction,stderr,qpadm_pvalue\n" "I001.SG,0.8,0.04,0.2\n",
        encoding="utf-8",
    )

    exit_code = main(
        [
            "load-qpadm-estimates",
            "--qpadm-estimates",
            str(table_path),
            "--ancestry-estimates-out",
            str(output_path),
        ]
    )
    captured = capsys.readouterr()
    output_text = output_path.read_text(encoding="utf-8")

    assert exit_code == 0
    assert f"sample_ancestry_estimates={output_path}" in captured.out
    assert output_text.startswith("status,sample_id,source")
    assert "published,I001.SG,steppe,0.8,0.04,qpadm_steppe" in output_text


def test_cli_plan_qpadm_run_writes_manifest(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    """The CLI should preflight and manifest an external qpAdm command."""
    aadr_dir = _tiny_aadr_dir(tmp_path)
    groups_path = tmp_path / "groups.tsv"
    output_path = tmp_path / "data" / "qpadm" / "steppe-estimates.csv"
    f2_dir = tmp_path / "data" / "qpadm" / "f2"
    manifest_path = tmp_path / "manifests" / "qpadm.json"
    groups_path.write_text(
        "region\taadr_group_id\niberia\tGreece_EBA\n", encoding="utf-8"
    )

    exit_code = main(
        [
            "plan-qpadm-run",
            "--genotype-prefix",
            str(aadr_dir),
            "--aadr-groups",
            str(groups_path),
            "--qpadm-estimates",
            str(output_path),
            "--qpadm-f2-dir",
            str(f2_dir),
            "--qpadm-manifest-json",
            str(manifest_path),
        ]
    )
    captured = capsys.readouterr()
    manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert f"qpadm_manifest={manifest_path}" in captured.out
    assert "qpadm_command=Rscript scripts/run_qpadm.R --prefix" in captured.out
    assert manifest_payload["target_group_count"] == 1
    assert manifest_payload["regions"] == ["iberia"]
    assert manifest_payload["command"][0] == "Rscript"


def test_cli_prepare_aadr_target_inputs_writes_real_input_csvs(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    """The CLI should prepare target-pipeline inputs from AADR groups."""
    aadr_dir = _tiny_aadr_dir(tmp_path)
    groups_path = tmp_path / "groups.tsv"
    sample_output = tmp_path / "outputs" / "aadr-samples.csv"
    curation_output = tmp_path / "outputs" / "aadr-curation.csv"
    groups_path.write_text(
        "region\taadr_group_id\ngreece\tGreece\nmissing\tMissing_Group\n",
        encoding="utf-8",
    )

    exit_code = main(
        [
            "prepare-aadr-target-inputs",
            "--aadr-dir",
            str(aadr_dir),
            "--aadr-groups",
            str(groups_path),
            "--aadr-group-match",
            "prefix",
            "--allow-missing-aadr-groups",
            "--sample-metadata-out",
            str(sample_output),
            "--target-curation-out",
            str(curation_output),
            "--ancestry-method",
            "qpAdm_pending",
            "--aggregation-method",
            "unweighted_mean",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "aadr_selected_sample_count=1" in captured.out
    assert "target_curation_count=1" in captured.out
    assert "unmatched_aadr_group=missing,Missing_Group" in captured.out
    assert "published,aadr-v66-p1-1240k,I001.SG" in sample_output.read_text(
        encoding="utf-8"
    )
    assert "published,aadr-greece-steppe-greece" in curation_output.read_text(
        encoding="utf-8"
    )
    assert "qpAdm_pending" in curation_output.read_text(encoding="utf-8")


def test_cli_suggest_aadr_groups_writes_group_tsv(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    """The CLI should suggest reviewable AADR region/group selections."""
    aadr_dir = _tiny_aadr_dir(tmp_path)
    output_path = tmp_path / "outputs" / "aadr-groups.tsv"

    exit_code = main(
        [
            "suggest-aadr-groups",
            "--aadr-dir",
            str(aadr_dir),
            "--aadr-groups-out",
            str(output_path),
            "--min-group-samples",
            "1",
        ]
    )
    captured = capsys.readouterr()
    output_text = output_path.read_text(encoding="utf-8")

    assert exit_code == 0
    assert "aadr_group_count=1" in captured.out
    assert f"aadr_groups={output_path}" in captured.out
    assert "iberia\tGreece_EBA" in output_text


@pytest.mark.parametrize(
    "argv",
    [
        ["load-aadr"],
        [
            "load-aadr",
            "--aadr-dir",
            "aadr",
        ],
    ],
)
def test_cli_load_aadr_requires_paths(argv: list[str]) -> None:
    """The AADR command should reject incomplete input paths."""
    with raises(SystemExit) as exc_info:
        main(argv)
    assert exc_info.value.code == 2


@pytest.mark.parametrize(
    "argv",
    [
        ["load-qpadm-estimates"],
        ["load-qpadm-estimates", "--qpadm-estimates", "qpadm.csv"],
    ],
)
def test_cli_load_qpadm_estimates_requires_paths(argv: list[str]) -> None:
    """The qpAdm conversion command should reject incomplete paths."""
    with raises(SystemExit) as exc_info:
        main(argv)
    assert exc_info.value.code == 2


@pytest.mark.parametrize(
    "argv",
    [
        ["plan-qpadm-run"],
        ["plan-qpadm-run", "--genotype-prefix", "aadr"],
        ["plan-qpadm-run", "--genotype-prefix", "aadr", "--aadr-groups", "groups.tsv"],
        [
            "plan-qpadm-run",
            "--genotype-prefix",
            "aadr",
            "--aadr-groups",
            "groups.tsv",
            "--qpadm-estimates",
            "steppe.csv",
        ],
    ],
)
def test_cli_plan_qpadm_run_requires_paths(argv: list[str]) -> None:
    """The qpAdm planning command should reject incomplete paths."""
    with raises(SystemExit) as exc_info:
        main(argv)
    assert exc_info.value.code == 2


@pytest.mark.parametrize(
    "argv",
    [
        ["prepare-aadr-target-inputs"],
        ["prepare-aadr-target-inputs", "--aadr-dir", "aadr"],
        [
            "prepare-aadr-target-inputs",
            "--aadr-dir",
            "aadr",
            "--aadr-groups",
            "groups.tsv",
        ],
        [
            "prepare-aadr-target-inputs",
            "--aadr-dir",
            "aadr",
            "--aadr-groups",
            "groups.tsv",
            "--sample-metadata-out",
            "samples.csv",
        ],
    ],
)
def test_cli_prepare_aadr_target_inputs_requires_paths(argv: list[str]) -> None:
    """The AADR target-input command should reject incomplete paths."""
    with raises(SystemExit) as exc_info:
        main(argv)
    assert exc_info.value.code == 2


@pytest.mark.parametrize(
    "argv",
    [
        ["suggest-aadr-groups"],
        ["suggest-aadr-groups", "--aadr-dir", "aadr"],
    ],
)
def test_cli_suggest_aadr_groups_requires_paths(argv: list[str]) -> None:
    """The AADR group-suggestion command should reject incomplete paths."""
    with raises(SystemExit) as exc_info:
        main(argv)
    assert exc_info.value.code == 2


@pytest.mark.parametrize(
    "argv",
    [
        ["download-sources"],
        [
            "download-sources",
            "--data-sources",
            "examples/data-sources.example.toml",
        ],
    ],
)
def test_cli_download_sources_requires_paths(argv: list[str]) -> None:
    """The download command should reject incomplete input paths."""
    with raises(SystemExit) as exc_info:
        main(argv)
    assert exc_info.value.code == 2


@pytest.mark.parametrize(
    "argv",
    [
        ["build-targets"],
        [
            "build-targets",
            "--sample-metadata",
            "examples/sample-metadata.example.csv",
        ],
        [
            "build-targets",
            "--sample-metadata",
            "examples/sample-metadata.example.csv",
            "--target-curation",
            "examples/target-curation.example.csv",
            "--ancestry-estimates",
            "examples/sample-ancestry-estimates.example.csv",
        ],
    ],
)
def test_cli_build_targets_requires_pipeline_paths(argv: list[str]) -> None:
    """The target-building command should reject incomplete input paths."""
    with raises(SystemExit) as exc_info:
        main(argv)
    assert exc_info.value.code == 2


@pytest.mark.parametrize(
    "argv",
    [
        ["filter-target-inputs"],
        ["filter-target-inputs", "--sample-metadata", "samples.csv"],
        [
            "filter-target-inputs",
            "--sample-metadata",
            "samples.csv",
            "--target-curation",
            "curation.csv",
        ],
        [
            "filter-target-inputs",
            "--sample-metadata",
            "samples.csv",
            "--target-curation",
            "curation.csv",
            "--ancestry-estimates",
            "estimates.csv",
        ],
        [
            "filter-target-inputs",
            "--sample-metadata",
            "samples.csv",
            "--target-curation",
            "curation.csv",
            "--ancestry-estimates",
            "estimates.csv",
            "--sample-metadata-out",
            "filtered-samples.csv",
        ],
    ],
)
def test_cli_filter_target_inputs_requires_paths(argv: list[str]) -> None:
    """The target-input filtering command should reject incomplete paths."""
    with raises(SystemExit) as exc_info:
        main(argv)
    assert exc_info.value.code == 2


def test_cli_demo_can_write_plot_and_use_config(tmp_path: Path) -> None:
    """The CLI should load config files and write optional plots."""
    config_path = tmp_path / "scenario.toml"
    plot_path = tmp_path / "plots" / "ancestry.png"
    manifest_path = tmp_path / "manifests" / "demo.json"
    config_path.write_text(
        """
        [simulation]
        start_bce = 3000
        end_bce = 2950
        step_years = 25

        [parameters]
        migration_rate = 0.001

        [counts.britain]
        local = 100
        steppe = 5
        """,
        encoding="utf-8",
    )

    exit_code = main(
        [
            "demo",
            "--config",
            str(config_path),
            "--plot",
            str(plot_path),
            "--manifest-json",
            str(manifest_path),
            "--region",
            "britain",
            "--stochastic",
            "--seed",
            "11",
        ]
    )

    assert exit_code == 0
    assert plot_path.exists()
    manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest_payload["metadata"]["simulator"] == "tau_leap"
    assert manifest_payload["metadata"]["seed"] == "11"
    assert {artifact["role"] for artifact in manifest_payload["artifacts"]} == {
        "config",
        "plot",
    }
    assert manifest_payload["fingerprints"][0]["kind"] == "simulation_result"


def test_cli_demo_can_compare_targets(
    tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    """The CLI should print target comparisons when a target CSV is supplied."""
    target_path = tmp_path / "targets.csv"
    target_path.write_text(
        "\n".join(
            [
                "status,region,source,time_bce,mean,uncertainty,citation_key,citation,note",
                'synthetic,britain,steppe,2750,0.1,0.05,key,"Synthetic",Example',
            ]
        ),
        encoding="utf-8",
    )

    exit_code = main(["demo", "--targets", str(target_path)])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "target_comparison=britain,steppe,2750.0" in captured.out


def test_cli_demo_can_write_provenance_csv(tmp_path: Path) -> None:
    """The CLI should write a provenance report for smoke runs."""
    target_path = tmp_path / "targets.csv"
    report_path = tmp_path / "reports" / "provenance.csv"
    manifest_path = tmp_path / "manifests" / "demo.json"
    target_path.write_text(
        "\n".join(
            [
                "status,region,source,time_bce,mean,uncertainty,citation_key,citation,note",
                'synthetic,britain,steppe,2750,0.1,0.05,key,"Synthetic",Example',
            ]
        ),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "demo",
            "--targets",
            str(target_path),
            "--provenance-csv",
            str(report_path),
            "--manifest-json",
            str(manifest_path),
        ]
    )
    report_text = report_path.read_text(encoding="utf-8")
    manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert "final_ancestry" in report_text
    assert "target_mean" in report_text
    assert "chi_square" in report_text
    assert {artifact["role"] for artifact in manifest_payload["artifacts"]} == {
        "provenance",
        "targets",
    }


def test_cli_demo_can_write_fingerprint_only_manifest(tmp_path: Path) -> None:
    """The CLI should write a manifest even when no file artifacts exist."""
    manifest_path = tmp_path / "manifests" / "demo.json"

    exit_code = main(["demo", "--manifest-json", str(manifest_path)])
    manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert manifest_payload["name"] == "cli-demo"
    assert manifest_payload["artifacts"] == []
    assert manifest_payload["metadata"]["simulator"] == "deterministic"
    assert manifest_payload["fingerprints"][0]["kind"] == "simulation_result"


def test_cli_sweep_can_write_outputs(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    """The sweep command should run a TOML-backed deterministic sweep."""
    sweep_csv = tmp_path / "outputs" / "sweep-runs.csv"
    sensitivity_csv = tmp_path / "outputs" / "sensitivity.csv"
    manifest_path = tmp_path / "outputs" / "sweep-manifest.json"

    exit_code = main(
        [
            "sweep",
            "--config",
            "examples/sweep.example.toml",
            "--sweep-runs-csv",
            str(sweep_csv),
            "--sensitivity-csv",
            str(sensitivity_csv),
            "--manifest-json",
            str(manifest_path),
        ]
    )
    captured = capsys.readouterr()
    manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert "sweep_run_count=3" in captured.out
    assert "sensitivity=migration_rate" in captured.out
    assert "summary_final_ancestry" in sweep_csv.read_text(encoding="utf-8")
    assert sensitivity_csv.read_text(encoding="utf-8").startswith("parameter,outcome")
    assert manifest_payload["name"] == "cli-sweep"
    assert manifest_payload["fingerprints"][0]["kind"] == "sweep_collection"
    assert {artifact["role"] for artifact in manifest_payload["artifacts"]} == {
        "config",
        "sensitivity",
        "sweep_runs",
    }


def test_cli_sweep_can_write_target_fit_outputs(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    """The sweep command should rank deterministic runs against targets."""
    target_path = tmp_path / "targets.csv"
    target_fit_csv = tmp_path / "outputs" / "target-fit.csv"
    manifest_path = tmp_path / "outputs" / "sweep-manifest.json"
    target_path.write_text(
        "\n".join(
            [
                "status,region,source,time_bce,mean,uncertainty,citation_key,citation,note",
                'synthetic,britain,steppe,2900,0.1,0.05,key,"Synthetic",Example',
            ]
        ),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "sweep",
            "--config",
            "examples/sweep.example.toml",
            "--targets",
            str(target_path),
            "--target-fit-csv",
            str(target_fit_csv),
            "--manifest-json",
            str(manifest_path),
            "--fit-metric",
            "root_mean_squared_error",
        ]
    )
    captured = capsys.readouterr()
    manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert "best_target_fit=" in captured.out
    assert "metric=root_mean_squared_error" in captured.out
    assert "fit_root_mean_squared_error" in target_fit_csv.read_text(encoding="utf-8")
    assert manifest_payload["metadata"]["target_fit_metric"] == (
        "root_mean_squared_error"
    )
    assert {artifact["role"] for artifact in manifest_payload["artifacts"]} == {
        "config",
        "targets",
        "target_fit",
    }


def test_cli_sweep_requires_config() -> None:
    """The sweep command should reject missing TOML configuration."""
    with raises(SystemExit) as exc_info:
        main(["sweep"])
    assert exc_info.value.code == 2


def test_cli_sweep_target_fit_requires_targets() -> None:
    """The sweep command should reject target-fit CSVs without target data."""
    with raises(SystemExit) as exc_info:
        main(
            [
                "sweep",
                "--config",
                "examples/sweep.example.toml",
                "--target-fit-csv",
                "target-fit.csv",
            ]
        )
    assert exc_info.value.code == 2


def _tiny_aadr_dir(tmp_path: Path) -> Path:
    """Create a tiny AADR quartet for CLI tests."""
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
            "Latitude",
            "Longitude",
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
            "40.4",
            "-3.7",
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
