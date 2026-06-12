"""CLI handler for unified structural SMC robustness decisions."""

from __future__ import annotations

import argparse
from pathlib import Path

from indoeuropop.data.structural_smc_caveat_dispositions import (
    StructuralSMCCaveatDispositionValidationReport,
    initialize_structural_smc_caveat_disposition_template,
    validate_structural_smc_caveat_dispositions,
    write_structural_smc_caveat_dispositions_csv,
)
from indoeuropop.orchestration.structural_smc_caveat_drilldown import (
    run_structural_smc_caveat_drilldown,
    structural_smc_caveat_drilldown_paths_from_dir,
)
from indoeuropop.orchestration.structural_smc_caveat_drilldown_models import (
    StructuralSMCCaveatDrilldownReport,
)
from indoeuropop.orchestration.structural_smc_caveat_priority import (
    run_structural_smc_caveat_prioritization,
    structural_smc_caveat_priority_paths_from_dir,
)
from indoeuropop.orchestration.structural_smc_caveat_priority_models import (
    StructuralSMCCaveatPriorityReport,
)
from indoeuropop.orchestration.structural_smc_robustness import (
    run_structural_smc_robustness_decision,
    structural_smc_robustness_decision_paths_from_dir,
)
from indoeuropop.orchestration.structural_smc_robustness_models import (
    StructuralSMCRobustnessDecision,
)
from indoeuropop.reporting.structural_smc_caveat_dispositions import (
    write_structural_smc_caveat_disposition_validation_markdown,
)

STRUCTURAL_SMC_ROBUSTNESS_COMMANDS = (
    "initialize-structural-smc-caveat-dispositions",
    "prioritize-structural-smc-caveat-dispositions",
    "summarize-structural-smc-caveats",
    "validate-structural-smc-caveat-dispositions",
    "validate-structured-smc-robustness",
)


def add_structural_smc_robustness_arguments(parser: argparse.ArgumentParser) -> None:
    """Register unified structural SMC robustness CLI arguments."""
    parser.add_argument(
        "--robustness-candidate-name",
        default="structural-smc-candidate",
        help="candidate label to record in the unified robustness report",
    )
    parser.add_argument(
        "--robustness-output-dir",
        type=Path,
        help="directory for unified structural SMC robustness artifacts",
    )
    parser.add_argument(
        "--robustness-drilldown-output-dir",
        type=Path,
        help="directory for structural SMC caveat drilldown artifacts",
    )
    parser.add_argument(
        "--caveat-drilldown-csv",
        type=Path,
        help="structural SMC caveat drilldown CSV",
    )
    parser.add_argument(
        "--caveat-dispositions-csv",
        type=Path,
        help="reviewed structural SMC caveat dispositions CSV",
    )
    parser.add_argument(
        "--caveat-dispositions-out",
        type=Path,
        help="output path for initialized caveat disposition template CSV",
    )
    parser.add_argument(
        "--caveat-disposition-report-md",
        type=Path,
        help="optional Markdown validation report for caveat dispositions",
    )
    parser.add_argument(
        "--caveat-priority-output-dir",
        type=Path,
        help="directory for prioritized caveat review queue artifacts",
    )
    parser.add_argument(
        "--robustness-max-unstable-holdout-folds",
        type=int,
        default=0,
        help="maximum unstable folds allowed before blocking promotion",
    )
    parser.add_argument(
        "--target-fragility-decisions-csv",
        type=Path,
        help="target-fragility decisions CSV produced by the fragility gate",
    )
    parser.add_argument(
        "--fit-metric-sensitivity-summary-csv",
        type=Path,
        help="fit-metric sensitivity summary CSV",
    )
    parser.add_argument(
        "--fit-metric-sensitivity-report-md",
        type=Path,
        help="fit-metric sensitivity Markdown report",
    )
    parser.add_argument(
        "--source-model-sensitivity-summary-csv",
        type=Path,
        help="source-model sensitivity summary CSV",
    )
    parser.add_argument(
        "--source-model-sensitivity-report-md",
        type=Path,
        help="source-model sensitivity Markdown report",
    )


def run_structural_smc_robustness_command(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
) -> int | None:
    """Run the unified robustness command or return `None`."""
    if args.command not in STRUCTURAL_SMC_ROBUSTNESS_COMMANDS:
        return None
    if args.command == "initialize-structural-smc-caveat-dispositions":
        return _run_initialize_caveat_dispositions_command(args, parser)
    if args.command == "prioritize-structural-smc-caveat-dispositions":
        return _run_prioritize_caveat_dispositions_command(args, parser)
    if args.command == "summarize-structural-smc-caveats":
        return _run_caveat_drilldown_command(args, parser)
    if args.command == "validate-structural-smc-caveat-dispositions":
        return _run_validate_caveat_dispositions_command(args, parser)
    _require_inputs(args, parser)
    decision = run_structural_smc_robustness_decision(
        candidate_name=args.robustness_candidate_name,
        target_fragility_decisions_csv=args.target_fragility_decisions_csv,
        fit_metric_summary_csv=args.fit_metric_sensitivity_summary_csv,
        fit_metric_report_md=args.fit_metric_sensitivity_report_md,
        source_model_summary_csv=args.source_model_sensitivity_summary_csv,
        source_model_report_md=args.source_model_sensitivity_report_md,
        caveat_drilldown_csv=args.caveat_drilldown_csv,
        caveat_dispositions_csv=args.caveat_dispositions_csv,
        paths=structural_smc_robustness_decision_paths_from_dir(
            args.robustness_output_dir
        ),
        max_unstable_holdout_folds=args.robustness_max_unstable_holdout_folds,
    )
    _print_result(decision)
    return 0


def _run_initialize_caveat_dispositions_command(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
) -> int:
    """Initialize an undecided caveat disposition template."""
    if args.caveat_drilldown_csv is None:
        parser.error(f"{args.command} requires --caveat-drilldown-csv")
    if args.caveat_dispositions_out is None:
        parser.error(f"{args.command} requires --caveat-dispositions-out")
    dataset = initialize_structural_smc_caveat_disposition_template(
        args.caveat_drilldown_csv
    )
    output_path = write_structural_smc_caveat_dispositions_csv(
        dataset, args.caveat_dispositions_out
    )
    print("structural_smc_caveat_disposition_template=true")
    print(f"structural_smc_caveat_disposition_row_count={len(dataset.records)}")
    print(f"structural_smc_caveat_dispositions_csv={output_path}")
    return 0


def _run_prioritize_caveat_dispositions_command(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
) -> int:
    """Run a prioritized caveat disposition review queue."""
    if args.caveat_drilldown_csv is None:
        parser.error(f"{args.command} requires --caveat-drilldown-csv")
    if args.caveat_priority_output_dir is None:
        parser.error(f"{args.command} requires --caveat-priority-output-dir")
    report = run_structural_smc_caveat_prioritization(
        caveat_drilldown_csv=args.caveat_drilldown_csv,
        caveat_dispositions_csv=args.caveat_dispositions_csv,
        paths=structural_smc_caveat_priority_paths_from_dir(
            args.caveat_priority_output_dir
        ),
    )
    _print_priority_result(report)
    return 0


def _run_caveat_drilldown_command(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
) -> int:
    """Run the caveat drilldown command."""
    _require_drilldown_inputs(args, parser)
    report = run_structural_smc_caveat_drilldown(
        target_fragility_decisions_csv=args.target_fragility_decisions_csv,
        fit_metric_summary_csv=args.fit_metric_sensitivity_summary_csv,
        source_model_summary_csv=args.source_model_sensitivity_summary_csv,
        paths=structural_smc_caveat_drilldown_paths_from_dir(
            args.robustness_drilldown_output_dir
        ),
    )
    _print_drilldown_result(report)
    return 0


def _run_validate_caveat_dispositions_command(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
) -> int:
    """Validate reviewed caveat dispositions against a drilldown queue."""
    if args.caveat_drilldown_csv is None:
        parser.error(f"{args.command} requires --caveat-drilldown-csv")
    if args.caveat_dispositions_csv is None:
        parser.error(f"{args.command} requires --caveat-dispositions-csv")
    report = validate_structural_smc_caveat_dispositions(
        drilldown_csv=args.caveat_drilldown_csv,
        dispositions_csv=args.caveat_dispositions_csv,
    )
    if args.caveat_disposition_report_md is not None:
        write_structural_smc_caveat_disposition_validation_markdown(
            report, args.caveat_disposition_report_md
        )
    _print_caveat_disposition_result(report)
    return 0


def _require_inputs(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
) -> None:
    """Raise argparse errors for missing robustness decision inputs."""
    required = (
        "robustness_output_dir",
        "target_fragility_decisions_csv",
        "fit_metric_sensitivity_summary_csv",
        "fit_metric_sensitivity_report_md",
        "source_model_sensitivity_summary_csv",
        "source_model_sensitivity_report_md",
    )
    for argument_name in required:
        if getattr(args, argument_name) is None:
            parser.error(f"{args.command} requires --{argument_name.replace('_', '-')}")
    if args.caveat_dispositions_csv is not None and args.caveat_drilldown_csv is None:
        parser.error(f"{args.command} requires --caveat-drilldown-csv")


def _require_drilldown_inputs(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
) -> None:
    """Raise argparse errors for missing caveat drilldown inputs."""
    required = (
        "robustness_drilldown_output_dir",
        "target_fragility_decisions_csv",
        "fit_metric_sensitivity_summary_csv",
        "source_model_sensitivity_summary_csv",
    )
    for argument_name in required:
        if getattr(args, argument_name) is None:
            parser.error(f"{args.command} requires --{argument_name.replace('_', '-')}")


def _print_result(decision: StructuralSMCRobustnessDecision) -> None:
    """Print compact machine-readable robustness decision summary lines."""
    print("structural_smc_robustness=true")
    print(f"structural_smc_robustness_status={decision.status}")
    print(f"structural_smc_robustness_recommendation={decision.recommendation}")
    print(f"structural_smc_robustness_blocker_count={decision.blocker_count}")
    print(f"structural_smc_robustness_caution_count={decision.caution_count}")
    print(f"structural_smc_robustness_summary_csv={decision.paths.summary_csv}")
    print(f"structural_smc_robustness_report_md={decision.paths.report_md}")
    report = decision.caveat_dispositions
    if report is not None:
        print(
            f"structural_smc_caveat_disposition_reviewed_count={report.reviewed_count}"
        )
        print(
            "structural_smc_caveat_disposition_unresolved_count="
            f"{report.unresolved_count}"
        )
        print(
            f"structural_smc_caveat_disposition_blocking_count={report.blocking_count}"
        )


def _print_drilldown_result(report: StructuralSMCCaveatDrilldownReport) -> None:
    """Print compact machine-readable caveat drilldown summary lines."""
    print("structural_smc_caveat_drilldown=true")
    print(f"structural_smc_caveat_drilldown_row_count={report.row_count}")
    for caveat_type in report.caveat_types:
        print(
            "structural_smc_caveat_drilldown_type="
            f"{caveat_type},count={report.count_by_type(caveat_type)}"
        )
    print(f"structural_smc_caveat_drilldown_csv={report.paths.detail_csv}")
    print(f"structural_smc_caveat_drilldown_report_md={report.paths.report_md}")


def _print_caveat_disposition_result(
    report: StructuralSMCCaveatDispositionValidationReport,
) -> None:
    """Print compact machine-readable caveat disposition validation lines."""
    print("structural_smc_caveat_disposition_validation=true")
    print(f"structural_smc_caveat_disposition_valid={str(report.valid).lower()}")
    print(
        "structural_smc_caveat_disposition_drilldown_count="
        f"{report.drilldown_caveat_count}"
    )
    print(
        "structural_smc_caveat_disposition_reviewed_count=" f"{report.reviewed_count}"
    )
    print(
        "structural_smc_caveat_disposition_unresolved_count="
        f"{report.unresolved_count}"
    )
    print(
        "structural_smc_caveat_disposition_blocking_count=" f"{report.blocking_count}"
    )
    print("structural_smc_caveat_disposition_issue_count=" f"{len(report.issues)}")


def _print_priority_result(report: StructuralSMCCaveatPriorityReport) -> None:
    """Print compact machine-readable caveat priority summary lines."""
    print("structural_smc_caveat_prioritization=true")
    print(f"structural_smc_caveat_priority_row_count={report.row_count}")
    print(f"structural_smc_caveat_priority_unresolved_count={report.unresolved_count}")
    print(f"structural_smc_caveat_priority_reviewed_count={report.reviewed_count}")
    print(f"structural_smc_caveat_priority_blocking_count={report.blocking_count}")
    print(f"structural_smc_caveat_priority_csv={report.paths.priority_csv}")
    print(f"structural_smc_caveat_priority_report_md={report.paths.report_md}")
    top = report.rows[0]
    print(
        "structural_smc_caveat_priority_top="
        f"rank={top.review_rank},band={top.priority_band},"
        f"score={top.priority_score:.6g},type={top.caveat_type}"
    )
