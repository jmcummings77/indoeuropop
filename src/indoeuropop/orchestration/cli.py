"""Command-line interface for IndoEuroPop smoke runs."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from indoeuropop.data.target_pipeline import load_and_build_target_dataset
from indoeuropop.data.targets import load_target_dataset, write_target_dataset_csv
from indoeuropop.orchestration.data_cli import (
    DATA_COMMANDS,
    add_data_arguments,
    run_data_command,
)
from indoeuropop.orchestration.sweep_workflows import (
    SweepOutputPaths,
    run_sweep_workflow,
)
from indoeuropop.orchestration.target_comparison import (
    TargetComparisonOutputPaths,
    run_target_comparison_workflow,
)
from indoeuropop.orchestration.workflows import (
    SimulationOutputPaths,
    SimulatorKind,
    run_configured_simulation,
    write_simulation_outputs,
)
from indoeuropop.reporting.target_audit import (
    load_target_curation_audit,
)
from indoeuropop.reporting.target_audit_report import (
    target_curation_audit_markdown,
    write_target_curation_audit_markdown,
)
from indoeuropop.reporting.target_review import (
    load_target_residual_review,
    target_residual_review_markdown,
    write_target_residual_review_markdown,
)
from indoeuropop.simulation.config import default_config, load_config, load_sweep_spec


def main(argv: Sequence[str] | None = None) -> int:
    """Run the IndoEuroPop command-line interface."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "audit-target-curation":
        return _run_audit_target_curation_command(args, parser)
    if args.command == "build-targets":
        return _run_build_targets_command(args, parser)
    if args.command == "compare-targets":
        return _run_compare_targets_command(args, parser)
    if args.command == "review-target-residuals":
        return _run_review_target_residuals_command(args, parser)
    data_exit_code = run_data_command(args, parser)
    if data_exit_code is not None:
        return data_exit_code
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


def _run_build_targets_command(
    args: argparse.Namespace, parser: argparse.ArgumentParser
) -> int:
    """Run the CLI target-building command."""
    for argument_name in ("sample_metadata", "target_curation", "ancestry_estimates"):
        if getattr(args, argument_name) is None:
            parser.error(f"build-targets requires --{argument_name.replace('_', '-')}")
    if args.target_output is None:
        parser.error("build-targets requires --target-output")

    dataset = load_and_build_target_dataset(
        sample_metadata_path=args.sample_metadata,
        curation_path=args.target_curation,
        estimates_path=args.ancestry_estimates,
    )
    write_target_dataset_csv(dataset, args.target_output)
    print(f"target_count={len(dataset.observations)}")
    print(f"target_output={args.target_output}")
    return 0


def _run_sweep_command(
    args: argparse.Namespace, parser: argparse.ArgumentParser
) -> int:
    """Run the CLI deterministic sweep command."""
    if args.config is None:
        parser.error("sweep requires --config")
    if args.target_fit_csv is not None and args.targets is None:
        parser.error("sweep --target-fit-csv requires --targets")
    spec = load_sweep_spec(args.config)
    dataset = load_target_dataset(args.targets) if args.targets else None
    result = run_sweep_workflow(
        spec,
        paths=SweepOutputPaths(
            config=args.config,
            targets=args.targets,
            sweep_runs_csv=args.sweep_runs_csv,
            sensitivity_csv=args.sensitivity_csv,
            target_fit_csv=args.target_fit_csv,
            manifest_json=args.manifest_json,
        ),
        targets=dataset,
        sensitivity_outcome=args.sensitivity_outcome,
        fit_metric=args.fit_metric,
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
    if result.scored_runs:
        best_fit = result.scored_runs[0]
        print(
            "best_target_fit="
            f"run_index={best_fit.run.index},"
            f"metric={args.fit_metric},"
            f"value={best_fit.metric_value(args.fit_metric):.6f},"
            f"observations={best_fit.fit.observation_count}"
        )
    return 0


def _run_compare_targets_command(
    args: argparse.Namespace, parser: argparse.ArgumentParser
) -> int:
    """Run the CLI deterministic target-comparison workflow."""
    if args.config is None:
        parser.error("compare-targets requires --config")
    if args.targets is None:
        parser.error("compare-targets requires --targets")
    result = run_target_comparison_workflow(
        load_sweep_spec(args.config),
        load_target_dataset(args.targets),
        paths=TargetComparisonOutputPaths(
            config=args.config,
            targets=args.targets,
            sweep_runs_csv=args.sweep_runs_csv,
            sensitivity_csv=args.sensitivity_csv,
            target_fit_csv=args.target_fit_csv,
            target_residuals_csv=args.target_residuals_csv,
            plot=args.plot,
            manifest_json=args.manifest_json,
        ),
        sensitivity_outcome=args.sensitivity_outcome,
        fit_metric=args.fit_metric,
        plot_source=args.source,
        plot_region=args.region,
        command=args.command,
        manifest_name="cli-target-comparison",
        manifest_description="CLI deterministic target-comparison manifest",
    )
    best_fit = result.best_run
    print(f"comparison_run_count={len(result.sweep.runs)}")
    print(
        "best_target_fit="
        f"run_index={best_fit.run.index},"
        f"metric={args.fit_metric},"
        f"value={best_fit.metric_value(args.fit_metric):.6f},"
        f"observations={best_fit.fit.observation_count}"
    )
    print(f"target_residual_count={len(result.best_comparisons)}")
    if result.target_residuals_csv_path is not None:
        print(f"target_residuals_csv={result.target_residuals_csv_path}")
    if result.plot_path is not None:
        print(f"target_comparison_plot={result.plot_path}")
    if result.manifest_json_path is not None:
        print(f"manifest_json={result.manifest_json_path}")
    return 0


def _run_review_target_residuals_command(
    args: argparse.Namespace, parser: argparse.ArgumentParser
) -> int:
    """Run the CLI target-residual review command."""
    if args.target_residuals is None:
        parser.error("review-target-residuals requires --target-residuals")
    review = load_target_residual_review(
        args.target_residuals,
        diagnostics_path=args.target_diagnostics_json,
        outlier_z_threshold=args.outlier_z_threshold,
    )
    if args.target_review_md is None:
        print(target_residual_review_markdown(review), end="")
    else:
        output_path = write_target_residual_review_markdown(
            review, args.target_review_md
        )
        print(f"target_review={output_path}")

    top_row = review.ranked_rows[0]
    print(f"residual_count={len(review.rows)}")
    print(f"outlier_count={len(review.outliers)}")
    print(
        "top_residual="
        f"{top_row.region},"
        f"{top_row.requested_group_id or 'unknown'},"
        f"z={top_row.z_score:.6f},"
        f"residual={top_row.residual:.6f}"
    )
    print(f"recommendation={review.recommendation}")
    return 0


def _run_audit_target_curation_command(
    args: argparse.Namespace, parser: argparse.ArgumentParser
) -> int:
    """Run the CLI target curation audit command."""
    for argument_name in (
        "target_residuals",
        "target_curation",
        "sample_metadata",
        "ancestry_estimates",
    ):
        if getattr(args, argument_name) is None:
            parser.error(
                "audit-target-curation requires " f"--{argument_name.replace('_', '-')}"
            )
    audit = load_target_curation_audit(
        residuals_path=args.target_residuals,
        curation_path=args.target_curation,
        sample_metadata_path=args.sample_metadata,
        ancestry_estimates_path=args.ancestry_estimates,
        target_id=args.target_id,
        requested_group_id=args.requested_group_id,
        outlier_z_threshold=args.outlier_z_threshold,
    )
    if args.target_audit_md is None:
        print(target_curation_audit_markdown(audit), end="")
    else:
        output_path = write_target_curation_audit_markdown(audit, args.target_audit_md)
        print(f"target_audit={output_path}")

    print(f"target_id={audit.target_id}")
    print(f"requested_group_id={audit.requested_group_id or 'unknown'}")
    print(f"sample_count={len(audit.samples)}")
    print(f"missing_metadata_count={len(audit.missing_metadata_ids)}")
    print(f"missing_estimate_count={len(audit.missing_estimate_ids)}")
    print(f"recommendation={audit.recommendation}")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    """Create the CLI argument parser."""
    parser = argparse.ArgumentParser(prog="indoeuropop")
    parser.add_argument(
        "command",
        choices=(
            "audit-target-curation",
            "build-targets",
            "compare-targets",
            "demo",
            "review-target-residuals",
            "sweep",
            *DATA_COMMANDS,
        ),
        help="run a CLI workflow",
    )
    parser.add_argument("--config", type=Path, help="path to a TOML config file")
    parser.add_argument("--plot", type=Path, help="optional output path for a plot")
    parser.add_argument("--region", help="region label to summarize")
    parser.add_argument("--source", default="steppe", help="source label to summarize")
    parser.add_argument("--seed", type=int, default=7, help="seed for stochastic runs")
    parser.add_argument("--targets", type=Path, help="optional target CSV to compare")
    parser.add_argument(
        "--sample-metadata",
        type=Path,
        help="sample metadata CSV for target building",
    )
    parser.add_argument(
        "--target-curation",
        type=Path,
        help="target curation CSV for target building",
    )
    parser.add_argument(
        "--ancestry-estimates",
        type=Path,
        help="sample ancestry estimate CSV for target building",
    )
    parser.add_argument(
        "--target-output",
        type=Path,
        help="output target observation CSV for target building",
    )
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
        "--target-fit-csv",
        type=Path,
        help="optional output path for ranked sweep target-fit CSV rows",
    )
    parser.add_argument(
        "--target-residuals-csv",
        type=Path,
        help="optional output path for best-run target residual CSV rows",
    )
    parser.add_argument(
        "--target-residuals",
        type=Path,
        help="target residual CSV input for review reporting",
    )
    parser.add_argument(
        "--target-review-md",
        type=Path,
        help="optional output path for target residual review Markdown",
    )
    parser.add_argument(
        "--target-audit-md",
        type=Path,
        help="optional output path for target curation audit Markdown",
    )
    parser.add_argument(
        "--target-id",
        help="target identifier to audit; defaults to the largest residual",
    )
    parser.add_argument(
        "--requested-group-id",
        help="requested AADR group identifier to audit",
    )
    parser.add_argument(
        "--outlier-z-threshold",
        type=float,
        default=2.0,
        help="absolute z-score threshold for target residual review outliers",
    )
    parser.add_argument(
        "--sensitivity-outcome",
        default="final_ancestry",
        help="trajectory summary field used for sweep sensitivity diagnostics",
    )
    parser.add_argument(
        "--fit-metric",
        default="chi_square",
        help="target-fit metric used to rank scored sweep rows",
    )
    parser.add_argument(
        "--stochastic",
        action="store_true",
        help="use the tau-leap simulator instead of the deterministic simulator",
    )
    add_data_arguments(parser)
    return parser


if __name__ == "__main__":
    raise SystemExit(main())
