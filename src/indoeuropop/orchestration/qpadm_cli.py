"""qpAdm planning command handlers for the IndoEuroPop CLI."""

from __future__ import annotations

import argparse

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

QPADM_COMMANDS = ("plan-qpadm-reruns", "plan-qpadm-run")


def run_qpadm_command(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
) -> int | None:
    """Run a qpAdm planning command or return `None` for unrelated commands."""
    if args.command == "plan-qpadm-reruns":
        return _run_plan_qpadm_reruns_command(args, parser)
    if args.command == "plan-qpadm-run":
        return _run_plan_qpadm_run_command(args, parser)
    return None


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
