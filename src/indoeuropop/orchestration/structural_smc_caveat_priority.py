"""Prioritize structural SMC caveats for disposition review."""

from __future__ import annotations

import csv
from pathlib import Path

from indoeuropop.data.structural_smc_caveat_dispositions import (
    STRUCTURAL_SMC_BLOCKING_CAVEAT_DISPOSITIONS,
    STRUCTURAL_SMC_CAVEAT_KEY_COLUMNS,
    StructuralSMCCaveatDispositionRecord,
    validate_structural_smc_caveat_dispositions,
)
from indoeuropop.orchestration.structural_smc_caveat_priority_models import (
    StructuralSMCCaveatPriorityPaths,
    StructuralSMCCaveatPriorityReport,
    StructuralSMCCaveatPriorityRow,
)
from indoeuropop.reporting.structural_smc_caveat_priority import (
    STRUCTURAL_SMC_CAVEAT_PRIORITY_SOURCE_FIELDS,
    write_structural_smc_caveat_priority_csv,
    write_structural_smc_caveat_priority_markdown,
)

BASE_CAVEAT_PRIORITY = {
    "missing_override_regions": 300.0,
    "skipped_folds": 280.0,
    "excluded_target": 240.0,
    "preference_disagreement": 220.0,
    "uncertainty_tie": 200.0,
}
BASE_GATE_PRIORITY = {
    "source_model": 60.0,
    "fit_metric": 40.0,
    "target_fragility": 30.0,
}
BASE_DISPOSITION_PRIORITY = {
    "blocks_promotion": 1000.0,
    "requires_qpadm_rerun": 950.0,
    "configuration_gap": 940.0,
    "undecided": 500.0,
    "accepted_caveat": 50.0,
    "not_applicable": 10.0,
}


def structural_smc_caveat_priority_paths_from_dir(
    output_dir: str | Path,
) -> StructuralSMCCaveatPriorityPaths:
    """Return conventional output paths for caveat priority artifacts."""
    root = Path(output_dir)
    return StructuralSMCCaveatPriorityPaths(
        output_dir=root,
        priority_csv=root / "structural-smc-caveat-priorities.csv",
        report_md=root / "structural-smc-caveat-priorities.md",
    )


def run_structural_smc_caveat_prioritization(
    *,
    caveat_drilldown_csv: str | Path,
    caveat_dispositions_csv: str | Path | None = None,
    paths: StructuralSMCCaveatPriorityPaths | None = None,
) -> StructuralSMCCaveatPriorityReport:
    """Rank caveat drilldown rows by review actionability and impact."""
    output_paths = (
        structural_smc_caveat_priority_paths_from_dir(
            "structural-smc-caveat-priorities"
        )
        if paths is None
        else paths
    )
    drilldown_rows = _read_drilldown_rows(caveat_drilldown_csv)
    disposition_by_key = _disposition_records_by_key(
        caveat_drilldown_csv, caveat_dispositions_csv
    )
    ranked_inputs = sorted(
        (
            _rankable_row(index, row, disposition_by_key.get(_key(row)))
            for index, row in enumerate(drilldown_rows)
        ),
        key=lambda item: (-item[0], item[1]),
    )
    priority_rows = tuple(
        _priority_row(rank, row, disposition, score)
        for rank, (score, _index, row, disposition) in enumerate(ranked_inputs, start=1)
    )
    report = StructuralSMCCaveatPriorityReport(rows=priority_rows, paths=output_paths)
    write_structural_smc_caveat_priority_csv(report, output_paths.priority_csv)
    write_structural_smc_caveat_priority_markdown(report, output_paths.report_md)
    return report


def _disposition_records_by_key(
    drilldown_csv: str | Path,
    dispositions_csv: str | Path | None,
) -> dict[tuple[str, ...], StructuralSMCCaveatDispositionRecord]:
    """Return reviewed disposition records keyed by caveat identity."""
    if dispositions_csv is None:
        return {}
    validation = validate_structural_smc_caveat_dispositions(
        drilldown_csv=drilldown_csv,
        dispositions_csv=dispositions_csv,
    )
    if validation.issues:
        raise ValueError(
            "caveat disposition file has structural issues: "
            + "; ".join(validation.issues)
        )
    return {record.key: record for record in validation.dispositions.records}


def _rankable_row(
    index: int,
    row: dict[str, str],
    disposition: StructuralSMCCaveatDispositionRecord | None,
) -> tuple[float, int, dict[str, str], StructuralSMCCaveatDispositionRecord | None]:
    """Return sortable row inputs with their priority score."""
    return _priority_score(row, disposition), index, row, disposition


def _priority_row(
    rank: int,
    row: dict[str, str],
    disposition: StructuralSMCCaveatDispositionRecord | None,
    score: float,
) -> StructuralSMCCaveatPriorityRow:
    """Build a ranked priority row."""
    disposition_value = "undecided" if disposition is None else disposition.disposition
    return StructuralSMCCaveatPriorityRow(
        review_rank=rank,
        priority_band=_priority_band(score),
        priority_score=score,
        review_status=_review_status(disposition_value),
        disposition=disposition_value,
        recommended_disposition=_recommended_disposition(row),
        rationale=_rationale(row, disposition_value),
        **{field: row[field] for field in STRUCTURAL_SMC_CAVEAT_PRIORITY_SOURCE_FIELDS},
    )


def _priority_score(
    row: dict[str, str],
    disposition: StructuralSMCCaveatDispositionRecord | None,
) -> float:
    """Return an explainable actionability score for one caveat row."""
    disposition_value = "undecided" if disposition is None else disposition.disposition
    score = BASE_DISPOSITION_PRIORITY.get(disposition_value, 0.0)
    score += BASE_CAVEAT_PRIORITY.get(row["caveat_type"], 100.0)
    score += BASE_GATE_PRIORITY.get(row["gate"], 0.0)
    score += _numeric_signal(row)
    score += _flag_signal(row["diagnostic_value"])
    return round(score, 6)


def _numeric_signal(row: dict[str, str]) -> float:
    """Return score contribution from numeric diagnostics."""
    signals = (
        _float_signal(row["rmse_delta"], multiplier=100.0),
        _float_signal(row["chi_square_delta"], multiplier=100.0),
        _float_signal(row["diagnostic_value"], multiplier=20.0),
    )
    return sum(signals)


def _float_signal(value: str, *, multiplier: float) -> float:
    """Parse one optional numeric cell into a priority contribution."""
    try:
        return abs(float(value)) * multiplier if value else 0.0
    except ValueError:
        return 0.0


def _flag_signal(diagnostic_value: str) -> float:
    """Return extra priority for target-curation flags."""
    flags = set(diagnostic_value.split(";"))
    score = 0.0
    if "sample_flag:critical" in flags:
        score += 80.0
    if "sample_flag:high_se" in flags:
        score += 30.0
    if "repeated_identical_estimates" in flags:
        score += 20.0
    return score


def _priority_band(score: float) -> str:
    """Return a compact priority band label."""
    if score >= 900:
        return "critical"
    if score >= 750:
        return "high"
    if score >= 550:
        return "medium"
    return "low"


def _review_status(disposition: str) -> str:
    """Return status from a disposition cell."""
    if disposition == "undecided":
        return "unresolved"
    if disposition in STRUCTURAL_SMC_BLOCKING_CAVEAT_DISPOSITIONS:
        return "blocking"
    return "reviewed"


def _recommended_disposition(row: dict[str, str]) -> str:
    """Return a conservative suggested disposition for reviewer triage."""
    caveat_type = row["caveat_type"]
    if caveat_type == "missing_override_regions":
        return "configuration_gap"
    if caveat_type in {"preference_disagreement", "skipped_folds"}:
        return "requires_qpadm_rerun"
    if (
        caveat_type == "excluded_target"
        and "sample_flag:critical" in row["diagnostic_value"]
    ):
        return "requires_qpadm_rerun"
    if caveat_type == "excluded_target":
        return "accepted_caveat"
    return "accepted_caveat"


def _rationale(row: dict[str, str], disposition: str) -> str:
    """Return a short human-readable reason for the priority score."""
    reasons = [_review_status(disposition), row["gate"], row["caveat_type"]]
    if row["rmse_delta"]:
        reasons.append(f"rmse_delta={row['rmse_delta']}")
    if row["chi_square_delta"]:
        reasons.append(f"chi_square_delta={row['chi_square_delta']}")
    if row["diagnostic_value"]:
        reasons.append(f"diagnostic={row['diagnostic_value']}")
    return "; ".join(reasons)


def _read_drilldown_rows(path: str | Path) -> tuple[dict[str, str], ...]:
    """Read caveat drilldown rows with required prioritization fields."""
    input_path = Path(path)
    with input_path.open(newline="", encoding="utf-8") as input_file:
        reader = csv.DictReader(input_file)
        if reader.fieldnames is None:
            raise ValueError(f"{input_path} must include a header row")
        missing = set(STRUCTURAL_SMC_CAVEAT_PRIORITY_SOURCE_FIELDS).difference(
            reader.fieldnames
        )
        if missing:
            raise ValueError(
                f"{input_path} missing columns: " + ", ".join(sorted(missing))
            )
        rows = [{key: value or "" for key, value in row.items()} for row in reader]
    if not rows:
        raise ValueError(f"{input_path} must contain at least one data row")
    return tuple(rows)


def _key(row: dict[str, str]) -> tuple[str, ...]:
    """Return the disposition key for a drilldown row."""
    return tuple(row[field] for field in STRUCTURAL_SMC_CAVEAT_KEY_COLUMNS)
