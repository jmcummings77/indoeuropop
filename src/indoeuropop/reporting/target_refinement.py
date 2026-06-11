"""CSV and Markdown reports for validation-guided parameter refinement."""

from __future__ import annotations

import csv
from collections.abc import Iterable
from io import StringIO
from pathlib import Path

from indoeuropop.analysis.refinement import (
    ParameterRangeChange,
    TargetRefinementScenario,
)

REFINEMENT_SUMMARY_FIELDS = (
    "candidate",
    "kind",
    "metric",
    "fold_count",
    "mean_calibration_metric",
    "mean_validation_metric",
    "worst_validation_metric",
    "priority_values",
    "priority_mean_delta",
    "priority_improved",
    "protected_values",
    "protected_max_delta",
    "protected_degraded",
)

REFINEMENT_RANGE_FIELDS = (
    "candidate",
    "parameter",
    "original_low",
    "original_high",
    "original_width",
    "refined_low",
    "refined_high",
    "refined_width",
    "center",
    "scale",
)


def target_refinement_summary_rows(
    scenarios: Iterable[TargetRefinementScenario],
    *,
    tolerance: float = 0.0,
) -> tuple[dict[str, str], ...]:
    """Return scenario-level refinement diagnostics as CSV-ready rows."""
    scenario_tuple = _validated_scenarios(scenarios)
    baseline = _baseline_scenario(scenario_tuple)
    return tuple(
        _summary_row(scenario, baseline, tolerance=tolerance)
        for scenario in scenario_tuple
    )


def target_refinement_ranges_rows(
    scenarios: Iterable[TargetRefinementScenario],
) -> tuple[dict[str, str], ...]:
    """Return parameter-range comparison rows for refinement candidates."""
    return tuple(
        _range_row(change)
        for scenario in _validated_scenarios(scenarios)
        for change in scenario.candidate.range_changes
    )


def target_refinement_summary_to_csv(
    scenarios: Iterable[TargetRefinementScenario],
    *,
    tolerance: float = 0.0,
) -> str:
    """Return refinement summary rows serialized as CSV text."""
    return _rows_to_csv(
        REFINEMENT_SUMMARY_FIELDS,
        target_refinement_summary_rows(scenarios, tolerance=tolerance),
    )


def target_refinement_ranges_to_csv(
    scenarios: Iterable[TargetRefinementScenario],
) -> str:
    """Return refinement parameter-range rows serialized as CSV text."""
    return _rows_to_csv(
        REFINEMENT_RANGE_FIELDS,
        target_refinement_ranges_rows(scenarios),
    )


def write_target_refinement_summary_csv(
    scenarios: Iterable[TargetRefinementScenario],
    path: str | Path,
    *,
    tolerance: float = 0.0,
) -> Path:
    """Write refinement scenario summary rows to CSV."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        target_refinement_summary_to_csv(scenarios, tolerance=tolerance),
        encoding="utf-8",
    )
    return output_path


def write_target_refinement_ranges_csv(
    scenarios: Iterable[TargetRefinementScenario], path: str | Path
) -> Path:
    """Write refinement range comparison rows to CSV."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(target_refinement_ranges_to_csv(scenarios), encoding="utf-8")
    return output_path


def target_refinement_markdown(
    scenarios: Iterable[TargetRefinementScenario],
    *,
    tolerance: float = 0.0,
) -> str:
    """Return a Markdown report for validation-guided refinement."""
    scenario_tuple = _validated_scenarios(scenarios)
    baseline = _baseline_scenario(scenario_tuple)
    output = StringIO()
    output.write("# Validation-Guided Parameter Refinement\n\n")
    output.write("This report compares the baseline sweep grid with generated ")
    output.write("narrowed and expanded grids. It is a diagnostic, not inference.\n\n")
    output.write(f"- metric: `{baseline.metric}`\n")
    output.write(f"- fold_count: {len(baseline.folds)}\n")
    output.write(f"- priority_values: `{_joined(baseline.priority_values)}`\n")
    output.write(f"- protected_values: `{_joined(baseline.protected_values)}`\n\n")
    output.write("## Scenario Summary\n\n")
    output.write("| candidate | mean_validation | worst_validation | ")
    output.write("priority_delta | protected_delta | protected_degraded |\n")
    output.write("| --- | ---: | ---: | ---: | ---: | --- |\n")
    for scenario in scenario_tuple:
        priority_delta = _value_text(
            scenario.mean_delta_for(baseline, scenario.priority_values)
        )
        protected_degraded = _bool_text(
            scenario.protected_degraded(baseline, tolerance=tolerance)
        )
        output.write(
            f"| {scenario.name} | "
            f"{_value_text(scenario.mean_validation_metric())} | "
            f"{_value_text(scenario.worst_validation_metric())} | "
            f"{priority_delta} | "
            f"{_value_text(_protected_max_delta(scenario, baseline))} | "
            f"{protected_degraded} |\n"
        )
    output.write("\n## Parameter Ranges\n\n")
    output.write("| candidate | parameter | original | refined |\n")
    output.write("| --- | --- | ---: | ---: |\n")
    for scenario in scenario_tuple:
        for change in scenario.candidate.range_changes:
            original_range = (
                f"{_value_text(change.original_low)}.."
                f"{_value_text(change.original_high)}"
            )
            refined_range = (
                f"{_value_text(change.refined_low)}.."
                f"{_value_text(change.refined_high)}"
            )
            output.write(
                f"| {scenario.name} | {change.parameter} | "
                f"{original_range} | {refined_range} |\n"
            )
    return output.getvalue()


def write_target_refinement_markdown(
    scenarios: Iterable[TargetRefinementScenario],
    path: str | Path,
    *,
    tolerance: float = 0.0,
) -> Path:
    """Write a refinement Markdown report and return the path."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        target_refinement_markdown(scenarios, tolerance=tolerance),
        encoding="utf-8",
    )
    return output_path


def _summary_row(
    scenario: TargetRefinementScenario,
    baseline: TargetRefinementScenario,
    *,
    tolerance: float,
) -> dict[str, str]:
    """Return one scenario summary row."""
    return {
        "candidate": scenario.name,
        "kind": scenario.candidate.kind,
        "metric": scenario.metric,
        "fold_count": str(len(scenario.folds)),
        "mean_calibration_metric": _value_text(scenario.mean_calibration_metric()),
        "mean_validation_metric": _value_text(scenario.mean_validation_metric()),
        "worst_validation_metric": _value_text(scenario.worst_validation_metric()),
        "priority_values": _joined(scenario.priority_values),
        "priority_mean_delta": _value_text(
            scenario.mean_delta_for(baseline, scenario.priority_values)
        ),
        "priority_improved": _bool_text(
            scenario.priority_improved(baseline, tolerance=tolerance)
        ),
        "protected_values": _joined(scenario.protected_values),
        "protected_max_delta": _value_text(_protected_max_delta(scenario, baseline)),
        "protected_degraded": _bool_text(
            scenario.protected_degraded(baseline, tolerance=tolerance)
        ),
    }


def _range_row(change: ParameterRangeChange) -> dict[str, str]:
    """Return one parameter-range comparison row."""
    return {
        "candidate": change.candidate_name,
        "parameter": change.parameter,
        "original_low": _value_text(change.original_low),
        "original_high": _value_text(change.original_high),
        "original_width": _value_text(change.original_width),
        "refined_low": _value_text(change.refined_low),
        "refined_high": _value_text(change.refined_high),
        "refined_width": _value_text(change.refined_width),
        "center": _value_text(change.center),
        "scale": _value_text(change.scale),
    }


def _baseline_scenario(
    scenarios: tuple[TargetRefinementScenario, ...],
) -> TargetRefinementScenario:
    """Return the single baseline scenario."""
    matches = tuple(
        scenario for scenario in scenarios if scenario.candidate.kind == "baseline"
    )
    if len(matches) != 1:
        raise ValueError("scenarios must contain exactly one baseline candidate")
    return matches[0]


def _validated_scenarios(
    scenarios: Iterable[TargetRefinementScenario],
) -> tuple[TargetRefinementScenario, ...]:
    """Return a non-empty scenario tuple."""
    scenario_tuple = tuple(scenarios)
    if not scenario_tuple:
        raise ValueError("scenarios must contain at least one refinement scenario")
    return scenario_tuple


def _protected_max_delta(
    scenario: TargetRefinementScenario,
    baseline: TargetRefinementScenario,
) -> float:
    """Return the largest protected validation delta."""
    if not scenario.protected_values:
        return 0.0
    return max(
        scenario.delta_for(baseline, value) for value in scenario.protected_values
    )


def _rows_to_csv(fieldnames: tuple[str, ...], rows: Iterable[dict[str, str]]) -> str:
    """Return rows as CSV text with stable line endings."""
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def _joined(values: Iterable[str]) -> str:
    """Return pipe-delimited values for compact CSV and Markdown cells."""
    return "|".join(values)


def _bool_text(value: bool) -> str:
    """Return a stable lowercase boolean string."""
    return "true" if value else "false"


def _value_text(value: float) -> str:
    """Return a stable string representation for numeric values."""
    return f"{value:.12g}"
