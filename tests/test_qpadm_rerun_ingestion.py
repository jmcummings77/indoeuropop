"""Tests for qpAdm rerun ingestion and pre/post target comparison."""

import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from indoeuropop.data.ancestry_estimates import (
    SampleAncestryEstimate,
    SampleAncestryEstimateDataset,
)
from indoeuropop.data.qpadm_rerun_ingestion import (
    compare_qpadm_rerun_targets,
    merge_sample_ancestry_estimate_datasets,
    run_qpadm_rerun_ingestion_workflow,
)
from indoeuropop.data.qpadm_rerun_models import (
    QpAdmRerunIngestionConfig,
    QpAdmRerunIngestionDiagnostics,
    QpAdmRerunTargetComparison,
)
from indoeuropop.data.target_curation import TargetCurationRecord
from indoeuropop.data.targets import TargetObservation
from indoeuropop.orchestration.cli import main
from indoeuropop.reporting.qpadm_rerun_report import (
    qpadm_rerun_comparison_to_csv,
    qpadm_rerun_ingestion_diagnostics_payload,
    qpadm_rerun_report_markdown,
)


def test_run_qpadm_rerun_ingestion_workflow_rescues_targets(
    tmp_path: Path,
) -> None:
    """Rerun ingestion should merge estimates and report newly buildable targets."""
    config = _rerun_config(tmp_path, with_decisions=True)

    result = run_qpadm_rerun_ingestion_workflow(config)
    diagnostics = result.diagnostics
    comparison_csv = config.comparison_csv_path.read_text(encoding="utf-8")
    report = config.report_markdown_path.read_text(encoding="utf-8")
    assert config.diagnostics_json_path is not None
    payload = json.loads(config.diagnostics_json_path.read_text(encoding="utf-8"))

    assert len(result.baseline_targets.observations) == 1
    assert len(result.post_targets.observations) == 2
    assert result.accepted_targets is not None
    assert len(result.accepted_targets.observations) == 1
    assert result.merged_ancestry_estimates.estimate_count == 2
    assert diagnostics.baseline_raw_qpadm_row_count == 2
    assert diagnostics.rerun_raw_qpadm_row_count == 1
    assert diagnostics.baseline_parsed_qpadm_estimate_count == 1
    assert diagnostics.rerun_parsed_qpadm_estimate_count == 1
    assert diagnostics.baseline_sample_estimate_count == 1
    assert diagnostics.rerun_sample_estimate_count == 1
    assert diagnostics.accepted_target_observation_count == 1
    assert diagnostics.rescued_target_count == 1
    assert diagnostics.lost_target_count == 0
    assert diagnostics.unchanged_retained_target_count == 1
    assert diagnostics.unchanged_dropped_target_count == 0
    assert diagnostics.reviewed_rerun_target_count == 1
    assert diagnostics.rescued_reviewed_rerun_target_count == 1
    assert diagnostics.rescued_target_ids == (
        "aadr-central-europe-steppe-germany-cordedware",
    )
    assert diagnostics.post_target_counts_by_region == (
        ("britain", 1),
        ("central_europe", 1),
    )
    assert "change" in comparison_csv
    assert "rescued" in comparison_csv
    assert "accepted target observations: `1`" in report
    assert "reviewed rerun targets rescued" in report
    assert payload["rescued_target_count"] == 1
    assert payload["accepted_target_observation_count"] == 1
    assert config.baseline_target_output_path is not None
    assert config.baseline_target_output_path.exists()
    assert config.accepted_target_output_path is not None
    assert config.accepted_target_output_path.exists()


def test_run_qpadm_rerun_ingestion_workflow_allows_unreviewed_inputs(
    tmp_path: Path,
) -> None:
    """The workflow should also compare pre/post availability without decisions."""
    config = _rerun_config(tmp_path, with_decisions=False)

    result = run_qpadm_rerun_ingestion_workflow(config)

    assert result.accepted_targets is None
    assert result.diagnostics.reviewed_rerun_target_count == 0
    assert result.comparisons[1].decision == ""


def test_run_qpadm_rerun_ingestion_requires_decisions_for_accepted_targets(
    tmp_path: Path,
) -> None:
    """Accepted-target output should require an explicit decision file."""
    config = replace(
        _rerun_config(tmp_path, with_decisions=False),
        accepted_target_output_path=tmp_path / "accepted.csv",
    )

    with pytest.raises(ValueError, match="accepted_target_output_path"):
        run_qpadm_rerun_ingestion_workflow(config)


def test_merge_sample_ancestry_estimate_datasets_prefers_reruns() -> None:
    """Validated rerun rows should replace baseline rows with the same identity."""
    baseline = SampleAncestryEstimateDataset.from_rows(
        (
            _estimate("S1", 0.1, note="baseline"),
            _estimate("S2", 0.2, note="baseline"),
        )
    )
    rerun = SampleAncestryEstimateDataset.from_rows(
        (_estimate("S2", 0.4, note="rerun"), _estimate("S3", 0.5, note="rerun"))
    )

    merged = merge_sample_ancestry_estimate_datasets(baseline, rerun)

    assert tuple(estimate.sample_id for estimate in merged.estimates) == (
        "S1",
        "S2",
        "S3",
    )
    assert merged.estimate_for(
        sample_id="S2", source="steppe", method="qpadm_steppe"
    ).estimate == pytest.approx(0.4)


def test_compare_qpadm_rerun_targets_reports_lost_and_unchanged_dropped() -> None:
    """Direct comparison should represent loss and unchanged drops explicitly."""
    records = (_curation("lost"), _curation("dropped"))
    baseline = {"lost": _observation(0.2)}

    comparisons = compare_qpadm_rerun_targets(records, baseline, {})
    csv_text = qpadm_rerun_comparison_to_csv(comparisons)

    assert tuple(comparison.change for comparison in comparisons) == (
        "lost",
        "unchanged_dropped",
    )
    assert "lost" in csv_text
    assert "unchanged_dropped" in csv_text


def test_qpadm_rerun_report_handles_no_rescued_and_lost_recommendation() -> None:
    """Report text should distinguish no-rescue and lost-target situations."""
    no_rescue = _diagnostics(rescued=0, lost=0)
    lost = _diagnostics(rescued=0, lost=1)

    no_rescue_markdown = qpadm_rerun_report_markdown(no_rescue, ())
    lost_markdown = qpadm_rerun_report_markdown(lost, ())
    payload = qpadm_rerun_ingestion_diagnostics_payload(lost)

    assert "No targets became newly buildable" in no_rescue_markdown
    assert "No target availability changed" in no_rescue_markdown
    assert "Investigate lost target rows" in lost_markdown
    assert payload["lost_target_count"] == 1


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("target_id", "", "target_id"),
        ("baseline_status", "bad", "baseline_status"),
        ("post_status", "bad", "post_status"),
        ("change", "bad", "change"),
        ("baseline_mean", float("nan"), "numeric comparison"),
    ],
)
def test_qpadm_rerun_target_comparison_validation(
    field: str, value: object, message: str
) -> None:
    """Comparison records should fail early when labels or values are invalid."""
    kwargs: dict[str, Any] = {
        "target_id": "target",
        "region": "britain",
        "source": "steppe",
        "decision": "",
        "baseline_status": "retained",
        "post_status": "retained",
        "change": "unchanged_retained",
        "baseline_mean": 0.1,
        "post_mean": 0.2,
        "mean_delta": 0.1,
        "baseline_uncertainty": 0.05,
        "post_uncertainty": 0.04,
        field: value,
    }

    with pytest.raises(ValueError, match=message):
        QpAdmRerunTargetComparison(**kwargs)


def test_cli_ingest_qpadm_reruns_writes_outputs(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The CLI should run rerun ingestion and print the key output paths."""
    config = _rerun_config(tmp_path, with_decisions=True)

    exit_code = main(
        [
            "ingest-qpadm-reruns",
            "--aadr-dir",
            str(config.aadr_dir),
            "--aadr-groups",
            str(config.aadr_groups_path),
            "--qpadm-estimates",
            str(config.baseline_qpadm_estimates_path),
            "--qpadm-rerun-estimates",
            str(config.rerun_qpadm_estimates_path),
            "--sample-metadata-out",
            str(config.sample_metadata_path),
            "--target-curation-out",
            str(config.target_curation_path),
            "--ancestry-estimates-out",
            str(config.merged_ancestry_estimates_path),
            "--target-output",
            str(config.post_target_output_path),
            "--baseline-target-output",
            str(config.baseline_target_output_path),
            "--accepted-target-output",
            str(config.accepted_target_output_path),
            "--qpadm-rerun-comparison-csv",
            str(config.comparison_csv_path),
            "--qpadm-rerun-report-md",
            str(config.report_markdown_path),
            "--target-diagnostics-json",
            str(config.diagnostics_json_path),
            "--target-decisions",
            str(config.target_decisions_path),
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "accepted_target_count=1" in captured.out
    assert "rescued_target_count=1" in captured.out
    assert "rescued_target=aadr-central-europe-steppe-germany-cordedware" in (
        captured.out
    )
    assert f"qpadm_rerun_report_md={config.report_markdown_path}" in captured.out
    assert f"accepted_target_output={config.accepted_target_output_path}" in (
        captured.out
    )
    assert config.post_target_output_path.exists()
    assert config.accepted_target_output_path is not None
    assert config.accepted_target_output_path.exists()


def test_cli_ingest_qpadm_reruns_prints_lost_targets(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The CLI lost-target print path should remain covered and explicit."""
    diagnostics = _diagnostics(rescued=0, lost=1)

    def fake_workflow(config: QpAdmRerunIngestionConfig) -> SimpleNamespace:
        """Return a minimal fake result for CLI output testing."""
        return SimpleNamespace(diagnostics=diagnostics)

    monkeypatch.setattr(
        "indoeuropop.orchestration.qpadm_cli.run_qpadm_rerun_ingestion_workflow",
        fake_workflow,
    )

    exit_code = main(
        [
            "ingest-qpadm-reruns",
            "--aadr-dir",
            str(tmp_path),
            "--aadr-groups",
            str(tmp_path / "groups.tsv"),
            "--qpadm-estimates",
            str(tmp_path / "baseline.csv"),
            "--qpadm-rerun-estimates",
            str(tmp_path / "rerun.csv"),
            "--sample-metadata-out",
            str(tmp_path / "metadata.csv"),
            "--target-curation-out",
            str(tmp_path / "curation.csv"),
            "--ancestry-estimates-out",
            str(tmp_path / "ancestry.csv"),
            "--target-output",
            str(tmp_path / "targets.csv"),
            "--qpadm-rerun-comparison-csv",
            str(tmp_path / "comparison.csv"),
            "--qpadm-rerun-report-md",
            str(tmp_path / "report.md"),
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "lost_target=lost-target" in captured.out


@pytest.mark.parametrize(
    "argv",
    [
        ["ingest-qpadm-reruns"],
        ["ingest-qpadm-reruns", "--aadr-dir", "aadr"],
    ],
)
def test_cli_ingest_qpadm_reruns_requires_paths(argv: list[str]) -> None:
    """The rerun-ingestion command should reject incomplete invocations."""
    with pytest.raises(SystemExit) as exc_info:
        main(argv)
    assert exc_info.value.code == 2


def _rerun_config(tmp_path: Path, *, with_decisions: bool) -> QpAdmRerunIngestionConfig:
    """Return a tiny rerun-ingestion config with one rescued target."""
    aadr_dir = _tiny_aadr_dir(tmp_path)
    groups_path = tmp_path / "groups.tsv"
    baseline_qpadm = tmp_path / "baseline-qpadm.csv"
    rerun_qpadm = tmp_path / "rerun-qpadm.csv"
    decisions_path = tmp_path / "target-decisions.csv"
    output_dir = tmp_path / "outputs"
    groups_path.write_text(
        "region\taadr_group_id\n"
        "britain\tEngland_BellBeaker\n"
        "central_europe\tGermany_CordedWare\n",
        encoding="utf-8",
    )
    baseline_qpadm.write_text(
        "Genetic ID,steppe_fraction,stderr,qpadm_pvalue\n"
        "I001,0.25,0.05,0.5\n"
        "I002,1.5,0.08,0.2\n",
        encoding="utf-8",
    )
    rerun_qpadm.write_text(
        "Genetic ID,steppe_fraction,stderr,qpadm_pvalue\n" "I002,0.45,0.08,0.6\n",
        encoding="utf-8",
    )
    decisions_path.write_text(
        "target_id,decision,reason,requested_group_id,reviewer,decision_date,note\n"
        "aadr-central-europe-steppe-germany-cordedware,rerun_qpadm,"
        "qpAdm rerun needed,Germany_CordedWare,Codex,2026-06-11,\n",
        encoding="utf-8",
    )
    return QpAdmRerunIngestionConfig(
        aadr_dir=aadr_dir,
        aadr_groups_path=groups_path,
        baseline_qpadm_estimates_path=baseline_qpadm,
        rerun_qpadm_estimates_path=rerun_qpadm,
        sample_metadata_path=output_dir / "sample-metadata.csv",
        target_curation_path=output_dir / "target-curation.csv",
        merged_ancestry_estimates_path=output_dir / "merged-ancestry.csv",
        post_target_output_path=output_dir / "targets-post.csv",
        comparison_csv_path=output_dir / "qpadm-rerun-comparison.csv",
        report_markdown_path=output_dir / "qpadm-rerun-report.md",
        diagnostics_json_path=output_dir / "qpadm-rerun-diagnostics.json",
        baseline_target_output_path=output_dir / "targets-baseline.csv",
        accepted_target_output_path=(
            output_dir / "targets-accepted.csv" if with_decisions else None
        ),
        target_decisions_path=decisions_path if with_decisions else None,
    )


def _estimate(sample_id: str, estimate: float, *, note: str) -> SampleAncestryEstimate:
    """Return one sample-level ancestry estimate for merge tests."""
    return SampleAncestryEstimate(
        status="published",
        sample_id=sample_id,
        source="steppe",
        estimate=estimate,
        standard_error=0.05,
        method="qpadm_steppe",
        note=note,
    )


def _curation(target_id: str) -> TargetCurationRecord:
    """Return one target curation record for direct comparison tests."""
    return TargetCurationRecord(
        status="published",
        target_id=target_id,
        region="britain",
        source="steppe",
        start_bce=2500,
        end_bce=2400,
        sample_ids=("S1",),
        sample_count=1,
        ancestry_method="qpadm_steppe",
        aggregation_method="unweighted_mean",
        citation_key="citation",
        citation="Citation",
    )


def _observation(mean: float) -> TargetObservation:
    """Return one target observation for direct comparison tests."""
    return TargetObservation(
        status="published",
        region="britain",
        source="steppe",
        time_bce=2450,
        mean=mean,
        uncertainty=0.05,
        citation_key="citation",
        citation="Citation",
    )


def _diagnostics(rescued: int, lost: int) -> QpAdmRerunIngestionDiagnostics:
    """Return diagnostics for report and CLI edge-path tests."""
    return QpAdmRerunIngestionDiagnostics(
        requested_target_count=2,
        baseline_raw_qpadm_row_count=2,
        rerun_raw_qpadm_row_count=1,
        baseline_parsed_qpadm_estimate_count=1,
        rerun_parsed_qpadm_estimate_count=1,
        baseline_sample_estimate_count=1,
        rerun_sample_estimate_count=1,
        merged_sample_estimate_count=2,
        baseline_target_observation_count=1,
        post_target_observation_count=1 + rescued - lost,
        accepted_target_observation_count=None,
        rescued_target_count=rescued,
        lost_target_count=lost,
        unchanged_retained_target_count=1,
        unchanged_dropped_target_count=0,
        reviewed_rerun_target_count=1,
        rescued_reviewed_rerun_target_count=rescued,
        rescued_target_ids=("rescued-target",) if rescued else (),
        lost_target_ids=("lost-target",) if lost else (),
        post_target_counts_by_region=(("britain", 1),),
    )


def _tiny_aadr_dir(tmp_path: Path) -> Path:
    """Create a tiny two-sample AADR quartet."""
    root = tmp_path / "aadr"
    root.mkdir(exist_ok=True)
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
    (root / "tiny.anno").write_text(
        f"{header}\n" + "\n".join("\t".join(row) for row in rows) + "\n",
        encoding="utf-8",
    )
    (root / "tiny.ind").write_text(
        "I001 M England_BellBeaker\nI002 F Germany_CordedWare\n",
        encoding="utf-8",
    )
    (root / "tiny.snp").write_text("rs1 1 0.0 1 A G\n", encoding="utf-8")
    (root / "tiny.geno").write_text("00\n", encoding="utf-8")
    return root
