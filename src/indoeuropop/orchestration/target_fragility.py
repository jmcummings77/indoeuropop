"""Target-fragility sensitivity workflows for structural validation."""

from __future__ import annotations

import csv
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from indoeuropop.analysis.abc_smc import ABCSMCOptions
from indoeuropop.analysis.structural_head_to_head import StructuredPulseCandidate
from indoeuropop.data.target_notes import target_note_metadata
from indoeuropop.data.targets import (
    TargetDataset,
    TargetObservation,
    write_target_dataset_csv,
)
from indoeuropop.orchestration.child_region_overrides import ChildRegionOverrideSet
from indoeuropop.orchestration.structural_smc_validation import (
    run_structural_smc_multifold_validation_workflow,
)
from indoeuropop.orchestration.structural_smc_validation_models import (
    StructuralSMCValidationFoldSpec,
)
from indoeuropop.orchestration.structural_smc_validation_outputs import (
    structural_smc_validation_output_paths_from_dir,
)
from indoeuropop.orchestration.sweeps import SweepSpec
from indoeuropop.orchestration.target_fragility_models import (
    DEFAULT_REPEATED_ESTIMATE_TOLERANCE,
    DEFAULT_TARGET_FRAGILITY_FLAGS,
    TargetFragilityDecision,
    TargetFragilityGatePaths,
    TargetFragilityGateResult,
    repeated_estimates,
)
from indoeuropop.reporting.target_fragility import (
    write_target_fragility_decisions_csv,
    write_target_fragility_gate_markdown,
)

REQUIRED_TARGET_FRAGILITY_AUDIT_COLUMNS = frozenset(
    ("target_id", "requested_group_id", "estimate", "sample_flags")
)


def target_fragility_gate_paths_from_dir(
    output_dir: str | Path,
) -> TargetFragilityGatePaths:
    """Return conventional output paths for a target-fragility gate."""
    root = Path(output_dir)
    return TargetFragilityGatePaths(
        output_dir=root,
        filtered_targets_csv=root / "filtered-targets.csv",
        decisions_csv=root / "target-fragility-decisions.csv",
        report_md=root / "target-fragility-gate.md",
        validation_output_dir=root / "validation",
    )


def load_target_fragility_decisions(
    sample_audit_csv: str | Path,
    *,
    excluded_flags: Iterable[str] = DEFAULT_TARGET_FRAGILITY_FLAGS,
    exclude_repeated_estimates: bool = True,
    repeated_estimate_tolerance: float = DEFAULT_REPEATED_ESTIMATE_TOLERANCE,
) -> tuple[TargetFragilityDecision, ...]:
    """Load target-level fragility decisions from a sample-audit CSV."""
    aggregates = _load_audit_aggregates(sample_audit_csv)
    return tuple(
        aggregate.decision(
            excluded_flags=excluded_flags,
            exclude_repeated_estimates=exclude_repeated_estimates,
            repeated_estimate_tolerance=repeated_estimate_tolerance,
        )
        for aggregate in aggregates
    )


def filter_targets_by_fragility(
    targets: TargetDataset,
    decisions: Iterable[TargetFragilityDecision],
) -> TargetDataset:
    """Return targets excluding observations whose `target_id` was fragile."""
    excluded_ids = {decision.target_id for decision in decisions if decision.excluded}
    filtered = tuple(
        observation
        for observation in targets.observations
        if target_note_metadata(observation.note).get("target_id") not in excluded_ids
    )
    return TargetDataset.from_rows(filtered).require_observations()


def usable_structural_smc_validation_folds(
    targets: TargetDataset,
    folds: Iterable[StructuralSMCValidationFoldSpec],
) -> tuple[StructuralSMCValidationFoldSpec, ...]:
    """Return folds that keep non-empty calibration and holdout target sets."""
    usable: list[StructuralSMCValidationFoldSpec] = []
    for fold in folds:
        if _fold_has_usable_split(targets, fold):
            usable.append(fold)
    return tuple(usable)


def run_structural_smc_target_fragility_gate(
    spec: SweepSpec,
    targets: TargetDataset,
    overrides: ChildRegionOverrideSet,
    structured_pulse_candidate: StructuredPulseCandidate,
    *,
    sample_audit_csv: str | Path,
    folds: Iterable[StructuralSMCValidationFoldSpec],
    child_candidate_name: str = "child-region-candidate",
    options: ABCSMCOptions | None = None,
    paths: TargetFragilityGatePaths | None = None,
    interval_probability: float = 0.9,
    excluded_flags: Iterable[str] = DEFAULT_TARGET_FRAGILITY_FLAGS,
    exclude_repeated_estimates: bool = True,
    repeated_estimate_tolerance: float = DEFAULT_REPEATED_ESTIMATE_TOLERANCE,
    config_path: Path | None = None,
    child_region_overrides_path: Path | None = None,
    command: str = "programmatic-validate-structured-smc-target-fragility",
) -> TargetFragilityGateResult:
    """Filter fragile targets and rerun usable structural SMC folds."""
    output_paths = (
        target_fragility_gate_paths_from_dir("target-fragility-gate")
        if paths is None
        else paths
    )
    decisions = load_target_fragility_decisions(
        sample_audit_csv,
        excluded_flags=excluded_flags,
        exclude_repeated_estimates=exclude_repeated_estimates,
        repeated_estimate_tolerance=repeated_estimate_tolerance,
    )
    filtered_targets = filter_targets_by_fragility(targets, decisions)
    write_target_dataset_csv(filtered_targets, output_paths.filtered_targets_csv)
    write_target_fragility_decisions_csv(decisions, output_paths.decisions_csv)
    original_folds = tuple(folds)
    usable_folds = usable_structural_smc_validation_folds(
        filtered_targets, original_folds
    )
    skipped_folds = tuple(fold for fold in original_folds if fold not in usable_folds)
    if not usable_folds:
        raise ValueError("target-fragility gate left no usable validation folds")
    validation_result = run_structural_smc_multifold_validation_workflow(
        spec,
        filtered_targets,
        overrides,
        structured_pulse_candidate,
        folds=usable_folds,
        child_candidate_name=child_candidate_name,
        options=options,
        paths=structural_smc_validation_output_paths_from_dir(
            output_paths.validation_output_dir,
            config=config_path,
            targets=output_paths.filtered_targets_csv,
            child_region_overrides=child_region_overrides_path,
        ),
        interval_probability=interval_probability,
        command=command,
        manifest_metadata={
            "target_fragility_excluded_target_count": str(
                sum(decision.excluded for decision in decisions)
            ),
            "target_fragility_skipped_fold_count": str(len(skipped_folds)),
        },
    )
    result = TargetFragilityGateResult(
        decisions=decisions,
        original_targets=targets,
        filtered_targets=filtered_targets,
        skipped_folds=skipped_folds,
        validation_result=validation_result,
        paths=output_paths,
    )
    write_target_fragility_gate_markdown(result, output_paths.report_md)
    return result


@dataclass
class _AuditAggregate:
    """Mutable sample-audit rows grouped by target ID."""

    target_id: str
    requested_group_id: str
    sample_count: int = 0
    flags: tuple[str, ...] = ()
    estimates: tuple[float, ...] = ()

    def append(self, row: dict[str, str]) -> None:
        """Add one sample row to this target aggregate."""
        self.sample_count += 1
        self.flags = _unique((*self.flags, *_row_flags(row)))
        estimate = _optional_float(row.get("estimate", ""))
        if estimate is not None:
            self.estimates = (*self.estimates, estimate)

    def decision(
        self,
        *,
        excluded_flags: Iterable[str],
        exclude_repeated_estimates: bool,
        repeated_estimate_tolerance: float,
    ) -> TargetFragilityDecision:
        """Return the inclusion decision for this target aggregate."""
        excluded_flag_set = {flag.strip() for flag in excluded_flags if flag.strip()}
        reasons = tuple(
            f"sample_flag:{flag}" for flag in self.flags if flag in excluded_flag_set
        )
        if exclude_repeated_estimates and repeated_estimates(
            self.estimates,
            tolerance=repeated_estimate_tolerance,
        ):
            reasons = (*reasons, "repeated_identical_estimates")
        return TargetFragilityDecision(
            target_id=self.target_id,
            requested_group_id=self.requested_group_id,
            sample_count=self.sample_count,
            available_estimate_count=len(self.estimates),
            unique_estimate_count=_unique_estimate_count(
                self.estimates, repeated_estimate_tolerance
            ),
            sample_flags=self.flags,
            reasons=_unique(reasons),
        )


def _load_audit_aggregates(path: str | Path) -> tuple[_AuditAggregate, ...]:
    """Load sample-audit rows grouped by target ID in file order."""
    audit_path = Path(path)
    with audit_path.open(newline="", encoding="utf-8") as audit_file:
        reader = csv.DictReader(audit_file)
        if reader.fieldnames is None:
            raise ValueError("sample audit CSV must include a header row")
        missing = REQUIRED_TARGET_FRAGILITY_AUDIT_COLUMNS.difference(reader.fieldnames)
        if missing:
            raise ValueError(
                "sample audit CSV missing columns: " + ", ".join(sorted(missing))
            )
        aggregates: dict[str, _AuditAggregate] = {}
        for line_number, row in enumerate(reader, start=2):
            target_id = _cell(row, "target_id", line_number)
            requested_group_id = _cell(row, "requested_group_id", line_number)
            aggregate = aggregates.setdefault(
                target_id,
                _AuditAggregate(target_id, requested_group_id),
            )
            aggregate.append({key: value or "" for key, value in row.items()})
    return tuple(aggregates.values())


def _fold_has_usable_split(
    targets: TargetDataset,
    fold: StructuralSMCValidationFoldSpec,
) -> bool:
    """Return whether a fold has both calibration and holdout observations."""
    calibration_count = holdout_count = 0
    for observation in targets.observations:
        if _observation_in_fold(observation, fold):
            holdout_count += 1
        else:
            calibration_count += 1
    return calibration_count > 0 and holdout_count > 0


def _observation_in_fold(
    observation: TargetObservation,
    fold: StructuralSMCValidationFoldSpec,
) -> bool:
    """Return whether an observation belongs to one validation fold."""
    if fold.is_time_window:
        assert fold.start_bce is not None
        assert fold.end_bce is not None
        return fold.end_bce <= observation.time_bce <= fold.start_bce
    return bool(getattr(observation, fold.holdout_field) == fold.holdout_value)


def _row_flags(row: dict[str, str]) -> tuple[str, ...]:
    """Return explicit and derived fragility flags from one sample-audit row."""
    flags = tuple(
        value.lower()
        for value in re.split(r"[;,| ]+", row.get("sample_flags", ""))
        if value.strip()
    )
    if row.get("has_metadata", "true").lower() == "false":
        flags = (*flags, "missing_metadata")
    if row.get("has_estimate", "true").lower() == "false":
        flags = (*flags, "missing_estimate")
    if "assessment=critical" in row.get("sample_metadata_note", "").lower():
        flags = (*flags, "critical")
    return _unique(flags)


def _unique_estimate_count(estimates: tuple[float, ...], tolerance: float) -> int:
    """Return an estimate-cluster count using the same tolerance as the gate."""
    representatives: list[float] = []
    for estimate in sorted(estimates):
        if not representatives or estimate - representatives[-1] > tolerance:
            representatives.append(estimate)
    return len(representatives)


def _cell(row: dict[str, str | None], column: str, line_number: int) -> str:
    """Return a stripped required CSV cell or raise a line-aware error."""
    value = row.get(column)
    if value is None or not value.strip():
        raise ValueError(f"invalid sample audit row {line_number}: missing {column}")
    return value.strip()


def _optional_float(value: str) -> float | None:
    """Return an optional float parsed from a CSV cell."""
    stripped = value.strip()
    return None if not stripped else float(stripped)


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    """Return unique non-empty values while preserving order."""
    unique_values: list[str] = []
    for value in values:
        normalized = value.strip()
        if normalized and normalized not in unique_values:
            unique_values.append(normalized)
    return tuple(unique_values)
