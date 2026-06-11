"""Command-line interface for IndoEuroPop smoke runs."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from indoeuropop.config import default_config, load_config
from indoeuropop.diagnostics import validate_simulation_result
from indoeuropop.experiments import (
    ExperimentArtifact,
    ExperimentManifest,
    artifact_from_path,
    write_experiment_manifest_json,
)
from indoeuropop.fitting import score_result_against_targets
from indoeuropop.models import SimulationResult
from indoeuropop.provenance import (
    ProvenanceRecord,
    summary_provenance_records,
    target_fit_provenance_records,
    target_observation_provenance_records,
)
from indoeuropop.reporting import diagnostic_issue_records, write_provenance_csv
from indoeuropop.reproducibility import fingerprint_simulation_result
from indoeuropop.simulation import run_deterministic, run_tau_leap
from indoeuropop.summary import summarize_trajectory
from indoeuropop.targets import TargetDataset, load_target_dataset
from indoeuropop.visualization import plot_ancestry


def main(argv: Sequence[str] | None = None) -> int:
    """Run the IndoEuroPop command-line interface."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    config = load_config(args.config) if args.config else default_config()
    if args.stochastic:
        result = run_tau_leap(
            config.initial_state,
            config.parameters,
            start_bce=config.start_bce,
            end_bce=config.end_bce,
            step_years=config.step_years,
            seed=args.seed,
            schedule=config.schedule,
            parameter_set=config.parameter_set,
        )
    else:
        result = run_deterministic(
            config.initial_state,
            config.parameters,
            start_bce=config.start_bce,
            end_bce=config.end_bce,
            step_years=config.step_years,
            schedule=config.schedule,
            parameter_set=config.parameter_set,
        )

    final_ancestry = result.final_state.ancestry_proportion(args.source, args.region)
    print(f"final_{args.source}_ancestry={final_ancestry:.6f}")

    dataset = load_target_dataset(args.targets) if args.targets else None
    if dataset is not None:
        for comparison in dataset.compare(result):
            observation = comparison.observation
            print(
                "target_comparison="
                f"{observation.region},"
                f"{observation.source},"
                f"{observation.time_bce:.1f},"
                f"predicted={comparison.predicted:.6f},"
                f"observed={observation.mean:.6f},"
                f"z={comparison.z_score:.3f}"
            )

    if args.plot:
        figure = plot_ancestry(result, source=args.source, region=args.region)
        args.plot.parent.mkdir(parents=True, exist_ok=True)
        figure.savefig(args.plot)

    if args.provenance_csv:
        write_provenance_csv(
            _provenance_records(
                result,
                source=args.source,
                region=args.region,
                dataset=dataset,
            ),
            args.provenance_csv,
        )
    if args.manifest_json:
        write_experiment_manifest_json(
            _experiment_manifest(
                args,
                result=result,
            ),
            args.manifest_json,
        )
    return 0


def _build_parser() -> argparse.ArgumentParser:
    """Create the CLI argument parser."""
    parser = argparse.ArgumentParser(prog="indoeuropop")
    parser.add_argument("command", choices=("demo",), help="run a smoke simulation")
    parser.add_argument("--config", type=Path, help="path to a TOML config file")
    parser.add_argument("--plot", type=Path, help="optional output path for a plot")
    parser.add_argument("--region", help="region label to summarize")
    parser.add_argument("--source", default="steppe", help="source label to summarize")
    parser.add_argument("--seed", type=int, default=7, help="seed for stochastic runs")
    parser.add_argument("--targets", type=Path, help="optional target CSV to compare")
    parser.add_argument(
        "--provenance-csv",
        type=Path,
        help="optional output path for a provenance CSV report",
    )
    parser.add_argument(
        "--manifest-json",
        type=Path,
        help="optional output path for an experiment manifest JSON file",
    )
    parser.add_argument(
        "--stochastic",
        action="store_true",
        help="use the tau-leap simulator instead of the deterministic simulator",
    )
    return parser


def _experiment_manifest(
    args: argparse.Namespace,
    *,
    result: SimulationResult,
) -> ExperimentManifest:
    """Return an experiment manifest for one CLI smoke run."""
    simulator = "tau_leap" if args.stochastic else "deterministic"
    metadata = {
        "command": args.command,
        "simulator": simulator,
        "source": args.source,
        "region": args.region or "all",
        "seed": str(args.seed) if args.stochastic else "",
    }
    return ExperimentManifest(
        name="cli-demo",
        description="CLI demo smoke-run manifest",
        artifacts=_manifest_artifacts(args),
        fingerprints=(fingerprint_simulation_result(result),),
        metadata=metadata,
    )


def _manifest_artifacts(args: argparse.Namespace) -> tuple[ExperimentArtifact, ...]:
    """Return checksum-bearing manifest artifacts for CLI inputs and outputs."""
    artifacts: list[ExperimentArtifact] = []
    if args.config is not None:
        artifacts.append(artifact_from_path("config", "config", args.config))
    if args.targets is not None:
        artifacts.append(artifact_from_path("targets", "targets", args.targets))
    if args.plot is not None:
        artifacts.append(artifact_from_path("plot", "plot", args.plot))
    if args.provenance_csv is not None:
        artifacts.append(
            artifact_from_path("provenance_csv", "provenance", args.provenance_csv)
        )
    return tuple(artifacts)


def _provenance_records(
    result: SimulationResult,
    *,
    source: str,
    region: str | None,
    dataset: TargetDataset | None,
) -> tuple[ProvenanceRecord, ...]:
    """Return provenance records for one CLI smoke run."""
    records = list(
        summary_provenance_records(
            summarize_trajectory(result, source=source, region=region)
        )
    )
    records.extend(
        diagnostic_issue_records(
            validate_simulation_result(result),
        )
    )
    if dataset is not None:
        for observation in dataset.observations:
            records.extend(target_observation_provenance_records(observation))
        records.extend(
            target_fit_provenance_records(score_result_against_targets(result, dataset))
        )
    return tuple(records)


if __name__ == "__main__":
    raise SystemExit(main())
