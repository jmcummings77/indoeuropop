"""Models for prioritized structural SMC caveat review queues."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class StructuralSMCCaveatPriorityPaths:
    """Filesystem paths written by a caveat priority report."""

    output_dir: Path
    priority_csv: Path
    report_md: Path


@dataclass(frozen=True)
class StructuralSMCCaveatPriorityRow:
    """One caveat row ranked for review disposition."""

    review_rank: int
    priority_band: str
    priority_score: float
    review_status: str
    disposition: str
    recommended_disposition: str
    rationale: str
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
        """Normalize labels and reject impossible priority records."""
        if self.review_rank < 1:
            raise ValueError("review_rank must be positive")
        if self.priority_score < 0:
            raise ValueError("priority_score must be non-negative")
        for field_name in (
            "priority_band",
            "review_status",
            "disposition",
            "recommended_disposition",
            "rationale",
            "gate",
            "run_label",
            "caveat_type",
            "next_action",
        ):
            normalized = getattr(self, field_name).strip()
            if not normalized:
                raise ValueError(f"{field_name} must be non-empty")
            object.__setattr__(self, field_name, normalized)

    @property
    def unresolved(self) -> bool:
        """Return whether this row still needs a reviewed disposition."""
        return self.review_status == "unresolved"

    @property
    def blocks_promotion(self) -> bool:
        """Return whether this row has a reviewed blocking disposition."""
        return self.review_status == "blocking"


@dataclass(frozen=True)
class StructuralSMCCaveatPriorityReport:
    """A ranked structural SMC caveat review queue."""

    rows: tuple[StructuralSMCCaveatPriorityRow, ...]
    paths: StructuralSMCCaveatPriorityPaths

    @property
    def row_count(self) -> int:
        """Return the number of ranked caveat rows."""
        return len(self.rows)

    @property
    def unresolved_count(self) -> int:
        """Return the number of rows still awaiting disposition."""
        return sum(row.unresolved for row in self.rows)

    @property
    def blocking_count(self) -> int:
        """Return the number of reviewed rows that block promotion."""
        return sum(row.blocks_promotion for row in self.rows)

    @property
    def reviewed_count(self) -> int:
        """Return the number of rows with a reviewed disposition."""
        return self.row_count - self.unresolved_count

    def top_rows(self, limit: int) -> tuple[StructuralSMCCaveatPriorityRow, ...]:
        """Return the first `limit` priority rows."""
        if limit < 1:
            raise ValueError("limit must be positive")
        return self.rows[:limit]
