"""CLI support for freezing structural SMC robustness evidence."""

from __future__ import annotations

import argparse
from pathlib import Path

from indoeuropop.orchestration.structural_smc_robustness_evidence import (
    StructuralSMCRobustnessEvidencePaths,
    write_structural_smc_robustness_evidence_manifest,
)
from indoeuropop.orchestration.structural_smc_robustness_models import (
    StructuralSMCRobustnessDecision,
)
from indoeuropop.reporting.structural_smc_caveat_dispositions import (
    write_structural_smc_caveat_disposition_validation_markdown,
)


def add_structural_smc_robustness_evidence_arguments(
    parser: argparse.ArgumentParser,
) -> None:
    """Register paths needed for a complete robustness evidence manifest."""
    parser.add_argument(
        "--target-fragility-report-md",
        type=Path,
        help="target-fragility Markdown report for the evidence package",
    )
    parser.add_argument(
        "--caveat-drilldown-report-md",
        type=Path,
        help="structural SMC caveat drilldown Markdown report",
    )
    parser.add_argument(
        "--robustness-decision-record-md",
        type=Path,
        help="tracked scientific decision record for the evidence package",
    )


def require_structural_smc_robustness_evidence_inputs(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
) -> None:
    """Require a complete evidence surface when a manifest is requested."""
    if args.manifest_json is None:
        return
    required = (
        "child_region_overrides",
        "robustness_decision_record_md",
        "target_fragility_report_md",
        "caveat_drilldown_csv",
        "caveat_drilldown_report_md",
        "caveat_dispositions_csv",
        "caveat_disposition_report_md",
    )
    for argument_name in required:
        if getattr(args, argument_name) is None:
            parser.error(
                f"{args.command} --manifest-json requires "
                f"--{argument_name.replace('_', '-')}"
            )


def write_requested_structural_smc_robustness_evidence(
    args: argparse.Namespace,
    decision: StructuralSMCRobustnessDecision,
) -> Path:
    """Write the requested disposition report and evidence manifest."""
    dispositions = decision.caveat_dispositions
    assert dispositions is not None
    write_structural_smc_caveat_disposition_validation_markdown(
        dispositions,
        args.caveat_disposition_report_md,
    )
    paths = StructuralSMCRobustnessEvidencePaths(
        candidate_config=args.child_region_overrides,
        decision_record_md=args.robustness_decision_record_md,
        target_fragility_decisions_csv=args.target_fragility_decisions_csv,
        target_fragility_report_md=args.target_fragility_report_md,
        fit_metric_summary_csv=args.fit_metric_sensitivity_summary_csv,
        fit_metric_report_md=args.fit_metric_sensitivity_report_md,
        source_model_summary_csv=args.source_model_sensitivity_summary_csv,
        source_model_report_md=args.source_model_sensitivity_report_md,
        caveat_drilldown_csv=args.caveat_drilldown_csv,
        caveat_drilldown_report_md=args.caveat_drilldown_report_md,
        caveat_dispositions_csv=args.caveat_dispositions_csv,
        caveat_disposition_report_md=args.caveat_disposition_report_md,
        robustness_summary_csv=decision.paths.summary_csv,
        robustness_report_md=decision.paths.report_md,
    )
    return write_structural_smc_robustness_evidence_manifest(
        decision,
        paths,
        args.manifest_json,
        command=args.command,
    )
