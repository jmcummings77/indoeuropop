"""Reports for target-fragility sensitivity gates."""

from __future__ import annotations

import csv
from collections.abc import Iterable
from io import StringIO
from pathlib import Path

from indoeuropop.orchestration.target_fragility_models import (
    TargetFragilityDecision,
    TargetFragilityGateResult,
)

TARGET_FRAGILITY_DECISION_FIELDS = (
    "target_id",
    "requested_group_id",
    "excluded",
    "reasons",
    "sample_count",
    "available_estimate_count",
    "unique_estimate_count",
    "sample_flags",
)


def target_fragility_decision_rows(
    decisions: Iterable[TargetFragilityDecision],
) -> tuple[dict[str, str], ...]:
    """Return target-fragility decisions as CSV-ready rows."""
    return tuple(_decision_row(decision) for decision in decisions)


def target_fragility_decisions_to_csv(
    decisions: Iterable[TargetFragilityDecision],
) -> str:
    """Return target-fragility decisions serialized as CSV text."""
    output = StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=TARGET_FRAGILITY_DECISION_FIELDS,
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerows(target_fragility_decision_rows(decisions))
    return output.getvalue()


def write_target_fragility_decisions_csv(
    decisions: Iterable[TargetFragilityDecision],
    path: str | Path,
) -> Path:
    """Write target-fragility decisions to CSV and return the path."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        target_fragility_decisions_to_csv(decisions),
        encoding="utf-8",
    )
    return output_path


def target_fragility_gate_markdown(result: TargetFragilityGateResult) -> str:
    """Return a Markdown report for a target-fragility sensitivity gate."""
    output = StringIO()
    output.write("# Target-Fragility Sensitivity Gate\n\n")
    output.write(
        "This diagnostic removes targets with sample-level fragility evidence, "
        "then reruns the structural SMC validation folds that still have both "
        "calibration and holdout observations. It is a robustness screen, not "
        "a final curation decision.\n\n"
    )
    output.write("## Summary\n\n")
    output.write(f"- original_target_count: {result.original_target_count}\n")
    output.write(f"- retained_target_count: {result.filtered_target_count}\n")
    output.write(f"- excluded_target_count: {result.excluded_target_count}\n")
    output.write(f"- validation_fold_count: {len(result.validation_result.folds)}\n")
    output.write(f"- skipped_fold_count: {result.skipped_fold_count}\n")
    output.write(
        "- preference_disagreement_count: "
        f"{result.validation_result.preference_disagreement_count}\n\n"
    )
    output.write(_excluded_targets_table(result.decisions))
    output.write(_skipped_folds_section(result))
    output.write("## Output Files\n\n")
    output.write(f"- filtered_targets_csv: `{result.paths.filtered_targets_csv}`\n")
    output.write(f"- decisions_csv: `{result.paths.decisions_csv}`\n")
    output.write(
        f"- validation_summary_csv: `{result.validation_result.summary_csv_path}`\n"
    )
    output.write(
        f"- validation_report_md: `{result.validation_result.report_md_path}`\n"
    )
    return output.getvalue()


def write_target_fragility_gate_markdown(
    result: TargetFragilityGateResult,
    path: str | Path,
) -> Path:
    """Write a target-fragility Markdown report and return the path."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(target_fragility_gate_markdown(result), encoding="utf-8")
    return output_path


def _decision_row(decision: TargetFragilityDecision) -> dict[str, str]:
    """Return one target-fragility decision as string-only fields."""
    return {
        "target_id": decision.target_id,
        "requested_group_id": decision.requested_group_id,
        "excluded": str(decision.excluded).lower(),
        "reasons": decision.reason_text,
        "sample_count": str(decision.sample_count),
        "available_estimate_count": str(decision.available_estimate_count),
        "unique_estimate_count": str(decision.unique_estimate_count),
        "sample_flags": decision.sample_flag_text,
    }


def _excluded_targets_table(
    decisions: tuple[TargetFragilityDecision, ...],
) -> str:
    """Return a compact Markdown table of excluded target IDs."""
    excluded = tuple(decision for decision in decisions if decision.excluded)
    if not excluded:
        return "## Excluded Targets\n\nNo targets were excluded.\n\n"
    output = StringIO()
    output.write("## Excluded Targets\n\n")
    output.write("| Target ID | Requested group | Samples | Reasons |\n")
    output.write("| --- | --- | ---: | --- |\n")
    for decision in excluded:
        output.write(
            f"| {decision.target_id} | {decision.requested_group_id} | "
            f"{decision.sample_count} | {decision.reason_text} |\n"
        )
    output.write("\n")
    return output.getvalue()


def _skipped_folds_section(result: TargetFragilityGateResult) -> str:
    """Return a Markdown list of validation folds dropped after filtering."""
    if not result.skipped_folds:
        return "## Skipped Folds\n\nNo folds were skipped after filtering.\n\n"
    output = StringIO()
    output.write("## Skipped Folds\n\n")
    for fold in result.skipped_folds:
        output.write(f"- {fold.name}: `{fold.holdout_field}={fold.holdout_value}`\n")
    output.write("\n")
    return output.getvalue()
