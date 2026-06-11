"""qpAdm planning command handlers for the IndoEuroPop CLI."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import cast

from indoeuropop.data.qpadm_rerun_ingestion import (
    run_qpadm_rerun_ingestion_workflow,
)
from indoeuropop.data.qpadm_rerun_models import (
    QpAdmRerunIngestionConfig,
)
from indoeuropop.data.qpadm_reruns import (
    load_qpadm_rerun_manifest_inputs,
    write_qpadm_rerun_groups_tsv,
    write_qpadm_rerun_manifest_json,
)
from indoeuropop.data.qpadm_workflow import (
    QpAdmRunConfig,
    qpadm_run_command,
    resolve_qpadm_genotype_prefix,
    write_qpadm_run_manifest,
)

QPADM_COMMANDS = ("ingest-qpadm-reruns", "plan-qpadm-reruns", "plan-qpadm-run")


def run_qpadm_command(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
) -> int | None:
    """Run a qpAdm planning command or return `None` for unrelated commands."""
    if args.command == "ingest-qpadm-reruns":
        return _run_ingest_qpadm_reruns_command(args, parser)
    if args.command == "plan-qpadm-reruns":
        return _run_plan_qpadm_reruns_command(args, parser)
    if args.command == "plan-qpadm-run":
        return _run_plan_qpadm_run_command(args, parser)
    return None


def _run_ingest_qpadm_reruns_command(
    args: argparse.Namespace, parser: argparse.ArgumentParser
) -> int:
    """Run the CLI qpAdm rerun-ingestion command."""
    config = QpAdmRerunIngestionConfig(
        aadr_dir=_required_path(args, parser, "aadr_dir"),
        aadr_groups_path=_required_path(args, parser, "aadr_groups"),
        baseline_qpadm_estimates_path=_required_path(args, parser, "qpadm_estimates"),
        rerun_qpadm_estimates_path=_required_path(
            args, parser, "qpadm_rerun_estimates"
        ),
        sample_metadata_path=_required_path(args, parser, "sample_metadata_out"),
        target_curation_path=_required_path(args, parser, "target_curation_out"),
        merged_ancestry_estimates_path=_required_path(
            args, parser, "ancestry_estimates_out"
        ),
        post_target_output_path=_required_path(args, parser, "target_output"),
        comparison_csv_path=_required_path(args, parser, "qpadm_rerun_comparison_csv"),
        report_markdown_path=_required_path(args, parser, "qpadm_rerun_report_md"),
        diagnostics_json_path=args.target_diagnostics_json,
        baseline_target_output_path=args.baseline_target_output,
        accepted_target_output_path=args.accepted_target_output,
        target_decisions_path=args.target_decisions,
        dataset_id=args.aadr_dataset_id,
        source=args.source,
        qpadm_method=args.qpadm_method,
        aggregation_method=args.aggregation_method,
        group_match_mode=args.aadr_group_match,
        allow_missing_groups=args.allow_missing_aadr_groups,
        default_standard_error=args.default_standard_error,
        skip_missing_standard_error=True,
    )
    result = run_qpadm_rerun_ingestion_workflow(config)
    diagnostics = result.diagnostics
    print(f"baseline_target_count={diagnostics.baseline_target_observation_count}")
    print(f"post_rerun_target_count={diagnostics.post_target_observation_count}")
    if diagnostics.accepted_target_observation_count is not None:
        print(f"accepted_target_count={diagnostics.accepted_target_observation_count}")
    print(f"rescued_target_count={diagnostics.rescued_target_count}")
    print(f"lost_target_count={diagnostics.lost_target_count}")
    print(f"merged_sample_estimate_count={diagnostics.merged_sample_estimate_count}")
    print(f"sample_metadata={config.sample_metadata_path}")
    print(f"target_curation={config.target_curation_path}")
    print(f"merged_sample_ancestry_estimates={config.merged_ancestry_estimates_path}")
    print(f"post_target_output={config.post_target_output_path}")
    if config.accepted_target_output_path is not None:
        print(f"accepted_target_output={config.accepted_target_output_path}")
    print(f"qpadm_rerun_comparison_csv={config.comparison_csv_path}")
    print(f"qpadm_rerun_report_md={config.report_markdown_path}")
    if config.diagnostics_json_path is not None:
        print(f"qpadm_rerun_diagnostics_json={config.diagnostics_json_path}")
    for target_id in diagnostics.rescued_target_ids:
        print(f"rescued_target={target_id}")
    for target_id in diagnostics.lost_target_ids:
        print(f"lost_target={target_id}")
    return 0


def _run_plan_qpadm_reruns_command(
    args: argparse.Namespace, parser: argparse.ArgumentParser
) -> int:
    """Run the CLI qpAdm rerun-manifest planning command."""
    if args.target_curation is None:
        parser.error("plan-qpadm-reruns requires --target-curation")
    if args.target_decisions is None:
        parser.error("plan-qpadm-reruns requires --target-decisions")
    if args.qpadm_rerun_manifest_json is None:
        parser.error("plan-qpadm-reruns requires --qpadm-rerun-manifest-json")

    manifest = load_qpadm_rerun_manifest_inputs(
        curation_path=args.target_curation,
        decisions_path=args.target_decisions,
    )
    manifest_path = write_qpadm_rerun_manifest_json(
        manifest, args.qpadm_rerun_manifest_json
    )
    print(f"qpadm_rerun_manifest={manifest_path}")
    print(f"qpadm_rerun_target_count={len(manifest.targets)}")
    for group in manifest.groups:
        print(
            "qpadm_rerun_group="
            f"{group.failure_reason},target_count={len(group.targets)}"
        )
    if args.qpadm_rerun_groups_out is not None:
        groups_path = write_qpadm_rerun_groups_tsv(
            manifest, args.qpadm_rerun_groups_out
        )
        print(f"qpadm_rerun_groups={groups_path}")
    return 0


def _run_plan_qpadm_run_command(
    args: argparse.Namespace, parser: argparse.ArgumentParser
) -> int:
    """Run the CLI external qpAdm planning command."""
    if args.genotype_prefix is None:
        parser.error("plan-qpadm-run requires --genotype-prefix")
    if args.aadr_groups is None:
        parser.error("plan-qpadm-run requires --aadr-groups")
    if args.qpadm_estimates is None:
        parser.error("plan-qpadm-run requires --qpadm-estimates")
    if args.qpadm_f2_dir is None:
        parser.error("plan-qpadm-run requires --qpadm-f2-dir")
    config = QpAdmRunConfig(
        genotype_prefix=resolve_qpadm_genotype_prefix(args.genotype_prefix),
        target_groups_path=args.aadr_groups,
        output_csv_path=args.qpadm_estimates,
        f2_dir=args.qpadm_f2_dir,
        runner_script_path=args.qpadm_runner,
    )
    if args.qpadm_manifest_json is not None:
        manifest_path = write_qpadm_run_manifest(config, args.qpadm_manifest_json)
        print(f"qpadm_manifest={manifest_path}")
    print("qpadm_command=" + " ".join(qpadm_run_command(config)))
    return 0


def _required_path(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
    argument_name: str,
) -> Path:
    """Return a required Path argument or fail through argparse."""
    value = getattr(args, argument_name)
    if value is None:
        parser.error(f"{args.command} requires --{argument_name.replace('_', '-')}")
    return cast(Path, value)
