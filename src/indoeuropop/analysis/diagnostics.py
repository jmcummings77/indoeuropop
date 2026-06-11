"""Sanity diagnostics for simulation outputs."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from math import isfinite
from typing import Literal

from indoeuropop.models import SimulationResult

DiagnosticSeverity = Literal["warning", "error"]


@dataclass(frozen=True)
class DiagnosticIssue:
    """One validation issue found in a simulation result."""

    code: str
    severity: DiagnosticSeverity
    message: str
    time_bce: float | None = None
    region: str | None = None
    source: str | None = None


def validate_simulation_result(
    result: SimulationResult,
    *,
    extinction_threshold: float = 1.0,
    max_population_multiplier: float = 20.0,
    sources: Iterable[str] | None = None,
) -> tuple[DiagnosticIssue, ...]:
    """Return sanity-check diagnostics for a simulation time series.

    These checks are intentionally mechanical. They flag results that deserve a
    closer look before plotting, sweeping, or comparing against targets; they do
    not decide whether a model is scientifically plausible.
    """
    extinction_limit = _require_finite_non_negative(
        "extinction_threshold", extinction_threshold
    )
    growth_limit = _require_minimum_multiplier(
        "max_population_multiplier", max_population_multiplier
    )
    source_labels = _source_labels(result, sources)
    issues = list(_time_order_issues(result))
    regions = _regions_in_result(result)
    initial_totals = _initial_totals(result, regions)

    for time_bce, state in zip(result.times_bce, result.states, strict=True):
        for region in regions:
            if region not in state.counts:
                issues.append(
                    DiagnosticIssue(
                        code="missing_region",
                        severity="error",
                        message=f"state is missing region {region!r}",
                        time_bce=time_bce,
                        region=region,
                    )
                )
                continue

            total = state.total(region)
            if total <= extinction_limit:
                issues.append(
                    DiagnosticIssue(
                        code="extinction",
                        severity="warning",
                        message=(
                            f"region {region!r} is at or below extinction threshold"
                        ),
                        time_bce=time_bce,
                        region=region,
                    )
                )

            if total > initial_totals.get(region, 1.0) * growth_limit:
                issues.append(
                    DiagnosticIssue(
                        code="runaway_growth",
                        severity="warning",
                        message=f"region {region!r} exceeds configured growth limit",
                        time_bce=time_bce,
                        region=region,
                    )
                )

            for source in source_labels:
                if source not in state.counts[region]:
                    issues.append(
                        DiagnosticIssue(
                            code="missing_source",
                            severity="error",
                            message=(f"region {region!r} is missing source {source!r}"),
                            time_bce=time_bce,
                            region=region,
                            source=source,
                        )
                    )

    return tuple(issues)


def has_errors(issues: Iterable[DiagnosticIssue]) -> bool:
    """Return whether any diagnostic issue has error severity."""
    return any(issue.severity == "error" for issue in issues)


def _time_order_issues(result: SimulationResult) -> tuple[DiagnosticIssue, ...]:
    """Return diagnostics for non-decreasing BCE time labels."""
    issues: list[DiagnosticIssue] = []
    for previous_time, time_bce in zip(
        result.times_bce, result.times_bce[1:], strict=False
    ):
        if time_bce >= previous_time:
            issues.append(
                DiagnosticIssue(
                    code="non_decreasing_time",
                    severity="error",
                    message="BCE time labels must strictly decrease",
                    time_bce=time_bce,
                )
            )
    return tuple(issues)


def _regions_in_result(result: SimulationResult) -> tuple[str, ...]:
    """Return all region labels seen across a simulation result."""
    regions: list[str] = []
    for state in result.states:
        for region in state.regions():
            if region not in regions:
                regions.append(region)
    return tuple(regions)


def _source_labels(
    result: SimulationResult, sources: Iterable[str] | None
) -> tuple[str, ...]:
    """Return validated source labels to check in every region."""
    source_labels = _provided_or_inferred_sources(result, sources)
    if any(source == "" for source in source_labels):
        raise ValueError("sources must not contain empty labels")
    return source_labels


def _provided_or_inferred_sources(
    result: SimulationResult, sources: Iterable[str] | None
) -> tuple[str, ...]:
    """Return caller-provided source labels or infer them from the result."""
    if sources is None:
        return _sources_in_result(result)
    return tuple(sources)


def _sources_in_result(result: SimulationResult) -> tuple[str, ...]:
    """Return all source labels seen across a simulation result."""
    sources: list[str] = []
    for state in result.states:
        for source in state.sources():
            if source not in sources:
                sources.append(source)
    return tuple(sources)


def _initial_totals(
    result: SimulationResult, regions: tuple[str, ...]
) -> dict[str, float]:
    """Return positive baseline totals for growth diagnostics."""
    initial_state = result.states[0]
    return {
        region: max(1.0, initial_state.total(region))
        for region in regions
        if region in initial_state.counts
    }


def _require_finite_non_negative(name: str, value: float) -> float:
    """Return a numeric value after validating it is finite and non-negative."""
    numeric_value = float(value)
    if not isfinite(numeric_value) or numeric_value < 0:
        raise ValueError(f"{name} must be finite and non-negative")
    return numeric_value


def _require_minimum_multiplier(name: str, value: float) -> float:
    """Return a numeric multiplier after validating it is at least one."""
    numeric_value = _require_finite_non_negative(name, value)
    if numeric_value < 1:
        raise ValueError(f"{name} must be at least 1")
    return numeric_value
