"""Command-line interface for IndoEuroPop smoke runs."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from indoeuropop.aadr import write_aadr_sample_metadata_csv
from indoeuropop.aadr_curation import (
    AADRTargetInputOptions,
    load_aadr_group_selections,
    prepare_aadr_target_inputs,
    write_aadr_target_inputs,
)
from indoeuropop.config import default_config, load_config, load_sweep_spec
from indoeuropop.data_sources import load_data_source_catalog
from indoeuropop.source_downloader import (
    DownloadOptions,
    download_catalog_sources,
    write_download_manifest_csv,
)
from indoeuropop.sweep_workflows import SweepOutputPaths, run_sweep_workflow
from indoeuropop.target_pipeline import load_and_build_target_dataset
from indoeuropop.targets import load_target_dataset, write_target_dataset_csv
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
    if args.command == "build-targets":
        return _run_build_targets_command(args, parser)
    if args.command == "download-sources":
        return _run_download_sources_command(args, parser)
    if args.command == "load-aadr":
        return _run_load_aadr_command(args, parser)
    if args.command == "prepare-aadr-target-inputs":
        return _run_prepare_aadr_target_inputs_command(args, parser)
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


def _run_download_sources_command(
    args: argparse.Namespace, parser: argparse.ArgumentParser
) -> int:
    """Run the CLI data-source download command."""
    if args.data_sources is None:
        parser.error("download-sources requires --data-sources")
    if args.output_dir is None:
        parser.error("download-sources requires --output-dir")
    catalog = load_data_source_catalog(args.data_sources)
    downloads = download_catalog_sources(
        catalog,
        DownloadOptions(
            output_dir=args.output_dir,
            base_path=args.source_base,
            overwrite=args.overwrite,
        ),
        dataset_ids=args.dataset_id,
    )
    if args.download_manifest_csv is not None:
        write_download_manifest_csv(downloads, args.download_manifest_csv)
    print(f"download_count={len(downloads)}")
    for download in downloads:
        print(
            "downloaded_source="
            f"{download.dataset_id},"
            f"path={download.path},"
            f"sha256={download.checksum_sha256},"
            f"bytes={download.size_bytes}"
        )
    return 0


def _run_load_aadr_command(
    args: argparse.Namespace, parser: argparse.ArgumentParser
) -> int:
    """Run the CLI AADR metadata loading command."""
    if args.aadr_dir is None:
        parser.error("load-aadr requires --aadr-dir")
    if args.sample_metadata_out is None:
        parser.error("load-aadr requires --sample-metadata-out")
    output_path = write_aadr_sample_metadata_csv(
        args.aadr_dir,
        args.sample_metadata_out,
        dataset_id=args.aadr_dataset_id,
        limit=args.aadr_limit,
    )
    print(f"aadr_sample_metadata={output_path}")
    return 0


def _run_prepare_aadr_target_inputs_command(
    args: argparse.Namespace, parser: argparse.ArgumentParser
) -> int:
    """Run the CLI AADR target-input preparation command."""
    if args.aadr_dir is None:
        parser.error("prepare-aadr-target-inputs requires --aadr-dir")
    if args.aadr_groups is None:
        parser.error("prepare-aadr-target-inputs requires --aadr-groups")
    if args.sample_metadata_out is None:
        parser.error("prepare-aadr-target-inputs requires --sample-metadata-out")
    if args.target_curation_out is None:
        parser.error("prepare-aadr-target-inputs requires --target-curation-out")

    selections = load_aadr_group_selections(args.aadr_groups)
    inputs = prepare_aadr_target_inputs(
        args.aadr_dir,
        selections,
        options=AADRTargetInputOptions(
            dataset_id=args.aadr_dataset_id,
            source=args.source,
            ancestry_method=args.ancestry_method,
            aggregation_method=args.aggregation_method,
            group_match_mode=args.aadr_group_match,
            citation_key=args.aadr_dataset_id,
            allow_missing_groups=args.allow_missing_aadr_groups,
        ),
    )
    paths = write_aadr_target_inputs(
        inputs,
        sample_metadata_path=args.sample_metadata_out,
        target_curation_path=args.target_curation_out,
    )
    print(f"aadr_selected_sample_count={inputs.sample_metadata.sample_count}")
    print(f"target_curation_count={len(inputs.curation.records)}")
    print(f"aadr_sample_metadata={paths.sample_metadata_path}")
    print(f"target_curation={paths.target_curation_path}")
    for selection in inputs.unmatched_selections:
        print(f"unmatched_aadr_group={selection.region},{selection.group_id}")
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


def _build_parser() -> argparse.ArgumentParser:
    """Create the CLI argument parser."""
    parser = argparse.ArgumentParser(prog="indoeuropop")
    parser.add_argument(
        "command",
        choices=(
            "build-targets",
            "demo",
            "download-sources",
            "load-aadr",
            "prepare-aadr-target-inputs",
            "sweep",
        ),
        help="run a CLI workflow",
    )
    parser.add_argument("--config", type=Path, help="path to a TOML config file")
    parser.add_argument("--aadr-dir", type=Path, help="directory containing AADR files")
    parser.add_argument(
        "--aadr-dataset-id",
        default="aadr-v66-p1-1240k",
        help="dataset ID to assign to exported AADR sample metadata",
    )
    parser.add_argument("--aadr-limit", type=int, help="optional AADR row limit")
    parser.add_argument("--aadr-groups", type=Path, help="AADR region/group file")
    parser.add_argument(
        "--aadr-group-match",
        choices=("exact", "prefix"),
        default="exact",
        help="how AADR group selections match observed group IDs",
    )
    parser.add_argument("--allow-missing-aadr-groups", action="store_true")
    parser.add_argument("--sample-metadata-out", type=Path, help="AADR metadata CSV")
    parser.add_argument(
        "--data-sources",
        type=Path,
        help="data-source catalog TOML for source downloads",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="directory for downloaded or materialized source files",
    )
    parser.add_argument(
        "--source-base",
        type=Path,
        default=Path("."),
        help="base directory for local catalog source paths",
    )
    parser.add_argument(
        "--dataset-id",
        action="append",
        default=(),
        help="catalog dataset ID to download; can be repeated",
    )
    parser.add_argument(
        "--download-manifest-csv",
        type=Path,
        help="optional output CSV manifest for downloaded sources",
    )
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
    parser.add_argument("--target-curation-out", type=Path, help="AADR curation CSV")
    parser.add_argument(
        "--ancestry-estimates",
        type=Path,
        help="sample ancestry estimate CSV for target building",
    )
    parser.add_argument(
        "--ancestry-method",
        default="external_autosomal_steppe_required",
        help="ancestry method label to write into prepared AADR curation rows",
    )
    parser.add_argument(
        "--aggregation-method",
        default="unweighted_mean",
        help="aggregation method label to write into prepared AADR curation rows",
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
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="overwrite existing downloaded source files",
    )
    return parser


if __name__ == "__main__":
    raise SystemExit(main())
