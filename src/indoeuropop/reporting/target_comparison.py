"""CSV reporting helpers for target-vs-simulation comparisons."""

from __future__ import annotations

import csv
from collections.abc import Iterable
from io import StringIO
from pathlib import Path

from indoeuropop.data.targets import TargetComparison

TARGET_COMPARISON_FIELDS = (
    "target_index",
    "status",
    "region",
    "source",
    "time_bce",
    "observed_mean",
    "uncertainty",
    "predicted",
    "residual",
    "z_score",
    "citation_key",
    "citation",
    "note",
)


def target_comparison_rows(
    comparisons: Iterable[TargetComparison],
) -> tuple[dict[str, str], ...]:
    """Return target comparisons as string-only CSV rows."""
    comparison_tuple = _validated_comparisons(comparisons)
    return tuple(
        _target_comparison_row(index, comparison)
        for index, comparison in enumerate(comparison_tuple, start=1)
    )


def target_comparisons_to_csv(comparisons: Iterable[TargetComparison]) -> str:
    """Return target comparisons serialized as CSV text."""
    rows = target_comparison_rows(comparisons)
    output = StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=TARGET_COMPARISON_FIELDS,
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def write_target_comparisons_csv(
    comparisons: Iterable[TargetComparison], path: str | Path
) -> Path:
    """Write target-comparison residuals to a CSV file and return the path."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(target_comparisons_to_csv(comparisons), encoding="utf-8")
    return output_path


def _validated_comparisons(
    comparisons: Iterable[TargetComparison],
) -> tuple[TargetComparison, ...]:
    """Return a non-empty comparison tuple."""
    comparison_tuple = tuple(comparisons)
    if not comparison_tuple:
        raise ValueError("comparisons must contain at least one target comparison")
    return comparison_tuple


def _target_comparison_row(index: int, comparison: TargetComparison) -> dict[str, str]:
    """Return one target-comparison CSV row."""
    observation = comparison.observation
    return {
        "target_index": str(index),
        "status": observation.status,
        "region": observation.region,
        "source": observation.source,
        "time_bce": _value_text(observation.time_bce),
        "observed_mean": _value_text(observation.mean),
        "uncertainty": _value_text(observation.uncertainty),
        "predicted": _value_text(comparison.predicted),
        "residual": _value_text(comparison.residual),
        "z_score": _value_text(comparison.z_score),
        "citation_key": observation.citation_key,
        "citation": observation.citation,
        "note": observation.note,
    }


def _value_text(value: float) -> str:
    """Return a stable string representation for numeric values."""
    return f"{value:.12g}"
