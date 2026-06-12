"""Models for structural SMC caveat drilldown reports."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class StructuralSMCCaveatDrilldownPaths:
    """Filesystem paths written by a caveat drilldown report."""

    output_dir: Path
    detail_csv: Path
    report_md: Path


@dataclass(frozen=True)
class StructuralSMCCaveatDrilldownRow:
    """One target, fold, or run-level caveat needing review."""

    gate: str
    run_label: str
    caveat_type: str
    fold_name: str = ""
    target_id: str = ""
    requested_group_id: str = ""
    calibration_preferred_candidate: str = ""
    holdout_preferred_candidate: str = ""
    raw_residual_preferred_candidate: str = ""
    uncertainty_weighted_preferred_candidate: str = ""
    rmse_delta: str = ""
    chi_square_delta: str = ""
    diagnostic_value: str = ""
    next_action: str = ""
    source_path: str = ""

    def __post_init__(self) -> None:
        """Normalize required labels and reject empty review actions."""
        for field_name in ("gate", "run_label", "caveat_type", "next_action"):
            normalized = getattr(self, field_name).strip()
            if not normalized:
                raise ValueError(f"{field_name} must be non-empty")
            object.__setattr__(self, field_name, normalized)


@dataclass(frozen=True)
class StructuralSMCCaveatDrilldownReport:
    """A collection of caveat rows and their output paths."""

    rows: tuple[StructuralSMCCaveatDrilldownRow, ...]
    paths: StructuralSMCCaveatDrilldownPaths

    @property
    def row_count(self) -> int:
        """Return the number of caveat rows in the report."""
        return len(self.rows)

    def count_by_type(self, caveat_type: str) -> int:
        """Return the number of rows with a caveat type."""
        return sum(row.caveat_type == caveat_type for row in self.rows)

    @property
    def caveat_types(self) -> tuple[str, ...]:
        """Return caveat types in first-seen order."""
        types: list[str] = []
        for row in self.rows:
            if row.caveat_type not in types:
                types.append(row.caveat_type)
        return tuple(types)
