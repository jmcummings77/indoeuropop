"""Tests for reproducibility fingerprints."""

from typing import cast

import pytest

from indoeuropop.models import PopulationState, SimulationParameters, SimulationResult
from indoeuropop.reproducibility import (
    FingerprintKind,
    ReproducibilityFingerprint,
    canonical_json_payload,
    fingerprint_payload,
    fingerprint_simulation_result,
    fingerprint_sweep_collection,
    fingerprint_sweep_run,
    population_state_payload,
    simulation_parameters_payload,
    simulation_result_payload,
    sweep_collection_payload,
    sweep_run_payload,
    trajectory_summary_payload,
)
from indoeuropop.summary import TrajectorySummary
from indoeuropop.sweeps import SweepRun


def _summary(final_ancestry: float = 0.25) -> TrajectorySummary:
    """Return one trajectory summary for fingerprint tests."""
    return TrajectorySummary(
        source="steppe",
        region="britain",
        start_bce=3000,
        end_bce=2900,
        initial_ancestry=0.0,
        final_ancestry=final_ancestry,
        ancestry_delta=final_ancestry,
        ancestry_slope_per_century=final_ancestry,
        min_total_population=100,
        final_total_population=100,
        is_extinct=False,
    )


def _sweep_run(index: int = 1, final_ancestry: float = 0.25) -> SweepRun:
    """Return one sweep run for fingerprint tests."""
    return SweepRun(
        index=index,
        sampled_values={"migration_rate": 0.002, "epidemic_mortality_rate": 0.0},
        parameters=SimulationParameters(migration_rate=0.002),
        summary=_summary(final_ancestry),
    )


def test_canonical_json_payload_sorts_keys_and_omits_spaces() -> None:
    """Canonical JSON should be compact and key-sorted."""
    assert canonical_json_payload({"b": 1, "a": 2}) == '{"a":2,"b":1}'


def test_canonical_json_payload_rejects_non_finite_numbers() -> None:
    """Fingerprint payloads should not serialize non-finite floating values."""
    with pytest.raises(ValueError):
        canonical_json_payload({"value": float("nan")})


@pytest.mark.parametrize(
    "kind,digest_sha256,payload",
    [
        (cast(FingerprintKind, "unknown"), "0" * 64, {"x": 1}),
        ("simulation_result", "not-a-digest", {"x": 1}),
        ("simulation_result", "0" * 64, {}),
    ],
)
def test_reproducibility_fingerprint_rejects_invalid_fields(
    kind: FingerprintKind, digest_sha256: str, payload: dict[str, object]
) -> None:
    """Invalid fingerprint fields should fail before use."""
    with pytest.raises(ValueError):
        ReproducibilityFingerprint(
            kind=kind,
            digest_sha256=digest_sha256,
            payload=payload,
        )


def test_fingerprint_payload_includes_schema_and_digest() -> None:
    """Generic payload fingerprints should include schema metadata."""
    fingerprint = fingerprint_payload("simulation_result", {"answer": 42})

    assert fingerprint.kind == "simulation_result"
    assert len(fingerprint.digest_sha256) == 64
    assert fingerprint.payload["schema_version"] == "indoeuropop-fingerprint-v1"
    assert fingerprint.payload["kind"] == "simulation_result"
    assert fingerprint.canonical_json() == canonical_json_payload(fingerprint.payload)


def test_simulation_result_fingerprint_is_independent_of_mapping_order() -> None:
    """Semantically identical population states should share a fingerprint."""
    first = SimulationResult(
        (3000,),
        (
            PopulationState(
                {
                    "britain": {"local": 80, "steppe": 20},
                    "iberia": {"steppe": 5, "local": 95},
                }
            ),
        ),
    )
    second = SimulationResult(
        (3000,),
        (
            PopulationState(
                {
                    "iberia": {"local": 95, "steppe": 5},
                    "britain": {"steppe": 20, "local": 80},
                }
            ),
        ),
    )

    assert population_state_payload(first.states[0]) == population_state_payload(
        second.states[0]
    )
    assert simulation_result_payload(first) == simulation_result_payload(second)
    assert (
        fingerprint_simulation_result(first).digest_sha256
        == fingerprint_simulation_result(second).digest_sha256
    )


def test_simulation_result_fingerprint_changes_when_output_changes() -> None:
    """Different simulator outputs should produce different fingerprints."""
    baseline = SimulationResult(
        (3000,),
        (PopulationState({"britain": {"local": 80, "steppe": 20}}),),
    )
    changed = SimulationResult(
        (3000,),
        (PopulationState({"britain": {"local": 79, "steppe": 21}}),),
    )

    assert (
        fingerprint_simulation_result(baseline).digest_sha256
        != fingerprint_simulation_result(changed).digest_sha256
    )


def test_sweep_run_payload_is_stable_and_complete() -> None:
    """Sweep run payloads should include sampled values, parameters, and summary."""
    run = _sweep_run(index=3)
    payload = sweep_run_payload(run)

    assert payload["index"] == 3
    assert payload["sampled_values"] == [
        {"name": "epidemic_mortality_rate", "value": 0.0},
        {"name": "migration_rate", "value": 0.002},
    ]
    assert payload["parameters"] == simulation_parameters_payload(run.parameters)
    assert payload["summary"] == trajectory_summary_payload(run.summary)


def test_sweep_run_fingerprint_changes_when_summary_changes() -> None:
    """Sweep fingerprints should change when run outputs change."""
    baseline = fingerprint_sweep_run(_sweep_run(final_ancestry=0.25))
    changed = fingerprint_sweep_run(_sweep_run(final_ancestry=0.3))

    assert baseline.digest_sha256 != changed.digest_sha256


def test_sweep_collection_fingerprint_uses_ordered_runs() -> None:
    """Sweep collection fingerprints should preserve run ordering."""
    first = _sweep_run(index=1)
    second = _sweep_run(index=2)

    forward = fingerprint_sweep_collection((first, second))
    reversed_runs = fingerprint_sweep_collection((second, first))

    assert sweep_collection_payload((first, second))["runs"] == [
        sweep_run_payload(first),
        sweep_run_payload(second),
    ]
    assert forward.digest_sha256 != reversed_runs.digest_sha256


def test_sweep_collection_payload_rejects_empty_runs() -> None:
    """Sweep collection payloads should require at least one run."""
    with pytest.raises(ValueError):
        sweep_collection_payload(())


def test_fingerprint_can_be_converted_to_provenance_record() -> None:
    """Fingerprints should bridge into existing provenance reports."""
    fingerprint = fingerprint_sweep_run(_sweep_run())

    record = fingerprint.to_provenance_record()

    assert record.name == "sweep_run_fingerprint"
    assert record.kind == "derived"
    assert record.value == fingerprint.digest_sha256
    assert record.unit == "sha256"
    assert record.metadata == {
        "fingerprint_kind": "sweep_run",
        "schema_version": "indoeuropop-fingerprint-v1",
    }
