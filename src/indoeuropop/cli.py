"""Command-line interface for IndoEuroPop smoke runs."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from indoeuropop.config import default_config, load_config
from indoeuropop.simulation import run_deterministic, run_tau_leap
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
        )
    else:
        result = run_deterministic(
            config.initial_state,
            config.parameters,
            start_bce=config.start_bce,
            end_bce=config.end_bce,
            step_years=config.step_years,
        )

    final_ancestry = result.final_state.ancestry_proportion(args.source, args.region)
    print(f"final_{args.source}_ancestry={final_ancestry:.6f}")

    if args.plot:
        figure = plot_ancestry(result, source=args.source, region=args.region)
        args.plot.parent.mkdir(parents=True, exist_ok=True)
        figure.savefig(args.plot)
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
    parser.add_argument(
        "--stochastic",
        action="store_true",
        help="use the tau-leap simulator instead of the deterministic simulator",
    )
    return parser


if __name__ == "__main__":
    raise SystemExit(main())
