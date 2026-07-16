"""Tests for checksummed structural SMC robustness evidence packages."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from indoeuropop.data.structural_smc_caveat_dispositions import (
    StructuralSMCCaveatDispositionDataset,
    StructuralSMCCaveatDispositionRecord,
    StructuralSMCCaveatDispositionValidationReport,
    load_structural_smc_caveat_dispositions,
)
from indoeuropop.orchestration.cli import main
from indoeuropop.orchestration.structural_smc_robustness_evidence import (
    StructuralSMCRobustnessEvidencePaths,
    structural_smc_robustness_evidence_manifest,
    write_structural_smc_robustness_evidence_manifest,
)
from indoeuropop.orchestration.structural_smc_robustness_models import (
    FitMetricRobustnessSummary,
    SourceModelRobustnessSummary,
    StructuralSMCRobustnessDecision,
    StructuralSMCRobustnessDecisionPaths,
    StructuralSMCRobustnessIssue,
    TargetFragilityRobustnessSummary,
)


def test_robustness_evidence_manifest_checksums_complete_review(
    tmp_path: Path,
) -> None:
    """A complete review should produce stable checksum-bearing artifacts."""
    paths = _write_evidence_paths(tmp_path)
    decision = _decision(tmp_path, _validation_report("accepted_caveat"))
    output_path = tmp_path / "evidence-manifest.json"

    written_path = write_structural_smc_robustness_evidence_manifest(
        decision,
        paths,
        output_path,
        command="test-command",
    )
    payload = json.loads(written_path.read_text(encoding="utf-8"))

    assert written_path == output_path
    assert payload["name"] == "structural-smc-robustness-evidence"
    assert payload["metadata"]["command"] == "test-command"
    assert payload["metadata"]["status"] == "review_with_caveats"
    assert payload["metadata"]["reviewed_disposition_count"] == "1"
    assert len(payload["artifacts"]) == 14
    assert all(artifact["checksum_sha256"] for artifact in payload["artifacts"])


@pytest.mark.parametrize(
    ("review_state", "message"),
    (
        ("missing", "requires caveat dispositions"),
        ("invalid", "requires valid"),
        ("undecided", "requires fully reviewed"),
    ),
)
def test_robustness_evidence_manifest_rejects_incomplete_review(
    tmp_path: Path,
    review_state: str,
    message: str,
) -> None:
    """Evidence freezing should fail when human disposition review is incomplete."""
    report = _incomplete_validation_report(review_state)
    decision = _decision(tmp_path, report)

    with pytest.raises(ValueError, match=message):
        structural_smc_robustness_evidence_manifest(
            decision,
            _write_evidence_paths(tmp_path),
        )


def test_robustness_cli_writes_complete_evidence_package(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The CLI should rebuild reports and freeze their checksummed manifest."""
    inputs = _write_cli_inputs(tmp_path)
    output_dir = tmp_path / "robustness"
    disposition_report = tmp_path / "dispositions.md"
    manifest_path = tmp_path / "manifest.json"

    exit_code = main(
        [
            *_robustness_cli_args(inputs, output_dir),
            "--caveat-disposition-report-md",
            str(disposition_report),
            "--manifest-json",
            str(manifest_path),
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert disposition_report.exists()
    assert payload["metadata"]["unresolved_disposition_count"] == "0"
    assert "structural_smc_robustness_evidence_manifest=" in captured.out


def test_robustness_cli_requires_complete_manifest_inputs(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Requesting a manifest should reject a partial evidence surface."""
    inputs = _write_cli_inputs(tmp_path)

    with pytest.raises(SystemExit):
        main(
            [
                *_robustness_cli_args(inputs, tmp_path / "out", include_evidence=False),
                "--manifest-json",
                str(tmp_path / "manifest.json"),
            ]
        )

    captured = capsys.readouterr()
    assert "--manifest-json requires --child-region-overrides" in captured.err


def test_tracked_structural_smc_dispositions_are_complete() -> None:
    """The repository's promoted review table should remain fully resolved."""
    project_root = Path(__file__).parents[1]
    dataset = load_structural_smc_caveat_dispositions(
        project_root / "curation/aadr-v66-structural-smc-caveat-dispositions.csv"
    )

    assert len(dataset.records) == 42
    assert dataset.reviewed_count == 42
    assert dataset.blocking_count == 0
    assert (
        sum(record.disposition == "accepted_caveat" for record in dataset.records) == 38
    )
    assert (
        sum(record.disposition == "not_applicable" for record in dataset.records) == 4
    )


def _validation_report(
    disposition: str,
    *,
    issues: tuple[str, ...] = (),
) -> StructuralSMCCaveatDispositionValidationReport:
    """Return a one-row caveat validation report for evidence tests."""
    record = StructuralSMCCaveatDispositionRecord(
        gate="fit_metric",
        run_label="rmse",
        caveat_type="uncertainty_tie",
        fold_name="fold-a",
        target_id="target-a",
        requested_group_id="GroupA",
        disposition=disposition,  # type: ignore[arg-type]
        reason="reviewed" if disposition != "undecided" else "",
    )
    dataset = StructuralSMCCaveatDispositionDataset.from_rows((record,))
    return StructuralSMCCaveatDispositionValidationReport(
        drilldown_caveat_count=1,
        dispositions=dataset,
        issues=issues,
    )


def _incomplete_validation_report(
    review_state: str,
) -> StructuralSMCCaveatDispositionValidationReport | None:
    """Return the incomplete review variant selected by a test parameter."""
    if review_state == "missing":
        return None
    if review_state == "invalid":
        return _validation_report("accepted_caveat", issues=("bad key",))
    return _validation_report("undecided")


def _decision(
    root: Path,
    report: StructuralSMCCaveatDispositionValidationReport | None,
) -> StructuralSMCRobustnessDecision:
    """Return a compact robustness decision with optional caveat review."""
    output_dir = root / "decision"
    output_dir.mkdir(exist_ok=True)
    summary_csv = _write(output_dir / "summary.csv", "status\nreview_with_caveats\n")
    report_md = _write(output_dir / "report.md", "# Review with caveats\n")
    return StructuralSMCRobustnessDecision(
        candidate_name="candidate",
        target_fragility=TargetFragilityRobustnessSummary(1, 1),
        fit_metric=FitMetricRobustnessSummary(2, 0, 1, 1),
        source_model=SourceModelRobustnessSummary(2, 0, 1, 1, 0, 0),
        issues=(
            StructuralSMCRobustnessIssue(
                "target_fragility",
                "caution",
                "1 audited target excluded",
            ),
        ),
        paths=StructuralSMCRobustnessDecisionPaths(
            output_dir=output_dir,
            summary_csv=summary_csv,
            report_md=report_md,
        ),
        caveat_dispositions=report,
    )


def _write_evidence_paths(root: Path) -> StructuralSMCRobustnessEvidencePaths:
    """Write and return all files in a compact evidence package."""
    names = (
        "candidate.toml",
        "decision.md",
        "fragility.csv",
        "fragility.md",
        "fit.csv",
        "fit.md",
        "source.csv",
        "source.md",
        "drilldown.csv",
        "drilldown.md",
        "dispositions.csv",
        "dispositions.md",
        "robustness.csv",
        "robustness.md",
    )
    files = tuple(_write(root / name, f"evidence for {name}\n") for name in names)
    return StructuralSMCRobustnessEvidencePaths(*files)


def _write_cli_inputs(root: Path) -> dict[str, Path]:
    """Write the minimal valid gate surface used by the robustness CLI."""
    inputs = {
        "candidate": _write(root / "candidate.toml", "[review]\nstatus='candidate'\n"),
        "decision": _write(root / "decision.md", "# Decision\n"),
        "fragility": _write(root / "fragility.csv", "target_id,excluded\na,false\n"),
        "fragility_report": _write(root / "fragility.md", "# Fragility\n"),
        "fit_summary": _write(
            root / "fit.csv",
            "fit_metric,preference_disagreement_count,uncertainty_tie_target_count\n"
            "rmse,0,0\nchi_square,0,0\n",
        ),
        "fit_report": _write(root / "fit.md", "- unstable_holdout_fold_count: 0\n"),
        "source_summary": _write(
            root / "source.csv",
            "source_model,preference_disagreement_count,uncertainty_tie_target_count,"
            "missing_override_region_count,skipped_fold_count\n"
            "baseline,0,0,0,0\naccepted,0,0,0,0\n",
        ),
        "source_report": _write(
            root / "source.md", "- unstable_holdout_fold_count: 0\n"
        ),
        "drilldown": _write(
            root / "drilldown.csv",
            "gate,run_label,caveat_type,fold_name,target_id,requested_group_id\n"
            "fit_metric,rmse,uncertainty_tie,fold-a,target-a,GroupA\n",
        ),
        "drilldown_report": _write(root / "drilldown.md", "# Drilldown\n"),
        "dispositions": _write(
            root / "dispositions.csv",
            "gate,run_label,caveat_type,fold_name,target_id,requested_group_id,"
            "disposition,reason,reviewer,decision_date,note\n"
            "fit_metric,rmse,uncertainty_tie,fold-a,target-a,GroupA,"
            "accepted_caveat,reviewed,reviewer,2026-07-15,\n",
        ),
    }
    return inputs


def _robustness_cli_args(
    inputs: dict[str, Path],
    output_dir: Path,
    *,
    include_evidence: bool = True,
) -> list[str]:
    """Return common robustness CLI arguments for evidence tests."""
    arguments = [
        "validate-structured-smc-robustness",
        "--robustness-output-dir",
        str(output_dir),
        "--target-fragility-decisions-csv",
        str(inputs["fragility"]),
        "--fit-metric-sensitivity-summary-csv",
        str(inputs["fit_summary"]),
        "--fit-metric-sensitivity-report-md",
        str(inputs["fit_report"]),
        "--source-model-sensitivity-summary-csv",
        str(inputs["source_summary"]),
        "--source-model-sensitivity-report-md",
        str(inputs["source_report"]),
    ]
    if not include_evidence:
        return arguments
    return [
        *arguments,
        "--child-region-overrides",
        str(inputs["candidate"]),
        "--robustness-decision-record-md",
        str(inputs["decision"]),
        "--target-fragility-report-md",
        str(inputs["fragility_report"]),
        "--caveat-drilldown-csv",
        str(inputs["drilldown"]),
        "--caveat-drilldown-report-md",
        str(inputs["drilldown_report"]),
        "--caveat-dispositions-csv",
        str(inputs["dispositions"]),
    ]


def _write(path: Path, text: str) -> Path:
    """Write one UTF-8 test artifact and return its path."""
    path.write_text(text, encoding="utf-8")
    return path
