"""CLI wrapper for the real AADR plus qpAdm target workflow."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import cast

from indoeuropop.data.real_targets import (
    AADRQpAdmTargetWorkflowConfig,
    run_aadr_qpadm_target_workflow,
)


def run_build_aadr_qpadm_targets_command(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
) -> int:
    """Run the CLI workflow that builds real AADR-derived target observations."""
    config = AADRQpAdmTargetWorkflowConfig(
        aadr_dir=_required_path(args, parser, "aadr_dir"),
        aadr_groups_path=_required_path(args, parser, "aadr_groups"),
        qpadm_estimates_path=_required_path(args, parser, "qpadm_estimates"),
        sample_metadata_path=_required_path(args, parser, "sample_metadata_out"),
        target_curation_path=_required_path(args, parser, "target_curation_out"),
        ancestry_estimates_path=_required_path(
            args,
            parser,
            "ancestry_estimates_out",
        ),
        target_output_path=_required_path(args, parser, "target_output"),
        diagnostics_json_path=args.target_diagnostics_json,
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
    result = run_aadr_qpadm_target_workflow(config)
    diagnostics = result.diagnostics
    print(f"selected_sample_count={diagnostics.selected_sample_count}")
    print(f"raw_qpadm_row_count={diagnostics.raw_qpadm_row_count}")
    print(
        f"retained_sample_estimate_count={diagnostics.retained_sample_estimate_count}"
    )
    print(f"retained_target_count={diagnostics.retained_target_count}")
    print(f"dropped_target_count={diagnostics.dropped_target_count}")
    if diagnostics.decision_deferred_target_count:
        print(
            "decision_deferred_target_count="
            f"{diagnostics.decision_deferred_target_count}"
        )
    print(f"target_observation_count={diagnostics.target_observation_count}")
    print(f"sample_metadata={config.sample_metadata_path}")
    print(f"target_curation={config.target_curation_path}")
    print(f"sample_ancestry_estimates={config.ancestry_estimates_path}")
    print(f"target_output={config.target_output_path}")
    if config.diagnostics_json_path is not None:
        print(f"target_diagnostics={config.diagnostics_json_path}")
    for target_id in diagnostics.dropped_target_ids:
        print(f"dropped_target={target_id}")
    for target_id in diagnostics.decision_deferred_target_ids:
        print(f"decision_deferred_target={target_id}")
    return 0


def _required_path(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
    argument_name: str,
) -> Path:
    """Return a required Path argument or fail through argparse."""
    value = getattr(args, argument_name)
    if value is None:
        parser.error(
            "build-aadr-qpadm-targets requires " f"--{argument_name.replace('_', '-')}"
        )
    return cast(Path, value)
