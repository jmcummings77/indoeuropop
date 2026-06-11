"""Validation helpers for future emulator predictions."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from math import isfinite

from indoeuropop.emulator_training import EmulatorTrainingDataset
from indoeuropop.reproducibility import HEX_DIGITS
from indoeuropop.summary_statistics import SummaryVector


@dataclass(frozen=True)
class EmulatorPrediction:
    """A future emulator's predicted summary vector for one sweep run."""

    run_fingerprint_sha256: str
    summary_vector: SummaryVector

    def __post_init__(self) -> None:
        """Validate the referenced sweep-run fingerprint digest."""
        if not _is_sha256_digest(self.run_fingerprint_sha256):
            raise ValueError("run_fingerprint_sha256 must be a 64-character hex digest")


@dataclass(frozen=True)
class EmulatorValidationCase:
    """One emulator prediction compared to one explicit simulator output."""

    row_index: int
    run_fingerprint_sha256: str
    root_mean_square_distance: float
    within_threshold: bool

    def __post_init__(self) -> None:
        """Validate comparison metadata and distance."""
        if self.row_index < 0:
            raise ValueError("row_index must be non-negative")
        if not _is_sha256_digest(self.run_fingerprint_sha256):
            raise ValueError("run_fingerprint_sha256 must be a 64-character hex digest")
        if (
            not isfinite(self.root_mean_square_distance)
            or self.root_mean_square_distance < 0
        ):
            raise ValueError(
                "root_mean_square_distance must be finite and non-negative"
            )


@dataclass(frozen=True)
class EmulatorValidationReport:
    """Aggregate validation report for emulator predictions."""

    cases: tuple[EmulatorValidationCase, ...]
    statistic_names: tuple[str, ...]
    max_allowed_distance: float | None = None

    def __post_init__(self) -> None:
        """Validate report structure and optional threshold."""
        if not self.cases:
            raise ValueError("cases must contain at least one validation case")
        if not self.statistic_names:
            raise ValueError("statistic_names must not be empty")
        if self.max_allowed_distance is not None and (
            not isfinite(self.max_allowed_distance) or self.max_allowed_distance < 0
        ):
            raise ValueError("max_allowed_distance must be finite and non-negative")

    @property
    def mean_distance(self) -> float:
        """Return the mean root-mean-square summary distance."""
        return sum(case.root_mean_square_distance for case in self.cases) / len(
            self.cases
        )

    @property
    def max_distance(self) -> float:
        """Return the largest root-mean-square summary distance."""
        return max(case.root_mean_square_distance for case in self.cases)

    @property
    def failed_cases(self) -> tuple[EmulatorValidationCase, ...]:
        """Return validation cases outside the configured threshold."""
        return tuple(case for case in self.cases if not case.within_threshold)

    @property
    def passes(self) -> bool:
        """Return whether all cases are within the configured threshold."""
        return not self.failed_cases


def validate_emulator_predictions(
    dataset: EmulatorTrainingDataset,
    predictions: Iterable[EmulatorPrediction],
    *,
    statistic_names: Iterable[str] | None = None,
    max_allowed_distance: float | None = None,
) -> EmulatorValidationReport:
    """Compare emulator predictions against explicit simulator summary vectors."""
    if max_allowed_distance is not None and (
        not isfinite(max_allowed_distance) or max_allowed_distance < 0
    ):
        raise ValueError("max_allowed_distance must be finite and non-negative")

    selected_statistic_names = _selected_statistic_names(dataset, statistic_names)
    prediction_map = _prediction_map(predictions)
    expected_fingerprints = set(dataset.run_fingerprints())
    observed_fingerprints = set(prediction_map)
    missing_fingerprints = expected_fingerprints.difference(observed_fingerprints)
    if missing_fingerprints:
        missing_text = ", ".join(sorted(missing_fingerprints))
        raise ValueError(f"missing emulator predictions for: {missing_text}")
    extra_fingerprints = observed_fingerprints.difference(expected_fingerprints)
    if extra_fingerprints:
        extra_text = ", ".join(sorted(extra_fingerprints))
        raise ValueError(f"unexpected emulator predictions for: {extra_text}")

    cases = tuple(
        _validation_case(
            row_index=row.index,
            actual=row.summary_vector,
            prediction=prediction_map[row.run_fingerprint.digest_sha256],
            statistic_names=selected_statistic_names,
            max_allowed_distance=max_allowed_distance,
        )
        for row in dataset.rows
    )
    return EmulatorValidationReport(
        cases=cases,
        statistic_names=selected_statistic_names,
        max_allowed_distance=max_allowed_distance,
    )


def _prediction_map(
    predictions: Iterable[EmulatorPrediction],
) -> dict[str, EmulatorPrediction]:
    """Return predictions keyed by run fingerprint after duplicate checks."""
    prediction_by_fingerprint: dict[str, EmulatorPrediction] = {}
    for prediction in predictions:
        fingerprint = prediction.run_fingerprint_sha256
        if fingerprint in prediction_by_fingerprint:
            raise ValueError(f"duplicate emulator prediction for: {fingerprint}")
        prediction_by_fingerprint[fingerprint] = prediction
    if not prediction_by_fingerprint:
        raise ValueError("predictions must contain at least one emulator prediction")
    return prediction_by_fingerprint


def _selected_statistic_names(
    dataset: EmulatorTrainingDataset, statistic_names: Iterable[str] | None
) -> tuple[str, ...]:
    """Return selected summary-statistic names after validation."""
    names = (
        dataset.summary_statistic_names()
        if statistic_names is None
        else tuple(statistic_names)
    )
    if not names:
        raise ValueError("statistic_names must not be empty")
    unknown_names = set(names).difference(dataset.summary_statistic_names())
    if unknown_names:
        unknown_text = ", ".join(sorted(unknown_names))
        raise KeyError(f"unknown summary statistic names: {unknown_text}")
    return names


def _validation_case(
    *,
    row_index: int,
    actual: SummaryVector,
    prediction: EmulatorPrediction,
    statistic_names: tuple[str, ...],
    max_allowed_distance: float | None,
) -> EmulatorValidationCase:
    """Return one validation case for actual and predicted summary vectors."""
    distance = actual.root_mean_square_distance(
        prediction.summary_vector, names=statistic_names
    )
    return EmulatorValidationCase(
        row_index=row_index,
        run_fingerprint_sha256=prediction.run_fingerprint_sha256,
        root_mean_square_distance=distance,
        within_threshold=(
            True if max_allowed_distance is None else distance <= max_allowed_distance
        ),
    )


def _is_sha256_digest(value: str) -> bool:
    """Return whether a value is a lowercase SHA-256 hex digest."""
    return len(value) == 64 and all(character in HEX_DIGITS for character in value)
