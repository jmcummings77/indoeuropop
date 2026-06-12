"""Tests for structural SMC caveat drilldown reports."""

from __future__ import annotations

from pathlib import Path

import pytest

from indoeuropop.orchestration.cli import main
from indoeuropop.orchestration.structural_smc_caveat_drilldown import (
    run_structural_smc_caveat_drilldown,
    structural_smc_caveat_drilldown_paths_from_dir,
)
from indoeuropop.orchestration.structural_smc_caveat_drilldown_models import (
    StructuralSMCCaveatDrilldownPaths,
    StructuralSMCCaveatDrilldownReport,
    StructuralSMCCaveatDrilldownRow,
)
from indoeuropop.reporting.structural_smc_caveat_drilldown import (
    structural_smc_caveat_drilldown_markdown,
    structural_smc_caveat_drilldown_rows,
    structural_smc_caveat_drilldown_to_csv,
)


def test_structural_smc_caveat_drilldown_writes_actionable_rows(
    tmp_path: Path,
) -> None:
    """Gate artifacts should join to fold-level and target-level caveats."""
    artifacts = _write_artifacts(tmp_path, caveats=True)

    report = run_structural_smc_caveat_drilldown(
        target_fragility_decisions_csv=artifacts.fragility,
        fit_metric_summary_csv=artifacts.fit_summary,
        source_model_summary_csv=artifacts.source_summary,
        paths=structural_smc_caveat_drilldown_paths_from_dir(tmp_path / "out"),
    )
    rows = structural_smc_caveat_drilldown_rows(report)
    markdown = report.paths.report_md.read_text(encoding="utf-8")

    assert report.row_count == 15
    assert report.count_by_type("excluded_target") == 1
    assert report.count_by_type("preference_disagreement") == 4
    assert report.count_by_type("uncertainty_tie") == 8
    assert report.count_by_type("missing_override_regions") == 1
    assert report.count_by_type("skipped_folds") == 1
    assert rows[0]["target_id"] == "target-a"
    assert "preference_disagreement_count: 4" in markdown
    assert "structural-smc-caveat-drilldown.csv" in str(report.paths.detail_csv)


def test_structural_smc_caveat_drilldown_can_be_empty(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A clean artifact set should produce an empty review queue."""
    monkeypatch.chdir(tmp_path)
    artifacts = _write_artifacts(tmp_path, caveats=False)

    report = run_structural_smc_caveat_drilldown(
        target_fragility_decisions_csv=artifacts.fragility,
        fit_metric_summary_csv=artifacts.fit_summary,
        source_model_summary_csv=artifacts.source_summary,
    )
    markdown = structural_smc_caveat_drilldown_markdown(report)

    assert report.row_count == 0
    assert report.caveat_types == ()
    assert "No caveats were detected" in markdown
    assert structural_smc_caveat_drilldown_to_csv(report).count("\n") == 1


def test_structural_smc_caveat_drilldown_cli_writes_outputs(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The top-level CLI should expose the caveat drilldown report."""
    artifacts = _write_artifacts(tmp_path, caveats=True)
    output_dir = tmp_path / "cli-out"

    exit_code = main(
        [
            "summarize-structural-smc-caveats",
            "--robustness-drilldown-output-dir",
            str(output_dir),
            "--target-fragility-decisions-csv",
            str(artifacts.fragility),
            "--fit-metric-sensitivity-summary-csv",
            str(artifacts.fit_summary),
            "--source-model-sensitivity-summary-csv",
            str(artifacts.source_summary),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "structural_smc_caveat_drilldown_row_count=15" in captured.out
    assert (output_dir / "structural-smc-caveat-drilldown.md").exists()


def test_structural_smc_caveat_drilldown_validates_artifacts(
    tmp_path: Path,
) -> None:
    """Malformed artifact files should fail before writing misleading reports."""
    artifacts = _write_artifacts(tmp_path, caveats=False)
    missing_column = tmp_path / "missing.csv"
    missing_column.write_text("target_id,excluded\na,true\n", encoding="utf-8")
    empty_rows = tmp_path / "empty.csv"
    empty_rows.write_text("target_id,requested_group_id,excluded,reasons\n")
    no_header = tmp_path / "no-header.csv"
    no_header.write_text("", encoding="utf-8")
    bad_bool = tmp_path / "bad-bool.csv"
    bad_bool.write_text(
        "target_id,requested_group_id,excluded,reasons\na,A,maybe,bad\n",
        encoding="utf-8",
    )
    bad_source_text = tmp_path / "bad-source-text.csv"
    _write_source_summary_csv(
        bad_source_text,
        artifacts.source_validation,
        artifacts.source_uncertainty,
        caveats=True,
        missing_count="many",
    )
    bad_source_negative = tmp_path / "bad-source-negative.csv"
    _write_source_summary_csv(
        bad_source_negative,
        artifacts.source_validation,
        artifacts.source_uncertainty,
        caveats=True,
        skipped_count="-1",
    )

    with pytest.raises(ValueError, match="missing columns"):
        run_structural_smc_caveat_drilldown(
            target_fragility_decisions_csv=missing_column,
            fit_metric_summary_csv=artifacts.fit_summary,
            source_model_summary_csv=artifacts.source_summary,
        )
    with pytest.raises(ValueError, match="data row"):
        run_structural_smc_caveat_drilldown(
            target_fragility_decisions_csv=empty_rows,
            fit_metric_summary_csv=artifacts.fit_summary,
            source_model_summary_csv=artifacts.source_summary,
        )
    with pytest.raises(ValueError, match="header row"):
        run_structural_smc_caveat_drilldown(
            target_fragility_decisions_csv=no_header,
            fit_metric_summary_csv=artifacts.fit_summary,
            source_model_summary_csv=artifacts.source_summary,
        )
    with pytest.raises(ValueError, match="true or false"):
        run_structural_smc_caveat_drilldown(
            target_fragility_decisions_csv=bad_bool,
            fit_metric_summary_csv=artifacts.fit_summary,
            source_model_summary_csv=artifacts.source_summary,
        )
    with pytest.raises(ValueError, match="integer"):
        run_structural_smc_caveat_drilldown(
            target_fragility_decisions_csv=artifacts.fragility,
            fit_metric_summary_csv=artifacts.fit_summary,
            source_model_summary_csv=bad_source_text,
        )
    with pytest.raises(ValueError, match="non-negative"):
        run_structural_smc_caveat_drilldown(
            target_fragility_decisions_csv=artifacts.fragility,
            fit_metric_summary_csv=artifacts.fit_summary,
            source_model_summary_csv=bad_source_negative,
        )


def test_structural_smc_caveat_drilldown_models_validate_required_fields() -> None:
    """Directly constructed drilldown rows should require review labels."""
    paths = StructuralSMCCaveatDrilldownPaths(
        output_dir=Path("out"),
        detail_csv=Path("out/detail.csv"),
        report_md=Path("out/report.md"),
    )
    with pytest.raises(ValueError, match="gate"):
        StructuralSMCCaveatDrilldownRow("", "run", "type", next_action="act")
    with pytest.raises(ValueError, match="run_label"):
        StructuralSMCCaveatDrilldownRow("gate", "", "type", next_action="act")
    with pytest.raises(ValueError, match="caveat_type"):
        StructuralSMCCaveatDrilldownRow("gate", "run", "", next_action="act")
    with pytest.raises(ValueError, match="next_action"):
        StructuralSMCCaveatDrilldownRow("gate", "run", "type", next_action="")

    report = StructuralSMCCaveatDrilldownReport(rows=(), paths=paths)
    assert report.row_count == 0
    assert report.count_by_type("missing") == 0


def test_structural_smc_caveat_drilldown_cli_requires_inputs(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The CLI should reject missing caveat-drilldown inputs."""
    with pytest.raises(SystemExit):
        main(["summarize-structural-smc-caveats"])

    captured = capsys.readouterr()
    assert "requires --robustness-drilldown-output-dir" in captured.err


class _Artifacts:
    """Paths to synthetic drilldown input artifacts."""

    def __init__(self, root: Path) -> None:
        """Create deterministic artifact paths under a temporary root."""
        self.fragility = root / "target-fragility.csv"
        self.fit_summary = root / "fit-summary.csv"
        self.fit_validation = root / "fit-validation.csv"
        self.fit_uncertainty = root / "fit-uncertainty.csv"
        self.source_summary = root / "source-summary.csv"
        self.source_validation = root / "source-validation.csv"
        self.source_uncertainty = root / "source-uncertainty.csv"


def _write_artifacts(root: Path, *, caveats: bool) -> _Artifacts:
    """Write synthetic drilldown input artifacts."""
    artifacts = _Artifacts(root)
    _write_fragility_csv(artifacts.fragility, caveats)
    _write_validation_csv(artifacts.fit_validation, caveats)
    _write_uncertainty_csv(artifacts.fit_uncertainty, caveats)
    _write_validation_csv(artifacts.source_validation, caveats)
    _write_uncertainty_csv(artifacts.source_uncertainty, caveats)
    _write_fit_summary_csv(
        artifacts.fit_summary,
        artifacts.fit_validation,
        artifacts.fit_uncertainty,
    )
    _write_source_summary_csv(
        artifacts.source_summary,
        artifacts.source_validation,
        artifacts.source_uncertainty,
        caveats=caveats,
    )
    return artifacts


def _write_fragility_csv(path: Path, caveats: bool) -> None:
    """Write a small target-fragility decisions CSV."""
    path.write_text(
        "target_id,requested_group_id,excluded,reasons\n"
        f"target-a,GroupA,{str(caveats).lower()},sample_flag:high_se\n"
        "target-b,GroupB,false,\n",
        encoding="utf-8",
    )


def _write_fit_summary_csv(
    path: Path,
    validation_csv: Path,
    uncertainty_csv: Path,
) -> None:
    """Write a two-run fit-metric sensitivity summary CSV."""
    path.write_text(
        "fit_metric,validation_summary_csv,uncertainty_csv\n"
        f"rmse,{validation_csv},{uncertainty_csv}\n"
        f"chi_square,{validation_csv},{uncertainty_csv}\n",
        encoding="utf-8",
    )


def _write_source_summary_csv(
    path: Path,
    validation_csv: Path,
    uncertainty_csv: Path,
    *,
    caveats: bool,
    missing_count: str | None = None,
    skipped_count: str | None = None,
) -> None:
    """Write a two-run source-model sensitivity summary CSV."""
    missing = missing_count if missing_count is not None else ("1" if caveats else "0")
    skipped = skipped_count if skipped_count is not None else ("2" if caveats else "0")
    path.write_text(
        "source_model,validation_summary_csv,uncertainty_csv,"
        "missing_override_region_count,skipped_fold_count\n"
        f"baseline,{validation_csv},{uncertainty_csv},{missing},{skipped}\n"
        f"accepted,{validation_csv},{uncertainty_csv},0,0\n",
        encoding="utf-8",
    )


def _write_validation_csv(path: Path, caveats: bool) -> None:
    """Write a small validation summary CSV."""
    disagreement = str(caveats).lower()
    path.write_text(
        "fold_name,calibration_preferred_candidate,holdout_preferred_candidate,"
        "preference_disagreement,holdout_child_minus_structured_pulse_rmse_delta\n"
        f"fold-a,child_override,structured_pulse,{disagreement},0.25\n"
        "fold-b,child_override,child_override,false,-0.50\n",
        encoding="utf-8",
    )


def _write_uncertainty_csv(path: Path, caveats: bool) -> None:
    """Write a small uncertainty review CSV."""
    tie = "uncertainty_tie" if caveats else "child_override"
    path.write_text(
        "fold_name,target_id,requested_group_id,raw_residual_preferred_candidate,"
        "uncertainty_weighted_preferred_candidate,"
        "child_minus_structured_pulse_chi_square_delta\n"
        f"fold-a,target-a,GroupA,structured_pulse,{tie},0.10\n"
        f"fold-b,target-b,GroupB,child_override,{tie},-0.20\n",
        encoding="utf-8",
    )
