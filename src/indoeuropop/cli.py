"""Command-line interface for IndoEuroPop smoke runs."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from indoeuropop.config import default_config, load_config
from indoeuropop.experiments import (
    ExperimentArtifact,
    artifact_from_path,
    write_experiment_manifest_json,
)
from indoeuropop.reporting import write_provenance_csv
from indoeuropop.targets import load_target_dataset
from indoeuropop.visualization import plot_ancestry
from indoeuropop.workflows import (
    SimulatorKind,
    run_configured_simulation,
    simulation_experiment_manifest,
    simulation_provenance_records,
)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the IndoEuroPop command-line interface."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    config = load_config(args.config) if args.config else default_config()
    simulator: SimulatorKind = "tau_leap" if args.stochastic else "deterministic"
    run = run_configured_simulation(config, simulator=simulator, seed=args.seed)

    final_ancestry = run.final_ancestry(args.source, args.region)
    print(f"final_{args.source}_ancestry={final_ancestry:.6f}")

    dataset = load_target_dataset(args.targets) if args.targets else None
    if dataset is not None:
        for comparison in dataset.compare(run.result):
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
        figure = plot_ancestry(run.result, source=args.source, region=args.region)
        args.plot.parent.mkdir(parents=True, exist_ok=True)
        figure.savefig(args.plot)

    if args.provenance_csv:
        write_provenance_csv(
            simulation_provenance_records(
                run,
                source=args.source,
                region=args.region,
                dataset=dataset,
            ),
            args.provenance_csv,
        )
    if args.manifest_json:
        write_experiment_manifest_json(
            simulation_experiment_manifest(
                run,
                source=args.source,
                region=args.region,
                artifacts=_manifest_artifacts(args),
                command=args.command,
                name="cli-demo",
                description="CLI demo smoke-run manifest",
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


if __name__ == "__main__":
    raise SystemExit(main())
