"""Tests for reusable simulation workflow helpers."""

import json
from pathlib import Path
from typing import cast

import pytest

from indoeuropop.config import default_config
from indoeuropop.experiments import ExperimentArtifact
from indoeuropop.targets import TargetDataset, TargetObservation
from indoeuropop.workflows import (
    SIMULATOR_KINDS,
    SimulationOutputPaths,
    SimulationRun,
    SimulatorKind,
    run_configured_simulation,
    simulation_experiment_manifest,
    simulation_provenance_records,
    write_simulation_outputs,
)


def _target_dataset() -> TargetDataset:
    """Return one synthetic target dataset for workflow tests."""
    return TargetDataset.from_rows(
        [
            TargetObservation(
                status="synthetic",
                region="britain",
                source="steppe",
                time_bce=2750,
                mean=0.1,
                uncertainty=0.05,
                citation_key="synthetic",
                citation="Synthetic test target",
            )
        ]
    )


def test_run_configured_simulation_runs_deterministic_default() -> None:
    """Configured deterministic runs should expose stable run metadata."""
    run = run_configured_simulation(default_config())

    assert "deterministic" in SIMULATOR_KINDS
    assert run.simulator == "deterministic"
    assert run.seed is None
    assert run.final_ancestry("steppe", "britain") > 0.0
    assert run.fingerprint().kind == "simulation_result"


def test_run_configured_simulation_runs_seeded_tau_leap() -> None:
    """Configured tau-leap runs should preserve their stochastic seed."""
    first = run_configured_simulation(
        default_config(),
        simulator="tau_leap",
        seed=13,
    )
    second = run_configured_simulation(
        default_config(),
        simulator="tau_leap",
        seed=13,
    )

    assert first.simulator == "tau_leap"
    assert first.seed == 13
    assert first.fingerprint().digest_sha256 == second.fingerprint().digest_sha256


@pytest.mark.parametrize(
    "simulator,seed,match",
    [
        ("deterministic", 7, "deterministic"),
        ("tau_leap", None, "tau_leap"),
    ],
)
def test_simulation_run_rejects_invalid_seed_metadata(
    simulator: SimulatorKind,
    seed: int | None,
    match: str,
) -> None:
    """Run metadata should not imply stochastic information that is absent."""
    run = run_configured_simulation(default_config())

    with pytest.raises(ValueError, match=match):
        SimulationRun(result=run.result, simulator=simulator, seed=seed)


def test_run_configured_simulation_rejects_unknown_simulator() -> None:
    """Unknown simulator names should fail before execution."""
    with pytest.raises(ValueError, match="simulator"):
        run_configured_simulation(
            default_config(),
            simulator=cast(SimulatorKind, "unknown"),
        )


def test_simulation_provenance_records_include_targets_and_fit() -> None:
    """Workflow provenance should include summaries, targets, and fit metrics."""
    run = run_configured_simulation(default_config())

    records = simulation_provenance_records(
        run,
        source="steppe",
        region="britain",
        dataset=_target_dataset(),
    )
    names = {record.name for record in records}

    assert "final_ancestry" in names
    assert "target_mean" in names
    assert "chi_square" in names


def test_simulation_experiment_manifest_records_run_metadata() -> None:
    """Workflow manifests should attach artifacts and simulation fingerprints."""
    run = run_configured_simulation(default_config())
    artifact = ExperimentArtifact("config", "config", "scenario.toml")

    manifest = simulation_experiment_manifest(
        run,
        source="steppe",
        region="britain",
        artifacts=(artifact,),
        command="demo",
        name="demo-run",
        description="Demo run manifest",
        metadata={"scenario": "synthetic"},
    )

    assert manifest.name == "demo-run"
    assert manifest.description == "Demo run manifest"
    assert manifest.artifacts == (artifact,)
    assert manifest.fingerprints[0].kind == "simulation_result"
    assert manifest.metadata == {
        "command": "demo",
        "simulator": "deterministic",
        "source": "steppe",
        "region": "britain",
        "seed": "",
        "scenario": "synthetic",
    }


def test_write_simulation_outputs_materializes_requested_files(
    tmp_path: Path,
) -> None:
    """Workflow output writing should create plots, reports, and manifests."""
    config_path = tmp_path / "scenario.toml"
    targets_path = tmp_path / "targets.csv"
    plot_path = tmp_path / "plots" / "ancestry.png"
    provenance_path = tmp_path / "reports" / "provenance.csv"
    manifest_path = tmp_path / "manifests" / "run.json"
    config_path.write_text("[simulation]\n", encoding="utf-8")
    targets_path.write_text("synthetic target placeholder\n", encoding="utf-8")
    run = run_configured_simulation(default_config())

    bundle = write_simulation_outputs(
        run,
        source="steppe",
        region="britain",
        dataset=_target_dataset(),
        paths=SimulationOutputPaths(
            config=config_path,
            targets=targets_path,
            plot=plot_path,
            provenance_csv=provenance_path,
            manifest_json=manifest_path,
        ),
        command="test-run",
        manifest_name="test-manifest",
        manifest_description="Test manifest",
        manifest_metadata={"scenario": "synthetic"},
    )
    manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert plot_path.exists()
    assert "target_mean" in provenance_path.read_text(encoding="utf-8")
    assert bundle.plot_path == plot_path
    assert bundle.provenance_csv_path == provenance_path
    assert bundle.manifest_json_path == manifest_path
    assert bundle.manifest is not None
    assert bundle.manifest.name == "test-manifest"
    assert {artifact.role for artifact in bundle.artifacts} == {
        "config",
        "targets",
        "plot",
        "provenance",
    }
    assert {record.name for record in bundle.provenance_records}.issuperset(
        {"final_ancestry", "target_mean", "chi_square"}
    )
    assert manifest_payload["name"] == "test-manifest"
    assert manifest_payload["metadata"]["scenario"] == "synthetic"


def test_write_simulation_outputs_can_return_records_without_files() -> None:
    """Workflow output writing should also work as an in-memory assembler."""
    run = run_configured_simulation(default_config())

    bundle = write_simulation_outputs(
        run,
        source="steppe",
        region="britain",
    )

    assert bundle.artifacts == ()
    assert bundle.manifest is None
    assert bundle.plot_path is None
    assert bundle.provenance_csv_path is None
    assert bundle.manifest_json_path is None
    assert "final_ancestry" in {record.name for record in bundle.provenance_records}
