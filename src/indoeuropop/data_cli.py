"""Data-oriented command handlers for the IndoEuroPop CLI."""

from __future__ import annotations

import argparse
from pathlib import Path

from indoeuropop.aadr import write_aadr_sample_metadata_csv
from indoeuropop.aadr_curation import (
    AADRTargetInputOptions,
    load_aadr_group_selections,
    prepare_aadr_target_inputs,
    write_aadr_target_inputs,
)
from indoeuropop.aadr_groups import (
    DEFAULT_AADR_TARGET_KEYWORDS,
    AADRGroupSuggestionOptions,
    load_aadr_group_suggestions,
    write_aadr_group_selections_tsv,
)
from indoeuropop.data_sources import load_data_source_catalog
from indoeuropop.qpadm_estimates import write_qpadm_sample_ancestry_estimates_csv
from indoeuropop.source_downloader import (
    DownloadOptions,
    download_catalog_sources,
    write_download_manifest_csv,
)

DATA_COMMANDS = (
    "download-sources",
    "load-aadr",
    "load-qpadm-estimates",
    "prepare-aadr-target-inputs",
    "suggest-aadr-groups",
)


def run_data_command(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
) -> int | None:
    """Run a data command, returning `None` when the command is unrelated."""
    if args.command == "download-sources":
        return _run_download_sources_command(args, parser)
    if args.command == "load-aadr":
        return _run_load_aadr_command(args, parser)
    if args.command == "load-qpadm-estimates":
        return _run_load_qpadm_estimates_command(args, parser)
    if args.command == "prepare-aadr-target-inputs":
        return _run_prepare_aadr_target_inputs_command(args, parser)
    if args.command == "suggest-aadr-groups":
        return _run_suggest_aadr_groups_command(args, parser)
    return None


def add_data_arguments(parser: argparse.ArgumentParser) -> None:
    """Register data-command arguments on the shared CLI parser."""
    parser.add_argument("--aadr-dir", type=Path, help="directory containing AADR files")
    parser.add_argument(
        "--aadr-dataset-id",
        default="aadr-v66-p1-1240k",
        help="dataset ID to assign to exported AADR sample metadata",
    )
    parser.add_argument("--aadr-limit", type=int, help="optional AADR row limit")
    parser.add_argument("--aadr-groups", type=Path, help="AADR region/group file")
    parser.add_argument("--aadr-groups-out", type=Path, help="suggested group TSV")
    parser.add_argument(
        "--aadr-group-match",
        choices=("exact", "prefix"),
        default="exact",
        help="how AADR group selections match observed group IDs",
    )
    parser.add_argument("--allow-missing-aadr-groups", action="store_true")
    parser.add_argument("--min-group-samples", type=int, default=3)
    parser.add_argument("--date-min-bce", type=float, default=1000.0)
    parser.add_argument("--date-max-bce", type=float, default=3000.0)
    parser.add_argument(
        "--aadr-target-keywords",
        default=",".join(DEFAULT_AADR_TARGET_KEYWORDS),
        help="comma-separated AADR group label keywords",
    )
    parser.add_argument("--sample-metadata-out", type=Path, help="AADR metadata CSV")
    parser.add_argument("--qpadm-estimates", type=Path, help="qpAdm estimate table")
    parser.add_argument(
        "--ancestry-estimates-out",
        type=Path,
        help="output sample ancestry estimate CSV",
    )
    parser.add_argument("--qpadm-method", default="qpadm_steppe")
    parser.add_argument("--default-standard-error", type=float)
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
    parser.add_argument("--target-curation-out", type=Path, help="AADR curation CSV")
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
        "--overwrite",
        action="store_true",
        help="overwrite existing downloaded source files",
    )


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


def _run_load_qpadm_estimates_command(
    args: argparse.Namespace, parser: argparse.ArgumentParser
) -> int:
    """Run the CLI qpAdm estimate conversion command."""
    if args.qpadm_estimates is None:
        parser.error("load-qpadm-estimates requires --qpadm-estimates")
    if args.ancestry_estimates_out is None:
        parser.error("load-qpadm-estimates requires --ancestry-estimates-out")
    output_path = write_qpadm_sample_ancestry_estimates_csv(
        args.qpadm_estimates,
        args.ancestry_estimates_out,
        source=args.source,
        method=args.qpadm_method,
        default_standard_error=args.default_standard_error,
    )
    print(f"sample_ancestry_estimates={output_path}")
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


def _run_suggest_aadr_groups_command(
    args: argparse.Namespace, parser: argparse.ArgumentParser
) -> int:
    """Run the CLI AADR group-suggestion command."""
    if args.aadr_dir is None:
        parser.error("suggest-aadr-groups requires --aadr-dir")
    if args.aadr_groups_out is None:
        parser.error("suggest-aadr-groups requires --aadr-groups-out")
    selections = load_aadr_group_suggestions(
        args.aadr_dir,
        options=AADRGroupSuggestionOptions(
            min_count=args.min_group_samples,
            date_min_bce=args.date_min_bce,
            date_max_bce=args.date_max_bce,
            keywords=_keyword_tuple(args.aadr_target_keywords),
        ),
    )
    output_path = write_aadr_group_selections_tsv(selections, args.aadr_groups_out)
    print(f"aadr_group_count={len(selections)}")
    print(f"aadr_groups={output_path}")
    return 0


def _keyword_tuple(value: str) -> tuple[str, ...]:
    """Return non-empty comma-separated AADR target keywords."""
    return tuple(keyword.strip() for keyword in value.split(",") if keyword.strip())
