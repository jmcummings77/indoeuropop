"""Tests for the one-command real-pipeline refresh workflow."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pytest import CaptureFixture

from indoeuropop.data.data_sources import sha256_file
from indoeuropop.orchestration.cli import main
from indoeuropop.orchestration.real_pipeline_refresh import (
    DEFAULT_FOCUS_OBSERVATION_INDEX,
    run_real_pipeline_refresh_workflow,
)
from indoeuropop.orchestration.real_pipeline_refresh_cli import (
    _child_candidate_name,
    _fit_metric,
    _focus_observation_index,
    run_real_pipeline_refresh_command,
)


def test_real_pipeline_refresh_workflow_runs_default_sequence(tmp_path: Path) -> None:
    """The refresh workflow should structure targets, compare, and check readiness."""
    _write_default_refresh_tree(tmp_path)

    result = run_real_pipeline_refresh_workflow(
        project_root=tmp_path,
        focus_observation_index=0,
    )

    assert result.ready
    assert len(result.target_structure.targets.observations) == 2
    assert len(result.target_structure.mappings) == 1
    assert result.head_to_head.structured_pulse_region_count == 1
    assert result.head_to_head.baseline.inference.accepted_count == 6
    assert result.readiness_report_md_path == Path(
        "results/qpadm-rerun/real-pipeline-readiness.md"
    )
    assert (
        tmp_path / "results/qpadm-rerun/central-europe-structured-targets.csv"
    ).exists()
    assert (
        tmp_path / "results/qpadm-rerun/"
        "central-europe-structured-pulse-vs-child-head-to-head.md"
    ).exists()
    assert "Status: ready" in (
        tmp_path / "results/qpadm-rerun/real-pipeline-readiness.md"
    ).read_text(encoding="utf-8")


def test_cli_refresh_real_pipeline_runs_default_sequence(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    """The refresh CLI should run the standard real-pipeline sequence."""
    _write_default_refresh_tree(tmp_path)

    exit_code = main(
        [
            "refresh-real-pipeline",
            "--project-root",
            str(tmp_path),
            "--focus-observation-index",
            "0",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "real_pipeline_refresh=true" in captured.out
    assert "accepted_target_count=2" in captured.out
    assert "structured_region_count=1" in captured.out
    assert "child_minus_structured_pulse_rmse_delta=" in captured.out
    assert "pipeline_ready=true" in captured.out
    assert "readiness_issue_count=0" in captured.out


def test_real_pipeline_refresh_handler_ignores_unrelated_commands() -> None:
    """The delegated refresh handler should ignore unrelated commands."""
    args = argparse.Namespace(command="demo")
    parser = argparse.ArgumentParser()

    assert run_real_pipeline_refresh_command(args, parser) is None


def test_real_pipeline_refresh_cli_helper_defaults_and_overrides() -> None:
    """Refresh CLI helpers should preserve overrides and fill refresh defaults."""
    assert (
        _child_candidate_name(
            argparse.Namespace(child_region_candidate_name="custom-child")
        )
        == "custom-child"
    )
    assert (
        _fit_metric(
            argparse.Namespace(
                fit_metric="root_mean_squared_error",
                refresh_fit_metric="mean_absolute_error",
            )
        )
        == "root_mean_squared_error"
    )
    assert (
        _focus_observation_index(argparse.Namespace(focus_observation_index=None))
        == DEFAULT_FOCUS_OBSERVATION_INDEX
    )


def _write_default_refresh_tree(root: Path) -> None:
    """Write a tiny project tree using the standard refresh paths."""
    _write_source_catalog(root)
    _write_base_config(root)
    _write_accepted_targets(root)
    _write_standard_readiness_artifacts(root)
    _write_curation_pair(root)


def _write_source_catalog(root: Path) -> None:
    """Write one local source-data record and backing file."""
    _write_text(root / "data/tiny.anno", "sample\n")
    _write_text(
        root / "curation/local-aadr-v66-data-sources.toml",
        """
        [[data_sources]]
        dataset_id = "tiny-aadr"
        kind = "aadr"
        status = "local"
        citation_key = "tiny"
        citation = "Tiny local source."
        uri = "data/tiny.anno"
        download_filename = "tiny.anno"
        """,
    )


def _write_base_config(root: Path) -> None:
    """Write a small loadable default sweep config."""
    _write_text(
        root / "curation/aadr-v66-western-europe-comparison.toml",
        """
        [simulation]
        start_bce = 3100
        end_bce = 2900
        step_years = 50

        [parameters]
        migration_rate = 0.0

        [counts.central_europe]
        local = 1000
        steppe = 5

        [counts.britain]
        local = 900
        steppe = 10

        [sweep]
        sample_count = 6
        seed = 41
        source = "steppe"

        [[parameter_ranges]]
        name = "migration_rate"
        low = 0.0
        high = 0.001
        """,
    )


def _write_accepted_targets(root: Path) -> None:
    """Write a tiny accepted-target CSV at the standard path."""
    _write_text(
        root / "results/qpadm-rerun/accepted-target-observations.csv",
        "\n".join(
            (
                "status,region,source,time_bce,mean,uncertainty,citation_key,"
                "citation,note",
                "synthetic,central_europe,steppe,2950,0.2,0.1,synthetic,"
                "Synthetic target,requested_group_id=Germany_A",
                "synthetic,britain,steppe,2950,0.05,0.1,synthetic,"
                "Synthetic target,requested_group_id=Britain_A",
            )
        )
        + "\n",
    )


def _write_standard_readiness_artifacts(root: Path) -> None:
    """Write non-refreshed readiness artifacts required by the default gate."""
    _write_json(
        root / "results/real-aadr-comparison/aadr-target-diagnostics.json",
        {
            "selected_sample_count": 4,
            "retained_target_count": 1,
            "target_observation_count": 1,
            "decision_deferred_target_count": 0,
        },
    )
    _write_json(
        root / "results/qpadm-rerun/qpadm-rerun-diagnostics.json",
        {
            "baseline_target_observation_count": 1,
            "post_target_observation_count": 2,
            "accepted_target_observation_count": 2,
            "rescued_target_count": 1,
        },
    )
    _write_text(
        root / "results/real-aadr-comparison/aadr-target-observations.csv",
        _target_csv(("britain",)),
    )
    _write_json(
        root / "results/real-aadr-comparison/target-comparison-manifest.json",
        {},
    )
    _write_text(
        root / "results/qpadm-rerun/accepted-validation-fit.csv",
        "holdout_field,holdout_value,rank\nregion,britain,1\n",
    )
    _write_json(root / "results/qpadm-rerun/accepted-validation-manifest.json", {})
    _write_text(
        root / "results/qpadm-rerun/central-europe-curated-validation-fit.csv",
        "holdout_field,holdout_value,rank\nregion,britain,1\n",
    )
    _write_text(
        root / "results/qpadm-rerun/central-europe-interaction-best-validation-fit.csv",
        "holdout_field,holdout_value,rank\nregion,britain,1\n",
    )
    _write_text(
        root
        / "results/qpadm-rerun/central-europe-curated-vs-interaction-best-delta.csv",
        (
            "validation_delta,priority,protected,protected_degraded\n"
            "0.0,false,true,false\n"
            "-0.05,true,false,false\n"
        ),
    )
    _write_text(
        root
        / "results/qpadm-rerun/central-europe-curated-vs-interaction-best-delta.md",
        "# Delta\n",
    )
    _write_delta_manifest(root)
    _write_text(root / "docs/central-europe-override-decision.md", "# Decision\n")


def _write_curation_pair(root: Path) -> None:
    """Write default active and superseded curation files."""
    common = """
    decision_record = "docs/central-europe-override-decision.md"
    fit_metric = "root_mean_squared_error"
    protected_holdouts = ["britain"]
    priority_holdouts = ["central_europe__germany_a"]
    baseline_validation_fit_csv = \
"results/qpadm-rerun/central-europe-curated-validation-fit.csv"
    override_validation_fit_csv = \
"results/qpadm-rerun/central-europe-interaction-best-validation-fit.csv"
    acceptance_gate = "indoeuropop review-override-deltas"
    """
    _write_text(
        root / "curation/aadr-v66-central-europe-child-overrides.toml",
        f"""
        [review]
        status = "superseded_review_candidate"
        superseded_by = \
"curation/aadr-v66-central-europe-child-overrides-interaction-best.toml"
        {common}
        """,
    )
    _write_text(
        root / "curation/aadr-v66-central-europe-child-overrides-interaction-best.toml",
        f"""
        [review]
        status = "review_candidate"
        supersedes = "curation/aadr-v66-central-europe-child-overrides.toml"
        source_delta_report = \
"results/qpadm-rerun/central-europe-curated-vs-interaction-best-delta.md"
        same_baseline_head_to_head_report = \
"results/qpadm-rerun/central-europe-structured-pulse-vs-child-head-to-head.md"
        {common}

        [counts.central_europe__germany_a]
        local = 760
        steppe = 38

        [[migration_pulses]]
        region = "central_europe__germany_a"
        start_bce = 3050
        end_bce = 2925
        annual_rate = 0.0002
        """,
    )


def _write_delta_manifest(root: Path) -> None:
    """Write a source delta manifest matching its validation CSV files."""
    baseline = root / "results/qpadm-rerun/central-europe-curated-validation-fit.csv"
    override = (
        root / "results/qpadm-rerun/central-europe-interaction-best-validation-fit.csv"
    )
    _write_json(
        root / "results/qpadm-rerun/"
        "central-europe-curated-vs-interaction-best-delta-manifest.json",
        {
            "artifacts": [
                _artifact("baseline_validation_fit_csv", baseline, root),
                _artifact("override_validation_fit_csv", override, root),
            ]
        },
    )


def _target_csv(regions: tuple[str, ...]) -> str:
    """Return a target-observation CSV for readiness row-count checks."""
    rows = ["status,region,source,time_bce,mean,uncertainty,citation_key,citation,note"]
    rows.extend(
        f"synthetic,{region},steppe,2950,0.05,0.1,synthetic,citation,note"
        for region in regions
    )
    return "\n".join(rows) + "\n"


def _artifact(name: str, path: Path, root: Path) -> dict[str, str]:
    """Return a minimal experiment-manifest artifact entry."""
    return {
        "name": name,
        "path": path.relative_to(root).as_posix(),
        "checksum_sha256": sha256_file(path),
    }


def _write_json(path: Path, payload: object) -> None:
    """Write JSON to a fixture path."""
    _write_text(path, json.dumps(payload))


def _write_text(path: Path, text: str) -> None:
    """Write fixture text, creating parent directories first."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
