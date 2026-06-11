"""Tests for future-emulator validation helpers."""

import pytest

from indoeuropop.emulator_training import (
    EmulatorTrainingDataset,
    emulator_training_dataset_from_sweep_runs,
)
from indoeuropop.emulator_validation import (
    EmulatorPrediction,
    EmulatorValidationCase,
    EmulatorValidationReport,
    validate_emulator_predictions,
)
from indoeuropop.models import SimulationParameters
from indoeuropop.summary import TrajectorySummary
from indoeuropop.summary_statistics import SummaryVector, trajectory_summary_vector
from indoeuropop.sweeps import SweepRun


def _summary(final_ancestry: float = 0.2) -> TrajectorySummary:
    """Return one trajectory summary for emulator-validation tests."""
    return TrajectorySummary(
        source="steppe",
        region="britain",
        start_bce=3000,
        end_bce=2900,
        initial_ancestry=0,
        final_ancestry=final_ancestry,
        ancestry_delta=final_ancestry,
        ancestry_slope_per_century=final_ancestry,
        min_total_population=100,
        final_total_population=100,
        is_extinct=False,
    )


def _run(index: int, final_ancestry: float) -> SweepRun:
    """Return one sweep run for validation tests."""
    return SweepRun(
        index=index,
        sampled_values={"migration_rate": 0.001 * index},
        parameters=SimulationParameters(migration_rate=0.001 * index),
        summary=_summary(final_ancestry),
    )


def _dataset() -> tuple[EmulatorTrainingDataset, tuple[SweepRun, ...]]:
    """Return a small emulator-training dataset and its source runs."""
    runs = (_run(1, 0.2), _run(2, 0.4))
    return (
        emulator_training_dataset_from_sweep_runs(
            runs,
            scales={"final_ancestry": 0.1},
        ),
        runs,
    )


def _predictions(final_values: tuple[float, float]) -> tuple[EmulatorPrediction, ...]:
    """Return predictions aligned with the helper dataset."""
    dataset, _runs = _dataset()
    return tuple(
        EmulatorPrediction(
            run_fingerprint_sha256=row.run_fingerprint.digest_sha256,
            summary_vector=trajectory_summary_vector(
                _summary(final_values[index]),
                scales={"final_ancestry": 0.1},
            ),
        )
        for index, row in enumerate(dataset.rows)
    )


def test_validate_emulator_predictions_reports_distances_and_thresholds() -> None:
    """Predictions should compare against explicit simulator summary vectors."""
    dataset, _runs = _dataset()

    report = validate_emulator_predictions(
        dataset,
        _predictions((0.2, 0.45)),
        statistic_names=("final_ancestry",),
        max_allowed_distance=0.25,
    )

    assert report.statistic_names == ("final_ancestry",)
    assert report.mean_distance == pytest.approx(0.25)
    assert report.max_distance == pytest.approx(0.5)
    assert not report.passes
    assert len(report.failed_cases) == 1
    assert tuple(case.row_index for case in report.cases) == (1, 2)
    assert tuple(case.within_threshold for case in report.cases) == (True, False)


def test_validate_emulator_predictions_without_threshold_passes_all_cases() -> None:
    """Without a configured threshold, validation cases should be informational."""
    dataset, _runs = _dataset()

    report = validate_emulator_predictions(
        dataset,
        _predictions((0.0, 1.0)),
        statistic_names=("final_ancestry",),
    )

    assert report.passes
    assert report.failed_cases == ()
    assert report.max_allowed_distance is None


def test_validate_emulator_predictions_uses_all_statistics_by_default() -> None:
    """Default comparisons should include the dataset summary schema."""
    dataset, _runs = _dataset()

    report = validate_emulator_predictions(dataset, _predictions((0.2, 0.4)))

    assert report.statistic_names == dataset.summary_statistic_names()
    assert report.max_distance == 0


@pytest.mark.parametrize("bad_threshold", [-0.1, float("nan")])
def test_validate_emulator_predictions_rejects_bad_threshold(
    bad_threshold: float,
) -> None:
    """Validation thresholds should be finite and non-negative."""
    dataset, _runs = _dataset()

    with pytest.raises(ValueError):
        validate_emulator_predictions(
            dataset,
            _predictions((0.2, 0.4)),
            max_allowed_distance=bad_threshold,
        )


def test_validate_emulator_predictions_rejects_missing_extra_or_duplicate() -> None:
    """Prediction sets should match dataset run fingerprints exactly."""
    dataset, _runs = _dataset()
    predictions = _predictions((0.2, 0.4))
    extra_prediction = EmulatorPrediction(
        run_fingerprint_sha256="0" * 64,
        summary_vector=trajectory_summary_vector(_summary(0.2)),
    )

    with pytest.raises(ValueError, match="missing emulator predictions"):
        validate_emulator_predictions(dataset, predictions[:1])
    with pytest.raises(ValueError, match="unexpected emulator predictions"):
        validate_emulator_predictions(dataset, (*predictions, extra_prediction))
    with pytest.raises(ValueError, match="duplicate emulator prediction"):
        validate_emulator_predictions(dataset, (predictions[0], predictions[0]))
    with pytest.raises(ValueError, match="at least one"):
        validate_emulator_predictions(dataset, ())


def test_validate_emulator_predictions_rejects_bad_statistic_selection() -> None:
    """Selected summary-statistic names should be known and non-empty."""
    dataset, _runs = _dataset()

    with pytest.raises(KeyError):
        validate_emulator_predictions(
            dataset,
            _predictions((0.2, 0.4)),
            statistic_names=("unknown",),
        )
    with pytest.raises(ValueError):
        validate_emulator_predictions(
            dataset,
            _predictions((0.2, 0.4)),
            statistic_names=(),
        )


def test_validate_emulator_predictions_rejects_prediction_schema_mismatch() -> None:
    """Predicted summary vectors should contain every selected statistic."""
    dataset, _runs = _dataset()
    first_prediction, second_prediction = _predictions((0.2, 0.4))
    bad_prediction = EmulatorPrediction(
        run_fingerprint_sha256=first_prediction.run_fingerprint_sha256,
        summary_vector=SummaryVector.from_mapping({"other": 0.2}),
    )

    with pytest.raises(KeyError):
        validate_emulator_predictions(
            dataset,
            (bad_prediction, second_prediction),
            statistic_names=("final_ancestry",),
        )


def test_emulator_prediction_rejects_invalid_fingerprint() -> None:
    """Predictions should reference a lowercase SHA-256 run fingerprint."""
    with pytest.raises(ValueError):
        EmulatorPrediction(
            run_fingerprint_sha256="not-a-digest",
            summary_vector=trajectory_summary_vector(_summary()),
        )


@pytest.mark.parametrize(
    "row_index,run_fingerprint_sha256,root_mean_square_distance",
    [
        (-1, "0" * 64, 0),
        (0, "not-a-digest", 0),
        (0, "0" * 64, -1),
    ],
)
def test_emulator_validation_case_rejects_invalid_fields(
    row_index: int,
    run_fingerprint_sha256: str,
    root_mean_square_distance: float,
) -> None:
    """Invalid validation cases should fail before report construction."""
    with pytest.raises(ValueError):
        EmulatorValidationCase(
            row_index=row_index,
            run_fingerprint_sha256=run_fingerprint_sha256,
            root_mean_square_distance=root_mean_square_distance,
            within_threshold=True,
        )


@pytest.mark.parametrize(
    "cases,statistic_names,max_allowed_distance",
    [
        ((), ("final_ancestry",), None),
        (
            (
                EmulatorValidationCase(
                    row_index=0,
                    run_fingerprint_sha256="0" * 64,
                    root_mean_square_distance=0,
                    within_threshold=True,
                ),
            ),
            (),
            None,
        ),
        (
            (
                EmulatorValidationCase(
                    row_index=0,
                    run_fingerprint_sha256="0" * 64,
                    root_mean_square_distance=0,
                    within_threshold=True,
                ),
            ),
            ("final_ancestry",),
            -1,
        ),
    ],
)
def test_emulator_validation_report_rejects_invalid_fields(
    cases: tuple[EmulatorValidationCase, ...],
    statistic_names: tuple[str, ...],
    max_allowed_distance: float | None,
) -> None:
    """Invalid validation reports should fail clearly."""
    with pytest.raises(ValueError):
        EmulatorValidationReport(
            cases=cases,
            statistic_names=statistic_names,
            max_allowed_distance=max_allowed_distance,
        )
