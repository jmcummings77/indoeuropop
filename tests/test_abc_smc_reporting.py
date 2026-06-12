"""Tests for ABC-SMC calibration report serializers."""

from __future__ import annotations

from pathlib import Path

from indoeuropop.analysis.abc_smc import ABCSMCOptions, run_abc_smc_inference
from indoeuropop.data.targets import TargetDataset, TargetObservation
from indoeuropop.models import PopulationState, SimulationParameters
from indoeuropop.orchestration.sweeps import ParameterRange, SweepSpec
from indoeuropop.reporting.abc_smc import (
    ABC_SMC_GENERATION_FIELDS,
    abc_smc_generation_rows,
    abc_smc_generations_to_csv,
    abc_smc_markdown,
    write_abc_smc_generations_csv,
    write_abc_smc_markdown,
)


def test_abc_smc_generation_csv_and_markdown_are_stable(tmp_path: Path) -> None:
    """SMC generation reports should be inspectable and writable."""
    result = run_abc_smc_inference(
        _spec(),
        _targets(),
        ABCSMCOptions(generation_count=2, acceptance_count=1),
    )
    generations_path = tmp_path / "reports" / "generations.csv"
    markdown_path = tmp_path / "reports" / "smc.md"

    rows = abc_smc_generation_rows(result)
    csv_text = abc_smc_generations_to_csv(result)
    markdown = abc_smc_markdown(result)

    assert ABC_SMC_GENERATION_FIELDS[0] == "generation"
    assert rows[0]["generation"] == "0"
    assert rows[0]["fit_metric"] == "root_mean_squared_error"
    assert csv_text.startswith("generation,seed,candidate_count")
    assert "ABC-SMC-style calibration" in markdown
    assert "Final Parameter Summaries" in markdown
    assert write_abc_smc_generations_csv(result, generations_path) == generations_path
    assert write_abc_smc_markdown(result, markdown_path) == markdown_path
    assert generations_path.read_text(encoding="utf-8") == csv_text
    assert markdown_path.read_text(encoding="utf-8") == markdown


def _spec() -> SweepSpec:
    """Return one small sweep spec for SMC reporting tests."""
    return SweepSpec(
        initial_state=PopulationState({"britain": {"local": 1000, "steppe": 20}}),
        base_parameters=SimulationParameters(migration_rate=0.0),
        parameter_ranges=(ParameterRange("migration_rate", 0.001, 0.004),),
        start_bce=3000,
        end_bce=2900,
        step_years=50,
        sample_count=3,
        seed=17,
        source="steppe",
        region="britain",
    )


def _targets() -> TargetDataset:
    """Return synthetic targets compatible with the SMC reporting spec."""
    return TargetDataset.from_rows(
        [
            TargetObservation(
                status="synthetic",
                region="britain",
                source="steppe",
                time_bce=2950,
                mean=0.04,
                uncertainty=0.03,
                citation_key="synthetic",
                citation="Synthetic SMC report target",
            )
        ]
    )
