"""Tests for unified structural SMC robustness decisions."""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from indoeuropop.orchestration.cli import main
from indoeuropop.orchestration.structural_smc_robustness import (
    _decision_issues,
    load_fit_metric_robustness_summary,
    load_source_model_robustness_summary,
    load_target_fragility_robustness_summary,
    run_structural_smc_robustness_decision,
    structural_smc_robustness_decision_paths_from_dir,
)
from indoeuropop.orchestration.structural_smc_robustness_cli import (
    run_structural_smc_robustness_command,
)
from indoeuropop.orchestration.structural_smc_robustness_models import (
    FitMetricRobustnessSummary,
    SourceModelRobustnessSummary,
    StructuralSMCRobustnessDecision,
    StructuralSMCRobustnessDecisionPaths,
    StructuralSMCRobustnessIssue,
    TargetFragilityRobustnessSummary,
)
from indoeuropop.reporting.structural_smc_robustness import (
    structural_smc_robustness_decision_markdown,
    structural_smc_robustness_decision_row,
    structural_smc_robustness_decision_to_csv,
)


def test_structural_smc_robustness_decision_writes_caveated_report(
    tmp_path: Path,
) -> None:
    """Existing gate artifacts should collapse into one caveated decision."""
    artifacts = _write_artifacts(tmp_path, caveats=True)

    decision = run_structural_smc_robustness_decision(
        candidate_name="central-europe-child-interaction-best",
        target_fragility_decisions_csv=artifacts.fragility,
        fit_metric_summary_csv=artifacts.fit_summary,
        fit_metric_report_md=artifacts.fit_report,
        source_model_summary_csv=artifacts.source_summary,
        source_model_report_md=artifacts.source_report,
        paths=structural_smc_robustness_decision_paths_from_dir(
            tmp_path / "robustness"
        ),
    )

    row = structural_smc_robustness_decision_row(decision)
    assert decision.status == "review_with_caveats"
    assert decision.recommendation == "promote_only_with_documented_caveats"
    assert decision.blocker_count == 0
    assert decision.caution_count == 7
    assert row["excluded_target_count"] == "1"
    assert "review_with_caveats" in decision.paths.summary_csv.read_text(
        encoding="utf-8"
    )
    assert "maximum missing override regions" in decision.paths.report_md.read_text(
        encoding="utf-8"
    )


def test_structural_smc_robustness_decision_can_be_ready(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A clean set of robustness artifacts should be ready to promote."""
    monkeypatch.chdir(tmp_path)
    artifacts = _write_artifacts(tmp_path, caveats=False)

    decision = run_structural_smc_robustness_decision(
        candidate_name="candidate",
        target_fragility_decisions_csv=artifacts.fragility,
        fit_metric_summary_csv=artifacts.fit_summary,
        fit_metric_report_md=artifacts.fit_report,
        source_model_summary_csv=artifacts.source_summary,
        source_model_report_md=artifacts.source_report,
    )
    markdown = structural_smc_robustness_decision_markdown(decision)

    assert decision.status == "ready_to_promote"

    issues = _decision_issues(
        TargetFragilityRobustnessSummary(0, 0),
        FitMetricRobustnessSummary(2, 0, 0, 0),
        SourceModelRobustnessSummary(2, 0, 0, 0, 0, 0),
        max_unstable_holdout_folds=0,
    )
    assert issues[0].message == "no target-fragility decisions found"
    assert decision.recommendation == "promote"
    assert decision.paths.summary_csv.exists()
    assert "No blockers or caveats" in markdown
    assert structural_smc_robustness_decision_to_csv(decision).count("\n") == 2


def test_structural_smc_robustness_blocks_unstable_gates(
    tmp_path: Path,
) -> None:
    """Metric and source-model instability should block candidate promotion."""
    artifacts = _write_artifacts(tmp_path, caveats=False, unstable_folds=1)

    decision = run_structural_smc_robustness_decision(
        candidate_name="candidate",
        target_fragility_decisions_csv=artifacts.fragility,
        fit_metric_summary_csv=artifacts.fit_summary,
        fit_metric_report_md=artifacts.fit_report,
        source_model_summary_csv=artifacts.source_summary,
        source_model_report_md=artifacts.source_report,
        paths=structural_smc_robustness_decision_paths_from_dir(tmp_path / "out"),
    )

    assert decision.status == "blocked"
    assert decision.recommendation == "do_not_promote"
    assert decision.blocker_count == 2


def test_structural_smc_robustness_blocks_reviewed_caveat_dispositions(
    tmp_path: Path,
) -> None:
    """Reviewed blocking caveat dispositions should feed into robustness."""
    artifacts = _write_artifacts(tmp_path, caveats=False)
    drilldown = tmp_path / "drilldown.csv"
    dispositions = tmp_path / "dispositions.csv"
    drilldown.write_text(
        "gate,run_label,caveat_type,fold_name,target_id,requested_group_id\n"
        "fit_metric,rmse,uncertainty_tie,fold-a,target-a,GroupA\n",
        encoding="utf-8",
    )
    dispositions.write_text(
        "gate,run_label,caveat_type,fold_name,target_id,requested_group_id,"
        "disposition,reason,reviewer,decision_date,note\n"
        "fit_metric,rmse,uncertainty_tie,fold-a,target-a,GroupA,"
        "blocks_promotion,source model unresolved,reviewer,2026-06-12,\n",
        encoding="utf-8",
    )

    decision = run_structural_smc_robustness_decision(
        candidate_name="candidate",
        target_fragility_decisions_csv=artifacts.fragility,
        fit_metric_summary_csv=artifacts.fit_summary,
        fit_metric_report_md=artifacts.fit_report,
        source_model_summary_csv=artifacts.source_summary,
        source_model_report_md=artifacts.source_report,
        caveat_drilldown_csv=drilldown,
        caveat_dispositions_csv=dispositions,
        paths=structural_smc_robustness_decision_paths_from_dir(tmp_path / "out"),
    )

    assert decision.status == "blocked"
    assert decision.caveat_dispositions is not None
    assert decision.caveat_dispositions.blocking_count == 1
    assert "reviewed caveats block promotion" in decision.paths.report_md.read_text(
        encoding="utf-8"
    )


def test_structural_smc_robustness_blocks_invalid_caveat_dispositions(
    tmp_path: Path,
) -> None:
    """Structural disposition-file issues should block robustness promotion."""
    artifacts = _write_artifacts(tmp_path, caveats=False)
    drilldown = tmp_path / "drilldown.csv"
    dispositions = tmp_path / "dispositions.csv"
    drilldown.write_text(
        "gate,run_label,caveat_type,fold_name,target_id,requested_group_id\n"
        "fit_metric,rmse,uncertainty_tie,fold-a,target-a,GroupA\n",
        encoding="utf-8",
    )
    dispositions.write_text(
        "gate,run_label,caveat_type,fold_name,target_id,requested_group_id,"
        "disposition,reason,reviewer,decision_date,note\n"
        "fit_metric,other,uncertainty_tie,fold-a,target-a,GroupA,"
        "accepted_caveat,reviewed,reviewer,2026-06-12,\n",
        encoding="utf-8",
    )

    decision = run_structural_smc_robustness_decision(
        candidate_name="candidate",
        target_fragility_decisions_csv=artifacts.fragility,
        fit_metric_summary_csv=artifacts.fit_summary,
        fit_metric_report_md=artifacts.fit_report,
        source_model_summary_csv=artifacts.source_summary,
        source_model_report_md=artifacts.source_report,
        caveat_drilldown_csv=drilldown,
        caveat_dispositions_csv=dispositions,
        paths=structural_smc_robustness_decision_paths_from_dir(tmp_path / "out"),
    )

    assert decision.status == "blocked"
    assert any(
        issue.message == "1 structural disposition-file issues"
        for issue in decision.issues
    )


def test_structural_smc_robustness_cli_writes_outputs(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The top-level CLI should expose the unified robustness gate."""
    artifacts = _write_artifacts(tmp_path, caveats=True)
    output_dir = tmp_path / "cli-robustness"

    exit_code = main(
        [
            "validate-structured-smc-robustness",
            "--robustness-candidate-name",
            "candidate",
            "--robustness-output-dir",
            str(output_dir),
            "--target-fragility-decisions-csv",
            str(artifacts.fragility),
            "--fit-metric-sensitivity-summary-csv",
            str(artifacts.fit_summary),
            "--fit-metric-sensitivity-report-md",
            str(artifacts.fit_report),
            "--source-model-sensitivity-summary-csv",
            str(artifacts.source_summary),
            "--source-model-sensitivity-report-md",
            str(artifacts.source_report),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "structural_smc_robustness_status=review_with_caveats" in captured.out
    assert (output_dir / "structural-smc-robustness-decision.csv").exists()


def test_structural_smc_robustness_cli_prints_disposition_feedback(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The robustness CLI should print disposition feedback when supplied."""
    artifacts = _write_artifacts(tmp_path, caveats=False)
    drilldown = tmp_path / "drilldown.csv"
    dispositions = tmp_path / "dispositions.csv"
    drilldown.write_text(
        "gate,run_label,caveat_type,fold_name,target_id,requested_group_id\n"
        "fit_metric,rmse,uncertainty_tie,fold-a,target-a,GroupA\n",
        encoding="utf-8",
    )
    dispositions.write_text(
        "gate,run_label,caveat_type,fold_name,target_id,requested_group_id,"
        "disposition,reason,reviewer,decision_date,note\n"
        "fit_metric,rmse,uncertainty_tie,fold-a,target-a,GroupA,undecided,,,,\n",
        encoding="utf-8",
    )

    exit_code = main(
        [
            "validate-structured-smc-robustness",
            "--robustness-output-dir",
            str(tmp_path / "out"),
            "--target-fragility-decisions-csv",
            str(artifacts.fragility),
            "--fit-metric-sensitivity-summary-csv",
            str(artifacts.fit_summary),
            "--fit-metric-sensitivity-report-md",
            str(artifacts.fit_report),
            "--source-model-sensitivity-summary-csv",
            str(artifacts.source_summary),
            "--source-model-sensitivity-report-md",
            str(artifacts.source_report),
            "--caveat-drilldown-csv",
            str(drilldown),
            "--caveat-dispositions-csv",
            str(dispositions),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "structural_smc_caveat_disposition_unresolved_count=1" in captured.out


def test_structural_smc_robustness_validates_edge_cases(
    tmp_path: Path,
) -> None:
    """Malformed artifacts and impossible counts should fail clearly."""
    artifacts = _write_artifacts(tmp_path, caveats=False)
    bad_bool = tmp_path / "bad-bool.csv"
    bad_bool.write_text("target_id,excluded\na,maybe\n", encoding="utf-8")
    missing_column = tmp_path / "missing-column.csv"
    missing_column.write_text("target_id\na\n", encoding="utf-8")
    empty_rows = tmp_path / "empty.csv"
    empty_rows.write_text("target_id,excluded\n", encoding="utf-8")
    no_header = tmp_path / "no-header.csv"
    no_header.write_text("", encoding="utf-8")
    missing_summary = tmp_path / "missing-summary.md"
    missing_summary.write_text("- other: 0\n", encoding="utf-8")
    negative_summary = tmp_path / "negative-summary.md"
    negative_summary.write_text("- unstable_holdout_fold_count: -1\n", encoding="utf-8")
    text_summary = tmp_path / "text-summary.md"
    text_summary.write_text("- unstable_holdout_fold_count: many\n", encoding="utf-8")
    negative_fit = tmp_path / "negative-fit.csv"
    negative_fit.write_text(
        "fit_metric,preference_disagreement_count,"
        "uncertainty_tie_target_count\nrmse,-1,0\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="candidate_name"):
        run_structural_smc_robustness_decision(
            candidate_name=" ",
            target_fragility_decisions_csv=artifacts.fragility,
            fit_metric_summary_csv=artifacts.fit_summary,
            fit_metric_report_md=artifacts.fit_report,
            source_model_summary_csv=artifacts.source_summary,
            source_model_report_md=artifacts.source_report,
        )
    with pytest.raises(ValueError, match="max_unstable"):
        run_structural_smc_robustness_decision(
            candidate_name="candidate",
            target_fragility_decisions_csv=artifacts.fragility,
            fit_metric_summary_csv=artifacts.fit_summary,
            fit_metric_report_md=artifacts.fit_report,
            source_model_summary_csv=artifacts.source_summary,
            source_model_report_md=artifacts.source_report,
            max_unstable_holdout_folds=-1,
        )
    with pytest.raises(ValueError, match="caveat_drilldown"):
        run_structural_smc_robustness_decision(
            candidate_name="candidate",
            target_fragility_decisions_csv=artifacts.fragility,
            fit_metric_summary_csv=artifacts.fit_summary,
            fit_metric_report_md=artifacts.fit_report,
            source_model_summary_csv=artifacts.source_summary,
            source_model_report_md=artifacts.source_report,
            caveat_dispositions_csv=artifacts.fragility,
        )
    with pytest.raises(ValueError, match="true or false"):
        load_target_fragility_robustness_summary(bad_bool)
    with pytest.raises(ValueError, match="missing columns"):
        load_target_fragility_robustness_summary(missing_column)
    with pytest.raises(ValueError, match="data row"):
        load_target_fragility_robustness_summary(empty_rows)
    with pytest.raises(ValueError, match="header row"):
        load_target_fragility_robustness_summary(no_header)
    with pytest.raises(ValueError, match="missing summary key"):
        load_fit_metric_robustness_summary(artifacts.fit_summary, missing_summary)
    with pytest.raises(ValueError, match="non-negative"):
        load_fit_metric_robustness_summary(artifacts.fit_summary, negative_summary)
    with pytest.raises(ValueError, match="integer"):
        load_fit_metric_robustness_summary(artifacts.fit_summary, text_summary)
    with pytest.raises(ValueError, match="non-negative"):
        load_fit_metric_robustness_summary(negative_fit, artifacts.fit_report)


def test_structural_smc_robustness_models_validate_counts() -> None:
    """Robustness dataclasses should reject invalid direct construction."""
    paths = StructuralSMCRobustnessDecisionPaths(
        output_dir=Path("out"),
        summary_csv=Path("out/summary.csv"),
        report_md=Path("out/report.md"),
    )
    with pytest.raises(ValueError, match="gate"):
        StructuralSMCRobustnessIssue("", "caution", "message")
    with pytest.raises(ValueError, match="severity"):
        StructuralSMCRobustnessIssue("gate", "bad", "message")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="message"):
        StructuralSMCRobustnessIssue("gate", "caution", "")
    with pytest.raises(ValueError, match="cannot exceed"):
        TargetFragilityRobustnessSummary(1, 2)
    with pytest.raises(ValueError, match="non-negative"):
        FitMetricRobustnessSummary(-1, 0, 0, 0)
    with pytest.raises(ValueError, match="non-negative"):
        SourceModelRobustnessSummary(2, 0, 0, 0, 0, -1)

    decision = StructuralSMCRobustnessDecision(
        candidate_name="candidate",
        target_fragility=TargetFragilityRobustnessSummary(1, 0),
        fit_metric=FitMetricRobustnessSummary(1, 0, 0, 0),
        source_model=SourceModelRobustnessSummary(1, 0, 0, 0, 0, 0),
        issues=(),
        paths=paths,
    )
    assert decision.status == "ready_to_promote"


def test_structural_smc_robustness_single_runs_are_blockers(
    tmp_path: Path,
) -> None:
    """Single metric or source-model artifacts should block robustness promotion."""
    artifacts = _write_artifacts(tmp_path, caveats=False, single_rows=True)

    decision = run_structural_smc_robustness_decision(
        candidate_name="candidate",
        target_fragility_decisions_csv=artifacts.fragility,
        fit_metric_summary_csv=artifacts.fit_summary,
        fit_metric_report_md=artifacts.fit_report,
        source_model_summary_csv=artifacts.source_summary,
        source_model_report_md=artifacts.source_report,
        paths=structural_smc_robustness_decision_paths_from_dir(tmp_path / "out"),
        max_unstable_holdout_folds=1,
    )

    assert decision.status == "blocked"
    assert decision.blocker_count == 2


def test_structural_smc_robustness_cli_handler_ignores_other_commands() -> None:
    """The command handler should ignore commands owned by other modules."""
    parser = argparse.ArgumentParser()
    args = argparse.Namespace(command="demo")

    assert run_structural_smc_robustness_command(args, parser) is None


def test_structural_smc_robustness_cli_requires_inputs(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The CLI should report missing required robustness inputs."""
    with pytest.raises(SystemExit):
        main(["validate-structured-smc-robustness"])

    captured = capsys.readouterr()
    assert "requires --robustness-output-dir" in captured.err


def test_structural_smc_robustness_cli_requires_disposition_drilldown(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The robustness CLI should pair dispositions with a drilldown CSV."""
    artifacts = _write_artifacts(tmp_path, caveats=False)

    with pytest.raises(SystemExit):
        main(
            [
                "validate-structured-smc-robustness",
                "--robustness-output-dir",
                str(tmp_path / "out"),
                "--target-fragility-decisions-csv",
                str(artifacts.fragility),
                "--fit-metric-sensitivity-summary-csv",
                str(artifacts.fit_summary),
                "--fit-metric-sensitivity-report-md",
                str(artifacts.fit_report),
                "--source-model-sensitivity-summary-csv",
                str(artifacts.source_summary),
                "--source-model-sensitivity-report-md",
                str(artifacts.source_report),
                "--caveat-dispositions-csv",
                str(artifacts.fragility),
            ]
        )

    captured = capsys.readouterr()
    assert "requires --caveat-drilldown-csv" in captured.err


def test_source_model_robustness_summary_loader(tmp_path: Path) -> None:
    """The source-model summary loader should expose max diagnostic counts."""
    artifacts = _write_artifacts(tmp_path, caveats=True)

    summary = load_source_model_robustness_summary(
        artifacts.source_summary, artifacts.source_report
    )

    assert summary.source_model_count == 2
    assert summary.max_skipped_fold_count == 2


class _Artifacts:
    """Paths to small gate artifacts used by robustness tests."""

    def __init__(self, root: Path) -> None:
        """Create deterministic artifact paths under a temporary root."""
        self.fragility = root / "target-fragility-decisions.csv"
        self.fit_summary = root / "fit-metric-summary.csv"
        self.fit_report = root / "fit-metric.md"
        self.source_summary = root / "source-model-summary.csv"
        self.source_report = root / "source-model.md"


def _write_artifacts(
    root: Path,
    *,
    caveats: bool,
    unstable_folds: int = 0,
    single_rows: bool = False,
) -> _Artifacts:
    """Write small robustness-gate artifact files."""
    artifacts = _Artifacts(root)
    _write_fragility_csv(artifacts.fragility, caveats)
    _write_fit_summary_csv(artifacts.fit_summary, caveats, single_rows)
    _write_source_summary_csv(artifacts.source_summary, caveats, single_rows)
    summary = f"- unstable_holdout_fold_count: {unstable_folds}\n"
    artifacts.fit_report.write_text(summary, encoding="utf-8")
    artifacts.source_report.write_text(summary, encoding="utf-8")
    return artifacts


def _write_fragility_csv(path: Path, caveats: bool) -> None:
    """Write a tiny target-fragility decisions CSV."""
    excluded = "true" if caveats else "false"
    path.write_text(
        "target_id,excluded\n" f"target-a,{excluded}\n" "target-b,false\n",
        encoding="utf-8",
    )


def _write_fit_summary_csv(path: Path, caveats: bool, single_rows: bool) -> None:
    """Write a tiny fit-metric sensitivity summary CSV."""
    rows = ["rmse,2,2" if caveats else "rmse,0,0"]
    if not single_rows:
        rows.append("chi_square,1,1" if caveats else "chi_square,0,0")
    path.write_text(
        "fit_metric,preference_disagreement_count,"
        "uncertainty_tie_target_count\n" + "\n".join(rows) + "\n",
        encoding="utf-8",
    )


def _write_source_summary_csv(path: Path, caveats: bool, single_rows: bool) -> None:
    """Write a tiny source-model sensitivity summary CSV."""
    rows = ["baseline,5,7,1,2" if caveats else "baseline,0,0,0,0"]
    if not single_rows:
        rows.append("accepted,5,7,1,2" if caveats else "accepted,0,0,0,0")
    path.write_text(
        "source_model,preference_disagreement_count,uncertainty_tie_target_count,"
        "missing_override_region_count,skipped_fold_count\n" + "\n".join(rows) + "\n",
        encoding="utf-8",
    )
