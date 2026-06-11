"""Command-line interface for IndoEuroPop smoke runs."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from indoeuropop.config import default_config, load_config, load_sweep_spec
from indoeuropop.sweep_workflows import SweepOutputPaths, run_sweep_workflow
from indoeuropop.targets import load_target_dataset
from indoeuropop.workflows import (
    SimulationOutputPaths,
    SimulatorKind,
    run_configured_simulation,
    write_simulation_outputs,
)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the IndoEuroPop command-line interface."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "sweep":
        return _run_sweep_command(args, parser)
    return _run_demo_command(args)


def _run_demo_command(args: argparse.Namespace) -> int:
    """Run the CLI demo simulation command."""
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

    write_simulation_outputs(
        run,
        source=args.source,
        region=args.region,
        dataset=dataset,
        paths=SimulationOutputPaths(
            config=args.config,
            targets=args.targets,
            plot=args.plot,
            provenance_csv=args.provenance_csv,
            manifest_json=args.manifest_json,
        ),
        command=args.command,
        manifest_name="cli-demo",
        manifest_description="CLI demo smoke-run manifest",
    )
    return 0


def _run_sweep_command(
    args: argparse.Namespace, parser: argparse.ArgumentParser
) -> int:
    """Run the CLI deterministic sweep command."""
    if args.config is None:
        parser.error("sweep requires --config")
    spec = load_sweep_spec(args.config)
    result = run_sweep_workflow(
        spec,
        paths=SweepOutputPaths(
            config=args.config,
            sweep_runs_csv=args.sweep_runs_csv,
            sensitivity_csv=args.sensitivity_csv,
            manifest_json=args.manifest_json,
        ),
        sensitivity_outcome=args.sensitivity_outcome,
        command=args.command,
        manifest_name="cli-sweep",
        manifest_description="CLI deterministic sweep manifest",
    )
    print(f"sweep_run_count={len(result.runs)}")
    for sensitivity in result.sensitivity_results:
        print(
            "sensitivity="
            f"{sensitivity.parameter},"
            f"outcome={sensitivity.outcome},"
            f"spearman={sensitivity.spearman_correlation:.6f},"
            f"pearson={sensitivity.pearson_correlation:.6f}"
        )
    return 0


def _build_parser() -> argparse.ArgumentParser:
    """Create the CLI argument parser."""
    parser = argparse.ArgumentParser(prog="indoeuropop")
    parser.add_argument(
        "command",
        choices=("demo", "sweep"),
        help="run a smoke simulation or deterministic sweep",
    )
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
        "--sweep-runs-csv",
        type=Path,
        help="optional output path for deterministic sweep-run CSV rows",
    )
    parser.add_argument(
        "--sensitivity-csv",
        type=Path,
        help="optional output path for sweep sensitivity CSV rows",
    )
    parser.add_argument(
        "--sensitivity-outcome",
        default="final_ancestry",
        help="trajectory summary field used for sweep sensitivity diagnostics",
    )
    parser.add_argument(
        "--stochastic",
        action="store_true",
        help="use the tau-leap simulator instead of the deterministic simulator",
    )
    return parser


if __name__ == "__main__":
    raise SystemExit(main())
