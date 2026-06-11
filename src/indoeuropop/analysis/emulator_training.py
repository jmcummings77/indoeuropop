"""Reproducible training tables for future emulator experiments."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from math import isfinite

import numpy as np
from numpy.typing import NDArray

from indoeuropop.analysis.summary_statistics import (
    SummaryVector,
    trajectory_summary_vector,
)
from indoeuropop.orchestration.sweeps import SweepRun
from indoeuropop.reporting.reproducibility import (
    ReproducibilityFingerprint,
    fingerprint_sweep_collection,
    fingerprint_sweep_run,
)


@dataclass(frozen=True)
class EmulatorTrainingRow:
    """One sweep run transformed into emulator-training features and outputs."""

    index: int
    parameter_values: Mapping[str, float]
    summary_vector: SummaryVector
    run_fingerprint: ReproducibilityFingerprint

    def __post_init__(self) -> None:
        """Validate row fields and normalize parameter values."""
        if self.index < 0:
            raise ValueError("index must be non-negative")
        if not self.parameter_values:
            raise ValueError("parameter_values must not be empty")
        if self.run_fingerprint.kind != "sweep_run":
            raise ValueError("run_fingerprint must describe a sweep_run")

        normalized: dict[str, float] = {}
        for name, value in self.parameter_values.items():
            if not name:
                raise ValueError("parameter names must be non-empty")
            numeric_value = float(value)
            if not isfinite(numeric_value):
                raise ValueError("parameter values must be finite")
            normalized[name] = numeric_value
        object.__setattr__(self, "parameter_values", normalized)

    def parameter_names(self) -> tuple[str, ...]:
        """Return parameter names in deterministic matrix order."""
        return tuple(sorted(self.parameter_values))

    def parameter_value(self, name: str) -> float:
        """Return one sampled parameter value."""
        return self.parameter_values[name]


@dataclass(frozen=True)
class EmulatorTrainingDataset:
    """A validated matrix-ready dataset for future emulator experiments."""

    rows: tuple[EmulatorTrainingRow, ...]
    collection_fingerprint: ReproducibilityFingerprint

    def __post_init__(self) -> None:
        """Validate dataset rows and shared matrix schema."""
        if not self.rows:
            raise ValueError("rows must contain at least one emulator training row")
        if self.collection_fingerprint.kind != "sweep_collection":
            raise ValueError("collection_fingerprint must describe a sweep_collection")
        indices = [row.index for row in self.rows]
        if len(indices) != len(set(indices)):
            raise ValueError("row indices must be unique")
        _require_consistent_names(
            self.rows[0].parameter_names(),
            (row.parameter_names() for row in self.rows),
            "parameter",
        )
        _require_consistent_names(
            self.rows[0].summary_vector.names(),
            (row.summary_vector.names() for row in self.rows),
            "summary statistic",
        )

    def parameter_names(self) -> tuple[str, ...]:
        """Return parameter names in matrix column order."""
        return self.rows[0].parameter_names()

    def summary_statistic_names(self) -> tuple[str, ...]:
        """Return summary-statistic names in matrix column order."""
        return self.rows[0].summary_vector.names()

    def parameter_matrix(
        self, names: Iterable[str] | None = None
    ) -> NDArray[np.float64]:
        """Return sampled parameter values as a two-dimensional matrix."""
        selected_names = _selected_names(self.parameter_names(), names, "parameter")
        return np.array(
            [
                [row.parameter_value(name) for name in selected_names]
                for row in self.rows
            ],
            dtype=np.float64,
        )

    def summary_matrix(
        self,
        names: Iterable[str] | None = None,
        *,
        normalized: bool = False,
    ) -> NDArray[np.float64]:
        """Return summary statistics as a two-dimensional matrix."""
        selected_names = _selected_names(
            self.summary_statistic_names(), names, "summary statistic"
        )
        values = [
            (
                row.summary_vector.normalized_values(selected_names)
                if normalized
                else tuple(row.summary_vector.value(name) for name in selected_names)
            )
            for row in self.rows
        ]
        return np.array(values, dtype=np.float64)

    def run_fingerprints(self) -> tuple[str, ...]:
        """Return row-level sweep-run fingerprint digests in row order."""
        return tuple(row.run_fingerprint.digest_sha256 for row in self.rows)


def emulator_training_dataset_from_sweep_runs(
    runs: Iterable[SweepRun],
    *,
    scales: Mapping[str, float] | None = None,
    include_extinction: bool = True,
) -> EmulatorTrainingDataset:
    """Build an emulator-training dataset from reproducible sweep runs.

    This prepares matrices for later surrogate modeling; it does not train,
    validate, or endorse an emulator.
    """
    run_tuple = tuple(runs)
    collection_fingerprint = fingerprint_sweep_collection(run_tuple)
    rows = tuple(
        EmulatorTrainingRow(
            index=run.index,
            parameter_values=run.sampled_values,
            summary_vector=trajectory_summary_vector(
                run.summary,
                scales=scales,
                include_extinction=include_extinction,
            ),
            run_fingerprint=fingerprint_sweep_run(run),
        )
        for run in run_tuple
    )
    return EmulatorTrainingDataset(
        rows=rows,
        collection_fingerprint=collection_fingerprint,
    )


def _require_consistent_names(
    expected: tuple[str, ...], observed_values: Iterable[tuple[str, ...]], label: str
) -> None:
    """Require every observed name tuple to match the expected schema."""
    for observed in observed_values:
        if observed != expected:
            raise ValueError(f"{label} names must be consistent across rows")


def _selected_names(
    available_names: tuple[str, ...], selected_names: Iterable[str] | None, label: str
) -> tuple[str, ...]:
    """Return selected names after validating they exist and are non-empty."""
    names = available_names if selected_names is None else tuple(selected_names)
    if not names:
        raise ValueError(f"at least one {label} name must be selected")
    unknown_names = set(names).difference(available_names)
    if unknown_names:
        unknown_text = ", ".join(sorted(unknown_names))
        raise KeyError(f"unknown {label} names: {unknown_text}")
    return names
