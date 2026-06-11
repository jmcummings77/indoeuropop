"""Tests for emulator-training dataset scaffolds."""

import pytest

from indoeuropop.emulator_training import (
    EmulatorTrainingDataset,
    EmulatorTrainingRow,
    emulator_training_dataset_from_sweep_runs,
)
from indoeuropop.models import SimulationParameters
from indoeuropop.reproducibility import (
    fingerprint_payload,
    fingerprint_sweep_collection,
    fingerprint_sweep_run,
)
from indoeuropop.summary import TrajectorySummary
from indoeuropop.summary_statistics import SummaryVector, trajectory_summary_vector
from indoeuropop.sweeps import SweepRun


def _summary(final_ancestry: float = 0.2, extinct: bool = False) -> TrajectorySummary:
    """Return one trajectory summary for emulator-training tests."""
    return TrajectorySummary(
        source="steppe",
        region="britain",
        start_bce=3000,
        end_bce=2900,
        initial_ancestry=0.0,
        final_ancestry=final_ancestry,
        ancestry_delta=final_ancestry,
        ancestry_slope_per_century=final_ancestry,
        min_total_population=100,
        final_total_population=100,
        is_extinct=extinct,
    )


def _run(index: int, migration_rate: float, final_ancestry: float) -> SweepRun:
    """Return one sweep run with sampled parameters and summary output."""
    return SweepRun(
        index=index,
        sampled_values={
            "migration_rate": migration_rate,
            "epidemic_mortality_rate": 0.01,
        },
        parameters=SimulationParameters(
            migration_rate=migration_rate,
            epidemic_mortality_rate=0.01,
        ),
        summary=_summary(final_ancestry),
    )


def _row(
    index: int = 1, summary_vector: SummaryVector | None = None
) -> EmulatorTrainingRow:
    """Return one valid training row."""
    run = _run(index=index, migration_rate=0.002, final_ancestry=0.2)
    return EmulatorTrainingRow(
        index=index,
        parameter_values=run.sampled_values,
        summary_vector=summary_vector or trajectory_summary_vector(run.summary),
        run_fingerprint=fingerprint_sweep_run(run),
    )


def _dataset(rows: tuple[EmulatorTrainingRow, ...]) -> EmulatorTrainingDataset:
    """Return a dataset with a valid collection fingerprint."""
    runs = tuple(
        _run(row.index, row.parameter_value("migration_rate"), 0.2) for row in rows
    )
    return EmulatorTrainingDataset(
        rows=rows,
        collection_fingerprint=fingerprint_sweep_collection(runs),
    )


def test_emulator_training_row_normalizes_parameters_and_names() -> None:
    """Training rows should expose finite sampled parameters in stable order."""
    row = _row()

    assert row.parameter_names() == (
        "epidemic_mortality_rate",
        "migration_rate",
    )
    assert row.parameter_value("migration_rate") == 0.002
    assert row.run_fingerprint.kind == "sweep_run"


@pytest.mark.parametrize(
    "index,parameter_values",
    [
        (-1, {"migration_rate": 0.1}),
        (0, {}),
        (0, {"": 0.1}),
        (0, {"migration_rate": float("nan")}),
    ],
)
def test_emulator_training_row_rejects_invalid_fields(
    index: int, parameter_values: dict[str, float]
) -> None:
    """Invalid row metadata should fail before matrix construction."""
    with pytest.raises(ValueError):
        EmulatorTrainingRow(
            index=index,
            parameter_values=parameter_values,
            summary_vector=trajectory_summary_vector(_summary()),
            run_fingerprint=fingerprint_sweep_run(_run(0, 0.001, 0.2)),
        )


def test_emulator_training_row_rejects_wrong_fingerprint_kind() -> None:
    """Row fingerprints should identify individual sweep runs."""
    with pytest.raises(ValueError):
        EmulatorTrainingRow(
            index=0,
            parameter_values={"migration_rate": 0.1},
            summary_vector=trajectory_summary_vector(_summary()),
            run_fingerprint=fingerprint_payload("simulation_result", {"x": 1}),
        )


def test_dataset_from_sweep_runs_builds_matrices_and_fingerprints() -> None:
    """Sweep runs should become stable parameter and summary matrices."""
    runs = (
        _run(index=1, migration_rate=0.001, final_ancestry=0.2),
        _run(index=2, migration_rate=0.003, final_ancestry=0.4),
    )

    dataset = emulator_training_dataset_from_sweep_runs(
        runs,
        scales={"final_total_population": 100},
    )

    assert dataset.parameter_names() == (
        "epidemic_mortality_rate",
        "migration_rate",
    )
    assert dataset.parameter_matrix().tolist() == [[0.01, 0.001], [0.01, 0.003]]
    assert dataset.parameter_matrix(("migration_rate",)).tolist() == [[0.001], [0.003]]
    assert dataset.summary_statistic_names() == (
        "initial_ancestry",
        "final_ancestry",
        "ancestry_delta",
        "ancestry_slope_per_century",
        "min_total_population",
        "final_total_population",
        "is_extinct",
    )
    assert dataset.summary_matrix(("final_ancestry",)).tolist() == [[0.2], [0.4]]
    assert dataset.summary_matrix(
        ("final_total_population",), normalized=True
    ).tolist() == [
        [1.0],
        [1.0],
    ]
    assert dataset.run_fingerprints() == tuple(
        fingerprint_sweep_run(run).digest_sha256 for run in runs
    )
    assert dataset.collection_fingerprint.digest_sha256 == (
        fingerprint_sweep_collection(runs).digest_sha256
    )


def test_dataset_from_sweep_runs_can_omit_extinction_indicator() -> None:
    """Continuous-only summary matrices can omit the extinction indicator."""
    dataset = emulator_training_dataset_from_sweep_runs(
        (_run(index=1, migration_rate=0.001, final_ancestry=0.2),),
        include_extinction=False,
    )

    assert "is_extinct" not in dataset.summary_statistic_names()


def test_dataset_from_sweep_runs_rejects_empty_runs() -> None:
    """Training datasets should require at least one source run."""
    with pytest.raises(ValueError):
        emulator_training_dataset_from_sweep_runs(())


def test_emulator_training_dataset_rejects_invalid_rows_or_fingerprint() -> None:
    """Dataset-level validation should reject invalid row collections."""
    row = _row()
    valid_collection = fingerprint_sweep_collection((_run(1, 0.002, 0.2),))

    with pytest.raises(ValueError):
        EmulatorTrainingDataset(rows=(), collection_fingerprint=valid_collection)
    with pytest.raises(ValueError):
        EmulatorTrainingDataset(
            rows=(row,),
            collection_fingerprint=fingerprint_payload("sweep_run", {"x": 1}),
        )
    with pytest.raises(ValueError):
        EmulatorTrainingDataset(
            rows=(row, row),
            collection_fingerprint=valid_collection,
        )


def test_emulator_training_dataset_rejects_inconsistent_parameter_names() -> None:
    """Rows in one dataset should share the same parameter schema."""
    first = _row(index=1)
    second_run = _run(index=2, migration_rate=0.004, final_ancestry=0.3)
    second = EmulatorTrainingRow(
        index=2,
        parameter_values={"migration_rate": 0.004},
        summary_vector=trajectory_summary_vector(second_run.summary),
        run_fingerprint=fingerprint_sweep_run(second_run),
    )

    with pytest.raises(ValueError, match="parameter names"):
        _dataset((first, second))


def test_emulator_training_dataset_rejects_inconsistent_summary_names() -> None:
    """Rows in one dataset should share the same summary-statistic schema."""
    first = _row(index=1)
    second = _row(
        index=2,
        summary_vector=SummaryVector.from_mapping({"final_ancestry": 0.3}),
    )

    with pytest.raises(ValueError, match="summary statistic names"):
        _dataset((first, second))


def test_emulator_training_dataset_rejects_invalid_matrix_selections() -> None:
    """Matrix column selections should be known and non-empty."""
    dataset = emulator_training_dataset_from_sweep_runs(
        (_run(index=1, migration_rate=0.001, final_ancestry=0.2),)
    )

    with pytest.raises(KeyError):
        dataset.parameter_matrix(("unknown",))
    with pytest.raises(ValueError):
        dataset.parameter_matrix(())
    with pytest.raises(KeyError):
        dataset.summary_matrix(("unknown",))
    with pytest.raises(ValueError):
        dataset.summary_matrix(())
