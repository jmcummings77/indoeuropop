"""CLI tests for curation-decision metadata validation."""

from __future__ import annotations

import argparse
import shutil
import tomllib
from pathlib import Path

import pytest
from pytest import CaptureFixture

from indoeuropop.orchestration.cli import main
from indoeuropop.orchestration.curation_decision_cli import (
    run_curation_decision_command,
)


def test_cli_validate_curation_decisions_accepts_checked_in_pair(
    capsys: CaptureFixture[str],
) -> None:
    """The CLI should validate checked-in metadata without generated artifacts."""
    exit_code = main(
        [
            "validate-curation-decisions",
            "--curation-decision-file",
            "curation/aadr-v66-central-europe-child-overrides.toml",
            "--curation-decision-file",
            "curation/aadr-v66-central-europe-child-overrides-interaction-best.toml",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "curation_decision_valid=true" in captured.out
    assert "curation_decision_record_count=2" in captured.out
    assert "curation_decision_issue_count=0" in captured.out
    assert "status=review_candidate" in captured.out


def test_cli_validate_curation_decisions_requires_artifacts_when_requested(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    """Strict mode should reject missing evidence in an isolated project."""
    project_root = Path(__file__).resolve().parents[1]
    curation_paths = (
        Path("curation/aadr-v66-central-europe-child-overrides.toml"),
        Path("curation/aadr-v66-central-europe-child-overrides-interaction-best.toml"),
    )
    args = ["validate-curation-decisions", "--project-root", str(tmp_path)]
    for curation_path in curation_paths:
        source_path = project_root / curation_path
        destination_path = tmp_path / curation_path
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, destination_path)
        with source_path.open("rb") as source_file:
            review = tomllib.load(source_file)["review"]
        decision_path = Path(review["decision_record"])
        (tmp_path / decision_path).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(project_root / decision_path, tmp_path / decision_path)
        args.extend(("--curation-decision-file", str(curation_path)))

    assert main(args) == 0
    assert "curation_decision_valid=true" in capsys.readouterr().out

    assert main([*args, "--require-artifacts"]) == 1
    captured = capsys.readouterr()
    assert "curation_decision_valid=false" in captured.out
    assert "baseline_validation_fit_csv does not exist" in captured.out
    assert "override_validation_fit_csv does not exist" in captured.out
    assert "source_delta_report manifest missing" in captured.out


def test_cli_validate_curation_decisions_reports_invalid_pair(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    """Invalid curation metadata should print issues and return nonzero."""
    bad_path = tmp_path / "bad.toml"
    bad_path.write_text(
        """
        [review]
        status = 1
        decision_record = "docs/missing.md"
        fit_metric = "root_mean_squared_error"
        protected_holdouts = ["britain"]
        priority_holdouts = ["central_europe__example"]
        baseline_validation_fit_csv = "results/baseline.csv"
        override_validation_fit_csv = "results/override.csv"
        acceptance_gate = "indoeuropop review-override-deltas"
        """,
        encoding="utf-8",
    )

    exit_code = main(
        [
            "validate-curation-decisions",
            "--project-root",
            str(tmp_path),
            "--curation-decision-file",
            str(bad_path),
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "curation_decision_valid=false" in captured.out
    assert "status=invalid" in captured.out
    assert "curation_decision_issue=" in captured.out


def test_cli_validate_curation_decisions_requires_files(
    capsys: CaptureFixture[str],
) -> None:
    """The CLI should reject missing curation-decision file arguments."""
    with pytest.raises(SystemExit, match="2"):
        main(["validate-curation-decisions"])
    captured = capsys.readouterr()

    assert "requires --curation-decision-file" in captured.err


def test_curation_decision_handler_ignores_unrelated_commands() -> None:
    """The delegated handler should return None for unrelated commands."""
    args = argparse.Namespace(command="demo")
    parser = argparse.ArgumentParser()

    assert run_curation_decision_command(args, parser) is None
