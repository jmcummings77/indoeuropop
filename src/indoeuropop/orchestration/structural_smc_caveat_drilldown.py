"""Build fold-level structural SMC caveat drilldown reports."""

from __future__ import annotations

import csv
from pathlib import Path

from indoeuropop.orchestration.structural_smc_caveat_drilldown_models import (
    StructuralSMCCaveatDrilldownPaths,
    StructuralSMCCaveatDrilldownReport,
    StructuralSMCCaveatDrilldownRow,
)
from indoeuropop.reporting.structural_smc_caveat_drilldown import (
    write_structural_smc_caveat_drilldown_csv,
    write_structural_smc_caveat_drilldown_markdown,
)

TARGET_FRAGILITY_DETAIL_COLUMNS = frozenset(
    ("target_id", "requested_group_id", "excluded", "reasons")
)
FIT_METRIC_RUN_COLUMNS = frozenset(
    ("fit_metric", "validation_summary_csv", "uncertainty_csv")
)
SOURCE_MODEL_RUN_COLUMNS = frozenset(
    (
        "source_model",
        "validation_summary_csv",
        "uncertainty_csv",
        "missing_override_region_count",
        "skipped_fold_count",
    )
)
VALIDATION_DETAIL_COLUMNS = frozenset(
    (
        "fold_name",
        "calibration_preferred_candidate",
        "holdout_preferred_candidate",
        "preference_disagreement",
        "holdout_child_minus_structured_pulse_rmse_delta",
    )
)
UNCERTAINTY_DETAIL_COLUMNS = frozenset(
    (
        "fold_name",
        "target_id",
        "requested_group_id",
        "raw_residual_preferred_candidate",
        "uncertainty_weighted_preferred_candidate",
        "child_minus_structured_pulse_chi_square_delta",
    )
)


def structural_smc_caveat_drilldown_paths_from_dir(
    output_dir: str | Path,
) -> StructuralSMCCaveatDrilldownPaths:
    """Return conventional output paths for caveat drilldown artifacts."""
    root = Path(output_dir)
    return StructuralSMCCaveatDrilldownPaths(
        output_dir=root,
        detail_csv=root / "structural-smc-caveat-drilldown.csv",
        report_md=root / "structural-smc-caveat-drilldown.md",
    )


def run_structural_smc_caveat_drilldown(
    *,
    target_fragility_decisions_csv: str | Path,
    fit_metric_summary_csv: str | Path,
    source_model_summary_csv: str | Path,
    paths: StructuralSMCCaveatDrilldownPaths | None = None,
) -> StructuralSMCCaveatDrilldownReport:
    """Join robustness caveats to their fold and target evidence rows."""
    output_paths = (
        structural_smc_caveat_drilldown_paths_from_dir(
            "structural-smc-caveat-drilldown"
        )
        if paths is None
        else paths
    )
    rows = (
        *_target_fragility_rows(target_fragility_decisions_csv),
        *_fit_metric_rows(fit_metric_summary_csv),
        *_source_model_rows(source_model_summary_csv),
    )
    report = StructuralSMCCaveatDrilldownReport(rows=rows, paths=output_paths)
    write_structural_smc_caveat_drilldown_csv(report, output_paths.detail_csv)
    write_structural_smc_caveat_drilldown_markdown(report, output_paths.report_md)
    return report


def _target_fragility_rows(
    decisions_csv: str | Path,
) -> tuple[StructuralSMCCaveatDrilldownRow, ...]:
    """Return target-level rows for excluded fragile targets."""
    source_path = Path(decisions_csv)
    rows: list[StructuralSMCCaveatDrilldownRow] = []
    for row in _read_rows(source_path, TARGET_FRAGILITY_DETAIL_COLUMNS):
        if _bool(row["excluded"]):
            rows.append(
                StructuralSMCCaveatDrilldownRow(
                    gate="target_fragility",
                    run_label="target_fragility",
                    caveat_type="excluded_target",
                    target_id=row["target_id"],
                    requested_group_id=row["requested_group_id"],
                    diagnostic_value=row["reasons"],
                    next_action=(
                        "Review target curation and qpAdm estimates before "
                        "reintroducing this target."
                    ),
                    source_path=str(source_path),
                )
            )
    return tuple(rows)


def _fit_metric_rows(
    summary_csv: str | Path,
) -> tuple[StructuralSMCCaveatDrilldownRow, ...]:
    """Return drilldown rows for each fit-metric sensitivity run."""
    rows: list[StructuralSMCCaveatDrilldownRow] = []
    for run in _read_rows(summary_csv, FIT_METRIC_RUN_COLUMNS):
        run_label = run["fit_metric"]
        rows.extend(
            _preference_disagreement_rows(
                gate="fit_metric",
                run_label=run_label,
                validation_summary_csv=run["validation_summary_csv"],
            )
        )
        rows.extend(
            _uncertainty_tie_rows(
                gate="fit_metric",
                run_label=run_label,
                uncertainty_csv=run["uncertainty_csv"],
            )
        )
    return tuple(rows)


def _source_model_rows(
    summary_csv: str | Path,
) -> tuple[StructuralSMCCaveatDrilldownRow, ...]:
    """Return drilldown rows for each source-model sensitivity run."""
    rows: list[StructuralSMCCaveatDrilldownRow] = []
    for run in _read_rows(summary_csv, SOURCE_MODEL_RUN_COLUMNS):
        run_label = run["source_model"]
        rows.extend(
            _preference_disagreement_rows(
                gate="source_model",
                run_label=run_label,
                validation_summary_csv=run["validation_summary_csv"],
            )
        )
        rows.extend(
            _uncertainty_tie_rows(
                gate="source_model",
                run_label=run_label,
                uncertainty_csv=run["uncertainty_csv"],
            )
        )
        rows.extend(_run_level_source_model_rows(run))
    return tuple(rows)


def _preference_disagreement_rows(
    *,
    gate: str,
    run_label: str,
    validation_summary_csv: str,
) -> tuple[StructuralSMCCaveatDrilldownRow, ...]:
    """Return fold rows where calibration and holdout preferences disagree."""
    source_path = Path(validation_summary_csv)
    rows: list[StructuralSMCCaveatDrilldownRow] = []
    for row in _read_rows(source_path, VALIDATION_DETAIL_COLUMNS):
        if _bool(row["preference_disagreement"]):
            rows.append(
                StructuralSMCCaveatDrilldownRow(
                    gate=gate,
                    run_label=run_label,
                    caveat_type="preference_disagreement",
                    fold_name=row["fold_name"],
                    calibration_preferred_candidate=(
                        row["calibration_preferred_candidate"]
                    ),
                    holdout_preferred_candidate=row["holdout_preferred_candidate"],
                    rmse_delta=row["holdout_child_minus_structured_pulse_rmse_delta"],
                    next_action=(
                        "Inspect held-out targets and require gate stability "
                        "before treating this fold as structural evidence."
                    ),
                    source_path=str(source_path),
                )
            )
    return tuple(rows)


def _uncertainty_tie_rows(
    *,
    gate: str,
    run_label: str,
    uncertainty_csv: str,
) -> tuple[StructuralSMCCaveatDrilldownRow, ...]:
    """Return target rows where uncertainty erases material preference."""
    source_path = Path(uncertainty_csv)
    rows: list[StructuralSMCCaveatDrilldownRow] = []
    for row in _read_rows(source_path, UNCERTAINTY_DETAIL_COLUMNS):
        if row["uncertainty_weighted_preferred_candidate"] == "uncertainty_tie":
            rows.append(
                StructuralSMCCaveatDrilldownRow(
                    gate=gate,
                    run_label=run_label,
                    caveat_type="uncertainty_tie",
                    fold_name=row["fold_name"],
                    target_id=row["target_id"],
                    requested_group_id=row["requested_group_id"],
                    raw_residual_preferred_candidate=(
                        row["raw_residual_preferred_candidate"]
                    ),
                    uncertainty_weighted_preferred_candidate=(
                        row["uncertainty_weighted_preferred_candidate"]
                    ),
                    chi_square_delta=row[
                        "child_minus_structured_pulse_chi_square_delta"
                    ],
                    next_action=(
                        "Treat as weak evidence; improve target uncertainty or "
                        "source modeling before using the raw residual preference."
                    ),
                    source_path=str(source_path),
                )
            )
    return tuple(rows)


def _run_level_source_model_rows(
    run: dict[str, str],
) -> tuple[StructuralSMCCaveatDrilldownRow, ...]:
    """Return source-model caveats that are only available as run-level counts."""
    rows: list[StructuralSMCCaveatDrilldownRow] = []
    for field_name, caveat_type, next_action in (
        (
            "missing_override_region_count",
            "missing_override_regions",
            "Decide whether absent child regions are expected alignment losses "
            "or configuration gaps.",
        ),
        (
            "skipped_fold_count",
            "skipped_folds",
            "Rerun with enough retained targets or document why the fold is "
            "inapplicable.",
        ),
    ):
        count = _int_cell(run[field_name], field_name)
        if count:
            rows.append(
                StructuralSMCCaveatDrilldownRow(
                    gate="source_model",
                    run_label=run["source_model"],
                    caveat_type=caveat_type,
                    diagnostic_value=str(count),
                    next_action=next_action,
                )
            )
    return tuple(rows)


def _read_rows(
    path: str | Path, required_columns: frozenset[str]
) -> list[dict[str, str]]:
    """Read a CSV file and require named columns plus at least one row."""
    input_path = Path(path)
    with input_path.open(newline="", encoding="utf-8") as input_file:
        reader = csv.DictReader(input_file)
        if reader.fieldnames is None:
            raise ValueError(f"{input_path} must include a header row")
        missing = required_columns.difference(reader.fieldnames)
        if missing:
            raise ValueError(
                f"{input_path} missing columns: " + ", ".join(sorted(missing))
            )
        rows = [{key: value or "" for key, value in row.items()} for row in reader]
    if not rows:
        raise ValueError(f"{input_path} must contain at least one data row")
    return rows


def _bool(value: str) -> bool:
    """Parse a lowercase CSV boolean cell."""
    normalized = value.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise ValueError("boolean cells must be true or false")


def _int_cell(value: str, field_name: str) -> int:
    """Parse a non-negative integer cell."""
    try:
        parsed = int(value)
    except ValueError as error:
        raise ValueError(f"{field_name} must be an integer") from error
    if parsed < 0:
        raise ValueError(f"{field_name} must be non-negative")
    return parsed
