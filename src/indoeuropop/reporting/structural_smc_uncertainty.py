"""Uncertainty-aware diagnostics for structural SMC disagreement folds."""

from __future__ import annotations

import csv
from collections.abc import Iterable
from dataclasses import dataclass
from io import StringIO
from math import isfinite
from pathlib import Path

from indoeuropop.reporting.structural_smc_disagreement_models import (
    StructuralSMCDisagreementRow,
)
from indoeuropop.reporting.structural_smc_disagreements import (
    load_structural_smc_disagreement_report,
)

DEFAULT_MATERIAL_CHI_SQUARE_DELTA = 1.0

STRUCTURAL_SMC_UNCERTAINTY_FIELDS = (
    "fold_name",
    "target_id",
    "requested_group_id",
    "sample_count",
    "observed_mean",
    "uncertainty",
    "structured_pulse_prediction_mean",
    "structured_pulse_mean_residual",
    "structured_pulse_z_score",
    "structured_pulse_chi_square",
    "child_override_prediction_mean",
    "child_override_mean_residual",
    "child_override_z_score",
    "child_override_chi_square",
    "child_minus_structured_pulse_chi_square_delta",
    "raw_residual_preferred_candidate",
    "uncertainty_weighted_preferred_candidate",
)


@dataclass(frozen=True)
class StructuralSMCUncertaintyRow:
    """One disagreement target with residuals normalized by target uncertainty."""

    disagreement: StructuralSMCDisagreementRow

    @property
    def uncertainty(self) -> float:
        """Return the target observation uncertainty."""
        return self.disagreement.observation.uncertainty

    @property
    def structured_pulse_z_score(self) -> float:
        """Return the structured-pulse residual divided by target uncertainty."""
        return self.disagreement.structured_pulse_mean_residual / self.uncertainty

    @property
    def child_override_z_score(self) -> float:
        """Return the child-override residual divided by target uncertainty."""
        return self.disagreement.child_override_mean_residual / self.uncertainty

    @property
    def structured_pulse_chi_square(self) -> float:
        """Return the one-target chi-square contribution for structured pulse."""
        return self.structured_pulse_z_score**2

    @property
    def child_override_chi_square(self) -> float:
        """Return the one-target chi-square contribution for child override."""
        return self.child_override_z_score**2

    @property
    def child_minus_structured_pulse_chi_square_delta(self) -> float:
        """Return child chi-square minus structured-pulse chi-square."""
        return self.child_override_chi_square - self.structured_pulse_chi_square

    def uncertainty_weighted_preferred_candidate(
        self,
        material_chi_square_delta: float = DEFAULT_MATERIAL_CHI_SQUARE_DELTA,
    ) -> str:
        """Return the uncertainty-weighted target preference."""
        return _preferred_candidate(
            self.child_minus_structured_pulse_chi_square_delta,
            material_chi_square_delta,
        )


@dataclass(frozen=True)
class StructuralSMCUncertaintyReport:
    """Uncertainty-aware report for structural SMC disagreement targets."""

    rows: tuple[StructuralSMCUncertaintyRow, ...]
    material_chi_square_delta: float = DEFAULT_MATERIAL_CHI_SQUARE_DELTA

    def __post_init__(self) -> None:
        """Validate the material-difference threshold."""
        if (
            not isfinite(self.material_chi_square_delta)
            or self.material_chi_square_delta < 0
        ):
            raise ValueError("material_chi_square_delta must be non-negative")

    @property
    def fold_count(self) -> int:
        """Return the number of disagreement folds represented by rows."""
        return len({row.disagreement.fold_name for row in self.rows})

    @property
    def target_count(self) -> int:
        """Return the number of held-out target rows represented."""
        return len(self.rows)

    @property
    def structured_pulse_target_count(self) -> int:
        """Return targets materially favoring structured pulse."""
        return self._candidate_count("structured_pulse")

    @property
    def child_override_target_count(self) -> int:
        """Return targets materially favoring child override."""
        return self._candidate_count("child_override")

    @property
    def uncertainty_tie_target_count(self) -> int:
        """Return targets whose chi-square delta is below the material threshold."""
        return self._candidate_count("uncertainty_tie")

    @property
    def ranked_rows(self) -> tuple[StructuralSMCUncertaintyRow, ...]:
        """Return rows sorted by strongest material chi-square difference."""
        return tuple(
            sorted(
                self.rows,
                key=lambda row: abs(row.child_minus_structured_pulse_chi_square_delta),
                reverse=True,
            )
        )

    def _candidate_count(self, candidate: str) -> int:
        """Return the count of rows assigned to one uncertainty preference."""
        return sum(
            row.uncertainty_weighted_preferred_candidate(self.material_chi_square_delta)
            == candidate
            for row in self.rows
        )


def load_structural_smc_uncertainty_report(
    summary_csv: str | Path,
    validation_output_dir: str | Path,
    *,
    material_chi_square_delta: float = DEFAULT_MATERIAL_CHI_SQUARE_DELTA,
) -> StructuralSMCUncertaintyReport:
    """Load uncertainty-aware rows for structural SMC disagreement folds."""
    disagreement_report = load_structural_smc_disagreement_report(
        summary_csv,
        validation_output_dir,
    )
    return StructuralSMCUncertaintyReport(
        rows=tuple(
            StructuralSMCUncertaintyRow(row) for row in disagreement_report.rows
        ),
        material_chi_square_delta=material_chi_square_delta,
    )


def structural_smc_uncertainty_rows(
    report: StructuralSMCUncertaintyReport,
) -> tuple[dict[str, str], ...]:
    """Return uncertainty-aware target rows as CSV-ready dictionaries."""
    return tuple(_row_payload(report, row) for row in report.rows)


def structural_smc_uncertainty_to_csv(
    report: StructuralSMCUncertaintyReport,
) -> str:
    """Return uncertainty-aware target rows serialized as CSV text."""
    output = StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=STRUCTURAL_SMC_UNCERTAINTY_FIELDS,
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerows(structural_smc_uncertainty_rows(report))
    return output.getvalue()


def write_structural_smc_uncertainty_csv(
    report: StructuralSMCUncertaintyReport,
    path: str | Path,
) -> Path:
    """Write uncertainty-aware target rows to CSV and return the path."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(structural_smc_uncertainty_to_csv(report), encoding="utf-8")
    return output_path


def structural_smc_uncertainty_markdown(
    report: StructuralSMCUncertaintyReport,
) -> str:
    """Return a Markdown uncertainty-aware disagreement report."""
    output = StringIO()
    output.write("# Structural SMC Uncertainty-Aware Disagreement Review\n\n")
    output.write(
        "This report rescales candidate residuals by each held-out target's "
        "uncertainty. A small chi-square delta is treated as an uncertainty tie, "
        "even when one candidate has a slightly smaller raw residual.\n\n"
    )
    output.write(_summary_markdown(report))
    output.write(_fold_markdown(report))
    output.write(_target_markdown(report))
    output.write("## Interpretation Guardrail\n\n")
    output.write(
        "Treat uncertainty ties as weak evidence for structural revision. They "
        "should usually trigger better target or likelihood modeling before "
        "promoting a new population-structure mechanism.\n"
    )
    return output.getvalue()


def write_structural_smc_uncertainty_markdown(
    report: StructuralSMCUncertaintyReport,
    path: str | Path,
) -> Path:
    """Write an uncertainty-aware Markdown report and return the path."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        structural_smc_uncertainty_markdown(report), encoding="utf-8"
    )
    return output_path


def _row_payload(
    report: StructuralSMCUncertaintyReport,
    row: StructuralSMCUncertaintyRow,
) -> dict[str, str]:
    """Return one uncertainty-aware row as string-only CSV fields."""
    disagreement = row.disagreement
    sample_count = disagreement.sample_count
    return {
        "fold_name": disagreement.fold_name,
        "target_id": disagreement.target_id,
        "requested_group_id": disagreement.requested_group_id,
        "sample_count": "" if sample_count is None else str(sample_count),
        "observed_mean": _value_text(disagreement.observation.mean),
        "uncertainty": _value_text(row.uncertainty),
        "structured_pulse_prediction_mean": _value_text(
            disagreement.structured_pulse_prediction_mean
        ),
        "structured_pulse_mean_residual": _value_text(
            disagreement.structured_pulse_mean_residual
        ),
        "structured_pulse_z_score": _value_text(row.structured_pulse_z_score),
        "structured_pulse_chi_square": _value_text(row.structured_pulse_chi_square),
        "child_override_prediction_mean": _value_text(
            disagreement.child_override_prediction_mean
        ),
        "child_override_mean_residual": _value_text(
            disagreement.child_override_mean_residual
        ),
        "child_override_z_score": _value_text(row.child_override_z_score),
        "child_override_chi_square": _value_text(row.child_override_chi_square),
        "child_minus_structured_pulse_chi_square_delta": _value_text(
            row.child_minus_structured_pulse_chi_square_delta
        ),
        "raw_residual_preferred_candidate": disagreement.target_preferred_candidate,
        "uncertainty_weighted_preferred_candidate": (
            row.uncertainty_weighted_preferred_candidate(
                report.material_chi_square_delta
            )
        ),
    }


def _summary_markdown(report: StructuralSMCUncertaintyReport) -> str:
    """Return aggregate uncertainty-aware summary bullets."""
    return (
        "## Summary\n\n"
        f"- disagreement_fold_count: {report.fold_count}\n"
        f"- target_count: {report.target_count}\n"
        f"- material_chi_square_delta: {report.material_chi_square_delta:.12g}\n"
        f"- structured_pulse_target_count: {report.structured_pulse_target_count}\n"
        f"- child_override_target_count: {report.child_override_target_count}\n"
        f"- uncertainty_tie_target_count: {report.uncertainty_tie_target_count}\n\n"
    )


def _fold_markdown(report: StructuralSMCUncertaintyReport) -> str:
    """Return fold-level uncertainty-aware Markdown table."""
    output = StringIO()
    output.write("## Fold Summary\n\n")
    output.write(
        "| Fold | Targets | Chi-square delta | Max abs z | "
        "Uncertainty-weighted preference |\n"
    )
    output.write("| --- | ---: | ---: | ---: | --- |\n")
    for fold_name in _unique(row.disagreement.fold_name for row in report.rows):
        rows = tuple(
            row for row in report.rows if row.disagreement.fold_name == fold_name
        )
        delta = _fold_chi_square_delta(rows)
        output.write(
            f"| {fold_name} | {len(rows)} | {_value_text(delta)} | "
            f"{_value_text(_fold_max_abs_z(rows))} | "
            f"{_preferred_candidate(delta, report.material_chi_square_delta)} |\n"
        )
    output.write("\n")
    return output.getvalue()


def _target_markdown(report: StructuralSMCUncertaintyReport) -> str:
    """Return target-level uncertainty-aware Markdown table."""
    output = StringIO()
    output.write("## Target Summary\n\n")
    output.write(
        "| Fold | Requested group | Uncertainty | Pulse z | Child z | "
        "Chi-square delta | Raw preference | Uncertainty preference |\n"
    )
    output.write("| --- | --- | ---: | ---: | ---: | ---: | --- | --- |\n")
    for row in report.ranked_rows:
        disagreement = row.disagreement
        uncertainty_preference = row.uncertainty_weighted_preferred_candidate(
            report.material_chi_square_delta
        )
        output.write(
            f"| {disagreement.fold_name} | "
            f"{disagreement.requested_group_id or 'unknown'} | "
            f"{_value_text(row.uncertainty)} | "
            f"{_value_text(row.structured_pulse_z_score)} | "
            f"{_value_text(row.child_override_z_score)} | "
            f"{_value_text(row.child_minus_structured_pulse_chi_square_delta)} | "
            f"{disagreement.target_preferred_candidate} | "
            f"{uncertainty_preference} |\n"
        )
    output.write("\n")
    return output.getvalue()


def _fold_chi_square_delta(rows: tuple[StructuralSMCUncertaintyRow, ...]) -> float:
    """Return fold-level child-minus-pulse chi-square delta."""
    return sum(row.child_minus_structured_pulse_chi_square_delta for row in rows)


def _fold_max_abs_z(rows: tuple[StructuralSMCUncertaintyRow, ...]) -> float:
    """Return the largest absolute target z-score in a fold."""
    return max(
        (
            max(abs(row.structured_pulse_z_score), abs(row.child_override_z_score))
            for row in rows
        ),
        default=0.0,
    )


def _preferred_candidate(delta: float, material_delta: float) -> str:
    """Return candidate preference from child-minus-pulse chi-square delta."""
    if delta > material_delta:
        return "structured_pulse"
    if delta < -material_delta:
        return "child_override"
    return "uncertainty_tie"


def _value_text(value: float) -> str:
    """Return a stable numeric string for reports."""
    return f"{value:.12g}"


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    """Return unique values while preserving order."""
    unique_values: list[str] = []
    for value in values:
        if value not in unique_values:
            unique_values.append(value)
    return tuple(unique_values)
