"""CSV and Markdown reports for child-override sensitivity sweeps."""

from __future__ import annotations

import csv
from collections.abc import Iterable
from io import StringIO
from pathlib import Path

from indoeuropop.analysis.override_sensitivity import (
    OverrideSensitivityScenario,
    rank_override_sensitivity_scenarios,
)
from indoeuropop.analysis.validation import TargetValidationFold

OVERRIDE_SENSITIVITY_FIELDS = (
    "rank",
    "candidate",
    "region",
    "parameter",
    "base_value",
    "candidate_value",
    "metric",
    "fold_count",
    "mean_validation_metric",
    "worst_validation_metric",
    "priority_values",
    "priority_mean_delta",
    "protected_values",
    "protected_max_delta",
    "protected_degraded",
    "accepted",
)


def override_sensitivity_summary_rows(
    scenarios: Iterable[OverrideSensitivityScenario],
    baseline_folds: tuple[TargetValidationFold, ...],
    *,
    tolerance: float,
) -> tuple[dict[str, str], ...]:
    """Return ranked sensitivity scenarios as CSV-ready dictionaries."""
    ranked = rank_override_sensitivity_scenarios(
        scenarios,
        baseline_folds,
        tolerance=tolerance,
    )
    return tuple(
        _summary_row(rank, scenario, baseline_folds, tolerance=tolerance)
        for rank, scenario in enumerate(ranked, start=1)
    )


def override_sensitivity_summary_to_csv(
    scenarios: Iterable[OverrideSensitivityScenario],
    baseline_folds: tuple[TargetValidationFold, ...],
    *,
    tolerance: float,
) -> str:
    """Return ranked sensitivity scenario rows serialized as CSV text."""
    output = StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=OVERRIDE_SENSITIVITY_FIELDS,
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerows(
        override_sensitivity_summary_rows(
            scenarios,
            baseline_folds,
            tolerance=tolerance,
        )
    )
    return output.getvalue()


def write_override_sensitivity_summary_csv(
    scenarios: Iterable[OverrideSensitivityScenario],
    baseline_folds: tuple[TargetValidationFold, ...],
    path: str | Path,
    *,
    tolerance: float,
) -> Path:
    """Write ranked sensitivity summary rows and return the output path."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        override_sensitivity_summary_to_csv(
            scenarios,
            baseline_folds,
            tolerance=tolerance,
        ),
        encoding="utf-8",
    )
    return output_path


def override_sensitivity_markdown(
    scenarios: Iterable[OverrideSensitivityScenario],
    baseline_folds: tuple[TargetValidationFold, ...],
    *,
    tolerance: float,
) -> str:
    """Return a Markdown report for child-override sensitivity scenarios."""
    rows = override_sensitivity_summary_rows(
        scenarios,
        baseline_folds,
        tolerance=tolerance,
    )
    top_row = rows[0]
    output = StringIO()
    output.write("# Child-Override Sensitivity Sweep\n\n")
    output.write("This report ranks child-region override sensitivity candidates. ")
    output.write("Negative priority deltas indicate improved held-out fit; ")
    output.write("protected deltas are constrained by the configured tolerance.\n\n")
    output.write(f"- metric: `{top_row['metric']}`\n")
    output.write(f"- fold_count: {top_row['fold_count']}\n")
    output.write(f"- priority_values: `{top_row['priority_values']}`\n")
    output.write(f"- protected_values: `{top_row['protected_values']}`\n")
    output.write(f"- protected_tolerance: {_value_text(tolerance)}\n")
    output.write(f"- top_candidate: `{top_row['candidate']}`\n")
    output.write(f"- top_priority_delta: {top_row['priority_mean_delta']}\n")
    output.write(f"- top_protected_delta: {top_row['protected_max_delta']}\n\n")
    output.write("| rank | candidate | parameter | value | priority_delta | ")
    output.write("protected_delta | accepted |\n")
    output.write("| ---: | --- | --- | ---: | ---: | ---: | --- |\n")
    for row in rows:
        output.write(
            f"| {row['rank']} | {row['candidate']} | {row['parameter']} | "
            f"{row['candidate_value']} | {row['priority_mean_delta']} | "
            f"{row['protected_max_delta']} | {row['accepted']} |\n"
        )
    return output.getvalue()


def write_override_sensitivity_markdown(
    scenarios: Iterable[OverrideSensitivityScenario],
    baseline_folds: tuple[TargetValidationFold, ...],
    path: str | Path,
    *,
    tolerance: float,
) -> Path:
    """Write a child-override sensitivity Markdown report."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        override_sensitivity_markdown(
            scenarios,
            baseline_folds,
            tolerance=tolerance,
        ),
        encoding="utf-8",
    )
    return output_path


def _summary_row(
    rank: int,
    scenario: OverrideSensitivityScenario,
    baseline_folds: tuple[TargetValidationFold, ...],
    *,
    tolerance: float,
) -> dict[str, str]:
    """Return one ranked sensitivity summary row."""
    candidate = scenario.candidate
    return {
        "rank": str(rank),
        "candidate": candidate.name,
        "region": candidate.region,
        "parameter": candidate.parameter,
        "base_value": _value_text(candidate.base_value),
        "candidate_value": _value_text(candidate.candidate_value),
        "metric": scenario.metric,
        "fold_count": str(len(scenario.folds)),
        "mean_validation_metric": _value_text(scenario.mean_validation_metric()),
        "worst_validation_metric": _value_text(scenario.worst_validation_metric()),
        "priority_values": _joined(scenario.priority_values),
        "priority_mean_delta": _value_text(
            scenario.priority_mean_delta(baseline_folds)
        ),
        "protected_values": _joined(scenario.protected_values),
        "protected_max_delta": _value_text(
            scenario.protected_max_delta(baseline_folds)
        ),
        "protected_degraded": _bool_text(
            scenario.protected_degraded(baseline_folds, tolerance=tolerance)
        ),
        "accepted": _bool_text(scenario.accepted(baseline_folds, tolerance=tolerance)),
    }


def _joined(values: Iterable[str]) -> str:
    """Return values joined by a report-friendly delimiter."""
    return "|".join(values)


def _bool_text(value: bool) -> str:
    """Return a lower-case boolean string."""
    return "true" if value else "false"


def _value_text(value: float) -> str:
    """Return a stable numeric string for reports."""
    return f"{value:.12g}"
